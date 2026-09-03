"""Canonical data construction from validated annual SRTR releases."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from math import log, log1p
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from kasm.config import DataSourceManifest, PublishedPrecision, SourceRecord
from kasm.data.parse import (
    OfferGroup,
    ProgramSignal,
    WorkbookSheet,
    load_workbook_payload,
    parse_offer_acceptance_workbook,
    read_workbook_sheets,
)

_DIRECTORY_FIELDS = (
    "ENTIRE_NAME",
    "PRIMARY_CITY",
    "PRIMARY_STATE",
    "PRIMARY_ZIP",
    "CTR_CD",
    "CTR_TY",
    "ORGAN",
)
_CENTER_CODE = re.compile(r"^[A-Z0-9]{4}$")
_SUBGROUPS: tuple[OfferGroup, ...] = ("low", "medium", "high", "hard-to-place")

MODEL_FEATURE_COLUMNS = (
    "current_log_overall_oar",
    "previous_annual_log_overall_oar",
    "one_year_change_log_overall_oar",
    "log1p_overall_expected_acceptances",
    "log_credible_interval_width",
    "current_log_low_oar",
    "current_log_medium_oar",
    "current_log_high_oar",
    "current_log_hard_to_place_oar",
    "high_offers_share",
    "hard_to_place_offers_share",
    "missing_previous_annual_log_overall_oar",
    "missing_one_year_change_log_overall_oar",
    "missing_current_log_low_oar",
    "missing_current_log_medium_oar",
    "missing_current_log_high_oar",
    "missing_current_log_hard_to_place_oar",
)

_CATEGORY = pa.dictionary(pa.int8(), pa.string())
PROGRAM_SIGNALS_SCHEMA = pa.schema(
    [
        pa.field("program_key", pa.string(), nullable=False),
        pa.field("center_code", pa.string(), nullable=False),
        pa.field("center_type", pa.string(), nullable=False),
        pa.field("center_name", pa.string(), nullable=False),
        pa.field("city", pa.string()),
        pa.field("state", pa.string()),
        pa.field("zip", pa.string()),
        pa.field("release_code", pa.string(), nullable=False),
        pa.field("published_value", pa.string(), nullable=False),
        pa.field("published_precision", _CATEGORY, nullable=False),
        pa.field("cohort_year", pa.int16(), nullable=False),
        pa.field("cohort_start", pa.date32(), nullable=False),
        pa.field("cohort_end", pa.date32(), nullable=False),
        pa.field("offer_group", _CATEGORY, nullable=False),
        pa.field("offers", pa.int64()),
        pa.field("acceptances", pa.int64()),
        pa.field("expected_acceptances", pa.float64()),
        pa.field("oar_mean", pa.float64()),
        pa.field("oar_lower", pa.float64()),
        pa.field("oar_upper", pa.float64()),
        pa.field("source_url", pa.string(), nullable=False),
        pa.field("source_sha256", pa.string(), nullable=False),
    ]
)

MODEL_PANEL_SCHEMA = pa.schema(
    [
        pa.field("program_key", pa.string(), nullable=False),
        pa.field("feature_cohort_year", pa.int16(), nullable=False),
        pa.field("target_cohort_year", pa.int16(), nullable=False),
        pa.field("prediction_as_of", pa.string(), nullable=False),
        pa.field("prediction_as_of_precision", _CATEGORY, nullable=False),
        pa.field("target_cohort_end", pa.date32(), nullable=False),
        pa.field("truth_published_value", pa.string()),
        pa.field("truth_published_precision", _CATEGORY),
        pa.field("elapsed_target_cohort_fraction_at_prediction", pa.float64(), nullable=False),
        pa.field("current_log_overall_oar", pa.float64(), nullable=False),
        pa.field("previous_annual_log_overall_oar", pa.float64()),
        pa.field("one_year_change_log_overall_oar", pa.float64()),
        pa.field("log1p_overall_expected_acceptances", pa.float64(), nullable=False),
        pa.field("log_credible_interval_width", pa.float64(), nullable=False),
        pa.field("current_log_low_oar", pa.float64()),
        pa.field("current_log_medium_oar", pa.float64()),
        pa.field("current_log_high_oar", pa.float64()),
        pa.field("current_log_hard_to_place_oar", pa.float64()),
        pa.field("high_offers_share", pa.float64()),
        pa.field("hard_to_place_offers_share", pa.float64()),
        pa.field("missing_previous_annual_log_overall_oar", pa.bool_(), nullable=False),
        pa.field("missing_one_year_change_log_overall_oar", pa.bool_(), nullable=False),
        pa.field("missing_current_log_low_oar", pa.bool_(), nullable=False),
        pa.field("missing_current_log_medium_oar", pa.bool_(), nullable=False),
        pa.field("missing_current_log_high_oar", pa.bool_(), nullable=False),
        pa.field("missing_current_log_hard_to_place_oar", pa.bool_(), nullable=False),
        pa.field("target_oar", pa.float64()),
        pa.field("target_log_oar", pa.float64()),
        pa.field("analytic_eligible", pa.bool_(), nullable=False),
        pa.field("public_forecast_eligible", pa.bool_(), nullable=False),
        pa.field("first_observed_program", pa.bool_(), nullable=False),
    ]
)


class BuildError(ValueError):
    """Raised when canonical construction would violate a data contract."""


@dataclass(frozen=True)
class DirectoryEntry:
    """Display-only fields from the latest workbook directory."""

    program_key: str
    center_name: str
    city: str | None
    state: str | None
    zip: str | None


@dataclass(frozen=True)
class CanonicalSignal:
    """One typed canonical program-year and offer-group signal."""

    program_key: str
    center_code: str
    center_type: str
    center_name: str
    city: str | None
    state: str | None
    zip: str | None
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
    raw_cohort_start: str | None = None
    raw_cohort_end: str | None = None


@dataclass(frozen=True)
class ModelPanelRow:
    """One feature-cohort row with an explicitly aligned next-year target."""

    program_key: str
    feature_cohort_year: int
    target_cohort_year: int
    prediction_as_of: str
    prediction_as_of_precision: PublishedPrecision
    target_cohort_end: date
    truth_published_value: str | None
    truth_published_precision: PublishedPrecision | None
    elapsed_target_cohort_fraction_at_prediction: float
    current_log_overall_oar: float
    previous_annual_log_overall_oar: float | None
    one_year_change_log_overall_oar: float | None
    log1p_overall_expected_acceptances: float
    log_credible_interval_width: float
    current_log_low_oar: float | None
    current_log_medium_oar: float | None
    current_log_high_oar: float | None
    current_log_hard_to_place_oar: float | None
    high_offers_share: float | None
    hard_to_place_offers_share: float | None
    missing_previous_annual_log_overall_oar: bool
    missing_one_year_change_log_overall_oar: bool
    missing_current_log_low_oar: bool
    missing_current_log_medium_oar: bool
    missing_current_log_high_oar: bool
    missing_current_log_hard_to_place_oar: bool
    target_oar: float | None
    target_log_oar: float | None
    analytic_eligible: bool
    public_forecast_eligible: bool
    first_observed_program: bool


@dataclass(frozen=True)
class DataBuildResult:
    """Paths and row counts for one published canonical data build."""

    program_signals_path: Path
    model_panel_path: Path
    qa_report_path: Path
    program_signal_rows: int
    model_panel_rows: int


def _directory_text(value: object, *, required: bool, field: str) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise BuildError(f"Current directory field {field!r} is missing.")
        return None
    if isinstance(value, bool):
        raise BuildError(f"Current directory field {field!r} must be text.")
    if isinstance(value, float) and value.is_integer():
        result = str(int(value))
    else:
        result = str(value).strip()
    return result or None


def _directory_header(sheet: WorkbookSheet) -> tuple[int, dict[str, int]]:
    required = set(_DIRECTORY_FIELDS)
    for row_index, row in enumerate(sheet.rows[:10]):
        headers = tuple(value.strip() if isinstance(value, str) else "" for value in row)
        if not required.issubset(headers):
            continue
        positions: dict[str, int] = {}
        for column_index, header in enumerate(headers):
            if not header:
                continue
            if header in positions:
                raise BuildError(f"Current directory duplicates machine field {header!r}.")
            positions[header] = column_index
        return row_index, positions
    raise BuildError("Current directory does not contain its required machine fields.")


def _directory_value(row: tuple[object, ...], positions: dict[str, int], field: str) -> object:
    position = positions[field]
    return row[position] if position < len(row) else None


def parse_current_directory(
    source: SourceRecord, sheets: tuple[WorkbookSheet, ...]
) -> dict[str, DirectoryEntry]:
    """Parse kidney display fields from the latest release's `Tiers` sheet."""
    sheet = next((candidate for candidate in sheets if candidate.name == "Tiers"), None)
    if sheet is None:
        raise BuildError(f"Release {source.release_code!r} is missing the 'Tiers' directory sheet.")
    header_index, positions = _directory_header(sheet)
    rows = sheet.rows[header_index + 1 :]
    if rows and _directory_value(rows[0], positions, "CTR_CD") == "Center Code":
        rows = rows[1:]

    entries: dict[str, DirectoryEntry] = {}
    for row in rows:
        organ = _directory_text(
            _directory_value(row, positions, "ORGAN"), required=False, field="ORGAN"
        )
        if organ is None or organ.casefold() != "kidney":
            continue
        center_code = _directory_text(
            _directory_value(row, positions, "CTR_CD"), required=True, field="CTR_CD"
        )
        center_type = _directory_text(
            _directory_value(row, positions, "CTR_TY"), required=True, field="CTR_TY"
        )
        assert center_code is not None and center_type is not None
        center_code = center_code.upper()
        if _CENTER_CODE.fullmatch(center_code) is None:
            raise BuildError(
                f"Current directory center code {center_code!r} must match [A-Z0-9]{{4}}."
            )
        program_key = f"{center_code}:{center_type}"
        if program_key in entries:
            raise BuildError(f"Current directory duplicates program key {program_key!r}.")
        center_name = (
            _directory_text(
                _directory_value(row, positions, "ENTIRE_NAME"),
                required=False,
                field="ENTIRE_NAME",
            )
            or f"Program {center_code}"
        )
        entries[program_key] = DirectoryEntry(
            program_key=program_key,
            center_name=center_name,
            city=_directory_text(
                _directory_value(row, positions, "PRIMARY_CITY"),
                required=False,
                field="PRIMARY_CITY",
            ),
            state=_directory_text(
                _directory_value(row, positions, "PRIMARY_STATE"),
                required=False,
                field="PRIMARY_STATE",
            ),
            zip=_directory_text(
                _directory_value(row, positions, "PRIMARY_ZIP"),
                required=False,
                field="PRIMARY_ZIP",
            ),
        )
    return entries


