"""Compare fixed V2 predictions of later reported functioning-transplant percentages.

Ridge, a regression that limits coefficient size, uses the original fixed input
groups. Missing-value replacement, scaling, and fitting use the earlier training
rows only. The single eligible evaluation period is exploratory and cannot
support model promotion.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np
from scipy.special import expit  # type: ignore[import-untyped]
from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
from sklearn.linear_model import Ridge  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from kasm.patient_journey.config import (
    FEATURE_GROUPS,
    PatientJourneyConfig,
)
from kasm.patient_journey.evaluation import (
    EvaluationPrediction,
    assign_within_release_volume_quartiles,
)

_ALLOWED_FEATURES = frozenset(feature for _, features in FEATURE_GROUPS for feature in features)
_DIRECT_NUMERIC = frozenset(
    {
        "prior_target_logit",
        "historical_mean_target_proportion",
        "historical_target_count",
    }
)
_DIRECT_BOOLEAN = frozenset(
    feature for feature in _ALLOWED_FEATURES if feature.startswith("missing_")
)


class PatientJourneyModelError(ValueError):
    """Raised when V2 model construction would violate the frozen contract."""


def _number(row: Mapping[str, object], field: str, *, required: bool) -> float | None:
    value = row.get(field)
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        qualifier = "numeric" if required else "numeric or null"
        raise PatientJourneyModelError(f"Model field {field!r} must be {qualifier}.")
    result = float(value)
    if not math.isfinite(result):
        raise PatientJourneyModelError(f"Model field {field!r} must be finite.")
    return result


def _positive_log(row: Mapping[str, object], field: str) -> float | None:
    value = _number(row, field, required=False)
    if value is None:
        return None
    if value <= 0:
        raise PatientJourneyModelError(f"Reported model field {field!r} must be positive.")
    return math.log(value)


def _nonnegative_log1p(row: Mapping[str, object], field: str) -> float | None:
    value = _number(row, field, required=False)
    if value is None:
        return None
    if value < 0:
        raise PatientJourneyModelError(f"Reported model field {field!r} must be nonnegative.")
    return math.log1p(value)


def _interval_log_width(
    row: Mapping[str, object], lower_field: str, upper_field: str
) -> float | None:
    lower = _number(row, lower_field, required=False)
    upper = _number(row, upper_field, required=False)
    if lower is None and upper is None:
        return None
    if lower is None or upper is None:
        raise PatientJourneyModelError(
            f"Model interval {lower_field!r}/{upper_field!r} must be jointly reported."
        )
    if lower <= 0 or upper <= 0:
        raise PatientJourneyModelError(
            f"Reported model interval {lower_field!r}/{upper_field!r} must be positive."
        )
    if lower > upper:
        raise PatientJourneyModelError(
            f"Model interval {lower_field!r}/{upper_field!r} is reversed."
        )
    return math.log(upper) - math.log(lower)


def _feature_value(row: Mapping[str, object], feature: str) -> float | None:
    if feature in _DIRECT_NUMERIC:
        value = _number(row, feature, required=True)
        if value is None:  # pragma: no cover - required=True cannot return None
            raise PatientJourneyModelError(f"Model field {feature!r} is missing.")
        if feature == "historical_mean_target_proportion" and not 0 <= value <= 1:
            raise PatientJourneyModelError(
                "Historical mean target proportion must be bounded in [0, 1]."
            )
        return value
    if feature in _DIRECT_BOOLEAN:
        raw_value = row.get(feature)
        if not isinstance(raw_value, bool):
            raise PatientJourneyModelError(f"Model field {feature!r} must be boolean.")
        return float(raw_value)
    transforms: dict[str, tuple[str, str]] = {
        "log1p_prior_target_n": ("log1p", "prior_target_n"),
        "log_transplant_rate_ratio": ("log", "transplant_rate_ratio"),
        "log1p_transplant_rate_person_years": (
            "log1p",
            "transplant_rate_person_years",
        ),
        "log1p_wait_time_months_25th_percentile": (
            "log1p",
            "wait_time_months_25th_percentile",
        ),
        "log1p_acceptance_overall_expected_acceptances": (
            "log1p",
            "acceptance_overall_expected_acceptances",
        ),
        "log_acceptance_overall_oar": ("log", "acceptance_overall_oar"),
        "log_acceptance_low_oar": ("log", "acceptance_low_oar"),
        "log_acceptance_medium_oar": ("log", "acceptance_medium_oar"),
        "log_acceptance_high_oar": ("log", "acceptance_high_oar"),
        "log_acceptance_hard_to_place_oar": (
            "log",
            "acceptance_hard_to_place_oar",
        ),
        "log_waiting_list_mortality_ratio": ("log", "waiting_list_mortality_ratio"),
    }
    if feature == "acceptance_interval_log_width":
        return _interval_log_width(
            row,
            "acceptance_overall_oar_lower",
            "acceptance_overall_oar_upper",
        )
    if feature == "waiting_list_mortality_interval_log_width":
        return _interval_log_width(
            row,
            "waiting_list_mortality_lower",
            "waiting_list_mortality_upper",
        )
    if feature not in transforms:
        raise PatientJourneyModelError(
            f"Feature {feature!r} is outside the frozen feature allowlist."
        )
    transform, source = transforms[feature]
    return _positive_log(row, source) if transform == "log" else _nonnegative_log1p(row, source)


def build_feature_matrix(
    rows: Sequence[Mapping[str, object]], feature_names: Sequence[str]
) -> np.ndarray:
    """Build the fixed numeric inputs while keeping rows with missing predictors.

    Nulls become NaN for later replacement using training data; they never become
    observed zeroes. Ratios require positive inputs for logs. Counts and times
    permit zero through ``log1p(x) = log(1 + x)``. Unknown fields are rejected.
    """
    if not rows:
        raise PatientJourneyModelError("Feature construction requires at least one row.")
    if not feature_names or len(feature_names) != len(set(feature_names)):
        raise PatientJourneyModelError("Features must be a non-empty unique sequence.")
    prohibited = [feature for feature in feature_names if feature not in _ALLOWED_FEATURES]
    if prohibited:
        raise PatientJourneyModelError(
            f"Features are outside the frozen feature allowlist: {sorted(prohibited)}."
        )
    return np.asarray(
        [
            [
                np.nan if (value := _feature_value(row, feature)) is None else value
                for feature in feature_names
            ]
            for row in rows
        ],
        dtype=np.float64,
    )


def _text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise PatientJourneyModelError(f"Model field {field!r} must be non-empty text.")
    return value


def _integer(row: Mapping[str, object], field: str) -> int:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PatientJourneyModelError(f"Model field {field!r} must be an integer.")
    return value


def _boolean(row: Mapping[str, object], field: str) -> bool:
    value = row.get(field)
    if not isinstance(value, bool):
        raise PatientJourneyModelError(f"Model field {field!r} must be boolean.")
    return value


def _eligible_rows(rows: Sequence[Mapping[str, object]]) -> tuple[Mapping[str, object], ...]:
    return tuple(row for row in rows if _boolean(row, "primary_analytic_eligible"))


def _pair_rows(
    rows: Sequence[Mapping[str, object]], pair: tuple[str, str]
) -> tuple[Mapping[str, object], ...]:
    return tuple(
        sorted(
            (
                row
                for row in _eligible_rows(rows)
                if _text(row, "feature_release_code") == pair[0]
                and _text(row, "target_release_code") == pair[1]
            ),
            key=lambda row: _text(row, "program_key"),
        )
    )


def _prediction(
    row: Mapping[str, object],
    *,
    model: str,
    predicted_proportion: float,
    training_pairs: tuple[tuple[str, str], ...],
    volume_quartile: int,
    any_missing: bool,
) -> EvaluationPrediction:
    target_percent = _number(row, "target_published_percent", required=True)
    target_n = _integer(row, "target_n")
    if target_percent is None:  # pragma: no cover - required=True cannot return None
        raise PatientJourneyModelError("Eligible row target is missing.")
    if target_n <= 0 or not 0 <= target_percent <= 100:
        raise PatientJourneyModelError("Eligible target values are outside their valid bounds.")
    if not math.isfinite(predicted_proportion) or not 0 <= predicted_proportion <= 1:
        raise PatientJourneyModelError("Predicted proportion must be finite and bounded in [0, 1].")
    predicted_percent = predicted_proportion * 100
    signed_error = predicted_percent - target_percent
    return EvaluationPrediction(
        program_key=_text(row, "program_key"),
        feature_release_code=_text(row, "feature_release_code"),
        target_release_code=_text(row, "target_release_code"),
        model=model,
        training_pairs=training_pairs,
        target_n=target_n,
        target_published_percent=target_percent,
        predicted_proportion=predicted_proportion,
        predicted_percent=predicted_percent,
        absolute_error_percentage_points=abs(signed_error),
        signed_error_percentage_points=signed_error,
        volume_quartile=volume_quartile,
        first_observed_program=_boolean(row, "first_observed_program"),
        any_model_feature_missing=any_missing,
    )


def generate_baseline_predictions(
    rows: Sequence[Mapping[str, object]], config: PatientJourneyConfig
) -> tuple[EvaluationPrediction, ...]:
    """Evaluate the three fixed simple predictions from each row's available history.

    Carry forward the latest outcome, average that program's earlier outcomes,
    or use the available-cohort reference calculated from the earlier report.
    These baselines require no fitted model; errors use the later published
    percentage, not reconstructed candidate counts.
    """
    eligible = _eligible_rows(rows)
    if not eligible:
        raise PatientJourneyModelError("Baseline evaluation requires eligible rows.")
    quartiles = assign_within_release_volume_quartiles(eligible)
    predictions: list[EvaluationPrediction] = []
    for row in sorted(
        eligible,
        key=lambda item: (
            _text(item, "target_release_code"),
            _text(item, "program_key"),
        ),
    ):
        values = {
            "persistence": _number(row, "prior_target_proportion", required=True),
            "available_cohort_reference": _number(
                row, "available_cohort_target_proportion", required=True
            ),
            "historical_mean": _number(row, "historical_mean_target_proportion", required=True),
        }
        for model in config.model_design.baselines:
            value = values[model]
            if value is None or not 0 <= value <= 1:
                raise PatientJourneyModelError(
                    f"Baseline {model!r} must be available and bounded for eligible rows."
                )
            predictions.append(
                _prediction(
                    row,
                    model=model,
                    predicted_proportion=value,
                    training_pairs=(),
                    volume_quartile=quartiles[
                        (_text(row, "program_key"), _text(row, "target_release_code"))
                    ],
                    any_missing=False,
                )
            )
    return tuple(predictions)


def _fit_pipeline(
    training_rows: Sequence[Mapping[str, object]],
    feature_names: Sequence[str],
    config: PatientJourneyConfig,
) -> Pipeline:
    features = build_feature_matrix(training_rows, feature_names)
    targets = np.asarray(
        [_number(row, "target_logit", required=True) for row in training_rows],
        dtype=np.float64,
    )
    ridge = config.model_design.ridge
    pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
            (
                "ridge",
                Ridge(
                    alpha=ridge.alpha,
                    solver=ridge.solver,
                    tol=ridge.tolerance,
                    max_iter=ridge.max_iterations,
                ),
            ),
        ]
    )
    pipeline.fit(features, targets)
    return pipeline


def generate_ridge_predictions(
    rows: Sequence[Mapping[str, object]], config: PatientJourneyConfig
) -> tuple[EvaluationPrediction, ...]:
    """Evaluate all fixed Ridge input groups on the same programs and single period.

    The configured training outcomes were public by the evaluation prediction
    date. Fit each group's preprocessing on those training rows, then convert
    predicted logits with the inverse-logit function to proportions in [0, 1].
    """
    ridge = config.model_design.ridge
    training_rows = tuple(row for pair in ridge.training_pairs for row in _pair_rows(rows, pair))
    evaluation_rows = _pair_rows(rows, ridge.evaluation_pair)
    if not training_rows:
        raise PatientJourneyModelError(
            "The frozen Ridge evaluation has no eligible strict-vintage training pair rows."
        )
    if not evaluation_rows:
        raise PatientJourneyModelError("The frozen Ridge evaluation pair has no eligible rows.")
    quartiles = assign_within_release_volume_quartiles(evaluation_rows)
    predictions: list[EvaluationPrediction] = []
    for group in config.model_design.feature_groups:
        pipeline = _fit_pipeline(training_rows, group.features, config)
        evaluation_matrix = build_feature_matrix(evaluation_rows, group.features)
        predicted_logits = pipeline.predict(evaluation_matrix)
        predicted_proportions = expit(predicted_logits)
        for row, proportion, matrix_row in zip(
            evaluation_rows,
            predicted_proportions,
            evaluation_matrix,
            strict=True,
        ):
            predictions.append(
                _prediction(
                    row,
                    model=group.name,
                    predicted_proportion=float(proportion),
                    training_pairs=ridge.training_pairs,
                    volume_quartile=quartiles[
                        (_text(row, "program_key"), _text(row, "target_release_code"))
                    ],
                    any_missing=bool(np.isnan(matrix_row).any()),
                )
            )
    return tuple(predictions)
