"""Run the fixed V1 comparison on 2025 outcomes and save its canonical result once.

The fit ends at target year 2023; 2024 outcomes remain reserved for band calibration
when activation was attempted. The already-inspected 2025 outcomes provide descriptive
product-selection evidence, not a new independent test.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from math import exp, isfinite
from pathlib import Path
from typing import cast

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from kasm.config import DataSourceManifest, load_data_source_manifest
from kasm.data.build import MODEL_PANEL_SCHEMA
from kasm.modeling.activation import (
    BandPromotion,
    PairedAbsoluteErrors,
    PointPromotion,
    assess_band_promotion,
    assess_point_promotion,
    clopper_pearson_interval,
    paired_bootstrap_mae_difference_interval,
)
from kasm.modeling.backtest import assign_volume_quartiles
from kasm.modeling.challenger import fit_ridge_pipeline
from kasm.modeling.experiment import ExperimentConfig, load_frozen_experiment_config
from kasm.modeling.features import extract_feature_matrix

_PRECISION_TYPE = pa.dictionary(pa.int8(), pa.string())
FROZEN_REPLAY_PREDICTIONS_SCHEMA = pa.schema(
    [
        pa.field("program_key", pa.string(), nullable=False),
        pa.field("feature_cohort_year", pa.int16(), nullable=False),
        pa.field("target_cohort_year", pa.int16(), nullable=False),
        pa.field("prediction_as_of", pa.string(), nullable=False),
        pa.field("prediction_as_of_precision", _PRECISION_TYPE, nullable=False),
        pa.field("target_cohort_end", pa.date32(), nullable=False),
        pa.field("truth_published_value", pa.string(), nullable=False),
        pa.field("truth_published_precision", _PRECISION_TYPE, nullable=False),
        pa.field("elapsed_target_cohort_fraction_at_prediction", pa.float64(), nullable=False),
        pa.field("first_observed_program", pa.bool_(), nullable=False),
        pa.field("public_forecast_eligible", pa.bool_(), nullable=False),
        pa.field("any_predictor_missing", pa.bool_(), nullable=False),
        pa.field("log1p_overall_expected_acceptances", pa.float64(), nullable=False),
        pa.field("expected_acceptance_quartile", pa.int8(), nullable=False),
        pa.field("target_log_oar", pa.float64(), nullable=False),
        pa.field("target_oar", pa.float64(), nullable=False),
        pa.field("ridge_alpha", pa.float64(), nullable=False),
        pa.field("ridge_predicted_log_oar", pa.float64(), nullable=False),
        pa.field("ridge_predicted_oar", pa.float64(), nullable=False),
        pa.field("ridge_absolute_error_log_oar", pa.float64(), nullable=False),
        pa.field("ridge_absolute_error_oar", pa.float64(), nullable=False),
        pa.field("ridge_signed_error_log_oar", pa.float64(), nullable=False),
        pa.field("persistence_predicted_log_oar", pa.float64(), nullable=False),
        pa.field("persistence_predicted_oar", pa.float64(), nullable=False),
        pa.field("persistence_absolute_error_log_oar", pa.float64(), nullable=False),
        pa.field("persistence_absolute_error_oar", pa.float64(), nullable=False),
        pa.field("persistence_signed_error_log_oar", pa.float64(), nullable=False),
        pa.field("absolute_error_difference_vs_persistence", pa.float64(), nullable=False),
        pa.field("ridge_band_lower_log_oar", pa.float64(), nullable=False),
        pa.field("ridge_band_upper_log_oar", pa.float64(), nullable=False),
        pa.field("ridge_band_lower_oar", pa.float64(), nullable=False),
        pa.field("ridge_band_upper_oar", pa.float64(), nullable=False),
        pa.field("ridge_band_covered", pa.bool_(), nullable=False),
        pa.field("persistence_band_lower_log_oar", pa.float64(), nullable=False),
        pa.field("persistence_band_upper_log_oar", pa.float64(), nullable=False),
        pa.field("persistence_band_lower_oar", pa.float64(), nullable=False),
        pa.field("persistence_band_upper_oar", pa.float64(), nullable=False),
        pa.field("persistence_band_covered", pa.bool_(), nullable=False),
    ]
)

# Keep the released attempted-activation schema exact. Only the skipped path permits null bands.
POINT_ONLY_REPLAY_PREDICTIONS_SCHEMA = pa.schema(
    [
        field.with_nullable(True) if "_band_" in field.name else field
        for field in FROZEN_REPLAY_PREDICTIONS_SCHEMA
    ]
)


class FrozenReplayError(ValueError):
    """Raised when a replay would violate the frozen, write-once contract."""


@dataclass(frozen=True)
class FrozenReplayPrediction:
    """One target-year 2025 prediction with paired persistence and band evidence."""

    program_key: str
    feature_cohort_year: int
    target_cohort_year: int
    prediction_as_of: str
    prediction_as_of_precision: str
    target_cohort_end: date
    truth_published_value: str
    truth_published_precision: str
    elapsed_target_cohort_fraction_at_prediction: float
    first_observed_program: bool
    public_forecast_eligible: bool
    any_predictor_missing: bool
    log1p_overall_expected_acceptances: float
    expected_acceptance_quartile: int
    target_log_oar: float
    target_oar: float
    ridge_alpha: float
    ridge_predicted_log_oar: float
    ridge_predicted_oar: float
    ridge_absolute_error_log_oar: float
    ridge_absolute_error_oar: float
    ridge_signed_error_log_oar: float
    persistence_predicted_log_oar: float
    persistence_predicted_oar: float
    persistence_absolute_error_log_oar: float
    persistence_absolute_error_oar: float
    persistence_signed_error_log_oar: float
    absolute_error_difference_vs_persistence: float
    ridge_band_lower_log_oar: float | None
    ridge_band_upper_log_oar: float | None
    ridge_band_lower_oar: float | None
    ridge_band_upper_oar: float | None
    ridge_band_covered: bool | None
    persistence_band_lower_log_oar: float | None
    persistence_band_upper_log_oar: float | None
    persistence_band_lower_oar: float | None
    persistence_band_upper_oar: float | None
    persistence_band_covered: bool | None


@dataclass(frozen=True)
class FrozenReplayFit:
    """Fixed fitting years and target-year replay predictions."""

    training_target_years: tuple[int, ...]
    evaluation_target_year: int
    excluded_cohort_years: tuple[int, ...]
    predictions: tuple[FrozenReplayPrediction, ...]


@dataclass(frozen=True)
class FrozenReplayResult:
    """Published canonical replay artifact paths and activation decision."""

    output_directory: Path
    predictions_path: Path
    metrics_path: Path
    completion_path: Path
    prediction_rows: int
    displayed_model: str
    display_band: bool


@dataclass(frozen=True)
class ReleaseDecision:
    """Effective product state after applying the separate frozen gates."""

    activation_status: str
    displayed_model: str
    ridge_band_gate_passed: bool
    display_band: bool
    band_suppression_reason: str | None


def resolve_release_decision(*, point: PointPromotion, band: BandPromotion) -> ReleaseDecision:
    """Keep the band decision separate, but never show a band for a suppressed Ridge point."""
    not_attempted = "forecast_activation_not_attempted" in point.failed_criteria
    activation_status = (
        "not_attempted"
        if not_attempted
        else "promoted"
        if point.promoted
        else "attempted_not_promoted"
    )
    display_band = point.promoted and band.display_band
    suppression_reason: str | None = None
    if not point.promoted:
        suppression_reason = "ridge_point_not_promoted"
    elif not band.display_band:
        suppression_reason = "ridge_band_gate_failed"
    return ReleaseDecision(
        activation_status=activation_status,
        displayed_model=point.displayed_model,
        ridge_band_gate_passed=band.display_band,
        display_band=display_band,
        band_suppression_reason=suppression_reason,
    )


def _required_int(row: Mapping[str, object], field: str) -> int:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise FrozenReplayError(f"Panel field {field!r} must be an integer.")
    return value


def _required_float(row: Mapping[str, object], field: str) -> float:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise FrozenReplayError(f"Panel field {field!r} must be numeric.")
    result = float(value)
    if not isfinite(result):
        raise FrozenReplayError(f"Panel field {field!r} must be finite.")
    return result


def _required_string(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise FrozenReplayError(f"Panel field {field!r} must be non-empty text.")
    return value


def _required_bool(row: Mapping[str, object], field: str) -> bool:
    value = row.get(field)
    if not isinstance(value, bool):
        raise FrozenReplayError(f"Panel field {field!r} must be boolean.")
    return value


def _required_date(row: Mapping[str, object], field: str) -> date:
    value = row.get(field)
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, date):
        raise FrozenReplayError(f"Panel field {field!r} must be a date.")
    return value


def _feature_matrix(
    rows: Sequence[Mapping[str, object]], feature_columns: Sequence[str]
) -> np.ndarray:
    matrix = extract_feature_matrix(rows, feature_columns)
    return np.asarray(
        [[np.nan if value is None else float(value) for value in row] for row in matrix],
        dtype=np.float64,
    )


def _frozen_radius(value: float | None, name: str) -> float:
    if value is None or not isfinite(value) or value < 0:
        raise FrozenReplayError(f"Frozen config must contain a valid {name}.")
    return value


def _prediction_band(
    predicted_log: float,
    target_log: float,
    radius: float | None,
) -> tuple[float | None, float | None, float | None, float | None, bool | None]:
    """Leave the whole band unknown when activation was skipped."""
    if radius is None:
        return None, None, None, None, None
    lower, upper = predicted_log - radius, predicted_log + radius
    return lower, upper, exp(lower), exp(upper), lower <= target_log <= upper


def _training_years(
    config: ExperimentConfig, excluded_cohort_years: Sequence[int]
) -> tuple[int, ...]:
    excluded = set(excluded_cohort_years)
    return tuple(
        target_year
        for target_year in range(
            config.training_target_year_start,
            config.replay_model_training_target_year_end + 1,
        )
        if target_year not in excluded and target_year - 1 not in excluded
    )


def generate_frozen_replay_predictions(
    rows: Sequence[Mapping[str, object]],
    *,
    config: ExperimentConfig,
    excluded_cohort_years: Sequence[int] = (),
) -> FrozenReplayFit:
    """Fit the frozen alpha through target year 2023 and evaluate only 2025."""
    if config.selected_ridge_alpha is None:
        raise FrozenReplayError("Frozen replay requires ridge.selected_alpha.")
    excluded = tuple(sorted(set(excluded_cohort_years)))
    if config.replay_target_year in excluded or config.replay_target_year - 1 in excluded:
        raise FrozenReplayError("A sensitivity cannot exclude the frozen replay transition.")
    quartiles = assign_volume_quartiles(rows)
    training_years = _training_years(config, excluded)
    training_rows = tuple(
        row
        for row in rows
        if _required_bool(row, "analytic_eligible")
        and _required_int(row, "target_cohort_year") in training_years
    )
    observed_training_years = tuple(
        sorted({_required_int(row, "target_cohort_year") for row in training_rows})
    )
    if observed_training_years != training_years:
        raise FrozenReplayError(
            f"Frozen replay requires training target years {training_years}, "
            f"found {observed_training_years}."
        )
    evaluation_rows = tuple(
        sorted(
            (
                row
                for row in rows
                if _required_bool(row, "analytic_eligible")
                and _required_int(row, "target_cohort_year") == config.replay_target_year
            ),
            key=lambda row: _required_string(row, "program_key"),
        )
    )
    if not evaluation_rows:
        raise FrozenReplayError(
            f"Frozen replay target year {config.replay_target_year} has no analytic rows."
        )

    pipeline = fit_ridge_pipeline(
        training_rows,
        feature_columns=config.feature_columns,
        target_column=config.target_column,
        alpha=config.selected_ridge_alpha,
        random_seed=config.ridge_random_seed,
    )
    predicted_values = pipeline.predict(_feature_matrix(evaluation_rows, config.feature_columns))
    ridge_radius = (
        _frozen_radius(
            config.ridge_absolute_log_residual_radius,
            "ridge absolute-log-residual radius",
        )
        if config.forecast_activation_attempted
        else None
    )
    persistence_radius = (
        _frozen_radius(
            config.persistence_absolute_log_residual_radius,
            "persistence absolute-log-residual radius",
        )
        if config.forecast_activation_attempted
        else None
    )
    missingness_columns = tuple(
        column for column in config.feature_columns if column.startswith("missing_")
    )
    predictions: list[FrozenReplayPrediction] = []
    for row, predicted_value in zip(evaluation_rows, predicted_values, strict=True):
        program_key = _required_string(row, "program_key")
        target_year = _required_int(row, "target_cohort_year")
        target_log = _required_float(row, config.target_column)
        target_oar = _required_float(row, "target_oar")
        ridge_log = float(predicted_value)
        ridge_oar = exp(ridge_log)
        persistence_log = _required_float(row, "current_log_overall_oar")
        persistence_oar = exp(persistence_log)
        ridge_absolute_error = abs(ridge_log - target_log)
        persistence_absolute_error = abs(persistence_log - target_log)
        ridge_band = _prediction_band(ridge_log, target_log, ridge_radius)
        persistence_band = _prediction_band(persistence_log, target_log, persistence_radius)
        predictions.append(
            FrozenReplayPrediction(
                program_key=program_key,
                feature_cohort_year=_required_int(row, "feature_cohort_year"),
                target_cohort_year=target_year,
                prediction_as_of=_required_string(row, "prediction_as_of"),
                prediction_as_of_precision=_required_string(row, "prediction_as_of_precision"),
                target_cohort_end=_required_date(row, "target_cohort_end"),
                truth_published_value=_required_string(row, "truth_published_value"),
                truth_published_precision=_required_string(row, "truth_published_precision"),
                elapsed_target_cohort_fraction_at_prediction=_required_float(
                    row, "elapsed_target_cohort_fraction_at_prediction"
                ),
                first_observed_program=_required_bool(row, "first_observed_program"),
                public_forecast_eligible=_required_bool(row, "public_forecast_eligible"),
                any_predictor_missing=any(
                    _required_bool(row, column) for column in missingness_columns
                ),
                log1p_overall_expected_acceptances=_required_float(
                    row, "log1p_overall_expected_acceptances"
                ),
                expected_acceptance_quartile=quartiles[(program_key, target_year)],
                target_log_oar=target_log,
                target_oar=target_oar,
                ridge_alpha=config.selected_ridge_alpha,
                ridge_predicted_log_oar=ridge_log,
                ridge_predicted_oar=ridge_oar,
                ridge_absolute_error_log_oar=ridge_absolute_error,
                ridge_absolute_error_oar=abs(ridge_oar - target_oar),
                ridge_signed_error_log_oar=ridge_log - target_log,
                persistence_predicted_log_oar=persistence_log,
                persistence_predicted_oar=persistence_oar,
                persistence_absolute_error_log_oar=persistence_absolute_error,
                persistence_absolute_error_oar=abs(persistence_oar - target_oar),
                persistence_signed_error_log_oar=persistence_log - target_log,
                absolute_error_difference_vs_persistence=(
                    ridge_absolute_error - persistence_absolute_error
                ),
                ridge_band_lower_log_oar=ridge_band[0],
                ridge_band_upper_log_oar=ridge_band[1],
                ridge_band_lower_oar=ridge_band[2],
                ridge_band_upper_oar=ridge_band[3],
                ridge_band_covered=ridge_band[4],
                persistence_band_lower_log_oar=persistence_band[0],
                persistence_band_upper_log_oar=persistence_band[1],
                persistence_band_lower_oar=persistence_band[2],
                persistence_band_upper_oar=persistence_band[3],
                persistence_band_covered=persistence_band[4],
            )
        )
    return FrozenReplayFit(
        training_target_years=training_years,
        evaluation_target_year=config.replay_target_year,
        excluded_cohort_years=excluded,
        predictions=tuple(predictions),
    )


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise FrozenReplayError("A frozen replay metric group cannot be empty.")
    return sum(values) / len(values)


def _calibration_slope(
    predictions: Sequence[FrozenReplayPrediction], *, prediction_field: str
) -> float | None:
    predicted = [float(getattr(row, prediction_field)) for row in predictions]
    outcomes = [row.target_log_oar for row in predictions]
    predicted_mean = _mean(predicted)
    outcome_mean = _mean(outcomes)
    denominator = sum((value - predicted_mean) ** 2 for value in predicted)
    if denominator == 0:
        return None
    return (
        sum(
            (prediction - predicted_mean) * (outcome - outcome_mean)
            for prediction, outcome in zip(predicted, outcomes, strict=True)
        )
        / denominator
    )


def _band_metrics(
    predictions: Sequence[FrozenReplayPrediction],
    *,
    model: str,
    nominal_coverage: float,
    activation_attempted: bool,
) -> dict[str, object]:
    if not activation_attempted:
        result: dict[str, object] = {
            f"{model}_band_coverage": None,
            f"{model}_band_coverage_exact_95_interval": None,
            f"{model}_band_mean_width_oar": None,
        }
        if model == "ridge":
            result["ridge_band_coverage_warning"] = None
        return result
    records = [asdict(row) for row in predictions]
    covered = sum(_required_bool(row, f"{model}_band_covered") for row in records)
    interval = clopper_pearson_interval(
        successes=covered,
        trials=len(predictions),
        confidence_level=0.95,
    )
    result = {
        f"{model}_band_coverage": covered / len(predictions),
        f"{model}_band_coverage_exact_95_interval": list(interval),
        f"{model}_band_mean_width_oar": _mean(
            [
                _required_float(row, f"{model}_band_upper_oar")
                - _required_float(row, f"{model}_band_lower_oar")
                for row in records
            ]
        ),
    }
    if model == "ridge":
        result["ridge_band_coverage_warning"] = interval[1] < nominal_coverage
    return result


def _metric_record(
    predictions: Sequence[FrozenReplayPrediction],
    *,
    nominal_coverage: float,
    activation_attempted: bool,
) -> dict[str, object]:
    ridge_mae = _mean([row.ridge_absolute_error_log_oar for row in predictions])
    persistence_mae = _mean([row.persistence_absolute_error_log_oar for row in predictions])
    result: dict[str, object] = {
        "n": len(predictions),
        "ridge_mae_log_oar": ridge_mae,
        "persistence_mae_log_oar": persistence_mae,
        "ridge_mae_oar": _mean([row.ridge_absolute_error_oar for row in predictions]),
        "persistence_mae_oar": _mean([row.persistence_absolute_error_oar for row in predictions]),
        "skill_over_persistence": (
            None if persistence_mae == 0 else 1 - ridge_mae / persistence_mae
        ),
        "mean_paired_absolute_error_difference_vs_persistence": _mean(
            [row.absolute_error_difference_vs_persistence for row in predictions]
        ),
        "ridge_mean_signed_log_error": _mean(
            [row.ridge_signed_error_log_oar for row in predictions]
        ),
        "persistence_mean_signed_log_error": _mean(
            [row.persistence_signed_error_log_oar for row in predictions]
        ),
        "ridge_calibration_slope": _calibration_slope(
            predictions, prediction_field="ridge_predicted_log_oar"
        ),
        "persistence_calibration_slope": _calibration_slope(
            predictions, prediction_field="persistence_predicted_log_oar"
        ),
    }
    for model in ("ridge", "persistence"):
        result.update(
            _band_metrics(
                predictions,
                model=model,
                nominal_coverage=nominal_coverage,
                activation_attempted=activation_attempted,
            )
        )
    return result


def _diagnostic_record(
    name: str,
    predictions: Sequence[FrozenReplayPrediction],
    *,
    nominal_coverage: float,
    activation_attempted: bool,
) -> dict[str, object]:
    if not predictions:
        return {"stratum": name, "n": 0, "available": False}
    return {
        "stratum": name,
        "available": True,
        **_metric_record(
            predictions,
            nominal_coverage=nominal_coverage,
            activation_attempted=activation_attempted,
        ),
    }


def _activation_evidence(
    predictions: Sequence[FrozenReplayPrediction],
    overall: Mapping[str, object],
    lowest: Mapping[str, object],
    config: ExperimentConfig,
) -> dict[str, object]:
    if not config.forecast_activation_attempted:
        return {
            "bootstrap": None,
            "point_promotion": {
                "promoted": False,
                "displayed_model": "persistence",
                "skill_over_persistence": overall["skill_over_persistence"],
                "failed_criteria": ["forecast_activation_not_attempted"],
            },
            "band_promotion": None,
            "release_decision": asdict(
                ReleaseDecision(
                    activation_status="not_attempted",
                    displayed_model="persistence",
                    ridge_band_gate_passed=False,
                    display_band=False,
                    band_suppression_reason="forecast_activation_not_attempted",
                )
            ),
        }
    bootstrap = paired_bootstrap_mae_difference_interval(
        tuple(
            PairedAbsoluteErrors(
                program_key=row.program_key,
                challenger_absolute_error=row.ridge_absolute_error_log_oar,
                persistence_absolute_error=row.persistence_absolute_error_log_oar,
            )
            for row in predictions
        ),
        config=config,
    )
    point_promotion = assess_point_promotion(
        challenger_mae=cast(float, overall["ridge_mae_log_oar"]),
        persistence_mae=cast(float, overall["persistence_mae_log_oar"]),
        bootstrap_lower=bootstrap.lower,
        bootstrap_upper=bootstrap.upper,
        challenger_bias=cast(float, overall["ridge_mean_signed_log_error"]),
        persistence_bias=cast(float, overall["persistence_mean_signed_log_error"]),
        challenger_low_volume_mae=cast(float, lowest["ridge_mae_log_oar"]),
        persistence_low_volume_mae=cast(float, lowest["persistence_mae_log_oar"]),
        low_volume_rows=cast(int, lowest["n"]),
        config=config,
    )
    band_promotion = assess_band_promotion(
        covered=sum(_required_bool(asdict(row), "ridge_band_covered") for row in predictions),
        total=len(predictions),
        challenger_mean_width=cast(float, overall["ridge_band_mean_width_oar"]),
        persistence_mean_width=cast(float, overall["persistence_band_mean_width_oar"]),
        config=config,
    )
    release_decision = resolve_release_decision(
        point=point_promotion,
        band=band_promotion,
    )
    bootstrap_record = asdict(bootstrap)
    bootstrap_record["resampling_unit"] = "program_key"
    return {
        "bootstrap": bootstrap_record,
        "point_promotion": asdict(point_promotion),
        "band_promotion": asdict(band_promotion),
        "release_decision": asdict(release_decision),
    }


def evaluate_frozen_replay(
    replay: FrozenReplayFit,
    *,
    rows: Sequence[Mapping[str, object]],
    config: ExperimentConfig,
) -> dict[str, object]:
    """Calculate frozen replay metrics, diagnostics, sensitivities, and display gates."""
    if replay.evaluation_target_year != config.replay_target_year:
        raise FrozenReplayError("Replay evaluation year does not match the frozen config.")
    if replay.excluded_cohort_years:
        raise FrozenReplayError("Primary replay evidence cannot use a sensitivity fit.")
    predictions = replay.predictions
    if not predictions or {row.target_cohort_year for row in predictions} != {
        config.replay_target_year
    }:
        raise FrozenReplayError("Primary replay evidence requires only target year 2025.")
    overall = _metric_record(
        predictions,
        nominal_coverage=config.band_nominal_coverage,
        activation_attempted=bool(config.forecast_activation_attempted),
    )
    quartile_records: list[dict[str, object]] = []
    for quartile in range(1, 5):
        group = tuple(row for row in predictions if row.expected_acceptance_quartile == quartile)
        if not group:
            raise FrozenReplayError(f"Replay is missing expected-acceptance quartile {quartile}.")
        quartile_records.append(
            {
                "expected_acceptance_quartile": quartile,
                **_metric_record(
                    group,
                    nominal_coverage=config.band_nominal_coverage,
                    activation_attempted=bool(config.forecast_activation_attempted),
                ),
            }
        )
    lowest = quartile_records[0]
    diagnostics = (
        (
            "first_observed_program",
            tuple(row for row in predictions if row.first_observed_program),
        ),
        (
            "established_program",
            tuple(row for row in predictions if not row.first_observed_program),
        ),
        (
            "any_predictor_missing",
            tuple(row for row in predictions if row.any_predictor_missing),
        ),
        (
            "no_predictor_missing",
            tuple(row for row in predictions if not row.any_predictor_missing),
        ),
    )
    sensitivities: list[dict[str, object]] = []
    for sensitivity in config.sensitivities:
        sensitivity_fit = generate_frozen_replay_predictions(
            rows,
            config=config,
            excluded_cohort_years=sensitivity.excluded_cohort_years,
        )
        sensitivities.append(
            {
                "name": sensitivity.name,
                "excluded_cohort_years": list(sensitivity.excluded_cohort_years),
                "training_target_years": list(sensitivity_fit.training_target_years),
                **_metric_record(
                    sensitivity_fit.predictions,
                    nominal_coverage=config.band_nominal_coverage,
                    activation_attempted=bool(config.forecast_activation_attempted),
                ),
            }
        )
    return {
        "frozen_replay_evaluated": True,
        "evidence_classification": "descriptive_retrospective_product_selection",
        "prospective_validation": False,
        "training_target_years": list(replay.training_target_years),
        "calibration_target_year": config.band_calibration_target_year
        if config.forecast_activation_attempted
        else None,
        "replay_target_year": replay.evaluation_target_year,
        "selected_alpha": config.selected_ridge_alpha,
        "overall": overall,
        "by_expected_acceptance_quartile": quartile_records,
        "missingness_and_entry_diagnostics": [
            _diagnostic_record(
                name,
                group,
                nominal_coverage=config.band_nominal_coverage,
                activation_attempted=bool(config.forecast_activation_attempted),
            )
            for name, group in diagnostics
        ],
        "sensitivities": sensitivities,
        **_activation_evidence(predictions, overall, lowest, config),
        "cohort_context": {
            "2023": "mixed offer-acceptance monitoring context after 2023-07-27",
            "2024": "full post-monitoring-policy cohort",
            "2025": "full post-monitoring-policy cohort",
        },
    }


def frozen_replay_predictions_table(
    predictions: Sequence[FrozenReplayPrediction],
    *,
    activation_attempted: bool = True,
) -> pa.Table:
    """Return replay predictions in a stable, exact Parquet schema."""
    ordered = sorted(predictions, key=lambda row: row.program_key)
    schema = (
        FROZEN_REPLAY_PREDICTIONS_SCHEMA
        if activation_attempted
        else POINT_ONLY_REPLAY_PREDICTIONS_SCHEMA
    )
    for row in ordered:
        for field in schema:
            if "_band_" in field.name:
                value = getattr(row, field.name)
                if (value is None) == activation_attempted:
                    raise FrozenReplayError("Replay band fields disagree with activation state.")
    arrays = [
        pa.array([getattr(row, field.name) for row in ordered], type=field.type) for field in schema
    ]
    return pa.Table.from_arrays(arrays, schema=schema)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_replay_directory(
    output_root: Path, config_path: Path, source_manifest_path: Path
) -> Path:
    """Return the canonical directory keyed by both frozen input hashes."""
    return output_root / f"{_file_sha256(config_path)}_{_file_sha256(source_manifest_path)}"


def _run_git(repository_root: Path, arguments: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603 - fixed executable, no shell, internal arguments only
        ["git", *arguments],  # noqa: S607 - Git is an explicit repository prerequisite
        cwd=repository_root,
        check=False,
        capture_output=True,
    )


def _verify_committed_frozen_config(config_path: Path) -> tuple[Path, str, bool]:
    root_result = _run_git(config_path.parent, ("rev-parse", "--show-toplevel"))
    if root_result.returncode != 0:
        raise FrozenReplayError("Frozen replay must run from a Git worktree.")
    repository_root = Path(root_result.stdout.decode().strip()).resolve()
    try:
        relative_config = config_path.resolve().relative_to(repository_root)
    except ValueError as error:
        raise FrozenReplayError("Frozen config must be inside the Git worktree.") from error
    tracked = _run_git(
        repository_root,
        ("ls-files", "--error-unmatch", "--", relative_config.as_posix()),
    )
    if tracked.returncode != 0:
        raise FrozenReplayError("Frozen config must be tracked and committed before replay.")
    unchanged = _run_git(
        repository_root,
        ("diff", "--quiet", "HEAD", "--", relative_config.as_posix()),
    )
    if unchanged.returncode != 0:
        raise FrozenReplayError("Frozen config differs from HEAD; commit it before replay.")
    commit_result = _run_git(repository_root, ("rev-parse", "HEAD"))
    if commit_result.returncode != 0:
        raise FrozenReplayError("Unable to resolve the replay Git commit.")
    status_result = _run_git(repository_root, ("status", "--porcelain"))
    if status_result.returncode != 0:
        raise FrozenReplayError("Unable to inspect replay worktree status.")
    return (
        repository_root,
        commit_result.stdout.decode().strip(),
        bool(status_result.stdout.strip()),
    )


def _read_panel_rows(panel_path: Path, replay_target_year: int) -> tuple[dict[str, object], ...]:
    if not panel_path.is_file():
        raise FrozenReplayError(f"Trusted model panel not found: {panel_path}.")
    table = pq.read_table(
        panel_path,
        filters=[("target_cohort_year", "<=", replay_target_year)],
    )
    if table.schema != MODEL_PANEL_SCHEMA:
        raise FrozenReplayError("Trusted model panel schema does not match MODEL_PANEL_SCHEMA.")
    return tuple(cast(dict[str, object], row) for row in table.to_pylist())


def _methodology_ledger(manifest: DataSourceManifest) -> tuple[list[dict[str, object]], str]:
    entries: list[dict[str, object]] = []
    for source in manifest.sources:
        context: list[str] = []
        if source.cohort_year == 2020:
            context.append("COVID-19 pandemic cohort")
        if source.cohort_year == 2021:
            context.append("circle-based kidney allocation began 2021-03-15")
        if source.cohort_year == 2023:
            context.append("mixed monitoring context after OAR metric took effect 2023-07-27")
        if source.cohort_year >= 2024:
            context.append("full post-monitoring-policy cohort")
        entries.append(
            {
                "release_code": source.release_code,
                "cohort_year": source.cohort_year,
                "sheet_name": source.sheet_name,
                "published_value": source.published_value,
                "published_precision": source.published_precision,
                "kdpi_ge_60_fields_available": source.release_code in {"2505", "2605"},
                "context": context,
            }
        )
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return entries, sha256(payload).hexdigest()


def _write_json(value: Mapping[str, object], path: Path) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_frozen_replay(
    *,
    panel_path: Path,
    config_path: Path,
    source_manifest_path: Path,
    output_root: Path,
) -> FrozenReplayResult:
    """Execute and atomically publish the one canonical frozen replay."""
    repository_root, git_commit_sha, git_worktree_dirty = _verify_committed_frozen_config(
        config_path
    )
    config = load_frozen_experiment_config(config_path)
    manifest = load_data_source_manifest(source_manifest_path)
    destination = canonical_replay_directory(output_root, config_path, source_manifest_path)
    if destination.exists():
        raise FrozenReplayError(f"Canonical frozen replay output already exists: {destination}.")
    rows = _read_panel_rows(panel_path, config.replay_target_year)
    replay = generate_frozen_replay_predictions(rows, config=config)
    metrics = evaluate_frozen_replay(replay, rows=rows, config=config)

    config_sha256 = _file_sha256(config_path)
    source_manifest_sha256 = _file_sha256(source_manifest_path)
    panel_sha256 = _file_sha256(panel_path)
    lock_path = repository_root / "uv.lock"
    if not lock_path.is_file():
        raise FrozenReplayError("The committed dependency lockfile is required for replay.")
    methodology_ledger, methodology_ledger_sha256 = _methodology_ledger(manifest)
    feature_schema_payload = json.dumps(
        list(config.feature_columns), separators=(",", ":")
    ).encode()
    built_at_utc = datetime.now(UTC).isoformat()
    provenance: dict[str, object] = {
        "build_timestamp_utc": built_at_utc,
        "git_commit_sha": git_commit_sha,
        "git_worktree_dirty": git_worktree_dirty,
        "python_version": sys.version.split()[0],
        "dependency_lock_sha256": _file_sha256(lock_path),
        "frozen_experiment_sha256": config_sha256,
        "source_manifest_schema_version": manifest.schema_version,
        "source_manifest_sha256": source_manifest_sha256,
        "source_sha256": {
            source.release_code: source.download_sha256 for source in manifest.sources
        },
        "input_panel_sha256": panel_sha256,
        "feature_schema_sha256": sha256(feature_schema_payload).hexdigest(),
        "feature_columns": list(config.feature_columns),
        "training_target_years": list(replay.training_target_years),
        "calibration_target_year": config.band_calibration_target_year
        if config.forecast_activation_attempted
        else None,
        "replay_target_year": config.replay_target_year,
        "model_parameters": {
            "alpha": config.selected_ridge_alpha,
            "imputation": "median",
            "keep_empty_features": True,
            "scaling": "standard",
            "solver": "lsqr",
            "random_seed": config.ridge_random_seed,
        },
        "methodology_version_ledger_sha256": methodology_ledger_sha256,
    }
    if not config.forecast_activation_attempted:
        provenance["forecast_activation_attempted"] = False
    metrics["provenance"] = provenance
    metrics["methodology_version_ledger"] = methodology_ledger

    output_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".frozen-replay-staging-", dir=output_root))
    predictions_name = "replay_predictions.parquet"
    metrics_name = "replay_metrics.json"
    completion_name = "completion.json"
    try:
        table = frozen_replay_predictions_table(
            replay.predictions, activation_attempted=bool(config.forecast_activation_attempted)
        )
        table = table.replace_schema_metadata(
            {b"kasm_provenance": json.dumps(provenance, sort_keys=True).encode()}
        )
        predictions_path = staging / predictions_name
        metrics_path = staging / metrics_name
        pq.write_table(
            table,
            predictions_path,
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )
        _write_json(metrics, metrics_path)
        completion: dict[str, object] = {
            "status": "complete",
            "completed_at_utc": built_at_utc,
            "git_commit_sha": git_commit_sha,
            "git_worktree_dirty": git_worktree_dirty,
            "frozen_experiment_sha256": config_sha256,
            "source_manifest_sha256": source_manifest_sha256,
            "input_panel_sha256": panel_sha256,
            "prediction_rows": len(replay.predictions),
            "artifacts": {
                "predictions": predictions_name,
                "metrics": metrics_name,
            },
            "artifact_sha256": {
                "predictions": _file_sha256(predictions_path),
                "metrics": _file_sha256(metrics_path),
            },
        }
        _write_json(completion, staging / completion_name)
        if destination.exists():
            raise FrozenReplayError(
                f"Canonical frozen replay output already exists: {destination}."
            )
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    release_decision = cast(dict[str, object], metrics["release_decision"])
    return FrozenReplayResult(
        output_directory=destination,
        predictions_path=destination / predictions_name,
        metrics_path=destination / metrics_name,
        completion_path=destination / completion_name,
        prediction_rows=len(replay.predictions),
        displayed_model=cast(str, release_decision["displayed_model"]),
        display_band=cast(bool, release_decision["display_band"]),
    )
