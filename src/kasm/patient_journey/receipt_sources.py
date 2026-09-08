"""Bind the receipt study's dates to independently saved report evidence."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from kasm.config import DataSourceManifest, SourceRecord, load_data_source_manifest
from kasm.data.parse import (
    ParsedRelease,
    WorkbookSheet,
    load_workbook_payload,
    parse_offer_acceptance_workbook,
    read_workbook_sheets,
)
from kasm.patient_journey.ledger import MetricMethodology, ReleaseMethodology, SheetContract
from kasm.patient_journey.parse import (
    ProgramIdentity,
    TransplantRate,
    WaitTime,
    _parse_identities,
    _parse_transplant_rates,
    _parse_wait_times,
    _program_key,
    _row_value,
    _validate_publication_date,
    _validated_sheet_rows,
)
from kasm.patient_journey.receipt_accounting import (
    ARITHMETIC_TOLERANCE,
    DECEASED_FIELDS,
    LIVING_FIELDS,
    RECEIPT_FIELDS,
    ReceiptValues,
    parse_receipt_values,
)
from kasm.patient_journey.receipt_config import ANALYSIS_ID, ReceiptError

Pair = tuple[str, str]
Fold = tuple[Pair, tuple[Pair, ...]]
_DATE_TEXT = r"(\d{2}/\d{2}/\d{4})"
FIXED_RELEASES = ("1905", "2105", "2205", "2305", "2405", "2505", "2605")
FIXED_PAIRS: tuple[Pair, ...] = (
    ("1905", "2205"),
    ("2105", "2405"),
    ("2205", "2505"),
    ("2305", "2605"),
)
FIXED_FOLDS: tuple[Fold, ...] = (
    (("2205", "2505"), (("1905", "2205"),)),
    (("2305", "2605"), (("1905", "2205"),)),
)
BINDING_FIELDS = ("SAL_N_C", *DECEASED_FIELDS, *LIVING_FIELDS, "SAL_TOTFTX_C18", "SAL_TOTTX_C18")
_DONOR_DESCRIPTIONS = (
    "Functioning (alive)",
    "Failed-Retransplanted (alive)",
    "Failed-alive not retransplanted",
    "Died",
    "Status Yet Unknown",
)
OUTCOME_DESCRIPTIONS = {
    **dict(zip(DECEASED_FIELDS, _DONOR_DESCRIPTIONS, strict=True)),
    **dict(zip(LIVING_FIELDS, _DONOR_DESCRIPTIONS, strict=True)),
    "SAL_N_C": "N",
    "SAL_TOTFTX_C18": "Functioning tx (alive)",
    "SAL_TOTTX_C18": "Removed for tx",
    "SAL_TOTAL_C18": "Total",
    "SAL_LOST_C18": "Lost or Transferred",
    "SAL_REFTX_C18": "Refused transplant (status unknown)",
    "SAL_REMDET_C18": "Condition Worsened (status unknown)",
    "SAL_REMOTH_C18": "Other",
    "SAL_REMREC_C18": "Condition improved (status unknown)",
    "SAL_WLDIED_C18": "Died on waitlist",
    "SAL_WLLIVE_C18": "Alive on waitlist",
}


@dataclass(frozen=True)
class SourcePeriods:
    """Source listing dates and a conservative bound for all 18-month observations."""

    listing_start: date
    listing_end: date
    outcome_follow_up_bound: date
    wait_start: date
    wait_end: date
    wait_follow_up_end: date

    def require_listing_dates(self, start: date, end: date) -> None:
        """Reject a configuration that disagrees with the independent report."""
        if (start, end) != (self.listing_start, self.listing_end):
            raise ReceiptError("Configured listing dates disagree with source-period evidence.")


@dataclass(frozen=True)
class ReceiptOutcome:
    """One program's derived receipt percentage; all dates come from verified evidence."""

    program_key: str
    values: ReceiptValues


@dataclass(frozen=True)
class ReceiptRelease:
    """Program directory, receipt outcomes and earlier access/acceptance measurements."""

    source: SourceRecord
    periods: SourcePeriods
    identities: tuple[ProgramIdentity, ...]
    outcomes: tuple[ReceiptOutcome, ...]
    transplant_rates: tuple[TransplantRate, ...]
    wait_times: tuple[WaitTime, ...]
    acceptance: ParsedRelease
    methodology: ReleaseMethodology


