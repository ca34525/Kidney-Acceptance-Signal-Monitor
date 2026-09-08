from __future__ import annotations

import hashlib
import json
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

PROJECT_ROOT = Path(__file__).parents[2]


def _release_root(tmp_path: Path) -> Path:
    # Full replay fingerprints need a short test root on Windows.
    return tmp_path.parent / hashlib.sha256(str(tmp_path).encode()).hexdigest()[:6]


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


def _write_fixture(artifact_dir: Path, *, public_eligible: bool) -> None:
    signals = tuple(
        _signal(year, group, None if group == "low" and year == 2025 else ratio)
        for year, ratio in ((2024, 0.8), (2025, 0.9))
        for group in ("overall", "low", "medium", "high", "hard-to-place")
    )
    sources = (_source(2024), _source(2025))
    panel = build_model_panel(signals, sources)
    panel = tuple(
        replace(row, public_forecast_eligible=public_eligible)
        if row.feature_cohort_year == 2025
        else row
        for row in panel
    )
    write_data_artifacts(signals, panel, {}, artifact_dir)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_modeling_fixture(modeling_dir: Path, *, panel_sha256: str) -> None:
    modeling_dir.mkdir(parents=True)
    for name in (
        "baseline_predictions.parquet",
        "ridge_predictions.parquet",
        "ridge_selection.json",
        "temporal_folds.json",
    ):
        (modeling_dir / name).write_bytes(b"unused synthetic UI payload")
    baseline_rows = [
        {
            "target_year": year,
            "model": model,
            "n": 50,
            "mae_log_oar": mae,
        }
        for year in range(2021, 2025)
        for model, mae in (
            ("neutral", 0.50),
            ("persistence", 0.30),
            ("historical_mean", 0.38),
        )
    ]
    _write_json(
        modeling_dir / "baseline_metrics.json",
        {
            "by_target_year": baseline_rows,
            "frozen_replay_evaluated": False,
            "input_panel_sha256": panel_sha256,
        },
    )
    _write_json(
        modeling_dir / "ridge_metrics.json",
        {
            "by_target_year": [
                {
                    "target_year": year,
                    "n": 50,
                    "mae_log_oar": 0.27,
                    "persistence_mae_log_oar": 0.30,
                    "skill_over_persistence": 0.10,
                }
                for year in range(2021, 2025)
            ],
            "frozen_replay_evaluated": False,
            "input_panel_sha256": panel_sha256,
        },
    )
    config_hash = "1" * 64
    source_hash = "2" * 64
    bundle = modeling_dir / "frozen-replay" / f"{config_hash}_{source_hash}"
    bundle.mkdir(parents=True)
    predictions = bundle / "replay_predictions.parquet"
    predictions.write_bytes(b"fixture replay predictions")
    metrics = bundle / "replay_metrics.json"
    _write_json(
        metrics,
        {
            "frozen_replay_evaluated": True,
            "evidence_classification": "descriptive_retrospective_product_selection",
            "prospective_validation": False,
            "replay_target_year": 2025,
            "selected_alpha": 10.0,
            "overall": {
                "n": 50,
                "ridge_mae_log_oar": 0.24,
                "persistence_mae_log_oar": 0.27,
                "ridge_mean_signed_log_error": -0.011,
                "persistence_mean_signed_log_error": -0.009,
                "skill_over_persistence": 0.111,
            },
            "bootstrap": {"lower": -0.04, "upper": -0.01},
            "point_promotion": {
                "displayed_model": "persistence",
                "failed_criteria": ["bias_not_exceed_persistence"],
                "promoted": False,
                "skill_over_persistence": 0.111,
            },
            "band_promotion": {
                "coverage": 0.82,
                "display_band": True,
                "exact_interval_lower": 0.76,
                "exact_interval_upper": 0.87,
                "failed_criteria": [],
                "mean_width_relative_to_persistence": 0.90,
            },
            "provenance": {
                "frozen_experiment_sha256": config_hash,
                "source_manifest_sha256": source_hash,
                "input_panel_sha256": panel_sha256,
                "git_commit_sha": "3" * 40,
            },
        },
    )
    _write_json(
        bundle / "completion.json",
        {
            "status": "complete",
            "frozen_experiment_sha256": config_hash,
            "source_manifest_sha256": source_hash,
            "input_panel_sha256": panel_sha256,
            "prediction_rows": 50,
            "artifacts": {
                "metrics": metrics.name,
                "predictions": predictions.name,
            },
            "artifact_sha256": {
                "metrics": _sha256(metrics),
                "predictions": _sha256(predictions),
            },
        },
    )


def _write_release_manifest(release_root: Path) -> None:
    """Give the synthetic UI fixture the complete release's integrity envelope."""
    manifest = json.loads(
        (PROJECT_ROOT / "artifacts/release/release_manifest.json").read_text(encoding="utf-8")
    )
    manifest["provenance"].update(
        frozen_experiment_sha256="1" * 64,
        source_manifest_sha256="2" * 64,
        input_panel_sha256=_sha256(release_root / "processed/model_panel.parquet"),
    )
    files = sorted(
        path
        for path in release_root.rglob("*")
        if path.is_file() and path.name != "release_manifest.json"
    )
    entries = []
    for path in files:
        relative = path.relative_to(release_root)
        entries.append(
            {
                "bytes": path.stat().st_size,
                "canonical_path": Path(*relative.parts[1:]).as_posix(),
                "canonical_root": relative.parts[0],
                "path": relative.as_posix(),
                "sha256": _sha256(path),
            }
        )
    identity = [{key: entry[key] for key in ("bytes", "path", "sha256")} for entry in entries]
    manifest["files"] = entries
    manifest["file_count"] = len(entries)
    manifest["bundle_content_sha256"] = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload_size = sum(path.stat().st_size for path in files)
    manifest["total_bytes"] = 0
    for _ in range(10):
        rendered = json.dumps(manifest).encode()
        total = payload_size + len(rendered)
        if manifest["total_bytes"] == total:
            (release_root / "release_manifest.json").write_bytes(rendered)
            return
        manifest["total_bytes"] = total
    raise AssertionError("Synthetic release size did not stabilize.")


