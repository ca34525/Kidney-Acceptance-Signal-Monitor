"""Compare earlier public inputs with later reported transplant receipt.

One prediction describes one program and listing group. Fits use only the
source-approved earlier pairs supplied by the panel; errors retain the exact
percentage derived from published donor components.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from scipy.special import expit  # type: ignore[import-untyped]
from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
from sklearn.linear_model import Ridge  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from kasm.patient_journey.modeling import PatientJourneyModelError, build_feature_matrix
from kasm.patient_journey.receipt_config import (
    BASELINES,
    FEATURE_GROUPS,
    ReceiptConfig,
    ReceiptError,
    validate_receipt_config,
)

type Pair = tuple[str, str]
type Fold = tuple[Pair, tuple[Pair, ...]]
type Row = Mapping[str, object]

_ALLOWED_TRAINING = {
    ("2205", "2505"): (("1905", "2205"),),
    ("2305", "2605"): (("1905", "2205"),),
}
_KNOWN_PAIRS = frozenset((*_ALLOWED_TRAINING, ("1905", "2205"), ("2105", "2405")))
_MODELS = (*BASELINES, *(name for name, _ in FEATURE_GROUPS))
_FULL = "history_access_acceptance"
_GATE_COMPARATORS = (*BASELINES, "history_access")


@dataclass(frozen=True)
class ReceiptPrediction:
    """A program's derived receipt percentage and one model's error in points."""

    program_key: str
    feature_release_code: str
    target_release_code: str
    model: str
    training_pairs: tuple[Pair, ...]
    target_n: int
    derived_receipt_percent: float
    predicted_proportion: float
    predicted_percent: float
    absolute_error_percentage_points: float
    signed_error_percentage_points: float


@dataclass(frozen=True)
class ReceiptOriginSummary:
    """Average errors among programs visible at one publication origin."""

    feature_release_code: str
    target_release_code: str
    n: int
    listing_n: int
    mean_absolute_error_percentage_points: float
    mean_signed_error_percentage_points: float
    volume_weighted_mae_percentage_points: float


@dataclass(frozen=True)
class ReceiptSummary:
    """Each origin has equal weight, including the listing-count-weighted summary."""

    n: int
    origins: tuple[ReceiptOriginSummary, ...]
    mean_absolute_error_percentage_points: float
    mean_signed_error_percentage_points: float
    volume_weighted_mae_percentage_points: float


@dataclass(frozen=True)
class ReceiptBootstrap:
    """Descriptive error difference; negative values favor the added inputs."""

    point_estimate: float
    lower: float
    upper: float
    resamples: int
    seed: int
    attempted_draws: int
    rejected_draws: int


@dataclass(frozen=True)
class ReceiptContrast:
    """The fixed paired comparison of two models on the same program groups."""

    challenger: str
    comparator: str
    interval: ReceiptBootstrap


@dataclass(frozen=True)
class ReceiptContinuation:
    """Whether the prespecified project-use rule passes, with every failure reason."""

    passed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ReceiptFitParameters:
    """Plain numeric evidence of what was learned from each earlier training fold."""

    feature_release_code: str
    target_release_code: str
    model: str
    training_pairs: tuple[Pair, ...]
    feature_names: tuple[str, ...]
    coefficients: tuple[float, ...]
    intercept: float
    imputer_statistics: tuple[float, ...]
    scaler_mean: tuple[float, ...]
    scaler_scale: tuple[float, ...]


@dataclass(frozen=True)
class ReceiptEvaluation:
    """All fixed comparisons; larger-N summaries reuse the original predictions."""

    predictions: tuple[ReceiptPrediction, ...]
    summaries: dict[str, ReceiptSummary]
    contrasts: tuple[ReceiptContrast, ...]
    continuation: ReceiptContinuation
    sensitivities: dict[int, dict[str, ReceiptSummary]]
    fit_parameters: dict[str, ReceiptFitParameters]


def _text(row: Row, name: str) -> str:
    value = row.get(name)
    if not isinstance(value, str) or not value:
        raise ReceiptError(f"Receipt model field {name} must be nonempty text.")
    return value


def _number(row: Row, name: str) -> float:
    value = row.get(name)
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ReceiptError(f"Receipt model field {name} must be finite numeric evidence.")
    return float(value)


def _count(row: Row, name: str, minimum: int) -> int:
    value = row.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ReceiptError(f"Receipt model field {name} must be a whole count >= {minimum}.")
    return value


def _proportion(row: Row, name: str) -> float:
    value = _number(row, name)
    if not 0 <= value <= 1:
        raise ReceiptError(f"Receipt model field {name} must be in [0, 1].")
    return value


def _smoothed_logit(p: float, n: int) -> float:
    return math.log((n * p + 0.5) / (n * (1 - p) + 0.5))


def _validate_target_and_history(row: Row, minimum: int) -> None:
    n = _count(row, "target_n", minimum)
    p = _proportion(row, "target_proportion")
    percent = _number(row, "derived_receipt_percent")
    if not 0 <= percent <= 100 or not math.isclose(percent, p * 100, abs_tol=1e-10, rel_tol=0):
        raise ReceiptError("Derived receipt percentage and target proportion disagree.")
    if not math.isclose(
        _number(row, "target_logit"), _smoothed_logit(p, n), abs_tol=1e-12, rel_tol=0
    ):
        raise ReceiptError("Target logit disagrees with fractional smoothing of derived receipt.")
    prior_n = _count(row, "prior_target_n", 1)
    prior = _proportion(row, "prior_target_proportion")
    if not math.isclose(
        _number(row, "prior_target_logit"),
        _smoothed_logit(prior, prior_n),
        abs_tol=1e-12,
        rel_tol=0,
    ):
        raise ReceiptError("Prior receipt logit must use its own source listing count.")
    _proportion(row, "historical_mean_target_proportion")


def _prepare_rows(rows: Sequence[Row], config: ReceiptConfig) -> dict[Pair, tuple[Row, ...]]:
    seen: set[tuple[str, str, str]] = set()
    by_pair: dict[Pair, list[Row]] = {}
    for row in rows:
        program = _text(row, "program_key")
        pair = (_text(row, "feature_release_code"), _text(row, "target_release_code"))
        if pair not in _KNOWN_PAIRS:
            raise ReceiptError(f"Receipt model row has an unknown study pair {pair}.")
        key = (program, *pair)
        if key in seen:
            raise ReceiptError(f"Receipt model rows duplicate {key}.")
        seen.add(key)
        eligible = row.get("primary_analytic_eligible")
        if not isinstance(eligible, bool):
            raise ReceiptError("Receipt analytic eligibility must be an explicit boolean.")
        if eligible:
            _validate_target_and_history(row, config.primary_min_target_n)
            by_pair.setdefault(pair, []).append(row)
    return {
        pair: tuple(sorted(values, key=lambda row: _text(row, "program_key")))
        for pair, values in by_pair.items()
    }


def _validate_folds(folds: tuple[Fold, ...]) -> None:
    if not folds:
        raise ReceiptError("Receipt evaluation requires a source-approved training fold.")
    seen: set[Pair] = set()
    for evaluation, training in folds:
        if evaluation in seen or evaluation not in _ALLOWED_TRAINING:
            raise ReceiptError("Receipt evaluation fold is duplicate or outside the fixed study.")
        seen.add(evaluation)
        if (
            not training
            or len(training) != len(set(training))
            or evaluation in training
            or not set(training).issubset(_ALLOWED_TRAINING[evaluation])
            or ("1905", "2205") not in training
        ):
            raise ReceiptError("Receipt training pairs violate the fixed publication-origin map.")


def _prediction(row: Row, model: str, p: float, training: tuple[Pair, ...]) -> ReceiptPrediction:
    if not math.isfinite(p) or not 0 <= p <= 1:
        raise ReceiptError("Receipt predictions must be finite proportions in [0, 1].")
    percent = _number(row, "derived_receipt_percent")
    predicted = 100 * p
    signed = predicted - percent
    return ReceiptPrediction(
        program_key=_text(row, "program_key"),
        feature_release_code=_text(row, "feature_release_code"),
        target_release_code=_text(row, "target_release_code"),
        model=model,
        training_pairs=training,
        target_n=_count(row, "target_n", 1),
        derived_receipt_percent=percent,
        predicted_proportion=p,
        predicted_percent=predicted,
        absolute_error_percentage_points=abs(signed),
        signed_error_percentage_points=signed,
    )


def _fit_fold(
    training_rows: tuple[Row, ...],
    evaluation_rows: tuple[Row, ...],
    training: tuple[Pair, ...],
    config: ReceiptConfig,
) -> tuple[list[ReceiptPrediction], dict[str, ReceiptFitParameters]]:
    result: list[ReceiptPrediction] = []
    parameters: dict[str, ReceiptFitParameters] = {}
    targets = np.asarray([_number(row, "target_logit") for row in training_rows])
    for model, features in config.feature_groups:
        pipeline = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                ("scaler", StandardScaler()),
                (
                    "ridge",
                    Ridge(
                        alpha=config.alpha,
                        solver=config.solver,
                        tol=config.tolerance,
                        max_iter=config.max_iterations,
                    ),
                ),
            ]
        )
        try:
            training_matrix = build_feature_matrix(training_rows, features)
            evaluation_matrix = build_feature_matrix(evaluation_rows, features)
        except PatientJourneyModelError as exc:
            raise ReceiptError(str(exc)) from exc
        pipeline.fit(training_matrix, targets)
        origin = _text(evaluation_rows[0], "feature_release_code")
        target = _text(evaluation_rows[0], "target_release_code")
        fit = ReceiptFitParameters(
            feature_release_code=origin,
            target_release_code=target,
            model=model,
            training_pairs=training,
            feature_names=features,
            coefficients=tuple(float(value) for value in pipeline.named_steps["ridge"].coef_),
            intercept=float(pipeline.named_steps["ridge"].intercept_),
            imputer_statistics=tuple(
                float(value) for value in pipeline.named_steps["imputer"].statistics_
            ),
            scaler_mean=tuple(float(value) for value in pipeline.named_steps["scaler"].mean_),
            scaler_scale=tuple(float(value) for value in pipeline.named_steps["scaler"].scale_),
        )
        if not all(
            math.isfinite(value)
            for value in (
                fit.intercept,
                *fit.coefficients,
                *fit.imputer_statistics,
                *fit.scaler_mean,
                *fit.scaler_scale,
            )
        ):
            raise ReceiptError("Receipt fitted parameter evidence must be finite.")
        parameters[f"{origin}->{target}/{model}"] = fit
        proportions = expit(pipeline.predict(evaluation_matrix))
        result.extend(
            _prediction(row, model, float(p), training)
            for row, p in zip(evaluation_rows, proportions, strict=True)
        )
    return result, parameters


def _key(row: ReceiptPrediction) -> tuple[str, str, str]:
    return row.program_key, row.feature_release_code, row.target_release_code


def _validate_predictions(rows: Sequence[ReceiptPrediction]) -> None:
    if not rows or len({row.model for row in rows}) != 1:
        raise ReceiptError("Receipt summary requires one model and at least one prediction.")
    if len({_key(row) for row in rows}) != len(rows):
        raise ReceiptError("Receipt predictions duplicate program/origin/target rows.")
    for row in rows:
        numbers = (
            row.derived_receipt_percent,
            row.predicted_proportion,
            row.predicted_percent,
            row.absolute_error_percentage_points,
            row.signed_error_percentage_points,
        )
        if (
            isinstance(row.target_n, bool)
            or not isinstance(row.target_n, int)
            or row.target_n <= 0
            or not all(math.isfinite(value) for value in numbers)
            or not 0 <= row.derived_receipt_percent <= 100
            or not 0 <= row.predicted_proportion <= 1
        ):
            raise ReceiptError("Receipt prediction evidence is outside its valid numeric bounds.")
        expected = row.predicted_percent - row.derived_receipt_percent
        if any(
            not math.isclose(left, right, rel_tol=0, abs_tol=1e-10)
            for left, right in (
                (row.predicted_percent, 100 * row.predicted_proportion),
                (row.signed_error_percentage_points, expected),
                (row.absolute_error_percentage_points, abs(expected)),
            )
        ):
            raise ReceiptError("Receipt prediction errors disagree with the derived target.")


def summarize_receipt(predictions: Sequence[ReceiptPrediction]) -> ReceiptSummary:
    """Average each origin separately so a larger program population cannot dominate."""
    _validate_predictions(predictions)
    groups: dict[Pair, list[ReceiptPrediction]] = {}
    for row in sorted(predictions, key=_key):
        groups.setdefault((row.feature_release_code, row.target_release_code), []).append(row)
    origins = []
    for (feature, target), rows in sorted(groups.items()):
        count = len(rows)
        listing_n = sum(row.target_n for row in rows)
        origins.append(
            ReceiptOriginSummary(
                feature,
                target,
                count,
                listing_n,
                sum(row.absolute_error_percentage_points for row in rows) / count,
                sum(row.signed_error_percentage_points for row in rows) / count,
                sum(row.target_n * row.absolute_error_percentage_points for row in rows)
                / listing_n,
            )
        )
    return ReceiptSummary(
        len(predictions),
        tuple(origins),
        sum(row.mean_absolute_error_percentage_points for row in origins) / len(origins),
        sum(row.mean_signed_error_percentage_points for row in origins) / len(origins),
        sum(row.volume_weighted_mae_percentage_points for row in origins) / len(origins),
    )


def _paired(
    challenger: Sequence[ReceiptPrediction], comparator: Sequence[ReceiptPrediction]
) -> tuple[tuple[ReceiptPrediction, ReceiptPrediction], ...]:
    _validate_predictions(challenger)
    _validate_predictions(comparator)
    left = {_key(row): row for row in challenger}
    right = {_key(row): row for row in comparator}
    if left.keys() != right.keys():
        raise ReceiptError("Paired receipt comparison requires identical program/origin rows.")
    for key in left:
        if (
            left[key].target_n != right[key].target_n
            or left[key].derived_receipt_percent != right[key].derived_receipt_percent
        ):
            raise ReceiptError("Paired receipt comparison has different target evidence.")
    return tuple((left[key], right[key]) for key in sorted(left))


def paired_receipt_bootstrap(
    challenger: Sequence[ReceiptPrediction],
    comparator: Sequence[ReceiptPrediction],
    *,
    resamples: int = 2000,
    seed: int = 20260908,
    percentiles: tuple[float, float] = (2.5, 97.5),
    max_attempt_factor: int = 100,
) -> ReceiptBootstrap:
    """Sample whole programs; redraw if a sample would drop an evaluation origin."""
    if (
        isinstance(resamples, bool)
        or not isinstance(resamples, int)
        or resamples < 1
        or isinstance(max_attempt_factor, bool)
        or not isinstance(max_attempt_factor, int)
        or max_attempt_factor < 1
        or not 0 <= percentiles[0] < percentiles[1] <= 100
    ):
        raise ReceiptError("Receipt bootstrap needs positive draws and ordered percentiles.")
    pairs = _paired(challenger, comparator)
    programs = sorted({left.program_key for left, _ in pairs})
    origins = sorted({(left.feature_release_code, left.target_release_code) for left, _ in pairs})
    program_index = {program: index for index, program in enumerate(programs)}
    origin_index = {origin: index for index, origin in enumerate(origins)}
    differences = np.zeros((len(programs), len(origins)))
    counts = np.zeros_like(differences)
    for left, right in pairs:
        i = program_index[left.program_key]
        j = origin_index[(left.feature_release_code, left.target_release_code)]
        differences[i, j] += (
            left.absolute_error_percentage_points - right.absolute_error_percentage_points
        )
        counts[i, j] += 1
    generator = np.random.default_rng(seed)
    values: list[float] = []
    attempted = 0
    while len(values) < resamples and attempted < resamples * max_attempt_factor:
        attempted += 1
        sample = generator.integers(0, len(programs), size=len(programs))
        sampled_counts = counts[sample].sum(axis=0)
        if np.any(sampled_counts == 0):
            continue
        values.append(float(np.mean(differences[sample].sum(axis=0) / sampled_counts)))
    if len(values) != resamples:
        raise ReceiptError("Receipt bootstrap exhausted its attempt limit retaining every origin.")
    lower, upper = np.percentile(values, percentiles, method="linear")
    return ReceiptBootstrap(
        float(np.mean(differences.sum(axis=0) / counts.sum(axis=0))),
        float(lower),
        float(upper),
        resamples,
        seed,
        attempted,
        attempted - resamples,
    )


def _group_models(
    predictions: Sequence[ReceiptPrediction],
) -> dict[str, tuple[ReceiptPrediction, ...]]:
    groups = {model: tuple(row for row in predictions if row.model == model) for model in _MODELS}
    if len(predictions) != sum(len(rows) for rows in groups.values()):
        raise ReceiptError("Receipt predictions include an unplanned model.")
    for model in _MODELS:
        _paired(groups[_FULL], groups[model])
    return groups


def _bias_failures(
    full: ReceiptSummary, comparator: ReceiptSummary, name: str, config: ReceiptConfig
) -> list[str]:
    reasons = []
    if (
        abs(full.mean_signed_error_percentage_points)
        - abs(comparator.mean_signed_error_percentage_points)
        > config.maximum_bias_worsening_points + 1e-12
    ):
        reasons.append(
            f"Absolute origin-balanced bias worsens by more than 0.5 points versus {name}."
        )
    for left, right in zip(full.origins, comparator.origins, strict=True):
        origin = left.feature_release_code
        if (
            left.mean_absolute_error_percentage_points
            >= right.mean_absolute_error_percentage_points
        ):
            reasons.append(f"No absolute-error improvement versus {name} at origin {origin}.")
        if (
            abs(left.mean_signed_error_percentage_points)
            - abs(right.mean_signed_error_percentage_points)
            > config.maximum_bias_worsening_points + 1e-12
        ):
            reasons.append(
                f"Absolute bias worsens by more than 0.5 points versus {name} at {origin}."
            )
    return reasons


def receipt_continuation_gate(
    predictions: Sequence[ReceiptPrediction], config: ReceiptConfig
) -> ReceiptContinuation:
    """Apply project continuation limits without choosing models from favorable scores."""
    validate_receipt_config(config)
    groups = _group_models(predictions)
    summaries = {model: summarize_receipt(rows) for model, rows in groups.items()}
    full = summaries[_FULL]
    reasons = []
    if len(full.origins) < config.minimum_evaluation_origins:
        reasons.append("Fewer than two usable evaluation origins.")
    for origin in full.origins:
        if abs(origin.mean_signed_error_percentage_points) > config.maximum_absolute_bias_points:
            reasons.append(
                f"Absolute signed error exceeds 2 points at {origin.feature_release_code}."
            )
    for name in _GATE_COMPARATORS:
        comparator = summaries[name]
        gain = (
            comparator.mean_absolute_error_percentage_points
            - full.mean_absolute_error_percentage_points
        )
        if gain + 1e-12 < config.minimum_improvement_points:
            reasons.append(f"Absolute-error improvement is below 0.5 points versus {name}.")
        if gain + 1e-12 < (
            config.minimum_relative_improvement * comparator.mean_absolute_error_percentage_points
        ):
            reasons.append(f"Absolute-error improvement is below 5% versus {name}.")
        reasons.extend(_bias_failures(full, comparator, name, config))
    return ReceiptContinuation(not reasons, tuple(reasons))


def evaluate_receipt(
    rows: Sequence[Row], config: ReceiptConfig, folds: tuple[Fold, ...]
) -> ReceiptEvaluation:
    """Fit the approved earlier pairs once and return all five matched comparisons.

    The caller must validate source identities, publication and measurement
    dates before invoking this function. This boundary separately rejects an
    unpublished training-pair map or inconsistent numerical target evidence.
    """
    validate_receipt_config(config)
    _validate_folds(folds)
    by_pair = _prepare_rows(rows, config)
    active_folds = []
    for evaluation, training in sorted(folds):
        training = tuple(sorted(training))
        if any(not by_pair.get(pair) for pair in training):
            raise ReceiptError("Receipt training fold lacks eligible rows for a specified pair.")
        if not by_pair.get(evaluation):
            raise ReceiptError("Receipt evaluation fold has no eligible rows.")
        active_folds.append((evaluation, training))
    predictions: list[ReceiptPrediction] = []
    fit_parameters: dict[str, ReceiptFitParameters] = {}
    for evaluation, _ in active_folds:
        for row in by_pair[evaluation]:
            predictions.extend(
                _prediction(row, model, _proportion(row, field), ())
                for model, field in (
                    ("persistence", "prior_target_proportion"),
                    ("historical_mean", "historical_mean_target_proportion"),
                )
            )
    for evaluation, training in active_folds:
        fitted_predictions, parameters = _fit_fold(
            tuple(row for pair in training for row in by_pair[pair]),
            by_pair[evaluation],
            training,
            config,
        )
        predictions.extend(fitted_predictions)
        fit_parameters.update(parameters)
    ordered = tuple(sorted(predictions, key=lambda row: (*_key(row), row.model)))
    groups = _group_models(ordered)
    summaries = {model: summarize_receipt(values) for model, values in groups.items()}
    contrasts = tuple(
        ReceiptContrast(
            challenger,
            comparator,
            paired_receipt_bootstrap(
                groups[challenger],
                groups[comparator],
                resamples=config.bootstrap_resamples,
                seed=config.bootstrap_seed,
                percentiles=config.bootstrap_percentiles,
                max_attempt_factor=config.bootstrap_max_attempt_factor,
            ),
        )
        for challenger, comparator in config.contrasts
    )
    sensitivities = {
        minimum: {
            model: summarize_receipt(selected)
            for model, values in groups.items()
            if (selected := tuple(row for row in values if row.target_n >= minimum))
        }
        for minimum in config.sensitivity_min_target_n
    }
    return ReceiptEvaluation(
        ordered,
        summaries,
        contrasts,
        receipt_continuation_gate(ordered, config),
        sensitivities,
        fit_parameters,
    )