@dataclass(frozen=True)
class ReceiptSources:
    """The source-feasible release set and exact forward-in-time comparisons."""

    releases: tuple[ReceiptRelease, ...]
    pairs: tuple[Pair, ...]
    folds: tuple[Fold, ...]
    exclusions: Mapping[str, object]
    config_sha256: str


def _mapping(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ReceiptError(f"{context} must be a mapping with named fields.")
    return cast(dict[str, object], value)


def _string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReceiptError(f"{context} must be nonempty text.")
    return value


def _sequence(value: object, context: str) -> list[object]:
    if not isinstance(value, list) or not value:
        raise ReceiptError(f"{context} must be a nonempty list.")
    return value


def read_source_evidence(pin: Mapping[str, object], *, repository_root: Path) -> str:
    """Verify saved text bytes before reading dates; no network or PDF subprocess runs."""
    content = _fingerprinted_bytes(
        pin,
        repository_root=repository_root,
        prefix=Path("data/receipt-study/source-research"),
        suffix="txt",
        maximum_bytes=1_000_000,
    )
    try:
        return content.decode("utf-8")
    except UnicodeError as exc:
        raise ReceiptError("Cannot read required source-period evidence.") from exc


def _fingerprinted_bytes(
    pin: Mapping[str, object],
    *,
    repository_root: Path,
    prefix: Path,
    suffix: str,
    maximum_bytes: int,
) -> bytes:
    path = Path(_string(pin.get("path"), "Source evidence path"))
    if (
        path.is_absolute()
        or path.drive
        or ".." in path.parts
        or path.parent != prefix
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\." + suffix, path.name) is None
    ):
        raise ReceiptError("Source evidence path must stay in its isolated input directory.")
    size_pin, hash_pin = pin.get("bytes"), pin.get("sha256")
    if (
        set(pin) != {"path", "bytes", "sha256"}
        or type(size_pin) is not int
        or not 0 < size_pin <= maximum_bytes
        or not isinstance(hash_pin, str)
        or re.fullmatch(r"[0-9a-f]{64}", hash_pin) is None
    ):
        raise ReceiptError("Source evidence fingerprint needs a valid integer size and SHA-256.")
    root = repository_root.resolve()
    full = root / path
    for current in (full, *full.parents):
        if current == root:
            break
        if current.is_symlink() or current.is_junction():
            raise ReceiptError("Source evidence path cannot traverse filesystem links.")
    try:
        size = full.stat().st_size
        if size != size_pin:
            raise ReceiptError("Source evidence fingerprint size disagrees.")
        content = full.read_bytes()
        if len(content) != size_pin or sha256(content).hexdigest() != hash_pin:
            raise ReceiptError("Source evidence fingerprint changed; review the source copy.")
        return content
    except OSError as exc:
        raise ReceiptError("Cannot read required source-period evidence.") from exc


def _clean(text: str) -> str:
    return re.sub(r"^L\d+@P[\d-]+: ?", "", text, flags=re.MULTILINE)


def _source_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%m/%d/%Y").date()
    except ValueError as exc:
        raise ReceiptError("Source evidence contains an invalid date.") from exc


def _report_identity(text: str, program_key: str, published_value: str) -> None:
    if re.fullmatch(r"[A-Z0-9]{4}:[A-Z0-9]+", program_key) is None:
        raise ReceiptError("Source evidence identity needs a composite program key.")
    if re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", published_value) is None:
        raise ReceiptError("Source publication must preserve valid month or day precision.")
    try:
        date.fromisoformat(
            published_value + "-01" if len(published_value) == 7 else published_value
        )
    except ValueError as exc:
        raise ReceiptError("Source publication date is invalid.") from exc
    organ = re.findall(r"Transplant Program \(Organ\):\s*([^\r\n]+)", text)
    centers = re.findall(r"Center Code:\s*([A-Z0-9]{4})\b", text)
    if (
        not organ
        or any(value.strip() != "Kidney" for value in organ)
        or set(centers) != {program_key.split(":")[0]}
    ):
        raise ReceiptError("Source evidence identity must match the specific kidney program.")
    releases = re.findall(r"Release Date:\s*([A-Za-z]+ \d{1,2}, \d{4})", text)
    if not releases:
        raise ReceiptError("Source evidence lacks its report publication date.")
    try:
        days = {datetime.strptime(value, "%B %d, %Y").date().isoformat() for value in releases}
    except ValueError as exc:
        raise ReceiptError("Invalid source publication date.") from exc
    if len(days) != 1 or not next(iter(days)).startswith(published_value):
        raise ReceiptError("Report publication disagrees with its pinned workbook release.")


def parse_source_periods(
    outcome_text: str, wait_text: str, *, program_key: str, published_value: str
) -> SourcePeriods:
    """Read independent report dates, preserving the difference between dates and bounds."""
    outcome, wait = _clean(outcome_text), _clean(wait_text)
    _report_identity(outcome, program_key, published_value)
    _report_identity(wait, program_key, published_value)
    listing = re.findall(
        r"Candidates registered on waiting list between\s*"
        + _DATE_TEXT
        + r"\s*and\s*"
        + _DATE_TEXT,
        outcome,
    )
    if len(set(listing)) != 1 or not re.search(r"Months Since Listing\s*6\s*12\s*18", outcome):
        raise ReceiptError("Source listing period or 18-month horizon is missing or ambiguous.")
    start, end = (_source_date(value) for value in listing[0])
    if (start.month, start.day, end.month, end.day, end.year) != (7, 1, 6, 30, start.year + 1):
        raise ReceiptError("Source listing cohort must be one complete July-June year.")
    wait_matches = re.findall(
        r"Table B(?:9|10)\. Time to transplant for waiting list candidates[^\n]*\s*"
        r"Candidates registered on the waiting list between\s*"
        + _DATE_TEXT
        + r"\s*and\s*"
        + _DATE_TEXT,
        wait,
    )
    censor = re.findall(r"Censored on\s*" + _DATE_TEXT, wait)
    if len(set(wait_matches)) != 1 or len(set(censor)) != 1:
        raise ReceiptError("Source wait-time period or censor date is missing or ambiguous.")
    wait_start, wait_end = (_source_date(value) for value in wait_matches[0])
    wait_censor = _source_date(censor[0])
    if not wait_start < wait_end <= wait_censor:
        raise ReceiptError("Source wait-time dates are reversed.")
    return SourcePeriods(start, end, date(end.year + 1, 12, 31), wait_start, wait_end, wait_censor)


def _shape(raw: object) -> SheetContract:
    values = _mapping(raw, "Sheet shape")
    rows, columns = values.get("expected_rows"), values.get("expected_columns")
    if type(rows) is not int or type(columns) is not int or rows <= 0 or columns <= 0:
        raise ReceiptError("Sheet shape requires positive integer dimensions.")
    fields = tuple(
        _string(v, "Machine field")
        for v in _sequence(values.get("required_fields"), "Machine fields")
    )
    if set(values) != {"name", "expected_rows", "expected_columns", "required_fields"} or len(
        set(fields)
    ) != len(fields):
        raise ReceiptError("Sheet shape has extra settings or duplicate machine fields.")
    return SheetContract(_string(values.get("name"), "Sheet name"), rows, columns, fields)


def _methodology(
    entry: Mapping[str, object], source: SourceRecord, periods: SourcePeriods
) -> ReleaseMethodology:
    shapes = _mapping(entry.get("shapes"), "Release shapes")
    rate_dates = _sequence(entry.get("rate_dates"), "Transplant-rate dates")
    if len(rate_dates) != 2:
        raise ReceiptError("Transplant-rate dates require start and end.")
    rate_start, rate_end = (date.fromisoformat(_string(value, "Rate date")) for value in rate_dates)
    if not rate_start < rate_end:
        raise ReceiptError("Transplant-rate source dates are reversed.")
    url = _string(entry.get("source_url"), "Report URL")
    metrics = (
        MetricMethodology(
            "patient_outcome",
            _shape(shapes.get("outcome")),
            periods.listing_start,
            periods.listing_end,
            periods.outcome_follow_up_bound,
            url,
            ("Derived receipt from five published deceased-donor statuses.",),
            (),
            (),
        ),
        MetricMethodology(
            "transplant_rate",
            _shape(shapes.get("rate")),
            rate_start,
            rate_end,
            rate_end,
            source.url,
            ("Published all-candidate transplant rate and person-years.",),
            (),
            (),
        ),
        MetricMethodology(
            "wait_time",
            _shape(shapes.get("wait")),
            periods.wait_start,
            periods.wait_end,
            periods.wait_follow_up_end,
            url,
            ("Published 25th-percentile time to transplant.",),
            (),
            (),
        ),
    )
    return ReleaseMethodology(
        source.release_code,
        source.published_value,
        source.published_precision,
        source.url,
        source.download_sha256,
        _shape(shapes.get("identity")),
        metrics,
    )


def _receipt_rows(
    source: SourceRecord,
    methodology: ReleaseMethodology,
    sheets: tuple[WorkbookSheet, ...],
    registry: Mapping[str, ProgramIdentity],
    checks: Mapping[str, object],
    checked_program: str,
) -> tuple[ReceiptOutcome, ...]:
    _validate_checks(checks)
    contract = methodology.metric("patient_outcome").sheet
    if not set(
        (*RECEIPT_FIELDS, "SAL_TOTFTX_C18", "CTR_CD", "CTR_TY", "ORG", "RELEASE_DATE")
    ).issubset(contract.required_fields):
        raise ReceiptError("Receipt shape omits required accounting machine fields.")
    positions, raw_rows = _validated_sheet_rows(source, contract, sheets)
    _validate_descriptions(contract, sheets)
    outcomes: dict[str, ReceiptOutcome] = {}
    bound = False
    for row in raw_rows:
        values = {field: _row_value(row, positions, field) for field in positions}
        _, _, key = _program_key(
            values.get("CTR_CD"), values.get("CTR_TY"), context="Receipt outcome"
        )
        if key not in registry or key in outcomes or values.get("ORG") != "KI":
            raise ReceiptError("Receipt rows have a duplicate, unknown or wrong-organ program.")
        _validate_publication_date(
            values.get("RELEASE_DATE"),
            source=source,
            field="RELEASE_DATE",
            context="Receipt outcome",
        )
        parsed = parse_receipt_values(values)
        if key == checked_program:
            for field, raw_check in checks.items():
                check = _mapping(raw_check, "PDF/workbook check")
                observed, expected = values.get(field), check.get("source")
                observed_number = _binding_number(observed, allow_text=True)
                expected_number = _binding_number(expected)
                pinned_workbook = _binding_number(check.get("workbook"), allow_text=True)
                tolerance = 0.0 if field == "SAL_N_C" else 0.05 + ARITHMETIC_TOLERANCE
                if abs(observed_number - pinned_workbook) > ARITHMETIC_TOLERANCE:
                    raise ReceiptError(f"Source binding workbook value changed for {field}.")
                if abs(observed_number - expected_number) > tolerance:
                    raise ReceiptError(f"Source report and workbook disagree for {key} {field}.")
            bound = True
        outcomes[key] = ReceiptOutcome(key, parsed)
    if not bound:
        raise ReceiptError("Source report's program is absent from the workbook outcome table.")
    return tuple(outcomes[key] for key in sorted(outcomes))


def _binding_number(value: object, *, allow_text: bool = False) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float | str)
        or (isinstance(value, str) and not allow_text)
    ):
        raise ReceiptError("Source binding value must be finite numeric data.")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ReceiptError("Source binding value must be finite numeric data.") from exc
    if not math.isfinite(number) or number < 0:
        raise ReceiptError("Source binding value must be finite nonnegative data.")
    return number


