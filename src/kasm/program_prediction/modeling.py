"""Fit the sprint's earlier-report rules and models without using later information.

Each fold predicts every origin-eligible program, including programs whose later report
is missing. Failed fits and predictions retain their slots for coverage comparisons.
"""

from __future__ import annotations

import calendar
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from hashlib import sha256
from math import exp, expm1, isfinite, log, log1p
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import (  # type: ignore[import-untyped]
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
)
from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
from sklearn.linear_model import LinearRegression, Ridge  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]
from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]

from kasm.program_prediction.config import SprintConfig, validate_config
from kasm.program_prediction.panel import BROADER_FEATURES, HISTORY_FEATURES

BASELINES = ("persistence", "recent_mean", "damped_trend")
PIPELINES = ("ridge_history", "ridge_broader", "boosting_broader", "extra_trees_broader")


class ModelingError(ValueError):
    """The supplied records or a model output violate the research contract."""


def _number(value: Any, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
        raise ModelingError(f"{context} must be a finite number.")
    return float(value)


def _target_value(value: Any, target: str) -> float:
    number = _number(value, target)
    if number < 0 or (target == "overall_oar" and number == 0):
        raise ModelingError(f"{target} requires nonnegative counts or strictly positive OAR.")
    return number


def _bounds(value: Any, precision: Any) -> tuple[date, date]:
    try:
        if precision == "day":
            day = date.fromisoformat(value)
            return day, day
        if precision == "month" and isinstance(value, str) and len(value) == 7:
            year, month = (int(part) for part in value.split("-"))
            return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    except (TypeError, ValueError) as exc:
        raise ModelingError(
            "Publication metadata must preserve a valid date and precision."
        ) from exc
    raise ModelingError("Publication metadata must preserve a valid date and precision.")


def _public_by(row: Mapping[str, Any], origin: Mapping[str, Any]) -> bool:
    """Use conservative month bounds, while allowing the identical origin release."""
    if row["truth_release"] == origin["origin_release"]:
        if (row["truth_published_value"], row["truth_published_precision"]) != (
            origin["origin_value"],
            origin["origin_precision"],
        ):
            raise ModelingError("The same release has inconsistent publication metadata.")
        return True
    upper = _bounds(row["truth_published_value"], row["truth_published_precision"])[1]
    lower = _bounds(origin["origin_value"], origin["origin_precision"])[0]
    return upper <= lower


def _validate_row(row: Mapping[str, Any], config: SprintConfig) -> None:
    required = (
        "program_key",
        "target",
        "target_year",
        "feature_year",
        "origin_release",
        "origin_value",
        "origin_precision",
        "truth_release",
        "truth_published_value",
        "truth_published_precision",
        "eligible",
        "first_observed",
        "latest",
        "observed",
    )
    if any(field not in row for field in required):
        raise ModelingError("Panel row lacks required identity, outcome, or timing metadata.")
    if row["target"] not in config.targets:
        raise ModelingError("Panel target is not in the recorded configuration.")
    if not isinstance(row["program_key"], str) or ":" not in row["program_key"]:
        raise ModelingError("A row needs the composite program identity.")
    if any(type(row[field]) is not int for field in ("target_year", "feature_year")):
        raise ModelingError("Feature and target years must be integers.")
    if row["feature_year"] != row["target_year"] - 1:
        raise ModelingError("Feature periods must precede the target calendar year.")
    for field in ("b1_feature_year", "oar_feature_year"):
        if row.get(field) is not None and row[field] >= row["target_year"]:
            raise ModelingError("Feature period metadata extends into the target year.")
    if any(type(row[field]) is not bool for field in ("eligible", "first_observed")):
        raise ModelingError("Forecast eligibility and first-observed status must be explicit.")
    _bounds(row["origin_value"], row["origin_precision"])
    if row["truth_release"] is not None:
        if _public_by(row, row):
            raise ModelingError("An outcome already public at its own origin is not a forecast.")
    elif row["observed"] is not None:
        raise ModelingError("An observed outcome requires its publication identity.")
    if row["observed"] is not None:
        _target_value(row["observed"], row["target"])
    if row["eligible"]:
        if row["first_observed"]:
            raise ModelingError("First-observed programs cannot be marked origin-eligible.")
        _target_value(row["latest"], row["target"])


def _validate_panel(
    rows: Sequence[Mapping[str, Any]], config: SprintConfig, feature_map: Mapping[str, Any]
) -> None:
    allowed = set(HISTORY_FEATURES) | set(BROADER_FEATURES)
    if not feature_map or set(feature_map) - allowed:
        raise ModelingError("An unrecognized feature could expose identity or future information.")
    if not set(HISTORY_FEATURES).issubset(feature_map):
        raise ModelingError("The required history feature block must remain complete.")
    for field, details in feature_map.items():
        expected = "history" if field in HISTORY_FEATURES else "broader"
        if details.get("block") != expected:
            raise ModelingError(f"The feature block for {field} disagrees with its definition.")
    seen: set[tuple[str, str, int]] = set()
    origins: dict[tuple[str, int], tuple[Any, ...]] = {}
    for row in rows:
        _validate_row(row, config)
        identity = (row["program_key"], row["target"], row["target_year"])
        if identity in seen:
            raise ModelingError("Panel has a duplicate program/target/year record.")
        seen.add(identity)
        cohort = (row["target"], row["target_year"])
        origin = (row["origin_release"], row["origin_value"], row["origin_precision"])
        if cohort in origins and origins[cohort] != origin:
            raise ModelingError("All rows for an outcome cohort must share one origin and fold.")
        origins[cohort] = origin
        for field in feature_map:
            if field not in row:
                raise ModelingError(
                    f"Panel lacks feature {field}; missing values must be explicit."
                )
            if row[field] is not None:
                _number(row[field], f"Feature {field}")


def baseline_score(row: Mapping[str, Any], model: str) -> float:
    """Return an earlier-value rule in count units or log OAR, preserving gaps."""
    target = row["target"]
    latest = _target_value(row["latest"], target)
    transform = log if target == "overall_oar" else float
    score = transform(latest)
    if model == "recent_mean":
        recent = row["recent_values"][:2]
        if not recent or recent[0] != latest:
            raise ModelingError("Recent values must start with the latest available target value.")
        score = sum(transform(_target_value(value, target)) for value in recent) / len(recent)
    elif model == "damped_trend" and row["previous"] is not None:
        score += 0.5 * (score - transform(_target_value(row["previous"], target)))
    elif model not in BASELINES:
        raise ModelingError(f"Unknown simple rule: {model}.")
    return score if target == "overall_oar" else max(score, 0.0)


def backtransform(prediction: float, target: str) -> tuple[float, float]:
    """Return original units and the scoring scale; failed conversions stay explicit."""
    value = _number(prediction, "Transformed prediction")
    try:
        original = exp(value) if target == "overall_oar" else max(0.0, expm1(value))
    except OverflowError as exc:
        raise ModelingError("Prediction exceeds finite original-unit values.") from exc
    if not isfinite(original) or (target == "overall_oar" and original <= 0):
        raise ModelingError("Prediction must back-transform to a finite valid outcome.")
    return original, value if target == "overall_oar" else original


def _matrix(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> NDArray[np.float64]:
    values = np.asarray(
        [
            [np.nan if row[field] is None else float(row[field]) for field in columns]
            for row in rows
        ],
        dtype=np.float64,
    )
    # Every field has an indicator, including fields whose first missing value occurs later.
    return np.concatenate([values, np.isnan(values).astype(np.float64)], axis=1)


def fit_pipeline(
    training: Sequence[Mapping[str, Any]],
    columns: Sequence[str],
    model: str,
    seed: int,
    config: SprintConfig,
) -> Pipeline:
    """Learn filling values, scales and model parameters exclusively from training rows."""
    if not training:
        raise ModelingError("No earlier eligible training outcomes were public at this origin.")
    if model.startswith("ridge_"):
        estimator = Ridge(alpha=config.ridge_alpha, solver="lsqr", random_state=seed)
    elif model == "boosting_broader":
        estimator = HistGradientBoostingRegressor(
            max_iter=config.boosting_iterations,
            learning_rate=config.boosting_learning_rate,
            max_leaf_nodes=config.boosting_max_leaf_nodes,
            min_samples_leaf=config.boosting_min_samples_leaf,
            l2_regularization=config.boosting_l2_regularization,
            early_stopping=config.boosting_early_stopping,
            random_state=seed,
        )
    elif model == "extra_trees_broader":
        estimator = ExtraTreesRegressor(
            n_estimators=config.extra_trees_estimators,
            max_depth=config.extra_trees_max_depth,
            min_samples_leaf=config.extra_trees_min_samples_leaf,
            max_features=config.extra_trees_max_features,
            random_state=seed,
            n_jobs=1,
        )
    else:
        raise ModelingError(f"Unknown fitted pipeline: {model}.")
    steps: list[tuple[str, Any]] = [
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True))
    ]
    if model.startswith("ridge_"):
        steps.append(("scaler", StandardScaler()))
    steps.append(("model", estimator))
    pipeline = Pipeline(steps)
    transform = log if training[0]["target"] == "overall_oar" else log1p
    outcomes = np.asarray([transform(row["observed"]) for row in training], dtype=np.float64)
    with threadpool_limits(limits=1):
        pipeline.fit(_matrix(training, columns), outcomes)
    return pipeline