def test_complete_offline_app_flow_retains_persistence_and_suppresses_band(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_root = _release_root(tmp_path)
    artifact_dir = release_root / "processed"
    modeling_dir = release_root / "modeling"
    _write_fixture(artifact_dir, public_eligible=True)
    _write_modeling_fixture(
        modeling_dir, panel_sha256=_sha256(artifact_dir / "model_panel.parquet")
    )
    _write_release_manifest(release_root)

    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("The historical app attempted network access.")

    monkeypatch.setenv("KASM_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setenv("KASM_MODELING_DIR", str(modeling_dir))
    monkeypatch.setattr(socket, "create_connection", reject_network)

    app_path = Path(__file__).parents[2] / "app" / "streamlit_app.py"
    app = AppTest.from_file(app_path, default_timeout=10).run()

    assert not app.exception
    assert app.selectbox[0].value == "ABCD:TX1"
    assert app.warning[0].value == (
        "Public aggregate prototype — not clinical or regulatory decision support"
    )
    assert any("Published overall OAR history" in item.value for item in app.subheader)
    assert any("Donor-stratum history" in item.value for item in app.subheader)
    assert any("Model evaluation" in item.value for item in app.subheader)
    assert any("Data version:" in item.value for item in app.caption)
    assert any("Model version:" in item.value for item in app.caption)
    assert any(item.label == "Persistence projection" for item in app.metric)
    assert any(
        item.value == "0.90" for item in app.metric if item.label == "Persistence projection"
    )
    assert any("Persistence retained" in item.value for item in app.info)
    assert any("design mistake" in item.value for item in app.info)
    assert any("rule is retired" in item.value for item in app.info)
    assert any(
        "No nominal 80% empirical forecast band is displayed" in item.value for item in app.info
    )
    assert any("do not establish future coverage" in item.value for item in app.info)
    assert any("descriptive retrospective" in item.value.casefold() for item in app.caption)


def test_app_ineligible_state_never_exposes_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_root = _release_root(tmp_path)
    artifact_dir = release_root / "processed"
    modeling_dir = release_root / "modeling"
    _write_fixture(artifact_dir, public_eligible=False)
    _write_modeling_fixture(
        modeling_dir, panel_sha256=_sha256(artifact_dir / "model_panel.parquet")
    )
    _write_release_manifest(release_root)
    monkeypatch.setenv("KASM_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setenv("KASM_MODELING_DIR", str(modeling_dir))

    app_path = Path(__file__).parents[2] / "app" / "streamlit_app.py"
    app = AppTest.from_file(app_path, default_timeout=10).run()

    assert not app.exception
    assert any("Insufficient history or artifact ineligibility" in item.value for item in app.info)
    assert not any(item.label == "Persistence projection" for item in app.metric)


def test_offline_app_handles_activation_not_attempted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_root = _release_root(tmp_path)
    artifact_dir = release_root / "processed"
    modeling_dir = release_root / "modeling"
    _write_fixture(artifact_dir, public_eligible=True)
    _write_modeling_fixture(
        modeling_dir, panel_sha256=_sha256(artifact_dir / "model_panel.parquet")
    )
    metrics_path = next(modeling_dir.glob("frozen-replay/*/replay_metrics.json"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["point_promotion"]["failed_criteria"] = ["forecast_activation_not_attempted"]
    metrics["band_promotion"] = None
    metrics["bootstrap"] = None
    _write_json(metrics_path, metrics)
    completion_path = metrics_path.parent / "completion.json"
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    completion["artifact_sha256"]["metrics"] = _sha256(metrics_path)
    _write_json(completion_path, completion)
    _write_release_manifest(release_root)
    monkeypatch.setenv("KASM_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setenv("KASM_MODELING_DIR", str(modeling_dir))

    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("Offline app attempted network access")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    app = AppTest.from_file(Path("app/streamlit_app.py").resolve(), default_timeout=10).run()
    assert not app.exception
    assert any(item.label == "Persistence projection" for item in app.metric)
    assert any("not attempted" in item.value.lower() for item in app.info)
    assert any("not calculated" in item.value.lower() for item in app.caption)
    assert not any("calibrates the separate residual band" in item.value for item in app.markdown)


def test_product_copy_excludes_prohibited_claims() -> None:
    app_path = Path(__file__).parents[2] / "app" / "streamlit_app.py"
    copy = app_path.read_text(encoding="utf-8").casefold()

    for prohibited in (
        "leaderboard",
        "mpsc",
        "regulatory risk",
        "poor program",
        "unsafe program",
        "avoidable decline",
        "real-time forecast",
        "prospective validation",
    ):
        assert prohibited not in copy
