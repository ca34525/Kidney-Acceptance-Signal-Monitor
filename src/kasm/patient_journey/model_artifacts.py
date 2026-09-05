"""Trusted exploratory model evidence for patient-journey V2."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from kasm.patient_journey.artifacts import (
    PatientJourneyArtifactResult,
    current_patient_journey_build_context,
    validate_patient_journey_artifacts,
)
from kasm.patient_journey.config import PatientJourneyConfig, load_patient_journey_config
from kasm.patient_journey.evaluation import (
    EvaluationPrediction,
    paired_clustered_bootstrap_interval,
    summarize_predictions,
)
from kasm.patient_journey.modeling import (
    generate_baseline_predictions,
    generate_ridge_predictions,
)

PREDICTIONS_NAME = "predictions.parquet"
EVALUATION_NAME = "evaluation.json"
MANIFEST_NAME = "build_manifest.json"
_ARTIFACT_NAMES = frozenset((PREDICTIONS_NAME, EVALUATION_NAME, MANIFEST_NAME))
_CATEGORY = pa.dictionary(pa.int8(), pa.string())

PATIENT_JOURNEY_PREDICTION_SCHEMA = pa.schema(
    [
        pa.field("program_key", pa.string(), nullable=False),
        pa.field("feature_release_code", pa.string(), nullable=False),
        pa.field("target_release_code", pa.string(), nullable=False),
        pa.field("model", _CATEGORY, nullable=False),
        pa.field("training_pairs_json", pa.string(), nullable=False),
        pa.field("target_n", pa.int64(), nullable=False),
        pa.field("target_published_percent", pa.float64(), nullable=False),
        pa.field("predicted_proportion", pa.float64(), nullable=False),
        pa.field("predicted_percent", pa.float64(), nullable=False),
        pa.field("absolute_error_percentage_points", pa.float64(), nullable=False),
        pa.field("signed_error_percentage_points", pa.float64(), nullable=False),
        pa.field("volume_quartile", pa.int8(), nullable=False),
        pa.field("first_observed_program", pa.bool_(), nullable=False),
        pa.field("any_model_feature_missing", pa.bool_(), nullable=False),
    ]
)


class PatientJourneyModelArtifactError(ValueError):
    """Raised when V2 model evidence violates the frozen nonpromotion contract."""


@dataclass(frozen=True)
class PatientJourneyModelEvaluation:
    """Deterministic predictions and JSON-ready exploratory evidence."""

    predictions: tuple[EvaluationPrediction, ...]
    evidence: dict[str, object]


@dataclass(frozen=True)
class PatientJourneyModelArtifactResult:
    """Validated output paths for one atomic V2 model-evidence generation."""

    output_directory: Path
    predictions_path: Path
    evaluation_path: Path
    manifest_path: Path
    prediction_rows: int
    artifact_set_sha256: str


def _summary_payload(predictions: Sequence[EvaluationPrediction]) -> dict[str, object]:
    return asdict(summarize_predictions(predictions))


def _model_payload(
    predictions: tuple[EvaluationPrediction, ...],
    *,
    kind: str,
    features: tuple[str, ...],
    sensitivity_thresholds: tuple[int, int],
) -> dict[str, object]:
    by_release = {
        release: _summary_payload(
            tuple(row for row in predictions if row.target_release_code == release)
        )
        for release in sorted({row.target_release_code for row in predictions})
    }
    by_volume_quartile = {
        str(quartile): _summary_payload(
            tuple(row for row in predictions if row.volume_quartile == quartile)
        )
        for quartile in range(1, 5)
        if any(row.volume_quartile == quartile for row in predictions)
    }
    sensitivity = {
        f"target_n_at_least_{threshold}": _summary_payload(
            tuple(row for row in predictions if row.target_n >= threshold)
        )
        for threshold in sensitivity_thresholds
        if any(row.target_n >= threshold for row in predictions)
    }
    missingness: dict[str, object] = {}
    if kind == "ridge":
        for is_missing, label in ((False, "complete_features"), (True, "any_feature_missing")):
            rows = tuple(row for row in predictions if row.any_model_feature_missing is is_missing)
            if rows:
                missingness[label] = _summary_payload(rows)
    return {
        "kind": kind,
        "features": list(features),
        "primary": _summary_payload(predictions),
        "by_target_release": by_release,
        "by_volume_quartile": by_volume_quartile,
        "sensitivity": sensitivity,
        "missingness": missingness,
    }


def evaluate_patient_journey_rows(
    rows: Sequence[Mapping[str, object]],
    config: PatientJourneyConfig,
) -> PatientJourneyModelEvaluation:
    """Apply the complete frozen retrospective evaluation without selecting a winner."""
    if config.model_design.ridge.promotion_allowed:
        raise PatientJourneyModelArtifactError(
            "Patient-journey V2 cannot evaluate with model promotion enabled."
        )
    baseline_predictions = generate_baseline_predictions(rows, config)
    ridge_predictions = generate_ridge_predictions(rows, config)
    predictions = (*baseline_predictions, *ridge_predictions)
    by_model = {
        model: tuple(row for row in predictions if row.model == model)
        for model in (
            *config.model_design.baselines,
            *(g.name for g in config.model_design.feature_groups),
        )
    }
    feature_by_group = {group.name: group.features for group in config.model_design.feature_groups}
    models = {
        model: _model_payload(
            model_predictions,
            kind="baseline" if model in config.model_design.baselines else "ridge",
            features=feature_by_group.get(model, ()),
            sensitivity_thresholds=config.eligibility.sensitivity_min_target_n,
        )
        for model, model_predictions in by_model.items()
    }
    bootstrap = config.model_design.bootstrap
    contrasts = []
    for challenger, comparator in config.model_design.contrasts:
        interval = paired_clustered_bootstrap_interval(
            by_model[challenger],
            by_model[comparator],
            resamples=bootstrap.resamples,
            seed=bootstrap.seed,
            percentiles=bootstrap.percentiles,
        )
        contrasts.append(
            {
                "challenger": challenger,
                "comparator": comparator,
                "estimand": bootstrap.contrast,
                "units": "percentage_points",
                **asdict(interval),
            }
        )
    ridge = config.model_design.ridge
    evidence: dict[str, object] = {
        "schema_version": 1,
        "analysis_id": config.analysis_id,
        "evaluation_mode": config.temporal_design.evaluation_mode,
        "evidence_status": "retrospective_exploratory_feasibility",
        "target": {
            "field": config.target_column,
            "label": "published observed 18-month functioning-transplant percentage",
            "officially_risk_adjusted": False,
        },
        "error_units": "percentage_points",
        "promotion_allowed": False,
        "promoted_model": None,
        "ridge_training_pairs": [list(pair) for pair in ridge.training_pairs],
        "ridge_evaluation_pair": list(ridge.evaluation_pair),
        "ridge_parameters": {
            "alpha": ridge.alpha,
            "solver": ridge.solver,
            "tolerance": ridge.tolerance,
            "max_iterations": ridge.max_iterations,
            "target_scale": "empirical_logit",
            "inverse_link": "logistic",
            "preprocessing": {
                "imputation": "median",
                "keep_empty_features": True,
                "scaling": "standard",
                "fit_scope": "training_fold_only",
            },
        },
        "models": models,
        "contrasts": contrasts,
        "bootstrap": {
            "cluster": bootstrap.cluster,
            "resamples": bootstrap.resamples,
            "seed": bootstrap.seed,
            "percentiles": list(bootstrap.percentiles),
            "quantile_method": bootstrap.quantile_method,
        },
        "limitations": [
            "Only one strict-publication-vintage Ridge fold is evaluable.",
            "The evidence is retrospective and exploratory, not prospective or independent "
            "validation.",
            "No model is selected or promoted from this evaluation.",
            "The published patient-journey outcome is observed and is not officially risk "
            "adjusted.",
            "Safety measures retain distinct populations, denominators, timing, and uncertainty.",
        ],
    }
    return PatientJourneyModelEvaluation(
        predictions=tuple(predictions),
        evidence=evidence,
    )


def _json_normalized(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prediction_rows(
    predictions: Sequence[EvaluationPrediction],
) -> list[dict[str, object]]:
    return [
        {
            "program_key": row.program_key,
            "feature_release_code": row.feature_release_code,
            "target_release_code": row.target_release_code,
            "model": row.model,
            "training_pairs_json": json.dumps(
                [list(pair) for pair in row.training_pairs],
                separators=(",", ":"),
            ),
            "target_n": row.target_n,
            "target_published_percent": row.target_published_percent,
            "predicted_proportion": row.predicted_proportion,
            "predicted_percent": row.predicted_percent,
            "absolute_error_percentage_points": row.absolute_error_percentage_points,
            "signed_error_percentage_points": row.signed_error_percentage_points,
            "volume_quartile": row.volume_quartile,
            "first_observed_program": row.first_observed_program,
            "any_model_feature_missing": row.any_model_feature_missing,
        }
        for row in sorted(
            predictions,
            key=lambda item: (
                item.model,
                item.target_release_code,
                item.program_key,
            ),
        )
    ]


def patient_journey_prediction_table(
    predictions: Sequence[EvaluationPrediction],
) -> pa.Table:
    """Construct the exact deterministic model-prediction schema."""
    rows = _prediction_rows(predictions)
    arrays = [
        pa.array([row[field.name] for row in rows], type=field.type)
        for field in PATIENT_JOURNEY_PREDICTION_SCHEMA
    ]
    return pa.Table.from_arrays(arrays, schema=PATIENT_JOURNEY_PREDICTION_SCHEMA)


def _artifact_record(path: Path) -> dict[str, object]:
    return {
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": _file_sha256(path),
    }


def _artifact_set_identity(records: Mapping[str, Mapping[str, object]]) -> str:
    normalized = {
        name: {"bytes": record["bytes"], "sha256": record["sha256"]}
        for name, record in sorted(records.items())
    }
    return sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _publish_staging(staging: Path, output_dir: Path) -> None:
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


def write_model_evaluation_directory(
    evaluation: PatientJourneyModelEvaluation,
    *,
    output_dir: Path,
    provenance: Mapping[str, object],
) -> PatientJourneyModelArtifactResult:
    """Write one exact model-evidence generation atomically and validate it."""
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-staging-", dir=output_dir.parent))
    published = False
    try:
        predictions_path = staging / PREDICTIONS_NAME
        evaluation_path = staging / EVALUATION_NAME
        manifest_path = staging / MANIFEST_NAME
        table = patient_journey_prediction_table(evaluation.predictions)
        normalized_provenance = cast(dict[str, object], _json_normalized(provenance))
        table = table.replace_schema_metadata(
            {b"kasm_provenance": json.dumps(normalized_provenance, sort_keys=True).encode()}
        )
        pq.write_table(
            table,
            predictions_path,
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )
        _write_json(evaluation_path, evaluation.evidence)
        records = {
            "predictions": _artifact_record(predictions_path),
            "evaluation": _artifact_record(evaluation_path),
        }
        manifest = {
            "schema_version": 1,
            "status": "complete",
            "prediction_rows": table.num_rows,
            "artifacts": records,
            "artifact_set_sha256": _artifact_set_identity(records),
            "provenance": normalized_provenance,
        }
        _write_json(manifest_path, manifest)
        validate_model_evaluation_directory(
            staging,
            expected=evaluation,
            expected_provenance=provenance,
        )
        _publish_staging(staging, output_dir)
        published = True
    finally:
        if not published:
            shutil.rmtree(staging, ignore_errors=True)
    return validate_model_evaluation_directory(
        output_dir,
        expected=evaluation,
        expected_provenance=provenance,
    )


def _read_model_json(path: Path, *, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PatientJourneyModelArtifactError(f"Model {label} is unreadable.") from exc


def _validate_model_artifact_records(
    records: object,
    *,
    predictions_path: Path,
    evaluation_path: Path,
) -> tuple[dict[str, Mapping[str, object]], str]:
    if not isinstance(records, dict) or set(records) != {"predictions", "evaluation"}:
        raise PatientJourneyModelArtifactError("Model artifact records are incomplete.")
    typed_records: dict[str, Mapping[str, object]] = {}
    for key, path in (("predictions", predictions_path), ("evaluation", evaluation_path)):
        record = records.get(key)
        if not isinstance(record, dict):
            raise PatientJourneyModelArtifactError("Model artifact record is invalid.")
        if (
            record.get("path") != path.name
            or record.get("bytes") != path.stat().st_size
            or record.get("sha256") != _file_sha256(path)
        ):
            raise PatientJourneyModelArtifactError(f"Model {key} checksum or size disagrees.")
        typed_records[key] = record
    return typed_records, _artifact_set_identity(typed_records)


def _validate_prediction_payload(
    predictions_path: Path,
    *,
    expected: PatientJourneyModelEvaluation,
    expected_provenance: Mapping[str, object],
    prediction_rows: object,
) -> int:
    try:
        table = pq.read_table(predictions_path)
    except (OSError, ValueError) as exc:
        raise PatientJourneyModelArtifactError("Model predictions are unreadable.") from exc
    if table.schema.remove_metadata() != PATIENT_JOURNEY_PREDICTION_SCHEMA:
        raise PatientJourneyModelArtifactError("Model prediction schema disagrees.")
    metadata = table.schema.metadata or {}
    try:
        table_provenance: object = json.loads(metadata[b"kasm_provenance"])
    except (KeyError, UnicodeError, json.JSONDecodeError) as exc:
        raise PatientJourneyModelArtifactError("Model prediction provenance is invalid.") from exc
    if table_provenance != _json_normalized(expected_provenance):
        raise PatientJourneyModelArtifactError("Prediction provenance disagrees.")
    expected_rows = _prediction_rows(expected.predictions)
    if table.to_pylist() != expected_rows or prediction_rows != len(expected_rows):
        raise PatientJourneyModelArtifactError("Model predictions disagree with recomputation.")
    return len(expected_rows)


def validate_model_evaluation_directory(
    output_dir: Path,
    *,
    expected: PatientJourneyModelEvaluation,
    expected_provenance: Mapping[str, object],
) -> PatientJourneyModelArtifactResult:
    """Reject incomplete, rehashed, or analytically changed model evidence."""
    if not output_dir.is_dir() or {path.name for path in output_dir.iterdir()} != _ARTIFACT_NAMES:
        raise PatientJourneyModelArtifactError(
            "Model artifact directory does not contain the exact trusted file set."
        )
    manifest_path = output_dir / MANIFEST_NAME
    evaluation_path = output_dir / EVALUATION_NAME
    predictions_path = output_dir / PREDICTIONS_NAME
    manifest = _read_model_json(manifest_path, label="manifest")
    if not isinstance(manifest, dict):
        raise PatientJourneyModelArtifactError("Model manifest must be a JSON object.")
    if manifest.get("schema_version") != 1 or manifest.get("status") != "complete":
        raise PatientJourneyModelArtifactError("Model manifest is incomplete or unsupported.")
    if manifest.get("provenance") != _json_normalized(expected_provenance):
        raise PatientJourneyModelArtifactError("Model provenance disagrees with trusted inputs.")
    _, identity = _validate_model_artifact_records(
        manifest.get("artifacts"),
        predictions_path=predictions_path,
        evaluation_path=evaluation_path,
    )
    if manifest.get("artifact_set_sha256") != identity:
        raise PatientJourneyModelArtifactError("Model artifact-set checksum disagrees.")
    evidence = _read_model_json(evaluation_path, label="evaluation JSON")
    if evidence != _json_normalized(expected.evidence):
        raise PatientJourneyModelArtifactError("Model evaluation disagrees with recomputation.")
    prediction_count = _validate_prediction_payload(
        predictions_path,
        expected=expected,
        expected_provenance=expected_provenance,
        prediction_rows=manifest.get("prediction_rows"),
    )
    return PatientJourneyModelArtifactResult(
        output_directory=output_dir,
        predictions_path=predictions_path,
        evaluation_path=evaluation_path,
        manifest_path=manifest_path,
        prediction_rows=prediction_count,
        artifact_set_sha256=identity,
    )


def _resolved(path: Path, repository_root: Path) -> Path:
    return path.resolve() if path.is_absolute() else (repository_root / path).resolve()


def _processed_provenance(processed_manifest_path: Path) -> Mapping[str, object]:
    try:
        value: object = json.loads(processed_manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PatientJourneyModelArtifactError("Processed manifest is unreadable.") from exc
    if not isinstance(value, dict) or not isinstance(value.get("provenance"), dict):
        raise PatientJourneyModelArtifactError("Processed manifest provenance is invalid.")
    return cast(Mapping[str, object], value["provenance"])


def _build_provenance(
    *,
    repository_root: Path,
    source_manifest_path: Path,
    experiment_config_path: Path,
    methodology_path: Path,
    lock_path: Path,
    processed: PatientJourneyArtifactResult,
    build_timestamp_utc: str,
    git_commit_sha: str,
    git_worktree_dirty: bool,
    python_version: str,
) -> dict[str, object]:
    processed_source = _processed_provenance(processed.manifest_path)
    return {
        "analysis_id": "kidney_patient_journey_v2",
        "processed_artifact_set_sha256": processed.artifact_set_sha256,
        "processed_manifest_sha256": _file_sha256(processed.manifest_path),
        "processed_panel_sha256": _file_sha256(processed.panel_path),
        "processed_safety_sha256": _file_sha256(processed.safety_path),
        "source_manifest_sha256": _file_sha256(_resolved(source_manifest_path, repository_root)),
        "experiment_config_sha256": _file_sha256(
            _resolved(experiment_config_path, repository_root)
        ),
        "methodology_config_sha256": _file_sha256(_resolved(methodology_path, repository_root)),
        "dependency_lock_sha256": _file_sha256(_resolved(lock_path, repository_root)),
        "source_sha256": processed_source.get("source_sha256"),
        "git_commit_sha": git_commit_sha,
        "git_worktree_dirty": git_worktree_dirty,
        "canonical_build": not git_worktree_dirty,
        "build_timestamp_utc": build_timestamp_utc,
        "python_version": python_version,
    }


def build_patient_journey_model_artifacts(
    *,
    repository_root: Path,
    source_manifest_path: Path,
    experiment_config_path: Path,
    methodology_path: Path,
    lock_path: Path,
) -> PatientJourneyModelArtifactResult:
    """Evaluate the frozen design from trusted processed artifacts and publish atomically."""
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
    try:
        rows = pq.read_table(processed.panel_path).to_pylist()
    except (OSError, ValueError) as exc:
        raise PatientJourneyModelArtifactError("Trusted processed panel is unreadable.") from exc
    evaluation = evaluate_patient_journey_rows(rows, config)
    context = current_patient_journey_build_context(root)
    timestamp = context.build_timestamp_utc.isoformat().replace("+00:00", "Z")
    provenance = _build_provenance(
        repository_root=root,
        source_manifest_path=source_manifest_path,
        experiment_config_path=experiment_config_path,
        methodology_path=methodology_path,
        lock_path=lock_path,
        processed=processed,
        build_timestamp_utc=timestamp,
        git_commit_sha=context.git_commit_sha,
        git_worktree_dirty=context.git_worktree_dirty,
        python_version=context.python_version,
    )
    output_dir = _resolved(config.paths.modeling_dir, root)
    if output_dir == root or root not in output_dir.parents:
        raise PatientJourneyModelArtifactError(
            "Configured model output must remain inside the repository."
        )
    return write_model_evaluation_directory(
        evaluation,
        output_dir=output_dir,
        provenance=provenance,
    )


def validate_patient_journey_model_artifacts(
    *,
    repository_root: Path,
    source_manifest_path: Path,
    experiment_config_path: Path,
    methodology_path: Path,
    lock_path: Path,
) -> PatientJourneyModelArtifactResult:
    """Recompute and validate model evidence against the current trusted processed bundle."""
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
    rows = pq.read_table(processed.panel_path).to_pylist()
    evaluation = evaluate_patient_journey_rows(rows, config)
    output_dir = _resolved(config.paths.modeling_dir, root)
    manifest_path = output_dir / MANIFEST_NAME
    try:
        manifest: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PatientJourneyModelArtifactError("Model manifest is unreadable.") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("provenance"), dict):
        raise PatientJourneyModelArtifactError("Model manifest provenance is invalid.")
    recorded = cast(Mapping[str, object], manifest["provenance"])
    timestamp = recorded.get("build_timestamp_utc")
    git_commit_sha = recorded.get("git_commit_sha")
    dirty = recorded.get("git_worktree_dirty")
    python_version = recorded.get("python_version")
    if (
        not isinstance(timestamp, str)
        or not timestamp.endswith("Z")
        or not isinstance(git_commit_sha, str)
        or len(git_commit_sha) not in range(40, 65)
        or not isinstance(dirty, bool)
        or not isinstance(python_version, str)
        or not python_version
    ):
        raise PatientJourneyModelArtifactError("Model build context is invalid.")
    expected_provenance = _build_provenance(
        repository_root=root,
        source_manifest_path=source_manifest_path,
        experiment_config_path=experiment_config_path,
        methodology_path=methodology_path,
        lock_path=lock_path,
        processed=processed,
        build_timestamp_utc=timestamp,
        git_commit_sha=git_commit_sha,
        git_worktree_dirty=dirty,
        python_version=python_version,
    )
    return validate_model_evaluation_directory(
        output_dir,
        expected=evaluation,
        expected_provenance=expected_provenance,
    )
