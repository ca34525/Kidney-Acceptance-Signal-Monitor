"""Pure historical-view services over trusted canonical Parquet artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal, cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from kasm.data.build import MODEL_PANEL_SCHEMA, PROGRAM_SIGNALS_SCHEMA

_SUBGROUPS: tuple[tuple[str, str], ...] = (
    ("low", "Low KDRI"),
    ("medium", "Medium KDRI"),
    ("high", "High KDRI"),
    ("hard-to-place", "Hard-to-place"),
)


class HistoricalDataError(ValueError):
    """Raised when view data are missing or violate the trusted artifact contract."""


@dataclass(frozen=True)
class HistoricalArtifacts:
    """Validated, immutable inputs to the historical view layer."""

    signals: pa.Table
    panel: pa.Table
    artifact_version: str


@dataclass(frozen=True)
class ProgramOption:
    """A display label paired with the canonical composite program identity."""

    program_key: str
    label: str


@dataclass(frozen=True)
class HistoricalPoint:
    """One published overall OAR and its source context."""

    cohort_year: int
    cohort_start: date
    cohort_end: date
    published_value: str
    published_precision: Literal["month", "day"]
    publication_display: str
    offers: int | None
    expected_acceptances: float | None
    oar_mean: float | None
    oar_lower: float | None
    oar_upper: float | None
    source_url: str


@dataclass(frozen=True)
class OverallStatus:
    """Mechanical interpretation of the latest published credible interval."""

    cohort_year: int
    label: str


@dataclass(frozen=True)
class VolumeContext:
    """Latest overall source-volume values without missing-to-zero coercion."""

    cohort_year: int
    offers: int | None
    expected_acceptances: float | None
    offers_display: str
    expected_acceptances_display: str


@dataclass(frozen=True)
class SubgroupRow:
    """Latest donor-stratum values and explicit display states."""

    offer_group: str
    label: str
    offers: int | None
    expected_acceptances: float | None
    oar_mean: float | None
    oar_lower: float | None
    oar_upper: float | None
    offers_display: str
    expected_acceptances_display: str
    oar_display: str


@dataclass(frozen=True)
class ForecastEligibility:
    """Materialized public eligibility from the latest model-panel row."""

    feature_cohort_year: int
    target_cohort_year: int
    eligible: bool


SignalRow = dict[str, object]


def _artifact_hash(paths: tuple[Path, ...]) -> str:
    digest = sha256()
    for path in paths:
        with path.open("rb") as artifact:
            for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _load_exact_parquet(path: Path, expected_schema: pa.Schema) -> pa.Table:
    if not path.is_file():
        raise HistoricalDataError(f"Trusted artifact is missing: {path.name}.")
    try:
        table = pq.read_table(path)
    except (OSError, pa.ArrowException) as exc:
        raise HistoricalDataError(f"Trusted artifact {path.name} could not be read: {exc}") from exc
    if not table.schema.equals(expected_schema, check_metadata=True):
        raise HistoricalDataError(
            f"Trusted artifact {path.name} does not match the canonical schema."
        )
    return table


def load_historical_artifacts(artifact_dir: Path) -> HistoricalArtifacts:
    """Load the two canonical read-only app inputs after exact schema validation."""
    signals_path = artifact_dir / "program_signals.parquet"
    panel_path = artifact_dir / "model_panel.parquet"
    signals = _load_exact_parquet(signals_path, PROGRAM_SIGNALS_SCHEMA)
    panel = _load_exact_parquet(panel_path, MODEL_PANEL_SCHEMA)
    return HistoricalArtifacts(
        signals=signals,
        panel=panel,
        artifact_version=_artifact_hash((signals_path, panel_path))[:12],
    )


def _table_rows(table: pa.Table) -> tuple[SignalRow, ...]:
    return tuple(cast(list[SignalRow], table.to_pylist()))


def _required_text(row: SignalRow, field: str) -> str:
    value = row[field]
    if not isinstance(value, str) or not value:
        raise HistoricalDataError(f"Trusted field {field!r} must be nonempty text.")
    return value


def _required_int(row: SignalRow, field: str) -> int:
    value = row[field]
    if isinstance(value, bool) or not isinstance(value, int):
        raise HistoricalDataError(f"Trusted field {field!r} must be an integer.")
    return value


def _optional_int(row: SignalRow, field: str) -> int | None:
    value = row[field]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise HistoricalDataError(f"Trusted field {field!r} must be an integer or null.")
    return value


def _optional_float(row: SignalRow, field: str) -> float | None:
    value = row[field]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, float | int):
        raise HistoricalDataError(f"Trusted field {field!r} must be numeric or null.")
    return float(value)


def _required_date(row: SignalRow, field: str) -> date:
    value = row[field]
    if not isinstance(value, date):
        raise HistoricalDataError(f"Trusted field {field!r} must be a date.")
    return value


def _precision(row: SignalRow, field: str) -> Literal["month", "day"]:
    value = row[field]
    if value not in {"month", "day"}:
        raise HistoricalDataError(f"Trusted field {field!r} must be 'month' or 'day'.")
    return cast(Literal["month", "day"], value)


def format_publication_value(value: str, precision: Literal["month", "day"]) -> str:
    """Render source precision faithfully, without inventing a publication day."""
    try:
        if precision == "month":
            parsed = datetime.strptime(value, "%Y-%m")
            return parsed.strftime("%B %Y")
        parsed_day = date.fromisoformat(value)
    except ValueError as exc:
        raise HistoricalDataError(
            f"Publication value {value!r} does not match {precision!r} precision."
        ) from exc
    return f"{parsed_day.strftime('%B')} {parsed_day.day}, {parsed_day.year}"


def _latest_overall_row(artifacts: HistoricalArtifacts, program_key: str) -> SignalRow:
    rows = [
        row
        for row in _table_rows(artifacts.signals)
        if row["program_key"] == program_key and row["offer_group"] == "overall"
    ]
    if not rows:
        raise HistoricalDataError(f"Program {program_key!r} has no overall history.")
    return max(rows, key=lambda row: _required_int(row, "cohort_year"))


def program_options(artifacts: HistoricalArtifacts) -> tuple[ProgramOption, ...]:
    """Return deterministic display-only labels with composite keys as values."""
    latest_by_program: dict[str, SignalRow] = {}
    for row in _table_rows(artifacts.signals):
        if row["offer_group"] != "overall":
            continue
        program_key = _required_text(row, "program_key")
        current = latest_by_program.get(program_key)
        if current is None or _required_int(row, "cohort_year") > _required_int(
            current, "cohort_year"
        ):
            latest_by_program[program_key] = row

    choices: list[ProgramOption] = []
    for program_key, row in latest_by_program.items():
        center_name = _required_text(row, "center_name")
        city = row["city"] if isinstance(row["city"], str) else None
        state = row["state"] if isinstance(row["state"], str) else None
        location = ", ".join(value for value in (city, state) if value)
        label = f"{center_name} — {location}" if location else center_name
        choices.append(ProgramOption(program_key=program_key, label=label))
    return tuple(sorted(choices, key=lambda choice: (choice.label.casefold(), choice.program_key)))


def overall_history(
    artifacts: HistoricalArtifacts, program_key: str
) -> tuple[HistoricalPoint, ...]:
    """Return chronological published overall signals for one composite program key."""
    rows = [
        row
        for row in _table_rows(artifacts.signals)
        if row["program_key"] == program_key and row["offer_group"] == "overall"
    ]
    if not rows:
        raise HistoricalDataError(f"Program {program_key!r} has no overall history.")
    points: list[HistoricalPoint] = []
    for row in sorted(rows, key=lambda item: _required_int(item, "cohort_year")):
        published_value = _required_text(row, "published_value")
        published_precision = _precision(row, "published_precision")
        points.append(
            HistoricalPoint(
                cohort_year=_required_int(row, "cohort_year"),
                cohort_start=_required_date(row, "cohort_start"),
                cohort_end=_required_date(row, "cohort_end"),
                published_value=published_value,
                published_precision=published_precision,
                publication_display=format_publication_value(published_value, published_precision),
                offers=_optional_int(row, "offers"),
                expected_acceptances=_optional_float(row, "expected_acceptances"),
                oar_mean=_optional_float(row, "oar_mean"),
                oar_lower=_optional_float(row, "oar_lower"),
                oar_upper=_optional_float(row, "oar_upper"),
                source_url=_required_text(row, "source_url"),
            )
        )
    return tuple(points)


def interval_status(lower: float | None, upper: float | None) -> str:
    """Apply only the specification's descriptive, pointwise interval labels."""
    if lower is None or upper is None:
        return "Not reported"
    if upper < 1:
        return "95% interval entirely below 1"
    if lower > 1:
        return "95% interval entirely above 1"
    return "95% interval includes 1"


