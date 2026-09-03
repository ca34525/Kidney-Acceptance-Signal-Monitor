from __future__ import annotations

import socket
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from kasm.config import SourceRecord
from kasm.data.build import (
    CanonicalSignal,
    build_model_panel,
    write_data_artifacts,
)


def _source(year: int) -> SourceRecord:
    return SourceRecord(
        release_code=str(year),
        release_label=f"Fixture {year}",
        published_value=f"{year + 1}-07-07",
        published_precision="day",
        cohort_year=year,
        expected_rows=1,
        expected_columns=1,
        sheet_name="Fixture",
        transport="xls",
        url=f"https://example.test/{year}.xls",
        download_bytes=1,
        download_sha256="0" * 64,
    )


def _signal(year: int, group: str, ratio: float | None) -> CanonicalSignal:
    offers = {"overall": 100, "low": 20, "medium": 30, "high": 50, "hard-to-place": 10}[group]
    return CanonicalSignal(
        program_key="ABCD:TX1",
        center_code="ABCD",
        center_type="TX1",
        center_name="Fixture Kidney Program",
        city="Boston",
        state="MA",
        zip="01234",
        release_code=str(year),
        published_value=f"{year + 1}-07-07",
        published_precision="day",
        cohort_year=year,
        cohort_start=date(year, 1, 1),
        cohort_end=date(year, 12, 31),
        offer_group=group,  # type: ignore[arg-type]
        offers=offers,
        acceptances=offers // 10,
        expected_acceptances=12.5 if group == "overall" else offers / 8,
        oar_mean=ratio,
        oar_lower=None if ratio is None else ratio * 0.8,
        oar_upper=None if ratio is None else ratio * 1.2,
        source_url=f"https://example.test/{year}.xls",
        source_sha256="0" * 64,
    )


def _write_fixture(artifact_dir: Path) -> None:
    signals = tuple(
        _signal(year, group, None if group == "low" and year == 2025 else ratio)
        for year, ratio in ((2024, 0.8), (2025, 0.9))
        for group in ("overall", "low", "medium", "high", "hard-to-place")
    )
    sources = (_source(2024), _source(2025))
    panel = build_model_panel(signals, sources)
    panel = tuple(
        replace(row, public_forecast_eligible=False) if row.feature_cohort_year == 2025 else row
        for row in panel
    )
    write_data_artifacts(signals, panel, {}, artifact_dir)


def test_walking_skeleton_loads_one_program_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_dir = tmp_path / "processed"
    _write_fixture(artifact_dir)

    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("The historical app attempted network access.")

    monkeypatch.setenv("KASM_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setattr(socket, "create_connection", reject_network)

    app_path = Path(__file__).parents[2] / "app" / "streamlit_app.py"
    app = AppTest.from_file(app_path, default_timeout=10).run()

    assert not app.exception
    assert app.selectbox[0].value == "ABCD:TX1"
    assert app.warning[0].value == (
        "Public aggregate prototype — not clinical or regulatory decision support"
    )
    assert any("Published overall OAR history" in item.value for item in app.subheader)
    assert any("Artifact version:" in item.value for item in app.caption)
    assert any("Insufficient history" in item.value for item in app.info)
