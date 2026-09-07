"""Read the preserved V2 release and publish a separate complete follow-up once.

No original build command runs here. Source identities are checked before the
panel is used, and the writer permits only the agreed ignored follow-up root.
The manifest distinguishes the original study's lock from this build's lock.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import cast

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from kasm.patient_journey.artifacts import current_patient_journey_build_context
from kasm.patient_journey.config import PatientJourneyConfig, load_patient_journey_config
from kasm.patient_journey.followup_analysis import evaluate_followup
from kasm.patient_journey.followup_config import (
    ANALYSIS_ID,
    OUTPUT_ROOT,
    FollowupConfig,
    load_followup_config,
    validate_followup_config,
    validate_followup_destination,
)
from kasm.patient_journey.followup_report import render_followup_report
from kasm.patient_journey.model_artifacts import (
    PATIENT_JOURNEY_PREDICTION_SCHEMA,
    patient_journey_prediction_table,
)
from kasm.patient_journey.panel import PATIENT_JOURNEY_PANEL_SCHEMA
from kasm.patient_journey.release import (
    PatientJourneyReleaseError,
    validate_patient_journey_release_directory,
)

DEFAULT_CONFIG = Path("configs/patient_journey_v2_followup/experiment.yaml")
_ORIGINAL_CONFIG = Path("configs/patient_journey_v2/experiment.yaml")
_FILES = frozenset(
    {
        "predictions.parquet",
        "evaluation.json",
        "report.md",
        "report_counts.svg",
        "model_errors.svg",
        "report_counts.png",
        "model_errors.png",
    }
)


class FollowupArtifactError(ValueError):
    """Raised when inputs cannot be trusted or a complete run cannot be published."""


@dataclass(frozen=True)
class _OriginalInputs:
    rows: tuple[Mapping[str, object], ...]
    stored_predictions: tuple[Mapping[str, object], ...]
    config: PatientJourneyConfig
    provenance: dict[str, object]


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _file_hash(path: Path) -> str:
    try:
        return sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise FollowupArtifactError(f"Cannot verify input identity for {path}: {exc}") from exc


def _load_original_inputs(root: Path, config: FollowupConfig) -> _OriginalInputs:
    validate_followup_config(config)
    try:
        release = validate_patient_journey_release_directory(root / "artifacts/patient_journey_v2")
        if release.bundle_content_sha256 != config.original_bundle_sha256:
            raise FollowupArtifactError("The original bundle identity changed.")
        manifest = json.loads(release.manifest_path.read_text(encoding="utf-8"))
        original_provenance = manifest["provenance"]
        bindings = {
            "experiment_config_sha256": _ORIGINAL_CONFIG,
            "source_manifest_sha256": Path("configs/data_sources.yaml"),
            "methodology_config_sha256": Path("configs/patient_journey_v2/methodology.yaml"),
        }
        for field, relative in bindings.items():
            if _file_hash(root / relative) != original_provenance[field]:
                raise FollowupArtifactError(f"The original {field} binding changed.")
        if original_provenance["experiment_config_sha256"] != config.original_experiment_sha256:
            raise FollowupArtifactError("The original experiment identity changed.")
        original = load_patient_journey_config(root / _ORIGINAL_CONFIG, repository_root=root)
        panel = pq.read_table(release.panel_path)
        predictions = pq.read_table(release.predictions_path)
        if (
            panel.schema.remove_metadata() != PATIENT_JOURNEY_PANEL_SCHEMA
            or predictions.schema.remove_metadata() != PATIENT_JOURNEY_PREDICTION_SCHEMA
        ):
            raise FollowupArtifactError("The original panel or prediction schema changed.")
    except (OSError, ValueError, KeyError, TypeError, PatientJourneyReleaseError) as exc:
        raise FollowupArtifactError(f"Cannot use the preserved original V2 inputs: {exc}") from exc
    provenance = {
        "original_bundle_sha256": release.bundle_content_sha256,
        "original_release_manifest_sha256": _file_hash(release.manifest_path),
        "original_artifacts": manifest["artifacts"],
        "original_experiment_sha256": original_provenance["experiment_config_sha256"],
        "original_dependency_lock_sha256": original_provenance["dependency_lock_sha256"],
        "original_git_commit_sha": original_provenance["git_commit_sha"],
        "source_sha256": original_provenance["source_sha256"],
        "source_manifest_sha256": original_provenance["source_manifest_sha256"],
        "methodology_config_sha256": original_provenance["methodology_config_sha256"],
    }
    return _OriginalInputs(
        tuple(panel.to_pylist()), tuple(predictions.to_pylist()), original, provenance
    )


def _implementation_identity(root: Path, config_path: Path) -> dict[str, object]:
    # Include imported production helpers, not only the new orchestration file.
    paths = sorted((root / "src/kasm").rglob("*.py"))
    if not paths:
        raise FollowupArtifactError("Implementation sources are missing from the repository.")
    return {
        "analysis_id": ANALYSIS_ID,
        "followup_config_sha256": _file_hash(config_path),
        "followup_specification_sha256": _file_hash(
            root / "docs/specs/patient-journey-v2-followup.md"
        ),
        "dependency_lock_sha256": _file_hash(root / "uv.lock"),
        "project_configuration_sha256": _file_hash(root / "pyproject.toml"),
        "implementation_sha256": {p.relative_to(root).as_posix(): _file_hash(p) for p in paths},
    }


def _cohort_timing(rows: tuple[Mapping[str, object], ...]) -> list[dict[str, object]]:
    fields = (
        "feature_release_code",
        "target_release_code",
        "prediction_origin_value",
        "prediction_origin_precision",
        "target_listing_cohort_start",
        "target_listing_cohort_end",
        "target_follow_up_end",
        "target_published_value",
        "target_published_precision",
    )
    records = {tuple(str(row.get(field)) for field in fields) for row in rows}
    return [dict(zip(fields, record, strict=True)) for record in sorted(records)]


def _publish_files(
    files: Mapping[str, bytes],
    relative_destination: Path,
    *,
    repository_root: Path,
    provenance: Mapping[str, object],
) -> Path:
    """Stage the exact filenames, check their bytes and publish without replacement.

    An exclusive sibling lock excludes concurrent project writers. Existing
    destinations, including empty directories, are evidence and cannot be reused.
    A failed write leaves no completed run and cleans only its own staging area.
    """
    destination = validate_followup_destination(
        relative_destination, repository_root=repository_root
    )
    if set(files) != _FILES or any(not isinstance(v, bytes) or not v for v in files.values()):
        raise FollowupArtifactError("Follow-up payload file set is incomplete or unexpected.")
    if destination.exists():
        raise FollowupArtifactError("Follow-up run already exists; it cannot be overwritten.")
    lock = destination.parent / f".{destination.name}.lock"
    lock_acquired = False
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        validate_followup_destination(relative_destination, repository_root=repository_root)
        with lock.open("xb"):
            lock_acquired = True
            with tempfile.TemporaryDirectory(
                prefix=".staging-", dir=destination.parent
            ) as temporary:
                staging = Path(temporary)
                records = {}
                for name, payload in sorted(files.items()):
                    path = staging / name
                    with path.open("xb") as handle:
                        handle.write(payload)
                    digest = sha256(payload).hexdigest()
                    if _file_hash(path) != digest:
                        raise FollowupArtifactError(f"Written payload {name} failed its checksum.")
                    records[name] = {"bytes": len(payload), "sha256": digest}
                manifest = {
                    "schema_version": 1,
                    "analysis_id": ANALYSIS_ID,
                    "status": "complete",
                    "promotion_allowed": False,
                    "future_forecast_available": False,
                    "artifacts": records,
                    "provenance": dict(provenance),
                }
                (staging / "manifest.json").write_bytes(_json_bytes(manifest))
                validate_followup_destination(relative_destination, repository_root=repository_root)
                if destination.exists():
                    raise FollowupArtifactError(
                        "Follow-up run already exists; it cannot be overwritten."
                    )
                os.rename(staging, destination)
    except OSError as exc:
        raise FollowupArtifactError(f"Cannot publish the follow-up run: {exc}") from exc
    finally:
        if lock_acquired:
            lock.unlink(missing_ok=True)
    return destination


def build_followup(*, repository_root: Path, config_path: Path = DEFAULT_CONFIG) -> Path:
    """Reconstruct original predictions, run the fixed revision, and save development evidence."""
    root = repository_root.resolve()
    path = config_path if config_path.is_absolute() else root / config_path
    config = load_followup_config(path)
    inputs = _load_original_inputs(root, config)
    identity = _implementation_identity(root, path) | inputs.provenance
    run_hash = sha256(_json_bytes(identity)).hexdigest()
    relative = OUTPUT_ROOT / run_hash
    destination = validate_followup_destination(relative, repository_root=root)
    if destination.exists():
        raise FollowupArtifactError("Follow-up run already exists; it cannot be overwritten.")
    analysis = evaluate_followup(inputs.rows, inputs.stored_predictions, inputs.config, config)
    try:
        reports = render_followup_report(analysis.evidence)
    except (OSError, ValueError) as exc:
        raise FollowupArtifactError(f"Cannot render follow-up report evidence: {exc}") from exc
    buffer = BytesIO()
    table = patient_journey_prediction_table(analysis.predictions)
    table = table.replace_schema_metadata({b"kasm_provenance": _json_bytes(identity)})
    pq.write_table(table, buffer, compression="zstd")
    files = reports | {
        "predictions.parquet": buffer.getvalue(),
        "evaluation.json": _json_bytes(analysis.evidence),
    }
    # Bind the files actually used, even if another task edits code during a long run.
    if (
        identity
        != _implementation_identity(root, path) | _load_original_inputs(root, config).provenance
    ):
        raise FollowupArtifactError("Inputs or implementation changed during the follow-up run.")
    context = current_patient_journey_build_context(root)
    models = cast(Mapping[str, Mapping[str, object]], analysis.evidence["models"])
    provenance = identity | {
        "git_commit_sha": context.git_commit_sha,
        "git_worktree_dirty": context.git_worktree_dirty,
        "canonical_build": False,
        "evidence_status": "retrospective_exploratory_followup",
        "build_timestamp_utc": context.build_timestamp_utc.isoformat().replace("+00:00", "Z"),
        "python_version": context.python_version,
        "cohort_timing": _cohort_timing(inputs.rows),
        "training_pairs": inputs.config.model_design.ridge.training_pairs,
        "evaluation_pair": inputs.config.model_design.ridge.evaluation_pair,
        "ridge_settings": asdict(inputs.config.model_design.ridge),
        "bootstrap": asdict(inputs.config.model_design.bootstrap),
        "feature_schema": {name: model["features"] for name, model in models.items()},
        "model_parameters": {
            name: model["parameters"] for name, model in models.items() if "parameters" in model
        },
    }
    return _publish_files(files, relative, repository_root=root, provenance=provenance)