def latest_overall_status(artifacts: HistoricalArtifacts, program_key: str) -> OverallStatus:
    """Describe the latest published SRTR interval without regulatory interpretation."""
    latest = _latest_overall_row(artifacts, program_key)
    return OverallStatus(
        cohort_year=_required_int(latest, "cohort_year"),
        label=interval_status(
            _optional_float(latest, "oar_lower"), _optional_float(latest, "oar_upper")
        ),
    )


def _format_count(value: int | None) -> str:
    return "Not reported" if value is None else f"{value:,}"


def _format_expected(value: float | None) -> str:
    return "Not reported" if value is None else f"{value:,.2f}"


def _format_oar(mean: float | None, lower: float | None, upper: float | None) -> str:
    if mean is None:
        return "Not reported"
    if lower is None or upper is None:
        return f"{mean:.2f}"
    return f"{mean:.2f} ({lower:.2f}–{upper:.2f})"


def latest_volume_context(artifacts: HistoricalArtifacts, program_key: str) -> VolumeContext:
    """Return the latest overall offer and expected-acceptance context."""
    latest = _latest_overall_row(artifacts, program_key)
    offers = _optional_int(latest, "offers")
    expected = _optional_float(latest, "expected_acceptances")
    return VolumeContext(
        cohort_year=_required_int(latest, "cohort_year"),
        offers=offers,
        expected_acceptances=expected,
        offers_display=_format_count(offers),
        expected_acceptances_display=_format_expected(expected),
    )


