"""Record what each V2 source measure counts, its dates, and its workbook fields.

The methodology ledger links those definitions to the fixed source inventory.
Separate measurement, follow-up, and publication dates establish which reports
can supply inputs or training outcomes; a month-only date keeps that precision.
Safety measures retain their own populations and denominators.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlparse

import yaml

from kasm.config import DataSourceManifest, PublishedPrecision

MetricFamily = Literal["patient_outcome", "transplant_rate", "wait_time"]
SafetyFamily = Literal[
    "waiting_list_mortality",
    "mortality_after_listing",
    "graft_failure_90_day",
    "graft_failure_1_year_conditional",
]
SafetyDirection = Literal["lower_ratio_is_better"]
SafetyIntervalKind = Literal["bayesian_credible_interval"]

ANALYSIS_ID = "kidney_patient_journey_v2"
_METRIC_FAMILIES: tuple[MetricFamily, ...] = (
    "patient_outcome",
    "transplant_rate",
    "wait_time",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFETY_FAMILIES: tuple[SafetyFamily, ...] = (
    "waiting_list_mortality",
    "mortality_after_listing",
    "graft_failure_90_day",
    "graft_failure_1_year_conditional",
)
_EXPECTED_SAFETY_BY_RELEASE: dict[str, tuple[SafetyFamily, ...]] = {
    "1808": (),
    "1905": ("waiting_list_mortality",),
    "2006": ("waiting_list_mortality",),
    "2105": ("waiting_list_mortality", "mortality_after_listing"),
    "2205": _SAFETY_FAMILIES,
    "2305": _SAFETY_FAMILIES,
    "2405": _SAFETY_FAMILIES,
    "2505": _SAFETY_FAMILIES,
    "2605": _SAFETY_FAMILIES,
}


class MethodologyLedgerError(ValueError):
    """Raised when the v2 methodology ledger is incomplete or inconsistent."""


@dataclass(frozen=True)
class SheetContract:
    """Expected row/column counts and named machine fields for one workbook sheet."""

    name: str
    expected_rows: int
    expected_columns: int
    required_fields: tuple[str, ...]


@dataclass(frozen=True)
class MetricMethodology:
    """Dates, meaning, and workbook layout for one group of measures in one release."""

    family: MetricFamily
    sheet: SheetContract
    measurement_start: date
    measurement_end: date
    follow_up_end: date
    timing_source_url: str
    definition_notes: tuple[str, ...]
    method_changes: tuple[str, ...]
    policy_context: tuple[str, ...]


@dataclass(frozen=True)
class SafetyMethodology:
    """Independent timing and meaning for one published safety measure."""

    family: SafetyFamily
    sheet: SheetContract
    measurement_start: date
    measurement_end: date
    included_segments: tuple[tuple[date, date], ...]
    follow_up_end: date
    timing_source_url: str
    population: str
    event: str
    denominator: str
    direction: SafetyDirection
    interval_kind: SafetyIntervalKind
    interval_level: float
    definition_notes: tuple[str, ...]


@dataclass(frozen=True)
class ReleaseMethodology:
    """All v2 source contracts for one immutable PSR release."""

    release_code: str
    published_value: str
    published_precision: PublishedPrecision
    source_url: str
    source_sha256: str
    identity_sheet: SheetContract
    metrics: tuple[MetricMethodology, ...]
    safety_metrics: tuple[SafetyMethodology, ...] = ()

    def metric(self, family: MetricFamily) -> MetricMethodology:
        """Return one required metric family or fail with release context."""
        match = next((metric for metric in self.metrics if metric.family == family), None)
        if match is None:
            raise MethodologyLedgerError(
                f"Release {self.release_code!r} has no {family!r} methodology."
            )
        return match

    def safety_metric(self, family: SafetyFamily) -> SafetyMethodology:
        """Return one published safety family or fail with release context."""
        match = next((metric for metric in self.safety_metrics if metric.family == family), None)
        if match is None:
            raise MethodologyLedgerError(
                f"Release {self.release_code!r} has no published {family!r} safety metric."
            )
        return match


@dataclass(frozen=True)
class MethodologyLedger:
    """Release definitions checked against the fixed source-file inventory."""

    schema_version: int
    analysis_id: str
    source_manifest: str
    releases: tuple[ReleaseMethodology, ...]

    def release(self, release_code: str) -> ReleaseMethodology:
        """Return one pinned release methodology."""
        match = next(
            (release for release in self.releases if release.release_code == release_code), None
        )
        if match is None:
            raise MethodologyLedgerError(f"Unknown methodology release {release_code!r}.")
        return match

    def overlapping_outcome_cohorts(self) -> tuple[tuple[str, str], ...]:
        """Find consecutive reports whose listing periods share any calendar date."""
        overlaps: list[tuple[str, str]] = []
        for earlier, later in zip(self.releases, self.releases[1:], strict=False):
            earlier_timing = earlier.metric("patient_outcome")
            later_timing = later.metric("patient_outcome")
            if (
                earlier_timing.measurement_start <= later_timing.measurement_end
                and later_timing.measurement_start <= earlier_timing.measurement_end
            ):
                overlaps.append((earlier.release_code, later.release_code))
        return tuple(overlaps)


def _mapping(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise MethodologyLedgerError(f"{context} must be a mapping with string keys.")
    return cast(dict[str, object], value)


def _sequence(value: object, context: str, *, allow_empty: bool = False) -> list[object]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise MethodologyLedgerError(f"{context} must be {qualifier}.")
    return value


def _string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MethodologyLedgerError(f"{context} must be a non-empty string.")
    return value.strip()


def _integer(value: object, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MethodologyLedgerError(f"{context} must be an integer.")
    return value


def _date(value: object, context: str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise MethodologyLedgerError(f"{context} must be an ISO calendar date.") from error
    raise MethodologyLedgerError(f"{context} must be an ISO calendar date.")


def _published_value(value: object, context: str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return _string(value, context)


def _string_tuple(value: object, context: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    items = _sequence(value, context, allow_empty=allow_empty)
    result = tuple(_string(item, f"{context} item") for item in items)
    duplicate = next((item for index, item in enumerate(result) if item in result[:index]), None)
    if duplicate is not None:
        raise MethodologyLedgerError(f"{context} contains duplicate value {duplicate!r}.")
    return result


def _sheet(value: object, context: str) -> SheetContract:
    values = _mapping(value, context)
    name = _string(values.get("sheet_name"), f"{context}.sheet_name")
    expected_rows = _integer(values.get("expected_rows"), f"{context}.expected_rows")
    expected_columns = _integer(values.get("expected_columns"), f"{context}.expected_columns")
    fields = _string_tuple(values.get("required_fields"), f"{context}.required_fields")
    if expected_rows <= 0:
        raise MethodologyLedgerError(f"{context}.expected_rows must be positive.")
    if expected_columns < len(fields):
        raise MethodologyLedgerError(
            f"{context}.expected_columns cannot be smaller than required_fields."
        )
    return SheetContract(
        name=name,
        expected_rows=expected_rows,
        expected_columns=expected_columns,
        required_fields=fields,
    )


def _https_url(value: object, context: str) -> str:
    result = _string(value, context)
    parsed = urlparse(result)
    if parsed.scheme != "https" or not parsed.netloc:
        raise MethodologyLedgerError(f"{context} must be an absolute HTTPS URL.")
    return result


def _sha256(value: object, context: str) -> str:
    result = _string(value, context)
    if _SHA256.fullmatch(result) is None:
        raise MethodologyLedgerError(f"{context} must be a lowercase 64-character SHA-256 digest.")
    return result


def _metric(value: object, release_context: str, index: int) -> MetricMethodology:
    context = f"{release_context}.metrics[{index}]"
    values = _mapping(value, context)
    raw_family = _string(values.get("family"), f"{context}.family")
    if raw_family not in _METRIC_FAMILIES:
        raise MethodologyLedgerError(f"{context}.family is unsupported: {raw_family!r}.")
    family = raw_family
    measurement_start = _date(values.get("measurement_start"), f"{context}.measurement_start")
    measurement_end = _date(values.get("measurement_end"), f"{context}.measurement_end")
    follow_up_end = _date(values.get("follow_up_end"), f"{context}.follow_up_end")
    if measurement_end < measurement_start:
        raise MethodologyLedgerError(f"{context}.measurement_end cannot precede measurement_start.")
    if follow_up_end < measurement_end:
        raise MethodologyLedgerError(f"{context}.follow_up_end cannot precede measurement_end.")
    return MetricMethodology(
        family=family,
        sheet=_sheet(values, context),
        measurement_start=measurement_start,
        measurement_end=measurement_end,
        follow_up_end=follow_up_end,
        timing_source_url=_https_url(
            values.get("timing_source_url"), f"{context}.timing_source_url"
        ),
        definition_notes=_string_tuple(
            values.get("definition_notes"), f"{context}.definition_notes"
        ),
        method_changes=_string_tuple(
            values.get("method_changes"), f"{context}.method_changes", allow_empty=True
        ),
        policy_context=_string_tuple(
            values.get("policy_context"), f"{context}.policy_context", allow_empty=True
        ),
    )


def _included_segments(
    value: object, context: str, *, measurement_start: date, measurement_end: date
) -> tuple[tuple[date, date], ...]:
    segments: list[tuple[date, date]] = []
    for index, item in enumerate(_sequence(value, context)):
        segment_context = f"{context}[{index}]"
        values = _mapping(item, segment_context)
        start = _date(values.get("start"), f"{segment_context}.start")
        end = _date(values.get("end"), f"{segment_context}.end")
        if end < start:
            raise MethodologyLedgerError(f"{segment_context}.end cannot precede start.")
        if start < measurement_start or end > measurement_end:
            raise MethodologyLedgerError(
                f"{segment_context} must remain inside the metric measurement period."
            )
        if segments and start <= segments[-1][1]:
            raise MethodologyLedgerError(
                f"{segment_context} must be ordered and must not overlap a prior segment."
            )
        segments.append((start, end))
    return tuple(segments)


def _safety_metric(value: object, release_context: str, index: int) -> SafetyMethodology:
    context = f"{release_context}.safety_metrics[{index}]"
    values = _mapping(value, context)
    raw_family = _string(values.get("family"), f"{context}.family")
    if raw_family not in _SAFETY_FAMILIES:
        raise MethodologyLedgerError(f"{context}.family is unsupported: {raw_family!r}.")
    family: SafetyFamily = raw_family
    measurement_start = _date(values.get("measurement_start"), f"{context}.measurement_start")
    measurement_end = _date(values.get("measurement_end"), f"{context}.measurement_end")
    follow_up_end = _date(values.get("follow_up_end"), f"{context}.follow_up_end")
    if measurement_end < measurement_start:
        raise MethodologyLedgerError(f"{context}.measurement_end cannot precede start.")
    if follow_up_end < measurement_end:
        raise MethodologyLedgerError(f"{context}.follow_up_end cannot precede measurement_end.")
    raw_direction = _string(values.get("direction"), f"{context}.direction")
    if raw_direction != "lower_ratio_is_better":
        raise MethodologyLedgerError(f"{context}.direction must be 'lower_ratio_is_better'.")
    raw_interval = _string(values.get("interval_kind"), f"{context}.interval_kind")
    if raw_interval != "bayesian_credible_interval":
        raise MethodologyLedgerError(
            f"{context}.interval_kind must be 'bayesian_credible_interval'."
        )
    interval_level = values.get("interval_level")
    if isinstance(interval_level, bool) or not isinstance(interval_level, int | float):
        raise MethodologyLedgerError(f"{context}.interval_level must be numeric.")
    if float(interval_level) != 0.95:
        raise MethodologyLedgerError(f"{context}.interval_level must remain 0.95.")
    return SafetyMethodology(
        family=family,
        sheet=_sheet(values, context),
        measurement_start=measurement_start,
        measurement_end=measurement_end,
        included_segments=_included_segments(
            values.get("included_segments"),
            f"{context}.included_segments",
            measurement_start=measurement_start,
            measurement_end=measurement_end,
        ),
        follow_up_end=follow_up_end,
        timing_source_url=_https_url(
            values.get("timing_source_url"), f"{context}.timing_source_url"
        ),
        population=_string(values.get("population"), f"{context}.population"),
        event=_string(values.get("event"), f"{context}.event"),
        denominator=_string(values.get("denominator"), f"{context}.denominator"),
        direction="lower_ratio_is_better",
        interval_kind="bayesian_credible_interval",
        interval_level=0.95,
        definition_notes=_string_tuple(
            values.get("definition_notes"), f"{context}.definition_notes"
        ),
    )


def _release(value: object, index: int) -> ReleaseMethodology:
    context = f"releases[{index}]"
    values = _mapping(value, context)
    release_code = _string(values.get("release_code"), f"{context}.release_code")
    raw_precision = _string(values.get("published_precision"), f"{context}.published_precision")
    if raw_precision not in {"month", "day"}:
        raise MethodologyLedgerError(f"{context}.published_precision must be 'month' or 'day'.")
    published_precision = cast(PublishedPrecision, raw_precision)
    metrics = tuple(
        _metric(metric, context, metric_index)
        for metric_index, metric in enumerate(
            _sequence(values.get("metrics"), f"{context}.metrics")
        )
    )
    families = tuple(metric.family for metric in metrics)
    duplicate = next(
        (
            family
            for metric_index, family in enumerate(families)
            if family in families[:metric_index]
        ),
        None,
    )
    if duplicate is not None:
        raise MethodologyLedgerError(
            f"Release {release_code!r} has duplicate metric family {duplicate!r}."
        )
    if set(families) != set(_METRIC_FAMILIES):
        raise MethodologyLedgerError(
            f"Release {release_code!r} must define metric families {_METRIC_FAMILIES!r}."
        )
    safety_metrics = tuple(
        _safety_metric(metric, context, metric_index)
        for metric_index, metric in enumerate(
            _sequence(
                values.get("safety_metrics", []),
                f"{context}.safety_metrics",
                allow_empty=True,
            )
        )
    )
    safety_families = tuple(metric.family for metric in safety_metrics)
    if len(safety_families) != len(set(safety_families)):
        raise MethodologyLedgerError(
            f"Release {release_code!r} has a duplicate safety metric family."
        )
    expected_safety = _EXPECTED_SAFETY_BY_RELEASE.get(release_code)
    if expected_safety is not None and safety_families != expected_safety:
        raise MethodologyLedgerError(
            f"Release {release_code!r} must define safety families {expected_safety!r}."
        )
    return ReleaseMethodology(
        release_code=release_code,
        published_value=_published_value(
            values.get("published_value"), f"{context}.published_value"
        ),
        published_precision=published_precision,
        source_url=_https_url(values.get("source_url"), f"{context}.source_url"),
        source_sha256=_sha256(values.get("source_sha256"), f"{context}.source_sha256"),
        identity_sheet=_sheet(values.get("identity"), f"{context}.identity"),
        metrics=metrics,
        safety_metrics=safety_metrics,
    )


def load_methodology_ledger(path: Path, *, manifest: DataSourceManifest) -> MethodologyLedger:
    """Load the ledger and require exact agreement with the immutable source manifest."""
    raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    values = _mapping(raw, "Ledger root")
    schema_version = _integer(values.get("schema_version"), "Ledger root.schema_version")
    if schema_version != 1:
        raise MethodologyLedgerError(
            f"Unsupported methodology schema_version {schema_version}; expected 1."
        )
    analysis_id = _string(values.get("analysis_id"), "Ledger root.analysis_id")
    if analysis_id != ANALYSIS_ID:
        raise MethodologyLedgerError(f"Ledger root.analysis_id must be {ANALYSIS_ID!r}.")
    source_manifest = _string(values.get("source_manifest"), "Ledger root.source_manifest")
    releases = tuple(
        _release(release, index)
        for index, release in enumerate(_sequence(values.get("releases"), "Ledger root.releases"))
    )
    ledger_codes = tuple(release.release_code for release in releases)
    manifest_codes = tuple(source.release_code for source in manifest.sources)
    if ledger_codes != manifest_codes:
        raise MethodologyLedgerError(
            "Methodology releases must exactly cover manifest releases in manifest order."
        )
    source_by_code = {source.release_code: source for source in manifest.sources}
    for release in releases:
        source = source_by_code[release.release_code]
        if (
            release.published_value != source.published_value
            or release.published_precision != source.published_precision
        ):
            raise MethodologyLedgerError(
                f"Release {release.release_code!r} publication value and precision disagree "
                "with the source manifest."
            )
        if release.source_url != source.url or release.source_sha256 != source.download_sha256:
            raise MethodologyLedgerError(
                f"Release {release.release_code!r} source URL and SHA-256 disagree with the "
                "source manifest."
            )
    return MethodologyLedger(
        schema_version=schema_version,
        analysis_id=analysis_id,
        source_manifest=source_manifest,
        releases=releases,
    )
