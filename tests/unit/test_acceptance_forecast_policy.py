from __future__ import annotations

from math import exp
from types import SimpleNamespace
from typing import Any

import pytest

from kasm.acceptance_forecast.config import POLICY_DEFAULTS
from kasm.acceptance_forecast.diagnostics import DiagnosticError
from kasm.acceptance_forecast.policy import evaluate_policy, program_clustered_bootstrap

YEARS = (2021, 2022, 2023, 2024, 2025)
MODELS = ("persistence", "historical_mean", "ridge", "ridge_recent3", "adjusted_persistence")


def _config() -> Any:
    return SimpleNamespace(
        years=YEARS,
        models=MODELS,
        bootstrap_resamples=250,
        bootstrap_seed=20260908,
        policy=dict(POLICY_DEFAULTS),
    )


def _record(program: int, year: int, model: str, signed_error: float) -> dict[str, object]:
    return {
        "program_key": f"P{program:03d}:TX1",
        "target_cohort_year": year,
        "model": model,
        "target_oar": 1.0,
        "predicted_oar": exp(signed_error),
        "analytic_eligible": True,
        "public_forecast_eligible": True,
        "first_observed_program": False,
        "expected_acceptance_quartile": 1,
        "earlier_oar_group": "0.5-1",
        "predictor_missingness": "complete",
        "band_lower_oar": 0.5 if program % 5 else 1.1,
        "band_upper_oar": 1.5 if program % 5 else 2.1,
    }


def _records() -> list[dict[str, object]]:
    errors = {
        "persistence": 0.4,
        "historical_mean": 0.35,
        "ridge": 0.2,
        "ridge_recent3": 0.25,
        "adjusted_persistence": 0.28,
    }
    return [
        _record(
            program,
            year,
            model,
            (-1 if program % 2 else 1) * error + (0.01 if model == "ridge" else 0),
        )
        for year in YEARS
        for program in range(40)
        for model, error in errors.items()
    ]


def test_new_rule_can_select_ridge_despite_higher_absolute_bias_than_persistence() -> None:
    result = evaluate_policy(_records(), _config())
    ridge = result["result_by_model"]["ridge"]
    persistence = result["result_by_model"]["persistence"]

    assert ridge["absolute_log_bias"] > persistence["absolute_log_bias"]
    assert ridge["absolute_log_bias"] == pytest.approx(0.01)
    assert ridge["point_passed"]
    assert result["selected_model"] == "ridge"
    assert result["point_selected"]
    assert result["band_selected"]
    assert set(result["result_by_model"]) == set(MODELS)


@pytest.mark.parametrize(
    ("change", "criterion"),
    [
        ("accuracy", "primary_accuracy"),
        ("bias", "absolute_log_bias"),
        ("year", "worst_year_accuracy"),
        ("tail", "large_error_tail"),
        ("group", "group_accuracy"),
    ],
)
def test_unfavorable_accuracy_bias_year_tail_and_group_results_are_retained(
    change: str,
    criterion: str,
) -> None:
    records = _records()
    for row in records:
        if row["model"] != "ridge":
            continue
        program = int(str(row["program_key"])[1:4])
        sign = -1 if program % 2 else 1
        if change == "accuracy":
            row["predicted_oar"] = exp(sign * 0.5)
        elif change == "bias":
            row["predicted_oar"] = exp(0.2)
        elif change == "year" and row["target_cohort_year"] == 2025:
            row["predicted_oar"] = exp(sign * 0.5)
        elif change == "tail":
            row["predicted_oar"] = exp(sign * (0.5 if program < 8 else 0.05))
        elif change == "group":
            row["predicted_oar"] = exp(sign * (0.45 if program < 30 else 0.01))
    if change == "group":
        for row in records:
            row["expected_acceptance_quartile"] = 1 if int(str(row["program_key"])[1:4]) < 30 else 2

    ridge = evaluate_policy(records, _config())["result_by_model"]["ridge"]

    assert not ridge["point_passed"]
    assert criterion in ridge["failed_point_criteria"]


def test_all_failed_candidates_retain_persistence_and_suppress_new_band_selection() -> None:
    records = _records()
    for row in records:
        if row["model"] in ("ridge", "ridge_recent3", "adjusted_persistence"):
            row["predicted_oar"] = exp(0.5)

    result = evaluate_policy(records, _config())

    assert result["selected_model"] == "persistence"
    assert not result["point_selected"]
    assert not result["band_selected"]