def _validate_checks(checks: Mapping[str, object]) -> None:
    if set(checks) != set(BINDING_FIELDS):
        raise ReceiptError("Source binding requires all 13 fixed PDF/workbook checks.")
    for field, raw in checks.items():
        check = _mapping(raw, "Source binding check")
        if set(check) != {"source", "workbook", "matches"} or check.get("matches") is not True:
            raise ReceiptError("Source binding needs an explicitly successful complete check.")
        source = _binding_number(check.get("source"))
        workbook = _binding_number(check.get("workbook"), allow_text=True)
        if field == "SAL_N_C":
            if source <= 0 or not source.is_integer() or source != workbook:
                raise ReceiptError("Source binding SAL_N_C must be the same positive whole count.")
        elif source > 100 or workbook > 100 or abs(source - workbook) > 0.05 + ARITHMETIC_TOLERANCE:
            raise ReceiptError("Source binding percentages disagree within display rounding.")


def _validate_descriptions(contract: SheetContract, sheets: tuple[WorkbookSheet, ...]) -> None:
    selected = tuple(sheet for sheet in sheets if sheet.name == contract.name)
    if len(selected) != 1:
        raise ReceiptError("Receipt outcome sheet must be uniquely identified.")
    for index, row in enumerate(selected[0].rows[:10]):
        if set(OUTCOME_DESCRIPTIONS).issubset(row):
            if index + 1 >= len(selected[0].rows):
                break
            descriptions = selected[0].rows[index + 1]
            for field, expected in OUTCOME_DESCRIPTIONS.items():
                position = row.index(field)
                if position >= len(descriptions) or descriptions[position] != expected:
                    raise ReceiptError(f"Source description changed for {field}.")
            return
    raise ReceiptError("Source description row is missing from the receipt outcome sheet.")


