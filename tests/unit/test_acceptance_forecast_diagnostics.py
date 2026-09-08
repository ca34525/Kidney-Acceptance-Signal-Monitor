from __future__ import annotations

from math import log

import pytest

from kasm.acceptance_forecast.diagnostics import (
    DiagnosticError,
    error_values,
    paired_comparison,
    summarize_bands,
    summarize_predictions,
)


def _row(
    program: str,
    year: int,
    prediction: float | None,
    *,
    model: str = "ridge",
    target: float | None = 1.0,
) -> dict[str, object]:
    return {
        "program_key": program,
        "target_cohort_year": year,
        "model": model,
        "target_oar": target,
        "predicted_oar": prediction,
        "analytic_eligible": True,
        "public_forecast_eligible": True,
        "first_observed_program": False,
        "expected_acceptance_quartile": None,
    }


def test_error_units_keep_the_published_ratio_as_percentage_denominator() -> None:
    over = error_values(0.8, 1.0)
    under = error_values(1.0, 0.8)

    assert over["signed_ratio_error"] == pytest.approx(0.2)
    assert over["signed_percentage_error"] == 25.0
    assert under["signed_percentage_error"] == pytest.approx(-20.0)
    assert over["absolute_log_error"] == pytest.approx(log(1.25))
    assert error_values(0.00001, 1.0)["absolute_percentage_error"] == pytest.approx(9999900)


@pytest.mark.parametrize("value", [None, True, 0.0, -1.0, float("nan"), float("inf")])
@pytest.mark.parametrize("field", ["target", "prediction"])
def test_invalid_ratios_are_hard_errors(value: object, field: str) -> None:
    with pytest.raises(DiagnosticError, match="positive finite"):
        error_values(value if field == "target" else 1.0, value if field == "prediction" else 1.0)


def test_tolerances_include_boundaries_and_percentiles_use_linear_interpolation() -> None:
    rows = [_row(str(i), 2021, value) for i, value in enumerate((0.5, 0.75, 0.9, 1.1, 1.25, 1.5))]
    result = summarize_predictions(rows, models=("ridge",), years=(2021,))
    summary = result["by_year"][0]

    assert summary["within_10_percent_count"] == 2
    assert summary["within_25_percent_count"] == 4
    assert summary["within_50_percent_count"] == 6
    assert summary["signed_ratio_p10"] == pytest.approx(-0.375)
    assert summary["signed_ratio_p90"] == pytest.approx(0.375)
    assert summary["absolute_ratio_mean"] == pytest.approx(1.7 / 6)
    assert summary["absolute_ratio_median"] == 0.25
    assert summary["absolute_ratio_p95"] == 0.5
    assert summary["signed_ratio_min"] == -0.5
    assert summary["signed_ratio_max"] == 0.5


def test_year_balanced_means_do_not_pool_years_of_unequal_size() -> None:
    rows = [_row("A", 2021, 2.0), _row("A", 2022, 1.0), _row("B", 2022, 1.0)]
    result = summarize_predictions(rows, models=("ridge",), years=(2021, 2022))
    overall = result["year_balanced"][0]
    pooled = result["pooled_secondary"][0]

    assert overall["absolute_ratio_mean"] == 0.5
    assert overall["within_10_percent_fraction"] == 0.5
    assert "absolute_ratio_median" not in overall
    assert pooled["absolute_ratio_mean"] == pytest.approx(1 / 3)
    assert pooled["absolute_ratio_median"] == 0.0
    assert pooled["n"] == 3
    assert pooled["program_count"] == 2


def test_missing_targets_are_counted_once_and_unknown_strata_stay_visible() -> None:
    rows = [
        _row("A", 2021, 1.0),
        _row("A", 2021, 1.0, model="persistence"),
        _row("B", 2021, None, target=None),
        _row("B", 2021, None, model="persistence", target=None),
    ]
    result = summarize_predictions(
        rows,
        models=("ridge", "persistence"),
        years=(2021,),
        group_fields=("expected_acceptance_quartile",),
    )

    assert result["exclusions"]["missing_target_program_years"] == 1
    assert result["exclusions"]["eligible_program_years"] == 1
    assert all(group["group_value"] == "Unknown" for group in result["groups"])
    assert all(group["n"] == 1 for group in result["groups"])


