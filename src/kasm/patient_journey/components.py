"""Read donor-specific reported status without filling in unknown patient outcomes.

Every percentage uses the original listing group at 18 months. Only the two
functioning components or the two post-transplant unknown components may be added.
The published functioning total stays separate and authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from kasm.config import SourceRecord
from kasm.data.parse import WorkbookSheet
from kasm.patient_journey.component_config import (
    COMPONENT_FIELDS,
    ComponentConfig,
    ComponentError,
    validate_component_config,
)
from kasm.patient_journey.ledger import ReleaseMethodology
from kasm.patient_journey.parse import (
    PatientJourneyParseError,
    _number,
    _parse_identities,
    _program_key,
    _row_value,
    _validate_publication_date,
    _validated_sheet_rows,
)

DESCRIPTIONS = {
    "SAL_N_C": "N",
    "SAL_TOTFTX_C18": "Functioning tx (alive)",
    **{
        field: "Functioning (alive)" if "FNC" in field else "Status Yet Unknown"
        for field in COMPONENT_FIELDS
    },
}


@dataclass(frozen=True)
class ComponentValue:
    """One published percentage, its original raw value, denominator and elapsed time."""

    field: str
    percent: float | None
    raw_value: object = None
    denominator: str = "SAL_N_C"
    months_after_listing: int = 18


@dataclass(frozen=True)
class ComponentRecord:
    """One program/listing group; null components never stand for zero patients."""

    program_key: str
    release_code: str
    listing_cohort_start: date
    listing_cohort_end: date
    follow_up_end: date
    target_n: int | None
    published_total: float | None
    components: tuple[ComponentValue, ...]
    combined_unknown: float | None
    reconciliation: dict[str, object]
    raw_target_n: object
    raw_published_total: object


def _percent(value: object, field: str) -> float | None:
    if value is None or (
        isinstance(value, str) and value.strip().upper() in ComponentConfig().missing_markers
    ):
        return None
    try:
        number = _number(value, field=field, context="Outcome component")
    except PatientJourneyParseError as exc:
        raise ComponentError(str(exc)) from exc
    if number is not None and not 0 <= number <= 100:
        raise ComponentError(f"{field} must be a percentage between 0 and 100.")
    return number


def sum_components(components: tuple[ComponentValue, ...]) -> float | None:
    """Add one disjoint donor pair, preserving missing operands and source meaning."""
    fields = tuple(component.field for component in components)
    if (
        len(fields) != 2
        or set(fields) not in (set(COMPONENT_FIELDS[:2]), set(COMPONENT_FIELDS[2:]))
        or any(c.denominator != "SAL_N_C" or c.months_after_listing != 18 for c in components)
    ):
        raise ComponentError(
            "Only disjoint donor components with the same denominator/time can be added."
        )
    values = [_percent(c.percent, c.field) for c in components]
    if any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def _interval(value: float) -> tuple[float, float]:
    half = ComponentConfig().pdf_percentage_quantum / 2
    return max(0.0, value - half), min(100.0, value + half)


def reconcile_functioning(
    components: tuple[ComponentValue, ...], published_total: float | None
) -> dict[str, object]:
    """Check donor sums at the PDF's display precision without replacing its total."""
    donor_sum = sum_components(components)
    if set(c.field for c in components) != set(COMPONENT_FIELDS[:2]):
        raise ComponentError("Functioning reconciliation requires functioning components.")
    total = _percent(published_total, "SAL_TOTFTX_C18")
    if donor_sum is None or total is None:
        return {
            "status": "unavailable",
            "published_total": total,
            "donor_sum": donor_sum,
            "workbook_difference_percentage_points": None,
        }
    intervals = [_interval(c.percent) for c in components if c.percent is not None]
    lower, upper = sum(i[0] for i in intervals), sum(i[1] for i in intervals)
    total_lower, total_upper = _interval(total)
    if max(lower, total_lower) > min(upper, total_upper) + ComponentConfig().arithmetic_tolerance:
        raise ComponentError(
            "Functioning donor components disagree with the published total within PDF rounding."
        )
    return {
        "status": "compatible",
        "published_total": total,
        "donor_sum": donor_sum,
        "workbook_difference_percentage_points": donor_sum - total,
    }


