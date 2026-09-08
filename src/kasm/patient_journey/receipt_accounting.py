"""Count all reported receipt statuses within the original 18-month listing group.

The deceased-donor percentage is a derived sum of five published percentages.
Unknown later health status still records receipt; missing source values stay missing.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from kasm.patient_journey.component_config import ComponentConfig
from kasm.patient_journey.components import ComponentValue
from kasm.patient_journey.parse import PatientJourneyParseError, _number

DECEASED_FIELDS = (
    "SAL_CTXFNC_C18",
    "SAL_CTXRE_C18",
    "SAL_CTXFAIL_C18",
    "SAL_CTXDIED_C18",
    "SAL_CTXUNK_C18",
)
LIVING_FIELDS = tuple(field.replace("CTX", "LTX") for field in DECEASED_FIELDS)
OTHER_FIELDS = (
    "SAL_LOST_C18",
    "SAL_REFTX_C18",
    "SAL_REMDET_C18",
    "SAL_REMOTH_C18",
    "SAL_REMREC_C18",
    "SAL_WLDIED_C18",
    "SAL_WLLIVE_C18",
)
RECEIPT_FIELDS = (
    "SAL_N_C",
    *DECEASED_FIELDS,
    *LIVING_FIELDS,
    *OTHER_FIELDS,
    "SAL_TOTTX_C18",
    "SAL_TOTAL_C18",
)
PDF_PERCENTAGE_QUANTUM = 0.1
ARITHMETIC_TOLERANCE = 1e-10
DERIVED_LABEL = "Derived from published deceased-donor components"


class ReceiptAccountingError(ValueError):
    """The values cannot describe the agreed original listing group and statuses."""


@dataclass(frozen=True)
class ReceiptValues:
    """One program/cohort's source percentages and separately labeled fitting transform."""

    target_n: int | None
    derived_receipt_percent: float | None
    target_proportion: float | None
    target_logit: float | None
    deceased_components: tuple[ComponentValue, ...]
    living_components: tuple[ComponentValue, ...]
    other_components: tuple[ComponentValue, ...]
    published_all_donor_percent: float | None
    published_status_total: float | None
    derived_living_receipt_percent: float | None
    reconciliation: dict[str, dict[str, object]]
    raw_target_n: object
    derived_label: str = DERIVED_LABEL


def _reported_number(value: object, field: str) -> float | None:
    if isinstance(value, str) and value.strip().upper() in ComponentConfig().missing_markers:
        return None
    try:
        return _number(value, field=field, context="Receipt accounting")
    except OverflowError as exc:
        raise ReceiptAccountingError(f"{field} must be a finite numeric value.") from exc
    except PatientJourneyParseError as exc:
        raise ReceiptAccountingError(str(exc)) from exc


def _bounded_percent(value: float, field: str) -> float:
    if not -ARITHMETIC_TOLERANCE <= value <= 100 + ARITHMETIC_TOLERANCE:
        raise ReceiptAccountingError(f"{field} must be a percentage between 0 and 100.")
    # Only arithmetic noise can cross a boundary; PDF rounding never permits clipping.
    return min(100.0, max(0.0, value))


def _percent(value: object, field: str) -> float | None:
    number = _reported_number(value, field)
    return None if number is None else _bounded_percent(number, field)


def _count(value: object) -> int | None:
    number = _reported_number(value, "SAL_N_C")
    if number is None:
        return None
    if number < 0 or not number.is_integer():
        raise ReceiptAccountingError("SAL_N_C must be a nonnegative whole candidate count.")
    return int(number)


def sum_donor_receipt(components: tuple[ComponentValue, ...]) -> float | None:
    """Add exactly five disjoint donor statuses with the same denominator and time."""
    fields = tuple(component.field for component in components)
    if (
        len(fields) != 5
        or set(fields) not in (set(DECEASED_FIELDS), set(LIVING_FIELDS))
        or any(c.denominator != "SAL_N_C" or c.months_after_listing != 18 for c in components)
    ):
        raise ReceiptAccountingError(
            "Receipt requires five distinct same-donor statuses, "
            "denominator SAL_N_C, and 18 months."
        )
    values = [_percent(c.percent, c.field) for c in components]
    known_sum = math.fsum(value for value in values if value is not None)
    bounded_sum = _bounded_percent(known_sum, "Derived donor receipt")
    return None if any(value is None for value in values) else bounded_sum