def _report_values(text: str) -> dict[str, float]:
    """Read the center's 18-month column under each explicit donor heading."""
    cleaned = _clean(text)
    tables = re.findall(
        r"Table B(?:6|7)\. Waiting list candidate status after listing\s*"
        r"(.*?Total % with known functioning transplant \(alive\)[^\r\n]*)",
        cleaned,
        flags=re.DOTALL,
    )
    if len(tables) != 1:
        raise ReceiptError("Source report binding needs exactly one receipt table.")
    table = tables[0]
    count = re.findall(r"This Center\s*\(N=([\d,]+)\)", table)
    if len(count) != 1 or not re.search(r"6\s+12\s+18\s+6\s+12\s+18", table):
        raise ReceiptError("Source report binding lacks its listing denominator or column horizon.")
    living_heading = "Transplant (living donor from waiting list only) (%):"
    deceased_heading = "Transplant (deceased donor) (%):"
    if table.count(living_heading) != 1 or table.count(deceased_heading) != 1:
        raise ReceiptError("Source report binding lacks unambiguous donor headings.")
    living = table.split(living_heading)[1].split(deceased_heading)[0]
    deceased = table.split(deceased_heading)[1].split("Lost or Transferred")[0]
    result = {"SAL_N_C": float(count[0].replace(",", ""))}
    for section, fields in ((living, LIVING_FIELDS), (deceased, DECEASED_FIELDS)):
        for field, label in zip(fields, _DONOR_DESCRIPTIONS, strict=True):
            result[field] = _report_percent(section, label)
    for field, label in (
        ("SAL_TOTTX_C18", "Total % removed for transplant"),
        ("SAL_TOTFTX_C18", "Total % with known functioning transplant (alive)"),
    ):
        result[field] = _report_percent(table, label)
    return result