def join_current_directory(
    signals: tuple[ProgramSignal, ...], directory: dict[str, DirectoryEntry]
) -> tuple[CanonicalSignal, ...]:
    """Attach display-only current directory fields without changing signal identity."""
    result: list[CanonicalSignal] = []
    for signal in signals:
        entry = directory.get(signal.program_key)
        result.append(
            CanonicalSignal(
                program_key=signal.program_key,
                center_code=signal.center_code,
                center_type=signal.center_type,
                center_name=entry.center_name if entry is not None else signal.center_name,
                city=entry.city if entry is not None else None,
                state=entry.state if entry is not None else None,
                zip=entry.zip if entry is not None else None,
                release_code=signal.release_code,
                published_value=signal.published_value,
                published_precision=signal.published_precision,
                cohort_year=signal.cohort_year,
                cohort_start=signal.cohort_start,
                cohort_end=signal.cohort_end,
                offer_group=signal.offer_group,
                offers=signal.offers,
                acceptances=signal.acceptances,
                expected_acceptances=signal.expected_acceptances,
                oar_mean=signal.oar_mean,
                oar_lower=signal.oar_lower,
                oar_upper=signal.oar_upper,
                source_url=signal.source_url,
                source_sha256=signal.source_sha256,
                raw_cohort_start=signal.raw_cohort_start,
                raw_cohort_end=signal.raw_cohort_end,
            )
        )
    return tuple(result)