def _interval(value: float) -> tuple[float, float]:
    half = PDF_PERCENTAGE_QUANTUM / 2
    return max(0.0, value - half), min(100.0, value + half)


def _sum_interval(components: tuple[ComponentValue, ...]) -> tuple[float, float]:
    intervals = [_interval(c.percent) for c in components if c.percent is not None]
    return math.fsum(i[0] for i in intervals), math.fsum(i[1] for i in intervals)


def _reconcile(
    components: tuple[ComponentValue, ...],
    published_total: float | None,
    *,
    whole_group: bool,
) -> dict[str, object]:
    available = published_total is not None and all(c.percent is not None for c in components)
    component_sum = (
        math.fsum(c.percent for c in components if c.percent is not None)
        if all(c.percent is not None for c in components)
        else None
    )
    result: dict[str, object] = {
        "status": "unavailable",
        "published_total": published_total,
        "component_sum": component_sum,
        "workbook_difference_percentage_points": None,
    }
    if not available or published_total is None or component_sum is None:
        return result
    lower, upper = _sum_interval(components)
    total_lower, total_upper = _interval(published_total)
    if max(lower, total_lower) > min(upper, total_upper) + ARITHMETIC_TOLERANCE or (
        whole_group
        and not max(lower, total_lower) - ARITHMETIC_TOLERANCE
        <= 100
        <= min(upper, total_upper) + ARITHMETIC_TOLERANCE
    ):
        raise ReceiptAccountingError(
            "Reported statuses disagree with their total within PDF rounding."
        )
    result.update(
        status="compatible",
        workbook_difference_percentage_points=component_sum - published_total,
    )
    return result


def _components(
    values: Mapping[str, object], fields: tuple[str, ...]
) -> tuple[ComponentValue, ...]:
    return tuple(
        ComponentValue(field, _percent(values.get(field), field), values.get(field))
        for field in fields
    )


def parse_receipt_values(values: Mapping[str, object]) -> ReceiptValues:
    """Parse one listing group by machine field, retaining source precision and missingness.

    Source identity, field descriptions, donor headings and release dates must already
    pass the separate source gate. Extra fields, including other endpoints, are not used.
    """
    target_n = _count(values.get("SAL_N_C"))
    deceased = _components(values, DECEASED_FIELDS)
    living = _components(values, LIVING_FIELDS)
    other = _components(values, OTHER_FIELDS)
    all_components = (*deceased, *living, *other)
    published_all = _percent(values.get("SAL_TOTTX_C18"), "SAL_TOTTX_C18")
    published_status_total = _percent(values.get("SAL_TOTAL_C18"), "SAL_TOTAL_C18")
    if (target_n is None or target_n == 0) and any(
        percent is not None
        for percent in (published_all, published_status_total, *(c.percent for c in all_components))
    ):
        raise ReceiptAccountingError(
            "Reported percentages require a positive original listing denominator."
        )
    deceased_receipt = sum_donor_receipt(deceased)
    living_receipt = sum_donor_receipt(living)
    if _sum_interval(all_components)[0] > 100 + ARITHMETIC_TOLERANCE:
        raise ReceiptAccountingError("Disjoint reported statuses exceed 100 within PDF rounding.")
    proportion = None if deceased_receipt is None else deceased_receipt / 100
    target_logit = (
        None
        if proportion is None or target_n is None
        else math.log(target_n * proportion + 0.5) - math.log(target_n * (1 - proportion) + 0.5)
    )
    return ReceiptValues(
        target_n=target_n,
        derived_receipt_percent=deceased_receipt,
        target_proportion=proportion,
        target_logit=target_logit,
        deceased_components=deceased,
        living_components=living,
        other_components=other,
        published_all_donor_percent=published_all,
        published_status_total=published_status_total,
        derived_living_receipt_percent=living_receipt,
        reconciliation={
            "donor_receipt": _reconcile((*deceased, *living), published_all, whole_group=False),
            "all_statuses": _reconcile(all_components, published_status_total, whole_group=True),
        },
        raw_target_n=values.get("SAL_N_C"),
    )
