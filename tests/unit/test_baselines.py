from __future__ import annotations

from math import exp

import pytest

from kasm.modeling.backtest import (
    BacktestError,
    assign_volume_quartiles,
    build_rolling_origin_folds,
    evaluate_baselines,
    generate_baseline_predictions,
)


def _row(
    program_key: str,
    target_year: int,
    *,
    current: float,
    target: float | None,
    expected_log1p: float = 4.0,
) -> dict[str, object]:
    return {
        "program_key": program_key,
        "feature_cohort_year": target_year - 1,
        "target_cohort_year": target_year,
        "current_log_overall_oar": current,
        "log1p_overall_expected_acceptances": expected_log1p,
        "target_log_oar": target,
        "target_oar": None if target is None else exp(target),
        "analytic_eligible": target is not None,
        "first_observed_program": target_year == 2018,
    }


def _fold_rows() -> tuple[dict[str, object], ...]:
    return tuple(
        _row("ABCD:TX1", year, current=year / 100, target=(year + 1) / 100)
        for year in range(2018, 2025)
    )


def test_rolling_folds_are_expanding_and_keep_target_years_whole() -> None:
    rows = (
        *_fold_rows(),
        *(
            _row("WXYZ:TX1", year, current=year / 200, target=(year + 1) / 200)
            for year in range(2018, 2025)
        ),
    )

    folds = build_rolling_origin_folds(rows)

    assert tuple(fold.evaluation_target_year for fold in folds) == (2021, 2022, 2023, 2024)
    assert folds[0].training_target_years == (2018, 2019, 2020)
    assert folds[-1].training_target_years == (2018, 2019, 2020, 2021, 2022, 2023)
    for fold in folds:
        assert {
            int(rows[index]["target_cohort_year"]) for index in fold.evaluation_row_indices
        } == {fold.evaluation_target_year}
        assert all(
            int(rows[index]["target_cohort_year"]) < fold.evaluation_target_year
            for index in fold.training_row_indices
        )


def test_misaligned_feature_and_target_year_is_rejected() -> None:
    row = _row("ABCD:TX1", 2021, current=0.1, target=0.2)
    row["feature_cohort_year"] = 2018

    with pytest.raises(BacktestError, match="adjacent calendar year"):
        build_rolling_origin_folds((row,))


def test_baseline_formulas_and_historical_mean_do_not_use_future_rows() -> None:
    rows = (
        _row("ABCD:TX1", 2019, current=-0.3, target=-0.2),
        _row("ABCD:TX1", 2020, current=-0.1, target=0.0),
        _row("ABCD:TX1", 2021, current=0.2, target=0.0),
        _row("ABCD:TX1", 2022, current=99.0, target=99.0),
    )

    predictions = generate_baseline_predictions(
        rows, evaluation_target_years=(2021,), training_target_year_start=2019
    )
    by_model = {prediction.model: prediction for prediction in predictions}

    assert by_model["neutral"].predicted_log_oar == 0.0
    assert by_model["persistence"].predicted_log_oar == 0.2
    assert by_model["historical_mean"].predicted_log_oar == pytest.approx((-0.3 - 0.1 + 0.2) / 3)
    assert by_model["persistence"].absolute_error_difference_vs_persistence == 0.0
    assert by_model["neutral"].absolute_error_difference_vs_persistence == pytest.approx(-0.2)


def test_volume_quartiles_use_within_year_rank_and_program_key_tie_break() -> None:
    rows = tuple(
        _row(
            f"{letter}000:TX1",
            2021,
            current=0.0,
            target=0.0,
            expected_log1p=1.0 if letter in {"A", "B"} else float(ord(letter)),
        )
        for letter in "ABCDEFGH"
    )

    assignments = assign_volume_quartiles(rows)

    assert assignments[("A000:TX1", 2021)] == 1
    assert assignments[("B000:TX1", 2021)] == 1
    assert assignments[("C000:TX1", 2021)] == 2
    assert assignments[("E000:TX1", 2021)] == 3
    assert assignments[("H000:TX1", 2021)] == 4


def test_primary_summary_weights_target_years_equally_not_rows() -> None:
    rows = (
        _row("A000:TX1", 2021, current=0.0, target=0.0),
        _row("B000:TX1", 2021, current=0.0, target=0.0),
        _row("C000:TX1", 2021, current=0.0, target=0.0),
        _row("D000:TX1", 2022, current=0.0, target=2.0),
    )
    predictions = generate_baseline_predictions(
        rows, evaluation_target_years=(2021, 2022), training_target_year_start=2021
    )

    metrics = evaluate_baselines(predictions)
    neutral = next(item for item in metrics["selection_summary"] if item["model"] == "neutral")

    assert neutral["unweighted_mean_yearly_mae_log_oar"] == 1.0
    assert neutral["row_pooled_mae_log_oar"] == 0.5
