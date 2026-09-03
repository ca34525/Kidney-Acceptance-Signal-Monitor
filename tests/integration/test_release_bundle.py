from __future__ import annotations

import socket
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


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
