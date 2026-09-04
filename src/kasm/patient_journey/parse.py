"""Schema-aware parsing for patient-journey v2 source metrics."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import cast

from kasm.config import DataSourceManifest, PublishedPrecision, SourceRecord
from kasm.data.parse import WorkbookSheet, load_workbook_payload, read_workbook_sheets
from kasm.patient_journey.ledger import (
    MethodologyLedger,
    MetricMethodology,
    ReleaseMethodology,
    SheetContract,
)

_CENTER_CODE = re.compile(r"^[A-Z0-9]{4}$")
_CENTER_TYPE = re.compile(r"^[A-Z0-9]+$")
_COMBINED_PROGRAM = re.compile(r"^([A-Z0-9]{4})([A-Z0-9]+)$")
_SUPPRESSED_WAIT_TIME = frozenset({"", "-", "--", ">72", "NOT OBSERVED"})

_IDENTITY_FIELDS = frozenset(
    {
        "ENTIRE_NAME",
        "PRIMARY_CITY",
        "PRIMARY_STATE",
        "PRIMARY_ZIP",
        "CTR_CD",
        "CTR_TY",
        "ORGAN",
    }
)
_OUTCOME_FIELDS = frozenset(
    {"ENTIRE_NAME", "CTR_CD", "CTR_TY", "RELEASE_DATE", "ORG", "SAL_N_C", "SAL_TOTFTX_C18"}
)
_TRANSPLANT_RATE_FIELDS = frozenset(
    {"center", "RELEASE_DATE", "wl_org", "begdate", "enddate", "TMR_TxPy_c"}
)
_WAIT_TIME_FIELDS = frozenset(
    {"ENTIRE_NAME", "CTR_CD", "CTR_TY", "RELEASE_DATE", "ORG", "TTT_25_C"}
)


class PatientJourneyParseError(ValueError):
    """Raised when a workbook violates a v2 source or scientific contract."""


@dataclass(frozen=True)
class ProgramIdentity:
    """Display-only program identity reconciled from the same-release directory."""

    program_key: str
    center_code: str
    center_type: str
    center_name: str
    city: str | None
    state: str | None
    zip_code: str | None


@dataclass(frozen=True)
class PatientJourneyOutcome:
    """Published observed 18-month functioning-transplant outcome."""

    program_key: str
    release_code: str
    published_value: str
    published_precision: PublishedPrecision
    listing_cohort_start: date
    listing_cohort_end: date
    follow_up_end: date
    target_n: int | None
    published_percent: float | None
    target_proportion: float | None
    reconstructed_successes: int | None
    target_logit: float | None
    source_url: str
    source_sha256: str


@dataclass(frozen=True)
class TransplantRate:
    """Published program access measures from the transplant-rate table."""

    program_key: str
    release_code: str
    measurement_start: date
    measurement_end: date
    person_years: float | None
    transplant_rate_ratio: float | None


@dataclass(frozen=True)
class WaitTime:
    """Published program 25th-percentile time to transplant with raw suppression text."""

    program_key: str
    release_code: str
    measurement_start: date
    measurement_end: date
    follow_up_end: date
    months_25th_percentile: float | None
    raw_value: str | None


@dataclass(frozen=True)
class ParsedPatientJourneyRelease:
    """Validated v2 source metrics for one immutable workbook release."""

    release_code: str
    identities: tuple[ProgramIdentity, ...]
    outcomes: tuple[PatientJourneyOutcome, ...]
    transplant_rates: tuple[TransplantRate, ...]
    wait_times: tuple[WaitTime, ...]


@dataclass(frozen=True)
class PatientJourneyInventoryEntry:
    """Read-only audit evidence for one cached patient-journey release."""

    release_code: str
    identity_rows: int
    outcome_rows: int
    transplant_rate_rows: int
    wait_time_rows: int


def _context(source: SourceRecord, sheet_name: str, row_number: int | None = None) -> str:
    result = f"Release {source.release_code!r}, sheet {sheet_name!r}"
    return f"{result}, worksheet row {row_number}" if row_number is not None else result


def _header(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _is_blank(row: tuple[object, ...]) -> bool:
    return all(value is None or (isinstance(value, str) and not value.strip()) for value in row)


def _row_value(row: tuple[object, ...], positions: Mapping[str, int], field: str) -> object:
    position = positions[field]
    return row[position] if position < len(row) else None


def _description_row(row: tuple[object, ...], positions: Mapping[str, int]) -> bool:
    if "CTR_CD" in positions:
        value = _row_value(row, positions, "CTR_CD")
        return isinstance(value, str) and value.strip() in {"Center Code", "Center ID"}
    if "center" in positions:
        value = _row_value(row, positions, "center")
        return isinstance(value, str) and value.strip().lower() in {
            "center",
            "center name",
            "program",
        }
    return False


def _validated_sheet_rows(
    source: SourceRecord,
    contract: SheetContract,
    sheets: tuple[WorkbookSheet, ...],
) -> tuple[dict[str, int], tuple[tuple[object, ...], ...]]:
    sheet = next((candidate for candidate in sheets if candidate.name == contract.name), None)
    if sheet is None:
        available = ", ".join(candidate.name for candidate in sheets)
        raise PatientJourneyParseError(
            f"{_context(source, contract.name)} is missing; available sheets: {available}."
        )
    if sheet.column_count != contract.expected_columns:
        raise PatientJourneyParseError(
            f"{_context(source, contract.name)} column count changed: expected "
            f"{contract.expected_columns}, found {sheet.column_count}."
        )

    positions: dict[str, int] | None = None
    header_index = -1
    required = set(contract.required_fields)
    for row_index, row in enumerate(sheet.rows[:10]):
        headers = tuple(_header(value) for value in row)
        if not required.issubset(headers):
            continue
        candidate_positions: dict[str, int] = {}
        for column_index, header in enumerate(headers):
            if not header:
                continue
            if header in candidate_positions:
                raise PatientJourneyParseError(
                    f"{_context(source, contract.name)} duplicates machine field {header!r}."
                )
            candidate_positions[header] = column_index
        positions = candidate_positions
        header_index = row_index
        break
    if positions is None:
        preview = ", ".join(contract.required_fields[:5])
        raise PatientJourneyParseError(
            f"{_context(source, contract.name)} lacks required machine fields such as {preview}."
        )

    rows = tuple(row for row in sheet.rows[header_index + 1 :] if not _is_blank(row))
    if rows and _description_row(rows[0], positions):
        rows = rows[1:]
    if len(rows) != contract.expected_rows:
        raise PatientJourneyParseError(
            f"{_context(source, contract.name)} row count changed: expected "
            f"{contract.expected_rows}, found {len(rows)}."
        )
    return positions, rows


def _text(value: object, *, field: str, context: str, required: bool = True) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise PatientJourneyParseError(f"{context}: {field} is missing.")
        return None
    if isinstance(value, bool):
        raise PatientJourneyParseError(f"{context}: {field} must be text, not boolean.")
    if isinstance(value, float) and value.is_integer():
        result = str(int(value))
    else:
        result = str(value).strip()
    return result or None


def _number(value: object, *, field: str, context: str, required: bool = False) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise PatientJourneyParseError(f"{context}: {field} is missing.")
        return None
    if isinstance(value, str):
        try:
            result = float(value.strip().replace(",", ""))
        except ValueError as error:
            raise PatientJourneyParseError(f"{context}: {field} must be numeric.") from error
    elif isinstance(value, bool) or not isinstance(value, int | float):
        raise PatientJourneyParseError(f"{context}: {field} must be numeric.")
    else:
        result = float(value)
    if not math.isfinite(result):
        raise PatientJourneyParseError(f"{context}: {field} must be finite.")
    return result


def _nonnegative_number(
    value: object, *, field: str, context: str, required: bool = False
) -> float | None:
    result = _number(value, field=field, context=context, required=required)
    if result is not None and result < 0:
        raise PatientJourneyParseError(f"{context}: {field} cannot be negative.")
    return result


def _count(value: object, *, field: str, context: str) -> int | None:
    number = _nonnegative_number(value, field=field, context=context)
    if number is None:
        return None
    if not number.is_integer():
        raise PatientJourneyParseError(f"{context}: {field} must be a whole number.")
    return int(number)


def _excel_date(value: int | float) -> date:
    return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()


def _date_value(value: object, *, field: str, context: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, bool):
        raise PatientJourneyParseError(f"{context}: {field} must be a date.")
    if isinstance(value, int | float):
        return _excel_date(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip()).date()
        except ValueError as error:
            raise PatientJourneyParseError(f"{context}: {field} must be a date.") from error
    raise PatientJourneyParseError(f"{context}: {field} must be a date.")


def _validate_publication_date(
    value: object,
    *,
    source: SourceRecord,
    field: str,
    context: str,
) -> None:
    observed = _date_value(value, field=field, context=context)
    if source.published_precision == "month":
        expected_year, expected_month = (int(part) for part in source.published_value.split("-"))
        if (observed.year, observed.month) != (expected_year, expected_month):
            raise PatientJourneyParseError(
                f"{context}: {field} disagrees with month-precision source publication."
            )
        return
    expected = date.fromisoformat(source.published_value)
    if abs(observed - expected) > timedelta(days=1):
        raise PatientJourneyParseError(
            f"{context}: {field} disagrees with source publication date."
        )


def _normalized_metric_date(
    value: object,
    expected: date,
    *,
    field: str,
    context: str,
) -> date:
    observed = _date_value(value, field=field, context=context)
    if abs(observed - expected) > timedelta(days=2):
        raise PatientJourneyParseError(
            f"{context}: {field} {observed.isoformat()} disagrees with methodology ledger "
            f"date {expected.isoformat()}."
        )
    return expected


def _program_key(code_value: object, type_value: object, *, context: str) -> tuple[str, str, str]:
    code = cast(str, _text(code_value, field="CTR_CD", context=context)).upper()
    center_type = cast(str, _text(type_value, field="CTR_TY", context=context)).upper()
    if _CENTER_CODE.fullmatch(code) is None:
        raise PatientJourneyParseError(f"{context}: CTR_CD must match [A-Z0-9]{{4}}.")
    if _CENTER_TYPE.fullmatch(center_type) is None:
        raise PatientJourneyParseError(f"{context}: CTR_TY must contain only letters and digits.")
    return code, center_type, f"{code}:{center_type}"


def _validate_contract_fields(
    contract: SheetContract, required: frozenset[str], *, context: str
) -> None:
    missing = required - set(contract.required_fields)
    if missing:
        preview = ", ".join(sorted(missing))
        raise PatientJourneyParseError(f"{context} contract omits required fields: {preview}.")


def _parse_identities(
    source: SourceRecord,
    methodology: ReleaseMethodology,
    sheets: tuple[WorkbookSheet, ...],
) -> tuple[ProgramIdentity, ...]:
    contract = methodology.identity_sheet
    _validate_contract_fields(contract, _IDENTITY_FIELDS, context="Identity")
    positions, rows = _validated_sheet_rows(source, contract, sheets)
    identities: list[ProgramIdentity] = []
    seen: set[str] = set()
    for row_index, row in enumerate(rows, start=1):
        context = _context(source, contract.name, row_index)
        organ = cast(
            str, _text(_row_value(row, positions, "ORGAN"), field="ORGAN", context=context)
        )
        if organ not in {"Kidney", "KI"}:
            raise PatientJourneyParseError(f"{context}: ORGAN must identify kidney.")
        code, center_type, key = _program_key(
            _row_value(row, positions, "CTR_CD"),
            _row_value(row, positions, "CTR_TY"),
            context=context,
        )
        if key in seen:
            raise PatientJourneyParseError(f"{context}: duplicate identity {key!r}.")
        seen.add(key)
        identities.append(
            ProgramIdentity(
                program_key=key,
                center_code=code,
                center_type=center_type,
                center_name=_text(
                    _row_value(row, positions, "ENTIRE_NAME"),
                    field="ENTIRE_NAME",
                    context=context,
                    required=False,
                )
                or f"Program {code}",
                city=_text(
                    _row_value(row, positions, "PRIMARY_CITY"),
                    field="PRIMARY_CITY",
                    context=context,
                    required=False,
                ),
                state=_text(
                    _row_value(row, positions, "PRIMARY_STATE"),
                    field="PRIMARY_STATE",
                    context=context,
                    required=False,
                ),
                zip_code=_text(
                    _row_value(row, positions, "PRIMARY_ZIP"),
                    field="PRIMARY_ZIP",
                    context=context,
                    required=False,
                ),
            )
        )
    identities.sort(key=lambda identity: identity.program_key)
    return tuple(identities)


def _validate_registered_key(
    key: str, registry: Mapping[str, ProgramIdentity], context: str
) -> None:
    if key not in registry:
        raise PatientJourneyParseError(
            f"{context}: program {key!r} is not present in the same-release identity registry."
        )


def _target_values(
    n_value: object, percent_value: object, *, context: str
) -> tuple[int | None, float | None, float | None, int | None, float | None]:
    target_n = _count(n_value, field="SAL_N_C", context=context)
    published_percent = _number(percent_value, field="SAL_TOTFTX_C18", context=context)
    if target_n is None and published_percent is None:
        return None, None, None, None, None
    if target_n is None or target_n == 0 or published_percent is None:
        raise PatientJourneyParseError(
            f"{context}: SAL_N_C and SAL_TOTFTX_C18 must be jointly reported with positive N."
        )
    if not 0 <= published_percent <= 100:
        raise PatientJourneyParseError(f"{context}: SAL_TOTFTX_C18 must be between 0 and 100.")
    target_proportion = published_percent / 100
    successes = math.floor(target_n * target_proportion + 0.5)
    if not 0 <= successes <= target_n:
        raise PatientJourneyParseError(f"{context}: reconstructed successes are out of bounds.")
    reconstructed_percent = successes / target_n * 100
    if abs(reconstructed_percent - published_percent) > 0.051:
        raise PatientJourneyParseError(
            f"{context}: SAL_TOTFTX_C18 cannot be reconciled with SAL_N_C within rounding."
        )
    smoothed = (successes + 0.5) / (target_n + 1)
    target_logit = math.log(smoothed / (1 - smoothed))
    return target_n, published_percent, target_proportion, successes, target_logit


def _parse_outcomes(
    source: SourceRecord,
    metric: MetricMethodology,
    sheets: tuple[WorkbookSheet, ...],
    registry: Mapping[str, ProgramIdentity],
) -> tuple[PatientJourneyOutcome, ...]:
    _validate_contract_fields(metric.sheet, _OUTCOME_FIELDS, context="Patient outcome")
    positions, rows = _validated_sheet_rows(source, metric.sheet, sheets)
    outcomes: list[PatientJourneyOutcome] = []
    seen: set[str] = set()
    for row_index, row in enumerate(rows, start=1):
        context = _context(source, metric.sheet.name, row_index)
        if _text(_row_value(row, positions, "ORG"), field="ORG", context=context) != "KI":
            raise PatientJourneyParseError(f"{context}: ORG must be 'KI'.")
        _, _, key = _program_key(
            _row_value(row, positions, "CTR_CD"),
            _row_value(row, positions, "CTR_TY"),
            context=context,
        )
        _validate_registered_key(key, registry, context)
        if key in seen:
            raise PatientJourneyParseError(f"{context}: duplicate outcome {key!r}.")
        seen.add(key)
        _validate_publication_date(
            _row_value(row, positions, "RELEASE_DATE"),
            source=source,
            field="RELEASE_DATE",
            context=context,
        )
        target_n, percent, proportion, successes, target_logit = _target_values(
            _row_value(row, positions, "SAL_N_C"),
            _row_value(row, positions, "SAL_TOTFTX_C18"),
            context=context,
        )
        outcomes.append(
            PatientJourneyOutcome(
                program_key=key,
                release_code=source.release_code,
                published_value=source.published_value,
                published_precision=source.published_precision,
                listing_cohort_start=metric.measurement_start,
                listing_cohort_end=metric.measurement_end,
                follow_up_end=metric.follow_up_end,
                target_n=target_n,
                published_percent=percent,
                target_proportion=proportion,
                reconstructed_successes=successes,
                target_logit=target_logit,
                source_url=source.url,
                source_sha256=source.download_sha256,
            )
        )
    outcomes.sort(key=lambda outcome: outcome.program_key)
    return tuple(outcomes)


def _combined_key(value: object, *, context: str) -> str:
    combined = cast(str, _text(value, field="center", context=context)).upper()
    match = _COMBINED_PROGRAM.fullmatch(combined)
    if match is None:
        raise PatientJourneyParseError(
            f"{context}: center must match four-character CTR_CD followed by CTR_TY."
        )
    return f"{match.group(1)}:{match.group(2)}"


def _parse_transplant_rates(
    source: SourceRecord,
    metric: MetricMethodology,
    sheets: tuple[WorkbookSheet, ...],
    registry: Mapping[str, ProgramIdentity],
) -> tuple[TransplantRate, ...]:
    _validate_contract_fields(metric.sheet, _TRANSPLANT_RATE_FIELDS, context="Transplant rate")
    positions, rows = _validated_sheet_rows(source, metric.sheet, sheets)
    rates: list[TransplantRate] = []
    seen: set[str] = set()
    for row_index, row in enumerate(rows, start=1):
        context = _context(source, metric.sheet.name, row_index)
        if _text(_row_value(row, positions, "wl_org"), field="wl_org", context=context) != "KI":
            raise PatientJourneyParseError(f"{context}: wl_org must be 'KI'.")
        key = _combined_key(_row_value(row, positions, "center"), context=context)
        _validate_registered_key(key, registry, context)
        if key in seen:
            raise PatientJourneyParseError(f"{context}: duplicate transplant-rate row {key!r}.")
        seen.add(key)
        _validate_publication_date(
            _row_value(row, positions, "RELEASE_DATE"),
            source=source,
            field="RELEASE_DATE",
            context=context,
        )
        measurement_start = _normalized_metric_date(
            _row_value(row, positions, "begdate"),
            metric.measurement_start,
            field="begdate",
            context=context,
        )
        measurement_end = _normalized_metric_date(
            _row_value(row, positions, "enddate"),
            metric.measurement_end,
            field="enddate",
            context=context,
        )
        ratio = (
            _nonnegative_number(_row_value(row, positions, "TX_RR"), field="TX_RR", context=context)
            if "TX_RR" in positions
            else None
        )
        rates.append(
            TransplantRate(
                program_key=key,
                release_code=source.release_code,
                measurement_start=measurement_start,
                measurement_end=measurement_end,
                person_years=_nonnegative_number(
                    _row_value(row, positions, "TMR_TxPy_c"),
                    field="TMR_TxPy_c",
                    context=context,
                ),
                transplant_rate_ratio=ratio,
            )
        )
    rates.sort(key=lambda rate: rate.program_key)
    return tuple(rates)


def _raw_wait_time(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip() or None


def _wait_time_value(value: object, *, context: str) -> tuple[float | None, str | None]:
    raw = _raw_wait_time(value)
    if raw is None or raw.upper() in _SUPPRESSED_WAIT_TIME:
        return None, raw
    number = _nonnegative_number(value, field="TTT_25_C", context=context, required=True)
    return number, raw


def _parse_wait_times(
    source: SourceRecord,
    metric: MetricMethodology,
    sheets: tuple[WorkbookSheet, ...],
    registry: Mapping[str, ProgramIdentity],
) -> tuple[WaitTime, ...]:
    _validate_contract_fields(metric.sheet, _WAIT_TIME_FIELDS, context="Wait time")
    positions, rows = _validated_sheet_rows(source, metric.sheet, sheets)
    wait_times: list[WaitTime] = []
    seen: set[str] = set()
    for row_index, row in enumerate(rows, start=1):
        context = _context(source, metric.sheet.name, row_index)
        if _text(_row_value(row, positions, "ORG"), field="ORG", context=context) != "KI":
            raise PatientJourneyParseError(f"{context}: ORG must be 'KI'.")
        _, _, key = _program_key(
            _row_value(row, positions, "CTR_CD"),
            _row_value(row, positions, "CTR_TY"),
            context=context,
        )
        _validate_registered_key(key, registry, context)
        if key in seen:
            raise PatientJourneyParseError(f"{context}: duplicate wait-time row {key!r}.")
        seen.add(key)
        _validate_publication_date(
            _row_value(row, positions, "RELEASE_DATE"),
            source=source,
            field="RELEASE_DATE",
            context=context,
        )
        months, raw = _wait_time_value(_row_value(row, positions, "TTT_25_C"), context=context)
        wait_times.append(
            WaitTime(
                program_key=key,
                release_code=source.release_code,
                measurement_start=metric.measurement_start,
                measurement_end=metric.measurement_end,
                follow_up_end=metric.follow_up_end,
                months_25th_percentile=months,
                raw_value=raw,
            )
        )
    wait_times.sort(key=lambda wait_time: wait_time.program_key)
    return tuple(wait_times)


def parse_patient_journey_workbook(
    source: SourceRecord,
    methodology: ReleaseMethodology,
    sheets: tuple[WorkbookSheet, ...],
) -> ParsedPatientJourneyRelease:
    """Parse target and access metrics without joining on program names."""
    if source.release_code != methodology.release_code:
        raise PatientJourneyParseError("Source and methodology release codes disagree.")
    if (
        source.published_value != methodology.published_value
        or source.published_precision != methodology.published_precision
    ):
        raise PatientJourneyParseError("Source and methodology publication values disagree.")
    identities = _parse_identities(source, methodology, sheets)
    registry = {identity.program_key: identity for identity in identities}
    return ParsedPatientJourneyRelease(
        release_code=source.release_code,
        identities=identities,
        outcomes=_parse_outcomes(source, methodology.metric("patient_outcome"), sheets, registry),
        transplant_rates=_parse_transplant_rates(
            source, methodology.metric("transplant_rate"), sheets, registry
        ),
        wait_times=_parse_wait_times(source, methodology.metric("wait_time"), sheets, registry),
    )


def parse_cached_patient_journey_source(
    source: SourceRecord,
    methodology: ReleaseMethodology,
    cache_dir: Path,
) -> ParsedPatientJourneyRelease:
    """Parse one checksum-verified cached workbook without extracting it."""
    payload = load_workbook_payload(source, cache_dir)
    return parse_patient_journey_workbook(source, methodology, read_workbook_sheets(payload))


def inspect_patient_journey_cache(
    manifest: DataSourceManifest,
    ledger: MethodologyLedger,
    cache_dir: Path,
) -> tuple[PatientJourneyInventoryEntry, ...]:
    """Read and validate all pinned v2 source contracts without writing artifacts."""
    entries: list[PatientJourneyInventoryEntry] = []
    for source in manifest.sources:
        parsed = parse_cached_patient_journey_source(
            source, ledger.release(source.release_code), cache_dir
        )
        entries.append(
            PatientJourneyInventoryEntry(
                release_code=source.release_code,
                identity_rows=len(parsed.identities),
                outcome_rows=len(parsed.outcomes),
                transplant_rate_rows=len(parsed.transplant_rates),
                wait_time_rows=len(parsed.wait_times),
            )
        )
    return tuple(entries)
