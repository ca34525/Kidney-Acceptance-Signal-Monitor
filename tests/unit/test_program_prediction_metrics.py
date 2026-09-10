"""Small program histories expose the denominators behind sprint comparisons."""

from __future__ import annotations

import math
from typing import Any

import pytest

from kasm.program_prediction.metrics import (
    PredictionMetricError,
    bootstrap_decision_difference,
    bootstrap_error_difference,
    freeze_comparators,
    review_budget,
    summarize,
)


def row(
    program: str,
    year: int,
    observed: float | None,
    predicted: float | None,
    *,
    model: str = "ridge_history",
    target: str = "registrations",
    latest: float = 10,
    previous: float | None = 9,
    eligible: bool = True,
) -> dict[str, Any]:
    return {
        "program_key": f"{program}:TX1",
        "target": target,
        "target_year": year,
        "origin_release": str(year),
        "origin_eligible": eligible,
        "eligible": eligible,
        "observed": observed,
        "latest": latest,
        "previous": previous,
        "last_change": None if previous is None else latest - previous,
        "earlier_list_size": 100,
        "model": model,
        "prediction": predicted,
        "status": "ok" if predicted is not None else "fit_failed",
    }


def test_summary_gives_years_equal_weight_and_preserves_unknown_outcomes() -> None:
    data = [
        row("A", 2022, 20, 15),
        row("B", 2022, 30, 30),
        row("C", 2022, None, 1),
        row("A", 2023, 50, 30),
    ]
    result = summarize(data)
    summary = result["summary_metrics"][0]
    assert summary["mae"] == 11.25
    assert summary["n_eligible"] == 4
    assert summary["n_observed"] == 3
    assert summary["n_missing_outcome"] == 1
    assert summary["forecast_coverage"] == 1
    assert result["period_metrics"][0]["signed_error"] == -2.5


def test_zero_count_is_valid_and_oar_scores_log_primary_plus_ratio() -> None:
    counts = summarize([row("A", 2022, 0, 2)])
    assert counts["period_metrics"][0]["mae"] == 2
    oar = summarize([row("A", 2022, 2, 1, target="overall_oar", latest=1)])
    assert oar["period_metrics"][0]["mae"] == pytest.approx(math.log(2))
    assert oar["period_metrics"][0]["ratio_mae"] == 1


def test_paired_errors_use_common_rows_but_do_not_hide_failures() -> None:
    data = [
        row("A", 2022, 20, 10),
        row("B", 2022, 100, None),
        row("A", 2022, 20, 0, model="persistence"),
        row("B", 2022, 100, 0, model="persistence"),
    ]
    comparison = summarize(data)["paired_comparisons"][0]
    assert comparison["n_paired"] == 1
    assert comparison["candidate_mae"] == 10
    assert comparison["comparator_mae"] == 20
    assert comparison["complete_forecast_coverage"] is False
    assert comparison["candidate_forecast_coverage"] == 0.5


def test_missing_model_rows_or_disagreeing_truth_raise() -> None:
    data = [row("A", 2022, 20, 10), row("A", 2022, 20, 0, model="persistence")]
    with pytest.raises(PredictionMetricError, match="same origin"):
        summarize([*data, row("B", 2022, 20, 10)])
    data[-1]["observed"] = 50
    with pytest.raises(PredictionMetricError, match="evidence disagrees"):
        summarize(data)


def test_freeze_uses_discovery_only_and_rejects_partial_success() -> None:
    data = [
        row("A", year, 20, value, model=model)
        for year in (2021, 2022, 2023)
        for model, value in (("persistence", 10), ("recent_mean", 15), ("damped_trend", 20))
    ]
    data[-1]["prediction"] = None
    data[-1]["status"] = "fit_failed"
    assert freeze_comparators(data) == {"registrations": "recent_mean"}
    assert any(
        summary["period_set"] == "without_2021" for summary in summarize(data)["summary_metrics"]
    )
    with pytest.raises(PredictionMetricError, match="discovery"):
        freeze_comparators([*data, row("A", 2024, 20, 15, model="recent_mean")])


def test_queue_is_selected_before_unknown_outcomes_and_never_refilled() -> None:
    data = [
        row("A", 2024, None, 100),
        row("B", 2024, 20, 30),
        row("C", 2024, 5, 20),
        row("INELIGIBLE", 2024, 1000, 1000, eligible=False),
    ]
    result = review_budget(data, target="registrations", model="ridge_history", budgets=(1, 10))
    small = next(
        metric
        for metric in result["metrics"]
        if metric["method"] == "ridge_history" and metric["budget"] == 1
    )
    assert small["n_universe"] == 3
    assert small["n_selected_observed"] == 0
    assert small["captured_share"] == 0
    assert small["selected_precision"] is None
    assert small["missed_observed_change"] == 10
    selected = [
        item["program_key"]
        for item in result["selections"]
        if item["method"] == "ridge_history" and item["budget"] == 1 and item["selected"]
    ]
    assert selected == ["A:TX1"]
    random = next(
        metric
        for metric in result["metrics"]
        if metric["method"] == "random_expectation" and metric["budget"] == 1
    )
    assert random["captured_share"] == pytest.approx(1 / 3)
    large = next(
        metric
        for metric in result["metrics"]
        if metric["method"] == "ridge_history" and metric["budget"] == 10
    )
    assert large["effective_budget"] == 3
    assert large["n_false_alarms"] == 1


