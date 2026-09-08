"""New reports stay confined, write-once and fingerprinted."""

import json
import socket
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from kasm.waiting_list_case_study.build import verify_run, write_run


def test_write_once_and_verify_all_outputs(tmp_path: Path) -> None:
    destination = write_run(tmp_path, "a" * 64, {"brief.html": b"<p>Counts</p>"}, {"years": [2025]})
    assert verify_run(tmp_path, destination.name)["run_identity"] == "a" * 64
    with pytest.raises(ValueError, match="already exists"):
        write_run(tmp_path, "a" * 64, {"brief.html": b"replacement"}, {})
    (destination / "brief.html").write_bytes(b"changed")
    with pytest.raises(ValueError, match="fingerprint"):
        verify_run(tmp_path, destination.name)


@pytest.mark.parametrize("identity", ["../outside", "/absolute", "A" * 64, "a" * 63])
def test_reject_unsafe_run_identity(tmp_path: Path, identity: str) -> None:
    with pytest.raises(ValueError, match="identity"):
        write_run(tmp_path, identity, {"brief.html": b"ok"}, {})
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize(
    "name",
    [
        "../brief.html",
        "sub/brief.html",
        "C:brief.html",
        "complete.json",
        "provenance.json",
        "code.py",
    ],
)
def test_reject_unsafe_output_name(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError, match="filename"):
        write_run(tmp_path, "a" * 64, {name: b"ok"}, {})
    assert not (tmp_path / "data").exists()


def test_missing_output_is_actionable(tmp_path: Path) -> None:
    destination = write_run(tmp_path, "a" * 64, {"brief.html": b"ok"}, {})
    (destination / "brief.html").unlink()
    with pytest.raises(ValueError, match="missing"):
        verify_run(tmp_path, destination.name)


def test_output_directory_redirect_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    output_parent = tmp_path / "data" / "research"
    output_parent.mkdir(parents=True)
    redirect = output_parent / "waiting-list-case-study-0026"
    try:
        redirect.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating filesystem links is unavailable on this host.")
    with pytest.raises(ValueError, match="link|redirect"):
        write_run(tmp_path, "a" * 64, {"brief.html": b"ok"}, {})
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("content", [b"[]", b"{", b'{"run_identity": false, "sha256": {}}'])
def test_malformed_completion_is_actionable(tmp_path: Path, content: bytes) -> None:
    destination = write_run(tmp_path, "a" * 64, {"brief.html": b"ok"}, {})
    (destination / "complete.json").write_bytes(content)
    with pytest.raises(ValueError, match="marker"):
        verify_run(tmp_path, destination.name)


def test_verifier_does_not_follow_marker_paths(tmp_path: Path) -> None:
    destination = write_run(tmp_path, "a" * 64, {"brief.html": b"ok"}, {})
    marker = json.loads((destination / "complete.json").read_bytes())
    marker["sha256"]["../elsewhere.json"] = "b" * 64
    (destination / "complete.json").write_text(json.dumps(marker), encoding="utf-8")
    with pytest.raises(ValueError, match="filename"):
        verify_run(tmp_path, destination.name)


def test_verifier_rejects_unrecorded_file(tmp_path: Path) -> None:
    destination = write_run(tmp_path, "a" * 64, {"brief.html": b"ok"}, {})
    (destination / "extra.html").write_bytes(b"extra")
    with pytest.raises(ValueError, match="inventory"):
        verify_run(tmp_path, destination.name)


def test_junction_guard_without_host_link_privilege(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "is_junction", lambda path: path.name == "research")
    with pytest.raises(ValueError, match="redirect"):
        write_run(tmp_path, "a" * 64, {"brief.html": b"ok"}, {})


def test_repository_root_redirect_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "is_junction", lambda path: path == tmp_path)
    with pytest.raises(ValueError, match="redirect"):
        write_run(tmp_path, "a" * 64, {"brief.html": b"ok"}, {})


def test_full_observation_table_is_a_fingerprinted_output(tmp_path: Path) -> None:
    destination = write_run(
        tmp_path, "a" * 64, {"observations.csv": b"program,change\nAAAA:TX1,-5\n"}, {}
    )
    assert "observations.csv" in verify_run(tmp_path, destination.name)["sha256"]


def test_duplicate_completion_fields_are_rejected(tmp_path: Path) -> None:
    destination = write_run(tmp_path, "a" * 64, {"brief.html": b"ok"}, {})
    marker_path = destination / "complete.json"
    original = marker_path.read_text(encoding="utf-8")
    marker_path.write_text(
        original.replace("{", '{"run_identity": "unexpected",', 1), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="marker"):
        verify_run(tmp_path, destination.name)


def test_offline_build_and_requested_brief_use_the_same_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kasm.waiting_list.parse import AnnualRecord
    from kasm.waiting_list.screen import compare_years
    from kasm.waiting_list_case_study import build as module
    from kasm.waiting_list_case_study import config, inputs

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Offline report attempted network or source parsing.")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr("kasm.waiting_list.build._read_releases", forbidden)
    monkeypatch.setattr("kasm.waiting_list.build.verdict", forbidden)
    records = tuple(
        AnnualRecord(
            "AAAA:TX1",
            "2605",
            year,
            100 + index * 5,
            105 + index * 5,
            15 + index,
            (10 + index, 0, 0, 0, 0, 0, 0, 0),
            "2026-07-07",
            "day",
            "https://example.org/source.xls",
            "c" * 64,
        )
        for index, year in enumerate(range(2022, 2026))
    )
    pairs, _ = compare_years(records)
    trusted = inputs.TrustedInputs(
        records, pairs, {}, {"exclusions": []}, {"source_releases": []}, {"complete.json": "d" * 64}
    )
    monkeypatch.setattr(config, "load_config", lambda path: config.CaseStudyConfig())
    monkeypatch.setattr(inputs, "load_inputs", lambda root, settings: trusted)
    monkeypatch.setattr(module, "_implementation_hashes", lambda root: {"fixture.py": "e" * 64})
    monkeypatch.setattr(
        module,
        "current_patient_journey_build_context",
        lambda root: SimpleNamespace(
            git_commit_sha="a" * 40,
            git_worktree_dirty=False,
            build_timestamp_utc=datetime(2026, 9, 8, tzinfo=UTC),
            python_version="3.12.11",
        ),
    )
    full = module.build(tmp_path)
    selected = json.loads((full / "program_briefs.json").read_bytes())[0]
    requested = module.build(tmp_path, "AAAA:TX1", 2025)
    assert json.loads((requested / "program_brief.json").read_bytes()) == selected
    assert "115" in (requested / "program_brief.html").read_text(encoding="utf-8")
    assert full != requested
    assert verify_run(tmp_path, full.name)["sha256"]["observations.csv"]
    unsupported = module.build(tmp_path, "AAAA:TX1", 2022)
    assert not json.loads((unsupported / "program_brief.json").read_bytes())["available"]
    assert "unsupported" in (unsupported / "program_brief.html").read_text(encoding="utf-8")
