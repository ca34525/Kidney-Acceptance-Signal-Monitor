from __future__ import annotations

from pathlib import Path

import yaml

from kasm.modeling.experiment import load_experiment_config
from kasm.modeling.features import MODEL_FEATURE_COLUMNS


def test_experiment_config_freezes_prespecified_baseline_design() -> None:
    path = Path("configs/experiment.yaml")

    config = load_experiment_config(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert config.feature_columns == MODEL_FEATURE_COLUMNS
    assert config.target_column == "target_log_oar"
    assert config.selection_target_years == (2021, 2022, 2023)
    assert config.validation_target_year == 2024
    assert config.replay_target_year == 2025
    assert config.baselines == ("neutral", "persistence", "historical_mean")
    assert config.ridge_alpha_grid == (0.01, 0.1, 1.0, 10.0, 100.0)
    assert config.ridge_alpha_tie_relative_tolerance == 0.01
    assert config.ridge_random_seed == 20260903
    assert config.minimum_lowest_quartile_rows == 30
    assert raw["ridge"]["alpha_grid"] == [0.01, 0.1, 1, 10, 100]
    assert raw["preprocessing"] == {
        "numeric_imputation": "median",
        "scaling": "standard",
        "fit_scope": "training_fold_only",
        "missingness_indicators": "prespecified_input_columns",
    }
    assert raw["bootstrap"] == {
        "resamples": 10000,
        "seed": 20260903,
        "percentiles": [2.5, 97.5],
        "resampling_unit": "program_key",
    }
    assert raw["empirical_band"]["nominal_coverage"] == 0.8
    assert raw["empirical_band"]["calibration_target_year"] == 2024
    assert raw["empirical_band"]["order_statistic"] == "min(n, ceil((n + 1) * 0.80))"
    assert raw["promotion"]["pre_replay"]["minimum_skill_over_persistence"] == 0.05
    assert raw["promotion"]["point_replay"]["maximum_absolute_mean_signed_log_error"] == 0.05
    assert raw["volume_quartiles"]["minimum_lowest_quartile_rows"] == 30
    assert raw["forecast_activation_attempted"] is None