def _parameters(pipeline: Pipeline, columns: Sequence[str]) -> dict[str, Any]:
    fitted = pipeline.named_steps["model"]
    metadata = {
        "feature_columns": list(columns),
        "indicator_features": list(columns),
        "imputer_statistics": pipeline.named_steps["imputer"].statistics_.tolist(),
        "model_settings": fitted.get_params(deep=False),
        "execution_threads": 1,
    }
    if "scaler" in pipeline.named_steps:
        scaler = pipeline.named_steps["scaler"]
        metadata.update(scaler_mean=scaler.mean_.tolist(), scaler_scale=scaler.scale_.tolist())
    if hasattr(fitted, "coef_"):
        metadata.update(coefficients=fitted.coef_.tolist(), intercept=float(fitted.intercept_))
    if hasattr(fitted, "feature_importances_"):
        metadata["feature_importances"] = fitted.feature_importances_.tolist()
    if hasattr(fitted, "n_iter_"):
        metadata["iterations_fitted"] = np.asarray(fitted.n_iter_).tolist()
    return metadata


def _fit_adjustment(
    training: Sequence[Mapping[str, Any]], evaluation: Sequence[Mapping[str, Any]]
) -> tuple[list[float], dict[str, Any]]:
    if not training:
        raise ModelingError("No earlier eligible training outcomes were public at this origin.")
    x = np.asarray([[log(row["latest"])] for row in training])
    y = np.asarray([log(row["observed"]) for row in training])
    fitted = LinearRegression().fit(x, y)
    values = fitted.predict(np.asarray([[log(row["latest"])] for row in evaluation]))
    return [float(value) for value in values], {
        "feature_columns": ["h_latest"],
        "coefficients": fitted.coef_.tolist(),
        "intercept": float(fitted.intercept_),
        "model_settings": fitted.get_params(deep=False),
    }


