"""Typed loading for the pre-replay experiment configuration."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite
from pathlib import Path
from typing import cast

import yaml

from kasm.modeling.features import validate_feature_columns


class ExperimentConfigError(ValueError):
    """Raised when an experiment configuration weakens a scientific contract."""


@dataclass(frozen=True)
class ExperimentConfig:
    """Configuration fields needed by the pre-replay temporal harness."""

    feature_columns: tuple[str, ...]
    target_column: str
    training_target_year_start: int
    selection_target_years: tuple[int, ...]
    validation_target_year: int
    replay_target_year: int
    baselines: tuple[str, ...]
    ridge_alpha_grid: tuple[float, ...]
    ridge_alpha_tie_relative_tolerance: float
    ridge_random_seed: int
    minimum_lowest_quartile_rows: int
    pre_replay_minimum_skill_over_persistence: float
    pre_replay_minimum_improved_years: int
    pre_replay_maximum_single_year_relative_worsening: float
    pre_replay_maximum_lowest_quartile_relative_worsening: float
    forecast_activation_attempted: bool | None
    selected_ridge_alpha: float | None
    replay_model_training_target_year_end: int
    band_nominal_coverage: float
    band_calibration_target_year: int
    band_coverage_interval_method: str
    band_calibration_sample_size: int | None
    band_order_statistic_rank: int | None
    ridge_absolute_log_residual_radius: float | None
    persistence_absolute_log_residual_radius: float | None
    bootstrap_resamples: int
    bootstrap_seed: int
    bootstrap_percentiles: tuple[float, ...]
    bootstrap_percentile_method: str
    point_minimum_skill_over_persistence: float
    point_bootstrap_interval_must_be_below_zero: bool
    point_maximum_absolute_mean_signed_log_error: float
    point_bias_must_not_exceed_persistence: bool
    point_maximum_lowest_quartile_relative_worsening: float
    band_exact_interval_must_include_nominal_coverage: bool
    band_maximum_mean_width_relative_to_persistence: float

    @property
    def pre_replay_evaluation_target_years(self) -> tuple[int, ...]:
        """Return model-selection years followed by the held-out validation year."""
        return (*self.selection_target_years, self.validation_target_year)


def _mapping(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ExperimentConfigError(f"{context} must be a mapping with string keys.")
    return cast(dict[str, object], value)


def _string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ExperimentConfigError(f"{context} must be a non-empty string.")
    return value


def _integer(value: object, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExperimentConfigError(f"{context} must be an integer.")
    return value


def _boolean(value: object, context: str) -> bool:
    if not isinstance(value, bool):
        raise ExperimentConfigError(f"{context} must be boolean.")
    return value


def _optional_boolean(value: object, context: str) -> bool | None:
    if value is None:
        return None
    return _boolean(value, context)


def _string_tuple(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ExperimentConfigError(f"{context} must be a list of strings.")
    return tuple(value)


def _integer_tuple(value: object, context: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        raise ExperimentConfigError(f"{context} must be a list of integers.")
    return tuple(value)


def _number(value: object, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ExperimentConfigError(f"{context} must be numeric.")
    return float(value)


def _number_tuple(value: object, context: str) -> tuple[float, ...]:
    if not isinstance(value, list):
        raise ExperimentConfigError(f"{context} must be a list of numbers.")
    return tuple(_number(item, context) for item in value)


def load_experiment_config(path: Path) -> ExperimentConfig:
    """Load the fixed baseline design and reject changes to its core scientific meaning."""
    raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    values = _mapping(raw, "Experiment config")
    if _integer(values.get("schema_version"), "schema_version") != 1:
        raise ExperimentConfigError("schema_version must be 1.")

    target = _mapping(values.get("target"), "target")
    target_column = _string(target.get("column"), "target.column")
    if target_column != "target_log_oar":
        raise ExperimentConfigError("target.column must be 'target_log_oar'.")

    features = _mapping(values.get("features"), "features")
    feature_columns = _string_tuple(features.get("columns"), "features.columns")
    try:
        validate_feature_columns(feature_columns)
    except ValueError as error:
        raise ExperimentConfigError(str(error)) from error

    temporal = _mapping(values.get("temporal_evaluation"), "temporal_evaluation")
    split_method = _string(temporal.get("split_method"), "temporal_evaluation.split_method")
    if split_method != "rolling_origin_by_target_year":
        raise ExperimentConfigError(
            "temporal_evaluation.split_method must be 'rolling_origin_by_target_year'."
        )
    training_start = _integer(
        temporal.get("training_target_year_start"),
        "temporal_evaluation.training_target_year_start",
    )
    selection_years = _integer_tuple(
        temporal.get("selection_target_years"), "temporal_evaluation.selection_target_years"
    )
    validation_year = _integer(
        temporal.get("validation_target_year"), "temporal_evaluation.validation_target_year"
    )
    replay_year = _integer(
        temporal.get("frozen_replay_target_year"),
        "temporal_evaluation.frozen_replay_target_year",
    )
    if (training_start, selection_years, validation_year, replay_year) != (
        2018,
        (2021, 2022, 2023),
        2024,
        2025,
    ):
        raise ExperimentConfigError(
            "Temporal years must match the prespecified 2018 training start, 2021-2023 "
            "selection years, 2024 validation year, and 2025 frozen replay year."
        )

    baselines = _string_tuple(values.get("baselines"), "baselines")
    if baselines != ("neutral", "persistence", "historical_mean"):
        raise ExperimentConfigError(
            "baselines must be neutral, persistence, and historical_mean in that order."
        )

    ridge = _mapping(values.get("ridge"), "ridge")
    alpha_grid = _number_tuple(ridge.get("alpha_grid"), "ridge.alpha_grid")
    alpha_tolerance = _number(
        ridge.get("alpha_tie_relative_tolerance"),
        "ridge.alpha_tie_relative_tolerance",
    )
    random_seed = _integer(ridge.get("random_seed"), "ridge.random_seed")
    if alpha_grid != (0.01, 0.1, 1.0, 10.0, 100.0):
        raise ExperimentConfigError("ridge.alpha_grid must match the prespecified fixed grid.")
    if alpha_tolerance != 0.01:
        raise ExperimentConfigError(
            "ridge.alpha_tie_relative_tolerance must match the prespecified 0.01 rule."
        )
    if random_seed != 20260903:
        raise ExperimentConfigError("ridge.random_seed must be 20260903.")
    selected_alpha_raw = ridge.get("selected_alpha")
    selected_alpha = (
        None if selected_alpha_raw is None else _number(selected_alpha_raw, "ridge.selected_alpha")
    )
    if selected_alpha is not None and selected_alpha not in alpha_grid:
        raise ExperimentConfigError("ridge.selected_alpha must be from ridge.alpha_grid.")

    replay_training_end = _integer(
        temporal.get("replay_model_training_target_year_end"),
        "temporal_evaluation.replay_model_training_target_year_end",
    )
    if replay_training_end != 2023:
        raise ExperimentConfigError(
            "temporal_evaluation.replay_model_training_target_year_end must be 2023."
        )

    volume = _mapping(values.get("volume_quartiles"), "volume_quartiles")
    minimum_lowest_quartile_rows = _integer(
        volume.get("minimum_lowest_quartile_rows"),
        "volume_quartiles.minimum_lowest_quartile_rows",
    )
    promotion = _mapping(values.get("promotion"), "promotion")
    pre_replay = _mapping(promotion.get("pre_replay"), "promotion.pre_replay")
    minimum_skill = _number(
        pre_replay.get("minimum_skill_over_persistence"),
        "promotion.pre_replay.minimum_skill_over_persistence",
    )
    minimum_improved_years = _integer(
        pre_replay.get("minimum_improved_years"),
        "promotion.pre_replay.minimum_improved_years",
    )
    maximum_single_year_worsening = _number(
        pre_replay.get("maximum_single_year_relative_worsening"),
        "promotion.pre_replay.maximum_single_year_relative_worsening",
    )
    maximum_lowest_quartile_worsening = _number(
        pre_replay.get("maximum_lowest_quartile_relative_worsening"),
        "promotion.pre_replay.maximum_lowest_quartile_relative_worsening",
    )
    if (
        minimum_lowest_quartile_rows,
        minimum_skill,
        minimum_improved_years,
        maximum_single_year_worsening,
        maximum_lowest_quartile_worsening,
    ) != (30, 0.05, 3, 0.10, 0.10):
        raise ExperimentConfigError("Pre-replay promotion rules must match the specification.")

    empirical_band = _mapping(values.get("empirical_band"), "empirical_band")
    band_nominal_coverage = _number(
        empirical_band.get("nominal_coverage"), "empirical_band.nominal_coverage"
    )
    band_calibration_year = _integer(
        empirical_band.get("calibration_target_year"),
        "empirical_band.calibration_target_year",
    )
    order_statistic = _string(
        empirical_band.get("order_statistic"), "empirical_band.order_statistic"
    )
    coverage_interval = _string(
        empirical_band.get("coverage_interval"), "empirical_band.coverage_interval"
    )
    if (
        band_nominal_coverage,
        band_calibration_year,
        order_statistic,
        coverage_interval,
    ) != (
        0.8,
        2024,
        "min(n, ceil((n + 1) * 0.80))",
        "two_sided_95_percent_clopper_pearson",
    ):
        raise ExperimentConfigError("Empirical-band rules must match the specification.")
    calibration_evidence_raw = empirical_band.get("calibration_evidence")
    calibration_sample_size: int | None = None
    calibration_rank: int | None = None
    ridge_radius: float | None = None
    persistence_radius: float | None = None
    if calibration_evidence_raw is not None:
        calibration_evidence = _mapping(
            calibration_evidence_raw, "empirical_band.calibration_evidence"
        )
        calibration_sample_size = _integer(
            calibration_evidence.get("sample_size"),
            "empirical_band.calibration_evidence.sample_size",
        )
        calibration_rank = _integer(
            calibration_evidence.get("order_statistic_rank"),
            "empirical_band.calibration_evidence.order_statistic_rank",
        )
        ridge_radius = _number(
            calibration_evidence.get("ridge_absolute_log_residual_radius"),
            "empirical_band.calibration_evidence.ridge_absolute_log_residual_radius",
        )
        persistence_radius = _number(
            calibration_evidence.get("persistence_absolute_log_residual_radius"),
            "empirical_band.calibration_evidence.persistence_absolute_log_residual_radius",
        )
        expected_rank = min(
            calibration_sample_size,
            ceil((calibration_sample_size + 1) * band_nominal_coverage),
        )
        if (
            calibration_sample_size <= 0
            or calibration_rank != expected_rank
            or not isfinite(ridge_radius)
            or ridge_radius < 0
            or not isfinite(persistence_radius)
            or persistence_radius < 0
        ):
            raise ExperimentConfigError(
                "Empirical-band calibration evidence violates the frozen order-statistic rule."
            )

    bootstrap = _mapping(values.get("bootstrap"), "bootstrap")
    bootstrap_resamples = _integer(bootstrap.get("resamples"), "bootstrap.resamples")
    bootstrap_seed = _integer(bootstrap.get("seed"), "bootstrap.seed")
    bootstrap_percentiles = _number_tuple(bootstrap.get("percentiles"), "bootstrap.percentiles")
    bootstrap_resampling_unit = _string(
        bootstrap.get("resampling_unit"), "bootstrap.resampling_unit"
    )
    percentile_method_raw = bootstrap.get("percentile_method")
    percentile_method = (
        "linear"
        if percentile_method_raw is None
        else _string(percentile_method_raw, "bootstrap.percentile_method")
    )
    if (
        bootstrap_resamples,
        bootstrap_seed,
        bootstrap_percentiles,
        bootstrap_resampling_unit,
        percentile_method,
    ) != (10_000, 20260903, (2.5, 97.5), "program_key", "linear"):
        raise ExperimentConfigError("Bootstrap rules must match the specification.")

    point_replay = _mapping(promotion.get("point_replay"), "promotion.point_replay")
    point_minimum_skill = _number(
        point_replay.get("minimum_skill_over_persistence"),
        "promotion.point_replay.minimum_skill_over_persistence",
    )
    point_bootstrap_below_zero = _boolean(
        point_replay.get("bootstrap_interval_must_be_below_zero"),
        "promotion.point_replay.bootstrap_interval_must_be_below_zero",
    )
    point_maximum_bias = _number(
        point_replay.get("maximum_absolute_mean_signed_log_error"),
        "promotion.point_replay.maximum_absolute_mean_signed_log_error",
    )
    point_bias_vs_persistence = _boolean(
        point_replay.get("bias_must_not_exceed_persistence"),
        "promotion.point_replay.bias_must_not_exceed_persistence",
    )
    point_lowest_quartile_worsening = _number(
        point_replay.get("maximum_lowest_quartile_relative_worsening"),
        "promotion.point_replay.maximum_lowest_quartile_relative_worsening",
    )
    if (
        point_minimum_skill,
        point_bootstrap_below_zero,
        point_maximum_bias,
        point_bias_vs_persistence,
        point_lowest_quartile_worsening,
    ) != (0.05, True, 0.05, True, 0.10):
        raise ExperimentConfigError("Replay point-promotion rules must match the specification.")

    band_replay = _mapping(promotion.get("band_replay"), "promotion.band_replay")
    band_interval_includes_nominal = _boolean(
        band_replay.get("exact_interval_must_include_nominal_coverage"),
        "promotion.band_replay.exact_interval_must_include_nominal_coverage",
    )
    band_maximum_relative_width = _number(
        band_replay.get("maximum_mean_width_relative_to_persistence"),
        "promotion.band_replay.maximum_mean_width_relative_to_persistence",
    )
    if (band_interval_includes_nominal, band_maximum_relative_width) != (True, 1.0):
        raise ExperimentConfigError("Replay band-promotion rules must match the specification.")

    activation_attempted = _optional_boolean(
        values.get("forecast_activation_attempted"), "forecast_activation_attempted"
    )

    return ExperimentConfig(
        feature_columns=feature_columns,
        target_column=target_column,
        training_target_year_start=training_start,
        selection_target_years=selection_years,
        validation_target_year=validation_year,
        replay_target_year=replay_year,
        baselines=baselines,
        ridge_alpha_grid=alpha_grid,
        ridge_alpha_tie_relative_tolerance=alpha_tolerance,
        ridge_random_seed=random_seed,
        minimum_lowest_quartile_rows=minimum_lowest_quartile_rows,
        pre_replay_minimum_skill_over_persistence=minimum_skill,
        pre_replay_minimum_improved_years=minimum_improved_years,
        pre_replay_maximum_single_year_relative_worsening=maximum_single_year_worsening,
        pre_replay_maximum_lowest_quartile_relative_worsening=(maximum_lowest_quartile_worsening),
        forecast_activation_attempted=activation_attempted,
        selected_ridge_alpha=selected_alpha,
        replay_model_training_target_year_end=replay_training_end,
        band_nominal_coverage=band_nominal_coverage,
        band_calibration_target_year=band_calibration_year,
        band_coverage_interval_method="clopper_pearson",
        band_calibration_sample_size=calibration_sample_size,
        band_order_statistic_rank=calibration_rank,
        ridge_absolute_log_residual_radius=ridge_radius,
        persistence_absolute_log_residual_radius=persistence_radius,
        bootstrap_resamples=bootstrap_resamples,
        bootstrap_seed=bootstrap_seed,
        bootstrap_percentiles=bootstrap_percentiles,
        bootstrap_percentile_method=percentile_method,
        point_minimum_skill_over_persistence=point_minimum_skill,
        point_bootstrap_interval_must_be_below_zero=point_bootstrap_below_zero,
        point_maximum_absolute_mean_signed_log_error=point_maximum_bias,
        point_bias_must_not_exceed_persistence=point_bias_vs_persistence,
        point_maximum_lowest_quartile_relative_worsening=point_lowest_quartile_worsening,
        band_exact_interval_must_include_nominal_coverage=band_interval_includes_nominal,
        band_maximum_mean_width_relative_to_persistence=band_maximum_relative_width,
    )


def load_frozen_experiment_config(path: Path) -> ExperimentConfig:
    """Load a replay-ready config and reject an ambiguous pre-replay freeze."""
    config = load_experiment_config(path)
    raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    values = _mapping(raw, "Frozen experiment config")
    bootstrap = _mapping(values.get("bootstrap"), "bootstrap")
    freeze = _mapping(values.get("pre_replay_freeze"), "pre_replay_freeze")
    if config.forecast_activation_attempted is None:
        raise ExperimentConfigError("Frozen config must record forecast_activation_attempted.")
    if config.forecast_activation_attempted and config.selected_ridge_alpha is None:
        raise ExperimentConfigError("Activation requires a frozen ridge.selected_alpha.")
    calibration_values = (
        config.band_calibration_sample_size,
        config.band_order_statistic_rank,
        config.ridge_absolute_log_residual_radius,
        config.persistence_absolute_log_residual_radius,
    )
    if config.forecast_activation_attempted and any(value is None for value in calibration_values):
        raise ExperimentConfigError("Activation requires frozen 2024 band calibration evidence.")
    if "percentile_method" not in bootstrap:
        raise ExperimentConfigError("Frozen config must serialize bootstrap.percentile_method.")
    if _boolean(freeze.get("frozen_replay_evaluated"), "pre_replay_freeze.frozen_replay_evaluated"):
        raise ExperimentConfigError("A pre-replay frozen config cannot contain replay results.")
    if (
        _integer_tuple(
            freeze.get("evaluated_target_years"), "pre_replay_freeze.evaluated_target_years"
        )
        != config.pre_replay_evaluation_target_years
    ):
        raise ExperimentConfigError(
            "pre_replay_freeze.evaluated_target_years must contain only 2021-2024."
        )
    if config.forecast_activation_attempted and not _boolean(
        freeze.get("candidate_gate_passed"), "pre_replay_freeze.candidate_gate_passed"
    ):
        raise ExperimentConfigError("Activation requires a passing pre-replay candidate gate.")
    return config
