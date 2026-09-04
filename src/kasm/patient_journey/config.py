"""Typed configuration for the isolated patient-journey v2 study."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

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
class PatientJourneyPair:
    """One feature-release to target-release relationship."""

    feature_release_code: str
    target_release_code: str


@dataclass(frozen=True)
class PatientJourneyExcludedPair:
    """A reviewed candidate pair deliberately excluded from the primary panel."""

    feature_release_code: str
    target_release_code: str
    reason: str


@dataclass(frozen=True)
class PatientJourneyTemporalDesign:
    """Non-overlapping release pairs and publication-vintage evaluation mode."""

    evaluation_mode: Literal["strict_vintage"]
    max_prediction_origin_month_offset: int
    primary_pairs: tuple[PatientJourneyPair, ...]
    excluded_candidates: tuple[PatientJourneyExcludedPair, ...]


@dataclass(frozen=True)
class PatientJourneyEligibility:
    """Prespecified primary and sensitivity target-size thresholds."""

    primary_min_target_n: int
    sensitivity_min_target_n: tuple[int, int]


@dataclass(frozen=True)
class PatientJourneyConfig:
    """Validated patient-journey v2 foundation configuration."""

    schema_version: int
    analysis_id: str
    target_column: str
    paths: PatientJourneyOutputPaths
    temporal_design: PatientJourneyTemporalDesign
    eligibility: PatientJourneyEligibility


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


def _object_sequence(value: object, context: str, *, allow_empty: bool = False) -> list[object]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise PatientJourneyConfigError(f"{context} must be {qualifier}.")
    return value


def _pair(value: object, context: str) -> PatientJourneyPair:
    values = _mapping(value, context)
    feature = _required_string(values, "feature_release_code", context)
    target = _required_string(values, "target_release_code", context)
    if feature == target:
        raise PatientJourneyConfigError(f"{context} must use distinct feature and target releases.")
    return PatientJourneyPair(feature_release_code=feature, target_release_code=target)


def _temporal_design(value: object) -> PatientJourneyTemporalDesign:
    values = _mapping(value, "temporal_design")
    evaluation_mode = _required_string(values, "evaluation_mode", "temporal_design")
    if evaluation_mode != "strict_vintage":
        raise PatientJourneyConfigError("temporal_design.evaluation_mode must be 'strict_vintage'.")
    max_origin_offset = _required_integer(
        values,
        "max_prediction_origin_month_offset",
        "temporal_design",
    )
    if max_origin_offset != 1:
        raise PatientJourneyConfigError(
            "temporal_design.max_prediction_origin_month_offset must remain 1."
        )
    primary_pairs = tuple(
        _pair(item, f"temporal_design.primary_pairs[{index}]")
        for index, item in enumerate(
            _object_sequence(values.get("primary_pairs"), "temporal_design.primary_pairs")
        )
    )
    if len(primary_pairs) != len(set(primary_pairs)):
        raise PatientJourneyConfigError("temporal_design.primary_pairs must be unique.")
    target_codes = tuple(pair.target_release_code for pair in primary_pairs)
    if len(target_codes) != len(set(target_codes)):
        raise PatientJourneyConfigError(
            "temporal_design.primary_pairs must use unique target releases."
        )

    excluded: list[PatientJourneyExcludedPair] = []
    for index, item in enumerate(
        _object_sequence(
            values.get("excluded_candidates"),
            "temporal_design.excluded_candidates",
            allow_empty=True,
        )
    ):
        context = f"temporal_design.excluded_candidates[{index}]"
        item_values = _mapping(item, context)
        parsed = _pair(item_values, context)
        excluded.append(
            PatientJourneyExcludedPair(
                feature_release_code=parsed.feature_release_code,
                target_release_code=parsed.target_release_code,
                reason=_required_string(item_values, "reason", context),
            )
        )
    excluded_pairs = tuple(excluded)
    excluded_keys = tuple(
        (pair.feature_release_code, pair.target_release_code) for pair in excluded_pairs
    )
    if len(excluded_keys) != len(set(excluded_keys)):
        raise PatientJourneyConfigError("temporal_design.excluded_candidates must be unique.")
    primary_keys = {(pair.feature_release_code, pair.target_release_code) for pair in primary_pairs}
    if primary_keys.intersection(excluded_keys):
        raise PatientJourneyConfigError(
            "A temporal pair cannot be both primary and explicitly excluded."
        )
    return PatientJourneyTemporalDesign(
        evaluation_mode="strict_vintage",
        max_prediction_origin_month_offset=max_origin_offset,
        primary_pairs=primary_pairs,
        excluded_candidates=excluded_pairs,
    )


def _eligibility(value: object) -> PatientJourneyEligibility:
    values = _mapping(value, "eligibility")
    primary = _required_integer(values, "primary_min_target_n", "eligibility")
    raw_sensitivity = _object_sequence(
        values.get("sensitivity_min_target_n"), "eligibility.sensitivity_min_target_n"
    )
    sensitivity = tuple(
        _required_integer(
            {"value": item}, "value", f"eligibility.sensitivity_min_target_n[{index}]"
        )
        for index, item in enumerate(raw_sensitivity)
    )
    if primary != 10 or sensitivity != (20, 30):
        raise PatientJourneyConfigError(
            "Eligibility thresholds must remain fixed at primary N>=10 and sensitivities N>=20/30."
        )
    return PatientJourneyEligibility(
        primary_min_target_n=primary,
        sensitivity_min_target_n=(20, 30),
    )


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
    if schema_version != 2:
        raise PatientJourneyConfigError(
            f"Unsupported patient-journey schema_version {schema_version}; expected 2."
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

    temporal_design = _temporal_design(values.get("temporal_design"))
    eligibility = _eligibility(values.get("eligibility"))

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
        temporal_design=temporal_design,
        eligibility=eligibility,
    )