def _positive_log(value: float | None, *, context: str, required: bool) -> float | None:
    if value is None:
        if required:
            raise BuildError(f"{context} is required.")
        return None
    if value <= 0:
        if required:
            raise BuildError(f"{context} must be positive for log transformation.")
        return None
    return log(value)


def _elapsed_target_fraction(source: SourceRecord, target_year: int) -> float:
    if source.published_precision == "month":
        parsed_month = datetime.strptime(source.published_value, "%Y-%m")
        if parsed_month.year != target_year:
            raise BuildError(
                f"Release {source.release_code!r} publication year must equal target year "
                f"{target_year}."
            )
        return (parsed_month.month - 1) / 12

    published = date.fromisoformat(source.published_value)
    if published.year != target_year:
        raise BuildError(
            f"Release {source.release_code!r} publication year must equal target year "
            f"{target_year}."
        )
    days_in_year = (date(target_year + 1, 1, 1) - date(target_year, 1, 1)).days
    elapsed_days = (published - date(target_year, 1, 1)).days + 1
    return elapsed_days / days_in_year


def _validate_canonical_rows(signals: tuple[CanonicalSignal, ...]) -> None:
    seen: set[tuple[str, int, OfferGroup]] = set()
    for signal in signals:
        expected_start = date(signal.cohort_year, 1, 1)
        expected_end = date(signal.cohort_year, 12, 31)
        if signal.cohort_start != expected_start or signal.cohort_end != expected_end:
            raise BuildError(
                f"{signal.program_key} cohort {signal.cohort_year} must be a full calendar year."
            )
        key = (signal.program_key, signal.cohort_year, signal.offer_group)
        if key in seen:
            raise BuildError(f"Canonical signal key {key!r} is not unique.")
        seen.add(key)


