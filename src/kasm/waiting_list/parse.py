"""Read annual Table B1 events without changing published counts or report versions.

Each record represents one program and calendar year. The two calendar years are
supplied from separately verified report evidence, never from the V1 offer cohort.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from kasm.config import PublishedPrecision, SourceRecord
from kasm.data.parse import ParseError, WorkbookSheet, _count, _is_blank_row

REMOVAL_FIELDS = (
    "REMTXC",
    "REMTXL",
    "REMTXOC",
    "REMTFER",
    "REMDIED",
    "REMDET",
    "REMREC",
    "REMOTH",
)
_LABELS = {
    "ADDCEN": "New Listings",
    "END": "On waitlist at end",
    "REMDET": "Deteriorated",
    "REMDIED": "Died",
    "REMOTH": "Other Reasons",
    "REMREC": "Recovered",
    "REMTFER": "Transferred to another center",
    "REMTXC": "Received deceased donor tx",
    "REMTXL": "Received living donor tx",
    "REMTXOC": "Transplanted at another center",
    "ST": "On waitlist at start",
}
_IDENTITY_LABELS = {
    "ENTIRE_NAME": "Center Name",
    "CTR_CD": "Center Code",
    "CTR_TY": "Center Type",
    "RELEASE_DATE": "Release Date",
    "ORG": "Organ",
}
_EXPECTED_LABELS = _IDENTITY_LABELS | {
    f"WLA_{field}_{suffix}": label
    for field, label in _LABELS.items()
    for suffix in ("NC1", "NC2", "PCZ", "PRZ", "PUZ")
}


@dataclass(frozen=True)
class AnnualRecord:
    """Published registration/event counts; derived differences are calculations."""

    program_key: str
    release_code: str
    year: int
    start: int | None
    end: int | None
    additions: int | None
    removals: tuple[int | None, ...]
    published_value: str
    published_precision: PublishedPrecision
    source_url: str
    source_sha256: str

    def __post_init__(self) -> None:
        if len(self.removals) != len(REMOVAL_FIELDS):
            raise ParseError("Annual record must contain the eight exclusive removal categories.")
        for value in (self.start, self.end, self.additions, *self.removals):
            if value is not None and (type(value) is not int or value < 0):
                raise ParseError("Annual record counts must be nonnegative integers or missing.")

    @property
    def growth(self) -> int | None:
        """Calculate ending minus starting registrations, retaining unknown counts."""
        return None if self.start is None or self.end is None else self.end - self.start

    @property
    def removal_total(self) -> int | None:
        """Sum the eight source-defined exclusive removal categories when complete."""
        if any(value is None for value in self.removals):
            return None
        return sum(value for value in self.removals if value is not None)

    @property
    def residual(self) -> int | None:
        """Retain unexplained ending-count differences; zero means exact accounting."""
        growth, removals = self.growth, self.removal_total
        if growth is None or removals is None or self.additions is None:
            return None
        return growth - self.additions + removals

    @property
    def clean(self) -> bool:
        """Require all counts and exact integer accounting for decomposition."""
        return self.residual == 0


@dataclass(frozen=True)
class Revision:
    """Compare one later published version with the retained earliest version."""

    program_key: str
    year: int
    canonical_release: str
    later_release: str
    canonical: AnnualRecord | None
    later: AnnualRecord | None
    changed_fields: tuple[str, ...]


def _header(sheet: WorkbookSheet, context: str) -> dict[str, int]:
    if len(sheet.rows) < 3:
        raise ParseError(f"{context}: Table B1 must contain machine fields, descriptions and data.")
    headers = sheet.rows[0]
    if (
        sheet.column_count != len(_EXPECTED_LABELS)
        or len(headers) != len(_EXPECTED_LABELS)
        or set(headers) != set(_EXPECTED_LABELS)
    ):
        raise ParseError(
            f"{context}: Table B1 machine fields changed; review category exclusivity."
        )
    positions = {str(field): index for index, field in enumerate(headers)}
    descriptions = sheet.rows[1]
    if len(descriptions) != len(headers):
        raise ParseError(f"{context}: Table B1 description row width changed.")
    for field, label in _EXPECTED_LABELS.items():
        if descriptions[positions[field]] != label:
            raise ParseError(f"{context}: {field} description changed; review its definition.")
    return positions


def _publication(value: object, source: SourceRecord, context: str) -> None:
    if isinstance(value, datetime):
        observed = value.date()
    elif isinstance(value, date):
        observed = value
    else:
        raise ParseError(f"{context}: RELEASE_DATE must contain a workbook date.")
    if source.published_precision == "month":
        agrees = observed.isoformat()[:7] == source.published_value
    else:
        # The existing verified loader exposes historical timezone/day offsets.
        agrees = abs(observed - date.fromisoformat(source.published_value)) <= timedelta(days=1)
    if not agrees:
        raise ParseError(f"{context}: RELEASE_DATE disagrees with source publication.")


def _identity(row: tuple[object, ...], positions: dict[str, int], context: str) -> str:
    parts = []
    for field, pattern in (("CTR_CD", r"[A-Z0-9]{4}"), ("CTR_TY", r"[A-Z0-9]+")):
        value = row[positions[field]]
        if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
            raise ParseError(f"{context}: invalid {field} program identity.")
        parts.append(value)
    if row[positions["ORG"]] != "KI":
        raise ParseError(f"{context}: ORG must identify kidney (KI).")
    return ":".join(parts)


def _annual_record(
    row: tuple[object, ...],
    positions: dict[str, int],
    source: SourceRecord,
    program_key: str,
    year: int,
    suffix: str,
    context: str,
) -> AnnualRecord:
    counts = {
        field: _count(
            row[positions[f"WLA_{field}_{suffix}"]], field=f"WLA_{field}_{suffix}", context=context
        )
        for field in _LABELS
    }
    return AnnualRecord(
        program_key=program_key,
        release_code=source.release_code,
        year=year,
        start=counts["ST"],
        end=counts["END"],
        additions=counts["ADDCEN"],
        removals=tuple(counts[field] for field in REMOVAL_FIELDS),
        published_value=source.published_value,
        published_precision=source.published_precision,
        source_url=source.url,
        source_sha256=source.download_sha256,
    )


def parse_release(
    source: SourceRecord,
    sheets: tuple[WorkbookSheet, ...],
    years: tuple[int, int],
) -> tuple[AnnualRecord, ...]:
    """Validate the complete Table B1 schema and parse its two verified calendar years."""
    if len(years) != 2 or any(type(year) is not int for year in years) or years[1] != years[0] + 1:
        raise ParseError("Table B1 requires two distinct consecutive calendar years in order.")
    tables = [sheet for sheet in sheets if sheet.name == "Table B1"]
    context = f"Release {source.release_code}"
    if len(tables) != 1:
        raise ParseError(f"{context}: expected exactly one Table B1 sheet.")
    sheet = tables[0]
    positions = _header(sheet, context)
    records: list[AnnualRecord] = []
    seen: set[str] = set()
    for row_number, row in enumerate(sheet.rows[2:], start=3):
        if _is_blank_row(row):
            continue
        row_context = f"{context}, row {row_number}"
        if len(row) != len(positions):
            raise ParseError(f"{row_context}: row width does not match machine fields.")
        program_key = _identity(row, positions, row_context)
        if program_key in seen:
            raise ParseError(f"{row_context}: duplicate program {program_key}.")
        seen.add(program_key)
        _publication(row[positions["RELEASE_DATE"]], source, row_context)
        records.extend(
            _annual_record(row, positions, source, program_key, year, suffix, row_context)
            for year, suffix in zip(years, ("NC1", "NC2"), strict=True)
        )
    if not records:
        raise ParseError(f"{context}: Table B1 contains no program records.")
    return tuple(sorted(records, key=lambda record: (record.program_key, record.year)))


def _changed_fields(first: AnnualRecord | None, later: AnnualRecord | None) -> tuple[str, ...]:
    if first is None or later is None:
        return ("program_presence",)
    changed = [
        field
        for field in ("start", "end", "additions")
        if getattr(first, field) != getattr(later, field)
    ]
    changed.extend(
        field
        for field, old, new in zip(REMOVAL_FIELDS, first.removals, later.removals, strict=True)
        if old != new
    )
    return tuple(changed)


def select_vintages(
    records: tuple[AnnualRecord, ...], release_order: tuple[str, ...]
) -> tuple[tuple[AnnualRecord, ...], tuple[Revision, ...]]:
    """Choose one earliest release per year globally, preserving all later comparisons.

    A program absent from that year's chosen release stays absent even when a later
    version reports it. Revision comparisons include unchanged counts and missing programs.
    """
    if len(set(release_order)) != len(release_order):
        raise ParseError("Vintage release order contains duplicate releases.")
    order = {release: index for index, release in enumerate(release_order)}
    grouped: dict[int, dict[str, dict[str, AnnualRecord]]] = {}
    publication: dict[str, str] = {}
    for record in records:
        if record.release_code not in order:
            raise ParseError(f"Unknown vintage release {record.release_code}.")
        old_date = publication.setdefault(record.release_code, record.published_value)
        if old_date != record.published_value:
            raise ParseError("A release has inconsistent publication dates.")
        programs = grouped.setdefault(record.year, {}).setdefault(record.release_code, {})
        if record.program_key in programs:
            raise ParseError("Duplicate program-year in the same release vintage.")
        programs[record.program_key] = record
    observed_dates = [publication[release] for release in release_order if release in publication]
    if observed_dates != sorted(observed_dates) or len(set(observed_dates)) != len(observed_dates):
        raise ParseError("Vintage release order must follow distinct publication dates.")
    selected: list[AnnualRecord] = []
    revisions: list[Revision] = []
    for year, releases in sorted(grouped.items()):
        sorted_releases = sorted(releases, key=order.__getitem__)
        earliest = sorted_releases[0]
        canonical = releases[earliest]
        selected.extend(canonical.values())
        for later_release in sorted_releases[1:]:
            later = releases[later_release]
            revisions.extend(
                Revision(
                    key,
                    year,
                    earliest,
                    later_release,
                    canonical.get(key),
                    later.get(key),
                    _changed_fields(canonical.get(key), later.get(key)),
                )
                for key in sorted(canonical.keys() | later.keys())
            )
    return tuple(sorted(selected, key=lambda record: (record.year, record.program_key))), tuple(
        revisions
    )
