"""Isolated research output must not follow links or replace earlier evidence."""

from pathlib import Path

import pytest

from kasm.waiting_list.build import (
    load_sources,
    prepare_destination,
    verify_reference,
    write_evidence,
)
from kasm.waiting_list.config import OUTPUT_ROOT, ScreenError


def test_destination_rejects_escape_and_existing_run(tmp_path: Path) -> None:
    for identity in ("../release", "a/b", "", "A" * 64):
        with pytest.raises(ScreenError, match="identity"):
            prepare_destination(tmp_path, identity)
    path = prepare_destination(tmp_path, "a" * 64)
    assert path == tmp_path / OUTPUT_ROOT / ("a" * 64)
    with pytest.raises(ScreenError, match="exists"):
        prepare_destination(tmp_path, "a" * 64)


def test_output_parent_symlink_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere"
    target.mkdir()
    parent = tmp_path / "data"
    try:
        parent.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("This host does not permit creating directory symlinks.")
    with pytest.raises(ScreenError, match="link"):
        prepare_destination(tmp_path, "a" * 64)


def test_evidence_hashes_and_completion_are_written_last(tmp_path: Path) -> None:
    result = write_evidence(
        tmp_path, "b" * 64, {"summary.json": {"count": 3}}, {"analysis_id": "test"}
    )
    assert (result / "complete.json").is_file()
    assert '"summary.json"' in (result / "complete.json").read_text(encoding="utf-8")
    with pytest.raises(ScreenError, match="filename"):
        write_evidence(tmp_path, "c" * 64, {"../bad": {}}, {})


def test_source_ledger_is_frozen_before_results(tmp_path: Path) -> None:
    source = Path("configs/waiting_list/sources.json")
    assert len(load_sources(source)["releases"]) == 9
    changed = tmp_path / "sources.json"
    changed.write_bytes(source.read_bytes().replace(b"2017", b"2016", 1))
    with pytest.raises(ScreenError, match="ledger"):
        load_sources(changed)


def test_source_evidence_rejects_absent_changed_and_escaping_files(tmp_path: Path) -> None:
    from hashlib import sha256

    directory = tmp_path / "data"
    directory.mkdir()
    source = directory / "report.txt"
    source.write_bytes(b"report evidence")
    expected = sha256(source.read_bytes()).hexdigest()
    verify_reference(tmp_path, "data/report.txt", expected)
    for name, fingerprint in (
        ("data/absent.txt", expected),
        ("data/report.txt", "a" * 64),
        ("../report.txt", expected),
        ("C:/report.txt", expected),
    ):
        with pytest.raises(ScreenError, match="evidence"):
            verify_reference(tmp_path, name, fingerprint)
