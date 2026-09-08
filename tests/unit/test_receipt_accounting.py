"""Keep receipt percentages tied to all five statuses and the original listing group."""

from dataclasses import replace
from math import log

import pytest

from kasm.patient_journey.components import ComponentValue
from kasm.patient_journey.receipt_accounting import (
    DECEASED_FIELDS,
    LIVING_FIELDS,
    ReceiptAccountingError,
    parse_receipt_values,
    sum_donor_receipt,
)


def receipt_row() -> dict[str, object]:
    """Hypothetical 200-person group; 30% deceased receipt and 10% living receipt."""
    return {
        "SAL_N_C": 200,
        "SAL_CTXFNC_C18": 20,
        "SAL_CTXRE_C18": 1,
        "SAL_CTXFAIL_C18": 2,
        "SAL_CTXDIED_C18": 3,
        "SAL_CTXUNK_C18": 4,
        "SAL_LTXFNC_C18": 6,
        "SAL_LTXRE_C18": 1,
        "SAL_LTXFAIL_C18": 1,
        "SAL_LTXDIED_C18": 1,
        "SAL_LTXUNK_C18": 1,
        "SAL_LOST_C18": 1,
        "SAL_REFTX_C18": 1,
        "SAL_REMDET_C18": 2,
        "SAL_REMOTH_C18": 1,
        "SAL_REMREC_C18": 1,
        "SAL_WLDIED_C18": 4,
        "SAL_WLLIVE_C18": 50,
        "SAL_TOTTX_C18": 40,
        "SAL_TOTAL_C18": 100,
    }


def test_receipt_includes_unknown_and_failed_statuses_in_original_denominator() -> None:
    result = parse_receipt_values(receipt_row())
    assert result.target_n == 200
    assert result.derived_receipt_percent == 30
    assert result.target_proportion == 0.3
    assert result.target_logit == pytest.approx(log(60.5 / 140.5))
    assert result.derived_living_receipt_percent == 10
    assert result.published_all_donor_percent == 40
    assert result.derived_label == "Derived from published deceased-donor components"
    assert result.deceased_components[-1].field == "SAL_CTXUNK_C18"
    assert result.deceased_components[-1].percent == 4
    assert all(c.denominator == "SAL_N_C" for c in result.deceased_components)
    assert all(c.months_after_listing == 18 for c in result.deceased_components)
    assert result.reconciliation["donor_receipt"]["status"] == "compatible"
    assert result.reconciliation["all_statuses"]["status"] == "compatible"


@pytest.mark.parametrize("field", DECEASED_FIELDS)
@pytest.mark.parametrize("missing", [None, "", "-", "--", "NOT REPORTED", "NOT OBSERVED"])
def test_each_missing_deceased_status_makes_receipt_unknown(field: str, missing: object) -> None:
    row = receipt_row()
    row[field] = missing
    result = parse_receipt_values(row)
    assert result.derived_receipt_percent is None
    assert result.target_proportion is None
    assert result.target_logit is None
    assert result.derived_living_receipt_percent == 10
    assert result.reconciliation["donor_receipt"]["status"] == "unavailable"
    assert result.reconciliation["all_statuses"]["status"] == "unavailable"
    assert next(c for c in result.deceased_components if c.field == field).raw_value == missing


@pytest.mark.parametrize(
    "field", [*LIVING_FIELDS, "SAL_TOTTX_C18", "SAL_LOST_C18", "SAL_TOTAL_C18"]
)
def test_missing_accounting_value_preserves_complete_target(field: str) -> None:
    row = receipt_row()
    del row[field]
    result = parse_receipt_values(row)
    assert result.derived_receipt_percent == 30
    check = "donor_receipt" if field in (*LIVING_FIELDS, "SAL_TOTTX_C18") else "all_statuses"
    assert result.reconciliation[check]["status"] == "unavailable"


def test_transform_preserves_fractional_published_information() -> None:
    row: dict[str, object] = {field: 0 for field in DECEASED_FIELDS}
    row.update({"SAL_N_C": "11", "SAL_CTXFNC_C18": "12.3456789"})
    result = parse_receipt_values(row)
    assert result.derived_receipt_percent == 12.3456789
    assert result.target_logit == pytest.approx(
        log((11 * 0.123456789 + 0.5) / (11 * (1 - 0.123456789) + 0.5))
    )
    assert result.deceased_components[0].raw_value == "12.3456789"


@pytest.mark.parametrize("percent", [0, 100])
def test_boundary_targets_have_finite_fitting_values(percent: int) -> None:
    row: dict[str, object] = {field: 0 for field in DECEASED_FIELDS}
    row.update({"SAL_N_C": 10, "SAL_CTXFNC_C18": percent})
    result = parse_receipt_values(row)
    assert result.derived_receipt_percent == percent
    assert result.target_logit == pytest.approx(
        log((percent / 10 + 0.5) / (10 - percent / 10 + 0.5))
    )


