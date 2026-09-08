"""Publish separate, immutable research runs with reproducible input and code identities."""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path, PureWindowsPath
from typing import Any

from kasm.acceptance_forecast.config import OUTPUT_ROOT, STUDY_ID, ForecastError
from kasm.acceptance_forecast.inputs import ensure_local_path, file_hash
from kasm.patient_journey.artifacts import current_patient_journey_build_context


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False, default=str) + "\n"
    ).encode()


def provenance(
    root: Path, config_path: Path, inputs: dict[str, Any], run_id: str
) -> dict[str, Any]:
    """Record both the original source identity and the current, possibly uncommitted code."""
    context = current_patient_journey_build_context(root)
    return {
        "study_id": STUDY_ID,
        "run_id": run_id,
        **asdict(context),
        "configuration_sha256": file_hash(config_path),
        "specification_sha256": file_hash(root / "docs/specs/acceptance-forecast-0027.md"),
        "dependency_lock_sha256": file_hash(root / "uv.lock"),
        "implementation_sha256": {
            p.relative_to(root).as_posix(): file_hash(p)
            for p in sorted((root / "src/kasm").rglob("*.py"))
        },
        "original_release": inputs,
        "prospective_validation": False,
        "publication_label": "Feature reports July 2021–July 2025; truth July 2022–July 2026",
    }


def validate_destination(root: Path, run_id: str) -> Path:
    """Reject an unsafe or already-used identity before any analysis can execute."""
    if (
        re.fullmatch(r"[a-z0-9][a-z0-9-]{0,100}", run_id) is None
        or PureWindowsPath(run_id).is_reserved()
    ):
        raise ForecastError("Run ID must be lowercase letters, digits and hyphens only.")
    destination = root / OUTPUT_ROOT / run_id
    ensure_local_path(destination, root)
    if not destination.resolve().is_relative_to(root.resolve() / OUTPUT_ROOT):
        raise ForecastError("Research destination escapes the approved output root.")
    if destination.exists():
        raise ForecastError("Research run already exists; choose a distinct audit run ID.")
    return destination


def publish_run(root: Path, run_id: str, files: dict[str, bytes], metadata: dict[str, Any]) -> Path:
    """Write safe local filenames atomically into a new run; existing evidence is immutable."""
    if not files or any(
        re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", name) is None
        or name == "completion.json"
        or name.endswith(".")
        or PureWindowsPath(name).is_reserved()
        or not isinstance(content, bytes)
        or not content
        for name, content in files.items()
    ):
        raise ForecastError("Research payload filenames must be simple, nonempty local files.")
    destination = validate_destination(root, run_id)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".staging-", dir=parent) as temp:
        staging = Path(temp) / "run"
        staging.mkdir()
        for name, content in files.items():
            (staging / name).write_bytes(content)
        completion = {
            "status": "complete",
            "provenance": metadata,
            "files": {
                name: {"sha256": sha256(data).hexdigest(), "bytes": len(data)}
                for name, data in files.items()
            },
        }
        (staging / "completion.json").write_bytes(json_bytes(completion))
        # rename cannot replace a nonempty completed run; the earlier check also catches retries.
        staging.rename(destination)
    return destination
