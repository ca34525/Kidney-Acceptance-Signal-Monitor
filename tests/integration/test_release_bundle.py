from __future__ import annotations

import shutil
import socket
from hashlib import sha256
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).parents[2]


@pytest.fixture
def copied_release(tmp_path: Path) -> Path:
    # Keep the full replay fingerprints below Windows' legacy path-length limit.
    destination = tmp_path.parent / sha256(str(tmp_path).encode()).hexdigest()[:6]
    shutil.copytree(PROJECT_ROOT / "artifacts/release", destination)
    return destination


def test_complete_release_override_opens_offline(
    copied_release: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KASM_ARTIFACT_DIR", str(copied_release / "processed"))
    monkeypatch.setenv("KASM_MODELING_DIR", str(copied_release / "modeling"))

    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("The copied release attempted network access.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    app = AppTest.from_file(PROJECT_ROOT / "app/streamlit_app.py", default_timeout=10).run()

    assert not app.exception
    assert not app.error
    assert app.selectbox
    assert any(item.label == "Persistence projection" for item in app.metric)


@pytest.mark.parametrize(
    ("damage", "message"),
    [
        ("same_schema_signal", "Release payload"),
        ("missing_manifest", "release_manifest.json"),
        ("invalid_manifest", "JSON artifact is invalid"),
        ("invalid_payload", "checksum"),
    ],
)
def test_app_rejects_unverified_release_before_analytical_display(
    copied_release: Path,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
    message: str,
) -> None:
    manifest_path = copied_release / "release_manifest.json"
    signals_path = copied_release / "processed/program_signals.parquet"
    if damage == "same_schema_signal":
        table = pq.read_table(signals_path)
        rows = table.to_pylist()
        selected = next(
            row
            for row in rows
            if row["program_key"] == "ALUA:TX1"
            and row["cohort_year"] == 2025
            and row["offer_group"] == "overall"
        )
        selected["oar_mean"] = 1.20
        pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), signals_path)
    elif damage == "missing_manifest":
        manifest_path.unlink()
    elif damage == "invalid_manifest":
        manifest_path.write_bytes(b"\xff")
    else:
        signals_path.write_bytes(b"x" * signals_path.stat().st_size)
    monkeypatch.setenv("KASM_ARTIFACT_DIR", str(copied_release / "processed"))
    monkeypatch.setenv("KASM_MODELING_DIR", str(copied_release / "modeling"))

    app = AppTest.from_file(PROJECT_ROOT / "app/streamlit_app.py", default_timeout=10).run()

    assert not app.exception
    assert app.error
    assert message in app.error[0].value
    assert not app.selectbox
    assert not app.metric


@pytest.mark.parametrize("explicit_modeling_override", [True, False])
def test_app_rejects_mixed_release_paths_even_when_panels_match(
    copied_release: Path,
    monkeypatch: pytest.MonkeyPatch,
    explicit_modeling_override: bool,
) -> None:
    monkeypatch.setenv("KASM_ARTIFACT_DIR", str(copied_release / "processed"))
    if explicit_modeling_override:
        monkeypatch.setenv("KASM_MODELING_DIR", str(PROJECT_ROOT / "artifacts/release/modeling"))
    else:
        monkeypatch.delenv("KASM_MODELING_DIR", raising=False)

    app = AppTest.from_file(PROJECT_ROOT / "app/streamlit_app.py", default_timeout=10).run()

    assert not app.exception
    assert app.error
    assert "same complete release" in app.error[0].value
    assert not app.selectbox
    assert not app.metric


def test_tracked_release_bundle_opens_through_default_paths_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KASM_ARTIFACT_DIR", raising=False)
    monkeypatch.delenv("KASM_MODELING_DIR", raising=False)

    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("The tracked offline bundle attempted network access.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    app_path = Path(__file__).parents[2] / "app" / "streamlit_app.py"
    app = AppTest.from_file(app_path, default_timeout=10).run()

    assert not app.exception
    assert app.selectbox
    assert any("Data version:" in item.value for item in app.caption)
    assert any("Model version:" in item.value for item in app.caption)
    assert any(
        "SRTR changed which offers count in the July 2025 and January 2026 reports." in item.value
        and "as well as program behavior" in item.value
        for item in app.caption
    )