def latest_subgroup_rows(
    artifacts: HistoricalArtifacts, program_key: str
) -> tuple[SubgroupRow, ...]:
    """Return a fixed-order latest subgroup display with explicit missing states."""
    latest_year = _required_int(_latest_overall_row(artifacts, program_key), "cohort_year")
    by_group = {
        _required_text(row, "offer_group"): row
        for row in _table_rows(artifacts.signals)
        if row["program_key"] == program_key
        and _required_int(row, "cohort_year") == latest_year
        and row["offer_group"] != "overall"
    }
    result: list[SubgroupRow] = []
    for offer_group, label in _SUBGROUPS:
        row = by_group.get(offer_group)
        offers = _optional_int(row, "offers") if row is not None else None
        expected = _optional_float(row, "expected_acceptances") if row is not None else None
        mean = _optional_float(row, "oar_mean") if row is not None else None
        lower = _optional_float(row, "oar_lower") if row is not None else None
        upper = _optional_float(row, "oar_upper") if row is not None else None
        result.append(
            SubgroupRow(
                offer_group=offer_group,
                label=label,
                offers=offers,
                expected_acceptances=expected,
                oar_mean=mean,
                oar_lower=lower,
                oar_upper=upper,
                offers_display=_format_count(offers),
                expected_acceptances_display=_format_expected(expected),
                oar_display=_format_oar(mean, lower, upper),
            )
        )
    return tuple(result)


def latest_public_forecast_eligibility(
    artifacts: HistoricalArtifacts, program_key: str
) -> ForecastEligibility:
    """Read, rather than derive, the latest trusted public-forecast eligibility flag."""
    rows = [row for row in _table_rows(artifacts.panel) if row["program_key"] == program_key]
    if not rows:
        raise HistoricalDataError(f"Program {program_key!r} has no model-panel row.")
    latest = max(rows, key=lambda row: _required_int(row, "feature_cohort_year"))
    eligible = latest["public_forecast_eligible"]
    if not isinstance(eligible, bool):
        raise HistoricalDataError(
            "Trusted field 'public_forecast_eligible' must be a materialized boolean."
        )
    return ForecastEligibility(
        feature_cohort_year=_required_int(latest, "feature_cohort_year"),
        target_cohort_year=_required_int(latest, "target_cohort_year"),
        eligible=eligible,
    )
