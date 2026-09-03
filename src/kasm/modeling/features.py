"""Prespecified model feature contract and matrix extraction."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite

MODEL_FEATURE_COLUMNS = (
    "current_log_overall_oar",
    "previous_annual_log_overall_oar",
    "one_year_change_log_overall_oar",
    "log1p_overall_expected_acceptances",
    "log_credible_interval_width",
    "current_log_low_oar",
    "current_log_medium_oar",
    "current_log_high_oar",
    "current_log_hard_to_place_oar",
    "high_offers_share",
    "hard_to_place_offers_share",
    "missing_previous_annual_log_overall_oar",
    "missing_one_year_change_log_overall_oar",
    "missing_current_log_low_oar",
    "missing_current_log_medium_oar",
    "missing_current_log_high_oar",
    "missing_current_log_hard_to_place_oar",
)

FeatureValue = float | bool | None
FeatureMatrix = tuple[tuple[FeatureValue, ...], ...]


class FeatureContractError(ValueError):
    """Raised when a model matrix could include an unapproved predictor."""


def validate_feature_columns(columns: Sequence[str]) -> None:
    """Require the exact ordered predictor allowlist frozen in the specification."""
    supplied = tuple(columns)
    duplicates = tuple(
        column for index, column in enumerate(supplied) if column in supplied[:index]
    )
    if duplicates:
        raise FeatureContractError(
            f"Model feature columns contain duplicates: {', '.join(sorted(set(duplicates)))}."
        )

    unapproved = tuple(column for column in supplied if column not in MODEL_FEATURE_COLUMNS)
    if unapproved:
        raise FeatureContractError(
            "Model feature contract rejects unapproved columns: "
            f"{', '.join(sorted(unapproved))}. Identity, location, cohort, and future-period "
            "fields are not predictors."
        )

    missing = tuple(column for column in MODEL_FEATURE_COLUMNS if column not in supplied)
    if missing:
        raise FeatureContractError(
            f"Model feature contract is missing prespecified columns: {', '.join(missing)}."
        )
    if supplied != MODEL_FEATURE_COLUMNS:
        raise FeatureContractError("Model feature columns must use the prespecified order.")


def _feature_value(value: object, *, column: str, row_index: int) -> FeatureValue:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        result = float(value)
        if isfinite(result):
            return result
    raise FeatureContractError(
        f"Feature {column!r} in row {row_index} must be finite numeric, boolean, or null."
    )


def extract_feature_matrix(
    rows: Sequence[Mapping[str, object]],
    columns: Sequence[str] = MODEL_FEATURE_COLUMNS,
) -> FeatureMatrix:
    """Extract model values only after enforcing the exact feature allowlist."""
    validate_feature_columns(columns)
    matrix: list[tuple[FeatureValue, ...]] = []
    for row_index, row in enumerate(rows):
        missing = [column for column in columns if column not in row]
        if missing:
            raise FeatureContractError(
                f"Feature row {row_index} is missing columns: {', '.join(missing)}."
            )
        matrix.append(
            tuple(
                _feature_value(row[column], column=column, row_index=row_index)
                for column in columns
            )
        )
    return tuple(matrix)
