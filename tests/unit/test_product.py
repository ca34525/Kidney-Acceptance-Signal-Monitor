from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from kasm.reporting.product import ProductDataError, load_model_evaluation


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _baseline_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    offsets = {"neutral": 0.20, "persistence": 0.0, "historical_mean": 0.08}
    for year in range(2021, 2025):
        for model, offset in offsets.items():
            rows.append(
                {
                    "target_year": year,
                    "model": model,
                    "n": 50,
                    "mae_log_oar": 0.30 + offset,
                }
            )
    return rows


def _write_modeling_bundle(modeling_dir: Path) -> Path:
    modeling_dir.mkdir(parents=True, exist_ok=True)
    panel_hash = "6" * 64
    _write_json(
        modeling_dir / "baseline_metrics.json",
        {
            "by_target_year": _baseline_rows(),
            "frozen_replay_evaluated": False,
            "input_panel_sha256": panel_hash,
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
            "input_panel_sha256": panel_hash,
        },
    )

    config_hash = "1" * 64
    source_hash = "2" * 64
    bundle = modeling_dir / "frozen-replay" / f"{config_hash}_{source_hash}"
    bundle.mkdir(parents=True)
    predictions = bundle / "replay_predictions.parquet"
    predictions.write_bytes(b"trusted replay predictions")
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
                "input_panel_sha256": panel_hash,
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
            "input_panel_sha256": panel_hash,
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
    return bundle


def test_model_evaluation_loader_validates_completed_frozen_bundle(tmp_path: Path) -> None:
    _write_modeling_bundle(tmp_path)

    evaluation = load_model_evaluation(tmp_path, expected_panel_sha256="6" * 64)

    assert evaluation.activation_status == "attempted_not_promoted"
    assert evaluation.displayed_model == "persistence"
    assert evaluation.point_failed_criteria == ("bias_not_exceed_persistence",)
    assert evaluation.ridge_band_gate_passed is True
    assert evaluation.display_band is False
    assert evaluation.band_suppression_reason == "ridge_point_not_promoted"
    assert evaluation.model_version == "111111111111"
    assert evaluation.panel_version == "666666666666"
    assert [row.target_year for row in evaluation.temporal_comparisons] == [
        2021,
        2022,
        2023,
        2024,
    ]
    first = evaluation.temporal_comparisons[0]
    assert first.neutral_mae_log_oar == pytest.approx(0.50)
    assert first.persistence_mae_log_oar == pytest.approx(0.30)
    assert first.historical_mean_mae_log_oar == pytest.approx(0.38)
    assert first.ridge_mae_log_oar == pytest.approx(0.27)
    assert evaluation.replay.target_year == 2025
    assert evaluation.replay.ridge_mae_log_oar == pytest.approx(0.24)
    assert evaluation.replay.bootstrap_interval == pytest.approx((-0.04, -0.01))
    assert evaluation.prospective_validation is False


def _disable_activation(bundle: Path) -> None:
    path = bundle / "replay_metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    metrics["point_promotion"]["failed_criteria"] = ["forecast_activation_not_attempted"]
    metrics["band_promotion"] = None
    metrics["bootstrap"] = None
    _write_json(path, metrics)
    completion = json.loads((bundle / "completion.json").read_text(encoding="utf-8"))
    completion["artifact_sha256"]["metrics"] = _sha256(path)
    _write_json(bundle / "completion.json", completion)


def test_model_loader_accepts_explicit_no_activation_without_band_or_bootstrap(
    tmp_path: Path,
) -> None:
    bundle = _write_modeling_bundle(tmp_path)
    _disable_activation(bundle)
    evaluation = load_model_evaluation(tmp_path, expected_panel_sha256="6" * 64)
    assert evaluation.activation_status == "not_attempted"
    assert evaluation.displayed_model == "persistence"
    assert evaluation.replay.bootstrap_interval is None
    assert evaluation.band_coverage is None
    assert evaluation.band_coverage_interval is None
    assert evaluation.band_mean_width_relative_to_persistence is None
    assert not evaluation.display_band
    assert evaluation.band_suppression_reason == "forecast_activation_not_attempted"


def test_no_activation_artifact_cannot_include_evaluated_uncertainty(tmp_path: Path) -> None:
    bundle = _write_modeling_bundle(tmp_path)
    path = bundle / "replay_metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    metrics["point_promotion"]["failed_criteria"] = ["forecast_activation_not_attempted"]
    _write_json(path, metrics)
    completion = json.loads((bundle / "completion.json").read_text(encoding="utf-8"))
    completion["artifact_sha256"]["metrics"] = _sha256(path)
    _write_json(bundle / "completion.json", completion)
    with pytest.raises(ProductDataError, match="not attempted"):
        load_model_evaluation(tmp_path, expected_panel_sha256="6" * 64)


def test_model_evaluation_loader_rejects_ambiguous_or_tampered_bundle(
    tmp_path: Path,
) -> None:
    bundle = _write_modeling_bundle(tmp_path)
    predictions = bundle / "replay_predictions.parquet"
    predictions.write_bytes(predictions.read_bytes() + b"tampered")

    with pytest.raises(ProductDataError, match="checksum"):
        load_model_evaluation(tmp_path, expected_panel_sha256="6" * 64)

    predictions.write_bytes(b"trusted replay predictions")
    second = tmp_path / "frozen-replay" / f"{'4' * 64}_{'5' * 64}"
    second.mkdir()
    (second / "completion.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ProductDataError, match="exactly one completed frozen replay"):
        load_model_evaluation(tmp_path, expected_panel_sha256="6" * 64)


def test_model_evaluation_loader_rejects_missing_bundle(tmp_path: Path) -> None:
    with pytest.raises(ProductDataError, match="exactly one completed frozen replay"):
        load_model_evaluation(tmp_path, expected_panel_sha256="6" * 64)


def test_model_evaluation_loader_rejects_mismatched_panel(tmp_path: Path) -> None:
    _write_modeling_bundle(tmp_path)

    with pytest.raises(ProductDataError, match="model panel checksum"):
        load_model_evaluation(tmp_path, expected_panel_sha256="7" * 64)


def test_model_evaluation_loader_rejects_incomplete_or_malformed_bundle(
    tmp_path: Path,
) -> None:
    incomplete = _write_modeling_bundle(tmp_path / "a")
    incomplete_ledger = json.loads((incomplete / "completion.json").read_text(encoding="utf-8"))
    incomplete_ledger["status"] = "in_progress"
    _write_json(incomplete / "completion.json", incomplete_ledger)

    with pytest.raises(ProductDataError, match="not complete"):
        load_model_evaluation(tmp_path / "a", expected_panel_sha256="6" * 64)

    malformed = _write_modeling_bundle(tmp_path / "b")
    metrics = malformed / "replay_metrics.json"
    metrics.write_text("{", encoding="utf-8")
    malformed_ledger = json.loads((malformed / "completion.json").read_text(encoding="utf-8"))
    malformed_ledger["artifact_sha256"]["metrics"] = _sha256(metrics)
    _write_json(malformed / "completion.json", malformed_ledger)

    with pytest.raises(ProductDataError, match="invalid JSON"):
        load_model_evaluation(tmp_path / "b", expected_panel_sha256="6" * 64)