def _report_percent(section: str, label: str) -> float:
    rows = re.findall(r"^" + re.escape(label) + r"\**\s*([^\r\n]+)", section, re.MULTILINE)
    if len(rows) != 1:
        raise ReceiptError(f"Source report binding lacks one complete {label} row.")
    fields = rows[0].split()
    if len(fields) != 6:
        raise ReceiptError("Source report binding needs three center and three national columns.")
    numbers = [_binding_number(value, allow_text=True) for value in fields]
    if any(number > 100 for number in numbers):
        raise ReceiptError("Source report binding percentage exceeds 100.")
    return numbers[2]


def _load_release(
    entry: Mapping[str, object],
    source: SourceRecord,
    root: Path,
    cache_dir: Path,
    manifest: DataSourceManifest,
) -> ReceiptRelease:
    _validate_release_entry(entry, source)
    if entry.get("workbook_sha256") != (source.member_sha256 or source.download_sha256):
        raise ReceiptError(
            "Source binding workbook fingerprint disagrees with the source manifest."
        )
    key = _string(entry.get("program_key"), "Bound program")
    outcome = read_source_evidence(
        _mapping(entry.get("outcome_source"), "Outcome evidence"), repository_root=root
    )
    wait = read_source_evidence(
        _mapping(entry.get("wait_source"), "Wait evidence"), repository_root=root
    )
    _validate_evidence_origin(entry, outcome, wait, root)
    periods = parse_source_periods(
        outcome, wait, program_key=key, published_value=source.published_value
    )
    checks = _mapping(entry.get("checks"), "Source value checks")
    _validate_checks(checks)
    source_values = _report_values(outcome)
    for field, value in source_values.items():
        if value != _mapping(checks[field], "Source binding check").get("source"):
            raise ReceiptError(
                f"Source binding expected value disagrees with report text for {field}."
            )
    periods.require_listing_dates(
        _source_date(_string(entry.get("listing_start_source"), "Listing start")),
        _source_date(_string(entry.get("listing_end_source"), "Listing end")),
    )
    expected_wait = tuple(
        _source_date(_string(entry.get(field), field))
        for field in (
            "wait_listing_start_source",
            "wait_listing_end_source",
            "wait_follow_up_end_source",
        )
    )
    if expected_wait != (periods.wait_start, periods.wait_end, periods.wait_follow_up_end):
        raise ReceiptError("Configured wait-time dates disagree with independent source evidence.")
    methodology = _methodology(entry, source, periods)
    sheets = read_workbook_sheets(load_workbook_payload(source, cache_dir))
    identities = _parse_identities(source, methodology, sheets)
    registry = {identity.program_key: identity for identity in identities}
    outcomes = _receipt_rows(source, methodology, sheets, registry, checks, key)
    return ReceiptRelease(
        source,
        periods,
        identities,
        outcomes,
        _parse_transplant_rates(source, methodology.metric("transplant_rate"), sheets, registry),
        _parse_wait_times(source, methodology.metric("wait_time"), sheets, registry),
        parse_offer_acceptance_workbook(manifest, source, sheets),
        methodology,
    )