def _share(numerator: int | None, denominator: int) -> float | None:
    return numerator / denominator if numerator is not None else None


def build_model_panel(
    signals: tuple[CanonicalSignal, ...], sources: tuple[SourceRecord, ...]
) -> tuple[ModelPanelRow, ...]:
    """Construct adjacent annual feature-to-target rows without future-value imputation."""
    _validate_canonical_rows(signals)
    sources_by_year = {source.cohort_year: source for source in sources}
    if len(sources_by_year) != len(sources):
        raise BuildError("Source cohort years must be unique when constructing the model panel.")

    by_key_year_group = {
        (signal.program_key, signal.cohort_year, signal.offer_group): signal for signal in signals
    }
    overall = {
        (signal.program_key, signal.cohort_year): signal
        for signal in signals
        if signal.offer_group == "overall"
    }
    first_year_by_program: dict[str, int] = {}
    for program_key, cohort_year in overall:
        first_year_by_program[program_key] = min(
            cohort_year, first_year_by_program.get(program_key, cohort_year)
        )

    rows: list[ModelPanelRow] = []
    for (program_key, feature_year), current in sorted(
        overall.items(), key=lambda item: (item[0][1], item[0][0])
    ):
        source = sources_by_year.get(feature_year)
        if source is None:
            raise BuildError(f"No source metadata exists for feature cohort {feature_year}.")
        current_log = _positive_log(
            current.oar_mean,
            context=f"{program_key} {feature_year} current overall OAR",
            required=True,
        )
        assert current_log is not None
        if current.expected_acceptances is None:
            raise BuildError(
                f"{program_key} {feature_year} overall expected acceptances are required."
            )
        if current.oar_lower is None or current.oar_upper is None:
            raise BuildError(f"{program_key} {feature_year} overall interval is required.")
        lower_log = _positive_log(
            current.oar_lower,
            context=f"{program_key} {feature_year} overall lower bound",
            required=True,
        )
        upper_log = _positive_log(
            current.oar_upper,
            context=f"{program_key} {feature_year} overall upper bound",
            required=True,
        )
        assert lower_log is not None and upper_log is not None
        if current.offers is None or current.offers <= 0:
            raise BuildError(f"{program_key} {feature_year} overall offers must be positive.")

        previous = overall.get((program_key, feature_year - 1))
        previous_log = (
            _positive_log(
                previous.oar_mean,
                context=f"{program_key} {feature_year - 1} previous overall OAR",
                required=True,
            )
            if previous is not None
            else None
        )
        change = current_log - previous_log if previous_log is not None else None
        groups = {
            group: by_key_year_group.get((program_key, feature_year, group)) for group in _SUBGROUPS
        }
        missing_groups = [group for group, signal in groups.items() if signal is None]
        if missing_groups:
            raise BuildError(
                f"{program_key} {feature_year} is missing canonical offer groups: "
                f"{', '.join(missing_groups)}."
            )
        low = groups["low"]
        medium = groups["medium"]
        high = groups["high"]
        hard = groups["hard-to-place"]
        assert low is not None and medium is not None and high is not None and hard is not None
        low_log = _positive_log(
            low.oar_mean, context=f"{program_key} {feature_year} low OAR", required=False
        )
        medium_log = _positive_log(
            medium.oar_mean,
            context=f"{program_key} {feature_year} medium OAR",
            required=False,
        )
        high_log = _positive_log(
            high.oar_mean, context=f"{program_key} {feature_year} high OAR", required=False
        )
        hard_log = _positive_log(
            hard.oar_mean,
            context=f"{program_key} {feature_year} hard-to-place OAR",
            required=False,
        )

        target_year = feature_year + 1
        target = overall.get((program_key, target_year))
        target_oar = target.oar_mean if target is not None else None
        target_log = (
            _positive_log(
                target_oar,
                context=f"{program_key} {target_year} target overall OAR",
                required=True,
            )
            if target is not None
            else None
        )
        truth_source = sources_by_year.get(target_year)
        observations_through_feature = sum(
            observed_program == program_key and observed_year <= feature_year
            for observed_program, observed_year in overall
        )
        first_observed = first_year_by_program[program_key] == feature_year
        rows.append(
            ModelPanelRow(
                program_key=program_key,
                feature_cohort_year=feature_year,
                target_cohort_year=target_year,
                prediction_as_of=source.published_value,
                prediction_as_of_precision=source.published_precision,
                target_cohort_end=date(target_year, 12, 31),
                truth_published_value=(
                    truth_source.published_value if truth_source is not None else None
                ),
                truth_published_precision=(
                    truth_source.published_precision if truth_source is not None else None
                ),
                elapsed_target_cohort_fraction_at_prediction=_elapsed_target_fraction(
                    source, target_year
                ),
                current_log_overall_oar=current_log,
                previous_annual_log_overall_oar=previous_log,
                one_year_change_log_overall_oar=change,
                log1p_overall_expected_acceptances=log1p(current.expected_acceptances),
                log_credible_interval_width=upper_log - lower_log,
                current_log_low_oar=low_log,
                current_log_medium_oar=medium_log,
                current_log_high_oar=high_log,
                current_log_hard_to_place_oar=hard_log,
                high_offers_share=_share(high.offers, current.offers),
                hard_to_place_offers_share=_share(hard.offers, current.offers),
                missing_previous_annual_log_overall_oar=previous_log is None,
                missing_one_year_change_log_overall_oar=change is None,
                missing_current_log_low_oar=low_log is None,
                missing_current_log_medium_oar=medium_log is None,
                missing_current_log_high_oar=high_log is None,
                missing_current_log_hard_to_place_oar=hard_log is None,
                target_oar=target_oar,
                target_log_oar=target_log,
                analytic_eligible=target_log is not None,
                public_forecast_eligible=(
                    current.oar_mean is not None
                    and observations_through_feature >= 2
                    and not first_observed
                ),
                first_observed_program=first_observed,
            )
        )
    return tuple(rows)


