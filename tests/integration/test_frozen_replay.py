from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import yaml

from kasm.data.build import ModelPanelRow, model_panel_table
from kasm.modeling import replay as replay_module
from kasm.modeling.replay import (
    FROZEN_REPLAY_PREDICTIONS_SCHEMA,
    POINT_ONLY_REPLAY_PREDICTIONS_SCHEMA,
    FrozenReplayError,
    canonical_replay_directory,
    run_frozen_replay,
)


def _panel_row(program_key: str, target_year: int, offset: float) -> ModelPanelRow:
    feature_year = target_year - 1
    current = (target_year - 2020) / 10 + offset
    target_log = current * 0.75 + 0.02
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
        log1p_overall_expected_acceptances=3.0 + offset,
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
        target_oar=exp(target_log),
        target_log_oar=target_log,
        analytic_eligible=True,
        public_forecast_eligible=target_year > 2018,
        first_observed_program=target_year == 2018,
    )


def exp(value: float) -> float:
    return 2.718281828459045**value


@pytest.mark.parametrize("activation_attempted", [True, False])
def test_frozen_replay_publishes_one_hash_addressed_bundle_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    activation_attempted: bool,
) -> None:
    panel_path = tmp_path / "model_panel.parquet"
    rows = tuple(
        _panel_row(f"{index:04d}:TX1", target_year, index / 100)
        for target_year in range(2018, 2026)
        for index in range(120)
    )
    pq.write_table(model_panel_table(rows), panel_path)
    output_root = tmp_path / "frozen-replay"
    config_path = Path("configs/frozen_experiment.yaml")
    manifest_path = Path("configs/data_sources.yaml")
    if not activation_attempted:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        raw["forecast_activation_attempted"] = False
        raw["empirical_band"]["calibration_evidence"] = None
        raw["pre_replay_freeze"]["candidate_gate_passed"] = False
        config_path = tmp_path / "point-only.yaml"
        config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
        # Only the synthetic configuration bypasses the committed-config requirement.
        monkeypatch.setattr(
            replay_module,
            "_verify_committed_frozen_config",
            lambda path: (Path.cwd(), "a" * 40, True),
        )

    result = run_frozen_replay(
        panel_path=panel_path,
        config_path=config_path,
        source_manifest_path=manifest_path,
        output_root=output_root,
    )

    expected_directory = canonical_replay_directory(output_root, config_path, manifest_path)
    assert result.output_directory == expected_directory
    table = pq.read_table(result.predictions_path)
    expected_schema = (
        FROZEN_REPLAY_PREDICTIONS_SCHEMA
        if activation_attempted
        else POINT_ONLY_REPLAY_PREDICTIONS_SCHEMA
    )
    assert table.schema == expected_schema
    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))
    ledger = json.loads(result.completion_path.read_text(encoding="utf-8"))
    assert metrics["frozen_replay_evaluated"] is True
    if not activation_attempted:
        assert metrics["bootstrap"] is None
        assert metrics["band_promotion"] is None
        assert metrics["provenance"]["forecast_activation_attempted"] is False
        assert metrics["provenance"]["calibration_target_year"] is None
        for name in table.column_names:
            if "_band_" in name:
                assert table[name].null_count == table.num_rows
    assert ledger["status"] == "complete"
    assert ledger["prediction_rows"] == 120
    assert ledger["artifact_sha256"]["predictions"]
    assert ledger["git_commit_sha"]
    assert not list(output_root.glob(".frozen-replay-staging-*"))

    with pytest.raises(FrozenReplayError, match="already exists"):
        run_frozen_replay(
            panel_path=panel_path,
            config_path=config_path,
            source_manifest_path=manifest_path,
            output_root=output_root,
        )
