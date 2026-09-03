from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq
import pytest

import kasm.modeling.challenger as challenger_module
from kasm.cli import main
from kasm.data.build import ModelPanelRow, model_panel_table
from kasm.modeling.challenger import RIDGE_PREDICTIONS_SCHEMA


def _panel_row(program_key: str, target_year: int, offset: float) -> ModelPanelRow:
    feature_year = target_year - 1
    current = (target_year - 2020) / 10 + offset
    target_log = current * 0.8 + 0.03
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
        target_oar=2.718281828459045**target_log,
        target_log_oar=target_log,
        analytic_eligible=True,
        public_forecast_eligible=target_year > 2018,
        first_observed_program=target_year == 2018,
    )


def test_model_backtest_writes_pre_replay_ridge_artifacts_without_2025(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel_path = tmp_path / "model_panel.parquet"
    rows = tuple(
        _panel_row(program_key, target_year, offset)
        for target_year in range(2018, 2026)
        for program_key, offset in (
            ("A000:TX1", -0.2),
            ("B000:TX1", 0.0),
            ("C000:TX1", 0.2),
            ("D000:TX1", 0.4),
        )
    )
    pq.write_table(model_panel_table(rows), panel_path)
    output_dir = tmp_path / "modeling"
    original_read_table = pq.read_table
    observed_filters: list[object] = []

    def read_table_without_replay(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        observed_filters.append(kwargs.get("filters"))
        return original_read_table(*args, **kwargs)

    monkeypatch.setattr(challenger_module.pq, "read_table", read_table_without_replay)

    exit_code = main(
        [
            "model",
            "backtest",
            "--panel-path",
            str(panel_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    predictions = pq.read_table(output_dir / "ridge_predictions.parquet")
    selection = json.loads((output_dir / "ridge_selection.json").read_text(encoding="utf-8"))
    metrics = json.loads((output_dir / "ridge_metrics.json").read_text(encoding="utf-8"))
    assert predictions.schema == RIDGE_PREDICTIONS_SCHEMA
    assert set(predictions.column("target_cohort_year").to_pylist()) == {
        2021,
        2022,
        2023,
        2024,
    }
    assert selection["selection_target_years"] == [2021, 2022, 2023]
    assert selection["selected_alpha"] in [0.01, 0.1, 1.0, 10.0, 100.0]
    assert selection["random_seed"] == 20260903
    assert metrics["frozen_replay_target_year"] == 2025
    assert metrics["frozen_replay_evaluated"] is False
    assert metrics["model_parameters"]["solver"] == "lsqr"
    assert "pre_replay_candidate_gate" in metrics
    assert [("target_cohort_year", "<=", 2024)] in observed_filters
