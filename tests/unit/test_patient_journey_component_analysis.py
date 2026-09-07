from dataclasses import replace
from datetime import date

import pytest
from test_patient_journey_components import _fixture

from kasm.patient_journey.component_analysis import analyze_components, describe_association
from kasm.patient_journey.component_config import ERROR_MODELS, ComponentConfig, ComponentError
from kasm.patient_journey.components import parse_component_workbook


def _inputs():
    source = parse_component_workbook(*_fixture(), ComponentConfig())[0]
    records, panel, predictions = [], [], []
    for index, key in enumerate(("AAAA:TX1", "BBBB:TX1", "CCCC:TX1")):
        components = (
            *source.components[:2],
            replace(source.components[2], percent=10.0 + index),
            source.components[3],
        )
        records.append(
            replace(source, program_key=key, components=components, combined_unknown=15.0 + index)
        )
        row = dict(
            program_key=key,
            feature_release_code="2205",
            target_release_code="2505",
            target_listing_cohort_start=date(2022, 7, 1),
            target_listing_cohort_end=date(2023, 6, 30),
            target_follow_up_end=date(2024, 12, 30),
            target_n=40,
            target_published_percent=37.5,
            primary_analytic_eligible=True,
            eligibility_status="eligible",
        )
        panel.append(row)
        for model in ERROR_MODELS:
            predictions.append(
                dict(
                    program_key=key,
                    feature_release_code="2205",
                    target_release_code="2505",
                    model=model,
                    target_n=40,
                    target_published_percent=37.5,
                    predicted_proportion=(38.5 + index) / 100,
                    predicted_percent=38.5 + index,
                    signed_error_percentage_points=1.0 + index,
                    absolute_error_percentage_points=1.0 + index,
                )
            )
    return records, panel, predictions


def test_exact_matching_and_correlations_keep_every_original_model():
    evidence = analyze_components(*_inputs(), ComponentConfig())
    assert evidence["audit"]["matched_eligible_count"] == 3
    assert (
        evidence["populations"]["original_evaluation"]["combined_unknown"]["median_percent"] == 16
    )
    assert set(evidence["associations"]["errors"]) == set(ERROR_MODELS)
    for result in evidence["associations"]["errors"].values():
        assert result["signed"]["pearson_r"] == pytest.approx(1)
        assert result["absolute"]["pairs"] == 3
    assert evidence["associations"]["published_outcome"]["reason"] == "constant_variable"


def test_missing_components_and_unmatched_exclusions_are_visible():
    records, panel, predictions = _inputs()
    record = records[0]
    records[0] = replace(
        record,
        components=(*record.components[:3], replace(record.components[3], percent=None)),
        combined_unknown=None,
    )
    records.append(replace(records[1], program_key="DDDD:TX1"))
    panel.append(
        panel[0]
        | dict(
            program_key="EEEE:TX1",
            primary_analytic_eligible=False,
            eligibility_status="missing_target",
            target_n=None,
            target_published_percent=None,
        )
    )
    evidence = analyze_components(records, panel, predictions, ComponentConfig())
    audit = evidence["audit"]
    assert audit["source_only_keys"] == ["DDDD:TX1"]
    assert audit["panel_only_keys"] == ["EEEE:TX1"]
    assert audit["missing_unknown_eligible_keys"] == ["AAAA:TX1"]
    assert audit["excluded_panel_rows"][0]["eligibility_status"] == "missing_target"
    assert evidence["associations"]["errors"]["history"]["signed"]["pairs"] == 2
    assert evidence["associations"]["errors"]["history"]["signed"]["pearson_r"] is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_n", 41),
        ("target_published_percent", 37.6),
        ("target_listing_cohort_start", date(2023, 1, 1)),
        ("primary_analytic_eligible", "true"),
    ],
)
def test_mismatched_panel_inputs_fail(field, value):
    records, panel, predictions = _inputs()
    panel[0][field] = value
    with pytest.raises(ComponentError):
        analyze_components(records, panel, predictions, ComponentConfig())


def test_duplicates_and_missing_eligible_source_fail():
    records, panel, predictions = _inputs()
    for inputs in [
        (records + [records[0]], panel, predictions),
        (records, panel + [panel[0]], predictions),
        (records[1:], panel, predictions),
        (records, panel, predictions + [predictions[0]]),
        (records, panel, predictions[1:]),
    ]:
        with pytest.raises(ComponentError):
            analyze_components(*inputs, ComponentConfig())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_n", 41),
        ("target_published_percent", 37.6),
        ("predicted_percent", float("nan")),
        ("predicted_proportion", 1.5),
        ("signed_error_percentage_points", 99),
        ("absolute_error_percentage_points", -1),
        ("model", "new_model"),
    ],
)
def test_prediction_tampering_fails(field, value):
    records, panel, predictions = _inputs()
    predictions[0][field] = value
    with pytest.raises(ComponentError):
        analyze_components(records, panel, predictions, ComponentConfig())


def test_association_never_fills_missing_or_constant_pairs():
    assert describe_association([(1, 2), (2, 4), (3, 6), (None, 8)]) == {
        "pearson_r": pytest.approx(1),
        "pairs": 3,
        "missing_pairs": 1,
        "reason": None,
    }
    assert describe_association([(1, 2), (2, 3)])["reason"] == "fewer_than_three_pairs"
    assert describe_association([(1, 2), (1, 3), (1, 4)])["reason"] == "constant_variable"


def test_analysis_is_order_independent():
    records, panel, predictions = _inputs()
    assert analyze_components(records, panel, predictions, ComponentConfig()) == analyze_components(
        records[::-1], panel[::-1], predictions[::-1], ComponentConfig()
    )
