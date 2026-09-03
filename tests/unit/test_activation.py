from __future__ import annotations

from math import exp
from pathlib import Path

import pytest
import yaml

from kasm.modeling.activation import (
    PairedAbsoluteErrors,
    assess_band_promotion,
    assess_point_promotion,
    calibrate_empirical_band,
    clopper_pearson_interval,
    paired_bootstrap_mae_difference_interval,
)
from kasm.modeling.challenger import RidgePrediction
from kasm.modeling.experiment import ExperimentConfigError, load_frozen_experiment_config


def _prediction(program_key: str, target_year: int, residual: float) -> RidgePrediction:
    predicted_log_oar = 0.2
    target_log_oar = predicted_log_oar + residual
    return RidgePrediction(
        program_key=program_key,
        feature_cohort_year=target_year - 1,
        target_cohort_year=target_year,
        fold_id=f"target_{target_year}",
        first_observed_program=False,
        log1p_overall_expected_acceptances=4.0,
        expected_acceptance_quartile=1,
        target_log_oar=target_log_oar,
        target_oar=exp(target_log_oar),
        model="ridge",
        ridge_alpha=10.0,
        predicted_log_oar=predicted_log_oar,
        predicted_oar=exp(predicted_log_oar),
        absolute_error_log_oar=abs(residual),
        absolute_error_oar=abs(exp(predicted_log_oar) - exp(target_log_oar)),
        signed_error_log_oar=-residual,
        persistence_absolute_error_log_oar=abs(residual) + 0.1,
        absolute_error_difference_vs_persistence=-0.1,
    )


def test_band_uses_only_2024_validation_residuals_and_exact_order_statistic() -> None:
    config = load_frozen_experiment_config(Path("configs/frozen_experiment.yaml"))
    residuals = (0.4, 0.1, 0.3, 0.2)
    predictions = tuple(
        _prediction(f"{index:04d}:TX1", 2024, residual) for index, residual in enumerate(residuals)
    )

    calibration = calibrate_empirical_band(predictions, config=config)

    assert calibration.calibration_target_year == 2024
    assert calibration.sample_size == 4
    assert calibration.order_statistic_rank == 4
    assert calibration.absolute_log_residual_radius == pytest.approx(0.4)
    with pytest.raises(ValueError, match="exactly target year 2024"):
        calibrate_empirical_band(
            (*predictions, _prediction("Z000:TX1", 2023, 0.9)),
            config=config,
        )


def test_paired_bootstrap_is_deterministic_and_resamples_program_keys() -> None:
    config = load_frozen_experiment_config(Path("configs/frozen_experiment.yaml"))
    pairs = tuple(
        PairedAbsoluteErrors(
            program_key=f"{index:04d}:TX1",
            challenger_absolute_error=challenger,
            persistence_absolute_error=persistence,
        )
        for index, (challenger, persistence) in enumerate(
            ((0.1, 0.4), (0.2, 0.3), (0.4, 0.2), (0.1, 0.5))
        )
    )

    first = paired_bootstrap_mae_difference_interval(pairs, config=config)
    second = paired_bootstrap_mae_difference_interval(tuple(reversed(pairs)), config=config)

    assert first == second
    assert first.resamples == 10_000
    assert first.seed == 20260903
    assert first.percentiles == (2.5, 97.5)
    with pytest.raises(ValueError, match="unique program_key"):
        paired_bootstrap_mae_difference_interval((pairs[0], pairs[0]), config=config)


