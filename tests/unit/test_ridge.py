from __future__ import annotations

from math import exp
from pathlib import Path

import pytest

from kasm.modeling.challenger import (
    assess_pre_replay_candidate,
    choose_ridge_alpha,
    fit_ridge_pipeline,
    generate_ridge_predictions,
    select_ridge_alpha,
)
from kasm.modeling.experiment import ExperimentConfig, load_experiment_config
from kasm.modeling.features import MODEL_FEATURE_COLUMNS


def _row(program_key: str, target_year: int, offset: float = 0.0) -> dict[str, object]:
    current = (target_year - 2020) / 10 + offset
    values: dict[str, object] = {
        "program_key": program_key,
        "feature_cohort_year": target_year - 1,
        "target_cohort_year": target_year,
        "current_log_overall_oar": current,
        "previous_annual_log_overall_oar": current - 0.1,
        "one_year_change_log_overall_oar": 0.1,
        "log1p_overall_expected_acceptances": 3.0 + offset,
        "log_credible_interval_width": 0.4 + offset / 10,
        "current_log_low_oar": current - 0.1,
        "current_log_medium_oar": current,
        "current_log_high_oar": current + 0.1,
        "current_log_hard_to_place_oar": current + 0.2,
        "high_offers_share": 0.4,
        "hard_to_place_offers_share": 0.1,
        "missing_previous_annual_log_overall_oar": False,
        "missing_one_year_change_log_overall_oar": False,
        "missing_current_log_low_oar": False,
        "missing_current_log_medium_oar": False,
        "missing_current_log_high_oar": False,
        "missing_current_log_hard_to_place_oar": False,
        "target_log_oar": current * 0.8 + 0.03,
        "target_oar": exp(current * 0.8 + 0.03),
        "analytic_eligible": True,
        "first_observed_program": target_year == 2018,
    }
    return values


def _rows() -> tuple[dict[str, object], ...]:
    return tuple(
        _row(program_key, target_year, offset)
        for target_year in range(2018, 2026)
        for program_key, offset in (
            ("A000:TX1", -0.2),
            ("B000:TX1", 0.0),
            ("C000:TX1", 0.2),
            ("D000:TX1", 0.4),
        )
    )


def test_preprocessing_statistics_are_fit_on_training_rows_only() -> None:
    training_rows = (
        _row("A000:TX1", 2018, -1.0),
        _row("B000:TX1", 2018, 0.0),
        _row("C000:TX1", 2018, 1.0),
    )
    held_out = _row("D000:TX1", 2021)
    held_out["log1p_overall_expected_acceptances"] = 1003.0
    config = load_experiment_config_path()

    pipeline = fit_ridge_pipeline(
        training_rows,
        feature_columns=config.feature_columns,
        target_column=config.target_column,
        alpha=1.0,
        random_seed=config.ridge_random_seed,
    )

    imputer = pipeline.named_steps["imputer"]
    expected_index = MODEL_FEATURE_COLUMNS.index("log1p_overall_expected_acceptances")
    assert imputer.statistics_[expected_index] == pytest.approx(3.0)
    assert held_out["log1p_overall_expected_acceptances"] == 1003.0


def test_ridge_pipeline_and_rolling_predictions_are_deterministic() -> None:
    rows = _rows()
    config = load_experiment_config_path()

    first_selection = select_ridge_alpha(rows, config)
    second_selection = select_ridge_alpha(rows, config)
    first_predictions = generate_ridge_predictions(rows, config, first_selection.selected_alpha)
    second_predictions = generate_ridge_predictions(rows, config, second_selection.selected_alpha)

    assert first_selection == second_selection
    assert first_predictions == second_predictions
    assert {row.target_cohort_year for row in first_predictions} == {2021, 2022, 2023, 2024}
    assert all(row.target_cohort_year != 2025 for row in first_predictions)


def test_alpha_tie_selects_more_regularized_model_within_one_percent() -> None:
    selected = choose_ridge_alpha(
        {0.01: 1.0, 0.1: 0.995, 1.0: 1.004, 10.0: 1.006},
        relative_tolerance=0.01,
    )

    assert selected == 1.0


def test_pre_replay_gate_requires_every_prespecified_condition() -> None:
    config = load_experiment_config_path()
    persistence = {2021: 1.0, 2022: 1.0, 2023: 1.0, 2024: 1.0}
    challenger = {2021: 0.90, 2022: 0.94, 2023: 0.89, 2024: 1.05}
    low_volume = {year: 1.05 for year in persistence}
    counts = {year: 30 for year in persistence}

    passing = assess_pre_replay_candidate(
        challenger_mae_by_year=challenger,
        persistence_mae_by_year=persistence,
        challenger_lowest_quartile_mae_by_year=low_volume,
        persistence_lowest_quartile_mae_by_year=persistence,
        lowest_quartile_rows_by_year=counts,
        config=config,
    )
    excessive_single_year_worsening = assess_pre_replay_candidate(
        challenger_mae_by_year={**challenger, 2024: 1.11},
        persistence_mae_by_year=persistence,
        challenger_lowest_quartile_mae_by_year=low_volume,
        persistence_lowest_quartile_mae_by_year=persistence,
        lowest_quartile_rows_by_year=counts,
        config=config,
    )
    too_few_low_volume_rows = assess_pre_replay_candidate(
        challenger_mae_by_year=challenger,
        persistence_mae_by_year=persistence,
        challenger_lowest_quartile_mae_by_year=low_volume,
        persistence_lowest_quartile_mae_by_year=persistence,
        lowest_quartile_rows_by_year={**counts, 2023: 29},
        config=config,
    )

    assert passing.passed is True
    assert passing.improved_years == 3
    assert excessive_single_year_worsening.passed is False
    assert "single_year_relative_worsening" in excessive_single_year_worsening.failed_criteria
    assert too_few_low_volume_rows.passed is False
    assert "lowest_quartile_minimum_rows" in too_few_low_volume_rows.failed_criteria


@pytest.mark.parametrize(
    ("challenger", "low_volume", "expected_failure"),
    [
        (
            {2021: 0.99, 2022: 0.99, 2023: 0.99, 2024: 1.0},
            {2021: 1.0, 2022: 1.0, 2023: 1.0, 2024: 1.0},
            "minimum_skill_over_persistence",
        ),
        (
            {2021: 0.8, 2022: 0.8, 2023: 1.0, 2024: 1.0},
            {2021: 1.0, 2022: 1.0, 2023: 1.0, 2024: 1.0},
            "minimum_improved_years",
        ),
        (
            {2021: 0.90, 2022: 0.94, 2023: 0.89, 2024: 1.05},
            {2021: 1.11, 2022: 1.11, 2023: 1.11, 2024: 1.11},
            "lowest_quartile_relative_worsening",
        ),
    ],
)
def test_pre_replay_gate_rejects_each_remaining_failed_criterion(
    challenger: dict[int, float],
    low_volume: dict[int, float],
    expected_failure: str,
) -> None:
    config = load_experiment_config_path()
    persistence = {2021: 1.0, 2022: 1.0, 2023: 1.0, 2024: 1.0}

    result = assess_pre_replay_candidate(
        challenger_mae_by_year=challenger,
        persistence_mae_by_year=persistence,
        challenger_lowest_quartile_mae_by_year=low_volume,
        persistence_lowest_quartile_mae_by_year=persistence,
        lowest_quartile_rows_by_year={year: 30 for year in persistence},
        config=config,
    )

    assert result.passed is False
    assert expected_failure in result.failed_criteria


def load_experiment_config_path() -> ExperimentConfig:
    return load_experiment_config(Path("configs/experiment.yaml"))
