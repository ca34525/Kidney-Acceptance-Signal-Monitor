from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import kasm.patient_journey.release as release_module
from kasm.patient_journey.release import (
    PatientJourneyReleaseError,
    PatientJourneyReleaseResult,
    validate_patient_journey_release_directory,
    write_patient_journey_release_directory,
)

ReleaseBundle = tuple[PatientJourneyReleaseResult, dict[str, Path], dict[str, object]]


def _content_identity(records: dict[str, dict[str, object]]) -> str:
    normalized = {
        key: {"bytes": value["bytes"], "sha256": value["sha256"]}
        for key, value in sorted(records.items())
    }
    return sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_parquet(path: Path, provenance: dict[str, object]) -> None:
    table = pa.table({"value": [1]}).replace_schema_metadata(
        {b"kasm_provenance": json.dumps(provenance, sort_keys=True).encode()}
    )
    pq.write_table(table, path)


def _release_inputs(
    directory: Path, *, generation: str = "a"
) -> tuple[dict[str, Path], dict[str, object]]:
    directory.mkdir()
    assets = {
        "panel": directory / "patient_journey_panel.parquet",
        "safety": directory / "safety_measures.parquet",
        "predictions": directory / "predictions.parquet",
        "evaluation": directory / "evaluation.json",
    }
    processed_provenance: dict[str, object] = {
        "analysis_id": "kidney_patient_journey_v2",
        "dependency_lock_sha256": "1" * 64,
        "experiment_config_sha256": "2" * 64,
        "methodology_config_sha256": "3" * 64,
        "source_manifest_sha256": "4" * 64,
        "source_sha256": {"1905": "5" * 64},
        "git_commit_sha": generation * 40,
        "git_worktree_dirty": False,
        "python_version": "3.12.13",
        "build_timestamp_utc": f"2026-09-04T18:00:0{generation == 'b'}Z",
    }
    _write_parquet(assets["panel"], processed_provenance)
    _write_parquet(assets["safety"], processed_provenance)
    model_provenance = {
        **{
            key: value
            for key, value in processed_provenance.items()
            if key != "build_timestamp_utc"
        },
        "build_timestamp_utc": f"2026-09-04T19:00:0{generation == 'b'}Z",
        "processed_artifact_set_sha256": generation * 64,
        "processed_manifest_sha256": "6" * 64,
        "processed_panel_sha256": _file_sha256(assets["panel"]),
        "processed_safety_sha256": _file_sha256(assets["safety"]),
    }
    _write_parquet(assets["predictions"], model_provenance)
    assets["evaluation"].write_text(
        json.dumps(
            {
                "analysis_id": "kidney_patient_journey_v2",
                "promotion_allowed": False,
                "promoted_model": None,
                "evidence_status": "retrospective_exploratory_feasibility",
            }
        ),
        encoding="utf-8",
    )
    model_records = {
        key: {
            "bytes": assets[key].stat().st_size,
            "sha256": _file_sha256(assets[key]),
        }
        for key in ("predictions", "evaluation")
    }
    provenance = {
        **model_provenance,
        "modeling_artifact_set_sha256": _content_identity(model_records),
        "promotion_allowed": False,
        "promoted_model": None,
        "evidence_status": "retrospective_exploratory_feasibility",
    }
    return assets, provenance


def test_v2_release_is_exact_self_contained_and_tamper_evident(tmp_path: Path) -> None:
    assets, provenance = _release_inputs(tmp_path / "inputs")
    output_dir = tmp_path / "release"

    result = write_patient_journey_release_directory(
        assets=assets,
        output_dir=output_dir,
        provenance=provenance,
    )

    assert {path.name for path in output_dir.iterdir()} == {
        "evaluation.json",
        "patient_journey_panel.parquet",
        "predictions.parquet",
        "release_manifest.json",
        "safety_measures.parquet",
    }
    assert result.file_count == 4
    validated = validate_patient_journey_release_directory(output_dir)
    assert validated.bundle_content_sha256 == result.bundle_content_sha256

    result.predictions_path.write_bytes(b"changed")
    with pytest.raises(PatientJourneyReleaseError, match="checksum"):
        validate_patient_journey_release_directory(output_dir)


def test_v2_release_refuses_any_promotion_claim(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    assets = {
        name: inputs / filename
        for name, filename in {
            "panel": "patient_journey_panel.parquet",
            "safety": "safety_measures.parquet",
            "predictions": "predictions.parquet",
            "evaluation": "evaluation.json",
        }.items()
    }
    for path in assets.values():
        path.write_text(json.dumps({}), encoding="utf-8")

    with pytest.raises(PatientJourneyReleaseError, match="nonpromotion"):
        write_patient_journey_release_directory(
            assets=assets,
            output_dir=tmp_path / "release",
            provenance={
                "analysis_id": "kidney_patient_journey_v2",
                "promotion_allowed": True,
                "promoted_model": "history_acceptance",
                "evidence_status": "retrospective_exploratory_feasibility",
                "git_commit_sha": "a" * 40,
                "git_worktree_dirty": False,
            },
        )


def test_v2_release_rejects_a_mixed_rehashed_generation(tmp_path: Path) -> None:
    assets, provenance = _release_inputs(tmp_path / "inputs-a")
    other_assets, _ = _release_inputs(tmp_path / "inputs-b", generation="b")
    output_dir = tmp_path / "release"
    write_patient_journey_release_directory(
        assets=assets,
        output_dir=output_dir,
        provenance=provenance,
    )
    replacement = output_dir / "safety_measures.parquet"
    replacement.write_bytes(other_assets["safety"].read_bytes())
    manifest_path = output_dir / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    safety_record = manifest["artifacts"]["safety"]
    safety_record["bytes"] = replacement.stat().st_size
    safety_record["sha256"] = sha256(replacement.read_bytes()).hexdigest()
    records = manifest["artifacts"]
    manifest["total_bytes"] = sum(record["bytes"] for record in records.values())
    manifest["bundle_content_sha256"] = _content_identity(records)
    manifest["provenance"]["processed_safety_sha256"] = safety_record["sha256"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PatientJourneyReleaseError, match="generation"):
        validate_patient_journey_release_directory(output_dir)


def test_v2_release_recomputes_the_modeling_artifact_identity(tmp_path: Path) -> None:
    assets, provenance = _release_inputs(tmp_path / "inputs")
    output_dir = tmp_path / "release"
    write_patient_journey_release_directory(
        assets=assets,
        output_dir=output_dir,
        provenance=provenance,
    )
    evaluation_path = output_dir / "evaluation.json"
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    evaluation["rewritten"] = True
    evaluation_path.write_text(json.dumps(evaluation), encoding="utf-8")
    manifest_path = output_dir / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    evaluation_record = manifest["artifacts"]["evaluation"]
    evaluation_record["bytes"] = evaluation_path.stat().st_size
    evaluation_record["sha256"] = _file_sha256(evaluation_path)
    records = manifest["artifacts"]
    manifest["total_bytes"] = sum(record["bytes"] for record in records.values())
    manifest["bundle_content_sha256"] = _content_identity(records)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PatientJourneyReleaseError, match="modeling generation"):
        validate_patient_journey_release_directory(output_dir)