@pytest.mark.parametrize("change", ["overcoverage", "undercoverage", "width", "missing"])
def test_point_selection_does_not_automatically_authorize_its_band(change: str) -> None:
    records = _records()
    for row in records:
        if row["model"] != "ridge":
            continue
        if change == "overcoverage":
            row.update(band_lower_oar=0.5, band_upper_oar=1.5)
        elif change == "undercoverage":
            row.update(band_lower_oar=1.1, band_upper_oar=1.5)
        elif change == "width":
            row["band_upper_oar"] = float(row["band_upper_oar"]) + 1.0
        else:
            row.update(band_lower_oar=None, band_upper_oar=None)

    result = evaluate_policy(records, _config())

    assert result["selected_model"] == "ridge"
    assert result["point_selected"]
    assert not result["band_selected"]
    assert result["result_by_model"]["ridge"]["failed_band_criteria"]


def test_bootstrap_resamples_whole_program_histories_and_is_deterministic() -> None:
    records = [
        _record(program, year, model, value)
        for program in range(2)
        for year in (2021, 2022)
        for model, value in (
            ("persistence", 0.4),
            ("ridge", 0.2 if (program == 0) == (year == 2021) else 0.6),
        )
    ]
    settings = {
        "candidate": "ridge",
        "comparator": "persistence",
        "years": (2021, 2022),
        "resamples": 1000,
        "seed": 123,
    }

    result = program_clustered_bootstrap(records, **settings)

    assert result == program_clustered_bootstrap(list(reversed(records)), **settings)
    # Every whole program has cancelling yearly differences; individual-row draws would not.
    assert result["lower"] == pytest.approx(0.0, abs=1e-15)
    assert result["upper"] == pytest.approx(0.0, abs=1e-15)
    assert result["program_count"] == 2
    assert result["retained_resamples"] == 1000
    assert result["skipped_missing_year"] == 0


def test_bootstrap_recomputes_year_balanced_means_and_records_missing_year_draws() -> None:
    records = [
        _record(program, year, model, value)
        for program, year, candidate in ((0, 2021, 0.2), (1, 2022, 0.6), (2, 2022, 0.6))
        for model, value in (("ridge", candidate), ("persistence", 0.4))
    ]
    result = program_clustered_bootstrap(
        records,
        candidate="ridge",
        comparator="persistence",
        years=(2021, 2022),
        resamples=1000,
        seed=123,
    )

    assert result["observed_mean_difference"] == pytest.approx(0.0, abs=1e-15)
    assert result["lower"] == pytest.approx(0.0, abs=1e-15)
    assert result["upper"] == pytest.approx(0.0, abs=1e-15)
    assert 0 < result["skipped_missing_year"] < 1000
    assert result["retained_resamples"] + result["skipped_missing_year"] == 1000


def test_exact_candidate_ties_follow_the_fixed_method_order() -> None:
    records = _records()
    for row in records:
        if row["model"] in ("ridge", "ridge_recent3", "adjusted_persistence"):
            program = int(str(row["program_key"])[1:4])
            row["predicted_oar"] = exp((-1 if program % 2 else 1) * 0.2)

    assert evaluate_policy(records, _config())["selected_model"] == "ridge"


def test_sparse_cells_remain_reported_without_becoming_unsupported_group_gates() -> None:
    records = _records()
    for row in records:
        program = int(str(row["program_key"])[1:4])
        row["expected_acceptance_quartile"] = 1 if program < 2 else 2
        if row["model"] == "ridge":
            row["predicted_oar"] = exp((-1 if program % 2 else 1) * (0.8 if program < 2 else 0.2))

    result = evaluate_policy(records, _config())
    small_cells = [
        row for row in result["result_by_model"]["ridge"]["group_cells"] if row["n"] == 2
    ]

    assert result["selected_model"] == "ridge"
    assert len(small_cells) == 5
    assert all(not row["gate_applied"] and row["passed"] is None for row in small_cells)


def test_equal_sized_groups_cannot_hide_different_program_membership_between_models() -> None:
    records = _records()
    for row in records:
        program = int(str(row["program_key"])[1:4])
        group = 1 if program < 20 else 2
        row["expected_acceptance_quartile"] = 3 - group if row["model"] == "ridge" else group

    with pytest.raises(DiagnosticError, match="same earlier group"):
        evaluate_policy(records, _config())


@pytest.mark.parametrize(("resamples", "seed"), [(0, 1), (True, 1), (10, -1), (10, True)])
def test_invalid_bootstrap_settings_fail(resamples: Any, seed: Any) -> None:
    with pytest.raises(DiagnosticError):
        program_clustered_bootstrap(
            _records(),
            candidate="ridge",
            comparator="persistence",
            years=YEARS,
            resamples=resamples,
            seed=seed,
        )
