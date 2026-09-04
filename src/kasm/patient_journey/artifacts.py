"""Trusted processed-artifact publication for the patient-journey v2 study."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from kasm.config import DataSourceManifest, load_data_source_manifest
from kasm.patient_journey.config import (
    PROTECTED_V1_ROOTS,
    PatientJourneyConfig,
    load_patient_journey_config,
)
from kasm.patient_journey.ledger import MethodologyLedger, load_methodology_ledger
from kasm.patient_journey.panel import (
    PATIENT_JOURNEY_PANEL_SCHEMA,
    PatientJourneyPairSummary,
    PatientJourneyPanel,
    PatientJourneyPanelError,
    PatientJourneyPanelRow,
    build_cached_patient_journey_panel,
    methodology_ledger_identity,
    patient_journey_panel_table,
    strict_vintage_folds,
    validate_patient_journey_panel_rows,
)

PANEL_NAME = "patient_journey_panel.parquet"
QA_NAME = "qa_report.json"
MANIFEST_NAME = "build_manifest.json"
_ARTIFACT_NAMES = frozenset((PANEL_NAME, QA_NAME, MANIFEST_NAME))
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")
_PROGRAM_KEY_PATTERN = re.compile(r"^[A-Z0-9]{4}:[A-Za-z0-9]+$")

JsonObject = dict[str, object]


class PatientJourneyArtifactError(ValueError):
    """Raised when a v2 processed artifact violates its trust contract."""


@dataclass(frozen=True)
class PatientJourneyBuildContext:
    """Run-specific provenance separated from deterministic analytical content."""

    build_timestamp_utc: datetime
    git_commit_sha: str
    git_worktree_dirty: bool
    python_version: str


@dataclass(frozen=True)
class PatientJourneyArtifactResult:
    """Validated paths and identity for one complete processed-data generation."""

    output_directory: Path
    panel_path: Path
    qa_report_path: Path
    manifest_path: Path
    panel_rows: int
    artifact_set_sha256: str


@dataclass(frozen=True)
class _BoundInputs:
    """Typed inputs and hashes proven to originate from one stable file snapshot."""

    manifest: DataSourceManifest
    config: PatientJourneyConfig
    ledger: MethodologyLedger
    file_sha256: Mapping[str, str]


def _file_sha256(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PatientJourneyArtifactError(
            f"Required artifact input is unreadable: {path}."
        ) from exc
    return digest.hexdigest()


def _repository_path(path: Path, repository_root: Path) -> Path:
    return path.resolve() if path.is_absolute() else (repository_root / path).resolve()


def _load_bound_inputs(
    *,
    repository_root: Path,
    source_manifest_path: Path,
    experiment_config_path: Path,
    methodology_path: Path,
    lock_path: Path,
) -> _BoundInputs:
    root = repository_root.resolve()
    paths = {
        "source_manifest_sha256": _repository_path(source_manifest_path, root),
        "experiment_config_sha256": _repository_path(experiment_config_path, root),
        "methodology_config_sha256": _repository_path(methodology_path, root),
        "dependency_lock_sha256": _repository_path(lock_path, root),
    }
    before = {name: _file_sha256(path) for name, path in paths.items()}
    manifest = load_data_source_manifest(paths["source_manifest_sha256"])
    config = load_patient_journey_config(
        paths["experiment_config_sha256"],
        repository_root=root,
    )
    ledger = load_methodology_ledger(paths["methodology_config_sha256"], manifest=manifest)
    after = {name: _file_sha256(path) for name, path in paths.items()}
    if after != before:
        raise PatientJourneyArtifactError(
            "A patient-journey input changed while its typed identity was being loaded."
        )
    return _BoundInputs(
        manifest=manifest,
        config=config,
        ledger=ledger,
        file_sha256=before,
    )


def _reload_matching_inputs(
    expected: _BoundInputs,
    *,
    repository_root: Path,
    source_manifest_path: Path,
    experiment_config_path: Path,
    methodology_path: Path,
    lock_path: Path,
    context: str,
) -> _BoundInputs:
    observed = _load_bound_inputs(
        repository_root=repository_root,
        source_manifest_path=source_manifest_path,
        experiment_config_path=experiment_config_path,
        methodology_path=methodology_path,
        lock_path=lock_path,
    )
    if observed != expected:
        raise PatientJourneyArtifactError(f"Patient-journey inputs changed {context}.")
    return observed


def _read_json(path: Path) -> JsonObject:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PatientJourneyArtifactError(f"Artifact JSON is invalid: {path}.") from exc
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PatientJourneyArtifactError(f"Artifact JSON must contain an object: {path}.")
    return cast(JsonObject, value)


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _mapping(value: object, field: str) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PatientJourneyArtifactError(f"Artifact field {field!r} must be an object.")
    return cast(JsonObject, value)


def _sequence(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise PatientJourneyArtifactError(f"Artifact field {field!r} must be an array.")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise PatientJourneyArtifactError(f"Artifact field {field!r} must be non-empty text.")
    return value


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PatientJourneyArtifactError(f"Artifact field {field!r} must be an integer.")
    return value


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise PatientJourneyArtifactError(f"Artifact field {field!r} must be numeric.")
    result = float(value)
    if not math.isfinite(result):
        raise PatientJourneyArtifactError(f"Artifact field {field!r} must be finite.")
    return result


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise PatientJourneyArtifactError(f"Artifact field {field!r} must be boolean.")
    return value


def _sha256_text(value: object, field: str) -> str:
    result = _text(value, field)
    if _SHA256_PATTERN.fullmatch(result) is None:
        raise PatientJourneyArtifactError(f"Artifact field {field!r} must be a SHA-256 value.")
    return result


def _hash_payload(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256(payload).hexdigest()


def _schema_fields() -> list[dict[str, object]]:
    return [
        {"name": field.name, "nullable": field.nullable, "type": str(field.type)}
        for field in PATIENT_JOURNEY_PANEL_SCHEMA
    ]


def _pair_payload(feature_release_code: str, target_release_code: str) -> JsonObject:
    return {
        "feature_release_code": feature_release_code,
        "target_release_code": target_release_code,
    }


def _cohort_timing(
    rows: tuple[PatientJourneyPanelRow, ...], config: PatientJourneyConfig
) -> list[JsonObject]:
    timing: list[JsonObject] = []
    for pair in config.temporal_design.primary_pairs:
        pair_rows = tuple(
            row
            for row in rows
            if row.feature_release_code == pair.feature_release_code
            and row.target_release_code == pair.target_release_code
        )
        if not pair_rows:
            raise PatientJourneyArtifactError(
                "Every configured primary pair must have a prediction-universe row before "
                f"publication; missing {pair.feature_release_code}->{pair.target_release_code}."
            )
        values = {
            (
                row.prediction_origin_value,
                row.prediction_origin_precision,
                row.prediction_origin_month_offset_from_target_start,
                row.target_listing_cohort_start,
                row.target_listing_cohort_end,
                row.target_follow_up_end,
                row.target_published_value,
                row.target_published_precision,
            )
            for row in pair_rows
        }
        if len(values) != 1:
            raise PatientJourneyArtifactError(
                f"Pair {pair.feature_release_code}->{pair.target_release_code} has inconsistent "
                "cohort timing."
            )
        (
            origin_value,
            origin_precision,
            origin_offset,
            target_start,
            target_end,
            follow_up_end,
            target_published_value,
            target_published_precision,
        ) = values.pop()
        timing.append(
            {
                **_pair_payload(pair.feature_release_code, pair.target_release_code),
                "prediction_origin_value": origin_value,
                "prediction_origin_precision": origin_precision,
                "prediction_origin_month_offset_from_target_start": origin_offset,
                "target_listing_cohort_start": target_start.isoformat(),
                "target_listing_cohort_end": target_end.isoformat(),
                "target_follow_up_end": follow_up_end.isoformat(),
                "target_published_value": target_published_value,
                "target_published_precision": target_published_precision,
            }
        )
    return timing


def _validate_build_context(context: PatientJourneyBuildContext) -> None:
    if context.build_timestamp_utc.tzinfo is None:
        raise PatientJourneyArtifactError("Build timestamp must be timezone-aware UTC.")
    if context.build_timestamp_utc.utcoffset() != UTC.utcoffset(context.build_timestamp_utc):
        raise PatientJourneyArtifactError("Build timestamp must use UTC.")
    if _GIT_SHA_PATTERN.fullmatch(context.git_commit_sha) is None:
        raise PatientJourneyArtifactError(
            "Git commit identity must be a lowercase hexadecimal SHA."
        )
    if not context.python_version:
        raise PatientJourneyArtifactError("Python version provenance must not be empty.")


def _validate_recorded_build_context(provenance: Mapping[str, object]) -> None:
    try:
        build_timestamp = datetime.fromisoformat(
            _text(provenance.get("build_timestamp_utc"), "build_timestamp_utc")
        )
    except ValueError as exc:
        raise PatientJourneyArtifactError(
            "Artifact build timestamp must be valid ISO 8601 text."
        ) from exc
    context = PatientJourneyBuildContext(
        build_timestamp_utc=build_timestamp,
        git_commit_sha=_text(provenance.get("git_commit_sha"), "git_commit_sha"),
        git_worktree_dirty=_boolean(provenance.get("git_worktree_dirty"), "git_worktree_dirty"),
        python_version=_text(provenance.get("python_version"), "python_version"),
    )
    _validate_build_context(context)
    if _boolean(provenance.get("canonical_build"), "canonical_build") != (
        not context.git_worktree_dirty
    ):
        raise PatientJourneyArtifactError(
            "Artifact canonical-build status disagrees with the recorded Git state."
        )


def _validate_fixed_provenance(
    provenance: Mapping[str, object], config: PatientJourneyConfig
) -> None:
    fixed_fields = {
        "analysis_stage": "canonical_panel",
        "target_column": config.target_column,
        "target_scale": "proportion",
    }
    for field, expected in fixed_fields.items():
        if _text(provenance.get(field), field) != expected:
            raise PatientJourneyArtifactError(
                f"Artifact provenance fixed field {field!r} disagrees."
            )
    if _boolean(
        provenance.get("target_officially_risk_adjusted"),
        "target_officially_risk_adjusted",
    ):
        raise PatientJourneyArtifactError(
            "Artifact provenance contains a prohibited risk-adjustment claim."
        )


def _run_git(repository_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(  # noqa: S603 - executable and arguments are fixed by this module.
            ("git", *arguments),
            cwd=repository_root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PatientJourneyArtifactError("Git provenance could not be inspected.") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git failure"
        raise PatientJourneyArtifactError(f"Git provenance could not be inspected: {detail}.")
    return completed.stdout.strip()


def current_patient_journey_build_context(repository_root: Path) -> PatientJourneyBuildContext:
    """Capture the real build time and repository state without mutating the checkout."""
    commit = _run_git(repository_root, "rev-parse", "HEAD")
    dirty_output = _run_git(repository_root, "status", "--porcelain", "--untracked-files=normal")
    context = PatientJourneyBuildContext(
        build_timestamp_utc=datetime.now(UTC),
        git_commit_sha=commit,
        git_worktree_dirty=bool(dirty_output),
        python_version=sys.version.split()[0],
    )
    _validate_build_context(context)
    return context


def _validate_destination(config: PatientJourneyConfig, repository_root: Path) -> Path:
    root = repository_root.resolve()
    output_dir = config.paths.processed_dir.resolve()
    if not output_dir.is_relative_to(root):
        raise PatientJourneyArtifactError(
            "Configured v2 processed output must stay in the repository."
        )
    for protected_relative in PROTECTED_V1_ROOTS:
        protected = (root / protected_relative).resolve()
        if (
            output_dir == protected
            or output_dir.is_relative_to(protected)
            or protected.is_relative_to(output_dir)
        ):
            raise PatientJourneyArtifactError(
                f"Configured v2 processed output overlaps protected v1 root {protected_relative}."
            )
    return output_dir


def _provenance(
    panel: PatientJourneyPanel,
    *,
    inputs: _BoundInputs,
    build_context: PatientJourneyBuildContext,
) -> JsonObject:
    _validate_build_context(build_context)
    manifest = inputs.manifest
    config = inputs.config
    schema_fields = _schema_fields()
    return {
        "analysis_id": config.analysis_id,
        "analysis_stage": "canonical_panel",
        "target_column": config.target_column,
        "target_scale": "proportion",
        "target_officially_risk_adjusted": False,
        "build_timestamp_utc": build_context.build_timestamp_utc.isoformat(),
        "git_commit_sha": build_context.git_commit_sha,
        "git_worktree_dirty": build_context.git_worktree_dirty,
        "canonical_build": not build_context.git_worktree_dirty,
        "python_version": build_context.python_version,
        "dependency_lock_sha256": inputs.file_sha256["dependency_lock_sha256"],
        "source_manifest_schema_version": manifest.schema_version,
        "source_manifest_sha256": inputs.file_sha256["source_manifest_sha256"],
        "experiment_config_sha256": inputs.file_sha256["experiment_config_sha256"],
        "methodology_config_sha256": inputs.file_sha256["methodology_config_sha256"],
        "methodology_ledger_identity": panel.methodology_ledger_identity,
        "source_sha256": {
            source.release_code: source.download_sha256 for source in manifest.sources
        },
        "primary_pairs": [
            _pair_payload(pair.feature_release_code, pair.target_release_code)
            for pair in config.temporal_design.primary_pairs
        ],
        "excluded_candidates": [
            asdict(pair) for pair in config.temporal_design.excluded_candidates
        ],
        "eligibility_thresholds": {
            "primary_min_target_n": config.eligibility.primary_min_target_n,
            "sensitivity_min_target_n": list(config.eligibility.sensitivity_min_target_n),
        },
        "cohort_timing": _cohort_timing(panel.rows, config),
        "panel_schema": schema_fields,
        "panel_schema_sha256": _hash_payload(schema_fields),
        "model_fitted": False,
        "model_parameters": {},
    }


def _fold_payloads(config: PatientJourneyConfig, ledger: MethodologyLedger) -> list[JsonObject]:
    return [
        {
            "evaluation_pair": _pair_payload(
                fold.evaluation_pair.feature_release_code,
                fold.evaluation_pair.target_release_code,
            ),
            "training_pairs": [
                _pair_payload(pair.feature_release_code, pair.target_release_code)
                for pair in fold.training_pairs
            ],
        }
        for fold in strict_vintage_folds(config, ledger)
    ]


def _eligibility_counts(rows: tuple[PatientJourneyPanelRow, ...]) -> JsonObject:
    status_counts = {
        status: sum(row.eligibility_status == status for row in rows)
        for status in (
            "eligible",
            "missing_prior_target",
            "missing_target",
            "target_n_below_10",
        )
    }
    return {
        "eligibility_status_counts": status_counts,
        "eligibility_threshold_counts": {
            "primary_n10": sum(row.primary_analytic_eligible for row in rows),
            "sensitivity_n20": sum(row.sensitivity_n20_eligible for row in rows),
            "sensitivity_n30": sum(row.sensitivity_n30_eligible for row in rows),
        },
    }


def _program_keys(values: Sequence[object], field: str) -> tuple[str, ...]:
    keys = tuple(_text(value, field) for value in values)
    if tuple(sorted(set(keys))) != keys or any(
        _PROGRAM_KEY_PATTERN.fullmatch(key) is None for key in keys
    ):
        raise PatientJourneyArtifactError(
            f"{field} must contain sorted, unique composite program identities."
        )
    return keys


def _validate_history_evidence_values(
    row: PatientJourneyPanelRow,
    *,
    release_code_values: Sequence[object],
    proportion_values: Sequence[object],
    earliest_identity_release_code: object,
    ledger: MethodologyLedger,
) -> None:
    release_codes = tuple(_text(value, "history.release_codes") for value in release_code_values)
    proportions = tuple(_number(value, "history.target_proportions") for value in proportion_values)
    if len(release_codes) != len(proportions):
        raise PatientJourneyArtifactError(
            "History release and target-proportion evidence lengths disagree."
        )
    release_order = {release.release_code: index for index, release in enumerate(ledger.releases)}
    try:
        history_order = tuple(release_order[code] for code in release_codes)
        feature_index = release_order[row.feature_release_code]
        earliest_code = _text(
            earliest_identity_release_code, "history.earliest_identity_release_code"
        )
        earliest_index = release_order[earliest_code]
    except KeyError as exc:
        raise PatientJourneyArtifactError(
            "History evidence contains an unknown release identity."
        ) from exc
    if history_order != tuple(sorted(set(history_order))) or any(
        index > feature_index for index in history_order
    ):
        raise PatientJourneyArtifactError(
            "History evidence is not strictly ordered through the feature release."
        )
    if earliest_index > feature_index:
        raise PatientJourneyArtifactError(
            "Earliest identity evidence occurs after the feature release."
        )
    if any(not 0 <= value <= 1 for value in proportions):
        raise PatientJourneyArtifactError(
            "History target-proportion evidence must remain between zero and one."
        )
    expected_mean = sum(proportions) / len(proportions) if proportions else None
    if row.historical_target_count != len(proportions):
        raise PatientJourneyArtifactError(
            "Row historical target count disagrees with source-derived history evidence."
        )
    if expected_mean is None:
        if row.historical_mean_target_proportion is not None:
            raise PatientJourneyArtifactError(
                "Row historical target mean disagrees with empty history evidence."
            )
    elif row.historical_mean_target_proportion is None or not math.isclose(
        row.historical_mean_target_proportion,
        expected_mean,
        rel_tol=0,
        abs_tol=1e-12,
    ):
        raise PatientJourneyArtifactError(
            "Row historical target mean disagrees with source-derived history evidence."
        )
    if release_codes:
        if (
            row.prior_target_release_code != release_codes[-1]
            or row.prior_target_proportion is None
            or not math.isclose(
                row.prior_target_proportion,
                proportions[-1],
                rel_tol=0,
                abs_tol=1e-12,
            )
        ):
            raise PatientJourneyArtifactError(
                "Row prior target disagrees with source-derived history evidence."
            )
    elif not row.missing_prior_target:
        raise PatientJourneyArtifactError(
            "Row prior-target status disagrees with empty history evidence."
        )
    if row.first_observed_program != (earliest_code == row.feature_release_code):
        raise PatientJourneyArtifactError(
            "First-observed status disagrees with earliest identity evidence."
        )


def _validate_target_roster_values(
    *,
    target_program_values: Sequence[object],
    target_only_values: Sequence[object],
    target_table_rows: object,
    target_only_additions: object,
    pair_rows: tuple[PatientJourneyPanelRow, ...],
    context: str,
) -> None:
    target_program_keys = _program_keys(target_program_values, f"{context} target source roster")
    target_only_keys = _program_keys(target_only_values, f"{context} target-only program evidence")
    pair_programs = {row.program_key for row in pair_rows}
    matched_programs = {row.program_key for row in pair_rows if not row.missing_target}
    expected_target_only = tuple(key for key in target_program_keys if key not in pair_programs)
    if target_only_keys != expected_target_only:
        raise PatientJourneyArtifactError(
            f"{context} target-only program evidence disagrees with the target source roster."
        )
    if set(target_program_keys).intersection(pair_programs) != matched_programs:
        raise PatientJourneyArtifactError(
            f"{context} target source roster disagrees with matched panel outcomes."
        )
    if _integer(target_table_rows, f"{context}.target_table_rows") != len(
        target_program_keys
    ) or _integer(target_only_additions, f"{context}.target_only_additions") != len(
        target_only_keys
    ):
        raise PatientJourneyArtifactError(
            f"{context} target-only program evidence counts do not reconcile."
        )


def _validate_available_cohort_values(
    *,
    successes_value: object,
    target_n_value: object,
    pair_rows: tuple[PatientJourneyPanelRow, ...],
    context: str,
) -> None:
    successes = _integer(successes_value, f"{context}.available_cohort_target_successes")
    target_n = _integer(target_n_value, f"{context}.available_cohort_target_n")
    if target_n < 0 or successes < 0 or successes > target_n:
        raise PatientJourneyArtifactError(f"{context} available-cohort target counts are invalid.")
    expected = successes / target_n if target_n else None
    for row in pair_rows:
        observed = row.available_cohort_target_proportion
        if (expected is None and observed is not None) or (
            expected is not None
            and (observed is None or not math.isclose(observed, expected, rel_tol=0, abs_tol=1e-12))
        ):
            raise PatientJourneyArtifactError(
                f"{context} available cohort target proportion disagrees with "
                "source-derived counts."
            )


def _validate_panel_pair_evidence(
    summary: PatientJourneyPairSummary,
    *,
    pair_rows: tuple[PatientJourneyPanelRow, ...],
    ledger: MethodologyLedger,
) -> None:
    _validate_target_roster_values(
        target_program_values=summary.target_program_keys,
        target_only_values=summary.target_only_program_keys,
        target_table_rows=summary.target_table_rows,
        target_only_additions=summary.target_only_additions,
        pair_rows=pair_rows,
        context="Panel",
    )
    _validate_available_cohort_values(
        successes_value=summary.available_cohort_target_successes,
        target_n_value=summary.available_cohort_target_n,
        pair_rows=pair_rows,
        context="Panel",
    )
    history_evidence = summary.row_history_evidence
    expected_program_keys = tuple(sorted(row.program_key for row in pair_rows))
    observed_program_keys = tuple(evidence.program_key for evidence in history_evidence)
    if observed_program_keys != expected_program_keys:
        raise PatientJourneyArtifactError(
            "Panel history evidence must cover each pair row exactly once in key order."
        )
    rows_by_program = {row.program_key: row for row in pair_rows}
    for evidence in history_evidence:
        _validate_history_evidence_values(
            rows_by_program[evidence.program_key],
            release_code_values=evidence.release_codes,
            proportion_values=evidence.target_proportions,
            earliest_identity_release_code=evidence.earliest_identity_release_code,
            ledger=ledger,
        )


def _validate_qa_pair_evidence(
    summary: Mapping[str, object],
    *,
    pair_rows: tuple[PatientJourneyPanelRow, ...],
    ledger: MethodologyLedger,
) -> None:
    _validate_target_roster_values(
        target_program_values=_sequence(summary.get("target_program_keys"), "target_program_keys"),
        target_only_values=_sequence(
            summary.get("target_only_program_keys"), "target_only_program_keys"
        ),
        target_table_rows=summary.get("target_table_rows"),
        target_only_additions=summary.get("target_only_additions"),
        pair_rows=pair_rows,
        context="QA",
    )
    _validate_available_cohort_values(
        successes_value=summary.get("available_cohort_target_successes"),
        target_n_value=summary.get("available_cohort_target_n"),
        pair_rows=pair_rows,
        context="QA",
    )
    history_values = _sequence(summary.get("row_history_evidence"), "row_history_evidence")
    history_by_program: dict[str, JsonObject] = {}
    for index, value in enumerate(history_values):
        evidence = _mapping(value, f"row_history_evidence[{index}]")
        program_key = _text(evidence.get("program_key"), "history.program_key")
        if program_key in history_by_program:
            raise PatientJourneyArtifactError("QA history evidence contains a duplicate program.")
        history_by_program[program_key] = evidence
    expected_program_keys = tuple(sorted(row.program_key for row in pair_rows))
    if tuple(history_by_program) != expected_program_keys:
        raise PatientJourneyArtifactError(
            "QA history evidence must cover each pair row exactly once in key order."
        )
    rows_by_program = {row.program_key: row for row in pair_rows}
    for program_key, evidence in history_by_program.items():
        _validate_history_evidence_values(
            rows_by_program[program_key],
            release_code_values=_sequence(evidence.get("release_codes"), "history.release_codes"),
            proportion_values=_sequence(
                evidence.get("target_proportions"), "history.target_proportions"
            ),
            earliest_identity_release_code=evidence.get("earliest_identity_release_code"),
            ledger=ledger,
        )


def _validate_panel_evidence(
    panel: PatientJourneyPanel,
    *,
    config: PatientJourneyConfig,
    ledger: MethodologyLedger,
) -> None:
    if panel.methodology_ledger_identity != methodology_ledger_identity(ledger):
        raise PatientJourneyArtifactError("Panel methodology evidence disagrees with the ledger.")
    if panel.excluded_candidates != config.temporal_design.excluded_candidates:
        raise PatientJourneyArtifactError("Panel excluded-pair evidence disagrees with the config.")
    if panel.strict_vintage_folds != strict_vintage_folds(config, ledger):
        raise PatientJourneyArtifactError("Panel strict-vintage fold evidence disagrees.")
    summaries = {
        (summary.feature_release_code, summary.target_release_code): summary
        for summary in panel.pair_summaries
    }
    expected_pairs = {
        (pair.feature_release_code, pair.target_release_code)
        for pair in config.temporal_design.primary_pairs
    }
    if set(summaries) != expected_pairs or len(summaries) != len(panel.pair_summaries):
        raise PatientJourneyArtifactError(
            "Panel pair-summary evidence is incomplete or duplicated."
        )
    for pair_key, summary in summaries.items():
        pair_rows = tuple(
            row
            for row in panel.rows
            if (row.feature_release_code, row.target_release_code) == pair_key
        )
        expected = {
            "prediction_universe_rows": len(pair_rows),
            "matched_target_rows": sum(not row.missing_target for row in pair_rows),
            "missing_target_rows": sum(row.missing_target for row in pair_rows),
            "primary_eligible_rows": sum(row.primary_analytic_eligible for row in pair_rows),
            "sensitivity_n20_eligible_rows": sum(row.sensitivity_n20_eligible for row in pair_rows),
            "sensitivity_n30_eligible_rows": sum(row.sensitivity_n30_eligible for row in pair_rows),
            "first_observed_rows": sum(row.first_observed_program for row in pair_rows),
        }
        for field, value in expected.items():
            if getattr(summary, field) != value:
                raise PatientJourneyArtifactError(
                    f"Panel pair-summary field {field!r} disagrees with its rows."
                )
        _validate_panel_pair_evidence(summary, pair_rows=pair_rows, ledger=ledger)


def _qa_report(
    panel: PatientJourneyPanel,
    provenance: JsonObject,
    *,
    config: PatientJourneyConfig,
    ledger: MethodologyLedger,
) -> JsonObject:
    eligibility = _eligibility_counts(panel.rows)
    return {
        "schema_version": 1,
        "analysis_id": provenance["analysis_id"],
        "row_count": len(panel.rows),
        "methodology_ledger_identity": panel.methodology_ledger_identity,
        "pair_summaries": [asdict(summary) for summary in panel.pair_summaries],
        "strict_vintage_folds": _fold_payloads(config, ledger),
        "excluded_candidates": [asdict(pair) for pair in panel.excluded_candidates],
        "eligibility_thresholds": provenance["eligibility_thresholds"],
        **eligibility,
        "provenance": provenance,
    }


def _artifact_set_identity(records: Mapping[str, Mapping[str, object]]) -> str:
    normalized = {
        name: {
            "bytes": _integer(record.get("bytes"), f"artifacts.{name}.bytes"),
            "sha256": _sha256_text(record.get("sha256"), f"artifacts.{name}.sha256"),
        }
        for name, record in sorted(records.items())
    }
    return _hash_payload(normalized)


def _artifact_record(path: Path) -> JsonObject:
    return {
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": _file_sha256(path),
    }


def _manifest(
    panel_path: Path,
    qa_path: Path,
    *,
    panel_rows: int,
    provenance: JsonObject,
) -> JsonObject:
    records = {
        "panel": _artifact_record(panel_path),
        "qa_report": _artifact_record(qa_path),
    }
    return {
        "schema_version": 1,
        "status": "complete",
        "panel_rows": panel_rows,
        "artifacts": records,
        "artifact_set_sha256": _artifact_set_identity(records),
        "provenance": provenance,
    }


def _validate_input_identity(
    provenance: Mapping[str, object],
    *,
    inputs: _BoundInputs,
) -> None:
    manifest = inputs.manifest
    config = inputs.config
    for field, expected in inputs.file_sha256.items():
        if _sha256_text(provenance.get(field), field) != expected:
            raise PatientJourneyArtifactError(f"Artifact provenance {field!r} disagrees.")
    if _text(provenance.get("analysis_id"), "analysis_id") != config.analysis_id:
        raise PatientJourneyArtifactError("Artifact provenance analysis identity disagrees.")
    _validate_fixed_provenance(provenance, config)
    _validate_recorded_build_context(provenance)
    if (
        _integer(provenance.get("source_manifest_schema_version"), "source_manifest_schema_version")
        != manifest.schema_version
    ):
        raise PatientJourneyArtifactError("Artifact source-manifest schema version disagrees.")
    recorded_sources = _mapping(provenance.get("source_sha256"), "source_sha256")
    expected_sources = {source.release_code: source.download_sha256 for source in manifest.sources}
    if recorded_sources != expected_sources:
        raise PatientJourneyArtifactError("Artifact per-release source checksums disagree.")
    expected_thresholds = {
        "primary_min_target_n": config.eligibility.primary_min_target_n,
        "sensitivity_min_target_n": list(config.eligibility.sensitivity_min_target_n),
    }
    if _mapping(provenance.get("eligibility_thresholds"), "eligibility_thresholds") != (
        expected_thresholds
    ):
        raise PatientJourneyArtifactError("Artifact eligibility thresholds disagree.")
    expected_pairs = [
        _pair_payload(pair.feature_release_code, pair.target_release_code)
        for pair in config.temporal_design.primary_pairs
    ]
    if provenance.get("primary_pairs") != expected_pairs:
        raise PatientJourneyArtifactError("Artifact primary-pair provenance disagrees.")
    expected_exclusions = [asdict(pair) for pair in config.temporal_design.excluded_candidates]
    if provenance.get("excluded_candidates") != expected_exclusions:
        raise PatientJourneyArtifactError("Artifact excluded-pair provenance disagrees.")
    if _boolean(provenance.get("model_fitted"), "model_fitted"):
        raise PatientJourneyArtifactError(
            "A processed panel must not claim that a model was fitted."
        )
    if _mapping(provenance.get("model_parameters"), "model_parameters"):
        raise PatientJourneyArtifactError("A processed panel must not contain model parameters.")
    if provenance.get("panel_schema") != _schema_fields() or _hash_payload(
        provenance.get("panel_schema")
    ) != _sha256_text(provenance.get("panel_schema_sha256"), "panel_schema_sha256"):
        raise PatientJourneyArtifactError("Artifact panel-schema identity disagrees.")


def _validate_artifact_records(output_dir: Path, build_manifest: Mapping[str, object]) -> str:
    records = _mapping(build_manifest.get("artifacts"), "artifacts")
    if set(records) != {"panel", "qa_report"}:
        raise PatientJourneyArtifactError(
            "Artifact manifest must bind exactly the panel and QA report."
        )
    typed_records: dict[str, Mapping[str, object]] = {}
    for key, expected_name in (("panel", PANEL_NAME), ("qa_report", QA_NAME)):
        record = _mapping(records[key], f"artifacts.{key}")
        if _text(record.get("path"), f"artifacts.{key}.path") != expected_name:
            raise PatientJourneyArtifactError(f"Artifact path for {key!r} disagrees.")
        path = output_dir / expected_name
        if _integer(record.get("bytes"), f"artifacts.{key}.bytes") != path.stat().st_size:
            raise PatientJourneyArtifactError(f"Artifact size for {key!r} disagrees.")
        if _sha256_text(record.get("sha256"), f"artifacts.{key}.sha256") != _file_sha256(path):
            raise PatientJourneyArtifactError(f"Artifact checksum for {key!r} disagrees.")
        typed_records[key] = record
    artifact_set_sha256 = _artifact_set_identity(typed_records)
    if artifact_set_sha256 != _sha256_text(
        build_manifest.get("artifact_set_sha256"), "artifact_set_sha256"
    ):
        raise PatientJourneyArtifactError("Artifact-set checksum disagrees.")
    return artifact_set_sha256


def _validate_panel_payload(
    panel_path: Path,
    *,
    build_manifest: Mapping[str, object],
    provenance: Mapping[str, object],
    inputs: _BoundInputs,
) -> tuple[int, tuple[PatientJourneyPanelRow, ...]]:
    try:
        table = pq.read_table(panel_path)
    except (OSError, ValueError) as exc:
        raise PatientJourneyArtifactError("Patient-journey panel Parquet is unreadable.") from exc
    if table.schema.remove_metadata() != PATIENT_JOURNEY_PANEL_SCHEMA:
        raise PatientJourneyArtifactError("Patient-journey panel schema disagrees.")
    metadata = table.schema.metadata or {}
    try:
        panel_provenance: object = json.loads(metadata[b"kasm_provenance"])
    except (KeyError, UnicodeError, json.JSONDecodeError) as exc:
        raise PatientJourneyArtifactError("Patient-journey panel provenance is invalid.") from exc
    if panel_provenance != provenance:
        raise PatientJourneyArtifactError("Panel and manifest provenance disagree.")
    panel_rows = _integer(build_manifest.get("panel_rows"), "panel_rows")
    if table.num_rows != panel_rows:
        raise PatientJourneyArtifactError("Patient-journey panel row count disagrees.")
    constructor = cast(Any, PatientJourneyPanelRow)
    rows = tuple(constructor(**row) for row in table.to_pylist())
    try:
        validate_patient_journey_panel_rows(
            rows,
            config=inputs.config,
            ledger=inputs.ledger,
            sources=inputs.manifest.sources,
        )
    except PatientJourneyPanelError as exc:
        raise PatientJourneyArtifactError(f"Panel scientific validation failed: {exc}") from exc
    if provenance.get("methodology_ledger_identity") != methodology_ledger_identity(inputs.ledger):
        raise PatientJourneyArtifactError("Panel methodology identity disagrees.")
    if provenance.get("cohort_timing") != _cohort_timing(rows, inputs.config):
        raise PatientJourneyArtifactError("Panel cohort-timing provenance disagrees.")
    return panel_rows, rows


def _validate_qa_pair_summaries(
    qa: Mapping[str, object],
    *,
    rows: tuple[PatientJourneyPanelRow, ...],
    config: PatientJourneyConfig,
    ledger: MethodologyLedger,
) -> None:
    summaries = _sequence(qa.get("pair_summaries"), "qa.pair_summaries")
    by_pair: dict[tuple[str, str], JsonObject] = {}
    for index, value in enumerate(summaries):
        summary = _mapping(value, f"qa.pair_summaries[{index}]")
        key = (
            _text(summary.get("feature_release_code"), "feature_release_code"),
            _text(summary.get("target_release_code"), "target_release_code"),
        )
        if key in by_pair:
            raise PatientJourneyArtifactError("QA pair summaries contain a duplicate pair.")
        by_pair[key] = summary
    expected_pairs = {
        (pair.feature_release_code, pair.target_release_code)
        for pair in config.temporal_design.primary_pairs
    }
    if set(by_pair) != expected_pairs:
        raise PatientJourneyArtifactError("QA pair summaries disagree with configured pairs.")
    for pair, summary in by_pair.items():
        pair_rows = tuple(
            row for row in rows if (row.feature_release_code, row.target_release_code) == pair
        )
        expected_counts = {
            "prediction_universe_rows": len(pair_rows),
            "matched_target_rows": sum(not row.missing_target for row in pair_rows),
            "missing_target_rows": sum(row.missing_target for row in pair_rows),
            "primary_eligible_rows": sum(row.primary_analytic_eligible for row in pair_rows),
            "sensitivity_n20_eligible_rows": sum(row.sensitivity_n20_eligible for row in pair_rows),
            "sensitivity_n30_eligible_rows": sum(row.sensitivity_n30_eligible for row in pair_rows),
            "first_observed_rows": sum(row.first_observed_program for row in pair_rows),
        }
        for field, expected in expected_counts.items():
            if _integer(summary.get(field), f"qa.{field}") != expected:
                raise PatientJourneyArtifactError(f"QA pair-summary field {field!r} disagrees.")
        _validate_qa_pair_evidence(summary, pair_rows=pair_rows, ledger=ledger)


def _validate_qa_payload(
    qa_path: Path,
    *,
    provenance: Mapping[str, object],
    panel_rows: int,
    rows: tuple[PatientJourneyPanelRow, ...],
    inputs: _BoundInputs,
) -> None:
    qa = _read_json(qa_path)
    if _mapping(qa.get("provenance"), "qa.provenance") != provenance:
        raise PatientJourneyArtifactError("QA and manifest provenance disagree.")
    if _integer(qa.get("row_count"), "qa.row_count") != panel_rows:
        raise PatientJourneyArtifactError("QA and panel row counts disagree.")
    if qa.get("methodology_ledger_identity") != methodology_ledger_identity(inputs.ledger):
        raise PatientJourneyArtifactError("QA methodology identity disagrees.")
    if qa.get("strict_vintage_folds") != _fold_payloads(inputs.config, inputs.ledger):
        raise PatientJourneyArtifactError("QA strict-vintage fold evidence disagrees.")
    expected_exclusions = [
        asdict(pair) for pair in inputs.config.temporal_design.excluded_candidates
    ]
    if qa.get("excluded_candidates") != expected_exclusions:
        raise PatientJourneyArtifactError("QA excluded-pair evidence disagrees.")
    if qa.get("eligibility_thresholds") != provenance.get("eligibility_thresholds"):
        raise PatientJourneyArtifactError("QA eligibility thresholds disagree.")
    for field, expected in _eligibility_counts(rows).items():
        if qa.get(field) != expected:
            raise PatientJourneyArtifactError(f"QA field {field!r} disagrees with panel rows.")
    _validate_qa_pair_summaries(
        qa,
        rows=rows,
        config=inputs.config,
        ledger=inputs.ledger,
    )


def _validate_artifact_directory(
    output_dir: Path,
    *,
    inputs: _BoundInputs,
) -> PatientJourneyArtifactResult:
    if not output_dir.is_dir():
        raise PatientJourneyArtifactError(
            f"Patient-journey artifact directory is missing: {output_dir}."
        )
    actual_names = {path.name for path in output_dir.iterdir()}
    if actual_names != _ARTIFACT_NAMES:
        raise PatientJourneyArtifactError(
            f"Patient-journey artifact file set must be exactly {sorted(_ARTIFACT_NAMES)!r}."
        )
    panel_path = output_dir / PANEL_NAME
    qa_path = output_dir / QA_NAME
    manifest_path = output_dir / MANIFEST_NAME
    build_manifest = _read_json(manifest_path)
    if _integer(build_manifest.get("schema_version"), "schema_version") != 1:
        raise PatientJourneyArtifactError("Unsupported patient-journey artifact schema version.")
    if _text(build_manifest.get("status"), "status") != "complete":
        raise PatientJourneyArtifactError("Patient-journey artifact generation is incomplete.")
    provenance = _mapping(build_manifest.get("provenance"), "provenance")
    _validate_input_identity(provenance, inputs=inputs)
    artifact_set_sha256 = _validate_artifact_records(output_dir, build_manifest)
    panel_rows, rows = _validate_panel_payload(
        panel_path,
        build_manifest=build_manifest,
        provenance=provenance,
        inputs=inputs,
    )
    _validate_qa_payload(
        qa_path,
        provenance=provenance,
        panel_rows=panel_rows,
        rows=rows,
        inputs=inputs,
    )
    return PatientJourneyArtifactResult(
        output_directory=output_dir,
        panel_path=panel_path,
        qa_report_path=qa_path,
        manifest_path=manifest_path,
        panel_rows=panel_rows,
        artifact_set_sha256=artifact_set_sha256,
    )


def validate_patient_journey_artifacts(
    output_dir: Path,
    *,
    repository_root: Path,
    source_manifest_path: Path,
    experiment_config_path: Path,
    methodology_path: Path,
    lock_path: Path,
) -> PatientJourneyArtifactResult:
    """Validate the exact config-owned v2 generation before it is consumed."""
    inputs = _load_bound_inputs(
        repository_root=repository_root,
        source_manifest_path=source_manifest_path,
        experiment_config_path=experiment_config_path,
        methodology_path=methodology_path,
        lock_path=lock_path,
    )
    expected = _validate_destination(inputs.config, repository_root)
    if output_dir.resolve() != expected:
        raise PatientJourneyArtifactError(
            "Trusted validation is limited to the configured v2 processed output."
        )
    return _validate_artifact_directory(expected, inputs=inputs)


def _recover_interrupted_publication(output_dir: Path, *, inputs: _BoundInputs) -> None:
    backup = output_dir.parent / f".{output_dir.name}-backup"
    if not backup.exists():
        return
    if not backup.is_dir():
        raise PatientJourneyArtifactError(f"Artifact recovery path is not a directory: {backup}.")
    if not output_dir.exists():
        _validate_artifact_directory(backup, inputs=inputs)
        os.replace(backup, output_dir)
        return
    _validate_artifact_directory(output_dir, inputs=inputs)
    try:
        shutil.rmtree(backup)
    except OSError as exc:
        raise PatientJourneyArtifactError(
            f"Valid output is active, but stale artifact backup cleanup failed: {backup}."
        ) from exc


def _publish_staged_directory(staging: Path, output_dir: Path) -> None:
    backup = output_dir.parent / f".{output_dir.name}-backup"
    if backup.exists():
        raise PatientJourneyArtifactError(f"Artifact backup was not recovered: {backup}.")
    if output_dir.exists() and not output_dir.is_dir():
        raise PatientJourneyArtifactError(
            f"Artifact output exists and is not a directory: {output_dir}."
        )
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


def _write_patient_journey_artifacts(
    panel: PatientJourneyPanel,
    *,
    inputs: _BoundInputs,
    repository_root: Path,
    source_manifest_path: Path,
    experiment_config_path: Path,
    methodology_path: Path,
    lock_path: Path,
    build_context: PatientJourneyBuildContext,
) -> PatientJourneyArtifactResult:
    """Stage and publish a panel bound to one previously verified input snapshot."""
    output_dir = _validate_destination(inputs.config, repository_root)
    try:
        validate_patient_journey_panel_rows(
            panel.rows,
            config=inputs.config,
            ledger=inputs.ledger,
            sources=inputs.manifest.sources,
        )
    except PatientJourneyPanelError as exc:
        raise PatientJourneyArtifactError(f"Panel scientific validation failed: {exc}") from exc
    _validate_panel_evidence(panel, config=inputs.config, ledger=inputs.ledger)
    table = patient_journey_panel_table(panel.rows)
    provenance = _provenance(
        panel,
        inputs=inputs,
        build_context=build_context,
    )
    table = table.replace_schema_metadata(
        {b"kasm_provenance": json.dumps(provenance, sort_keys=True).encode()}
    )
    qa = _qa_report(
        panel,
        provenance,
        config=inputs.config,
        ledger=inputs.ledger,
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    _recover_interrupted_publication(output_dir, inputs=inputs)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-staging-", dir=output_dir.parent))
    published = False
    try:
        panel_path = staging / PANEL_NAME
        qa_path = staging / QA_NAME
        manifest_path = staging / MANIFEST_NAME
        pq.write_table(
            table,
            panel_path,
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )
        _write_json(qa_path, qa)
        build_manifest = _manifest(
            panel_path,
            qa_path,
            panel_rows=table.num_rows,
            provenance=provenance,
        )
        _write_json(manifest_path, build_manifest)
        publication_inputs = _reload_matching_inputs(
            inputs,
            repository_root=repository_root,
            source_manifest_path=source_manifest_path,
            experiment_config_path=experiment_config_path,
            methodology_path=methodology_path,
            lock_path=lock_path,
            context="before artifact publication",
        )
        _validate_artifact_directory(staging, inputs=publication_inputs)
        _publish_staged_directory(staging, output_dir)
        published = True
    finally:
        if not published:
            shutil.rmtree(staging, ignore_errors=True)
    return validate_patient_journey_artifacts(
        output_dir,
        repository_root=repository_root,
        source_manifest_path=source_manifest_path,
        experiment_config_path=experiment_config_path,
        methodology_path=methodology_path,
        lock_path=lock_path,
    )


def write_patient_journey_artifacts(
    panel: PatientJourneyPanel,
    *,
    repository_root: Path,
    source_manifest_path: Path,
    experiment_config_path: Path,
    methodology_path: Path,
    lock_path: Path,
    build_context: PatientJourneyBuildContext,
) -> PatientJourneyArtifactResult:
    """Stage, validate, and atomically publish the config-owned processed generation."""
    inputs = _load_bound_inputs(
        repository_root=repository_root,
        source_manifest_path=source_manifest_path,
        experiment_config_path=experiment_config_path,
        methodology_path=methodology_path,
        lock_path=lock_path,
    )
    return _write_patient_journey_artifacts(
        panel,
        inputs=inputs,
        repository_root=repository_root,
        source_manifest_path=source_manifest_path,
        experiment_config_path=experiment_config_path,
        methodology_path=methodology_path,
        lock_path=lock_path,
        build_context=build_context,
    )


def build_cached_patient_journey_artifacts(
    *,
    repository_root: Path,
    source_manifest_path: Path,
    experiment_config_path: Path,
    methodology_path: Path,
    cache_dir: Path,
    lock_path: Path,
) -> PatientJourneyArtifactResult:
    """Build and publish v2 processed artifacts from the immutable verified cache."""
    inputs = _load_bound_inputs(
        repository_root=repository_root,
        source_manifest_path=source_manifest_path,
        experiment_config_path=experiment_config_path,
        methodology_path=methodology_path,
        lock_path=lock_path,
    )
    panel = build_cached_patient_journey_panel(
        manifest=inputs.manifest,
        ledger=inputs.ledger,
        config=inputs.config,
        cache_dir=_repository_path(cache_dir, repository_root.resolve()),
    )
    _reload_matching_inputs(
        inputs,
        repository_root=repository_root,
        source_manifest_path=source_manifest_path,
        experiment_config_path=experiment_config_path,
        methodology_path=methodology_path,
        lock_path=lock_path,
        context="during panel construction",
    )
    return _write_patient_journey_artifacts(
        panel,
        inputs=inputs,
        repository_root=repository_root,
        source_manifest_path=source_manifest_path,
        experiment_config_path=experiment_config_path,
        methodology_path=methodology_path,
        lock_path=lock_path,
        build_context=current_patient_journey_build_context(repository_root),
    )
