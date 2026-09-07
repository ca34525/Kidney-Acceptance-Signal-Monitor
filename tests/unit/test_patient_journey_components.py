from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
import yaml

from kasm.patient_journey.component_config import (
    COMPONENT_FIELDS,
    ComponentConfig,
    load_component_config,
    validate_component_config,
)
from kasm.patient_journey.components import (
    ComponentError,
    ComponentValue,
    parse_component_workbook,
    reconcile_functioning,
    sum_components,
)

ROOT = Path(__file__).parents[2]
CONFIG = ROOT / "configs/patient_journey_v2_followup/outcome_components.yaml"


def test_component_config_pins_scope_and_feature_exclusion(tmp_path):
    assert load_component_config(CONFIG) == ComponentConfig()
    for key, value in [
        ("release_code", "2605"),
        ("promotion_allowed", 0),
        ("component_fields", ["SAL_TOTFTX_C18"]),
        ("fit_models", True),
    ]:
        raw = yaml.safe_load(CONFIG.read_text())
        raw[key] = value
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.safe_dump(raw))
        with pytest.raises(ComponentError, match="fixed"):
            load_component_config(path)
    with pytest.raises(ComponentError, match="fixed"):
        validate_component_config(replace(ComponentConfig(), months_after_listing=12))


def _value(field, percent, **kwargs):
    return ComponentValue(field=field, percent=percent, **kwargs)


def test_donor_sums_keep_nulls_and_reject_overlap_or_different_meaning():
    a = _value("SAL_CTXFNC_C18", 10.0)
    b = _value("SAL_LTXFNC_C18", 20.0)
    assert sum_components((a, b)) == 30
    assert sum_components((a, replace(b, percent=None))) is None
    for changed in [
        a,
        replace(b, field="SAL_TOTFTX_C18"),
        replace(b, denominator="recipients"),
        replace(b, months_after_listing=12),
    ]:
        with pytest.raises(ComponentError, match="components"):
            sum_components((a, changed))


def test_rounding_intervals_include_boundary_and_keep_published_total():
    a, b = _value("SAL_CTXFNC_C18", 10), _value("SAL_LTXFNC_C18", 20)
    assert reconcile_functioning((a, b), 30.15)["status"] == "compatible"
    assert reconcile_functioning((a, b), 30.15)["published_total"] == 30.15
    with pytest.raises(ComponentError, match="rounding"):
        reconcile_functioning((a, b), 30.15001)
    assert reconcile_functioning((a, replace(b, percent=None)), 30)["status"] == "unavailable"


def _fixture(**changes):
    from test_patient_journey_parse import _methodology, _sheets, _source

    from kasm.data.parse import WorkbookSheet

    methodology = _methodology()
    metric = methodology.metric("patient_outcome")
    fields = metric.sheet.required_fields + COMPONENT_FIELDS
    values = [
        "Ignored label",
        "ABCD",
        "TX1",
        date(2025, 7, 8),
        "KI",
        40,
        37.5,
        25.0,
        "12.5",
        10.0,
        "5.0",
    ]
    for field, value in changes.items():
        values[fields.index(field)] = value
    descriptions = {
        "CTR_CD": "Center Code",
        "SAL_N_C": "N",
        "SAL_TOTFTX_C18": "Functioning tx (alive)",
        **{
            field: "Functioning (alive)" if "FNC" in field else "Status Yet Unknown"
            for field in COMPONENT_FIELDS
        },
    }
    sheet = WorkbookSheet(
        "Table B7",
        (fields, tuple(descriptions.get(f, f) for f in fields), tuple(values)),
        len(fields),
    )
    metric = replace(metric, sheet=replace(metric.sheet, expected_columns=len(fields)))
    methodology = replace(methodology, metrics=(metric, *methodology.metrics[1:]))
    return _source(), methodology, (_sheets()[0], sheet)


def test_parser_preserves_numeric_text_and_original_denominator():
    rows = parse_component_workbook(*_fixture(), ComponentConfig())
    row = rows[0]
    assert row.program_key == "ABCD:TX1"
    assert row.target_n == 40
    assert row.published_total == 37.5
    assert row.components[1].percent == 12.5
    assert row.components[1].raw_value == "12.5"
    assert row.listing_cohort_start == date(2022, 7, 1)
    assert row.combined_unknown == 15


@pytest.mark.parametrize("marker", [None, "", "-", "--", "Not Reported", "Not Observed"])
def test_missing_component_does_not_become_zero(marker):
    row = parse_component_workbook(*_fixture(SAL_LTXUNK_C18=marker), ComponentConfig())[0]
    assert row.combined_unknown is None
    assert row.components[3].raw_value == marker


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -1, 101, "new suppression"])
def test_malformed_component_fails(value):
    with pytest.raises(ComponentError):
        parse_component_workbook(*_fixture(SAL_LTXUNK_C18=value), ComponentConfig())


def test_missing_component_cannot_hide_impossible_reported_percentage():
    with pytest.raises(ComponentError, match="exceed 100"):
        parse_component_workbook(
            *_fixture(
                SAL_CTXFNC_C18=60,
                SAL_LTXFNC_C18=40,
                SAL_TOTFTX_C18=100,
                SAL_CTXUNK_C18=5,
                SAL_LTXUNK_C18=None,
            ),
            ComponentConfig(),
        )


def test_parser_rejects_changed_header_label_duplicate_key_and_wrong_timing():
    source, ledger, sheets = _fixture()
    sheet = sheets[1]
    for bad in [
        replace(sheet, column_count=999),
        replace(sheet, rows=(sheet.rows[0][:-1], *sheet.rows[1:])),
        replace(
            sheet, rows=(sheet.rows[0], tuple("changed" for _ in sheet.rows[1]), sheet.rows[2])
        ),
    ]:
        with pytest.raises(ComponentError):
            parse_component_workbook(source, ledger, (sheets[0], bad), ComponentConfig())
    metric = ledger.metric("patient_outcome")
    wrong = replace(ledger, metrics=(replace(metric, measurement_start=date(2023, 1, 1)),))
    with pytest.raises(ComponentError, match="cohort"):
        parse_component_workbook(source, wrong, sheets, ComponentConfig())
    duplicate = replace(sheet, rows=(*sheet.rows, sheet.rows[2]))
    ledger = replace(
        ledger, metrics=(replace(metric, sheet=replace(metric.sheet, expected_rows=2)),)
    )
    with pytest.raises(ComponentError, match="duplicate"):
        parse_component_workbook(source, ledger, (sheets[0], duplicate), ComponentConfig())


@pytest.mark.parametrize(
    "field",
    [*("SAL_CTXFNC_C18", "SAL_LTXFNC_C18", "SAL_CTXUNK_C18", "SAL_LTXUNK_C18"), "combined_unknown"],
)
def test_target_period_components_cannot_enter_original_model(field):
    from kasm.patient_journey.modeling import PatientJourneyModelError, build_feature_matrix

    with pytest.raises(PatientJourneyModelError, match="allowlist"):
        build_feature_matrix([{field: 20}], [field])
    from kasm.patient_journey.followup_config import (
        FollowupConfig,
        FollowupConfigError,
        validate_followup_config,
    )

    followup = FollowupConfig()
    changed_group = ("history", (*followup.feature_groups[0][1], field))
    with pytest.raises(FollowupConfigError, match="fixed"):
        validate_followup_config(
            replace(followup, feature_groups=(changed_group, *followup.feature_groups[1:]))
        )
