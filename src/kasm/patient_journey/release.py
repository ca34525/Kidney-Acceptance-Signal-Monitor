"""Self-contained offline release bundle for patient-journey V2."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import cast

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from kasm.patient_journey.artifacts import validate_patient_journey_artifacts
from kasm.patient_journey.config import load_patient_journey_config
from kasm.patient_journey.model_artifacts import (
    validate_patient_journey_model_artifacts,
)

PANEL_NAME = "patient_journey_panel.parquet"
SAFETY_NAME = "safety_measures.parquet"
PREDICTIONS_NAME = "predictions.parquet"
EVALUATION_NAME = "evaluation.json"
MANIFEST_NAME = "release_manifest.json"
_ASSET_NAMES = {
    "panel": PANEL_NAME,
    "safety": SAFETY_NAME,
    "predictions": PREDICTIONS_NAME,
    "evaluation": EVALUATION_NAME,
}
_EXACT_NAMES = frozenset((*_ASSET_NAMES.values(), MANIFEST_NAME))
_MAX_TRACKED_BYTES = 5 * 1024 * 1024
_SHARED_PROVENANCE_FIELDS = (
    "analysis_id",
    "dependency_lock_sha256",
    "experiment_config_sha256",
    "methodology_config_sha256",
    "source_manifest_sha256",
    "source_sha256",
    "git_commit_sha",
    "git_worktree_dirty",
    "python_version",
)


class PatientJourneyReleaseError(ValueError):
    """Raised when the offline V2 bundle is incomplete, promoted, or tampered."""


@dataclass(frozen=True)
class PatientJourneyReleaseResult:
    """Validated paths and content identity for one V2 release bundle."""

    output_directory: Path
    panel_path: Path
    safety_path: Path
    predictions_path: Path
    evaluation_path: Path
    manifest_path: Path
    file_count: int
    total_bytes: int
    bundle_content_sha256: str


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _record(path: Path) -> dict[str, object]:
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": _file_sha256(path)}


def _content_identity(records: Mapping[str, Mapping[str, object]]) -> str:
    normalized = {
        key: {"bytes": value["bytes"], "sha256": value["sha256"]}
        for key, value in sorted(records.items())
    }
    return sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _validate_nonpromotion(provenance: Mapping[str, object]) -> None:
    if (
        provenance.get("analysis_id") != "kidney_patient_journey_v2"
        or provenance.get("promotion_allowed") is not False
        or provenance.get("promoted_model") is not None
        or provenance.get("evidence_status") != "retrospective_exploratory_feasibility"
    ):
        raise PatientJourneyReleaseError(
            "Patient-journey V2 release provenance must preserve the frozen nonpromotion state."
        )


def _parquet_provenance(path: Path, *, label: str) -> Mapping[str, object]:
    try:
        metadata = pq.read_schema(path).metadata or {}
        value: object = json.loads(metadata[b"kasm_provenance"])
    except (OSError, ValueError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        raise PatientJourneyReleaseError(
            f"V2 release {label} generation provenance is invalid."
        ) from exc
    if not isinstance(value, dict):
        raise PatientJourneyReleaseError(
            f"V2 release {label} generation provenance must be an object."
        )
    return cast(Mapping[str, object], value)


def _evaluation_payload(path: Path) -> Mapping[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PatientJourneyReleaseError("V2 release evaluation is unreadable.") from exc
    if not isinstance(value, dict):
        raise PatientJourneyReleaseError("V2 release evaluation must be a JSON object.")
    return cast(Mapping[str, object], value)


def _validate_generation_bindings(
    output_dir: Path,
    *,
    provenance: Mapping[str, object],
    records: Mapping[str, Mapping[str, object]],
) -> None:
    panel_provenance = _parquet_provenance(output_dir / PANEL_NAME, label="panel")
    safety_provenance = _parquet_provenance(output_dir / SAFETY_NAME, label="safety")
    prediction_provenance = _parquet_provenance(output_dir / PREDICTIONS_NAME, label="predictions")
    if panel_provenance != safety_provenance:
        raise PatientJourneyReleaseError(
            "V2 release panel and safety assets are from different generations."
        )
    panel_hash = records["panel"].get("sha256")
    safety_hash = records["safety"].get("sha256")
    if (
        provenance.get("processed_panel_sha256") != panel_hash
        or provenance.get("processed_safety_sha256") != safety_hash
        or prediction_provenance.get("processed_panel_sha256") != panel_hash
        or prediction_provenance.get("processed_safety_sha256") != safety_hash
    ):
        raise PatientJourneyReleaseError(
            "V2 release processed assets disagree with the modeling generation."
        )
    model_identity = _content_identity(
        {
            "predictions": records["predictions"],
            "evaluation": records["evaluation"],
        }
    )
    if provenance.get("modeling_artifact_set_sha256") != model_identity:
        raise PatientJourneyReleaseError(
            "V2 release model assets disagree with the modeling generation."
        )
    if any(
        panel_provenance.get(field) != provenance.get(field) for field in _SHARED_PROVENANCE_FIELDS
    ):
        raise PatientJourneyReleaseError(
            "V2 release processed provenance disagrees with the release generation."
        )
    if any(provenance.get(key) != value for key, value in prediction_provenance.items()):
        raise PatientJourneyReleaseError(
            "V2 release prediction provenance disagrees with the release generation."
        )
    _validate_nonpromotion(_evaluation_payload(output_dir / EVALUATION_NAME))


def _publish(staging: Path, output_dir: Path) -> None:
    backup = output_dir.parent / f".{output_dir.name}-backup"
    if backup.exists():
        shutil.rmtree(backup)
    if not output_dir.exists():
        os.replace(staging, output_dir)
        return
    os.replace(output_dir, backup)
    try:
        os.replace(staging, output_dir)
    except Exception:
        os.replace(backup, output_dir)
        raise
    shutil.rmtree(backup)


def write_patient_journey_release_directory(
    *,
    assets: Mapping[str, Path],
    output_dir: Path,
    provenance: Mapping[str, object],
) -> PatientJourneyReleaseResult:
    """Copy the four trusted assets into one atomic, hash-bound offline bundle."""
    if set(assets) != set(_ASSET_NAMES):
        raise PatientJourneyReleaseError("V2 release inputs must contain exactly four assets.")
    _validate_nonpromotion(provenance)
    for key, path in assets.items():
        if not path.is_file():
            raise PatientJourneyReleaseError(f"V2 release input {key!r} is missing.")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-staging-", dir=output_dir.parent))
    published = False
    try:
        for key, filename in _ASSET_NAMES.items():
            shutil.copyfile(assets[key], staging / filename)
        records = {key: _record(staging / filename) for key, filename in _ASSET_NAMES.items()}
        total_bytes = sum(cast(int, record["bytes"]) for record in records.values())
        if total_bytes >= _MAX_TRACKED_BYTES:
            raise PatientJourneyReleaseError("V2 release assets must remain smaller than 5 MB.")
        manifest = {
            "schema_version": 1,
            "status": "complete",
            "artifacts": records,
            "file_count": len(records),
            "total_bytes": total_bytes,
            "bundle_content_sha256": _content_identity(records),
            "provenance": dict(provenance),
            "display_contract": {
                "default_v1_app_unchanged": True,
                "national_leaderboard_allowed": False,
                "patient_or_organ_input_allowed": False,
                "future_forecast_available": False,
                "target_officially_risk_adjusted": False,
                "safety_context_separate_from_patient_journey_outcome": True,
            },
        }
        _write_json(staging / MANIFEST_NAME, manifest)
        validate_patient_journey_release_directory(staging)
        _publish(staging, output_dir)
        published = True
    finally:
        if not published:
            shutil.rmtree(staging, ignore_errors=True)
    return validate_patient_journey_release_directory(output_dir)


def validate_patient_journey_release_directory(
    output_dir: Path,
) -> PatientJourneyReleaseResult:
    """Validate the release using only its own files for offline app startup."""
    if not output_dir.is_dir() or {path.name for path in output_dir.iterdir()} != _EXACT_NAMES:
        raise PatientJourneyReleaseError("V2 release does not contain the exact trusted file set.")
    manifest_path = output_dir / MANIFEST_NAME
    try:
        manifest: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PatientJourneyReleaseError("V2 release manifest is unreadable.") from exc
    if not isinstance(manifest, dict):
        raise PatientJourneyReleaseError("V2 release manifest must be a JSON object.")
    if manifest.get("schema_version") != 1 or manifest.get("status") != "complete":
        raise PatientJourneyReleaseError("V2 release manifest is incomplete or unsupported.")
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        raise PatientJourneyReleaseError("V2 release provenance is invalid.")
    _validate_nonpromotion(provenance)
    display = manifest.get("display_contract")
    expected_display = {
        "default_v1_app_unchanged": True,
        "national_leaderboard_allowed": False,
        "patient_or_organ_input_allowed": False,
        "future_forecast_available": False,
        "target_officially_risk_adjusted": False,
        "safety_context_separate_from_patient_journey_outcome": True,
    }
    if display != expected_display:
        raise PatientJourneyReleaseError("V2 release display contract disagrees.")
    records = manifest.get("artifacts")
    if not isinstance(records, dict) or set(records) != set(_ASSET_NAMES):
        raise PatientJourneyReleaseError("V2 release artifact records are incomplete.")
    typed_records: dict[str, Mapping[str, object]] = {}
    for key, filename in _ASSET_NAMES.items():
        record = records.get(key)
        path = output_dir / filename
        if not isinstance(record, dict):
            raise PatientJourneyReleaseError("V2 release artifact record is invalid.")
        if (
            record.get("path") != filename
            or record.get("bytes") != path.stat().st_size
            or record.get("sha256") != _file_sha256(path)
        ):
            raise PatientJourneyReleaseError(f"V2 release {key} checksum or size disagrees.")
        typed_records[key] = record
    total_bytes = sum(cast(int, record["bytes"]) for record in typed_records.values())
    identity = _content_identity(typed_records)
    if (
        manifest.get("file_count") != len(typed_records)
        or manifest.get("total_bytes") != total_bytes
        or manifest.get("bundle_content_sha256") != identity
    ):
        raise PatientJourneyReleaseError("V2 release aggregate checksum or size disagrees.")
    _validate_generation_bindings(
        output_dir,
        provenance=provenance,
        records=typed_records,
    )
    return PatientJourneyReleaseResult(
        output_directory=output_dir,
        panel_path=output_dir / PANEL_NAME,
        safety_path=output_dir / SAFETY_NAME,
        predictions_path=output_dir / PREDICTIONS_NAME,
        evaluation_path=output_dir / EVALUATION_NAME,
        manifest_path=manifest_path,
        file_count=len(typed_records),
        total_bytes=total_bytes,
        bundle_content_sha256=identity,
    )


def _resolved(path: Path, root: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def build_patient_journey_release_bundle(
    *,
    repository_root: Path,
    source_manifest_path: Path,
    experiment_config_path: Path,
    methodology_path: Path,
    lock_path: Path,
) -> PatientJourneyReleaseResult:
    """Publish byte-identical trusted processed/model assets to the V2 release root."""
    root = repository_root.resolve()
    config = load_patient_journey_config(
        _resolved(experiment_config_path, root),
        repository_root=root,
    )
    processed = validate_patient_journey_artifacts(
        _resolved(config.paths.processed_dir, root),
        repository_root=root,
        source_manifest_path=source_manifest_path,
        experiment_config_path=experiment_config_path,
        methodology_path=methodology_path,
        lock_path=lock_path,
    )
    modeling = validate_patient_journey_model_artifacts(
        repository_root=root,
        source_manifest_path=source_manifest_path,
        experiment_config_path=experiment_config_path,
        methodology_path=methodology_path,
        lock_path=lock_path,
    )
    try:
        evidence: object = json.loads(modeling.evaluation_path.read_text(encoding="utf-8"))
        model_manifest: object = json.loads(modeling.manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PatientJourneyReleaseError("Trusted model evidence is unreadable.") from exc
    if not isinstance(evidence, dict) or not isinstance(model_manifest, dict):
        raise PatientJourneyReleaseError("Trusted model evidence must be JSON objects.")
    model_provenance = model_manifest.get("provenance")
    if not isinstance(model_provenance, dict):
        raise PatientJourneyReleaseError("Trusted model provenance is invalid.")
    provenance = {
        **model_provenance,
        "processed_artifact_set_sha256": processed.artifact_set_sha256,
        "modeling_artifact_set_sha256": modeling.artifact_set_sha256,
        "promotion_allowed": evidence.get("promotion_allowed"),
        "promoted_model": evidence.get("promoted_model"),
        "evidence_status": evidence.get("evidence_status"),
    }
    output_dir = _resolved(config.paths.release_dir, root)
    if output_dir == root or root not in output_dir.parents:
        raise PatientJourneyReleaseError("Configured V2 release must remain inside the repository.")
    return write_patient_journey_release_directory(
        assets={
            "panel": processed.panel_path,
            "safety": processed.safety_path,
            "predictions": modeling.predictions_path,
            "evaluation": modeling.evaluation_path,
        },
        output_dir=output_dir,
        provenance=provenance,
    )
