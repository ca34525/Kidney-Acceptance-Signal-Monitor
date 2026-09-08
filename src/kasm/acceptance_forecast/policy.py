"""Apply the separate retrospective selection rule without changing the original gate.

Selection weighs average and large errors, differences between years and groups, and
uncertainty from resampling whole programs. Point and band decisions remain separate.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from statistics import fmean
from typing import Any

import numpy as np

from kasm.acceptance_forecast.config import ComparisonConfig
from kasm.acceptance_forecast.diagnostics import (
    DiagnosticError,
    error_values,
    paired_comparison,
    summarize_bands,
    summarize_predictions,
)
from kasm.modeling.activation import clopper_pearson_interval

Record = Mapping[str, Any]
Summary = dict[str, Any]
_SELECTION_ORDER = ("ridge", "adjusted_persistence", "ridge_recent3")
_GROUP_FIELDS = (
    "expected_acceptance_quartile",
    "earlier_oar_group",
    "predictor_missingness",
    "public_forecast_eligible",
)


def _eligible(records: Sequence[Record]) -> list[Record]:
    return [row for row in records if row["target_oar"] is not None and row["analytic_eligible"]]


def _require_common_groups(records: Sequence[Record]) -> None:
    assignments: dict[tuple[str, int], tuple[object, ...]] = {}
    for row in records:
        identity = row["program_key"], row["target_cohort_year"]
        groups = tuple(row.get(field) for field in _GROUP_FIELDS)
        if identity in assignments and assignments[identity] != groups:
            raise DiagnosticError(
                "Each program-year must have the same earlier group across models."
            )
        assignments[identity] = groups


def _paired_differences(
    records: Sequence[Record],
    candidate: str,
    comparator: str,
) -> list[Summary]:
    indexed = {
        (row["program_key"], row["target_cohort_year"], row["model"]): row
        for row in _eligible(records)
    }
    result = []
    for (program, year, model), row in sorted(indexed.items()):
        if model == candidate:
            other = indexed[(program, year, comparator)]
            difference = (
                error_values(row["target_oar"], row["predicted_oar"])["absolute_log_error"]
                - error_values(other["target_oar"], other["predicted_oar"])["absolute_log_error"]
            )
            result.append({"program_key": program, "target_year": year, "difference": difference})
    return result


def program_clustered_bootstrap(
    records: Sequence[Record],
    *,
    candidate: str,
    comparator: str,
    years: Sequence[int],
    resamples: int,
    seed: int,
) -> Summary:
    """Resample entire paired program histories and recompute the equal-year mean.

    The fixed number is attempted draws. A draw without observations in a required year
    is skipped and counted, so an absent year never receives zero error or disappears.
    """
    if isinstance(resamples, bool) or not isinstance(resamples, int) or resamples <= 0:
        raise DiagnosticError("Bootstrap resamples must be a positive integer.")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise DiagnosticError("Bootstrap seed must be a nonnegative integer.")
    comparison = paired_comparison(records, candidate=candidate, comparator=comparator, years=years)
    differences = _paired_differences(records, candidate, comparator)
    programs = sorted({row["program_key"] for row in differences})
    program_index = {program: index for index, program in enumerate(programs)}
    year_index = {year: index for index, year in enumerate(years)}
    values = np.zeros((len(programs), len(years)), dtype=np.float64)
    present = np.zeros_like(values)
    for row in differences:
        position = program_index[row["program_key"]], year_index[row["target_year"]]
        values[position] = row["difference"]
        present[position] = 1
    rng = np.random.default_rng(seed)
    retained: list[float] = []
    skipped = 0
    # Batches bound temporary arrays while keeping the same deterministic draw sequence.
    for start in range(0, resamples, 256):
        sampled = rng.integers(0, len(programs), size=(min(256, resamples - start), len(programs)))
        totals = values[sampled].sum(axis=1)
        counts = present[sampled].sum(axis=1)
        valid = (counts > 0).all(axis=1)
        skipped += int((~valid).sum())
        retained.extend((totals[valid] / counts[valid]).mean(axis=1).tolist())
    if not retained:
        raise DiagnosticError(
            "Every bootstrap draw omitted a required year; no interval is defined."
        )
    lower, upper = np.percentile(retained, [2.5, 97.5], method="linear")
    observed = next(
        row["difference_mean"] for row in comparison["year_balanced"] if row["scale"] == "log"
    )
    return {
        "observed_mean_difference": observed,
        "lower": float(lower),
        "upper": float(upper),
        "attempted_resamples": resamples,
        "retained_resamples": len(retained),
        "skipped_missing_year": skipped,
        "program_count": len(programs),
        "years": list(years),
        "seed": seed,
        "percentiles": [2.5, 97.5],
        "percentile_method": "linear",
        "resampling_unit": "whole_program",
        "interpretation": (
            "Descriptive variation across observed programs, not new years or model selection."
        ),
    }


def _group_checks(
    model: str,
    summaries: Sequence[Summary],
    policy: Mapping[str, Any],
) -> list[Summary]:
    persistence = {
        (row["target_year"], row["group_field"], row["group_value"]): row
        for row in summaries
        if row["model"] == "persistence"
    }
    results = []
    for row in summaries:
        if row["model"] != model:
            continue
        identity = row["target_year"], row["group_field"], row["group_value"]
        reference = persistence.get(identity)
        if reference is None or row["n"] != reference["n"]:
            raise DiagnosticError("Paired methods must retain identical group-year populations.")
        public_ineligible = (
            row["group_field"] == "public_forecast_eligible" and row["group_value"] != "True"
        )
        applied = row["n"] >= policy["minimum_group_n"] and not public_ineligible
        passed = row["absolute_log_mean"] <= reference["absolute_log_mean"] * (
            1 + policy["maximum_group_mae_worsening"]
        )
        results.append(
            {
                "target_year": identity[0],
                "group_field": identity[1],
                "group_value": identity[2],
                "n": row["n"],
                "mae_log": row["absolute_log_mean"],
                "persistence_mae_log": reference["absolute_log_mean"],
                "gate_applied": applied,
                "passed": passed if applied else None,
                "reason": "not_deployment_eligible"
                if public_ineligible
                else "sufficient_size"
                if applied
                else "fewer_than_minimum_programs",
            }
        )
    return results


def _band_checks(
    model: str,
    band_summaries: Sequence[Summary],
    years: Sequence[int],
    policy: Mapping[str, Any],
) -> Summary:
    cells: list[Summary] = []
    failed: list[str] = []
    for row in band_summaries:
        if row["model"] != model:
            continue
        public_ineligible = (
            row.get("group_field") == "public_forecast_eligible" and row["group_value"] != "True"
        )
        applied = row["n"] >= policy["minimum_group_n"] and not public_ineligible
        bounds = (
            clopper_pearson_interval(
                successes=row["covered"],
                trials=row["band_available"],
                confidence_level=policy["band_confidence"],
            )
            if row["band_available"]
            else None
        )
        passed = bounds is not None and bounds[0] <= policy["band_nominal_coverage"] <= bounds[1]
        if "group_field" not in row and (row["band_unavailable"] or not applied):
            failed.append("band_availability")
        if applied and not passed:
            failed.append("band_coverage")
        cells.append(
            {
                **row,
                "exact_interval": list(bounds) if bounds else None,
                "gate_applied": applied,
                "passed": passed if applied else None,
            }
        )
    yearly = {row["target_year"]: row for row in cells if "group_field" not in row}
    reference = {
        row["target_year"]: row
        for row in band_summaries
        if row["model"] == "persistence" and "group_field" not in row
    }
    widths = [yearly[year]["mean_width_ratio"] for year in years]
    reference_widths = [reference[year]["mean_width_ratio"] for year in years]
    complete = all(value is not None for value in [*widths, *reference_widths])
    mean_width = fmean(widths) if complete else None
    persistence_width = fmean(reference_widths) if complete else None
    if not complete or mean_width > persistence_width * policy["maximum_band_width_ratio"]:
        failed.append("band_width")
    return {
        "band_passed": not failed,
        "failed_band_criteria": sorted(set(failed)),
        "band_mean_width_ratio": mean_width,
        "persistence_band_mean_width_ratio": persistence_width,
        "band_cells": cells,
    }


def _point_checks(
    model: str,
    summaries: Summary,
    records: Sequence[Record],
    config: ComparisonConfig,
) -> Summary:
    policy = config.policy
    overall = {row["model"]: row for row in summaries["year_balanced"]}
    yearly = {(row["model"], row["target_year"]): row for row in summaries["by_year"]}
    candidate, persistence, history = (
        overall[name] for name in (model, "persistence", "historical_mean")
    )
    candidate_years = [yearly[(model, year)] for year in config.years]
    persistence_years = [yearly[("persistence", year)] for year in config.years]
    bias = abs(candidate["signed_log_mean"])
    improved = sum(
        row["absolute_log_mean"] < reference["absolute_log_mean"]
        for row, reference in zip(candidate_years, persistence_years, strict=True)
    )
    tail = fmean(row["absolute_log_p90"] for row in candidate_years)
    reference_tail = fmean(row["absolute_log_p90"] for row in persistence_years)
    group_checks = _group_checks(model, summaries["groups"], policy)
    differences = _paired_differences(records, model, "persistence")
    large_worsening = fmean(
        fmean(
            row["difference"] > policy["large_worsening_log_threshold"]
            for row in differences
            if row["target_year"] == year
        )
        for year in config.years
    )
    bootstrap = program_clustered_bootstrap(
        records,
        candidate=model,
        comparator="persistence",
        years=config.years,
        resamples=config.bootstrap_resamples,
        seed=config.bootstrap_seed,
    )
    checks = {
        "primary_accuracy": candidate["absolute_log_mean"]
        <= persistence["absolute_log_mean"] * (1 - policy["minimum_log_mae_improvement"]),
        "historical_mean_accuracy": candidate["absolute_log_mean"] <= history["absolute_log_mean"],
        "ratio_accuracy": candidate["absolute_ratio_mean"] <= persistence["absolute_ratio_mean"],
        "paired_uncertainty": bootstrap["upper"] < 0,
        "improved_year_count": improved >= policy["minimum_improved_years"],
        "worst_year_accuracy": all(
            row["absolute_log_mean"]
            <= reference["absolute_log_mean"] * (1 + policy["maximum_year_mae_worsening"])
            for row, reference in zip(candidate_years, persistence_years, strict=True)
        ),
        "absolute_log_bias": bias <= policy["maximum_absolute_log_bias"],
        "year_absolute_log_bias": all(
            abs(row["signed_log_mean"]) <= policy["maximum_year_absolute_log_bias"]
            for row in candidate_years
        ),
        "large_error_tail": tail <= reference_tail * policy["maximum_tail_ratio"],
        "group_accuracy": all(row["passed"] for row in group_checks if row["gate_applied"]),
        "large_paired_worsening": large_worsening <= policy["maximum_large_worsening_fraction"],
    }
    return {
        "mae_log": candidate["absolute_log_mean"],
        "mae_ratio": candidate["absolute_ratio_mean"],
        "mean_signed_log_error": candidate["signed_log_mean"],
        "absolute_log_bias": bias,
        "relative_log_mae_improvement": 1
        - candidate["absolute_log_mean"] / persistence["absolute_log_mean"]
        if persistence["absolute_log_mean"]
        else None,
        "improved_years": improved,
        "mean_yearly_absolute_log_p90": tail,
        "persistence_mean_yearly_absolute_log_p90": reference_tail,
        "large_paired_worsening_fraction": large_worsening,
        "point_checks": checks,
        "point_passed": all(checks.values()),
        "failed_point_criteria": [key for key, passed in checks.items() if not passed],
        "group_cells": group_checks,
        "bootstrap": bootstrap,
    }


def evaluate_policy(records: Sequence[Record], config: ComparisonConfig) -> Summary:
    """Apply all fixed gates, report every model, and recommend a point and band separately."""
    summaries = summarize_predictions(
        records, models=config.models, years=config.years, group_fields=_GROUP_FIELDS
    )
    _require_common_groups(records)
    band_summaries = summarize_bands(
        records, models=config.models, years=config.years, group_fields=_GROUP_FIELDS
    )
    results: dict[str, Summary] = {}
    for model in config.models:
        if model in _SELECTION_ORDER:
            result = _point_checks(model, summaries, records, config)
        else:
            overall = next(row for row in summaries["year_balanced"] if row["model"] == model)
            result = {
                "mae_log": overall["absolute_log_mean"],
                "mae_ratio": overall["absolute_ratio_mean"],
                "mean_signed_log_error": overall["signed_log_mean"],
                "absolute_log_bias": abs(overall["signed_log_mean"]),
                "point_passed": False,
                "failed_point_criteria": [],
                "reference_only": True,
            }
        result.update(_band_checks(model, band_summaries, config.years, config.policy))
        results[model] = result
    passing = [model for model in _SELECTION_ORDER if results[model]["point_passed"]]
    selected = (
        min(passing, key=lambda model: results[model]["mae_log"]) if passing else "persistence"
    )
    return {
        "thresholds": dict(config.policy),
        "result_by_model": results,
        "selected_model": selected,
        "point_selected": bool(passing),
        "band_selected": bool(passing) and results[selected]["band_passed"],
        "selection_order": list(_SELECTION_ORDER),
        "bootstrap": {model: results[model]["bootstrap"] for model in _SELECTION_ORDER},
        "population_exclusions": summaries["exclusions"],
        "decision_scope": (
            "Retrospective recommendation; a separate trusted release is required for display."
        ),
    }
