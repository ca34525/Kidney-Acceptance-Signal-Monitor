import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kasm.patient_journey.followup_artifacts import (
    FollowupArtifactError,
    _load_original_inputs,
    _OriginalInputs,
    _publish_files,
    build_followup,
)
from kasm.patient_journey.followup_config import OUTPUT_ROOT, FollowupConfig, FollowupConfigError

ROOT = Path(__file__).parents[2]


def _payloads() -> dict[str, bytes]:
    return {
        "evaluation.json": b"{}\n",
        "predictions.parquet": b"fixture",
        "report.md": b"fixture",
        "report_counts.svg": b"<svg/>",
        "model_errors.svg": b"<svg/>",
        "report_counts.png": b"fixture",
        "model_errors.png": b"fixture",
    }


def test_followup_writer_publishes_complete_files_once(tmp_path: Path) -> None:
    destination = OUTPUT_ROOT / ("a" * 64)
    result = _publish_files(_payloads(), destination, repository_root=tmp_path, provenance={})
    manifest = json.loads((result / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert set(manifest["artifacts"]) == set(_payloads())
    assert all(record["bytes"] > 0 for record in manifest["artifacts"].values())
    with pytest.raises(FollowupArtifactError, match="already exists"):
        _publish_files(_payloads(), destination, repository_root=tmp_path, provenance={})
    assert (result / "report.md").read_bytes() == b"fixture"
    assert [p.name for p in result.parent.iterdir()] == ["a" * 64]


def test_followup_writer_refuses_existing_empty_directory(tmp_path: Path) -> None:
    relative = OUTPUT_ROOT / ("a" * 64)
    destination = tmp_path / relative
    destination.mkdir(parents=True)
    with pytest.raises(FollowupArtifactError, match="already exists"):
        _publish_files(_payloads(), relative, repository_root=tmp_path, provenance={})
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize("name", ["../escaped", "/absolute", "extra.json", "manifest.json"])
def test_followup_writer_rejects_unexpected_payload_before_writing(
    tmp_path: Path, name: str
) -> None:
    files = _payloads() | {name: b"untrusted"}
    with pytest.raises(FollowupArtifactError, match="file set"):
        _publish_files(files, OUTPUT_ROOT / ("a" * 64), repository_root=tmp_path, provenance={})
    assert not (tmp_path / "data").exists()


def test_followup_writer_rechecks_protected_path(tmp_path: Path) -> None:
    with pytest.raises(FollowupConfigError):
        _publish_files(
            _payloads(),
            Path("artifacts/patient_journey_v2"),
            repository_root=tmp_path,
            provenance={},
        )
    assert list(tmp_path.iterdir()) == []


def test_followup_publish_failure_cannot_leave_complete_run(tmp_path: Path, monkeypatch) -> None:
    def fail(*args):
        raise OSError("simulated publication failure")

    monkeypatch.setattr("kasm.patient_journey.followup_artifacts.os.rename", fail)
    relative = OUTPUT_ROOT / ("a" * 64)
    with pytest.raises(FollowupArtifactError, match="publish"):
        _publish_files(_payloads(), relative, repository_root=tmp_path, provenance={})
    assert not (tmp_path / relative).exists()
    assert list((tmp_path / OUTPUT_ROOT).iterdir()) == []


def test_followup_missing_inputs_fail_without_creating_output(tmp_path: Path) -> None:
    with pytest.raises(FollowupArtifactError, match="original"):
        _load_original_inputs(tmp_path, FollowupConfig())
    assert not (tmp_path / OUTPUT_ROOT).exists()


def test_followup_rejects_changed_pinned_input(tmp_path: Path) -> None:
    bundle = tmp_path / "artifacts/patient_journey_v2"
    shutil.copytree(ROOT / "artifacts/patient_journey_v2", bundle)
    with (bundle / "predictions.parquet").open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises(FollowupArtifactError, match="original"):
        _load_original_inputs(tmp_path, FollowupConfig())
    assert not (tmp_path / OUTPUT_ROOT).exists()


def test_followup_reader_keeps_original_and_current_lock_identities_distinct() -> None:
    inputs = _load_original_inputs(ROOT, FollowupConfig())
    assert len(inputs.rows) == 966
    assert inputs.provenance["original_dependency_lock_sha256"] == (
        "9783d6fc61d5c69012494519e674b5c17c0f346ba1923a4758c38fcdc573a687"
    )
    assert inputs.provenance["original_bundle_sha256"] == FollowupConfig().original_bundle_sha256


def test_followup_cli_dispatches_only_separate_build(monkeypatch, capsys) -> None:
    from kasm.cli import main

    calls = []

    def build(**kwargs):
        calls.append(kwargs)
        return ROOT / OUTPUT_ROOT / ("a" * 64)

    monkeypatch.setattr("kasm.cli.build_followup", build)
    assert main(["patient-journey", "follow-up"]) == 0
    assert len(calls) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_followup_cli_returns_domain_error(monkeypatch, capsys) -> None:
    from kasm.cli import main

    def fail(**kwargs):
        raise FollowupArtifactError("changed original input")

    monkeypatch.setattr("kasm.cli.build_followup", fail)
    assert main(["patient-journey", "follow-up"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "changed original input"


def _fixture_build(tmp_path, monkeypatch):
    from test_patient_journey_followup_analysis import _row, _stored

    from kasm.patient_journey.artifacts import PatientJourneyBuildContext
    from kasm.patient_journey.config import load_patient_journey_config

    for name in (
        "configs/patient_journey_v2_followup/experiment.yaml",
        "docs/specs/patient-journey-v2-followup.md",
        "uv.lock",
        "pyproject.toml",
        "src/kasm/patient_journey/followup_artifacts.py",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, path)
    original = load_patient_journey_config(
        ROOT / "configs/patient_journey_v2/experiment.yaml", repository_root=ROOT
    )
    rows = tuple(
        _row(program, pair, count, target)
        for pair in (("1905", "2205"), ("2205", "2505"))
        for program, count, target in (("AAAA:TX1", 1, -1.0), ("BBBB:TX1", 2, 1.0))
    )
    inputs = _OriginalInputs(rows, tuple(_stored(rows, original)), original, {})
    monkeypatch.setattr(
        "kasm.patient_journey.followup_artifacts._load_original_inputs", lambda *a: inputs
    )
    context = PatientJourneyBuildContext(
        datetime(2026, 9, 5, tzinfo=UTC), "a" * 40, True, "3.12.13"
    )
    monkeypatch.setattr(
        "kasm.patient_journey.followup_artifacts.current_patient_journey_build_context",
        lambda *a: context,
    )


def test_followup_fixture_build_records_inputs_and_rejects_rerun(tmp_path, monkeypatch) -> None:
    import pyarrow.parquet as pq

    _fixture_build(tmp_path, monkeypatch)
    result = build_followup(repository_root=tmp_path)
    manifest = json.loads((result / "manifest.json").read_text())
    provenance = manifest["provenance"]
    assert provenance["git_worktree_dirty"] is True
    assert provenance["canonical_build"] is False
    assert provenance["build_timestamp_utc"] == "2026-09-05T00:00:00Z"
    assert len(provenance["implementation_sha256"]) == 1
    assert len(provenance["feature_schema"]) == 13
    assert len(provenance["model_parameters"]) == 10
    assert pq.read_table(result / "predictions.parquet").num_rows == 26
    with pytest.raises(FollowupArtifactError, match="already exists"):
        build_followup(repository_root=tmp_path)


def test_followup_changed_code_during_analysis_prevents_publication(tmp_path, monkeypatch) -> None:
    from kasm.patient_journey.followup_analysis import evaluate_followup

    _fixture_build(tmp_path, monkeypatch)

    def changed(*args):
        result = evaluate_followup(*args)
        (tmp_path / "src/kasm/patient_journey/followup_artifacts.py").write_text("changed")
        return result

    monkeypatch.setattr("kasm.patient_journey.followup_artifacts.evaluate_followup", changed)
    with pytest.raises(FollowupArtifactError, match="changed during"):
        build_followup(repository_root=tmp_path)
    assert not (tmp_path / OUTPUT_ROOT).exists()


def test_followup_missing_build_lock_is_actionable_domain_error(tmp_path, monkeypatch) -> None:
    _fixture_build(tmp_path, monkeypatch)
    (tmp_path / "uv.lock").unlink()
    with pytest.raises(FollowupArtifactError, match="identity"):
        build_followup(repository_root=tmp_path)


def test_followup_cli_handles_failed_reconstruction(monkeypatch, capsys) -> None:
    from kasm.cli import main
    from kasm.patient_journey.followup_analysis import FollowupAnalysisError

    def fail(**kwargs):
        raise FollowupAnalysisError("Reconstructed prediction exceeds tolerance")

    monkeypatch.setattr("kasm.cli.build_followup", fail)
    assert main(["patient-journey", "follow-up"]) == 1
    assert "tolerance" in json.loads(capsys.readouterr().out)["error"]


def test_followup_report_failure_publishes_nothing(tmp_path, monkeypatch) -> None:
    _fixture_build(tmp_path, monkeypatch)

    def fail(*args):
        raise ValueError("invalid report evidence")

    monkeypatch.setattr("kasm.patient_journey.followup_artifacts.render_followup_report", fail)
    with pytest.raises(FollowupArtifactError, match="report evidence"):
        build_followup(repository_root=tmp_path)
    assert not (tmp_path / OUTPUT_ROOT).exists()