def test_paired_wins_depend_on_the_named_scale_and_ties_use_unrounded_values() -> None:
    rows = [
        _row("A", 2021, 1.5),
        _row("A", 2021, 0.6, model="persistence"),
        _row("B", 2021, 1.0),
        _row("B", 2021, 1.0, model="persistence"),
        _row("C", 2021, 1.1),
        _row("C", 2021, 1.1000000001, model="persistence"),
    ]
    result = paired_comparison(rows, candidate="ridge", comparator="persistence", years=(2021,))
    log_summary = next(row for row in result["by_year"] if row["scale"] == "log")
    ratio_summary = next(row for row in result["by_year"] if row["scale"] == "ratio")

    assert (log_summary["wins"], log_summary["ties"], log_summary["losses"]) == (2, 1, 0)
    assert (ratio_summary["wins"], ratio_summary["ties"], ratio_summary["losses"]) == (1, 1, 1)
    assert ratio_summary["difference_max"] == pytest.approx(0.1)


@pytest.mark.parametrize(
    "change", ["missing_model", "missing_prediction", "target_mismatch", "duplicate"]
)
def test_paired_population_cannot_silently_drop_or_change_required_rows(change: str) -> None:
    rows = [_row("A", 2021, 1.0), _row("A", 2021, 1.0, model="persistence")]
    if change == "missing_model":
        rows.pop()
    elif change == "missing_prediction":
        rows[0]["predicted_oar"] = None
    elif change == "target_mismatch":
        rows[0]["target_oar"] = 2.0
    else:
        rows.append(dict(rows[0]))

    with pytest.raises(DiagnosticError):
        paired_comparison(rows, candidate="ridge", comparator="persistence", years=(2021,))


def test_bands_keep_unavailable_counts_and_include_boundary_outcomes() -> None:
    rows = [_row("A", 2021, 1.0), _row("B", 2021, 1.0), _row("C", 2021, 1.0)]
    rows[0].update(band_lower_oar=1.0, band_upper_oar=2.0)
    rows[1].update(band_lower_oar=1.1, band_upper_oar=2.0)
    rows[2].update(band_lower_oar=None, band_upper_oar=None)
    summary = summarize_bands(rows, models=("ridge",), years=(2021,))[0]

    assert summary["n"] == 3
    assert summary["band_available"] == 2
    assert summary["band_unavailable"] == 1
    assert summary["covered"] == 1
    assert summary["coverage"] == 0.5
    assert summary["mean_width_ratio"] == pytest.approx(0.95)


@pytest.mark.parametrize(("lower", "upper"), [(None, 2.0), (2.0, 1.0), (0.0, 1.0)])
def test_partial_or_invalid_bands_fail(lower: object, upper: object) -> None:
    row = _row("A", 2021, 1.0)
    row.update(band_lower_oar=lower, band_upper_oar=upper)

    with pytest.raises(DiagnosticError):
        summarize_bands([row], models=("ridge",), years=(2021,))


@pytest.mark.parametrize(
    "flag", ["analytic_eligible", "public_forecast_eligible", "first_observed_program"]
)
def test_unknown_eligibility_cannot_be_counted_as_false(flag: str) -> None:
    row = _row("A", 2021, 1.0)
    del row[flag]

    with pytest.raises(DiagnosticError, match="explicit boolean"):
        summarize_predictions([row], models=("ridge",), years=(2021,))


def test_public_population_and_band_groups_preserve_their_denominators() -> None:
    eligible = _row("A", 2021, 1.0)
    first = _row("B", 2021, 1.5)
    first.update(public_forecast_eligible=False, first_observed_program=True)
    excluded = _row("C", 2021, None)
    excluded["analytic_eligible"] = False
    for row in (eligible, first):
        row.update(band_lower_oar=1.0, band_upper_oar=1.5)
    records = [eligible, first, excluded]

    result = summarize_predictions(
        records, models=("ridge",), years=(2021,), group_fields=("public_forecast_eligible",)
    )
    bands = summarize_bands(
        records, models=("ridge",), years=(2021,), group_fields=("public_forecast_eligible",)
    )

    assert result["exclusions"]["analytic_ineligible_program_years"] == 1
    assert result["by_year"][0]["public_forecast_eligible_count"] == 1
    assert result["by_year"][0]["first_observed_program_count"] == 1
    assert {row["group_value"] for row in result["groups"]} == {"True", "False"}
    assert bands[0]["n"] == 2
    assert all(row["n"] == 1 and row["coverage"] == 1.0 for row in bands[1:])


def test_finite_values_that_overflow_percentage_errors_are_rejected_without_trimming() -> None:
    with pytest.raises(DiagnosticError, match="finite numeric range"):
        error_values(1e-300, 1e300)


def test_an_empty_required_year_is_not_dropped_from_the_primary_average() -> None:
    with pytest.raises(DiagnosticError, match="Every configured year"):
        summarize_predictions([_row("A", 2021, 1.0)], models=("ridge",), years=(2021, 2022))
