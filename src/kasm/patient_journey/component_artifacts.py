"""Publish a complete component description without rewriting any earlier study."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from kasm.config import load_data_source_manifest
from kasm.data.parse import load_workbook_payload, read_workbook_sheets
from kasm.patient_journey.artifacts import current_patient_journey_build_context
from kasm.patient_journey.component_analysis import analyze_components
from kasm.patient_journey.component_config import (
    ANALYSIS_ID,
    OUTPUT_ROOT,
    ComponentError,
    load_component_config,
    validate_component_destination,
)
from kasm.patient_journey.component_report import render_component_report
from kasm.patient_journey.components import DESCRIPTIONS, ComponentRecord, parse_component_workbook
from kasm.patient_journey.followup_artifacts import (
    _file_hash,
    _json_bytes,
    _load_original_inputs,
    _OriginalInputs,
)
from kasm.patient_journey.followup_config import FollowupConfig
from kasm.patient_journey.ledger import load_methodology_ledger

DEFAULT_CONFIG = Path("configs/patient_journey_v2_followup/outcome_components.yaml")
_FILES = frozenset(
    {
        "components.json",
        "analysis.json",
        "report.md",
        "outcome_components.svg",
        "outcome_components.png",
    }
)


def read_component_inputs(
    root: Path, config_path: Path
) -> tuple[_OriginalInputs, tuple[ComponentRecord, ...], dict[str, object]]:
    """Verify the preserved bundle and raw archive/member before source parsing."""
    config = load_component_config(config_path)
    original = _load_original_inputs(root, FollowupConfig())
    manifest = load_data_source_manifest(root / "configs/data_sources.yaml")
    ledger = load_methodology_ledger(
        root / "configs/patient_journey_v2/methodology.yaml", manifest=manifest
    )
    source = next(s for s in manifest.sources if s.release_code == config.release_code)
    methodology = ledger.release(config.release_code)
    payload = load_workbook_payload(source, root / "data/raw/srtr")
    records = parse_component_workbook(source, methodology, read_workbook_sheets(payload), config)
    metadata: dict[str, object] = {
        "component_source": asdict(source),
        "component_workbook_sha256": sha256(payload).hexdigest(),
        "component_source_sheet": asdict(methodology.metric("patient_outcome").sheet),
        "verified_descriptions": DESCRIPTIONS,
    }
    return original, records, metadata


def _identity(root: Path, config_path: Path) -> dict[str, object]:
    paths = sorted((root / "src/kasm").rglob("*.py"))
    if not paths:
        raise ComponentError("Implementation sources are missing.")
    return {
        "analysis_id": ANALYSIS_ID,
        "component_config_sha256": _file_hash(config_path),
        "component_specification_sha256": _file_hash(
            root / "docs/specs/patient-journey-v2-outcome-components.md"
        ),
        "component_ledger_sha256": _file_hash(root / "docs/patient_journey_v2_component_ledger.md"),
        "dependency_lock_sha256": _file_hash(root / "uv.lock"),
        "project_configuration_sha256": _file_hash(root / "pyproject.toml"),
        "implementation_sha256": {p.relative_to(root).as_posix(): _file_hash(p) for p in paths},
    }


def publish_component_files(
    files: Mapping[str, bytes],
    relative: Path,
    *,
    repository_root: Path,
    provenance: Mapping[str, object],
) -> Path:
    """Stage exact filenames and publish once; never replace an existing directory."""
    destination = validate_component_destination(relative, repository_root=repository_root)
    if set(files) != _FILES or any(
        not isinstance(value, bytes) or not value for value in files.values()
    ):
        raise ComponentError("Component payload file set is incomplete or unexpected.")
    if destination.exists():
        raise ComponentError("Component run already exists; it cannot be overwritten.")
    lock = destination.parent / f".{destination.name}.lock"
    acquired = False
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        validate_component_destination(relative, repository_root=repository_root)
        with lock.open("xb"):
            acquired = True
            with tempfile.TemporaryDirectory(
                prefix=".staging-", dir=destination.parent
            ) as temporary:
                staging = Path(temporary)
                artifacts = {}
                for name, payload in sorted(files.items()):
                    path = staging / name
                    with path.open("xb") as handle:
                        handle.write(payload)
                    digest = sha256(payload).hexdigest()
                    if _file_hash(path) != digest:
                        raise ComponentError(
                            f"Written component payload {name} failed its checksum."
                        )
                    artifacts[name] = {"bytes": len(payload), "sha256": digest}
                manifest = {
                    "schema_version": 1,
                    "analysis_id": ANALYSIS_ID,
                    "status": "complete",
                    "promotion_allowed": False,
                    "future_forecast_available": False,
                    "artifacts": artifacts,
                    "provenance": dict(provenance),
                }
                (staging / "manifest.json").write_bytes(_json_bytes(manifest))
                validate_component_destination(relative, repository_root=repository_root)
                if destination.exists():
                    raise ComponentError("Component run already exists; it cannot be overwritten.")
                os.rename(staging, destination)
    except OSError as exc:
        raise ComponentError(f"Cannot publish component output: {exc}") from exc
    finally:
        if acquired:
            lock.unlink(missing_ok=True)
    return destination


def component_payloads(records: tuple[ComponentRecord, ...]) -> bytes:
    """Save exact published numbers/raw markers with explicit program/cohort identity."""
    return _json_bytes(
        [
            asdict(record)
            | {
                "listing_cohort_start": str(record.listing_cohort_start),
                "listing_cohort_end": str(record.listing_cohort_end),
                "follow_up_end": str(record.follow_up_end),
            }
            for record in records
        ]
    )


def build_components(*, repository_root: Path, config_path: Path = DEFAULT_CONFIG) -> Path:
    """Read original predictions and describe their outcome components in an isolated run."""
    root = repository_root.resolve()
    path = config_path if config_path.is_absolute() else root / config_path
    try:
        config = load_component_config(path)
        original, records, metadata = read_component_inputs(root, path)
        identity = _identity(root, path) | original.provenance | metadata
        run_hash = sha256(_json_bytes(identity)).hexdigest()
        relative = OUTPUT_ROOT / run_hash
        destination = validate_component_destination(relative, repository_root=root)
        if destination.exists():
            raise ComponentError("Component run already exists; it cannot be overwritten.")
        evidence = analyze_components(records, original.rows, original.stored_predictions, config)
        files = render_component_report(evidence) | {
            "components.json": component_payloads(records),
            "analysis.json": _json_bytes(evidence),
        }
        after_original, after_records, after_metadata = read_component_inputs(root, path)
        if (
            identity != _identity(root, path) | after_original.provenance | after_metadata
            or records != after_records
        ):
            raise ComponentError("Inputs or implementation changed during the component run.")
        context = current_patient_journey_build_context(root)
        provenance = identity | {
            "git_commit_sha": context.git_commit_sha,
            "git_worktree_dirty": context.git_worktree_dirty,
            "canonical_build": False,
            "evidence_status": "retrospective_exploratory_followup",
            "build_timestamp_utc": context.build_timestamp_utc.isoformat().replace("+00:00", "Z"),
            "python_version": context.python_version,
            "cohort_timing": {
                field: getattr(config, field)
                for field in (
                    "release_code",
                    "feature_release_code",
                    "listing_cohort_start",
                    "listing_cohort_end",
                    "follow_up_end",
                    "published_value",
                    "published_precision",
                    "months_after_listing",
                )
            },
            "feature_schema": [],
            "model_parameters": {},
            "models_fitted": False,
        }
        return publish_component_files(files, relative, repository_root=root, provenance=provenance)
    except (OSError, ValueError) as exc:
        raise ComponentError(f"Cannot complete outcome-component analysis: {exc}") from exc
