"""Prepare saved V2 history and evaluation results for the optional offline view.

Load the verified release bundle and select one program by its code/type key.
The view uses historical predictions already in that bundle. Missing values
stay visibly unreported, and safety measures keep their separate timing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from kasm.patient_journey.model_artifacts import PATIENT_JOURNEY_PREDICTION_SCHEMA
from kasm.patient_journey.panel import (
    PATIENT_JOURNEY_PANEL_SCHEMA,
    PATIENT_JOURNEY_SAFETY_SCHEMA,
)
from kasm.patient_journey.release import (
    PatientJourneyReleaseError,
    PatientJourneyReleaseResult,
    validate_patient_journey_release_directory,
)


class PatientJourneyProductError(ValueError):
    """Raised when an offline V2 release cannot support the product view."""


@dataclass(frozen=True)
class PatientJourneyProduct:
    """Trusted in-memory V2 release content."""

    release: PatientJourneyReleaseResult
    panel: pa.Table
    safety: pa.Table
    predictions: pa.Table
    evaluation: dict[str, object]
    manifest: dict[str, object]


@dataclass(frozen=True)
class ProgramOption:
    """Stable program selector value with a display-only label."""

    program_key: str
    label: str


def reported_value(value: object, *, digits: int = 1) -> str:
    """Display missing values as 'Not reported' and preserve a reported zero."""
    if value is None:
        return "Not reported"
    if isinstance(value, int | float):
        return f"{float(value):.{digits}f}"
    return str(value)


def published_date_text(value: object) -> str:
    """Render a date without inventing precision for missing values."""
    if value is None:
        return "Not reported"
    if not isinstance(value, date):
        raise PatientJourneyProductError("Published date value must be a date or null.")
    return value.isoformat()


def publication_value_text(value: object, precision: object) -> str:
    """Render a source publication value without inventing day precision."""
    if value is None:
        return "Not reported"
    if not isinstance(value, str) or precision not in {"month", "day"}:
        raise PatientJourneyProductError("Publication value or precision is invalid.")
    try:
        if precision == "month":
            year, month = (int(part) for part in value.split("-"))
            if not 1 <= month <= 12:
                raise ValueError
            return f"{month:02d}/{year:04d}"
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise PatientJourneyProductError("Publication value disagrees with its precision.") from exc


def measurement_segments_text(value: object) -> str:
    """Show each included date span separately so excluded periods remain visible."""
    if not isinstance(value, str):
        raise PatientJourneyProductError("Measurement segments must be JSON text.")
    try:
        segments: object = json.loads(value)
    except json.JSONDecodeError as exc:
        raise PatientJourneyProductError("Measurement segments are invalid JSON.") from exc
    if not isinstance(segments, list) or not segments:
        raise PatientJourneyProductError("Measurement segments must be a non-empty list.")
    rendered: list[str] = []
    for segment in segments:
        if not isinstance(segment, dict):
            raise PatientJourneyProductError("Measurement segment must be an object.")
        start = segment.get("start")
        end = segment.get("end")
        if not isinstance(start, str) or not isinstance(end, str):
            raise PatientJourneyProductError("Measurement segment dates must be text.")
        try:
            start_text = date.fromisoformat(start).isoformat()
            end_text = date.fromisoformat(end).isoformat()
        except ValueError as exc:
            raise PatientJourneyProductError("Measurement segment dates are invalid.") from exc
        rendered.append(f"{start_text} to {end_text}")
    return "; ".join(rendered)


def _read_json_object(path: Path, context: str) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PatientJourneyProductError(f"{context} is unreadable.") from exc
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PatientJourneyProductError(f"{context} must be a JSON object.")
    return cast(dict[str, object], value)


def load_patient_journey_product(release_dir: Path) -> PatientJourneyProduct:
    """Load and schema-check the self-contained release without network or raw data."""
    try:
        release = validate_patient_journey_release_directory(release_dir)
        panel = pq.read_table(release.panel_path)
        safety = pq.read_table(release.safety_path)
        predictions = pq.read_table(release.predictions_path)
    except (PatientJourneyReleaseError, OSError, ValueError) as exc:
        raise PatientJourneyProductError(f"Patient-journey release is invalid: {exc}") from exc
    expected = (
        (panel, PATIENT_JOURNEY_PANEL_SCHEMA, "panel"),
        (safety, PATIENT_JOURNEY_SAFETY_SCHEMA, "safety"),
        (predictions, PATIENT_JOURNEY_PREDICTION_SCHEMA, "predictions"),
    )
    for table, schema, label in expected:
        if table.schema.remove_metadata() != schema:
            raise PatientJourneyProductError(f"Patient-journey {label} schema disagrees.")
    evaluation = _read_json_object(release.evaluation_path, "Patient-journey evaluation")
    manifest = _read_json_object(release.manifest_path, "Patient-journey manifest")
    if (
        evaluation.get("promotion_allowed") is not False
        or evaluation.get("promoted_model") is not None
        or evaluation.get("evidence_status") != "retrospective_exploratory_feasibility"
    ):
        raise PatientJourneyProductError("Patient-journey evaluation lost its nonpromotion state.")
    return PatientJourneyProduct(
        release=release,
        panel=panel,
        safety=safety,
        predictions=predictions,
        evaluation=evaluation,
        manifest=manifest,
    )


def program_options(product: PatientJourneyProduct) -> tuple[ProgramOption, ...]:
    """Build alphabetical selector labels without exposing identity as model features."""
    latest: dict[str, dict[str, object]] = {}
    for row in product.panel.select(
        ["program_key", "center_name", "city", "state", "feature_release_code"]
    ).to_pylist():
        key = cast(str, row["program_key"])
        if key not in latest or cast(str, row["feature_release_code"]) > cast(
            str, latest[key]["feature_release_code"]
        ):
            latest[key] = row
    options: list[ProgramOption] = []
    for key, row in latest.items():
        name = cast(str, row["center_name"])
        location = ", ".join(
            cast(str, value) for value in (row.get("city"), row.get("state")) if value
        )
        label = f"{name} — {location} ({key})" if location else f"{name} ({key})"
        options.append(ProgramOption(program_key=key, label=label))
    return tuple(sorted(options, key=lambda option: (option.label.casefold(), option.program_key)))


def _program_rows(table: pa.Table, program_key: str) -> pa.Table:
    if not program_key:
        raise PatientJourneyProductError("Program selection cannot be empty.")
    return table.filter(pc.equal(table["program_key"], pa.scalar(program_key)))


def program_panel(product: PatientJourneyProduct, program_key: str) -> pa.Table:
    """Return chronological patient-journey and feature context for one program."""
    table = _program_rows(product.panel, program_key)
    if table.num_rows == 0:
        raise PatientJourneyProductError(f"Program {program_key!r} is absent from the panel.")
    return table.sort_by([("target_listing_cohort_start", "ascending")])


def program_predictions(product: PatientJourneyProduct, program_key: str) -> pa.Table:
    """Return evaluated historical predictions only; no future row can be created here."""
    return _program_rows(product.predictions, program_key).sort_by(
        [("target_release_code", "ascending")]
    )


def program_safety(product: PatientJourneyProduct, program_key: str) -> pa.Table:
    """Return separately timed safety context for one program."""
    return _program_rows(product.safety, program_key).sort_by([("measurement_end", "ascending")])