def test_zero_change_and_stable_ties_are_explicit() -> None:
    data = [row(str(i), 2024, 10, 10) for i in range(8)]
    forward = review_budget(data, target="registrations", model="ridge_history", budgets=(3,))
    backward = review_budget(
        data[::-1], target="registrations", model="ridge_history", budgets=(3,)
    )
    assert forward == backward
    metric = forward["metrics"][0]
    assert metric["all_scores_zero"] is True
    assert metric["n_tied_at_cutoff"] == 8
    assert metric["captured_share"] is None
    assert metric["n_false_alarms"] == 3


def test_failed_forecast_does_not_shrink_or_partially_rank_universe() -> None:
    data = [row("A", 2024, 20, 30), row("B", 2024, 50, None)]
    result = review_budget(data, target="registrations", model="ridge_history", budgets=(1,))
    model = result["metrics"][0]
    assert model["n_universe"] == 2
    assert model["forecast_coverage"] == 0.5
    assert model["status"] == "incomplete_forecast_coverage"
    assert model["captured_share"] is None
    assert all(
        item["selected"] is None
        for item in result["selections"]
        if item["method"] == "ridge_history"
    )
    assert (
        next(item for item in result["metrics"] if item["method"] == "latest_level")["n_universe"]
        == 2
    )


def test_decline_scores_use_log_oar_and_count_differences() -> None:
    data = [
        row("A", 2024, 1, 1, target="overall_oar", latest=2),
        row("B", 2024, 3, 3, target="overall_oar", latest=4),
    ]
    result = review_budget(data, target="overall_oar", model="ridge_history", budgets=(1,))
    metric = result["metrics"][0]
    assert metric["captured_share"] == pytest.approx(math.log(2) / math.log(8 / 3))
    assert metric["selected_precision"] == 1


def test_error_bootstrap_keeps_each_programs_years_together() -> None:
    data = []
    for program, signs in (("A", (1, -1)), ("B", (-1, 1))):
        for year, sign in zip((2022, 2023), signs, strict=True):
            data.extend(
                [
                    row(program, year, 0, 10 + sign * 5),
                    row(program, year, 0, 10, model="persistence"),
                ]
            )
    result = bootstrap_error_difference(
        data,
        target="registrations",
        candidate="ridge_history",
        comparator="persistence",
        resamples=100,
        seed=42,
    )
    assert result["point_estimate"] == 0
    assert result["lower"] == result["upper"] == 0
    assert result["resampling_unit"] == "whole_program"


def test_simple_shortlist_can_equal_its_frozen_forecast_comparator() -> None:
    result = bootstrap_error_difference(
        [row("A", 2023, 20, 10, model="persistence")],
        target="registrations",
        candidate="persistence",
        comparator="persistence",
        resamples=10,
    )
    assert result["point_estimate"] == result["lower"] == result["upper"] == 0
    assert result["complete_forecast_coverage"] is True
    assert result["candidate_forecast_coverage"] == 1


def test_unknown_queue_comparator_is_an_actionable_error() -> None:
    with pytest.raises(PredictionMetricError, match="comparator"):
        review_budget(
            [row("A", 2024, 20, 10)],
            target="registrations",
            model="ridge_history",
            comparator="missing_baseline",
        )


def test_decision_bootstrap_compares_saved_flags_on_same_universe() -> None:
    data = [row("A", year, 30, 30, previous=10) for year in (2024, 2025)] + [
        row("B", year, 20, 20, previous=0) for year in (2024, 2025)
    ]
    selections = review_budget(
        data,
        target="registrations",
        model="ridge_history",
        budgets=(1,),
    )["selections"]
    result = bootstrap_decision_difference(
        selections,
        target="registrations",
        candidate="ridge_history",
        comparator="last_change",
        budget=1,
        resamples=100,
        seed=42,
    )
    assert result["point_estimate"] == pytest.approx(1 / 3)
    assert result["queue_resampling"] == "fixed_historical_selection_flags"
    assert result["retained_resamples"] == 100
    with pytest.raises(PredictionMetricError, match="same origin"):
        bootstrap_decision_difference(
            selections[:-1],
            target="registrations",
            candidate="ridge_history",
            comparator="latest_level",
            budget=1,
            resamples=10,
        )


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -1])
def test_invalid_report_or_prediction_does_not_silently_enter_metrics(invalid: float) -> None:
    with pytest.raises(PredictionMetricError, match="finite|nonnegative"):
        summarize([row("A", 2024, 1, invalid)])