@pytest.fixture
def release_bundle(tmp_path: Path) -> ReleaseBundle:
    assets, provenance = _release_inputs(tmp_path / "inputs")
    result = write_patient_journey_release_directory(
        assets=assets,
        provenance=provenance,
        output_dir=tmp_path / "release",
    )
    return result, assets, provenance


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", 999, "unsupported"),
        ("status", "in_progress", "incomplete"),
        ("provenance", None, "provenance"),
        ("display_contract", {}, "display contract"),
        ("artifacts", {}, "records are incomplete"),
        (
            "artifacts",
            {key: None for key in ("panel", "safety", "predictions", "evaluation")},
            "record is invalid",
        ),
        ("total_bytes", 0, "aggregate"),
        ("bundle_content_sha256", "0" * 64, "aggregate"),
    ],
)
def test_release_validator_rejects_manifest_contract_drift(
    release_bundle: ReleaseBundle, field: str, value: object, message: str
) -> None:
    result, _, _ = release_bundle
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    manifest[field] = value
    result.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PatientJourneyReleaseError, match=message):
        validate_patient_journey_release_directory(result.output_directory)


@pytest.mark.parametrize(("value", "message"), [("{", "unreadable"), ("[]", "JSON object")])
def test_release_validator_rejects_unreadable_manifest(
    release_bundle: ReleaseBundle, value: str, message: str
) -> None:
    result, _, _ = release_bundle
    result.manifest_path.write_text(value, encoding="utf-8")
    with pytest.raises(PatientJourneyReleaseError, match=message):
        validate_patient_journey_release_directory(result.output_directory)


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("missing_asset", "missing"),
        ("extra_asset", "exactly four"),
        ("invalid_parquet", "generation provenance is invalid"),
        ("array_provenance", "provenance must be an object"),
        ("invalid_evaluation", "evaluation is unreadable"),
        ("array_evaluation", "evaluation must be a JSON object"),
    ],
)
def test_release_writer_rejects_bad_inputs_without_changing_prior_release(
    release_bundle: ReleaseBundle, failure: str, message: str
) -> None:
    result, assets, provenance = release_bundle
    before = {p.name: p.read_bytes() for p in result.output_directory.iterdir()}
    if failure == "missing_asset":
        assets["panel"] = result.output_directory.parent / "absent.parquet"
    elif failure == "extra_asset":
        assets["extra"] = assets["panel"]
    elif failure == "invalid_parquet":
        assets["panel"].write_bytes(b"not parquet")
    elif failure == "array_provenance":
        table = pq.read_table(assets["panel"]).replace_schema_metadata({b"kasm_provenance": b"[]"})
        pq.write_table(table, assets["panel"])
    else:
        assets["evaluation"].write_text(
            "{" if failure == "invalid_evaluation" else "[]", encoding="utf-8"
        )
        provenance["modeling_artifact_set_sha256"] = _content_identity(
            {
                key: {"bytes": assets[key].stat().st_size, "sha256": _file_sha256(assets[key])}
                for key in ("predictions", "evaluation")
            }
        )
    with pytest.raises(PatientJourneyReleaseError, match=message):
        write_patient_journey_release_directory(
            assets=assets, provenance=provenance, output_dir=result.output_directory
        )
    assert {p.name: p.read_bytes() for p in result.output_directory.iterdir()} == before
    assert not list(result.output_directory.parent.glob(".*-staging-*"))


def test_release_publication_failure_rolls_back_prior_bundle(
    release_bundle: ReleaseBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, assets, provenance = release_bundle
    before = {p.name: p.read_bytes() for p in result.output_directory.iterdir()}
    original = release_module.os.replace

    def fail_publish(src: Path, dst: Path) -> None:
        if "-staging-" in Path(src).name and Path(dst) == result.output_directory:
            raise OSError("injected publish failure")
        return original(src, dst)

    monkeypatch.setattr(release_module.os, "replace", fail_publish)
    with pytest.raises(OSError, match="injected"):
        write_patient_journey_release_directory(
            assets=assets, provenance=provenance, output_dir=result.output_directory
        )
    assert {p.name: p.read_bytes() for p in result.output_directory.iterdir()} == before
    assert not list(result.output_directory.parent.glob(".*-staging-*"))
    assert not list(result.output_directory.parent.glob(".*-backup"))
