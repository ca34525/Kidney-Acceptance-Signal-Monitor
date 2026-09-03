from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq
import pytest

import kasm.modeling.backtest as backtest_module
from kasm.data.build import ModelPanelRow, model_panel_table
from kasm.modeling.backtest import BASELINE_PREDICTIONS_SCHEMA, run_baseline_backtest


def _panel_row(program_key: str, target_year: int, offset: float) -> ModelPanelRow:
    feature_year = target_year - 1
    current = (target_year - 2020) / 10 + offset
    return ModelPanelRow(
        program_key=program_key,
        feature_cohort_year=feature_year,
        target_cohort_year=target_year,
        prediction_as_of=f"{target_year}-07-01",
        prediction_as_of_precision="day",
        target_cohort_end=date(target_year, 12, 31),
        truth_published_value=f"{target_year + 1}-07-01",
        truth_published_precision="day",
        elapsed_target_cohort_fraction_at_prediction=0.5,
        current_log_overall_oar=current,
        previous_annual_log_overall_oar=current - 0.1,
        one_year_change_log_overall_oar=0.1,
        log1p_overall_expected_acceptances=4.0 + offset,
        log_credible_interval_width=0.4,
        current_log_low_oar=current - 0.1,
        current_log_medium_oar=current,
        current_log_high_oar=current + 0.1,
        current_log_hard_to_place_oar=current + 0.2,
        high_offers_share=0.4,
        hard_to_place_offers_share=0.1,
        missing_previous_annual_log_overall_oar=False,
        missing_one_year_change_log_overall_oar=False,
        missing_current_log_low_oar=False,
        missing_current_log_medium_oar=False,
        missing_current_log_high_oar=False,
        missing_current_log_hard_to_place_oar=False,
        target_oar=2.718281828459045 ** (current + 0.05),
        target_log_oar=current + 0.05,
        analytic_eligible=True,
        public_forecast_eligible=target_year > 2018,
        first_observed_program=target_year == 2018,
    )


def test_processed_panel_runs_through_pre_replay_baseline_artifacts(tmp_path: Path) -> None:
    panel_path = tmp_path / "model_panel.parquet"
    rows = tuple(
        _panel_row(program_key, target_year, offset)
        for target_year in range(2018, 2025)
        for program_key, offset in (("ABCD:TX1", 0.0), ("WXYZ:TX1", 0.2))
    )
    pq.write_table(model_panel_table(rows), panel_path)

    result = run_baseline_backtest(
        panel_path, Path("configs/experiment.yaml"), tmp_path / "modeling"
    )

    predictions = pq.read_table(result.predictions_path)
    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))
    folds = json.loads(result.folds_path.read_text(encoding="utf-8"))
    assert predictions.schema == BASELINE_PREDICTIONS_SCHEMA
    assert result.prediction_rows == 24
    assert set(predictions.column("target_cohort_year").to_pylist()) == {
        2021,
        2022,
        2023,
        2024,
    }
    assert metrics["frozen_replay_target_year"] == 2025
    assert metrics["frozen_replay_evaluated"] is False
    assert all(item["target_years"] == [2021, 2022, 2023] for item in metrics["selection_summary"])
    assert [fold["evaluation_target_year"] for fold in folds["folds"]] == [
        2021,
        2022,
        2023,
        2024,
    ]
    assert folds["random_row_split_available"] is False


def test_failed_backtest_does_not_publish_partial_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel_path = tmp_path / "model_panel.parquet"
    rows = tuple(_panel_row("ABCD:TX1", target_year, 0.0) for target_year in range(2018, 2025))
    pq.write_table(model_panel_table(rows), panel_path)
    output_dir = tmp_path / "modeling"

    def fail_json_write(_value: object, _path: Path) -> None:
        raise OSError("fixture metrics serialization failure")

    monkeypatch.setattr(backtest_module, "_write_json", fail_json_write)

    with pytest.raises(OSError, match="fixture metrics serialization failure"):
        run_baseline_backtest(panel_path, Path("configs/experiment.yaml"), output_dir)

    assert not output_dir.exists()
