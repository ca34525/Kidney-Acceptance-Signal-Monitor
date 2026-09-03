from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from kasm.config import load_data_source_manifest
from kasm.reporting.artifacts import (
    ReleaseBundleError,
    build_release_bundle,
    validate_release_bundle,
)

PROJECT_ROOT = Path(__file__).parents[2]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _canonical_fixture(tmp_path: Path) -> tuple[Path, Path]:
    short_root = tmp_path.parent / hashlib.sha256(str(tmp_path).encode()).hexdigest()[:8]
    processed = short_root / "p"
    modeling = short_root / "m"
    processed.mkdir(parents=True)
    modeling.mkdir()

    (processed / "program_signals.parquet").write_bytes(b"canonical signals")
    panel = processed / "model_panel.parquet"
    panel.write_bytes(b"canonical panel")
    _write_json(processed / "qa_report.json", {"schema_version": 1})
    panel_hash = _sha256(panel)

    for name in ("baseline_predictions.parquet", "ridge_predictions.parquet"):
        (modeling / name).write_bytes(name.encode())
    _write_json(
        modeling / "baseline_metrics.json",
        {"frozen_replay_evaluated": False, "input_panel_sha256": panel_hash},
    )
    _write_json(
        modeling / "ridge_metrics.json",
        {"frozen_replay_evaluated": False, "input_panel_sha256": panel_hash},
    )
    _write_json(
        modeling / "ridge_selection.json",
        {"input_panel_sha256": panel_hash, "selected_alpha": 10},
    )
    _write_json(
        modeling / "temporal_folds.json",
        {"input_panel_sha256": panel_hash, "split_method": "rolling_origin_by_target_year"},
    )

    source_hash = _sha256(PROJECT_ROOT / "configs" / "data_sources.yaml")
    frozen_hash = _sha256(PROJECT_ROOT / "configs" / "frozen_experiment.yaml")
    experiment_hash = _sha256(PROJECT_ROOT / "configs" / "experiment.yaml")
    source_manifest = load_data_source_manifest(PROJECT_ROOT / "configs" / "data_sources.yaml")
    source_hashes = {
        source.release_code: source.download_sha256 for source in source_manifest.sources
    }
    for name in (
        "baseline_metrics.json",
        "ridge_metrics.json",
        "ridge_selection.json",
        "temporal_folds.json",
    ):
        path = modeling / name
        value = json.loads(path.read_text(encoding="utf-8"))
        value["experiment_config_sha256"] = experiment_hash
        _write_json(path, value)
    replay_dir = modeling / "frozen-replay" / f"{frozen_hash}_{source_hash}"
    replay_dir.mkdir(parents=True)
    replay_predictions = replay_dir / "replay_predictions.parquet"
    replay_predictions.write_bytes(b"canonical replay predictions")
    replay_metrics = replay_dir / "replay_metrics.json"
    _write_json(
        replay_metrics,
        {
            "evidence_classification": "descriptive_retrospective_product_selection",
            "frozen_replay_evaluated": True,
            "methodology_version_ledger": [{"cohort_year": 2017}],
            "prospective_validation": False,
            "provenance": {
                "build_timestamp_utc": "2026-09-03T15:58:45+00:00",
                "calibration_target_year": 2024,
                "dependency_lock_sha256": _sha256(PROJECT_ROOT / "uv.lock"),
                "feature_columns": ["current_log_overall_oar"],
                "feature_schema_sha256": "a" * 64,
                "frozen_experiment_sha256": frozen_hash,
                "git_commit_sha": "b" * 40,
                "git_worktree_dirty": False,
                "input_panel_sha256": panel_hash,
                "methodology_version_ledger_sha256": "c" * 64,
                "model_parameters": {"alpha": 10, "random_seed": 20260903},
                "python_version": "3.12.13",
                "replay_target_year": 2025,
                "source_manifest_schema_version": 2,
                "source_manifest_sha256": source_hash,
                "source_sha256": source_hashes,
                "training_target_years": [2018, 2019, 2020, 2021, 2022, 2023],
            },
            "replay_target_year": 2025,
            "selected_alpha": 10,
        },
    )
    _write_json(
        replay_dir / "completion.json",
        {
            "artifact_sha256": {
                "metrics": _sha256(replay_metrics),
                "predictions": _sha256(replay_predictions),
            },
            "artifacts": {
                "metrics": replay_metrics.name,
                "predictions": replay_predictions.name,
            },
            "completed_at_utc": "2026-09-03T15:58:45+00:00",
            "frozen_experiment_sha256": frozen_hash,
            "git_commit_sha": "b" * 40,
            "input_panel_sha256": panel_hash,
            "prediction_rows": 1,
            "source_manifest_sha256": source_hash,
            "status": "complete",
        },
    )
    return processed, modeling


