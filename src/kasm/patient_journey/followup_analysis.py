"""Explain the original V2 calculation and compare the fixed count-removed models.

Each evaluated row is a program and July–June listing group. Published outcome
percentages remain the scoring target. Earlier training rows alone determine
replacement values, scales and fitted coefficients; these already-seen outcomes
cannot support model promotion or evidence about a new period.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace

import numpy as np
from scipy.special import expit  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]

from kasm.patient_journey.config import (
    BASELINES,
    FEATURE_GROUPS,
    PatientJourneyBootstrapDesign,
    PatientJourneyConfig,
    PatientJourneyRidgeDesign,
)
from kasm.patient_journey.evaluation import (
    EvaluationPrediction,
    assign_within_release_volume_quartiles,
    paired_clustered_bootstrap_interval,
    summarize_predictions,
)
from kasm.patient_journey.followup_config import FollowupConfig, validate_followup_config
from kasm.patient_journey.modeling import (
    _fit_pipeline,
    _prediction,
    build_feature_matrix,
    generate_baseline_predictions,
    generate_ridge_predictions,
)

Row = Mapping[str, object]
RowKey = tuple[str, str, str]
PredictionKey = tuple[str, str, str, str]


class FollowupAnalysisError(ValueError):
    """Raised when reconstruction or the fixed comparison loses its source meaning."""


@dataclass(frozen=True)
class FollowupAnalysis:
    """Same-program predictions and JSON-ready descriptive evidence; no fitted models."""

    predictions: tuple[EvaluationPrediction, ...]
    evidence: dict[str, object]


def _text(row: Row, field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise FollowupAnalysisError(f"Field {field!r} must be non-empty text.")
    return value


def _number(row: Row, field: str) -> float:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise FollowupAnalysisError(f"Field {field!r} must be numeric.")
    if not math.isfinite(value):
        raise FollowupAnalysisError(f"Field {field!r} must be finite.")
    return float(value)


def _key(row: Row) -> RowKey:
    return (
        _text(row, "program_key"),
        _text(row, "feature_release_code"),
        _text(row, "target_release_code"),
    )


def _key_payload(key: RowKey) -> dict[str, object]:
    return dict(
        zip(("program_key", "feature_release_code", "target_release_code"), key, strict=True)
    )


def _validate_contract(original: PatientJourneyConfig, config: FollowupConfig) -> None:
    if config.feature_groups != tuple(
        (name, tuple(field for field in fields if field != "historical_target_count"))
        for name, fields in FEATURE_GROUPS
    ):
        raise FollowupAnalysisError("Revised feature groups must remove only report count.")
    validate_followup_config(config)
    design = original.model_design
    ridge = PatientJourneyRidgeDesign(
        1.0, "lsqr", 1e-8, 10000, False, ("2205", "2505"), (("1905", "2205"),)
    )
    bootstrap = PatientJourneyBootstrapDesign(
        2000,
        20260904,
        "program_key",
        (2.5, 97.5),
        "linear",
        "challenger_minus_comparator_balanced_mae",
    )
    if (
        original.analysis_id != "kidney_patient_journey_v2"
        or original.target_column != "SAL_TOTFTX_C18"
        or original.temporal_design.evaluation_mode != "strict_vintage"
        or original.eligibility.primary_min_target_n != 10
        or design.baselines != BASELINES
        or tuple((group.name, group.features) for group in design.feature_groups) != FEATURE_GROUPS
        or design.ridge != ridge
        or design.bootstrap != bootstrap
    ):
        raise FollowupAnalysisError("Original V2 settings disagree with the fixed comparison.")


def _populations(
    rows: Sequence[Row], original: PatientJourneyConfig
) -> tuple[tuple[Row, ...], tuple[Row, ...], dict[str, object]]:
    indexed: dict[RowKey, Row] = {}
    for row in rows:
        key = _key(row)
        if key in indexed:
            raise FollowupAnalysisError(f"Panel has duplicate program/release keys: {key!r}.")
        if not isinstance(row.get("primary_analytic_eligible"), bool):
            raise FollowupAnalysisError("Original analytic eligibility must be boolean.")
        indexed[key] = row
    training: list[Row] = []
    evaluation: list[Row] = []
    excluded: list[dict[str, object]] = []
    for key, row in sorted(indexed.items()):
        pair = key[1:]
        eligible = row["primary_analytic_eligible"]
        if eligible and pair in original.model_design.ridge.training_pairs:
            training.append(row)
        elif eligible and pair == original.model_design.ridge.evaluation_pair:
            evaluation.append(row)
        else:
            excluded.append(
                {
                    **_key_payload(key),
                    "primary_analytic_eligible": eligible,
                    "reason": "originally_ineligible" if not eligible else "outside_fixed_split",
                }
            )
    if not training or not evaluation:
        raise FollowupAnalysisError("Both fixed training and evaluation populations are required.")
    return (
        tuple(training),
        tuple(evaluation),
        {
            "training": [
                {**_key_payload(_key(row)), "primary_analytic_eligible": True} for row in training
            ],
            "evaluation": [
                {**_key_payload(_key(row)), "primary_analytic_eligible": True} for row in evaluation
            ],
            "excluded": excluded,
        },
    )


def _stored_index(stored: Sequence[Row], pair: tuple[str, str]) -> dict[PredictionKey, Row]:
    indexed: dict[PredictionKey, Row] = {}
    for row in stored:
        row_key = _key(row)
        model = _text(row, "model")
        if row_key[1:] != pair:
            continue
        key = (*row_key, model)
        if key in indexed:
            raise FollowupAnalysisError(f"Stored prediction keys duplicate {key!r}.")
        indexed[key] = row
    return indexed


def _compare_stored(
    predictions: Sequence[EvaluationPrediction], stored: Sequence[Row], tolerance: float
) -> dict[str, object]:
    expected = {
        (row.program_key, row.feature_release_code, row.target_release_code, row.model): row
        for row in predictions
    }
    actual = _stored_index(stored, ("2205", "2505"))
    if set(expected) != set(actual):
        raise FollowupAnalysisError("Stored and reconstructed prediction keys must match exactly.")
    maximum = 0.0
    for key, prediction in expected.items():
        row = actual[key]
        target_n = row.get("target_n")
        if (
            isinstance(target_n, bool)
            or not isinstance(target_n, int)
            or target_n != prediction.target_n
            or _number(row, "target_published_percent") != prediction.target_published_percent
        ):
            raise FollowupAnalysisError(f"Stored paired target evidence disagrees for {key!r}.")
        difference = abs(_number(row, "predicted_proportion") - prediction.predicted_proportion)
        if difference > tolerance:
            raise FollowupAnalysisError(f"Reconstructed prediction exceeds tolerance for {key!r}.")
        for field in (
            "predicted_percent",
            "absolute_error_percentage_points",
            "signed_error_percentage_points",
        ):
            if abs(_number(row, field) - float(getattr(prediction, field))) > tolerance * 100:
                raise FollowupAnalysisError(
                    f"Stored prediction field {field!r} disagrees for {key!r}."
                )
        maximum = max(maximum, difference)
    return {
        "prediction_rows": len(expected),
        "max_absolute_difference": maximum,
        "absolute_tolerance": tolerance,
        "relative_tolerance": 0.0,
        "scale": "proportion",
    }


def _count_summary(rows: Sequence[Row]) -> dict[str, object]:
    counts: list[int] = []
    for row in rows:
        count = row.get("historical_target_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise FollowupAnalysisError(
                "Earlier available report count must be a positive integer."
            )
        counts.append(count)
    return {
        "n": len(counts),
        "frequencies": {str(count): n for count, n in sorted(Counter(counts).items())},
        "mean": float(np.mean(counts)),
        "population_standard_deviation": float(np.std(counts, ddof=0)),
        "minimum": min(counts),
        "maximum": max(counts),
    }


def _count_evidence(training: Sequence[Row], evaluation: Sequence[Row]) -> dict[str, object]:
    earlier = _count_summary(training)
    later = _count_summary(evaluation)
    deviation = _number(earlier, "population_standard_deviation")
    return {
        "training": earlier,
        "evaluation": later,
        "mean_shift_training_standard_deviations": (
            (_number(later, "mean") - _number(earlier, "mean")) / deviation if deviation else None
        ),
        "unavailable_reason": None if deviation else "training_report_count_has_zero_variance",
    }


def _feature_values(features: tuple[str, ...], values: np.ndarray) -> dict[str, float]:
    if not np.isfinite(values).all():
        raise FollowupAnalysisError("Fitted parameter or contribution must be finite.")
    return {feature: float(value) for feature, value in zip(features, values, strict=True)}


def _fitted_evidence(
    pipeline: Pipeline,
    features: tuple[str, ...],
    training_matrix: np.ndarray,
    evaluation_matrix: np.ndarray,
    tolerance: float,
) -> dict[str, object]:
    imputer, scaler, ridge = (pipeline.named_steps[name] for name in ("imputer", "scaler", "ridge"))
    training_z = scaler.transform(imputer.transform(training_matrix))
    evaluation_z = scaler.transform(imputer.transform(evaluation_matrix))
    contributions = ridge.coef_ * (evaluation_z.mean(axis=0) - training_z.mean(axis=0))
    total = float(contributions.sum())
    logit_change = float(
        pipeline.predict(evaluation_matrix).mean() - pipeline.predict(training_matrix).mean()
    )
    if not math.isfinite(logit_change) or abs(total - logit_change) > tolerance:
        raise FollowupAnalysisError("Feature contributions do not reproduce the mean logit change.")
    return {
        "features": list(features),
        "parameters": {
            "intercept": float(ridge.intercept_),
            "coefficients": _feature_values(features, ridge.coef_),
            "imputation_values": _feature_values(features, imputer.statistics_),
            "scaler_means": _feature_values(features, scaler.mean_),
            "scaler_scales": _feature_values(features, scaler.scale_),
        },
        "missingness": {
            "training_counts": {
                field: int(np.isnan(training_matrix[:, index]).sum())
                for index, field in enumerate(features)
            },
            "evaluation_counts": {
                field: int(np.isnan(evaluation_matrix[:, index]).sum())
                for index, field in enumerate(features)
            },
            "training_any_missing_rows": int(np.isnan(training_matrix).any(axis=1).sum()),
            "evaluation_any_missing_rows": int(np.isnan(evaluation_matrix).any(axis=1).sum()),
        },
        "contributions": {
            "by_feature": _feature_values(features, contributions),
            "sum": total,
            "mean_predicted_logit_change": logit_change,
            "units": "logit",
            "absolute_tolerance": tolerance,
        },
    }


def _fit_groups(
    training: Sequence[Row],
    evaluation: Sequence[Row],
    groups: tuple[tuple[str, tuple[str, ...]], ...],
    prefix: str,
    original: PatientJourneyConfig,
    tolerance: float,
) -> tuple[tuple[EvaluationPrediction, ...], dict[str, dict[str, object]]]:
    quartiles = assign_within_release_volume_quartiles(evaluation)
    predictions: list[EvaluationPrediction] = []
    evidence: dict[str, dict[str, object]] = {}
    for name, features in groups:
        model = f"{prefix}_{name}"
        pipeline = _fit_pipeline(training, features, original)
        train_matrix = build_feature_matrix(training, features)
        evaluation_matrix = build_feature_matrix(evaluation, features)
        proportions = expit(pipeline.predict(evaluation_matrix))
        for row, proportion, matrix_row in zip(
            evaluation, proportions, evaluation_matrix, strict=True
        ):
            key = _key(row)
            predictions.append(
                _prediction(
                    row,
                    model=model,
                    predicted_proportion=float(proportion),
                    training_pairs=original.model_design.ridge.training_pairs,
                    volume_quartile=quartiles[(key[0], key[2])],
                    any_missing=bool(np.isnan(matrix_row).any()),
                )
            )
        evidence[model] = _fitted_evidence(
            pipeline, features, train_matrix, evaluation_matrix, tolerance
        )
    return tuple(predictions), evidence


def _contrasts(
    predictions: Mapping[str, tuple[EvaluationPrediction, ...]],
    original: PatientJourneyConfig,
    config: FollowupConfig,
) -> list[dict[str, object]]:
    bootstrap = original.model_design.bootstrap
    return [
        {
            "challenger": left,
            "comparator": right,
            "units": "percentage_points",
            **asdict(
                paired_clustered_bootstrap_interval(
                    predictions[left],
                    predictions[right],
                    resamples=bootstrap.resamples,
                    seed=bootstrap.seed,
                    percentiles=bootstrap.percentiles,
                )
            ),
        }
        for left, right in config.contrasts
    ]


def _evaluate_followup(
    rows: Sequence[Row],
    stored: Sequence[Row],
    original: PatientJourneyConfig,
    config: FollowupConfig,
) -> FollowupAnalysis:
    _validate_contract(original, config)
    training, evaluation, populations = _populations(rows, original)
    baselines = generate_baseline_predictions(evaluation, original)
    reconstructed = generate_ridge_predictions((*training, *evaluation), original)
    reconstruction = _compare_stored(
        (*baselines, *reconstructed), stored, config.prediction_absolute_tolerance
    )
    original_predictions, original_models = _fit_groups(
        training,
        evaluation,
        FEATURE_GROUPS,
        "original",
        original,
        config.contribution_absolute_tolerance,
    )
    if original_predictions != tuple(
        replace(row, model=f"original_{row.model}") for row in reconstructed
    ):
        raise FollowupAnalysisError("Diagnostic reconstruction changed original predictions.")
    revised_predictions, revised_models = _fit_groups(
        training,
        evaluation,
        config.feature_groups,
        "revised",
        original,
        config.contribution_absolute_tolerance,
    )
    predictions = tuple(
        sorted(
            (*baselines, *original_predictions, *revised_predictions),
            key=lambda row: (row.model, row.target_release_code, row.program_key),
        )
    )
    by_model = {
        name: tuple(row for row in predictions if row.model == name)
        for name in sorted({row.model for row in predictions})
    }
    models = {**original_models, **revised_models}
    for name, model_predictions in by_model.items():
        models.setdefault(name, {"features": []})["summary"] = asdict(
            summarize_predictions(model_predictions)
        )
    return FollowupAnalysis(
        predictions=predictions,
        evidence={
            "analysis_id": config.analysis_id,
            "evidence_status": "retrospective_exploratory_followup",
            "promotion_allowed": False,
            "future_forecast_available": False,
            "reconstruction": reconstruction,
            "populations": populations,
            "report_count": _count_evidence(training, evaluation),
            "models": models,
            "contrasts": _contrasts(by_model, original, config),
        },
    )


def evaluate_followup(
    rows: Sequence[Row],
    stored_predictions: Sequence[Row],
    original: PatientJourneyConfig,
    config: FollowupConfig,
) -> FollowupAnalysis:
    """Verify original predictions before diagnosing and fitting the single revision.

    Errors use the original published percentages on exactly the same programs.
    Count contributions concern average fitted logits, not percentage-point
    effects. A failed reconstruction stops before fitting any revised model.
    """
    try:
        return _evaluate_followup(rows, stored_predictions, original, config)
    except ValueError as exc:
        raise FollowupAnalysisError(str(exc)) from exc
