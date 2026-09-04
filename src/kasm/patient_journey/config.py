"""Typed configuration for the isolated patient-journey v2 study."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

ANALYSIS_ID = "kidney_patient_journey_v2"
TARGET_COLUMN = "SAL_TOTFTX_C18"
PROTECTED_V1_ROOTS = (
    Path("data/processed"),
    Path("data/modeling"),
    Path("artifacts/release"),
)


class PatientJourneyConfigError(ValueError):
    """Raised when v2 configuration could weaken scientific or path isolation."""


@dataclass(frozen=True)
class PatientJourneyOutputPaths:
    """Resolved repository-local roots owned by patient-journey v2."""

    processed_dir: Path
    modeling_dir: Path
    release_dir: Path


@dataclass(frozen=True)
class PatientJourneyConfig:
    """Validated patient-journey v2 foundation configuration."""

    schema_version: int
    analysis_id: str
    target_column: str
    paths: PatientJourneyOutputPaths


def _mapping(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PatientJourneyConfigError(f"{context} must be a mapping with string keys.")
    return cast(dict[str, object], value)


def _required_string(values: dict[str, object], key: str, context: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PatientJourneyConfigError(f"{context}.{key} must be a non-empty string.")
    return value


def _required_integer(values: dict[str, object], key: str, context: str) -> int:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PatientJourneyConfigError(f"{context}.{key} must be an integer.")
    return value


def _required_boolean(values: dict[str, object], key: str, context: str) -> bool:
    value = values.get(key)
    if not isinstance(value, bool):
        raise PatientJourneyConfigError(f"{context}.{key} must be a boolean.")
    return value


def _path_strings(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise PatientJourneyConfigError(f"{context} must be a non-empty list of paths.")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise PatientJourneyConfigError(f"{context} must contain only non-empty path strings.")
    return tuple(cast(list[str], value))


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first.is_relative_to(second) or second.is_relative_to(first)


def _resolve_v2_output(
    value: str,
    *,
    key: str,
    repository_root: Path,
    protected_roots: tuple[Path, ...],
) -> Path:
    configured = Path(value)
    if configured.is_absolute():
        raise PatientJourneyConfigError(f"paths.{key} must be repository-relative.")
    if ".." in configured.parts:
        raise PatientJourneyConfigError(f"paths.{key} must not contain parent traversal.")

    resolved = (repository_root / configured).resolve()
    if not resolved.is_relative_to(repository_root):
        raise PatientJourneyConfigError(f"paths.{key} must remain inside the repository.")
    for protected in protected_roots:
        if _paths_overlap(resolved, protected):
            protected_relative = protected.relative_to(repository_root)
            raise PatientJourneyConfigError(
                f"paths.{key} overlaps protected v1 root {protected_relative.as_posix()!r}."
            )
    return resolved


def load_patient_journey_config(path: Path, *, repository_root: Path) -> PatientJourneyConfig:
    """Load v2 configuration and reject any path capable of writing into v1."""
    root = repository_root.resolve()
    raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    values = _mapping(raw, "Config root")

    schema_version = _required_integer(values, "schema_version", "Config root")
    if schema_version != 1:
        raise PatientJourneyConfigError(
            f"Unsupported patient-journey schema_version {schema_version}; expected 1."
        )

    analysis_id = _required_string(values, "analysis_id", "Config root")
    if analysis_id != ANALYSIS_ID:
        raise PatientJourneyConfigError(f"Config root.analysis_id must be {ANALYSIS_ID!r}.")

    target = _mapping(values.get("target"), "target")
    target_column = _required_string(target, "column", "target")
    if target_column != TARGET_COLUMN:
        raise PatientJourneyConfigError(f"target.column must be {TARGET_COLUMN!r}.")
    if _required_string(target, "canonical_scale", "target") != "proportion":
        raise PatientJourneyConfigError("target.canonical_scale must be 'proportion'.")
    if _required_boolean(target, "officially_risk_adjusted", "target"):
        raise PatientJourneyConfigError(
            "The patient-journey target is observed, not officially risk-adjusted."
        )

    configured_protected = tuple(
        Path(value)
        for value in _path_strings(values.get("protected_v1_roots"), "protected_v1_roots")
    )
    if configured_protected != PROTECTED_V1_ROOTS:
        raise PatientJourneyConfigError(
            "protected_v1_roots must exactly match the code-owned v1 protection contract."
        )
    protected_roots = tuple((root / protected).resolve() for protected in PROTECTED_V1_ROOTS)

    path_values = _mapping(values.get("paths"), "paths")
    output_paths = PatientJourneyOutputPaths(
        processed_dir=_resolve_v2_output(
            _required_string(path_values, "processed_dir", "paths"),
            key="processed_dir",
            repository_root=root,
            protected_roots=protected_roots,
        ),
        modeling_dir=_resolve_v2_output(
            _required_string(path_values, "modeling_dir", "paths"),
            key="modeling_dir",
            repository_root=root,
            protected_roots=protected_roots,
        ),
        release_dir=_resolve_v2_output(
            _required_string(path_values, "release_dir", "paths"),
            key="release_dir",
            repository_root=root,
            protected_roots=protected_roots,
        ),
    )
    named_outputs = (
        ("processed_dir", output_paths.processed_dir),
        ("modeling_dir", output_paths.modeling_dir),
        ("release_dir", output_paths.release_dir),
    )
    for index, (name, output) in enumerate(named_outputs):
        for other_name, other_output in named_outputs[index + 1 :]:
            if _paths_overlap(output, other_output):
                raise PatientJourneyConfigError(
                    f"paths.{name} and paths.{other_name} must be separate roots."
                )

    return PatientJourneyConfig(
        schema_version=schema_version,
        analysis_id=analysis_id,
        target_column=target_column,
        paths=output_paths,
    )