def _validate_release_entry(entry: Mapping[str, object], source: SourceRecord) -> None:
    """Require provenance settings to agree before interpreting any saved source values."""
    if entry.get("release_code") != source.release_code:
        raise ReceiptError("Source binding release disagrees with its workbook.")
    if entry.get("organ") != "Kidney":
        raise ReceiptError("Source binding organ must be Kidney.")
    if type(entry.get("horizon_months")) is not int or entry.get("horizon_months") != 18:
        raise ReceiptError("Source binding horizon must be 18 months.")
    if entry.get("evidence_kind") not in {"cached_web_reader_pdf_text", "local_pdf_text"}:
        raise ReceiptError("Source evidence kind must identify a verified report copy.")
    shapes = _mapping(entry.get("shapes"), "Source shapes")
    if set(shapes) != {"identity", "outcome", "rate", "wait"}:
        raise ReceiptError("Source shapes must identify all four required sheets.")
    for shape in shapes.values():
        _shape(shape)
    if entry.get("workbook_sheet") != _mapping(shapes["outcome"], "Outcome shape").get("name"):
        raise ReceiptError("Source binding outcome sheet disagrees with its shape.")
    published = _string(entry.get("report_release_date"), "Source publication date")
    try:
        day = datetime.strptime(published, "%B %d, %Y").date().isoformat()
    except ValueError as exc:
        raise ReceiptError("Source publication date is invalid.") from exc
    if not day.startswith(source.published_value):
        raise ReceiptError("Source publication disagrees with its workbook release.")
    _validate_report_url(entry, source)
    _validate_checks(_mapping(entry.get("checks"), "Source binding checks"))


def _validate_report_url(entry: Mapping[str, object], source: SourceRecord) -> None:
    key = _string(entry.get("program_key"), "Bound program")
    if re.fullmatch(r"[A-Z0-9]{4}:[A-Z0-9]+", key) is None:
        raise ReceiptError("Source binding identity requires a composite program key.")
    parsed = urlparse(_string(entry.get("source_url"), "Report URL"))
    name = Path(parsed.path).name.lower()
    program = key.replace(":", "").lower()
    expected = (
        program + "_ki"
        if entry.get("evidence_kind") == "local_pdf_text"
        else program + "ki20" + source.release_code + "pnew.pdf"
    )
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"srtr.org", "www.srtr.org", "srtr.hrsa.gov"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or name != expected
    ):
        raise ReceiptError("Report URL must bind this release's specific kidney program.")


def _validate_evidence_origin(
    entry: Mapping[str, object], outcome: str, wait: str, root: Path
) -> None:
    if entry.get("evidence_kind") == "cached_web_reader_pdf_text":
        url = _string(entry.get("source_url"), "Report URL")
        if "pdf_bytes" in entry or any(url not in text for text in (outcome, wait)):
            raise ReceiptError("Source evidence URL provenance disagrees with the pinned report.")
        return
    pdf = _fingerprinted_bytes(
        _mapping(entry.get("pdf_bytes"), "Local PDF fingerprint"),
        repository_root=root,
        prefix=Path("data/audit-0022"),
        suffix="pdf",
        maximum_bytes=16_000_000,
    )
    if not pdf.startswith(b"%PDF-"):
        raise ReceiptError("Local source evidence file is not a PDF.")


