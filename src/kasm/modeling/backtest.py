"""Deterministic rolling-origin evaluation for prespecified baseline models."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from math import exp, floor, isfinite
from pathlib import Path
from typing import Literal, cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from kasm.data.build import MODEL_PANEL_SCHEMA
from kasm.modeling.experiment import ExperimentConfig, load_experiment_config
from kasm.modeling.features import extract_feature_matrix

BaselineName = Literal["neutral", "persistence", "historical_mean"]
DEFAULT_EVALUATION_TARGET_YEARS = (2021, 2022, 2023, 2024)
_BASELINE_ORDER: tuple[BaselineName, ...] = ("neutral", "persistence", "historical_mean")
_MODEL_TYPE = pa.dictionary(pa.int8(), pa.string())

BASELINE_PREDICTIONS_SCHEMA = pa.schema(
    [
        pa.field("program_key", pa.string(), nullable=False),
        pa.field("feature_cohort_year", pa.int16(), nullable=False),
        pa.field("target_cohort_year", pa.int16(), nullable=False),
        pa.field("fold_id", pa.string(), nullable=False),
        pa.field("first_observed_program", pa.bool_(), nullable=False),
        pa.field("log1p_overall_expected_acceptances", pa.float64(), nullable=False),
        pa.field("expected_acceptance_quartile", pa.int8(), nullable=False),
        pa.field("target_log_oar", pa.float64(), nullable=False),
        pa.field("target_oar", pa.float64(), nullable=False),
        pa.field("model", _MODEL_TYPE, nullable=False),
        pa.field("predicted_log_oar", pa.float64(), nullable=False),
        pa.field("predicted_oar", pa.float64(), nullable=False),
        pa.field("absolute_error_log_oar", pa.float64(), nullable=False),
        pa.field("absolute_error_oar", pa.float64(), nullable=False),
        pa.field("signed_error_log_oar", pa.float64(), nullable=False),
        pa.field("absolute_error_difference_vs_persistence", pa.float64(), nullable=False),
    ]
)


class BacktestError(ValueError):
    """Raised when temporal evaluation would violate a modeling contract."""


@dataclass(frozen=True)
class TemporalFold:
    """One expanding training window and intact target-year evaluation group."""

    fold_id: str
    training_target_years: tuple[int, ...]
    evaluation_target_year: int
    training_row_indices: tuple[int, ...]
    evaluation_row_indices: tuple[int, ...]


@dataclass(frozen=True)
class BaselinePrediction:
    """One paired baseline prediction for an analytic program-year."""

    program_key: str
    feature_cohort_year: int
    target_cohort_year: int
    fold_id: str
    first_observed_program: bool
    log1p_overall_expected_acceptances: float
    expected_acceptance_quartile: int
    target_log_oar: float
    target_oar: float
    model: BaselineName
    predicted_log_oar: float
    predicted_oar: float
    absolute_error_log_oar: float
    absolute_error_oar: float
    signed_error_log_oar: float
    absolute_error_difference_vs_persistence: float


@dataclass(frozen=True)
class BaselineBacktestResult:
    """Published paths and row count for one baseline backtest."""

    predictions_path: Path
    metrics_path: Path
    folds_path: Path
    prediction_rows: int


def _required_int(row: Mapping[str, object], field: str) -> int:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise BacktestError(f"Panel field {field!r} must be an integer.")
    return value


def _required_float(row: Mapping[str, object], field: str) -> float:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise BacktestError(f"Panel field {field!r} must be numeric.")
    result = float(value)
    if not isfinite(result):
        raise BacktestError(f"Panel field {field!r} must be finite.")
    return result


def _required_bool(row: Mapping[str, object], field: str) -> bool:
    value = row.get(field)
    if not isinstance(value, bool):
        raise BacktestError(f"Panel field {field!r} must be boolean.")
    return value


def _required_string(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise BacktestError(f"Panel field {field!r} must be non-empty text.")
    return value


def _validate_panel_alignment(rows: Sequence[Mapping[str, object]]) -> None:
    seen: set[tuple[str, int]] = set()
    for row in rows:
        program_key = _required_string(row, "program_key")
        feature_year = _required_int(row, "feature_cohort_year")
        target_year = _required_int(row, "target_cohort_year")
        if target_year != feature_year + 1:
            raise BacktestError(
                f"{program_key} target cohort {target_year} must be the adjacent calendar year "
                f"after feature cohort {feature_year}."
            )
        key = (program_key, feature_year)
        if key in seen:
            raise BacktestError(f"Panel duplicates program-feature-year key {key!r}.")
        seen.add(key)


def build_rolling_origin_folds(
    rows: Sequence[Mapping[str, object]],
    *,
    evaluation_target_years: Sequence[int] = DEFAULT_EVALUATION_TARGET_YEARS,
    training_target_year_start: int = 2018,
) -> tuple[TemporalFold, ...]:
    """Build expanding folds without exposing a random row-split interface."""
    _validate_panel_alignment(rows)
    if tuple(evaluation_target_years) != tuple(sorted(set(evaluation_target_years))):
        raise BacktestError("Evaluation target years must be unique and increasing.")

    analytic_indices = tuple(
        index for index, row in enumerate(rows) if _required_bool(row, "analytic_eligible")
    )
    folds: list[TemporalFold] = []
    for evaluation_year in evaluation_target_years:
        evaluation_indices = tuple(
            index
            for index in analytic_indices
            if _required_int(rows[index], "target_cohort_year") == evaluation_year
        )
        if not evaluation_indices:
            raise BacktestError(
                f"Evaluation target year {evaluation_year} has no analytic-eligible rows."
            )
        training_indices = tuple(
            index
            for index in analytic_indices
            if training_target_year_start
            <= _required_int(rows[index], "target_cohort_year")
            < evaluation_year
        )
        training_years = tuple(
            sorted({_required_int(rows[index], "target_cohort_year") for index in training_indices})
        )
        expected_training_years = tuple(range(training_target_year_start, evaluation_year))
        if training_years != expected_training_years:
            raise BacktestError(
                f"Fold target {evaluation_year} requires analytic training target years "
                f"{expected_training_years}, found {training_years}."
            )
        folds.append(
            TemporalFold(
                fold_id=f"target_{evaluation_year}",
                training_target_years=training_years,
                evaluation_target_year=evaluation_year,
                training_row_indices=training_indices,
                evaluation_row_indices=evaluation_indices,
            )
        )
    return tuple(folds)


def assign_volume_quartiles(
    rows: Sequence[Mapping[str, object]],
) -> dict[tuple[str, int], int]:
    """Assign deterministic within-target-year expected-acceptance quartiles."""
    _validate_panel_alignment(rows)
    rows_by_year: dict[int, list[Mapping[str, object]]] = {}
    for row in rows:
        if not _required_bool(row, "analytic_eligible"):
            continue
        target_year = _required_int(row, "target_cohort_year")
        rows_by_year.setdefault(target_year, []).append(row)

    assignments: dict[tuple[str, int], int] = {}
    for target_year, year_rows in rows_by_year.items():
        ordered = sorted(
            year_rows,
            key=lambda row: (
                _required_float(row, "log1p_overall_expected_acceptances"),
                _required_string(row, "program_key"),
            ),
        )
        count = len(ordered)
        for rank, row in enumerate(ordered):
            key = (_required_string(row, "program_key"), target_year)
            assignments[key] = min(4, 1 + floor(4 * rank / count))
    return assignments


def _history_by_program(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, tuple[tuple[int, float], ...]]:
    history: dict[str, list[tuple[int, float]]] = {}
    for row in rows:
        program_key = _required_string(row, "program_key")
        feature_year = _required_int(row, "feature_cohort_year")
        current = _required_float(row, "current_log_overall_oar")
        history.setdefault(program_key, []).append((feature_year, current))
    return {key: tuple(sorted(values)) for key, values in history.items()}


def generate_baseline_predictions(
    rows: Sequence[Mapping[str, object]],
    *,
    evaluation_target_years: Sequence[int] = DEFAULT_EVALUATION_TARGET_YEARS,
    training_target_year_start: int = 2018,
) -> tuple[BaselinePrediction, ...]:
    """Generate paired baseline predictions for intact pre-replay target-year folds."""
    folds = build_rolling_origin_folds(
        rows,
        evaluation_target_years=evaluation_target_years,
        training_target_year_start=training_target_year_start,
    )
    quartiles = assign_volume_quartiles(rows)
    history = _history_by_program(rows)
    predictions: list[BaselinePrediction] = []

    for fold in folds:
        ordered_indices = sorted(
            fold.evaluation_row_indices,
            key=lambda index: _required_string(rows[index], "program_key"),
        )
        for index in ordered_indices:
            row = rows[index]
            program_key = _required_string(row, "program_key")
            feature_year = _required_int(row, "feature_cohort_year")
            target_year = _required_int(row, "target_cohort_year")
            target_log = _required_float(row, "target_log_oar")
            target_oar = _required_float(row, "target_oar")
            current_log = _required_float(row, "current_log_overall_oar")
            available_history = tuple(
                value for year, value in history.get(program_key, ()) if year <= feature_year
            )
            historical_mean = (
                sum(available_history) / len(available_history) if available_history else 0.0
            )
            persistence_error = abs(current_log - target_log)
            model_values: tuple[tuple[BaselineName, float], ...] = (
                ("neutral", 0.0),
                ("persistence", current_log),
                ("historical_mean", historical_mean),
            )
            for model, predicted_log in model_values:
                predicted_oar = exp(predicted_log)
                absolute_log_error = abs(predicted_log - target_log)
                predictions.append(
                    BaselinePrediction(
                        program_key=program_key,
                        feature_cohort_year=feature_year,
                        target_cohort_year=target_year,
                        fold_id=fold.fold_id,
                        first_observed_program=_required_bool(row, "first_observed_program"),
                        log1p_overall_expected_acceptances=_required_float(
                            row, "log1p_overall_expected_acceptances"
                        ),
                        expected_acceptance_quartile=quartiles[(program_key, target_year)],
                        target_log_oar=target_log,
                        target_oar=target_oar,
                        model=model,
                        predicted_log_oar=predicted_log,
                        predicted_oar=predicted_oar,
                        absolute_error_log_oar=absolute_log_error,
                        absolute_error_oar=abs(predicted_oar - target_oar),
                        signed_error_log_oar=predicted_log - target_log,
                        absolute_error_difference_vs_persistence=(
                            absolute_log_error - persistence_error
                        ),
                    )
                )
    return tuple(predictions)


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise BacktestError("A metric group cannot be empty.")
    return sum(values) / len(values)


def _calibration_slope(predictions: Sequence[BaselinePrediction]) -> float | None:
    predicted = [row.predicted_log_oar for row in predictions]
    outcomes = [row.target_log_oar for row in predictions]
    predicted_mean = _mean(predicted)
    outcome_mean = _mean(outcomes)
    denominator = sum((value - predicted_mean) ** 2 for value in predicted)
    if denominator == 0:
        return None
    numerator = sum(
        (prediction - predicted_mean) * (outcome - outcome_mean)
        for prediction, outcome in zip(predicted, outcomes, strict=True)
    )
    return numerator / denominator


def _metric_values(predictions: Sequence[BaselinePrediction]) -> dict[str, object]:
    return {
        "n": len(predictions),
        "mae_log_oar": _mean([row.absolute_error_log_oar for row in predictions]),
        "mae_oar": _mean([row.absolute_error_oar for row in predictions]),
        "mean_signed_log_error": _mean([row.signed_error_log_oar for row in predictions]),
        "calibration_slope": _calibration_slope(predictions),
        "mean_paired_absolute_error_difference_vs_persistence": _mean(
            [row.absolute_error_difference_vs_persistence for row in predictions]
        ),
    }


def _with_skill(
    records: list[dict[str, object]], key_fields: Sequence[str]
) -> list[dict[str, object]]:
    persistence: dict[tuple[object, ...], float] = {}
    for record in records:
        if record["model"] == "persistence":
            key = tuple(record[field] for field in key_fields)
            persistence[key] = cast(float, record["mae_log_oar"])
    for record in records:
        key = tuple(record[field] for field in key_fields)
        reference = persistence[key]
        mae = cast(float, record["mae_log_oar"])
        record["skill_over_persistence"] = None if reference == 0 else 1 - mae / reference
    return records


def evaluate_baselines(
    predictions: Sequence[BaselinePrediction],
    *,
    summary_target_years: Sequence[int] | None = None,
) -> dict[str, object]:
    """Calculate year-specific, quartile, paired, and year-balanced baseline metrics."""
    if not predictions:
        raise BacktestError("Baseline evaluation requires at least one prediction.")
    target_years = tuple(sorted({row.target_cohort_year for row in predictions}))
    summary_years = (
        tuple(summary_target_years) if summary_target_years is not None else target_years
    )
    missing_summary_years = sorted(set(summary_years) - set(target_years))
    if missing_summary_years:
        raise BacktestError(
            f"Summary target years are missing predictions: {missing_summary_years}."
        )

    by_year: list[dict[str, object]] = []
    by_quartile: list[dict[str, object]] = []
    for target_year in target_years:
        for model in _BASELINE_ORDER:
            group = [
                row
                for row in predictions
                if row.target_cohort_year == target_year and row.model == model
            ]
            by_year.append({"target_year": target_year, "model": model, **_metric_values(group)})
            for quartile in range(1, 5):
                quartile_group = [
                    row for row in group if row.expected_acceptance_quartile == quartile
                ]
                if quartile_group:
                    by_quartile.append(
                        {
                            "target_year": target_year,
                            "expected_acceptance_quartile": quartile,
                            "model": model,
                            **_metric_values(quartile_group),
                        }
                    )
    _with_skill(by_year, ("target_year",))
    _with_skill(by_quartile, ("target_year", "expected_acceptance_quartile"))

    selection_summary: list[dict[str, object]] = []
    for model in _BASELINE_ORDER:
        model_rows = [
            row
            for row in predictions
            if row.model == model and row.target_cohort_year in summary_years
        ]
        yearly_maes = [
            cast(
                float,
                next(
                    record["mae_log_oar"]
                    for record in by_year
                    if record["target_year"] == year and record["model"] == model
                ),
            )
            for year in summary_years
        ]
        mean_yearly_mae = _mean(yearly_maes)
        persistence_yearly_maes = [
            cast(
                float,
                next(
                    record["mae_log_oar"]
                    for record in by_year
                    if record["target_year"] == year and record["model"] == "persistence"
                ),
            )
            for year in summary_years
        ]
        persistence_mean = _mean(persistence_yearly_maes)
        selection_summary.append(
            {
                "model": model,
                "target_years": list(summary_years),
                "unweighted_mean_yearly_mae_log_oar": mean_yearly_mae,
                "row_pooled_mae_log_oar": _mean([row.absolute_error_log_oar for row in model_rows]),
                "skill_over_persistence": (
                    None if persistence_mean == 0 else 1 - mean_yearly_mae / persistence_mean
                ),
            }
        )

    return {
        "metric_definitions": {
            "primary": "unweighted mean of per-target-year MAE on published log OAR",
            "mae_oar": "mean absolute error on the original published OAR scale",
            "skill_over_persistence": "1 - model MAE / persistence MAE",
            "mean_signed_log_error": "mean prediction minus mean outcome on the log scale",
            "paired_difference": "model absolute log error minus persistence absolute log error",
        },
        "selection_summary": selection_summary,
        "by_target_year": by_year,
        "by_target_year_and_expected_acceptance_quartile": by_quartile,
    }


def baseline_predictions_table(predictions: Sequence[BaselinePrediction]) -> pa.Table:
    """Return baseline predictions in a stable, exact Parquet schema."""
    ordered = sorted(
        predictions,
        key=lambda row: (
            row.target_cohort_year,
            row.program_key,
            _BASELINE_ORDER.index(row.model),
        ),
    )
    arrays = [
        pa.array([getattr(row, field.name) for row in ordered], type=field.type)
        for field in BASELINE_PREDICTIONS_SCHEMA
    ]
    return pa.Table.from_arrays(arrays, schema=BASELINE_PREDICTIONS_SCHEMA)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fold_report(folds: Sequence[TemporalFold]) -> dict[str, object]:
    return {
        "split_method": "rolling_origin_by_target_year",
        "random_row_split_available": False,
        "folds": [
            {
                "fold_id": fold.fold_id,
                "training_target_years": list(fold.training_target_years),
                "evaluation_target_year": fold.evaluation_target_year,
                "training_rows": len(fold.training_row_indices),
                "evaluation_rows": len(fold.evaluation_row_indices),
            }
            for fold in folds
        ],
    }


def _write_json(value: Mapping[str, object], path: Path) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _read_panel_rows(
    panel_path: Path, *, maximum_target_year: int
) -> tuple[dict[str, object], ...]:
    if not panel_path.is_file():
        raise BacktestError(f"Trusted model panel not found: {panel_path}.")
    table = pq.read_table(panel_path, filters=[("target_cohort_year", "<=", maximum_target_year)])
    if table.schema != MODEL_PANEL_SCHEMA:
        raise BacktestError("Trusted model panel schema does not match MODEL_PANEL_SCHEMA.")
    return tuple(cast(dict[str, object], row) for row in table.to_pylist())


def _run_from_rows(
    rows: tuple[dict[str, object], ...], config: ExperimentConfig
) -> tuple[tuple[BaselinePrediction, ...], tuple[TemporalFold, ...], dict[str, object]]:
    extract_feature_matrix(rows, config.feature_columns)
    evaluation_years = config.pre_replay_evaluation_target_years
    folds = build_rolling_origin_folds(
        rows,
        evaluation_target_years=evaluation_years,
        training_target_year_start=config.training_target_year_start,
    )
    predictions = generate_baseline_predictions(
        rows,
        evaluation_target_years=evaluation_years,
        training_target_year_start=config.training_target_year_start,
    )
    metrics = evaluate_baselines(predictions, summary_target_years=config.selection_target_years)
    metrics["evaluated_target_years"] = list(evaluation_years)
    metrics["frozen_replay_target_year"] = config.replay_target_year
    metrics["frozen_replay_evaluated"] = False
    return predictions, folds, metrics


def run_baseline_backtest(
    panel_path: Path, config_path: Path, output_dir: Path
) -> BaselineBacktestResult:
    """Run the offline pre-replay baseline evaluation and publish its artifact set."""
    config = load_experiment_config(config_path)
    rows = _read_panel_rows(panel_path, maximum_target_year=config.validation_target_year)
    predictions, folds, metrics = _run_from_rows(rows, config)
    metrics["input_panel_sha256"] = _file_sha256(panel_path)
    metrics["experiment_config_sha256"] = _file_sha256(config_path)

    output_parent = output_dir.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-staging-", dir=output_parent))
    published_staging_dir = False
    try:
        staged_predictions = staging_dir / "baseline_predictions.parquet"
        staged_metrics = staging_dir / "baseline_metrics.json"
        staged_folds = staging_dir / "temporal_folds.json"
        pq.write_table(
            baseline_predictions_table(predictions),
            staged_predictions,
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )
        _write_json(metrics, staged_metrics)
        fold_report = _fold_report(folds)
        fold_report["input_panel_sha256"] = _file_sha256(panel_path)
        fold_report["experiment_config_sha256"] = _file_sha256(config_path)
        _write_json(fold_report, staged_folds)

        filenames = (
            "baseline_predictions.parquet",
            "baseline_metrics.json",
            "temporal_folds.json",
        )
        if not output_dir.exists():
            os.replace(staging_dir, output_dir)
            published_staging_dir = True
        else:
            if not output_dir.is_dir():
                raise BacktestError(f"Output path {output_dir} exists and is not a directory.")
            for filename in filenames:
                os.replace(staging_dir / filename, output_dir / filename)
    finally:
        if not published_staging_dir:
            shutil.rmtree(staging_dir, ignore_errors=True)

    return BaselineBacktestResult(
        predictions_path=output_dir / "baseline_predictions.parquet",
        metrics_path=output_dir / "baseline_metrics.json",
        folds_path=output_dir / "temporal_folds.json",
        prediction_rows=len(predictions),
    )
