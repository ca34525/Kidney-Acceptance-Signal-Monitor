"""Predict each later annual report using only information public at that origin.

These separately identified historical fits include the latest permitted training outcome.
Their bands use the preceding year's predictions made without that year's outcomes.
They do not replace the original frozen fit or reuse its residual band.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from math import ceil, exp, isclose, isfinite, log
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray
from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
from sklearn.linear_model import Ridge  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from kasm.acceptance_forecast.config import ForecastError
from kasm.acceptance_forecast.inputs import decorate
from kasm.config import DataSourceManifest, SourceRecord
from kasm.modeling.backtest import assign_volume_quartiles, build_rolling_origin_folds
from kasm.modeling.challenger import fit_ridge_pipeline
from kasm.modeling.features import MODEL_FEATURE_COLUMNS, extract_feature_matrix
from kasm.patient_journey.receipt_panel import publication_available

if TYPE_CHECKING:
    from kasm.acceptance_forecast.config import ComparisonConfig

_MODELS = ("persistence", "historical_mean", "ridge", "ridge_recent3", "adjusted_persistence")
_NOMINAL_COVERAGE = 0.8
_MINIMUM_CALIBRATION_N = 30


def _number(row: Mapping[str, object], field: str) -> float:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
        raise ForecastError(f"Panel {field} must be a finite number.")
    return float(value)


def _year(row: Mapping[str, object], field: str) -> int:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ForecastError(f"Panel {field} must be an integer year.")
    return value


def _source(sources: dict[int, SourceRecord], year: int) -> SourceRecord:
    if year not in sources:
        raise ForecastError(f"The manifest has no source for cohort {year}.")
    return sources[year]


def _require_public(source: SourceRecord, origin: SourceRecord, context: str) -> None:
    if source.cohort_year >= int(origin.published_value[:4]):
        raise ForecastError(f"{context} cohort was not complete at the prediction origin.")
    if not publication_available(source, origin):
        raise ForecastError(
            f"{context} was not public at prediction origin {origin.published_value}; "
            f"its source was published {source.published_value}."
        )


def _validate_row_timing(row: Mapping[str, object], sources: dict[int, SourceRecord]) -> None:
    feature_year = _year(row, "feature_cohort_year")
    target_year = _year(row, "target_cohort_year")
    origin = _source(sources, feature_year)
    if target_year != feature_year + 1 or row.get("target_cohort_end") != date(target_year, 12, 31):
        raise ForecastError("Each target must be the next complete calendar-year cohort.")
    if (row.get("prediction_as_of"), row.get("prediction_as_of_precision")) != (
        origin.published_value,
        origin.published_precision,
    ):
        raise ForecastError("Panel prediction origin disagrees with manifest publication metadata.")
    _require_public(origin, origin, "Current predictor")
    truth = sources.get(target_year)
    expected_truth = (
        (None, None) if truth is None else (truth.published_value, truth.published_precision)
    )
    if (row.get("truth_published_value"), row.get("truth_published_precision")) != expected_truth:
        raise ForecastError("Panel target publication disagrees with manifest metadata.")
    if row.get("previous_annual_log_overall_oar") is not None:
        _require_public(_source(sources, feature_year - 1), origin, "Earlier predictor report")


def _validate_row_values(row: Mapping[str, object]) -> None:
    for flag in ("analytic_eligible", "public_forecast_eligible", "first_observed_program"):
        if not isinstance(row.get(flag), bool):
            raise ForecastError(f"Panel {flag} must preserve an explicit boolean.")
    if not isinstance(row.get("program_key"), str) or not row["program_key"]:
        raise ForecastError("Panel program_key must be nonempty composite program identity.")
    _number(row, "current_log_overall_oar")
    if row["analytic_eligible"]:
        target = _number(row, "target_oar")
        target_log = _number(row, "target_log_oar")
        if target <= 0 or not isclose(log(target), target_log, rel_tol=1e-12, abs_tol=1e-12):
            raise ForecastError("Observed target must be positive and agree with its natural log.")
    elif row.get("target_oar") is not None or row.get("target_log_oar") is not None:
        raise ForecastError("An excluded missing target must stay null on both outcome scales.")


def _validate_panel(
    panel: Sequence[Mapping[str, object]], manifest: DataSourceManifest
) -> dict[int, SourceRecord]:
    sources = {source.cohort_year: source for source in manifest.sources}
    if len(sources) != len(manifest.sources):
        raise ForecastError("The source manifest duplicates a calendar-year cohort.")
    for row in panel:
        _validate_row_timing(row, sources)
        _validate_row_values(row)
    extract_feature_matrix(panel)
    return sources


def _matrix(rows: Sequence[Mapping[str, object]]) -> NDArray[np.float64]:
    values = extract_feature_matrix(rows)
    return np.asarray(
        [[np.nan if value is None else float(value) for value in row] for row in values],
        dtype=np.float64,
    )


def _fit_adjusted_persistence(
    training: Sequence[Mapping[str, object]], config: ComparisonConfig
) -> Pipeline:
    """Learn a slope and intercept from earlier current-ratio/next-ratio pairs.

    The original V1 matrix helper intentionally requires every frozen input. This
    separate one-input model therefore uses its own explicit, fixed input boundary.
    """
    features = np.asarray([[_number(row, "current_log_overall_oar")] for row in training])
    outcomes = np.asarray([_number(row, "target_log_oar") for row in training])
    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
            ("ridge", Ridge(alpha=config.alpha, solver="lsqr", random_state=config.seed)),
        ]
    )
    pipeline.fit(features, outcomes)
    return pipeline


def _fit_metadata(pipeline: Pipeline, columns: Sequence[str]) -> dict[str, Any]:
    return {
        "feature_columns": list(columns),
        "intercept": float(pipeline.named_steps["ridge"].intercept_),
        "coefficients": pipeline.named_steps["ridge"].coef_.tolist(),
        "imputer_statistics": pipeline.named_steps["imputer"].statistics_.tolist(),
        "scaler_mean": pipeline.named_steps["scaler"].mean_.tolist(),
        "scaler_scale": pipeline.named_steps["scaler"].scale_.tolist(),
    }


def _historical_mean(
    row: Mapping[str, object],
    panel: Sequence[Mapping[str, object]],
    sources: dict[int, SourceRecord],
) -> float:
    year = _year(row, "feature_cohort_year")
    origin = _source(sources, year)
    values = []
    for earlier in panel:
        if (
            earlier["program_key"] == row["program_key"]
            and _year(earlier, "feature_cohort_year") <= year
        ):
            _require_public(
                _source(sources, _year(earlier, "feature_cohort_year")),
                origin,
                "Historical-mean input",
            )
            values.append(_number(earlier, "current_log_overall_oar"))
    return sum(values) / len(values) if values else 0.0


def _predict_model(
    model: str,
    training: Sequence[Mapping[str, object]],
    evaluation: Sequence[Mapping[str, object]],
    panel: Sequence[Mapping[str, object]],
    sources: dict[int, SourceRecord],
    config: ComparisonConfig,
) -> tuple[list[float], dict[str, Any]]:
    columns: tuple[str, ...]
    if model == "persistence":
        return (
            [_number(row, "current_log_overall_oar") for row in evaluation],
            {"formula": "current_log_overall_oar", "feature_columns": ["current_log_overall_oar"]},
        )
    if model == "historical_mean":
        return (
            [_historical_mean(row, panel, sources) for row in evaluation],
            {
                "formula": "mean_earlier_available_current_log_oar",
                "feature_columns": ["current_log_overall_oar"],
            },
        )
    if model == "adjusted_persistence":
        pipeline = _fit_adjusted_persistence(training, config)
        matrix = np.asarray([[_number(row, "current_log_overall_oar")] for row in evaluation])
        columns = ("current_log_overall_oar",)
    else:
        pipeline = fit_ridge_pipeline(
            training,
            feature_columns=MODEL_FEATURE_COLUMNS,
            target_column="target_log_oar",
            alpha=config.alpha,
            random_seed=config.seed,
        )
        matrix = _matrix(evaluation)
        columns = MODEL_FEATURE_COLUMNS
    predicted = [float(value) for value in pipeline.predict(matrix)]
    return predicted, _fit_metadata(pipeline, columns)


def _calibration(
    previous: Sequence[Mapping[str, Any]],
    model: str,
    year: int,
    sources: dict[int, SourceRecord],
) -> dict[str, Any]:
    calibration_rows = [row for row in previous if row["model"] == model]
    n = len(calibration_rows)
    if calibration_rows:
        # The preceding outcome and current inputs share this exact release,
        # including when its publication is known only to the month.
        _require_public(_source(sources, year - 1), _source(sources, year - 1), "Band outcomes")
        if any(row["target_cohort_year"] != year - 1 for row in calibration_rows):
            raise ForecastError(
                "Band calibration requires the preceding year's out-of-sample predictions."
            )
    residuals = sorted(
        abs(row["predicted_log_oar"] - row["target_log_oar"]) for row in calibration_rows
    )
    rank = min(n, ceil((n + 1) * _NOMINAL_COVERAGE)) if n else None
    radius = residuals[rank - 1] if n >= _MINIMUM_CALIBRATION_N and rank is not None else None
    return {
        "calibration_target_year": year - 1 if n else None,
        "calibration_n": n,
        "calibration_order_statistic_rank": rank,
        "band_radius_log_oar": radius,
    }


def _prediction_record(
    row: Mapping[str, object], model: str, prediction: float, calibration: dict[str, Any]
) -> dict[str, Any]:
    if not isfinite(prediction):
        raise ForecastError(
            "A required candidate prediction is not finite; no rows may be dropped."
        )
    radius = calibration["band_radius_log_oar"]
    try:
        predicted_ratio = exp(prediction)
        lower = exp(prediction - radius) if radius is not None else None
        upper = exp(prediction + radius) if radius is not None else None
    except OverflowError as exc:
        raise ForecastError("Candidate prediction or band exceeds finite ratio values.") from exc
    if predicted_ratio <= 0 or lower == 0 or upper == 0:
        raise ForecastError("Candidate prediction and band ratios must be strictly positive.")
    return {
        **row,
        "model": model,
        "predicted_log_oar": prediction,
        "predicted_oar": predicted_ratio,
        "evidence_role": "retrospective_refit",
        **calibration,
        "band_lower_oar": lower,
        "band_upper_oar": upper,
        "band_covered": abs(prediction - _number(row, "target_log_oar")) <= radius
        if radius is not None
        else None,
    }


def _training_rows(
    panel: Sequence[Mapping[str, object]],
    indices: Sequence[int],
    model: str,
    year: int,
    sources: dict[int, SourceRecord],
    config: ComparisonConfig,
) -> list[Mapping[str, object]]:
    first = (
        max(config.training_start, year - config.recent_window)
        if model == "ridge_recent3"
        else config.training_start
    )
    training = [
        panel[index] for index in indices if _year(panel[index], "target_cohort_year") >= first
    ]
    expected_years = list(range(first, year))
    if sorted({_year(row, "target_cohort_year") for row in training}) != expected_years:
        raise ForecastError("A configured training cohort has no observed outcomes.")
    origin = _source(sources, year - 1)
    for row in training:
        _require_public(
            _source(sources, _year(row, "feature_cohort_year")), origin, "Training predictors"
        )
        _require_public(
            _source(sources, _year(row, "target_cohort_year")), origin, "Training outcome"
        )
    return training


def generate_predictions(
    panel: list[dict[str, object]], manifest: DataSourceManifest, config: ComparisonConfig
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return every configured method on the same observed program/year rows.

    Warmup predictions only supply the first band's earlier residuals. Returned
    evaluation records retain artifact eligibility and publication precision. Fit
    records contain reproducible numeric parameters, never serialized models.
    """
    years = (config.warmup_year, *config.years)
    if config.models != _MODELS or years != tuple(range(years[0], years[-1] + 1)):
        raise ForecastError("Comparison requires all five fixed methods and consecutive origins.")
    sources = _validate_panel(panel, manifest)
    quartiles = assign_volume_quartiles(panel)
    folds = build_rolling_origin_folds(
        panel, evaluation_target_years=years, training_target_year_start=config.training_start
    )
    records: list[dict[str, Any]] = []
    fits: list[dict[str, Any]] = []
    previous: list[dict[str, Any]] = []
    for fold in folds:
        year = fold.evaluation_target_year
        evaluation = sorted(
            [
                decorate(
                    {
                        **panel[index],
                        "expected_acceptance_quartile": quartiles[
                            (str(panel[index]["program_key"]), year)
                        ],
                    }
                )
                for index in fold.evaluation_row_indices
            ],
            key=lambda row: str(row["program_key"]),
        )
        current: list[dict[str, Any]] = []
        for model in config.models:
            training = _training_rows(
                panel, fold.training_row_indices, model, year, sources, config
            )
            values, parameters = _predict_model(model, training, evaluation, panel, sources, config)
            if len(values) != len(evaluation):
                raise ForecastError("Every required row must receive a candidate prediction.")
            calibration = _calibration(previous, model, year, sources)
            current.extend(
                _prediction_record(row, model, value, calibration)
                for row, value in zip(evaluation, values, strict=True)
            )
            fitted = model not in {"persistence", "historical_mean"}
            fits.append(
                {
                    "model": model,
                    "target_cohort_year": year,
                    "training_target_years": sorted(
                        {_year(row, "target_cohort_year") for row in training}
                    )
                    if fitted
                    else [],
                    "training_n": len(training) if fitted else 0,
                    "alpha": config.alpha if fitted else None,
                    "seed": config.seed if fitted else None,
                    "evidence_role": "retrospective_refit",
                    **parameters,
                    **calibration,
                }
            )
        if year in config.years:
            records.extend(current)
        previous = current
    return records, fits
