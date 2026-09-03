"""Build and validate the single tracked, offline release bundle."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from math import isfinite
from pathlib import Path, PurePosixPath
from typing import cast

import yaml

from kasm.config import DataSourceManifest, load_data_source_manifest

MAX_RELEASE_BYTES = 5 * 1024 * 1024
RELEASE_MANIFEST_NAME = "release_manifest.json"

_PROCESSED_FILES = (
    "model_panel.parquet",
    "program_signals.parquet",
    "qa_report.json",
)
_MODELING_FILES = (
    "baseline_metrics.json",
    "baseline_predictions.parquet",
    "ridge_metrics.json",
    "ridge_predictions.parquet",
    "ridge_selection.json",
    "temporal_folds.json",
)
_REPLAY_FILES = ("completion.json", "replay_metrics.json", "replay_predictions.parquet")
_SHA256_LENGTH = 64

JsonObject = dict[str, object]


class ReleaseBundleError(ValueError):
    """Raised when canonical inputs or a release bundle violate the release contract."""


@dataclass(frozen=True)
class ReleaseBundleResult:
    """Paths and stable content identity for one validated release bundle."""

    output_directory: Path
    manifest_path: Path
    file_count: int
    total_bytes: int
    bundle_content_sha256: str


@dataclass(frozen=True)
class _CanonicalFile:
    canonical_root: str
    canonical_path: str
    source: Path
    destination: PurePosixPath


def _file_sha256(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ReleaseBundleError(f"Release artifact is unreadable: {path}.") from exc
    return digest.hexdigest()


def _read_json(path: Path) -> JsonObject:
    if not path.is_file():
        raise ReleaseBundleError(f"Required canonical artifact is missing: {path}.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseBundleError(f"Canonical JSON artifact is invalid: {path}.") from exc
    if not isinstance(value, dict):
        raise ReleaseBundleError(f"Canonical JSON artifact must contain an object: {path}.")
    return cast(JsonObject, value)


def _object(value: object, field: str) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ReleaseBundleError(f"Release field {field!r} must be an object.")
    return cast(JsonObject, value)


def _array(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise ReleaseBundleError(f"Release field {field!r} must be an array.")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReleaseBundleError(f"Release field {field!r} must be nonempty text.")
    return value


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReleaseBundleError(f"Release field {field!r} must be an integer.")
    return value


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ReleaseBundleError(f"Release field {field!r} must be boolean.")
    return value


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ReleaseBundleError(f"Release field {field!r} must be numeric.")
    rendered = float(value)
    if not isfinite(rendered):
        raise ReleaseBundleError(f"Release field {field!r} must be finite.")
    return rendered


def _sha256_text(value: object, field: str) -> str:
    rendered = _text(value, field)
    if len(rendered) != _SHA256_LENGTH or any(
        character not in "0123456789abcdef" for character in rendered
    ):
        raise ReleaseBundleError(f"Release field {field!r} must be a lowercase SHA-256.")
    return rendered


def _json_bytes(value: Mapping[str, object]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.write_bytes(_json_bytes(value))


def _bundle_content_sha256(entries: Sequence[Mapping[str, object]]) -> str:
    identity = [
        {
            "bytes": _integer(entry.get("bytes"), "files.bytes"),
            "path": _text(entry.get("path"), "files.path"),
            "sha256": _sha256_text(entry.get("sha256"), "files.sha256"),
        }
        for entry in entries
    ]
    identity.sort(key=lambda entry: cast(str, entry["path"]))
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return sha256(payload).hexdigest()


def _source_hashes(manifest: DataSourceManifest) -> dict[str, str]:
    return {source.release_code: source.download_sha256 for source in manifest.sources}


def _yaml_object(path: Path, label: str) -> JsonObject:
    try:
        value: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ReleaseBundleError(f"{label} is unreadable or invalid YAML: {path}.") from exc
    return _object(value, label)


def _replay_directory(modeling_dir: Path) -> Path:
    completion_paths = tuple(sorted((modeling_dir / "frozen-replay").glob("*/completion.json")))
    if len(completion_paths) != 1:
        raise ReleaseBundleError(
            "Release build requires exactly one completed canonical frozen replay; "
            f"found {len(completion_paths)}."
        )
    return completion_paths[0].parent


def _canonical_files(
    processed_dir: Path, modeling_dir: Path, replay_dir: Path
) -> tuple[_CanonicalFile, ...]:
    files = [
        _CanonicalFile("processed", name, processed_dir / name, PurePosixPath("processed", name))
        for name in _PROCESSED_FILES
    ]
    files.extend(
        _CanonicalFile("modeling", name, modeling_dir / name, PurePosixPath("modeling", name))
        for name in _MODELING_FILES
    )
    files.extend(
        _CanonicalFile(
            "modeling",
            f"frozen-replay/{replay_dir.name}/{name}",
            replay_dir / name,
            PurePosixPath("modeling", "frozen-replay", replay_dir.name, name),
        )
        for name in _REPLAY_FILES
    )
    for artifact in files:
        if not artifact.source.is_file():
            raise ReleaseBundleError(f"Required canonical artifact is missing: {artifact.source}.")
    return tuple(files)


def _verify_input_identity(
    *,
    processed_dir: Path,
    modeling_dir: Path,
    replay_dir: Path,
    source_manifest_path: Path,
    experiment_config_path: Path,
    frozen_experiment_path: Path,
    lock_path: Path,
) -> tuple[JsonObject, JsonObject, DataSourceManifest, str]:
    source_manifest = load_data_source_manifest(source_manifest_path)
    source_manifest_hash = _file_sha256(source_manifest_path)
    frozen_hash = _file_sha256(frozen_experiment_path)
    experiment_hash = _file_sha256(experiment_config_path)
    lock_hash = _file_sha256(lock_path)
    panel_hash = _file_sha256(processed_dir / "model_panel.parquet")

    completion = _read_json(replay_dir / "completion.json")
    if completion.get("status") != "complete":
        raise ReleaseBundleError("Canonical frozen replay completion ledger is not complete.")
    if replay_dir.name != f"{frozen_hash}_{source_manifest_hash}":
        raise ReleaseBundleError("Canonical frozen replay directory does not match config hashes.")
    expected_completion = {
        "frozen_experiment_sha256": frozen_hash,
        "source_manifest_sha256": source_manifest_hash,
        "input_panel_sha256": panel_hash,
    }
    for field, expected in expected_completion.items():
        if _sha256_text(completion.get(field), f"completion.{field}") != expected:
            raise ReleaseBundleError(f"Canonical replay completion field {field!r} disagrees.")

    replay_artifacts = _object(completion.get("artifacts"), "completion.artifacts")
    replay_checksums = _object(completion.get("artifact_sha256"), "completion.artifact_sha256")
    for key, expected_name in (
        ("metrics", "replay_metrics.json"),
        ("predictions", "replay_predictions.parquet"),
    ):
        if _text(replay_artifacts.get(key), f"completion.artifacts.{key}") != expected_name:
            raise ReleaseBundleError(f"Canonical replay {key} filename is not approved.")
        if _sha256_text(
            replay_checksums.get(key), f"completion.artifact_sha256.{key}"
        ) != _file_sha256(replay_dir / expected_name):
            raise ReleaseBundleError(f"Canonical replay {key} checksum disagrees with its ledger.")

    replay_metrics = _read_json(replay_dir / "replay_metrics.json")
    if replay_metrics.get("frozen_replay_evaluated") is not True:
        raise ReleaseBundleError("Replay metrics must be frozen replay evidence.")
    if replay_metrics.get("prospective_validation") is not False:
        raise ReleaseBundleError("Replay metrics must not claim prospective validation.")
    provenance = _object(replay_metrics.get("provenance"), "replay_metrics.provenance")
    expected_provenance_hashes = {
        "dependency_lock_sha256": lock_hash,
        "frozen_experiment_sha256": frozen_hash,
        "source_manifest_sha256": source_manifest_hash,
        "input_panel_sha256": panel_hash,
    }
    for field, expected in expected_provenance_hashes.items():
        if _sha256_text(provenance.get(field), f"provenance.{field}") != expected:
            raise ReleaseBundleError(f"Replay provenance field {field!r} disagrees.")
    if (
        _integer(
            provenance.get("source_manifest_schema_version"),
            "provenance.source_manifest_schema_version",
        )
        != source_manifest.schema_version
    ):
        raise ReleaseBundleError("Replay provenance source-manifest version disagrees.")
    recorded_sources = _object(provenance.get("source_sha256"), "provenance.source_sha256")
    if recorded_sources != _source_hashes(source_manifest):
        raise ReleaseBundleError("Replay provenance source checksums disagree with the manifest.")

    for field in (
        "build_timestamp_utc",
        "feature_schema_sha256",
        "git_commit_sha",
        "methodology_version_ledger_sha256",
        "python_version",
    ):
        _text(provenance.get(field), f"provenance.{field}")
    _array(provenance.get("feature_columns"), "provenance.feature_columns")
    _array(provenance.get("training_target_years"), "provenance.training_target_years")
    _object(provenance.get("model_parameters"), "provenance.model_parameters")
    _integer(provenance.get("calibration_target_year"), "provenance.calibration_target_year")
    _integer(provenance.get("replay_target_year"), "provenance.replay_target_year")
    _array(replay_metrics.get("methodology_version_ledger"), "methodology_version_ledger")

    for name in (
        "baseline_metrics.json",
        "ridge_metrics.json",
        "ridge_selection.json",
        "temporal_folds.json",
    ):
        artifact = _read_json(modeling_dir / name)
        if (
            _sha256_text(artifact.get("input_panel_sha256"), f"{name}.input_panel_sha256")
            != panel_hash
        ):
            raise ReleaseBundleError(f"Canonical {name} uses a different model panel.")
        if (
            _sha256_text(
                artifact.get("experiment_config_sha256"), f"{name}.experiment_config_sha256"
            )
            != experiment_hash
        ):
            raise ReleaseBundleError(f"Canonical {name} uses a different experiment config.")
    for name in ("baseline_metrics.json", "ridge_metrics.json"):
        if _read_json(modeling_dir / name).get("frozen_replay_evaluated") is not False:
            raise ReleaseBundleError(f"Canonical {name} must remain pre-replay evidence.")

    return completion, provenance, source_manifest, experiment_hash


def _manifest_provenance(
    *,
    provenance: Mapping[str, object],
    source_manifest: DataSourceManifest,
    experiment_hash: str,
    frozen_config: Mapping[str, object],
) -> JsonObject:
    temporal = _object(frozen_config.get("temporal_evaluation"), "temporal_evaluation")
    validation_year = _integer(
        temporal.get("validation_target_year"), "temporal_evaluation.validation_target_year"
    )
    copied = dict(provenance)
    copied["experiment_config_sha256"] = experiment_hash
    copied["source_cohort_years"] = sorted(source.cohort_year for source in source_manifest.sources)
    copied["validation_target_year"] = validation_year
    replay_target_year = _integer(provenance.get("replay_target_year"), "replay_target_year")
    sources_by_year = {source.cohort_year: source for source in source_manifest.sources}
    feature_source = sources_by_year.get(replay_target_year - 1)
    truth_source = sources_by_year.get(replay_target_year)
    if feature_source is None or truth_source is None:
        raise ReleaseBundleError("Source manifest cannot describe the replay prediction context.")
    elapsed_fraction: float
    if feature_source.published_precision == "day":
        published_day = date.fromisoformat(feature_source.published_value)
        year_start = date(replay_target_year, 1, 1)
        year_end = date(replay_target_year, 12, 31)
        elapsed_days = (published_day - year_start).days + 1
        elapsed_fraction = elapsed_days / ((year_end - year_start).days + 1)
    else:
        published_year, published_month = (
            int(value) for value in feature_source.published_value.split("-")
        )
        if published_year != replay_target_year:
            raise ReleaseBundleError(
                "Month-precision prediction origin is outside its target year."
            )
        elapsed_fraction = (published_month - 1) / 12
    copied["prediction_context"] = {
        "elapsed_target_cohort_fraction_at_prediction": elapsed_fraction,
        "feature_cohort_year": replay_target_year - 1,
        "prediction_as_of": feature_source.published_value,
        "prediction_as_of_precision": feature_source.published_precision,
        "target_cohort_end": f"{replay_target_year}-12-31",
        "target_cohort_year": replay_target_year,
        "truth_published_precision": truth_source.published_precision,
        "truth_published_value": truth_source.published_value,
    }
    return copied


def _attribution(source_manifest_path: Path) -> JsonObject:
    manifest = _yaml_object(source_manifest_path, "Source manifest")
    fields = {
        "source_landing_page": "source_landing_page",
        "methods_url": "methods_url",
        "permissions_url": "permissions_url",
    }
    attribution: JsonObject = {
        "source_owner": _text(manifest.get("source_owner"), "source_owner"),
        "raw_sources_redistributed": False,
        "code_license": "MIT",
        "derived_artifact_notice": (
            "Derived from public aggregate SRTR Program-Specific Report workbooks; "
            "source attribution and source-site permissions guidance remain applicable."
        ),
    }
    for output, source in fields.items():
        attribution[output] = _text(manifest.get(source), source)
    return attribution


def _manifest_with_total_bytes(manifest: JsonObject, payload_bytes: int) -> bytes:
    total = 0
    for _ in range(10):
        manifest["total_bytes"] = total
        rendered = _json_bytes(manifest)
        updated = payload_bytes + len(rendered)
        if updated == total:
            return rendered
        total = updated
    raise ReleaseBundleError("Release manifest size did not stabilize.")


def _publish_staged_bundle(staging: Path, output_dir: Path) -> None:
    backup: Path | None = None
    if output_dir.exists():
        if not output_dir.is_dir():
            raise ReleaseBundleError(f"Release output path is not a directory: {output_dir}.")
        existing_files = tuple(path for path in output_dir.rglob("*") if path.is_file())
        if existing_files and {path.name for path in existing_files} != {".gitkeep"}:
            validate_release_bundle(output_dir)
        backup = output_dir.parent / f".{output_dir.name}-previous"
        if backup.exists():
            raise ReleaseBundleError(f"Stale release backup blocks publication: {backup}.")
        os.replace(output_dir, backup)
    try:
        os.replace(staging, output_dir)
    except Exception:
        if backup is not None and backup.exists() and not output_dir.exists():
            os.replace(backup, output_dir)
        raise
    if backup is not None:
        shutil.rmtree(backup)


def build_release_bundle(
    *,
    processed_dir: Path,
    modeling_dir: Path,
    source_manifest_path: Path,
    experiment_config_path: Path,
    frozen_experiment_path: Path,
    lock_path: Path,
    output_dir: Path,
) -> ReleaseBundleResult:
    """Copy the approved canonical files into one validated, atomically published bundle."""
    replay_dir = _replay_directory(modeling_dir)
    _, replay_provenance, source_manifest, experiment_hash = _verify_input_identity(
        processed_dir=processed_dir,
        modeling_dir=modeling_dir,
        replay_dir=replay_dir,
        source_manifest_path=source_manifest_path,
        experiment_config_path=experiment_config_path,
        frozen_experiment_path=frozen_experiment_path,
        lock_path=lock_path,
    )
    canonical_files = _canonical_files(processed_dir, modeling_dir, replay_dir)
    frozen_config = _yaml_object(frozen_experiment_path, "Frozen experiment config")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".s-", dir=output_dir.parent))
    published = False
    try:
        entries: list[JsonObject] = []
        payload_bytes = 0
        for artifact in canonical_files:
            destination = staging.joinpath(*artifact.destination.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(artifact.source, destination)
            size = destination.stat().st_size
            payload_bytes += size
            entries.append(
                {
                    "bytes": size,
                    "canonical_path": artifact.canonical_path,
                    "canonical_root": artifact.canonical_root,
                    "path": artifact.destination.as_posix(),
                    "sha256": _file_sha256(destination),
                }
            )
        entries.sort(key=lambda entry: cast(str, entry["path"]))
        bundle_hash = _bundle_content_sha256(entries)
        manifest: JsonObject = {
            "application_roots": {
                "modeling": "artifacts/release/modeling",
                "processed": "artifacts/release/processed",
            },
            "attribution": _attribution(source_manifest_path),
            "bundle_content_sha256": bundle_hash,
            "bundle_name": "kidney-acceptance-signal-monitor-demo",
            "file_count": len(entries),
            "files": entries,
            "provenance": _manifest_provenance(
                provenance=replay_provenance,
                source_manifest=source_manifest,
                experiment_hash=experiment_hash,
                frozen_config=frozen_config,
            ),
            "schema_version": 1,
        }
        (staging / RELEASE_MANIFEST_NAME).write_bytes(
            _manifest_with_total_bytes(manifest, payload_bytes)
        )
        staged_result = validate_release_bundle(staging)
        _publish_staged_bundle(staging, output_dir)
        published = True
        return ReleaseBundleResult(
            output_directory=output_dir,
            manifest_path=output_dir / RELEASE_MANIFEST_NAME,
            file_count=staged_result.file_count,
            total_bytes=staged_result.total_bytes,
            bundle_content_sha256=staged_result.bundle_content_sha256,
        )
    finally:
        if not published:
            shutil.rmtree(staging, ignore_errors=True)


def validate_release_bundle(
    bundle_dir: Path, *, max_bytes: int = MAX_RELEASE_BYTES
) -> ReleaseBundleResult:
    """Validate the tracked bundle's exact files, sizes, checksums, and provenance envelope."""
    manifest_path = bundle_dir / RELEASE_MANIFEST_NAME
    manifest = _read_json(manifest_path)
    if _integer(manifest.get("schema_version"), "schema_version") != 1:
        raise ReleaseBundleError("Unsupported release manifest schema version.")
    if _text(manifest.get("bundle_name"), "bundle_name") != (
        "kidney-acceptance-signal-monitor-demo"
    ):
        raise ReleaseBundleError("Release bundle name is not approved.")

    raw_entries = _array(manifest.get("files"), "files")
    entries = tuple(_object(entry, f"files[{index}]") for index, entry in enumerate(raw_entries))
    if not entries:
        raise ReleaseBundleError("Release manifest must list its payload files.")
    if _integer(manifest.get("file_count"), "file_count") != len(entries):
        raise ReleaseBundleError("Release manifest file count disagrees with its entries.")

    paths: list[PurePosixPath] = []
    payload_bytes = 0
    for index, entry in enumerate(entries):
        path_text = _text(entry.get("path"), f"files[{index}].path")
        relative = PurePosixPath(path_text)
        if (
            not relative.parts
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0]
            not in {
                "processed",
                "modeling",
            }
        ):
            raise ReleaseBundleError(
                f"Release file path is unsafe or outside approved roots: {path_text}."
            )
        if relative in paths:
            raise ReleaseBundleError(f"Release manifest repeats file path: {path_text}.")
        canonical_root = _text(entry.get("canonical_root"), f"files[{index}].canonical_root")
        canonical_path = _text(entry.get("canonical_path"), f"files[{index}].canonical_path")
        if canonical_root != relative.parts[0] or PurePosixPath(canonical_path) != PurePosixPath(
            *relative.parts[1:]
        ):
            raise ReleaseBundleError(
                f"Release payload canonical mapping disagrees for {path_text}."
            )
        paths.append(relative)
        artifact = bundle_dir.joinpath(*relative.parts)
        if not artifact.is_file():
            raise ReleaseBundleError(f"Release payload is missing: {path_text}.")
        expected_size = _integer(entry.get("bytes"), f"files[{index}].bytes")
        if artifact.stat().st_size != expected_size:
            raise ReleaseBundleError(f"Release payload size disagrees for {path_text}.")
        expected_hash = _sha256_text(entry.get("sha256"), f"files[{index}].sha256")
        if _file_sha256(artifact) != expected_hash:
            raise ReleaseBundleError(f"Release payload checksum disagrees for {path_text}.")
        payload_bytes += expected_size

    provenance = _object(manifest.get("provenance"), "provenance")
    for field in (
        "dependency_lock_sha256",
        "experiment_config_sha256",
        "feature_schema_sha256",
        "frozen_experiment_sha256",
        "input_panel_sha256",
        "methodology_version_ledger_sha256",
        "source_manifest_sha256",
    ):
        _sha256_text(provenance.get(field), f"provenance.{field}")
    for field in ("build_timestamp_utc", "git_commit_sha", "python_version"):
        _text(provenance.get(field), f"provenance.{field}")
    for field in (
        "calibration_target_year",
        "replay_target_year",
        "source_manifest_schema_version",
        "validation_target_year",
    ):
        _integer(provenance.get(field), f"provenance.{field}")
    for field in ("feature_columns", "source_cohort_years", "training_target_years"):
        _array(provenance.get(field), f"provenance.{field}")
    _object(provenance.get("model_parameters"), "provenance.model_parameters")
    source_hashes = _object(provenance.get("source_sha256"), "provenance.source_sha256")
    if not source_hashes:
        raise ReleaseBundleError("Release provenance must include source checksums.")
    for release_code, checksum in source_hashes.items():
        _sha256_text(checksum, f"provenance.source_sha256.{release_code}")
    prediction_context = _object(
        provenance.get("prediction_context"), "provenance.prediction_context"
    )
    for field in (
        "feature_cohort_year",
        "target_cohort_year",
    ):
        _integer(prediction_context.get(field), f"provenance.prediction_context.{field}")
    for field in (
        "prediction_as_of",
        "prediction_as_of_precision",
        "target_cohort_end",
        "truth_published_precision",
        "truth_published_value",
    ):
        _text(prediction_context.get(field), f"provenance.prediction_context.{field}")
    elapsed_fraction = _number(
        prediction_context.get("elapsed_target_cohort_fraction_at_prediction"),
        "provenance.prediction_context.elapsed_target_cohort_fraction_at_prediction",
    )
    if not 0 <= elapsed_fraction <= 1:
        raise ReleaseBundleError("Release prediction-context elapsed fraction is outside 0–1.")

    attribution = _object(manifest.get("attribution"), "attribution")
    _text(attribution.get("source_owner"), "attribution.source_owner")
    _text(attribution.get("source_landing_page"), "attribution.source_landing_page")
    _text(attribution.get("methods_url"), "attribution.methods_url")
    _text(attribution.get("permissions_url"), "attribution.permissions_url")
    if _boolean(
        attribution.get("raw_sources_redistributed"),
        "attribution.raw_sources_redistributed",
    ):
        raise ReleaseBundleError("The release bundle must not redistribute raw source files.")

    application_roots = _object(manifest.get("application_roots"), "application_roots")
    if application_roots != {
        "modeling": "artifacts/release/modeling",
        "processed": "artifacts/release/processed",
    }:
        raise ReleaseBundleError("Release application roots do not match the offline contract.")

    frozen_hash = _sha256_text(
        provenance.get("frozen_experiment_sha256"), "provenance.frozen_experiment_sha256"
    )
    source_hash = _sha256_text(
        provenance.get("source_manifest_sha256"), "provenance.source_manifest_sha256"
    )
    replay_prefix = PurePosixPath("modeling", "frozen-replay", f"{frozen_hash}_{source_hash}")
    expected_paths = {
        *(PurePosixPath("processed", name) for name in _PROCESSED_FILES),
        *(PurePosixPath("modeling", name) for name in _MODELING_FILES),
        *(replay_prefix / name for name in _REPLAY_FILES),
    }
    if set(paths) != expected_paths:
        raise ReleaseBundleError("Release bundle file set does not match the approved contract.")

    actual_files = {
        path.relative_to(bundle_dir).as_posix() for path in bundle_dir.rglob("*") if path.is_file()
    }
    expected_files = {path.as_posix() for path in paths} | {RELEASE_MANIFEST_NAME}
    if actual_files != expected_files:
        raise ReleaseBundleError("Release directory contains unapproved or unlisted files.")

    recorded_bundle_hash = _sha256_text(
        manifest.get("bundle_content_sha256"), "bundle_content_sha256"
    )
    if _bundle_content_sha256(entries) != recorded_bundle_hash:
        raise ReleaseBundleError("Release bundle content identity disagrees with its manifest.")
    total_bytes = payload_bytes + manifest_path.stat().st_size
    if _integer(manifest.get("total_bytes"), "total_bytes") != total_bytes:
        raise ReleaseBundleError("Release manifest total size disagrees with the directory.")
    if total_bytes >= max_bytes:
        raise ReleaseBundleError(
            f"Release bundle is {total_bytes} bytes; it must remain below {max_bytes} bytes."
        )

    return ReleaseBundleResult(
        output_directory=bundle_dir,
        manifest_path=manifest_path,
        file_count=len(entries),
        total_bytes=total_bytes,
        bundle_content_sha256=recorded_bundle_hash,
    )
