"""Schema-aware parsing for pinned SRTR offer-acceptance workbooks."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal, cast
from zipfile import ZipFile

import xlrd  # type: ignore[import-untyped]

from kasm.config import DataSourceManifest, PublishedPrecision, SourceRecord
from kasm.data.cache import verify_source_file

OfferGroup = Literal["overall", "low", "medium", "high", "hard-to-place"]

_CENTER_CODE = re.compile(r"^[A-Z0-9]{4}$")
_MISSING_STRINGS = frozenset({"", "-", "--", ".", "NA", "N/A", "NULL"})
_GROUP_PREFIXES: tuple[tuple[OfferGroup, str], ...] = (
    ("overall", "OA_OVERALL"),
    ("low", "OA_LOWRISK"),
    ("medium", "OA_MEDIUMRISK"),
    ("high", "OA_HIGHRISK"),
    ("hard-to-place", "OA_HARDTOPLACE100"),
)
_GROUP_ORDER = {group: index for index, (group, _) in enumerate(_GROUP_PREFIXES)}
_IDENTITY_COLUMNS = ("ENTIRE_NAME", "CTR_CD", "CTR_TY", "OAR_cohort_start", "OAR_cohort_end")
_MEASURE_SUFFIXES = (
    "OFFERS_CENTER",
    "ACCEPTS_CENTER",
    "EXP_ACCEPTS_CENTER",
    "HR_MN_CENTER",
    "HR_LB_CENTER",
    "HR_UB_CENTER",
)
_PARSER_REQUIRED_COLUMNS = _IDENTITY_COLUMNS + tuple(
    f"{prefix}_{suffix}" for _, prefix in _GROUP_PREFIXES for suffix in _MEASURE_SUFFIXES
)


class ParseError(ValueError):
    """Raised when a workbook violates the frozen source or scientific contract."""


@dataclass(frozen=True)
class WorkbookSheet:
    """Small adapter-neutral representation of one workbook sheet."""

    name: str
    rows: tuple[tuple[object, ...], ...]
    column_count: int


@dataclass(frozen=True)
class ProgramSignal:
    """One center-level published signal at program-year and offer-group grain."""

    program_key: str
    center_code: str
    center_type: str
    center_name: str
    release_code: str
    published_value: str
    published_precision: PublishedPrecision
    cohort_year: int
    cohort_start: date
    cohort_end: date
    offer_group: OfferGroup
    offers: int | None
    acceptances: int | None
    expected_acceptances: float | None
    oar_mean: float | None
    oar_lower: float | None
    oar_upper: float | None
    source_url: str
    source_sha256: str


@dataclass(frozen=True)
class ParsedRelease:
    """Validated parser result for one immutable source release."""

    release_code: str
    cohort_year: int
    sheet_name: str
    source_rows: int
    source_columns: int
    signals: tuple[ProgramSignal, ...]


@dataclass(frozen=True)
class SourceInventoryEntry:
    """Machine-readable evidence that one source satisfies the parser contract."""

    release_code: str
    cohort_year: int
    sheet_name: str
    source_rows: int
    source_columns: int
    signal_rows: int


def _context(source: SourceRecord, row_number: int | None = None) -> str:
    context = f"Release {source.release_code!r}"
    return f"{context}, worksheet row {row_number}" if row_number is not None else context


def load_workbook_payload(source: SourceRecord, cache_dir: Path) -> bytes:
    """Return verified XLS bytes, reading ZIP members in memory without extraction."""
    source_path = cache_dir / source.cache_filename
    issues = verify_source_file(source_path, source)
    if issues:
        details = "; ".join(issue.message for issue in issues)
        raise ParseError(f"{_context(source)} failed cache verification: {details}")
    if source.transport == "xls":
        return source_path.read_bytes()
    if source.member_path is None:
        raise ParseError(f"{_context(source)} has no configured ZIP member path.")
    with ZipFile(source_path) as archive:
        return archive.read(source.member_path)


def _cell_value(book: xlrd.book.Book, cell: xlrd.sheet.Cell) -> object:
    if cell.ctype in {xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK}:
        return None
    if cell.ctype == xlrd.XL_CELL_DATE:
        return xlrd.xldate_as_datetime(cell.value, book.datemode)
    if cell.ctype == xlrd.XL_CELL_BOOLEAN:
        return bool(cell.value)
    if cell.ctype == xlrd.XL_CELL_ERROR:
        return None
    return cast(object, cell.value)


def read_workbook_sheets(payload: bytes) -> tuple[WorkbookSheet, ...]:
    """Read legacy XLS bytes into an adapter-neutral sheet representation."""
    try:
        book = xlrd.open_workbook(file_contents=payload, on_demand=True)
    except xlrd.XLRDError as error:
        raise ParseError(f"Could not open XLS workbook: {error}.") from error

    sheets: list[WorkbookSheet] = []
    try:
        for sheet_name in book.sheet_names():
            sheet = book.sheet_by_name(sheet_name)
            rows = tuple(
                tuple(
                    _cell_value(book, sheet.cell(row_index, column_index))
                    for column_index in range(sheet.ncols)
                )
                for row_index in range(sheet.nrows)
            )
            sheets.append(WorkbookSheet(name=sheet.name, rows=rows, column_count=sheet.ncols))
    finally:
        book.release_resources()
    return tuple(sheets)


def _as_header(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _find_header(
    source: SourceRecord,
    sheet: WorkbookSheet,
    required_columns: tuple[str, ...],
) -> tuple[int, dict[str, int]]:
    required = set(required_columns)
    for row_index, row in enumerate(sheet.rows[:10]):
        headers = tuple(_as_header(value) for value in row)
        if not required.issubset(headers):
            continue
        positions: dict[str, int] = {}
        for column_index, header in enumerate(headers):
            if not header:
                continue
            if header in positions:
                raise ParseError(
                    f"{_context(source)} contains duplicate machine column {header!r}."
                )
            positions[header] = column_index
        return row_index, positions
    missing_preview = ", ".join(required_columns[:5])
    raise ParseError(
        f"{_context(source)} could not find a machine-header row containing required fields "
        f"such as {missing_preview}."
    )


def _is_blank_row(row: tuple[object, ...]) -> bool:
    return all(value is None or (isinstance(value, str) and not value.strip()) for value in row)


def _is_description_row(row: tuple[object, ...], positions: dict[str, int]) -> bool:
    """Recognize the documented human-label row immediately below machine fields."""
    return (
        _value(row, positions, "CTR_CD") == "Center ID"
        and _value(row, positions, "CTR_TY") == "Center Type"
    )


def _text(value: object, *, field: str, context: str, required: bool = True) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ParseError(f"{context}: {field} is missing.")
        return None
    if isinstance(value, bool):
        raise ParseError(f"{context}: {field} must be text, not boolean.")
    if isinstance(value, float) and value.is_integer():
        result = str(int(value))
    else:
        result = str(value).strip()
    if not result and required:
        raise ParseError(f"{context}: {field} is missing.")
    return result or None


def _number(value: object, *, field: str, context: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.upper() in _MISSING_STRINGS:
            return None
        try:
            result = float(stripped.replace(",", ""))
        except ValueError as error:
            raise ParseError(f"{context}: {field} must be numeric or missing.") from error
    elif isinstance(value, bool) or not isinstance(value, int | float):
        raise ParseError(f"{context}: {field} must be numeric or missing.")
    else:
        result = float(value)
    if not math.isfinite(result):
        raise ParseError(f"{context}: {field} must be finite when reported.")
    return result


def _count(value: object, *, field: str, context: str) -> int | None:
    number = _number(value, field=field, context=context)
    if number is None:
        return None
    if not number.is_integer():
        raise ParseError(f"{context}: {field} must be a whole number.")
    result = int(number)
    if result < 0:
        raise ParseError(f"{context}: {field} cannot be negative.")
    return result


def _ratio(value: object, *, field: str, context: str) -> float | None:
    result = _number(value, field=field, context=context)
    if result is not None and result < 0:
        raise ParseError(f"{context}: {field} cannot be negative.")
    return result


def _cohort_date(
    value: object,
    *,
    source: SourceRecord,
    boundary: Literal["start", "end"],
    context: str,
) -> date:
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip()).date()
        except ValueError as error:
            raise ParseError(f"{context}: cohort {boundary} is not a valid date.") from error
    else:
        raise ParseError(f"{context}: cohort {boundary} is missing or not a valid date.")

    normalized = (
        date(source.cohort_year, 1, 1) if boundary == "start" else date(source.cohort_year, 12, 31)
    )
    if abs(parsed - normalized) > timedelta(days=2):
        raise ParseError(
            f"{context}: cohort {boundary} {parsed.isoformat()} does not match full calendar "
            f"year {source.cohort_year}."
        )
    return normalized


def _value(row: tuple[object, ...], positions: dict[str, int], field: str) -> object:
    position = positions[field]
    return row[position] if position < len(row) else None


def _validate_measure(
    *,
    source: SourceRecord,
    row_number: int,
    offer_group: OfferGroup,
    offers: int | None,
    acceptances: int | None,
    expected_acceptances: float | None,
    oar_mean: float | None,
    oar_lower: float | None,
    oar_upper: float | None,
) -> None:
    context = f"{_context(source, row_number)} ({offer_group})"
    if expected_acceptances is not None and expected_acceptances < 0:
        raise ParseError(f"{context}: expected acceptances cannot be negative.")
    ratios = (oar_mean, oar_lower, oar_upper)
    if offers == 0 and (
        acceptances != 0 or expected_acceptances != 0 or any(value is not None for value in ratios)
    ):
        raise ParseError(
            f"{context}: zero offers require zero accepts and expected accepts with null ratio."
        )
    if offers is not None and acceptances is not None and acceptances > offers:
        raise ParseError(f"{context}: acceptances cannot exceed offers.")
    if offers is not None and expected_acceptances is not None and expected_acceptances > offers:
        raise ParseError(f"{context}: expected acceptances cannot exceed offers.")

    if any(value is None for value in ratios) and any(value is not None for value in ratios):
        raise ParseError(
            f"{context}: credible interval fields must be all reported or all missing."
        )
    if all(value is not None for value in ratios):
        mean = cast(float, oar_mean)
        lower = cast(float, oar_lower)
        upper = cast(float, oar_upper)
        if not lower <= mean <= upper:
            raise ParseError(f"{context}: credible interval must satisfy lower <= mean <= upper.")

    if offer_group == "overall" and any(
        value is None for value in (offers, acceptances, expected_acceptances, *ratios)
    ):
        raise ParseError(f"{context}: overall center fields must all be reported.")


def _parse_program(
    source: SourceRecord,
    positions: dict[str, int],
    row: tuple[object, ...],
    row_number: int,
) -> tuple[ProgramSignal, ...]:
    context = _context(source, row_number)
    center_code = _text(_value(row, positions, "CTR_CD"), field="center code", context=context)
    assert center_code is not None
    center_code = center_code.upper()
    if _CENTER_CODE.fullmatch(center_code) is None:
        raise ParseError(f"{context}: center code must match [A-Z0-9]{{4}}.")
    center_type = _text(_value(row, positions, "CTR_TY"), field="center type", context=context)
    assert center_type is not None
    center_name = (
        _text(
            _value(row, positions, "ENTIRE_NAME"),
            field="center name",
            context=context,
            required=False,
        )
        or f"Program {center_code}"
    )
    cohort_start = _cohort_date(
        _value(row, positions, "OAR_cohort_start"),
        source=source,
        boundary="start",
        context=context,
    )
    cohort_end = _cohort_date(
        _value(row, positions, "OAR_cohort_end"),
        source=source,
        boundary="end",
        context=context,
    )
    program_key = f"{center_code}:{center_type}"

    signals: list[ProgramSignal] = []
    for offer_group, prefix in _GROUP_PREFIXES:
        measure_context = f"{context} ({offer_group})"
        offers = _count(
            _value(row, positions, f"{prefix}_OFFERS_CENTER"),
            field="offers",
            context=measure_context,
        )
        acceptances = _count(
            _value(row, positions, f"{prefix}_ACCEPTS_CENTER"),
            field="acceptances",
            context=measure_context,
        )
        expected_acceptances = _number(
            _value(row, positions, f"{prefix}_EXP_ACCEPTS_CENTER"),
            field="expected acceptances",
            context=measure_context,
        )
        oar_mean = _ratio(
            _value(row, positions, f"{prefix}_HR_MN_CENTER"),
            field="OAR mean",
            context=measure_context,
        )
        oar_lower = _ratio(
            _value(row, positions, f"{prefix}_HR_LB_CENTER"),
            field="OAR lower bound",
            context=measure_context,
        )
        oar_upper = _ratio(
            _value(row, positions, f"{prefix}_HR_UB_CENTER"),
            field="OAR upper bound",
            context=measure_context,
        )
        _validate_measure(
            source=source,
            row_number=row_number,
            offer_group=offer_group,
            offers=offers,
            acceptances=acceptances,
            expected_acceptances=expected_acceptances,
            oar_mean=oar_mean,
            oar_lower=oar_lower,
            oar_upper=oar_upper,
        )
        signals.append(
            ProgramSignal(
                program_key=program_key,
                center_code=center_code,
                center_type=center_type,
                center_name=center_name,
                release_code=source.release_code,
                published_value=source.published_value,
                published_precision=source.published_precision,
                cohort_year=source.cohort_year,
                cohort_start=cohort_start,
                cohort_end=cohort_end,
                offer_group=offer_group,
                offers=offers,
                acceptances=acceptances,
                expected_acceptances=expected_acceptances,
                oar_mean=oar_mean,
                oar_lower=oar_lower,
                oar_upper=oar_upper,
                source_url=source.url,
                source_sha256=source.download_sha256,
            )
        )
    return tuple(signals)


def parse_offer_acceptance_workbook(
    manifest: DataSourceManifest,
    source: SourceRecord,
    sheets: tuple[WorkbookSheet, ...],
) -> ParsedRelease:
    """Validate and reshape one workbook's center offer-acceptance table."""
    missing_contract_fields = set(_PARSER_REQUIRED_COLUMNS) - set(manifest.required_machine_columns)
    if missing_contract_fields:
        preview = ", ".join(sorted(missing_contract_fields)[:5])
        raise ParseError(
            f"{_context(source)} manifest machine-column contract is incomplete: {preview}."
        )
    sheet = next((candidate for candidate in sheets if candidate.name == source.sheet_name), None)
    if sheet is None:
        available = ", ".join(candidate.name for candidate in sheets)
        raise ParseError(
            f"{_context(source)} is missing configured sheet {source.sheet_name!r}; "
            f"available sheets: {available}."
        )
    if sheet.column_count != source.expected_columns:
        raise ParseError(
            f"{_context(source)} column count changed: expected {source.expected_columns}, "
            f"found {sheet.column_count}."
        )
    header_index, positions = _find_header(source, sheet, manifest.required_machine_columns)
    rows_after_header = tuple(
        row for row in sheet.rows[header_index + 1 :] if not _is_blank_row(row)
    )
    if rows_after_header and _is_description_row(rows_after_header[0], positions):
        rows_after_header = rows_after_header[1:]
    data_rows = rows_after_header
    if len(data_rows) != source.expected_rows:
        raise ParseError(
            f"{_context(source)} row count changed: expected {source.expected_rows}, "
            f"found {len(data_rows)}."
        )

    signals: list[ProgramSignal] = []
    seen_program_keys: set[str] = set()
    for row_offset, row in enumerate(data_rows, start=header_index + 2):
        program_signals = _parse_program(source, positions, row, row_offset)
        program_key = program_signals[0].program_key
        if program_key in seen_program_keys:
            raise ParseError(
                f"{_context(source, row_offset)} duplicates program key {program_key!r}."
            )
        seen_program_keys.add(program_key)
        signals.extend(program_signals)

    signals.sort(key=lambda signal: (signal.program_key, _GROUP_ORDER[signal.offer_group]))
    return ParsedRelease(
        release_code=source.release_code,
        cohort_year=source.cohort_year,
        sheet_name=sheet.name,
        source_rows=len(data_rows),
        source_columns=sheet.column_count,
        signals=tuple(signals),
    )


def parse_cached_source(
    manifest: DataSourceManifest, source: SourceRecord, cache_dir: Path
) -> ParsedRelease:
    """Load and parse one source from an already verified immutable cache."""
    payload = load_workbook_payload(source, cache_dir)
    return parse_offer_acceptance_workbook(manifest, source, read_workbook_sheets(payload))


def inspect_source_cache(
    manifest: DataSourceManifest, cache_dir: Path
) -> tuple[SourceInventoryEntry, ...]:
    """Parse all configured releases and return deterministic inventory evidence."""
    entries: list[SourceInventoryEntry] = []
    for source in manifest.sources:
        release = parse_cached_source(manifest, source, cache_dir)
        entries.append(
            SourceInventoryEntry(
                release_code=release.release_code,
                cohort_year=release.cohort_year,
                sheet_name=release.sheet_name,
                source_rows=release.source_rows,
                source_columns=release.source_columns,
                signal_rows=len(release.signals),
            )
        )
    return tuple(entries)
