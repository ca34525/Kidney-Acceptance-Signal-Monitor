import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_patient_journey_component_analysis import _inputs

from kasm.patient_journey.component_analysis import analyze_components
from kasm.patient_journey.component_artifacts import build_components, publish_component_files
from kasm.patient_journey.component_config import OUTPUT_ROOT, ComponentConfig, ComponentError
from kasm.patient_journey.component_report import render_component_report

ROOT = Path(__file__).parents[2]


def _files():
    return {
        "components.json": b"[]",
        "analysis.json": b"{}",
        "report.md": b"fixture",
        "outcome_components.svg": b"<svg/>",
        "outcome_components.png": b"fixture",
    }


def test_component_writer_is_complete_and_write_once(tmp_path):
    relative = OUTPUT_ROOT / ("a" * 64)
    output = publish_component_files(_files(), relative, repository_root=tmp_path, provenance={})
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert manifest["promotion_allowed"] is False
    assert set(manifest["artifacts"]) == set(_files())
    with pytest.raises(ComponentError, match="already exists"):
        publish_component_files(_files(), relative, repository_root=tmp_path, provenance={})


@pytest.mark.parametrize(
    "path",
    [
        "artifacts/patient_journey_v2",
        "data/patient_journey_v2",
        "data/patient_journey_v2_followup/report_count_v1/" + "a" * 64,
        "../escape",
        "/absolute",
        str(OUTPUT_ROOT / "../escaped"),
    ],
)
def test_component_writer_rejects_protected_or_escaping_destination(tmp_path, path):
    with pytest.raises(ComponentError):
        publish_component_files(_files(), Path(path), repository_root=tmp_path, provenance={})
    assert list(tmp_path.iterdir()) == []


def test_component_writer_rejects_empty_destination_and_bad_filename(tmp_path):
    relative = OUTPUT_ROOT / ("a" * 64)
    (tmp_path / relative).mkdir(parents=True)
    with pytest.raises(ComponentError, match="already exists"):
        publish_component_files(_files(), relative, repository_root=tmp_path, provenance={})
    with pytest.raises(ComponentError, match="file set"):
        publish_component_files(
            _files() | {"../escape": b"bad"},
            OUTPUT_ROOT / ("b" * 64),
            repository_root=tmp_path,
            provenance={},
        )


def test_component_failed_publish_cleans_only_staging(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("simulated rename failure")

    monkeypatch.setattr("kasm.patient_journey.component_artifacts.os.rename", fail)
    with pytest.raises(ComponentError, match="publish"):
        publish_component_files(
            _files(), OUTPUT_ROOT / ("a" * 64), repository_root=tmp_path, provenance={}
        )
    assert list((tmp_path / OUTPUT_ROOT).iterdir()) == []


def test_component_writer_rejects_link_ancestor(tmp_path, monkeypatch):
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda p: p == tmp_path / "data" or original(p))
    with pytest.raises(ComponentError, match="link"):
        publish_component_files(
            _files(), OUTPUT_ROOT / ("a" * 64), repository_root=tmp_path, provenance={}
        )


def test_component_report_preserves_population_numbers_and_missing_states():
    evidence = analyze_components(*_inputs(), ComponentConfig())
    files = render_component_report(evidence)
    report = files["report.md"].decode()
    assert "16.00%" in report
    assert "37.50%" in report
    assert "constant variable" in report
    assert "historical mean" in report.lower()
    assert "original listing" in report.lower()
    assert "2022-07-01" in report
    assert "2025-07-08" in report
    assert "not additive" in report
    assert files == render_component_report(evidence)
    assert files["outcome_components.png"].startswith(b"\x89PNG")


def test_component_figure_handles_no_reported_components():
    evidence = analyze_components(*_inputs(), ComponentConfig())
    for population in evidence["populations"].values():
        for summary in population["components"].values():
            summary.update(median_percent=None, programs=0, missing_programs=3)
    files = render_component_report(evidence)
    assert "Not reported" in files["report.md"].decode()
    assert files["outcome_components.png"].startswith(b"\x89PNG")


