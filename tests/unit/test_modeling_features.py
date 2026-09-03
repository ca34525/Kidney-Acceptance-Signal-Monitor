from __future__ import annotations

import pytest

from kasm.modeling.features import (
    MODEL_FEATURE_COLUMNS,
    FeatureContractError,
    extract_feature_matrix,
    validate_feature_columns,
)


def _feature_row() -> dict[str, object]:
    return {
        "current_log_overall_oar": -0.1,
        "previous_annual_log_overall_oar": None,
        "one_year_change_log_overall_oar": None,
        "log1p_overall_expected_acceptances": 4.2,
        "log_credible_interval_width": 0.3,
        "current_log_low_oar": -0.2,
        "current_log_medium_oar": -0.1,
        "current_log_high_oar": None,
        "current_log_hard_to_place_oar": 0.1,
        "high_offers_share": 0.4,
        "hard_to_place_offers_share": 0.1,
        "missing_previous_annual_log_overall_oar": True,
        "missing_one_year_change_log_overall_oar": True,
        "missing_current_log_low_oar": False,
        "missing_current_log_medium_oar": False,
        "missing_current_log_high_oar": True,
        "missing_current_log_hard_to_place_oar": False,
    }


def test_model_feature_contract_is_exact_and_extracts_in_declared_order() -> None:
    validate_feature_columns(MODEL_FEATURE_COLUMNS)

    matrix = extract_feature_matrix((_feature_row(),))

    assert matrix[0][0] == -0.1
    assert matrix[0][1] is None
    assert matrix[0][-1] is False


@pytest.mark.parametrize(
    "unsafe_column",
    [
        "program_key",
        "center_code",
        "center_name",
        "city",
        "state",
        "zip",
        "feature_cohort_year",
        "target_log_oar",
        "future_report_available",
        "opo_identity",
    ],
)
def test_identity_location_cohort_and_future_fields_are_rejected(unsafe_column: str) -> None:
    columns = (*MODEL_FEATURE_COLUMNS, unsafe_column)

    with pytest.raises(FeatureContractError, match=unsafe_column):
        validate_feature_columns(columns)


def test_missing_prespecified_feature_is_rejected() -> None:
    with pytest.raises(FeatureContractError, match="missing_current_log_high_oar"):
        validate_feature_columns(
            tuple(
                column
                for column in MODEL_FEATURE_COLUMNS
                if column != "missing_current_log_high_oar"
            )
        )