def _training_rows(
    panel: Sequence[Mapping[str, Any]], origin: Mapping[str, Any], exclusions: list[dict[str, Any]]
) -> list[Mapping[str, Any]]:
    training = []
    for row in panel:
        if row["target"] != origin["target"] or row["target_year"] >= origin["target_year"]:
            continue
        reason = None
        if not row["eligible"]:
            reason = row.get("exclusion_reason") or "not_origin_eligible"
        elif row["observed"] is None:
            reason = "missing_training_outcome"
        elif not _public_by(row, origin):
            reason = "training_label_not_public"
        if reason is not None:
            exclusions.append(
                {**row, "evaluated_target_year": origin["target_year"], "reason": reason}
            )
        else:
            training.append(row)
    return sorted(training, key=lambda row: (row["target_year"], row["program_key"]))


def _model_predictions(
    model: str,
    training: Sequence[Mapping[str, Any]],
    evaluation: Sequence[Mapping[str, Any]],
    columns: Sequence[str],
    seed: int,
    config: SprintConfig,
) -> tuple[list[float], dict[str, Any], bool]:
    if model in BASELINES:
        return [baseline_score(row, model) for row in evaluation], {"formula": model}, False
    if model == "adjusted_persistence":
        values, metadata = _fit_adjustment(training, evaluation)
        return values, metadata, True
    pipeline = fit_pipeline(training, columns, model, seed, config)
    with threadpool_limits(limits=1):
        values = pipeline.predict(_matrix(evaluation, columns))
    return [float(value) for value in values], _parameters(pipeline, columns), True