def _pair(value: object) -> Pair:
    values = _sequence(value, "Release pair")
    if len(values) != 2:
        raise ReceiptError("A release pair needs exactly two release codes.")
    return _string(values[0], "Feature release"), _string(values[1], "Target release")


def _fixed_gate(config: Mapping[str, object], manifest: DataSourceManifest, root: Path) -> None:
    if (
        config.get("analysis_id") != ANALYSIS_ID
        or type(config.get("schema_version")) is not int
        or config.get("schema_version") != 1
    ):
        raise ReceiptError("Wrong receipt source contract identity.")
    if set(config) != {
        "analysis_id",
        "excluded_releases",
        "folds",
        "follow_up_convention",
        "pairs",
        "releases",
        "schema_version",
        "source_manifest_sha256",
    }:
        raise ReceiptError("Receipt source contract has missing or extra settings.")
    if config.get("follow_up_convention") != "conservative_december31_bound_not_source_censor_date":
        raise ReceiptError("Receipt follow-up convention changed from the fixed source contract.")
    if config.get("pairs") != [list(pair) for pair in FIXED_PAIRS]:
        raise ReceiptError("Receipt study pairs disagree with the fixed source gate.")
    expected_folds = [
        {"evaluation_pair": list(pair), "training_pairs": [list(p) for p in training]}
        for pair, training in FIXED_FOLDS
    ]
    if config.get("folds") != expected_folds:
        raise ReceiptError("Receipt study folds disagree with the fixed source gate.")
    entries = _sequence(config.get("releases"), "Source releases")
    codes = tuple(_mapping(entry, "Release binding").get("release_code") for entry in entries)
    if codes != FIXED_RELEASES:
        raise ReceiptError("Receipt source release set changed from the fixed seven releases.")
    manifest_path = root / "configs/data_sources.yaml"
    if (
        sha256(manifest_path.read_bytes()).hexdigest() != config.get("source_manifest_sha256")
        or load_data_source_manifest(manifest_path) != manifest
    ):
        raise ReceiptError("Receipt source manifest fingerprint or supplied manifest disagrees.")
    exclusions = _mapping(config.get("excluded_releases"), "Source exclusions")
    if set(exclusions) != {"1808", "2006"} or any(
        not isinstance(value, str) or not value.strip() for value in exclusions.values()
    ):
        raise ReceiptError("Receipt source exclusions must explain both omitted releases.")


def load_receipt_sources(
    path: Path, *, manifest: DataSourceManifest, repository_root: Path, cache_dir: Path
) -> ReceiptSources:
    """Read the fixed source gate, then build only verified, source-bound releases."""
    try:
        payload = path.read_bytes()
        config = _mapping(
            json.loads(payload, object_pairs_hook=_unique_json), "Receipt source configuration"
        )
        _fixed_gate(config, manifest, repository_root)
        entries = _sequence(config.get("releases"), "Source releases")
        sources = {source.release_code: source for source in manifest.sources}
        releases = tuple(
            _load_release(
                entry,
                sources[_string(entry.get("release_code"), "Release code")],
                repository_root,
                cache_dir,
                manifest,
            )
            for raw in entries
            for entry in [_mapping(raw, "Release binding")]
        )
        if len({release.source.release_code for release in releases}) != len(releases):
            raise ReceiptError("Receipt source configuration duplicates a release.")
        pairs = tuple(_pair(value) for value in _sequence(config.get("pairs"), "Study pairs"))
        folds = tuple(
            (
                _pair(fold.get("evaluation_pair")),
                tuple(
                    _pair(value)
                    for value in _sequence(fold.get("training_pairs"), "Training pairs")
                ),
            )
            for raw in _sequence(config.get("folds"), "Evaluation folds")
            for fold in [_mapping(raw, "Fold")]
        )
        return ReceiptSources(
            releases,
            pairs,
            folds,
            _mapping(config.get("excluded_releases"), "Source exclusions"),
            sha256(payload).hexdigest(),
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, ReceiptError):
            raise
        raise ReceiptError(f"Cannot build receipt sources: {exc}") from exc


def _unique_json(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptError(f"Source configuration contains a duplicate key: {key}.")
        result[key] = value
    return result
