"""Keep every sprint stage immutable and verify evidence before later scoring."""

import json
from pathlib import Path

import pytest

from kasm.program_prediction.runs import load_run, publish_run, validate_destination


def test_run_is_write_once_and_payload_is_verified(tmp_path: Path) -> None:
    path = publish_run(tmp_path, "test-build", {"panel.json": b"[]"}, {"stage": "build"})
    assert load_run(tmp_path, "test-build", stage="build")["panel.json"] == []
    with pytest.raises(ValueError, match="exists"):
        publish_run(tmp_path, "test-build", {"panel.json": b"[]"}, {})
    with pytest.raises(ValueError, match="stage"):
        load_run(tmp_path, "test-build", stage="screen")
    (path / "panel.json").write_text("[0]")
    with pytest.raises(ValueError, match="hash|identity"):
        load_run(tmp_path, "test-build", stage="build")


@pytest.mark.parametrize("run_id", ["../escape", "CON", "con", "c:/outside", "a/b", "bad."])
def test_unsafe_destination_is_rejected(tmp_path: Path, run_id: str) -> None:
    with pytest.raises(ValueError, match="Run ID"):
        validate_destination(tmp_path, run_id)


@pytest.mark.parametrize("filename", ["../escape.json", "CON.json", "con.json", "a.json."])
def test_unsafe_payload_is_rejected(tmp_path: Path, filename: str) -> None:
    with pytest.raises(ValueError, match="filename"):
        publish_run(tmp_path, "safe-id", {filename: b"{}"}, {})
    assert not (tmp_path / "data").exists()


def test_manifest_cannot_redirect_reads(tmp_path: Path) -> None:
    path = publish_run(tmp_path, "test-build", {"panel.json": b"[]"}, {"stage": "build"})
    completion = json.loads((path / "completion.json").read_text())
    completion["files"]["../../outside.json"] = completion["files"].pop("panel.json")
    (path / "completion.json").write_text(json.dumps(completion))
    with pytest.raises(ValueError, match="filename"):
        load_run(tmp_path, "test-build", stage="build")


def test_output_redirect_fails_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "is_junction", lambda path: path.name == "research")
    with pytest.raises(ValueError, match="link|redirect"):
        publish_run(tmp_path, "test-build", {"panel.json": b"[]"}, {})
    assert not (tmp_path / "data").exists()


def test_missing_and_malformed_completion_are_actionable(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing|unreadable"):
        load_run(tmp_path, "missing", stage="build")
    path = publish_run(tmp_path, "test-build", {"panel.json": b"[]"}, {"stage": "build"})
    (path / "completion.json").write_text("[]")
    with pytest.raises(ValueError, match="completion"):
        load_run(tmp_path, "test-build", stage="build")


def test_saved_parent_hash_is_checked_before_child_reuse(tmp_path: Path) -> None:
    from kasm.acceptance_forecast.inputs import file_hash

    parent = publish_run(tmp_path, "parent", {"panel.json": b"[]"}, {"stage": "build"})
    publish_run(
        tmp_path,
        "child",
        {"predictions.json": b"[]"},
        {
            "stage": "screen",
            "parents": {
                "panel": {
                    "run_id": "parent",
                    "completion_sha256": file_hash(parent / "completion.json"),
                }
            },
        },
    )
    (parent / "completion.json").write_text("{}")
    with pytest.raises(ValueError, match="parent|Parent"):
        load_run(tmp_path, "child", stage="screen")
