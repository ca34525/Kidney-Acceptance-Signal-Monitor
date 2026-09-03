"""Typed loading for the pre-replay experiment configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from kasm.modeling.features import validate_feature_columns


class ExperimentConfigError(ValueError):
    """Raised when an experiment configuration weakens a scientific contract."""


@dataclass(frozen=True)
class ExperimentConfig:
    """Configuration fields needed by the baseline temporal harness."""

    feature_columns: tuple[str, ...]
    target_column: str
    training_target_year_start: int
    selection_target_years: tuple[int, ...]
    validation_target_year: int
    replay_target_year: int
    baselines: tuple[str, ...]

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

    return ExperimentConfig(
        feature_columns=feature_columns,
        target_column=target_column,
        training_target_year_start=training_start,
        selection_target_years=selection_years,
        validation_target_year=validation_year,
        replay_target_year=replay_year,
        baselines=baselines,
    )