def _validate_scope(
    source: SourceRecord, methodology: ReleaseMethodology, config: ComponentConfig
) -> None:
    validate_component_config(config)
    metric = methodology.metric("patient_outcome")
    if (
        source.release_code != config.release_code
        or methodology.release_code != config.release_code
        or str(metric.measurement_start) != config.listing_cohort_start
        or str(metric.measurement_end) != config.listing_cohort_end
        or str(metric.follow_up_end) != config.follow_up_end
        or source.published_value != config.published_value
        or methodology.published_value != source.published_value
        or source.published_precision != config.published_precision
        or methodology.published_precision != source.published_precision
        or source.url != methodology.source_url
        or source.download_sha256 != methodology.source_sha256
    ):
        raise ComponentError(
            "Source, cohort or publication disagrees with the fixed component scope."
        )


def _descriptions(sheet: WorkbookSheet, required: tuple[str, ...]) -> None:
    for index, row in enumerate(sheet.rows[:10]):
        if set(required).issubset(row):
            if index + 1 >= len(sheet.rows):
                break
            description = sheet.rows[index + 1]
            for field, expected in DESCRIPTIONS.items():
                column = row.index(field)
                if column >= len(description) or description[column] != expected:
                    raise ComponentError(f"Source description changed for {field}.")
            return
    raise ComponentError("Source machine fields or description row are missing.")


def _record(values: dict[str, object], key: str, config: ComponentConfig) -> ComponentRecord:
    raw_n = values["SAL_N_C"]
    missing = raw_n is None or (
        isinstance(raw_n, str) and raw_n.strip().upper() in config.missing_markers
    )
    count = None if missing else _number(raw_n, field="SAL_N_C", context=key)
    if count is not None and (count < 0 or not count.is_integer()):
        raise ComponentError("SAL_N_C must be a nonnegative whole candidate count.")
    total = _percent(values["SAL_TOTFTX_C18"], "SAL_TOTFTX_C18")
    components = tuple(
        ComponentValue(field, _percent(values[field], field), values[field])
        for field in COMPONENT_FIELDS
    )
    if (count is None or count == 0) and any(
        v is not None for v in (total, *(c.percent for c in components))
    ):
        raise ComponentError(
            "Reported percentages require a positive original listing denominator."
        )
    minimum = sum(_interval(c.percent)[0] for c in components if c.percent is not None)
    if minimum > 100 + config.arithmetic_tolerance:
        raise ComponentError("Disjoint selected components exceed 100 within PDF rounding.")
    return ComponentRecord(
        key,
        config.release_code,
        date.fromisoformat(config.listing_cohort_start),
        date.fromisoformat(config.listing_cohort_end),
        date.fromisoformat(config.follow_up_end),
        None if count is None else int(count),
        total,
        components,
        sum_components(components[2:]),
        reconcile_functioning(components[:2], total),
        raw_n,
        values["SAL_TOTFTX_C18"],
    )


def parse_component_workbook(
    source: SourceRecord,
    methodology: ReleaseMethodology,
    sheets: tuple[WorkbookSheet, ...],
    config: ComponentConfig,
) -> tuple[ComponentRecord, ...]:
    """Read only the fixed outcome table and same-release directory, by field name."""
    _validate_scope(source, methodology, config)
    try:
        registry = {row.program_key for row in _parse_identities(source, methodology, sheets)}
        contract = methodology.metric("patient_outcome").sheet
        contract = replace(
            contract,
            required_fields=tuple(dict.fromkeys((*contract.required_fields, *DESCRIPTIONS))),
        )
        positions, rows = _validated_sheet_rows(source, contract, sheets)
        _descriptions(next(s for s in sheets if s.name == contract.name), contract.required_fields)
        records = {}
        for row in rows:
            values = {
                field: _row_value(row, positions, field) for field in contract.required_fields
            }
            _, _, key = _program_key(
                values["CTR_CD"], values["CTR_TY"], context=source.release_code
            )
            if key in records:
                raise ComponentError(f"Source has duplicate program key {key}.")
            if key not in registry or values["ORG"] != "KI":
                raise ComponentError(
                    "Outcome must be a kidney program in the same-release directory."
                )
            _validate_publication_date(
                values["RELEASE_DATE"], source=source, field="RELEASE_DATE", context=key
            )
            records[key] = _record(values, key, config)
    except PatientJourneyParseError as exc:
        raise ComponentError(str(exc)) from exc
    return tuple(records[key] for key in sorted(records))