def _decimal_places(value: float) -> int:
    exponent = Decimal(str(value)).as_tuple().exponent
    if not isinstance(exponent, int):
        raise BuildError("Rounding diagnostics require finite decimal values.")
    return max(0, -exponent)


def _rounding_diagnostics(
    signals: tuple[CanonicalSignal, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    precisions: dict[tuple[str, OfferGroup], tuple[int, int]] = {}
    for signal in signals:
        if signal.expected_acceptances is None or signal.oar_mean is None:
            continue
        key = (signal.release_code, signal.offer_group)
        expected_places, ratio_places = precisions.get(key, (0, 0))
        precisions[key] = (
            max(expected_places, _decimal_places(signal.expected_acceptances)),
            max(ratio_places, _decimal_places(signal.oar_mean)),
        )

    summary_counts: dict[tuple[str, int, OfferGroup], list[int]] = {}
    discrepancies: list[dict[str, Any]] = []
    for signal in signals:
        if (
            signal.acceptances is None
            or signal.expected_acceptances is None
            or signal.oar_mean is None
        ):
            continue
        expected_places, ratio_places = precisions[(signal.release_code, signal.offer_group)]
        expected_half_unit = 0.5 * (10.0**-expected_places)
        ratio_half_unit = 0.5 * (10.0**-ratio_places)
        expected_low = max(0.0, signal.expected_acceptances - expected_half_unit)
        expected_high = signal.expected_acceptances + expected_half_unit
        formula_low = (signal.acceptances + 2) / (expected_high + 2)
        formula_high = (signal.acceptances + 2) / (expected_low + 2)
        published_low = max(0.0, signal.oar_mean - ratio_half_unit)
        published_high = signal.oar_mean + ratio_half_unit
        agrees = formula_low <= published_high and published_low <= formula_high
        summary_key = (signal.release_code, signal.cohort_year, signal.offer_group)
        counts = summary_counts.setdefault(summary_key, [0, 0])
        counts[0] += 1
        counts[1] += int(agrees)
        if not agrees:
            discrepancies.append(
                {
                    "release_code": signal.release_code,
                    "cohort_year": signal.cohort_year,
                    "program_key": signal.program_key,
                    "offer_group": signal.offer_group,
                    "published_oar": signal.oar_mean,
                    "published_rounding_low": published_low,
                    "published_rounding_high": published_high,
                    "formula_rounding_low": formula_low,
                    "formula_rounding_high": formula_high,
                    "expected_acceptances_decimal_places": expected_places,
                    "oar_decimal_places": ratio_places,
                    "explanation": (
                        "Published OAR is authoritative; displayed expected acceptances and OAR "
                        "do not have overlapping rounding-implied ranges."
                    ),
                }
            )

    summaries = [
        {
            "release_code": release_code,
            "cohort_year": cohort_year,
            "offer_group": offer_group,
            "checked_rows": counts[0],
            "within_rounding_range_rows": counts[1],
            "discrepancy_rows": counts[0] - counts[1],
        }
        for (release_code, cohort_year, offer_group), counts in sorted(
            summary_counts.items(), key=lambda item: (item[0][1], item[0][2])
        )
    ]
    discrepancies.sort(
        key=lambda item: (item["cohort_year"], item["program_key"], item["offer_group"])
    )
    return summaries, discrepancies


def build_qa_report(
    signals: tuple[CanonicalSignal, ...],
    panel: tuple[ModelPanelRow, ...],
    sources: tuple[SourceRecord, ...],
    directory: dict[str, DirectoryEntry],
) -> dict[str, Any]:
    """Reconcile canonical counts and retain every nonblocking discrepancy."""
    _validate_canonical_rows(signals)
    sources_by_year = {source.cohort_year: source for source in sources}
    if len(sources_by_year) != len(sources):
        raise BuildError("Source cohort years must be unique when constructing QA artifacts.")
    years = sorted(sources_by_year)
    if any(target != feature + 1 for feature, target in zip(years, years[1:], strict=False)):
        raise BuildError("QA transitions require consecutive annual source cohorts.")

    program_keys_by_year: dict[int, set[str]] = {}
    for signal in signals:
        if signal.offer_group == "overall":
            program_keys_by_year.setdefault(signal.cohort_year, set()).add(signal.program_key)

    transitions: list[dict[str, Any]] = []
    for feature_year, target_year in zip(years, years[1:], strict=False):
        feature_keys = program_keys_by_year.get(feature_year, set())
        target_keys = program_keys_by_year.get(target_year, set())
        added = sorted(target_keys - feature_keys)
        closed = sorted(feature_keys - target_keys)
        transitions.append(
            {
                "feature_cohort_year": feature_year,
                "target_cohort_year": target_year,
                "feature_programs": len(feature_keys),
                "target_programs": len(target_keys),
                "matched_programs": len(feature_keys & target_keys),
                "added_program_keys": added,
                "closed_program_keys": closed,
                "unmatched_programs": len(added) + len(closed),
            }
        )

    missing_subgroup: list[dict[str, Any]] = []
    for year in years:
        for group in _SUBGROUPS:
            group_rows = [
                signal
                for signal in signals
                if signal.cohort_year == year and signal.offer_group == group
            ]
            missing_subgroup.append(
                {
                    "release_code": sources_by_year[year].release_code,
                    "cohort_year": year,
                    "offer_group": group,
                    "rows": len(group_rows),
                    "missing_rows": sum(signal.oar_mean is None for signal in group_rows),
                }
            )

    source_inventory = []
    for year in years:
        source = sources_by_year[year]
        program_rows = len(program_keys_by_year.get(year, set()))
        source_inventory.append(
            {
                "release_code": source.release_code,
                "cohort_year": year,
                "program_rows": program_rows,
                "signal_rows": sum(signal.cohort_year == year for signal in signals),
                "source_columns": source.expected_columns,
                "source_sha256": source.download_sha256,
            }
        )

    eligibility = []
    for year in years:
        year_rows = [row for row in panel if row.feature_cohort_year == year]
        eligibility.append(
            {
                "feature_cohort_year": year,
                "rows": len(year_rows),
                "analytic_eligible_rows": sum(row.analytic_eligible for row in year_rows),
                "public_forecast_eligible_rows": sum(
                    row.public_forecast_eligible for row in year_rows
                ),
                "first_observed_program_rows": sum(row.first_observed_program for row in year_rows),
            }
        )

    rounding_summaries, rounding_discrepancies = _rounding_diagnostics(signals)
    all_signal_programs = {signal.program_key for signal in signals}
    latest_programs = program_keys_by_year.get(years[-1], set()) if years else set()
    cohort_date_normalizations = [
        {
            "release_code": signal.release_code,
            "cohort_year": signal.cohort_year,
            "program_key": signal.program_key,
            "raw_cohort_start": signal.raw_cohort_start,
            "raw_cohort_end": signal.raw_cohort_end,
            "normalized_cohort_start": signal.cohort_start.isoformat(),
            "normalized_cohort_end": signal.cohort_end.isoformat(),
        }
        for signal in sorted(
            (item for item in signals if item.offer_group == "overall"),
            key=lambda item: (item.cohort_year, item.program_key),
        )
    ]
    return {
        "schema_version": 1,
        "source_inventory": source_inventory,
        "annual_transitions": transitions,
        "missing_subgroup_oar": missing_subgroup,
        "eligibility": eligibility,
        "cohort_date_normalizations": cohort_date_normalizations,
        "directory": {
            "release_code": sources_by_year[years[-1]].release_code if years else None,
            "directory_programs": len(directory),
            "matched_latest_programs": len(latest_programs & directory.keys()),
            "directory_only_program_keys": sorted(directory.keys() - latest_programs),
            "historical_programs_without_current_directory": sorted(
                all_signal_programs - directory.keys()
            ),
        },
        "rounding_diagnostics": rounding_summaries,
        "rounding_discrepancies": rounding_discrepancies,
    }


def _array_for_field(rows: tuple[object, ...], field: pa.Field) -> pa.Array:
    return pa.array([getattr(row, field.name) for row in rows], type=field.type)


def canonical_signals_table(signals: tuple[CanonicalSignal, ...]) -> pa.Table:
    """Return the exact canonical signal schema in stable logical order."""
    _validate_canonical_rows(signals)
    group_order = {
        "overall": 0,
        "low": 1,
        "medium": 2,
        "high": 3,
        "hard-to-place": 4,
    }
    ordered: tuple[CanonicalSignal, ...] = tuple(
        sorted(
            signals,
            key=lambda row: (
                row.cohort_year,
                row.program_key,
                group_order[row.offer_group],
            ),
        )
    )
    arrays = [_array_for_field(ordered, field) for field in PROGRAM_SIGNALS_SCHEMA]
    return pa.Table.from_arrays(arrays, schema=PROGRAM_SIGNALS_SCHEMA)


def model_panel_table(rows: tuple[ModelPanelRow, ...]) -> pa.Table:
    """Return the exact model-panel schema in stable logical order."""
    ordered: tuple[ModelPanelRow, ...] = tuple(
        sorted(rows, key=lambda row: (row.feature_cohort_year, row.program_key))
    )
    keys = [(row.program_key, row.feature_cohort_year) for row in rows]
    if len(keys) != len(set(keys)):
        raise BuildError("Model panel program-year keys must be unique.")
    arrays = [_array_for_field(ordered, field) for field in MODEL_PANEL_SCHEMA]
    return pa.Table.from_arrays(arrays, schema=MODEL_PANEL_SCHEMA)


def _write_qa_json(report: dict[str, Any], path: Path) -> None:
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_data_artifacts(
    signals: tuple[CanonicalSignal, ...],
    panel: tuple[ModelPanelRow, ...],
    qa_report: dict[str, Any],
    output_dir: Path,
) -> DataBuildResult:
    """Stage all artifacts before atomically publishing their individual files."""
    signal_table = canonical_signals_table(signals)
    panel_table = model_panel_table(panel)
    output_parent = output_dir.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-staging-", dir=output_parent))
    published_staging_dir = False
    try:
        staged_signals = staging_dir / "program_signals.parquet"
        staged_panel = staging_dir / "model_panel.parquet"
        staged_qa = staging_dir / "qa_report.json"
        pq.write_table(
            signal_table,
            staged_signals,
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )
        pq.write_table(
            panel_table,
            staged_panel,
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )
        _write_qa_json(qa_report, staged_qa)

        if not output_dir.exists():
            os.replace(staging_dir, output_dir)
            published_staging_dir = True
        else:
            if not output_dir.is_dir():
                raise BuildError(f"Output path {output_dir} exists and is not a directory.")
            for filename in ("program_signals.parquet", "model_panel.parquet", "qa_report.json"):
                os.replace(staging_dir / filename, output_dir / filename)
    finally:
        if not published_staging_dir:
            shutil.rmtree(staging_dir, ignore_errors=True)

    return DataBuildResult(
        program_signals_path=output_dir / "program_signals.parquet",
        model_panel_path=output_dir / "model_panel.parquet",
        qa_report_path=output_dir / "qa_report.json",
        program_signal_rows=signal_table.num_rows,
        model_panel_rows=panel_table.num_rows,
    )


def build_cached_data(
    manifest: DataSourceManifest, cache_dir: Path, output_dir: Path
) -> DataBuildResult:
    """Build canonical artifacts from the immutable, checksum-verified source cache."""
    if not manifest.sources:
        raise BuildError("At least one source release is required for a canonical build.")
    sources = tuple(sorted(manifest.sources, key=lambda source: source.cohort_year))
    latest_year = sources[-1].cohort_year
    parsed_signals: list[ProgramSignal] = []
    current_directory: dict[str, DirectoryEntry] | None = None
    for source in sources:
        payload = load_workbook_payload(source, cache_dir)
        sheets = read_workbook_sheets(payload)
        release = parse_offer_acceptance_workbook(manifest, source, sheets)
        parsed_signals.extend(release.signals)
        if source.cohort_year == latest_year:
            current_directory = parse_current_directory(source, sheets)
    if current_directory is None:
        raise BuildError("The latest release directory could not be loaded.")

    canonical = join_current_directory(tuple(parsed_signals), current_directory)
    panel = build_model_panel(canonical, sources)
    qa_report = build_qa_report(canonical, panel, sources, current_directory)
    return write_data_artifacts(canonical, panel, qa_report, output_dir)