def test_release_manifest_contains_required_provenance(tmp_path: Path) -> None:
    processed, modeling = _canonical_fixture(tmp_path)
    release = processed.parent / "o"

    result = build_release_bundle(
        processed_dir=processed,
        modeling_dir=modeling,
        source_manifest_path=PROJECT_ROOT / "configs" / "data_sources.yaml",
        experiment_config_path=PROJECT_ROOT / "configs" / "experiment.yaml",
        frozen_experiment_path=PROJECT_ROOT / "configs" / "frozen_experiment.yaml",
        lock_path=PROJECT_ROOT / "uv.lock",
        output_dir=release,
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["bundle_name"] == "kidney-acceptance-signal-monitor-demo"
    assert manifest["total_bytes"] < 5 * 1024 * 1024
    assert manifest["attribution"]["source_owner"] == (
        "Scientific Registry of Transplant Recipients"
    )
    assert manifest["attribution"]["raw_sources_redistributed"] is False
    assert set(manifest["provenance"]) >= {
        "build_timestamp_utc",
        "calibration_target_year",
        "dependency_lock_sha256",
        "experiment_config_sha256",
        "feature_columns",
        "feature_schema_sha256",
        "frozen_experiment_sha256",
        "git_commit_sha",
        "input_panel_sha256",
        "methodology_version_ledger_sha256",
        "model_parameters",
        "python_version",
        "replay_target_year",
        "source_manifest_schema_version",
        "source_manifest_sha256",
        "source_sha256",
        "training_target_years",
        "validation_target_year",
    }


def test_app_bundle_matches_canonical_artifacts(tmp_path: Path) -> None:
    processed, modeling = _canonical_fixture(tmp_path)
    release = processed.parent / "o"
    build_release_bundle(
        processed_dir=processed,
        modeling_dir=modeling,
        source_manifest_path=PROJECT_ROOT / "configs" / "data_sources.yaml",
        experiment_config_path=PROJECT_ROOT / "configs" / "experiment.yaml",
        frozen_experiment_path=PROJECT_ROOT / "configs" / "frozen_experiment.yaml",
        lock_path=PROJECT_ROOT / "uv.lock",
        output_dir=release,
    )

    summary = validate_release_bundle(release)
    manifest = json.loads((release / "release_manifest.json").read_text(encoding="utf-8"))
    roots = {"processed": processed, "modeling": modeling}
    for entry in manifest["files"]:
        canonical = roots[entry["canonical_root"]] / entry["canonical_path"]
        assert _sha256(release / entry["path"]) == _sha256(canonical)
    assert summary.file_count == len(manifest["files"])


def test_rebuilding_a_valid_bundle_preserves_its_content_identity(tmp_path: Path) -> None:
    processed, modeling = _canonical_fixture(tmp_path)
    release = processed.parent / "o"
    arguments = {
        "processed_dir": processed,
        "modeling_dir": modeling,
        "source_manifest_path": PROJECT_ROOT / "configs" / "data_sources.yaml",
        "experiment_config_path": PROJECT_ROOT / "configs" / "experiment.yaml",
        "frozen_experiment_path": PROJECT_ROOT / "configs" / "frozen_experiment.yaml",
        "lock_path": PROJECT_ROOT / "uv.lock",
        "output_dir": release,
    }

    first = build_release_bundle(**arguments)
    first_manifest = first.manifest_path.read_bytes()
    second = build_release_bundle(**arguments)

    assert second.bundle_content_sha256 == first.bundle_content_sha256
    assert second.manifest_path.read_bytes() == first_manifest


def test_release_validation_rejects_tampered_payload(tmp_path: Path) -> None:
    processed, modeling = _canonical_fixture(tmp_path)
    release = processed.parent / "o"
    build_release_bundle(
        processed_dir=processed,
        modeling_dir=modeling,
        source_manifest_path=PROJECT_ROOT / "configs" / "data_sources.yaml",
        experiment_config_path=PROJECT_ROOT / "configs" / "experiment.yaml",
        frozen_experiment_path=PROJECT_ROOT / "configs" / "frozen_experiment.yaml",
        lock_path=PROJECT_ROOT / "uv.lock",
        output_dir=release,
    )
    panel = release / "processed" / "model_panel.parquet"
    panel.write_bytes(b"x" * panel.stat().st_size)

    with pytest.raises(ReleaseBundleError, match="checksum"):
        validate_release_bundle(release)


def test_release_validation_rejects_unsafe_manifest_path_with_domain_error(
    tmp_path: Path,
) -> None:
    processed, modeling = _canonical_fixture(tmp_path)
    release = processed.parent / "o"
    build_release_bundle(
        processed_dir=processed,
        modeling_dir=modeling,
        source_manifest_path=PROJECT_ROOT / "configs" / "data_sources.yaml",
        experiment_config_path=PROJECT_ROOT / "configs" / "experiment.yaml",
        frozen_experiment_path=PROJECT_ROOT / "configs" / "frozen_experiment.yaml",
        lock_path=PROJECT_ROOT / "uv.lock",
        output_dir=release,
    )
    manifest_path = release / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["path"] = "."
    _write_json(manifest_path, manifest)

    with pytest.raises(ReleaseBundleError, match="unsafe"):
        validate_release_bundle(release)