def _prediction_rows(
    evaluation: Sequence[Mapping[str, Any]],
    model: str,
    values: Sequence[float],
    transformed: bool,
    fold: Mapping[str, Any],
    failures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    predictions = []
    for row, value in zip(evaluation, values, strict=True):
        record = {**row, "model": model, "status": "ok", "error": None}
        try:
            if transformed or row["target"] == "overall_oar":
                original, score = backtransform(value, row["target"])
            else:
                original = score = _target_value(value, row["target"])
            record.update(prediction=original, predicted_score=score)
        except (ValueError, OverflowError, FloatingPointError) as exc:
            record.update(
                prediction=None, predicted_score=None, status="prediction_failed", error=str(exc)
            )
            failures.append(
                {
                    **fold,
                    "program_key": row["program_key"],
                    "stage": "prediction",
                    "error": str(exc),
                }
            )
        predictions.append(record)
    return predictions


def _evaluate_model(
    model: str,
    training: Sequence[Mapping[str, Any]],
    evaluation: Sequence[Mapping[str, Any]],
    columns: Sequence[str],
    config: SprintConfig,
    failures: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    origin = evaluation[0]
    digest = sha256(
        f"{config.seed}:{origin['target']}:{origin['target_year']}:{model}".encode()
    ).digest()
    seed = int.from_bytes(digest[:4], "big")
    fitted = model not in BASELINES
    year_counts = Counter(str(row["target_year"]) for row in training)
    fold: dict[str, Any] = {
        "target": origin["target"],
        "target_year": origin["target_year"],
        "model": model,
        "origin_release": origin["origin_release"],
        "origin_value": origin["origin_value"],
        "origin_precision": origin["origin_precision"],
        "training_n": len(training) if fitted else 0,
        "training_programs": len({row["program_key"] for row in training}) if fitted else 0,
        "training_target_years": sorted({row["target_year"] for row in training}) if fitted else [],
        "training_year_counts": dict(sorted(year_counts.items())) if fitted else {},
        "evaluation_n": len(evaluation),
        "observed_n": sum(row["observed"] is not None for row in evaluation),
        "seed": seed if fitted else None,
        "feature_columns": list(columns) if fitted else [],
        "entirely_missing_features": [
            field for field in columns if training and all(row[field] is None for row in training)
        ]
        if fitted
        else [],
        "status": "ok",
        "parameters": {},
    }
    try:
        values, metadata, transformed = _model_predictions(
            model, training, evaluation, columns, seed, config
        )
        if len(values) != len(evaluation):
            raise ModelingError("A model must preserve one prediction slot per eligible program.")
        fold["parameters"] = metadata
    except (ValueError, RuntimeError, OverflowError, FloatingPointError) as exc:
        fold.update(status="fit_failed", error=f"{type(exc).__name__}: {exc}")
        failures.append({**fold, "stage": "fit"})
        return [
            {
                **row,
                "model": model,
                "prediction": None,
                "predicted_score": None,
                "status": "fit_failed",
                "error": fold["error"],
            }
            for row in evaluation
        ], fold
    predictions = _prediction_rows(evaluation, model, values, transformed, fold, failures)
    if any(row["status"] != "ok" for row in predictions):
        fold["status"] = "prediction_failed"
    return predictions, fold


def evaluate(
    panel_rows: list[dict[str, Any]],
    config: SprintConfig,
    years: tuple[int, ...],
    feature_map: dict[str, Any],
    *,
    prioritized_targets: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Evaluate complete cohorts with all baselines before the four fixed pipelines.

    The returned ledgers retain unknown outcomes, excluded programs, unavailable training
    labels, all settings, training-only preparation statistics and any failed prediction.
    """
    validate_config(config)
    _validate_panel(panel_rows, config, feature_map)
    if not years or tuple(sorted(set(years))) != years:
        raise ModelingError("Evaluation years must be nonempty, unique and increasing.")
    if any(model not in PIPELINES for model in config.pipelines):
        raise ModelingError("Only the four recorded model pipelines may enter this initial runner.")
    if len(set(prioritized_targets)) != len(prioritized_targets) or any(
        target not in config.targets for target in prioritized_targets
    ):
        raise ModelingError("Prioritized targets must be distinct configured questions.")
    predictions: list[dict[str, Any]] = []
    folds: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    target_order = (
        *prioritized_targets,
        *(target for target in config.targets if target not in prioritized_targets),
    )
    for target in target_order:
        models = (
            *BASELINES,
            *(("adjusted_persistence",) if target == "overall_oar" else ()),
            *config.pipelines,
        )
        for year in years:
            universe = [
                row for row in panel_rows if row["target"] == target and row["target_year"] == year
            ]
            exclusions.extend(
                {**row, "reason": row.get("exclusion_reason") or "not_origin_eligible"}
                for row in universe
                if not row["eligible"]
            )
            evaluation = sorted(
                [row for row in universe if row["eligible"]], key=lambda row: row["program_key"]
            )
            if not evaluation:
                for model in models:
                    failure = {
                        "target": target,
                        "target_year": year,
                        "model": model,
                        "stage": "fold",
                        "error": "No origin-eligible programs.",
                        "status": "fold_unavailable",
                        "training_n": 0,
                        "evaluation_n": 0,
                    }
                    failures.append(failure)
                    folds.append(failure.copy())
                continue
            training = _training_rows(panel_rows, evaluation[0], exclusions)
            for model in models:
                columns = (
                    tuple(HISTORY_FEATURES) if model == "ridge_history" else tuple(feature_map)
                )
                if model == "adjusted_persistence":
                    columns = ("h_latest",)
                if config.omit_oar_features:
                    columns = tuple(field for field in columns if not field.startswith("oar_"))
                rows, fold = _evaluate_model(model, training, evaluation, columns, config, failures)
                predictions.extend(rows)
                folds.append(fold)
    return {
        "predictions": predictions,
        "folds": folds,
        "failures": failures,
        "exclusions": exclusions,
    }
