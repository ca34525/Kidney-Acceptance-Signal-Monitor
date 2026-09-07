"""Choose and evaluate V1 Ridge regression using only years before the 2025 replay.

Ridge limits the fitted input weights with a penalty called alpha. Selection uses
average absolute log-OAR error in 2021-2023, giving each year equal weight. The
separate 2024 evaluation does not choose alpha.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from math import exp, isfinite
from pathlib import Path
from typing import Literal, cast

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
from sklearn.linear_model import Ridge  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from kasm.data.build import MODEL_PANEL_SCHEMA
from kasm.modeling.backtest import assign_volume_quartiles, build_rolling_origin_folds
from kasm.modeling.experiment import ExperimentConfig, load_experiment_config
from kasm.modeling.features import extract_feature_matrix

_RIDGE_MODEL_TYPE = pa.dictionary(pa.int8(), pa.string())

RIDGE_PREDICTIONS_SCHEMA = pa.schema(
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
        pa.field("model", _RIDGE_MODEL_TYPE, nullable=False),
        pa.field("ridge_alpha", pa.float64(), nullable=False),
        pa.field("predicted_log_oar", pa.float64(), nullable=False),
        pa.field("predicted_oar", pa.float64(), nullable=False),
        pa.field("absolute_error_log_oar", pa.float64(), nullable=False),
        pa.field("absolute_error_oar", pa.float64(), nullable=False),
        pa.field("signed_error_log_oar", pa.float64(), nullable=False),
        pa.field("persistence_absolute_error_log_oar", pa.float64(), nullable=False),
        pa.field("absolute_error_difference_vs_persistence", pa.float64(), nullable=False),
    ]
)


class ChallengerError(ValueError):
    """Raised when ridge evaluation would violate a pre-replay contract."""


@dataclass(frozen=True)
class RidgePrediction:
    """One ridge prediction paired with its persistence error."""

    program_key: str
    feature_cohort_year: int
    target_cohort_year: int
    fold_id: str
    first_observed_program: bool
    log1p_overall_expected_acceptances: float
    expected_acceptance_quartile: int
    target_log_oar: float
    target_oar: float
    model: Literal["ridge"]
    ridge_alpha: float
    predicted_log_oar: float
    predicted_oar: float
    absolute_error_log_oar: float
    absolute_error_oar: float
    signed_error_log_oar: float
    persistence_absolute_error_log_oar: float
    absolute_error_difference_vs_persistence: float


@dataclass(frozen=True)
class AlphaScore:
    """Year-balanced selection evidence for one fixed ridge alpha."""

    alpha: float
    mae_log_oar_by_target_year: tuple[tuple[int, float], ...]
    unweighted_mean_yearly_mae_log_oar: float
    row_pooled_mae_log_oar: float


@dataclass(frozen=True)
class RidgeSelection:
    """Selected alpha and all prespecified candidate scores."""

    selected_alpha: float
    selection_target_years: tuple[int, ...]
    candidate_scores: tuple[AlphaScore, ...]


@dataclass(frozen=True)
class PreReplayGate:
    """Result of the prespecified 2021–2024 ridge candidate gate."""

    passed: bool
    skill_over_persistence: float
    improved_years: int
    maximum_single_year_relative_worsening: float
    lowest_quartile_relative_worsening: float
    minimum_lowest_quartile_rows: int
    failed_criteria: tuple[str, ...]


@dataclass(frozen=True)
class RidgeBacktestResult:
    """Published paths and row count for the pre-replay ridge backtest."""

    predictions_path: Path
    metrics_path: Path
    selection_path: Path
    prediction_rows: int
    selected_alpha: float
    candidate_gate_passed: bool


def _required_float(row: Mapping[str, object], field: str) -> float:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ChallengerError(f"Panel field {field!r} must be numeric.")
    result = float(value)
    if not isfinite(result):
        raise ChallengerError(f"Panel field {field!r} must be finite.")
    return result


def _required_int(row: Mapping[str, object], field: str) -> int:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ChallengerError(f"Panel field {field!r} must be an integer.")
    return value


def _required_string(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ChallengerError(f"Panel field {field!r} must be non-empty text.")
    return value


def _required_bool(row: Mapping[str, object], field: str) -> bool:
    value = row.get(field)
    if not isinstance(value, bool):
        raise ChallengerError(f"Panel field {field!r} must be boolean.")
    return value


def _numpy_feature_matrix(
    rows: Sequence[Mapping[str, object]], feature_columns: Sequence[str]
) -> np.ndarray:
    matrix = extract_feature_matrix(rows, feature_columns)
    return np.asarray(
        [[np.nan if value is None else float(value) for value in row] for row in matrix],
        dtype=np.float64,
    )


def fit_ridge_pipeline(
    training_rows: Sequence[Mapping[str, object]],
    *,
    feature_columns: Sequence[str],
    target_column: str,
    alpha: float,
    random_seed: int,
) -> Pipeline:
    """Learn missing-value filling, input scaling, and Ridge from training rows only.

    Missing inputs use training medians (imputation); an entirely missing training
    column is retained with a zero fill. This is a modeling fallback, not a reported
    zero. Scaling uses training means and standard deviations. The caller supplies
    the temporally permitted rows,
    so evaluation outcomes cannot influence either preparation step or the fit.
    """
    if not training_rows:
        raise ChallengerError("Ridge training requires at least one row.")
    if alpha <= 0 or not isfinite(alpha):
        raise ChallengerError("Ridge alpha must be finite and positive.")
    features = _numpy_feature_matrix(training_rows, feature_columns)
    target = np.asarray(
        [_required_float(row, target_column) for row in training_rows], dtype=np.float64
    )
    pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
            (
                "ridge",
                Ridge(alpha=alpha, solver="lsqr", random_state=random_seed),
            ),
        ]
    )
    pipeline.fit(features, target)
    return pipeline


def _generate_ridge_predictions(
    rows: Sequence[Mapping[str, object]],
    config: ExperimentConfig,
    alpha: float,
    evaluation_target_years: Sequence[int],
) -> tuple[RidgePrediction, ...]:
    folds = build_rolling_origin_folds(
        rows,
        evaluation_target_years=evaluation_target_years,
        training_target_year_start=config.training_target_year_start,
    )
    quartiles = assign_volume_quartiles(rows)
    predictions: list[RidgePrediction] = []
    for fold in folds:
        training_rows = tuple(rows[index] for index in fold.training_row_indices)
        pipeline = fit_ridge_pipeline(
            training_rows,
            feature_columns=config.feature_columns,
            target_column=config.target_column,
            alpha=alpha,
            random_seed=config.ridge_random_seed,
        )
        ordered_indices = sorted(
            fold.evaluation_row_indices,
            key=lambda index: _required_string(rows[index], "program_key"),
        )
        evaluation_rows = tuple(rows[index] for index in ordered_indices)
        predicted_values = pipeline.predict(
            _numpy_feature_matrix(evaluation_rows, config.feature_columns)
        )
        for row, predicted_value in zip(evaluation_rows, predicted_values, strict=True):
            program_key = _required_string(row, "program_key")
            feature_year = _required_int(row, "feature_cohort_year")
            target_year = _required_int(row, "target_cohort_year")
            target_log = _required_float(row, config.target_column)
            target_oar = _required_float(row, "target_oar")
            predicted_log = float(predicted_value)
            predicted_oar = exp(predicted_log)
            absolute_log_error = abs(predicted_log - target_log)
            persistence_error = abs(_required_float(row, "current_log_overall_oar") - target_log)
            predictions.append(
                RidgePrediction(
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
                    model="ridge",
                    ridge_alpha=alpha,
                    predicted_log_oar=predicted_log,
                    predicted_oar=predicted_oar,
                    absolute_error_log_oar=absolute_log_error,
                    absolute_error_oar=abs(predicted_oar - target_oar),
                    signed_error_log_oar=predicted_log - target_log,
                    persistence_absolute_error_log_oar=persistence_error,
                    absolute_error_difference_vs_persistence=(
                        absolute_log_error - persistence_error
                    ),
                )
            )
    return tuple(predictions)


def generate_ridge_predictions(
    rows: Sequence[Mapping[str, object]], config: ExperimentConfig, alpha: float
) -> tuple[RidgePrediction, ...]:
    """Generate rolling ridge predictions through validation, never replay."""
    return _generate_ridge_predictions(
        rows, config, alpha, config.pre_replay_evaluation_target_years
    )


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ChallengerError("A ridge metric group cannot be empty.")
    return sum(values) / len(values)


def choose_ridge_alpha(scores: Mapping[float, float], *, relative_tolerance: float) -> float:
    """Prefer the stronger Ridge penalty when errors are within the fixed tolerance."""
    if not scores:
        raise ChallengerError("Ridge selection requires at least one alpha score.")
    if relative_tolerance < 0 or not isfinite(relative_tolerance):
        raise ChallengerError("Alpha tie tolerance must be finite and nonnegative.")
    if any(alpha <= 0 or not isfinite(alpha) for alpha in scores):
        raise ChallengerError("Ridge alpha values must be finite and positive.")
    if any(score < 0 or not isfinite(score) for score in scores.values()):
        raise ChallengerError("Ridge alpha scores must be finite and nonnegative.")
    best = min(scores.values())
    threshold = best * (1 + relative_tolerance)
    return max(alpha for alpha, score in scores.items() if score <= threshold)


def select_ridge_alpha(
    rows: Sequence[Mapping[str, object]], config: ExperimentConfig
) -> RidgeSelection:
    """Select alpha on year-balanced 2021–2023 rolling-origin MAE only."""
    candidate_scores: list[AlphaScore] = []
    for alpha in config.ridge_alpha_grid:
        predictions = _generate_ridge_predictions(
            rows, config, alpha, config.selection_target_years
        )
        yearly = tuple(
            (
                target_year,
                _mean(
                    [
                        row.absolute_error_log_oar
                        for row in predictions
                        if row.target_cohort_year == target_year
                    ]
                ),
            )
            for target_year in config.selection_target_years
        )
        candidate_scores.append(
            AlphaScore(
                alpha=alpha,
                mae_log_oar_by_target_year=yearly,
                unweighted_mean_yearly_mae_log_oar=_mean([value for _, value in yearly]),
                row_pooled_mae_log_oar=_mean([row.absolute_error_log_oar for row in predictions]),
            )
        )
    selected_alpha = choose_ridge_alpha(
        {score.alpha: score.unweighted_mean_yearly_mae_log_oar for score in candidate_scores},
        relative_tolerance=config.ridge_alpha_tie_relative_tolerance,
    )
    return RidgeSelection(
        selected_alpha=selected_alpha,
        selection_target_years=config.selection_target_years,
        candidate_scores=tuple(candidate_scores),
    )


def _relative_worsening(challenger: float, persistence: float) -> float:
    if persistence == 0:
        return 0.0 if challenger == 0 else float("inf")
    return challenger / persistence - 1


def assess_pre_replay_candidate(
    *,
    challenger_mae_by_year: Mapping[int, float],
    persistence_mae_by_year: Mapping[int, float],
    challenger_lowest_quartile_mae_by_year: Mapping[int, float],
    persistence_lowest_quartile_mae_by_year: Mapping[int, float],
    lowest_quartile_rows_by_year: Mapping[int, int],
    config: ExperimentConfig,
) -> PreReplayGate:
    """Apply every prespecified pre-replay point-candidate criterion."""
    years = config.pre_replay_evaluation_target_years
    mappings: tuple[Mapping[int, object], ...] = (
        challenger_mae_by_year,
        persistence_mae_by_year,
        challenger_lowest_quartile_mae_by_year,
        persistence_lowest_quartile_mae_by_year,
        lowest_quartile_rows_by_year,
    )
    if any(set(mapping) != set(years) for mapping in mappings):
        raise ChallengerError(
            f"Pre-replay gate evidence must contain exactly target years {years}."
        )
    challenger_mean = _mean([challenger_mae_by_year[year] for year in years])
    persistence_mean = _mean([persistence_mae_by_year[year] for year in years])
    skill = 0.0 if persistence_mean == 0 else 1 - challenger_mean / persistence_mean
    improved_years = sum(
        challenger_mae_by_year[year] < persistence_mae_by_year[year] for year in years
    )
    maximum_worsening = max(
        _relative_worsening(challenger_mae_by_year[year], persistence_mae_by_year[year])
        for year in years
    )
    challenger_low_mean = _mean([challenger_lowest_quartile_mae_by_year[year] for year in years])
    persistence_low_mean = _mean([persistence_lowest_quartile_mae_by_year[year] for year in years])
    lowest_quartile_worsening = _relative_worsening(challenger_low_mean, persistence_low_mean)
    minimum_rows = min(lowest_quartile_rows_by_year.values())

    failed: list[str] = []
    if skill < config.pre_replay_minimum_skill_over_persistence:
        failed.append("minimum_skill_over_persistence")
    if improved_years < config.pre_replay_minimum_improved_years:
        failed.append("minimum_improved_years")
    if maximum_worsening > config.pre_replay_maximum_single_year_relative_worsening:
        failed.append("single_year_relative_worsening")
    if minimum_rows < config.minimum_lowest_quartile_rows:
        failed.append("lowest_quartile_minimum_rows")
    if lowest_quartile_worsening > config.pre_replay_maximum_lowest_quartile_relative_worsening:
        failed.append("lowest_quartile_relative_worsening")
    return PreReplayGate(
        passed=not failed,
        skill_over_persistence=skill,
        improved_years=improved_years,
        maximum_single_year_relative_worsening=maximum_worsening,
        lowest_quartile_relative_worsening=lowest_quartile_worsening,
        minimum_lowest_quartile_rows=minimum_rows,
        failed_criteria=tuple(failed),
    )


def _calibration_slope(predictions: Sequence[RidgePrediction]) -> float | None:
    predicted_mean = _mean([row.predicted_log_oar for row in predictions])
    outcome_mean = _mean([row.target_log_oar for row in predictions])
    denominator = sum((row.predicted_log_oar - predicted_mean) ** 2 for row in predictions)
    if denominator == 0:
        return None
    return (
        sum(
            (row.predicted_log_oar - predicted_mean) * (row.target_log_oar - outcome_mean)
            for row in predictions
        )
        / denominator
    )


def _metric_record(predictions: Sequence[RidgePrediction]) -> dict[str, object]:
    ridge_mae = _mean([row.absolute_error_log_oar for row in predictions])
    persistence_mae = _mean([row.persistence_absolute_error_log_oar for row in predictions])
    return {
        "n": len(predictions),
        "mae_log_oar": ridge_mae,
        "mae_oar": _mean([row.absolute_error_oar for row in predictions]),
        "persistence_mae_log_oar": persistence_mae,
        "skill_over_persistence": (
            None if persistence_mae == 0 else 1 - ridge_mae / persistence_mae
        ),
        "mean_signed_log_error": _mean([row.signed_error_log_oar for row in predictions]),
        "calibration_slope": _calibration_slope(predictions),
        "mean_paired_absolute_error_difference_vs_persistence": _mean(
            [row.absolute_error_difference_vs_persistence for row in predictions]
        ),
    }


def evaluate_ridge_predictions(
    predictions: Sequence[RidgePrediction], config: ExperimentConfig
) -> dict[str, object]:
    """Calculate pre-replay ridge metrics and candidate-gate evidence."""
    years = config.pre_replay_evaluation_target_years
    if {row.target_cohort_year for row in predictions} != set(years):
        raise ChallengerError(f"Ridge metrics require exactly target years {years}.")
    by_year: list[dict[str, object]] = []
    by_quartile: list[dict[str, object]] = []
    for year in years:
        year_rows = [row for row in predictions if row.target_cohort_year == year]
        by_year.append({"target_year": year, **_metric_record(year_rows)})
        for quartile in range(1, 5):
            group = [row for row in year_rows if row.expected_acceptance_quartile == quartile]
            if group:
                by_quartile.append(
                    {
                        "target_year": year,
                        "expected_acceptance_quartile": quartile,
                        **_metric_record(group),
                    }
                )
    ridge_by_year = {
        cast(int, record["target_year"]): cast(float, record["mae_log_oar"]) for record in by_year
    }
    persistence_by_year = {
        cast(int, record["target_year"]): cast(float, record["persistence_mae_log_oar"])
        for record in by_year
    }
    lowest = {
        cast(int, record["target_year"]): record
        for record in by_quartile
        if record["expected_acceptance_quartile"] == 1
    }
    gate = assess_pre_replay_candidate(
        challenger_mae_by_year=ridge_by_year,
        persistence_mae_by_year=persistence_by_year,
        challenger_lowest_quartile_mae_by_year={
            year: cast(float, lowest[year]["mae_log_oar"]) for year in years
        },
        persistence_lowest_quartile_mae_by_year={
            year: cast(float, lowest[year]["persistence_mae_log_oar"]) for year in years
        },
        lowest_quartile_rows_by_year={year: cast(int, lowest[year]["n"]) for year in years},
        config=config,
    )
    return {
        "metric_definitions": {
            "primary": "unweighted mean of per-target-year MAE on published log OAR",
            "skill_over_persistence": "1 - ridge MAE / persistence MAE",
            "paired_difference": ("ridge absolute log error minus persistence absolute log error"),
        },
        "evaluated_target_years": list(years),
        "frozen_replay_target_year": config.replay_target_year,
        "frozen_replay_evaluated": False,
        "selection_summary": {
            "target_years": list(years),
            "unweighted_mean_yearly_mae_log_oar": _mean([ridge_by_year[year] for year in years]),
            "persistence_unweighted_mean_yearly_mae_log_oar": _mean(
                [persistence_by_year[year] for year in years]
            ),
            "row_pooled_mae_log_oar": _mean([row.absolute_error_log_oar for row in predictions]),
        },
        "by_target_year": by_year,
        "by_target_year_and_expected_acceptance_quartile": by_quartile,
        "pre_replay_candidate_gate": asdict(gate),
    }


def ridge_predictions_table(predictions: Sequence[RidgePrediction]) -> pa.Table:
    """Return ridge predictions in a stable, exact Parquet schema."""
    ordered = sorted(predictions, key=lambda row: (row.target_cohort_year, row.program_key))
    arrays = [
        pa.array([getattr(row, field.name) for row in ordered], type=field.type)
        for field in RIDGE_PREDICTIONS_SCHEMA
    ]
    return pa.Table.from_arrays(arrays, schema=RIDGE_PREDICTIONS_SCHEMA)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_panel_rows(
    panel_path: Path, *, maximum_target_year: int
) -> tuple[dict[str, object], ...]:
    if not panel_path.is_file():
        raise ChallengerError(f"Trusted model panel not found: {panel_path}.")
    table = pq.read_table(panel_path, filters=[("target_cohort_year", "<=", maximum_target_year)])
    if table.schema != MODEL_PANEL_SCHEMA:
        raise ChallengerError("Trusted model panel schema does not match MODEL_PANEL_SCHEMA.")
    return tuple(cast(dict[str, object], row) for row in table.to_pylist())


def _write_json(value: Mapping[str, object], path: Path) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _selection_record(selection: RidgeSelection) -> dict[str, object]:
    return {
        "selection_method": "unweighted_mean_of_target_year_maes",
        "tie_rule": "largest_alpha_within_one_percent_of_best",
        "selection_target_years": list(selection.selection_target_years),
        "selected_alpha": selection.selected_alpha,
        "candidate_scores": [asdict(score) for score in selection.candidate_scores],
        "frozen_replay_evaluated": False,
    }


def run_ridge_backtest(
    panel_path: Path, config_path: Path, output_dir: Path
) -> RidgeBacktestResult:
    """Run and publish the offline pre-replay ridge evaluation."""
    config = load_experiment_config(config_path)
    rows = _read_panel_rows(panel_path, maximum_target_year=config.validation_target_year)
    selection = select_ridge_alpha(rows, config)
    predictions = generate_ridge_predictions(rows, config, selection.selected_alpha)
    metrics = evaluate_ridge_predictions(predictions, config)
    metrics["selected_alpha"] = selection.selected_alpha
    metrics["model_parameters"] = {
        "alpha": selection.selected_alpha,
        "imputation": "median",
        "keep_empty_features": True,
        "scaling": "standard",
        "solver": "lsqr",
        "random_seed": config.ridge_random_seed,
    }
    metrics["input_panel_sha256"] = _file_sha256(panel_path)
    metrics["experiment_config_sha256"] = _file_sha256(config_path)
    selection_record = _selection_record(selection)
    selection_record["input_panel_sha256"] = _file_sha256(panel_path)
    selection_record["experiment_config_sha256"] = _file_sha256(config_path)
    selection_record["random_seed"] = config.ridge_random_seed

    output_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=".ridge-staging-", dir=output_dir.parent))
    try:
        pq.write_table(
            ridge_predictions_table(predictions),
            staging_dir / "ridge_predictions.parquet",
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )
        _write_json(metrics, staging_dir / "ridge_metrics.json")
        _write_json(selection_record, staging_dir / "ridge_selection.json")
        for filename in (
            "ridge_predictions.parquet",
            "ridge_metrics.json",
            "ridge_selection.json",
        ):
            os.replace(staging_dir / filename, output_dir / filename)
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

    gate = cast(dict[str, object], metrics["pre_replay_candidate_gate"])
    return RidgeBacktestResult(
        predictions_path=output_dir / "ridge_predictions.parquet",
        metrics_path=output_dir / "ridge_metrics.json",
        selection_path=output_dir / "ridge_selection.json",
        prediction_rows=len(predictions),
        selected_alpha=selection.selected_alpha,
        candidate_gate_passed=cast(bool, gate["passed"]),
    )