@pytest.mark.parametrize(
    ("overrides", "expected_failure"),
    [
        ({"challenger_mae": 0.96}, "minimum_skill_over_persistence"),
        ({"bootstrap_upper": 0.0}, "bootstrap_interval_below_zero"),
        ({"challenger_bias": 0.051}, "maximum_absolute_mean_signed_log_error"),
        ({"persistence_bias": 0.01}, "bias_not_exceed_persistence"),
        ({"challenger_low_volume_mae": 1.11}, "lowest_quartile_relative_worsening"),
        ({"low_volume_rows": 29}, "lowest_quartile_minimum_rows"),
    ],
)
def test_point_promotion_applies_every_replay_criterion(
    overrides: dict[str, float | int], expected_failure: str
) -> None:
    config = load_frozen_experiment_config(Path("configs/frozen_experiment.yaml"))
    evidence: dict[str, float | int] = {
        "challenger_mae": 0.90,
        "persistence_mae": 1.0,
        "bootstrap_lower": -0.2,
        "bootstrap_upper": -0.01,
        "challenger_bias": 0.02,
        "persistence_bias": 0.03,
        "challenger_low_volume_mae": 1.0,
        "persistence_low_volume_mae": 1.0,
        "low_volume_rows": 30,
    }
    evidence.update(overrides)

    result = assess_point_promotion(config=config, **evidence)

    assert result.promoted is False
    assert result.displayed_model == "persistence"
    assert expected_failure in result.failed_criteria


def test_point_promotion_passes_without_controlling_band_visibility() -> None:
    config = load_frozen_experiment_config(Path("configs/frozen_experiment.yaml"))

    result = assess_point_promotion(
        challenger_mae=0.90,
        persistence_mae=1.0,
        bootstrap_lower=-0.2,
        bootstrap_upper=-0.01,
        challenger_bias=-0.02,
        persistence_bias=0.03,
        challenger_low_volume_mae=1.0,
        persistence_low_volume_mae=1.0,
        low_volume_rows=30,
        config=config,
    )

    assert result.promoted is True
    assert result.displayed_model == "ridge"


def test_band_gate_uses_exact_binomial_interval_and_width() -> None:
    config = load_frozen_experiment_config(Path("configs/frozen_experiment.yaml"))

    exact_interval = clopper_pearson_interval(successes=8, trials=10, confidence_level=0.95)
    passing = assess_band_promotion(
        covered=8,
        total=10,
        challenger_mean_width=0.8,
        persistence_mean_width=1.0,
        config=config,
    )
    poor_coverage = assess_band_promotion(
        covered=2,
        total=10,
        challenger_mean_width=0.8,
        persistence_mean_width=1.0,
        config=config,
    )
    too_wide = assess_band_promotion(
        covered=8,
        total=10,
        challenger_mean_width=1.01,
        persistence_mean_width=1.0,
        config=config,
    )

    assert exact_interval == pytest.approx((0.4439045377, 0.9747892737))
    assert passing.display_band is True
    assert poor_coverage.display_band is False
    assert "exact_interval_includes_nominal_coverage" in poor_coverage.failed_criteria
    assert too_wide.display_band is False
    assert "maximum_mean_width_relative_to_persistence" in too_wide.failed_criteria


def test_frozen_config_serializes_unambiguous_activation_rules() -> None:
    config = load_frozen_experiment_config(Path("configs/frozen_experiment.yaml"))

    assert config.forecast_activation_attempted is True
    assert config.selected_ridge_alpha == 10.0
    assert config.replay_model_training_target_year_end == 2023
    assert config.band_calibration_target_year == 2024
    assert config.bootstrap_resamples == 10_000
    assert config.bootstrap_seed == 20260903
    assert config.bootstrap_percentiles == (2.5, 97.5)
    assert config.bootstrap_percentile_method == "linear"
    assert config.band_coverage_interval_method == "clopper_pearson"
    assert config.band_calibration_sample_size == 229
    assert config.band_order_statistic_rank == 184
    assert config.ridge_absolute_log_residual_radius == pytest.approx(0.3842946113686516)
    assert config.persistence_absolute_log_residual_radius == pytest.approx(0.4054651081081644)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (("forecast_activation_attempted",), "must record forecast_activation_attempted"),
        (("bootstrap", "percentile_method"), "must serialize bootstrap.percentile_method"),
    ],
)
def test_frozen_config_rejects_ambiguous_decisions_or_methods(
    tmp_path: Path, mutation: tuple[str, ...], message: str
) -> None:
    source = Path("configs/frozen_experiment.yaml")
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if len(mutation) == 1:
        raw[mutation[0]] = None
    else:
        del raw[mutation[0]][mutation[1]]
    mutated = tmp_path / "frozen_experiment.yaml"
    mutated.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(ExperimentConfigError, match=message):
        load_frozen_experiment_config(mutated)
