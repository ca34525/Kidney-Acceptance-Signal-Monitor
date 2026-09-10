"""Compare forecast errors and fixed review queues for the exploratory sprint.

Each row represents one program at one public-report origin. Unknown later outcomes
stay in the review universe, and each target year gets the same summary weight.
Review resampling describes the saved historical queues; it neither selects new
queues nor estimates intervention benefit.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from statistics import fmean
from typing import Any

import numpy as np

Record = Mapping[str, Any]
Result = dict[str, Any]
Key = tuple[str, int, str]
BASELINES = ("persistence", "recent_mean", "damped_trend", "adjusted_persistence")
DEFAULT_SEED = 20260909
_TARGETS = {"registrations", "ddkt_removals", "ldkt_removals", "ending_list", "overall_oar"}


class PredictionMetricError(ValueError):
    """The supplied rows cannot support the specified comparison."""


def _number(value: object, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise PredictionMetricError(f"{field} must be a finite number or null.")
    return float(value)


def _value(row: Record, field: str) -> float | None:
    return _number(row.get(field), field)


def _eligible(row: Record) -> bool:
    result = row.get("origin_eligible", row.get("eligible"))
    if not isinstance(result, bool):
        raise PredictionMetricError("Each prediction needs boolean origin eligibility.")
    return result


def _key(row: Record) -> Key:
    target, year, program = row.get("target"), row.get("target_year"), row.get("program_key")
    if target not in _TARGETS or isinstance(year, bool) or not isinstance(year, int):
        raise PredictionMetricError("Prediction target and target_year are invalid.")
    if not isinstance(program, str) or not program or ":" not in program:
        raise PredictionMetricError("program_key must preserve the composite program identity.")
    return target, year, program


def _scale(value: float, target: str) -> float:
    return math.log(value) if target == "overall_oar" else value


def _valid_outcome(row: Record) -> bool:
    value = _value(row, "observed")
    return value is not None and (row["target"] != "overall_oar" or value > 0)


def _valid_prediction(row: Record) -> bool:
    value = _value(row, "prediction")
    return (
        row.get("status") == "ok"
        and value is not None
        and (row["target"] != "overall_oar" or value > 0)
    )


def _validate_values(row: Record) -> None:
    for field in ("observed", "latest", "previous", "prediction", "earlier_list_size"):
        value = _value(row, field)
        if value is not None and value < 0:
            raise PredictionMetricError(f"{field} must be nonnegative; missing values stay null.")
    latest = _value(row, "latest")
    if _eligible(row) and (latest is None or (row["target"] == "overall_oar" and latest <= 0)):
        raise PredictionMetricError("Origin-eligible programs need a valid latest target value.")
    if row.get("status") == "ok" and not _valid_prediction(row):
        raise PredictionMetricError("An ok forecast needs a finite valid prediction.")
    if row.get("status") != "ok" and _value(row, "prediction") is not None:
        raise PredictionMetricError("A failed or excluded forecast must keep prediction null.")


def _validated(predictions: Sequence[Record]) -> dict[tuple[Key, str], Record]:
    if not predictions:
        raise PredictionMetricError("Prediction comparisons require rows.")
    indexed: dict[tuple[Key, str], Record] = {}
    evidence: dict[Key, tuple[Any, ...]] = {}
    universes: dict[str, dict[str, set[Key]]] = defaultdict(lambda: defaultdict(set))
    for row in predictions:
        key = _key(row)
        model = row.get("model")
        if not isinstance(model, str) or not model:
            raise PredictionMetricError("Each prediction needs a model name.")
        if (key, model) in indexed:
            raise PredictionMetricError(f"Duplicate program/origin/model row: {key}, {model}.")
        _validate_values(row)
        fixed = tuple(
            row.get(field)
            for field in (
                "observed",
                "latest",
                "previous",
                "last_change",
                "earlier_list_size",
                "origin_release",
            )
        ) + (_eligible(row),)
        if key in evidence and evidence[key] != fixed:
            raise PredictionMetricError(
                f"Origin or outcome evidence disagrees across models: {key}."
            )
        evidence[key] = fixed
        indexed[key, model] = row
        universes[key[0]][model].add(key)
    for target, models in universes.items():
        expected = set.union(*models.values())
        if any(keys != expected for keys in models.values()):
            raise PredictionMetricError(
                f"All {target} models must retain the same origin rows, including failed forecasts."
            )
    return indexed


def _errors(row: Record) -> tuple[float, float, float, float]:
    observed, prediction, latest = (
        float(row[field]) for field in ("observed", "prediction", "latest")
    )
    signed = _scale(prediction, row["target"]) - _scale(observed, row["target"])
    agreement = float(np.sign(prediction - latest) == np.sign(observed - latest))
    return abs(signed), signed, abs(prediction - observed), agreement


def _mean_or_none(values: Sequence[float | None]) -> float | None:
    reported = [value for value in values if value is not None]
    return fmean(reported) if reported and len(reported) == len(values) else None


def _period(rows: Sequence[Record]) -> Result:
    eligible = [row for row in rows if _eligible(row)]
    observed = [row for row in eligible if _valid_outcome(row)]
    forecast = [row for row in eligible if _valid_prediction(row)]
    errors = [_errors(row) for row in observed if _valid_prediction(row)]
    target = rows[0]["target"]
    return {
        "target": target,
        "target_year": rows[0]["target_year"],
        "model": rows[0]["model"],
        "primary_units": "log_oar"
        if target == "overall_oar"
        else ("registrations" if target == "ending_list" else "events"),
        "n_eligible": len(eligible),
        "n_ineligible": len(rows) - len(eligible),
        "n_observed": len(observed),
        "n_missing_outcome": sum(row.get("observed") is None for row in eligible),
        "n_invalid_outcome": sum(row.get("observed") is not None for row in eligible)
        - len(observed),
        "n_forecast": len(forecast),
        "n_failure": len(eligible) - len(forecast),
        "n_scored": len(errors),
        "forecast_coverage": len(forecast) / len(eligible) if eligible else None,
        "observed_outcome_coverage": len(observed) / len(eligible) if eligible else None,
        "scored_outcome_coverage": len(errors) / len(observed) if observed else None,
        "complete_forecast_coverage": bool(eligible) and len(forecast) == len(eligible),
        "mae": fmean(item[0] for item in errors) if errors else None,
        "signed_error": fmean(item[1] for item in errors) if errors else None,
        "p90_absolute_error": float(np.percentile([item[0] for item in errors], 90))
        if errors
        else None,
        "ratio_mae": fmean(item[2] for item in errors)
        if errors and target == "overall_oar"
        else None,
        "direction_agreement": fmean(item[3] for item in errors) if errors else None,
    }


def _balanced(periods: Sequence[Record], *, period_set: str = "all") -> Result:
    result: Result = {
        "target": periods[0]["target"],
        "model": periods[0]["model"],
        "period_set": period_set,
        "years": sorted(row["target_year"] for row in periods),
        "primary_units": periods[0]["primary_units"],
        "aggregation": "equal_target_year_weight; equal_program_weight_within_year",
        "p90_aggregation": "mean_of_each_year_p90; not_a_pooled_quantile",
        "complete_forecast_coverage": all(row["complete_forecast_coverage"] for row in periods),
        "all_years_scorable": all(row["n_scored"] > 0 for row in periods),
    }
    for field in (
        "n_eligible",
        "n_ineligible",
        "n_observed",
        "n_missing_outcome",
        "n_invalid_outcome",
        "n_forecast",
        "n_failure",
        "n_scored",
    ):
        result[field] = sum(row[field] for row in periods)
    for field in (
        "forecast_coverage",
        "observed_outcome_coverage",
        "scored_outcome_coverage",
        "mae",
        "signed_error",
        "p90_absolute_error",
        "ratio_mae",
        "direction_agreement",
    ):
        result[field] = _mean_or_none([row[field] for row in periods])
    return result


def _size_groups(indexed: Mapping[tuple[Key, str], Record]) -> dict[Key, str]:
    unique = {key: row for (key, _model), row in indexed.items() if _eligible(row)}
    by_period: dict[tuple[str, int], list[Record]] = defaultdict(list)
    for key, row in unique.items():
        by_period[key[:2]].append(row)
    assignments: dict[Key, str] = {}
    for rows in by_period.values():
        sizes = [
            float(row["earlier_list_size"])
            for row in rows
            if row.get("earlier_list_size") is not None
        ]
        cutoffs = np.percentile(sizes, [25, 50, 75]) if sizes else np.array([])
        for row in rows:
            size = _value(row, "earlier_list_size")
            assignments[_key(row)] = (
                "not_reported"
                if size is None
                else (f"quartile_{1 + int(np.searchsorted(cutoffs, size, side='left'))}")
            )
    return assignments


def _paired(
    indexed: Mapping[tuple[Key, str], Record],
    target: str,
    candidate: str,
    comparator: str,
    years: Sequence[int],
) -> tuple[list[Result], Result]:
    pairs: list[Result] = []
    periods: list[Result] = []
    for year in years:
        candidate_rows = [
            row
            for (key, model), row in indexed.items()
            if key[:2] == (target, year) and model == candidate and _eligible(row)
        ]
        if not candidate_rows or not any(
            key[:2] == (target, year) and model == comparator for key, model in indexed
        ):
            raise PredictionMetricError("Paired comparison requires every requested model/year.")
        candidate_forecasts = 0
        comparator_forecasts = 0
        year_pairs = []
        for row in candidate_rows:
            other = indexed[_key(row), comparator]
            candidate_forecasts += int(_valid_prediction(row))
            comparator_forecasts += int(_valid_prediction(other))
            if _valid_outcome(row) and _valid_prediction(row) and _valid_prediction(other):
                candidate_error, comparator_error = _errors(row)[0], _errors(other)[0]
                pair = {
                    "program_key": row["program_key"],
                    "target_year": year,
                    "candidate_error": candidate_error,
                    "comparator_error": comparator_error,
                    "difference": candidate_error - comparator_error,
                }
                pairs.append(pair)
                year_pairs.append(pair)
        periods.append(
            {
                "target_year": year,
                "n_eligible": len(candidate_rows),
                "n_paired": len(year_pairs),
                "candidate_forecast_coverage": candidate_forecasts / len(candidate_rows),
                "comparator_forecast_coverage": comparator_forecasts / len(candidate_rows),
                "candidate_mae": fmean(row["candidate_error"] for row in year_pairs)
                if year_pairs
                else None,
                "comparator_mae": fmean(row["comparator_error"] for row in year_pairs)
                if year_pairs
                else None,
            }
        )
    candidate_mae = _mean_or_none([row["candidate_mae"] for row in periods])
    comparator_mae = _mean_or_none([row["comparator_mae"] for row in periods])
    summary = {
        "target": target,
        "candidate": candidate,
        "comparator": comparator,
        "years": list(years),
        "n_paired": len(pairs),
        "n_eligible": sum(row["n_eligible"] for row in periods),
        "candidate_mae": candidate_mae,
        "comparator_mae": comparator_mae,
        "mae_difference": None
        if candidate_mae is None or comparator_mae is None
        else candidate_mae - comparator_mae,
        "relative_improvement": None
        if candidate_mae is None or not comparator_mae
        else 1 - candidate_mae / comparator_mae,
        "candidate_forecast_coverage": fmean(row["candidate_forecast_coverage"] for row in periods),
        "comparator_forecast_coverage": fmean(
            row["comparator_forecast_coverage"] for row in periods
        ),
        "complete_forecast_coverage": all(
            row["candidate_forecast_coverage"] == row["comparator_forecast_coverage"] == 1
            for row in periods
        ),
        "all_years_scorable": all(row["n_paired"] > 0 for row in periods),
        "periods": periods,
    }
    return pairs, summary


def summarize(predictions: Sequence[Record]) -> Result:
    """Return every period, equal-year summaries, size groups and paired baseline errors.

    Earlier list-size quartiles use only the origin-eligible universe. Equal values
    share the same group; missing earlier sizes form a reported separate group.
    The extra discovery summary omits 2021 without silently replacing the primary one.
    """
    indexed = _validated(predictions)
    groups = _size_groups(indexed)
    period_rows: dict[tuple[str, str, int], list[Record]] = defaultdict(list)
    size_rows: dict[tuple[str, str, int, str], list[Record]] = defaultdict(list)
    for (key, model), row in indexed.items():
        period_rows[key[0], model, key[1]].append(row)
        if key in groups:
            size_rows[key[0], model, key[1], groups[key]].append(row)
    periods = [_period(rows) for _key_value, rows in sorted(period_rows.items())]
    by_model: dict[tuple[str, str], list[Record]] = defaultdict(list)
    for period in periods:
        by_model[period["target"], period["model"]].append(period)
    summaries = []
    for rows in by_model.values():
        summaries.append(_balanced(rows))
        without_2021 = [row for row in rows if row["target_year"] != 2021]
        if without_2021 and len(without_2021) != len(rows):
            summaries.append(_balanced(without_2021, period_set="without_2021"))
    paired = []
    for target in sorted({row["target"] for row in predictions}):
        models = sorted({row["model"] for row in predictions if row["target"] == target})
        years = sorted({row["target_year"] for row in predictions if row["target"] == target})
        for candidate in models:
            for comparator in BASELINES:
                if comparator in models and comparator != candidate:
                    paired.append(_paired(indexed, target, candidate, comparator, years)[1])
    return {
        "period_metrics": periods,
        "summary_metrics": summaries,
        "list_size_metrics": [
            {**_period(rows), "list_size_group": key[3]} for key, rows in sorted(size_rows.items())
        ],
        "paired_comparisons": paired,
    }


def freeze_comparators(discovery_predictions: Sequence[Record]) -> dict[str, str]:
    """Fix each strongest complete simple baseline using only discovery years 2021–2023."""
    if any(row.get("target_year") not in (2021, 2022, 2023) for row in discovery_predictions):
        raise PredictionMetricError("Baseline selection accepts discovery years 2021–2023 only.")
    metrics = summarize(discovery_predictions)["summary_metrics"]
    result = {}
    for target in sorted({row["target"] for row in discovery_predictions}):
        candidates = [
            row
            for row in metrics
            if row["target"] == target
            and row["model"] in BASELINES
            and row["period_set"] == "all"
            and row["years"] == [2021, 2022, 2023]
            and row["complete_forecast_coverage"]
            and row["all_years_scorable"]
        ]
        if not candidates:
            raise PredictionMetricError(
                f"No complete discovery baseline is available for {target}."
            )
        result[target] = min(
            candidates, key=lambda row: (row["mae"], BASELINES.index(row["model"]))
        )["model"]
    return result


def _bootstrap_ratios(
    rows: Sequence[Record],
    *,
    years: Sequence[int],
    resamples: int,
    seed: int,
) -> Result:
    if isinstance(resamples, bool) or not isinstance(resamples, int) or resamples <= 0:
        raise PredictionMetricError("Bootstrap resamples must be a positive integer.")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise PredictionMetricError("Bootstrap seed must be a nonnegative integer.")
    programs = sorted({row["program_key"] for row in rows})
    program_index = {program: position for position, program in enumerate(programs)}
    year_index = {year: position for position, year in enumerate(years)}
    numerator = np.zeros((len(programs), len(years)), dtype=np.float64)
    denominator = np.zeros_like(numerator)
    for row in rows:
        position = program_index[row["program_key"]], year_index[row["target_year"]]
        numerator[position] = row["numerator"]
        denominator[position] = row["denominator"]
    totals = denominator.sum(axis=0)
    common: Result = {
        "program_count": len(programs),
        "years": list(years),
        "seed": seed,
        "attempted_resamples": resamples,
        "resampling_unit": "whole_program",
        "percentiles": [2.5, 97.5],
        "percentile_method": "linear",
        "aggregation": "equal_target_year_weight",
        "interpretation": (
            "Descriptive cross-program variation; excludes new-year shocks "
            "and model-selection uncertainty."
        ),
    }
    if not programs or not len(years) or not (totals > 0).all():
        return {
            **common,
            "point_estimate": None,
            "lower": None,
            "upper": None,
            "retained_resamples": 0,
            "skipped_undefined_year": resamples,
            "status": "unavailable_required_year_denominator",
        }
    rng = np.random.default_rng(seed)
    retained: list[float] = []
    for start in range(0, resamples, 256):
        draw = rng.integers(0, len(programs), size=(min(256, resamples - start), len(programs)))
        draw_numerator = numerator[draw].sum(axis=1)
        draw_denominator = denominator[draw].sum(axis=1)
        valid = (draw_denominator > 0).all(axis=1)
        retained.extend((draw_numerator[valid] / draw_denominator[valid]).mean(axis=1).tolist())
    lower, upper = (
        np.percentile(retained, [2.5, 97.5], method="linear") if retained else (None, None)
    )
    return {
        **common,
        "point_estimate": float((numerator.sum(axis=0) / totals).mean()),
        "lower": float(lower) if lower is not None else None,
        "upper": float(upper) if upper is not None else None,
        "retained_resamples": len(retained),
        "skipped_undefined_year": resamples - len(retained),
        "status": "ok" if retained else "unavailable_all_resamples",
    }


def bootstrap_error_difference(
    predictions: Sequence[Record],
    *,
    target: str,
    candidate: str,
    comparator: str,
    years: Sequence[int] | None = None,
    resamples: int = 2000,
    seed: int = DEFAULT_SEED,
) -> Result:
    """Resample paired whole programs; negative primary-error differences favor the candidate."""
    indexed = _validated(predictions)
    selected_years = (
        sorted(set(years))
        if years is not None
        else sorted({row["target_year"] for row in predictions if row["target"] == target})
    )
    pairs, comparison = _paired(indexed, target, candidate, comparator, selected_years)
    return {
        **_bootstrap_ratios(
            [{**row, "numerator": row["difference"], "denominator": 1} for row in pairs],
            years=selected_years,
            resamples=resamples,
            seed=seed,
        ),
        "target": target,
        "candidate": candidate,
        "comparator": comparator,
        "contrast": "candidate_minus_comparator_primary_mae",
        "n_paired": comparison["n_paired"],
        "complete_forecast_coverage": comparison["complete_forecast_coverage"],
        "candidate_forecast_coverage": comparison["candidate_forecast_coverage"],
        "comparator_forecast_coverage": comparison["comparator_forecast_coverage"],
    }


def _directional_change(row: Record, direction: str) -> float | None:
    if not _valid_outcome(row):
        return None
    change = _scale(float(row["observed"]), row["target"]) - _scale(
        float(row["latest"]), row["target"]
    )
    return max(change if direction == "growth" else -change, 0)


def _review_score(row: Record, method: str, direction: str) -> tuple[float | None, bool]:
    target, latest = row["target"], _scale(float(row["latest"]), row["target"])
    if method == "latest_level":
        return (-latest if target == "overall_oar" else latest), True
    if method == "last_change":
        previous = _value(row, "previous")
        # A missing consecutive pair conveys no observed direction; preserve the gap.
        if previous is None or (target == "overall_oar" and previous <= 0):
            return 0.0, False
        change = latest - _scale(previous, target)
    else:
        if not _valid_prediction(row):
            return None, False
        change = _scale(float(row["prediction"]), target) - latest
    return max(change if direction == "growth" else -change, 0), True


def _tie_key(row: Record, seed: int) -> str:
    identity = f"{seed}|{row['target']}|{row['target_year']}|{row['program_key']}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _queue_metrics(
    rows: Sequence[Record],
    scores: Mapping[str, float | None],
    selected: set[str] | None,
    *,
    budget: int,
    direction: str,
    method: str,
    score_available: int,
) -> Result:
    n, effective = len(rows), min(budget, len(rows))
    changes = {row["program_key"]: _directional_change(row, direction) for row in rows}
    observed = {program: change for program, change in changes.items() if change is not None}
    total = sum(observed.values())
    selected_observed = {
        program: change
        for program, change in observed.items()
        if selected is not None and program in selected
    }
    captured = sum(selected_observed.values())
    valid_scores = [score for score in scores.values() if score is not None]
    threshold = (
        sorted(valid_scores, reverse=True)[effective - 1] if selected and effective else None
    )
    complete = selected is not None
    return {
        "target": rows[0]["target"],
        "target_year": rows[0]["target_year"],
        "method": method,
        "direction": direction,
        "budget": budget,
        "effective_budget": effective,
        "n_universe": n,
        "n_forecast": len(valid_scores),
        "forecast_coverage": len(valid_scores) / n,
        "n_score_available": score_available,
        "n_score_missing_fallback_zero": n - score_available if method == "last_change" else 0,
        "status": "ok" if complete else "incomplete_forecast_coverage",
        "n_observed": len(observed),
        "n_missing_outcome": n - len(observed),
        "observed_outcome_coverage": len(observed) / n,
        "n_directional_programs": sum(change > 0 for change in observed.values()),
        "total_observed_directional_change": total,
        "n_selected": len(selected) if selected is not None else None,
        "n_selected_observed": len(selected_observed) if complete else None,
        "n_selected_missing_outcome": effective - len(selected_observed) if complete else None,
        "selected_outcome_coverage": len(selected_observed) / effective
        if complete and effective
        else None,
        "captured_observed_change": captured if complete else None,
        "captured_share": captured / total if complete and total > 0 else None,
        "selected_precision": sum(change > 0 for change in selected_observed.values())
        / len(selected_observed)
        if complete and selected_observed
        else None,
        "n_false_alarms": sum(change == 0 for change in selected_observed.values())
        if complete
        else None,
        "missed_observed_change": total - captured if complete else None,
        "n_missed_directional_programs": sum(
            change > 0
            for program, change in observed.items()
            if selected is not None and program not in selected
        )
        if complete
        else None,
        "all_scores_zero": all(score == 0 for score in valid_scores) if complete else None,
        "n_positive_scores": sum(score > 0 for score in valid_scores),
        "n_distinct_scores": len(set(valid_scores)),
        "n_tied_at_cutoff": sum(score == threshold for score in valid_scores)
        if threshold is not None
        else None,
        "is_expectation": False,
    }


def _random_metric(rows: Sequence[Record], *, budget: int, direction: str) -> Result:
    metric = _queue_metrics(
        rows,
        dict.fromkeys((row["program_key"] for row in rows), 0.0),
        set(),
        budget=budget,
        direction=direction,
        method="random_expectation",
        score_available=len(rows),
    )
    fraction = min(budget, len(rows)) / len(rows)
    total, observed = metric["total_observed_directional_change"], metric["n_observed"]
    for field in (
        "n_selected",
        "n_selected_observed",
        "n_selected_missing_outcome",
        "n_false_alarms",
        "n_missed_directional_programs",
        "all_scores_zero",
        "n_positive_scores",
        "n_distinct_scores",
        "n_tied_at_cutoff",
    ):
        metric[field] = None
    metric.update(
        {
            "is_expectation": True,
            "captured_share": fraction if total > 0 else None,
            "captured_observed_change": fraction * total,
            "missed_observed_change": (1 - fraction) * total,
            "selected_precision": metric["n_directional_programs"] / observed if observed else None,
            "selected_outcome_coverage": observed / len(rows),
            "expected_selected_observed": fraction * observed,
            "expected_false_alarms": fraction * (observed - metric["n_directional_programs"]),
            "random_review_probability": fraction,
        }
    )
    return metric


def review_budget(
    predictions: Sequence[Record],
    *,
    target: str,
    model: str,
    direction: str | None = None,
    budgets: Sequence[int] = (10, 15, 25),
    seed: int = DEFAULT_SEED,
    comparator: str | None = None,
) -> Result:
    """Select review queues before seeing outcomes; never refill an unscorable selection.

    Ties use the same stable seeded order across methods. If any model forecast is
    missing, its queue is unavailable for that year and the full universe remains.
    A missing last consecutive change ranks at zero and is counted explicitly.
    """
    indexed = _validated(predictions)
    selected_direction = direction or (
        "decline" if target in {"ddkt_removals", "overall_oar"} else "growth"
    )
    if selected_direction not in {"growth", "decline"}:
        raise PredictionMetricError("Review direction must be growth or decline.")
    if not budgets or any(isinstance(k, bool) or not isinstance(k, int) or k <= 0 for k in budgets):
        raise PredictionMetricError("Review budgets must be positive integers.")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise PredictionMetricError("Review seed must be a nonnegative integer.")
    by_year: dict[int, list[Record]] = defaultdict(list)
    for (key, model_name), row in indexed.items():
        if key[0] == target and model_name == model and _eligible(row):
            by_year[key[1]].append(row)
    if not by_year:
        raise PredictionMetricError("Review requires an origin-eligible target/model universe.")
    if comparator and comparator not in {
        row["model"] for row in predictions if row["target"] == target
    }:
        raise PredictionMetricError(
            "The requested review comparator has no forecasts for this target."
        )
    methods = list(
        dict.fromkeys([model, "last_change", "latest_level", *([comparator] if comparator else [])])
    )
    metrics: list[Result] = []
    selections: list[Result] = []
    for year, unsorted in sorted(by_year.items()):
        rows = sorted(unsorted, key=lambda row: row["program_key"])
        for method in methods:
            method_rows = (
                rows
                if method in {model, "last_change", "latest_level"}
                else [indexed[_key(row), method] for row in rows]
            )
            scores = {
                row["program_key"]: _review_score(row, method, selected_direction)
                for row in method_rows
            }
            values = {program: score for program, (score, _available) in scores.items()}
            complete = all(score is not None for score in values.values())
            ordered = sorted(
                rows, key=lambda row: (-(values[row["program_key"]] or 0), _tie_key(row, seed))
            )
            for budget in budgets:
                selected = {row["program_key"] for row in ordered[:budget]} if complete else None
                metrics.append(
                    _queue_metrics(
                        rows,
                        values,
                        selected,
                        budget=budget,
                        direction=selected_direction,
                        method=method,
                        score_available=sum(available for _score, available in scores.values()),
                    )
                )
                for row in rows:
                    selections.append(
                        {
                            "target": target,
                            "target_year": year,
                            "program_key": row["program_key"],
                            "origin_release": row.get("origin_release"),
                            "method": method,
                            "budget": budget,
                            "direction": selected_direction,
                            "selected": row["program_key"] in selected
                            if selected is not None
                            else None,
                            "score": values[row["program_key"]],
                            "score_available": scores[row["program_key"]][1],
                            "observed": row.get("observed"),
                            "latest": row["latest"],
                            "observed_directional_change": _directional_change(
                                row, selected_direction
                            ),
                        }
                    )
        metrics.extend(
            _random_metric(rows, budget=budget, direction=selected_direction) for budget in budgets
        )
    return {
        "metrics": metrics,
        "selections": selections,
        "seed": seed,
        "tie_rule": "descending_score_then_sha256_of_seed_target_year_composite_program_key",
        "unknown_outcome_rule": "keep_selected_unscorable_programs; never_refill",
        "claim": (
            "Observed program events support a review demonstration, not intervention benefit."
        ),
    }


def bootstrap_decision_difference(
    selections: Sequence[Record],
    *,
    target: str,
    candidate: str,
    comparator: str,
    budget: int,
    years: Sequence[int] | None = None,
    resamples: int = 2000,
    seed: int = DEFAULT_SEED,
) -> Result:
    """Resample whole programs' saved selection flags for captured-share differences.

    The queues were chosen once from the actual origin universe. Holding their flags
    fixed answers how their observed capture differs across program histories.
    Reranking a resampled population would instead construct new queues with duplicated
    programs, answer a different question, and lose the historical effective budget.
    These conditional descriptive intervals exclude queue selection, fitting, winner
    selection and new-year uncertainty. Unknown outcomes remain unscorable.
    """
    chosen_years = (
        sorted(set(years))
        if years is not None
        else sorted(
            {
                row["target_year"]
                for row in selections
                if row["target"] == target and row["budget"] == budget
            }
        )
    )
    indexed: dict[str, dict[tuple[str, int], Record]] = {candidate: {}, comparator: {}}
    for row in selections:
        if (
            row["target"] != target
            or row["budget"] != budget
            or row["method"] not in indexed
            or row["target_year"] not in chosen_years
        ):
            continue
        key = row["program_key"], row["target_year"]
        if key in indexed[row["method"]]:
            raise PredictionMetricError("Duplicate review selection row.")
        indexed[row["method"]][key] = row
    if set(indexed[candidate]) != set(indexed[comparator]) or not indexed[candidate]:
        raise PredictionMetricError("Decision methods must retain the same origin universe.")
    rows: list[Result] = []
    for key, left in indexed[candidate].items():
        right = indexed[comparator][key]
        if (
            left["observed_directional_change"] != right["observed_directional_change"]
            or left["direction"] != right["direction"]
        ):
            raise PredictionMetricError("Paired decision outcome evidence disagrees.")
        if left["selected"] is None or right["selected"] is None:
            raise PredictionMetricError(
                "An incomplete forecast queue cannot support a decision interval."
            )
        change = _number(left["observed_directional_change"], "observed_directional_change") or 0.0
        if (
            change < 0
            or not isinstance(left["selected"], bool)
            or not isinstance(right["selected"], bool)
        ):
            raise PredictionMetricError("Decision rows need nonnegative changes and boolean flags.")
        rows.append(
            {
                "program_key": key[0],
                "target_year": key[1],
                "numerator": (int(left["selected"]) - int(right["selected"])) * change,
                "denominator": change,
            }
        )
    return {
        **_bootstrap_ratios(rows, years=chosen_years, resamples=resamples, seed=seed),
        "target": target,
        "candidate": candidate,
        "comparator": comparator,
        "budget": budget,
        "contrast": "candidate_minus_comparator_captured_share",
        "queue_resampling": "fixed_historical_selection_flags",
        "interpretation": (
            "Descriptive cross-program variation conditional on fixed historical queues; "
            "no refit or reranking; excludes queue selection, model selection "
            "and new-year uncertainty."
        ),
    }