@pytest.mark.parametrize("value", [-1, 0.5, True, float("inf"), float("nan"), "bad"])
def test_invalid_listing_count_fails(value: object) -> None:
    row = receipt_row()
    row["SAL_N_C"] = value
    with pytest.raises(ReceiptAccountingError, match="SAL_N_C"):
        parse_receipt_values(row)


def test_oversized_integer_reports_an_actionable_numeric_error() -> None:
    row = receipt_row()
    row["SAL_N_C"] = 10**400
    with pytest.raises(ReceiptAccountingError, match="SAL_N_C.*finite"):
        parse_receipt_values(row)


def test_finite_large_denominator_cannot_overflow_fitting_transform() -> None:
    row: dict[str, object] = {field: 0 for field in DECEASED_FIELDS}
    row.update({"SAL_N_C": 1e308, "SAL_CTXFNC_C18": 100})
    assert parse_receipt_values(row).target_logit == pytest.approx(log(1e308) - log(0.5))


@pytest.mark.parametrize("value", [-0.01, 100.01, True, float("inf"), float("nan"), "bad", []])
def test_invalid_percentage_fails(value: object) -> None:
    row = receipt_row()
    row["SAL_CTXFNC_C18"] = value
    with pytest.raises(ReceiptAccountingError, match="SAL_CTXFNC_C18"):
        parse_receipt_values(row)


@pytest.mark.parametrize("count", [None, "-", 0])
def test_reported_percentage_requires_positive_denominator(count: object) -> None:
    row = receipt_row()
    row["SAL_N_C"] = count
    with pytest.raises(ReceiptAccountingError, match="positive original listing denominator"):
        parse_receipt_values(row)


@pytest.mark.parametrize("count", [None, "--", 0, 10])
def test_all_unreported_percentages_remain_unknown(count: object) -> None:
    result = parse_receipt_values({"SAL_N_C": count})
    assert result.derived_receipt_percent is None
    assert result.target_logit is None
    assert result.reconciliation["donor_receipt"]["status"] == "unavailable"


def test_rounding_intervals_reconcile_without_changing_values() -> None:
    row = receipt_row()
    row["SAL_TOTTX_C18"] = 40.5
    row["SAL_WLLIVE_C18"] = 50.2
    result = parse_receipt_values(row)
    assert result.published_all_donor_percent == 40.5
    assert result.derived_receipt_percent == 30
    assert result.reconciliation["donor_receipt"]["workbook_difference_percentage_points"] == -0.5
    assert result.reconciliation["all_statuses"]["component_sum"] == 100.2


@pytest.mark.parametrize(
    ("field", "value"), [("SAL_TOTTX_C18", 41), ("SAL_WLLIVE_C18", 51), ("SAL_TOTAL_C18", 99)]
)
def test_incompatible_complete_accounting_fails(field: str, value: float) -> None:
    row = receipt_row()
    row[field] = value
    with pytest.raises(ReceiptAccountingError, match="rounding"):
        parse_receipt_values(row)


def test_derived_excess_is_not_clipped_under_pdf_rounding_allowance() -> None:
    row: dict[str, object] = {field: 20 for field in DECEASED_FIELDS}
    row.update({"SAL_N_C": 100, "SAL_CTXUNK_C18": 20.01})
    with pytest.raises(ReceiptAccountingError, match="between 0 and 100"):
        parse_receipt_values(row)


def test_only_floating_point_boundary_noise_can_be_normalized() -> None:
    row: dict[str, object] = {field: 20 for field in DECEASED_FIELDS}
    row.update({"SAL_N_C": 100, "SAL_CTXUNK_C18": 20 + 5e-11})
    assert parse_receipt_values(row).derived_receipt_percent == 100


def test_incomplete_disjoint_statuses_cannot_already_exceed_entire_group() -> None:
    row = receipt_row()
    row["SAL_WLLIVE_C18"] = 90
    row["SAL_CTXUNK_C18"] = None
    with pytest.raises(ReceiptAccountingError, match="exceed 100"):
        parse_receipt_values(row)


@pytest.mark.parametrize(
    "change",
    [{"denominator": "recipients"}, {"months_after_listing": 12}, {"field": "SAL_LTXUNK_C18"}],
)
def test_sum_rejects_mixed_denominator_time_or_donor_fields(change: dict[str, object]) -> None:
    components = tuple(ComponentValue(field, 1) for field in DECEASED_FIELDS)
    changed = (replace(components[0], **change), *components[1:])
    with pytest.raises(ReceiptAccountingError, match="five.*denominator.*18"):
        sum_donor_receipt(changed)


def test_sum_requires_every_distinct_donor_status() -> None:
    components = tuple(ComponentValue(field, 1) for field in DECEASED_FIELDS)
    with pytest.raises(ReceiptAccountingError, match="five"):
        sum_donor_receipt(components[:-1])
    with pytest.raises(ReceiptAccountingError, match="five"):
        sum_donor_receipt((components[0], *components[:-1]))
