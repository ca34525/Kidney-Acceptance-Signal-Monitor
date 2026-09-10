"""Save distinct research stages and verify their identities before reuse."""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path, PureWindowsPath
from typing import Any

from kasm.acceptance_forecast.inputs import ensure_local_path, file_hash
from kasm.acceptance_forecast.runs import json_bytes
from kasm.patient_journey.artifacts import current_patient_journey_build_context

OUTPUT_ROOT = Path("data/research/program-prediction-0031")


def _destination(root: Path, run_id: str) -> Path:
    if (
        re.fullmatch(r"[a-z0-9][a-z0-9-]{0,100}", run_id) is None
        or PureWindowsPath(run_id).is_reserved()
    ):
        raise ValueError("Run ID must contain lowercase letters, digits and hyphens only.")
    destination = root / OUTPUT_ROOT / run_id
    ensure_local_path(destination, root)
    if not destination.resolve().is_relative_to(root.resolve() / OUTPUT_ROOT):
        raise ValueError("Research destination escapes the approved output root.")
    return destination


def validate_destination(root: Path, run_id: str) -> Path:
    """Reject an unsafe or used run identity before doing any analysis."""
    destination = _destination(root, run_id)
    if destination.exists():
        raise ValueError("Research run already exists; use a new run ID to preserve evidence.")
    return destination


def _validate_filename(name: str) -> None:
    if (
        re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", name) is None
        or name == "completion.json"
        or name.endswith(".")
        or PureWindowsPath(name).is_reserved()
    ):
        raise ValueError("Research payload filename must be a simple local filename.")


def publish_run(root: Path, run_id: str, files: dict[str, bytes], metadata: dict[str, Any]) -> Path:
    """Publish all payloads together, without replacing a preceding research run."""
    if not files:
        raise ValueError("A research run must contain payloads.")
    for name, content in files.items():
        _validate_filename(name)
        if not isinstance(content, bytes) or not content:
            raise ValueError("Research payloads must contain nonempty bytes.")
    destination = validate_destination(root, run_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".staging-", dir=destination.parent) as temporary:
        staging = Path(temporary) / "run"
        staging.mkdir()
        for name, content in files.items():
            (staging / name).write_bytes(content)
        completion = {
            "status": "complete",
            "study_id": "program-prediction-0031",
            "run_id": run_id,
            "provenance": metadata,
            "files": {
                name: {"sha256": sha256(content).hexdigest(), "bytes": len(content)}
                for name, content in files.items()
            },
        }
        (staging / "completion.json").write_bytes(json_bytes(completion))
        staging.rename(destination)
    return destination


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f"Research input is missing, unreadable or invalid JSON: {path}") from exc


def load_run(root: Path, run_id: str, *, stage: str) -> dict[str, Any]:
    """Check a complete stage and every byte before loading any analysis payload."""
    destination = _destination(root, run_id)
    ensure_local_path(destination / "completion.json", root)
    completion = _read_json(destination / "completion.json")
    if (
        not isinstance(completion, dict)
        or completion.get("status") != "complete"
        or completion.get("study_id") != "program-prediction-0031"
        or completion.get("run_id") != run_id
        or not isinstance(completion.get("files"), dict)
        or not isinstance(completion.get("provenance"), dict)
    ):
        raise ValueError("Research completion record is malformed or has a different identity.")
    if completion["provenance"].get("stage") != stage:
        raise ValueError(f"Expected a completed {stage} stage, not this run's stage.")
    _verify_parents(root, completion["provenance"].get("parents", {}))
    verified: dict[str, bytes] = {}
    for name, identity in completion["files"].items():
        _validate_filename(name)
        path = destination / name
        ensure_local_path(path, root)
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise ValueError(f"Research payload missing or unreadable: {name}") from exc
        if (
            not isinstance(identity, dict)
            or identity.get("sha256") != sha256(content).hexdigest()
            or identity.get("bytes") != len(content)
        ):
            raise ValueError(f"Research payload hash/size identity differs: {name}")
        verified[name] = content
    result: dict[str, Any] = {"completion.json": completion}
    for name, content in verified.items():
        try:
            result[name] = json.loads(content) if name.endswith(".json") else content
        except ValueError as exc:
            raise ValueError(f"Research payload is invalid JSON: {name}") from exc
    return result


def _verify_parents(root: Path, parents: Any) -> None:
    if not isinstance(parents, dict):
        raise ValueError("Research parent identities are malformed.")
    for parent in parents.values():
        if not isinstance(parent, dict) or not isinstance(parent.get("run_id"), str):
            raise ValueError("Research parent identity is malformed.")
        path = _destination(root, parent["run_id"]) / "completion.json"
        ensure_local_path(path, root)
        if file_hash(path) != parent.get("completion_sha256"):
            raise ValueError("Research parent completion identity changed since this stage ran.")


def provenance(
    root: Path, config_path: Path, *, stage: str, parents: dict[str, str] | None = None
) -> dict[str, Any]:
    """Record the exact revision, settings, dependencies and parent stage identities."""
    context = current_patient_journey_build_context(root)
    return {
        **asdict(context),
        "stage": stage,
        "configuration_sha256": file_hash(config_path),
        "specification_sha256": file_hash(root / "docs/specs/program-prediction-sprint-0031.md"),
        "dependency_lock_sha256": file_hash(root / "uv.lock"),
        "source_manifest_sha256": file_hash(root / "configs/data_sources.yaml"),
        "b1_ledger_sha256": file_hash(root / "configs/waiting_list/sources.json"),
        "implementation_sha256": {
            path.relative_to(root).as_posix(): file_hash(path)
            for path in sorted((root / "src/kasm").rglob("*.py"))
        },
        "parents": {
            role: {
                "run_id": identity,
                "completion_sha256": file_hash(_destination(root, identity) / "completion.json"),
            }
            for role, identity in (parents or {}).items()
        },
        "prospective_validation": False,
        "claims": "Exploratory historical delayed-report nowcasts; no clinical or regulatory use.",
    }
