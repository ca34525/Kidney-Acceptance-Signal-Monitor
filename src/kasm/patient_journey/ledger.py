"""Typed methodology and source-schema ledger for patient-journey v2."""

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

ANALYSIS_ID = "kidney_patient_journey_v2"
_METRIC_FAMILIES: tuple[MetricFamily, ...] = (
    "patient_outcome",
    "transplant_rate",
    "wait_time",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class MethodologyLedgerError(ValueError):
    """Raised when the v2 methodology ledger is incomplete or inconsistent."""


@dataclass(frozen=True)
class SheetContract:
    """Pinned table shape and machine fields for one workbook sheet."""

    name: str
    expected_rows: int
    expected_columns: int
    required_fields: tuple[str, ...]


@dataclass(frozen=True)
class MetricMethodology:
    """Timing, definition, and schema evidence for one release-level metric family."""

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
class ReleaseMethodology:
    """All v2 source contracts for one immutable PSR release."""

    release_code: str
    published_value: str
    published_precision: PublishedPrecision
    source_url: str
    source_sha256: str
    identity_sheet: SheetContract
    metrics: tuple[MetricMethodology, ...]

    def metric(self, family: MetricFamily) -> MetricMethodology:
        """Return one required metric family or fail with release context."""
        match = next((metric for metric in self.metrics if metric.family == family), None)
        if match is None:
            raise MethodologyLedgerError(
                f"Release {self.release_code!r} has no {family!r} methodology."
            )
        return match


@dataclass(frozen=True)
class MethodologyLedger:
    """Manifest-aligned patient-journey release methodology."""

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
        """Expose inclusive overlap between successive published outcome cohorts."""
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