def _fixture_build(tmp_path, monkeypatch):
    from kasm.patient_journey.artifacts import PatientJourneyBuildContext
    from kasm.patient_journey.config import load_patient_journey_config
    from kasm.patient_journey.followup_artifacts import _OriginalInputs

    records, panel, predictions = _inputs()
    for name in [
        "configs/patient_journey_v2_followup/outcome_components.yaml",
        "docs/specs/patient-journey-v2-outcome-components.md",
        "docs/patient_journey_v2_component_ledger.md",
        "uv.lock",
        "pyproject.toml",
        "src/kasm/patient_journey/component_artifacts.py",
    ]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, path)
    original = _OriginalInputs(
        tuple(panel),
        tuple(predictions),
        load_patient_journey_config(
            ROOT / "configs/patient_journey_v2/experiment.yaml", repository_root=ROOT
        ),
        {},
    )
    monkeypatch.setattr(
        "kasm.patient_journey.component_artifacts.read_component_inputs",
        lambda *a: (original, tuple(records), {}),
    )
    monkeypatch.setattr(
        "kasm.patient_journey.component_artifacts.current_patient_journey_build_context",
        lambda *a: PatientJourneyBuildContext(
            datetime(2026, 9, 7, tzinfo=UTC), "a" * 40, True, "3.12.13"
        ),
    )


def test_complete_fixture_build_records_provenance_and_rejects_repeat(tmp_path, monkeypatch):
    _fixture_build(tmp_path, monkeypatch)
    output = build_components(repository_root=tmp_path)
    manifest = json.loads((output / "manifest.json").read_text())
    provenance = manifest["provenance"]
    assert provenance["canonical_build"] is False
    assert provenance["git_worktree_dirty"] is True
    assert provenance["model_parameters"] == {}
    assert provenance["feature_schema"] == []
    assert provenance["cohort_timing"]["listing_cohort_start"] == "2022-07-01"
    assert len(json.loads((output / "components.json").read_text())) == 3
    with pytest.raises(ComponentError, match="already exists"):
        build_components(repository_root=tmp_path)


def test_changed_inputs_during_render_prevent_publication(tmp_path, monkeypatch):
    _fixture_build(tmp_path, monkeypatch)

    def changed(evidence):
        result = render_component_report(evidence)
        (tmp_path / "docs/patient_journey_v2_component_ledger.md").write_text("changed")
        return result

    monkeypatch.setattr("kasm.patient_journey.component_artifacts.render_component_report", changed)
    with pytest.raises(ComponentError, match="changed during"):
        build_components(repository_root=tmp_path)
    assert not (tmp_path / OUTPUT_ROOT).exists()


def test_component_cli_handles_failure_and_dispatches_only_component_build(monkeypatch, capsys):
    from kasm.cli import main

    monkeypatch.setattr(
        "kasm.cli.build_components", lambda **kwargs: ROOT / OUTPUT_ROOT / ("a" * 64)
    )
    assert main(["patient-journey", "outcome-components"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True

    def fail(**kwargs):
        raise ComponentError("invalid source")

    monkeypatch.setattr("kasm.cli.build_components", fail)
    assert main(["patient-journey", "outcome-components"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "invalid source"


def test_component_build_rejects_bad_cached_source_before_parsing(tmp_path, monkeypatch):
    from kasm.patient_journey.followup_artifacts import _load_original_inputs
    from kasm.patient_journey.followup_config import FollowupConfig

    original = _load_original_inputs(ROOT, FollowupConfig())
    monkeypatch.setattr(
        "kasm.patient_journey.component_artifacts._load_original_inputs", lambda *a: original
    )
    for name in (
        "configs/data_sources.yaml",
        "configs/patient_journey_v2/methodology.yaml",
        "configs/patient_journey_v2_followup/outcome_components.yaml",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, path)
    cache = tmp_path / "data/raw/srtr"
    cache.mkdir(parents=True)
    (cache / "csrs_final_tables_2505all.zip").write_bytes(b"unverified source")
    with pytest.raises(ComponentError, match="cache verification"):
        build_components(repository_root=tmp_path)
    assert not (tmp_path / OUTPUT_ROOT).exists()


def test_component_build_missing_contract_does_not_create_output(tmp_path):
    with pytest.raises(ComponentError, match="fixed"):
        build_components(repository_root=tmp_path)
    assert list(tmp_path.iterdir()) == []
