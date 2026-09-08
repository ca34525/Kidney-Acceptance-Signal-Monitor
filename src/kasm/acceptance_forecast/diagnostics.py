"""Describe saved program-year prediction errors without fitting or changing them.

Percent errors divide by the published ratio. Combined means weight years equally;
combined distributions retain their separate, secondary row-pooled interpretation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from math import floor, isfinite, log
from statistics import fmean
from typing import Any

Record = Mapping[str, object]
Summary = dict[str, Any]
_SCALES = ("log", "ratio", "percentage")
_FLAGS = ("analytic_eligible", "public_forecast_eligible", "first_observed_program")


class DiagnosticError(ValueError):
    """Raised when error descriptions would hide invalid values or changed populations."""


def _positive(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DiagnosticError(f"{name} must be a positive finite ratio.")
    result = float(value)
    if not isfinite(result) or result <= 0:
        raise DiagnosticError(f"{name} must be a positive finite ratio.")
    return result


def error_values(target_oar: object, predicted_oar: object) -> dict[str, float]:
    """Return errors in ratio units, percent of the published ratio, and natural logs."""
    target = _positive(target_oar, "Published target")
    prediction = _positive(predicted_oar, "Prediction")
    signed = {
        "ratio": prediction - target,
        "percentage": 100 * (prediction / target - 1),
        "log": log(prediction) - log(target),
    }
    if not all(isfinite(value) for value in signed.values()):
        raise DiagnosticError("Error calculation exceeded finite numeric range; do not trim it.")
    return {
        f"{direction}_{scale}_error": value if direction == "signed" else abs(value)
        for scale, value in signed.items()
        for direction in ("signed", "absolute")
    }


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def _text(row: Record, field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise DiagnosticError(f"{field} must be a nonempty string.")
    return value


def _identity(row: Record) -> tuple[str, int]:
    year = row.get("target_cohort_year")
    if isinstance(year, bool) or not isinstance(year, int):
        raise DiagnosticError("target_cohort_year must be an integer.")
    return _text(row, "program_key"), year


def _validate_population(group: Mapping[str, Record], models: Sequence[str]) -> Record:
    if set(group) != set(models):
        raise DiagnosticError("Every required program-year must have every configured model.")
    reference = group[models[0]]
    for row in group.values():
        if row.get("target_oar") != reference.get("target_oar"):
            raise DiagnosticError("Paired models must use the same published target.")
        for flag in _FLAGS:
            if not isinstance(row.get(flag), bool):
                raise DiagnosticError(f"{flag} must be an explicit boolean.")
            if row.get(flag) != reference.get(flag):
                raise DiagnosticError(f"Paired models disagree about {flag}.")
    return reference


def _prepare(
    records: Sequence[Record], models: Sequence[str], years: Sequence[int]
) -> tuple[list[Summary], Summary]:
    if not models or len(set(models)) != len(models):
        raise DiagnosticError("Configure a nonempty, unique model list.")
    if not years or len(set(years)) != len(years):
        raise DiagnosticError("Configure a nonempty, unique year list.")
    grouped: dict[tuple[str, int], dict[str, Record]] = defaultdict(dict)
    for row in records:
        identity = _identity(row)
        model = _text(row, "model")
        if identity[1] not in years or model not in models:
            raise DiagnosticError(
                "Prediction model or year falls outside the configured population."
            )
        if model in grouped[identity]:
            raise DiagnosticError("Duplicate model prediction for the same program-year.")
        grouped[identity][model] = row
    exclusions = {
        "input_program_years": len(grouped),
        "missing_target_program_years": 0,
        "analytic_ineligible_program_years": 0,
        "eligible_program_years": 0,
    }
    prepared: list[Summary] = []
    for identity in sorted(grouped):
        reference = _validate_population(grouped[identity], models)
        if reference.get("target_oar") is None:
            exclusions["missing_target_program_years"] += 1
            continue
        if reference.get("analytic_eligible") is False:
            exclusions["analytic_ineligible_program_years"] += 1
            continue
        exclusions["eligible_program_years"] += 1
        for row in grouped[identity].values():
            prepared.append(
                {**row, **error_values(row.get("target_oar"), row.get("predicted_oar"))}
            )
    if {row["target_cohort_year"] for row in prepared} != set(years):
        raise DiagnosticError("Every configured year needs an eligible prediction population.")
    return prepared, exclusions


def _tolerance_name(tolerance: float) -> str:
    return f"within_{100 * tolerance:g}_percent"


def _distribution(values: Sequence[float], prefix: str) -> Summary:
    return {
        f"{prefix}_mean": fmean(values),
        f"{prefix}_median": _percentile(values, 0.5),
        f"{prefix}_p10": _percentile(values, 0.1),
        f"{prefix}_p90": _percentile(values, 0.9),
        f"{prefix}_p95": _percentile(values, 0.95),
        f"{prefix}_min": min(values),
        f"{prefix}_max": max(values),
    }


def _describe(rows: Sequence[Summary], tolerances: Sequence[float]) -> Summary:
    result: Summary = {
        "n": len(rows),
        "program_count": len({row["program_key"] for row in rows}),
        "public_forecast_eligible_count": sum(
            row.get("public_forecast_eligible") is True for row in rows
        ),
        "first_observed_program_count": sum(
            row.get("first_observed_program") is True for row in rows
        ),
    }
    for scale in _SCALES:
        for direction in ("signed", "absolute"):
            prefix = f"{direction}_{scale}"
            result.update(_distribution([row[f"{prefix}_error"] for row in rows], prefix))
    for tolerance in tolerances:
        # Comparing bounds includes decimal boundary predictions such as 1.1 of 1.0.
        count = sum(
            row["target_oar"] * (1 - tolerance)
            <= row["predicted_oar"]
            <= row["target_oar"] * (1 + tolerance)
            for row in rows
        )
        key = _tolerance_name(tolerance)
        result[f"{key}_count"] = count
        result[f"{key}_fraction"] = count / len(rows)
    return result


def _year_balanced(rows: Sequence[Summary]) -> Summary:
    keys = [key for key in rows[0] if key.endswith(("_mean", "_fraction"))]
    return {
        "n": sum(row["n"] for row in rows),
        "year_count": len(rows),
        **{key: fmean(row[key] for row in rows) for key in keys},
    }


def _group_value(row: Record, field: str) -> str:
    value = row.get(field)
    if value is None:
        return "Unknown"
    if isinstance(value, bool):
        return "True" if value else "False"
    if not isinstance(value, str | int | float):
        raise DiagnosticError(f"Stratum {field} must be a scalar or null.")
    return str(value)


def _group_summaries(
    prepared: Sequence[Summary], group_fields: Sequence[str], tolerances: Sequence[float]
) -> tuple[list[Summary], list[Summary]]:
    groups: list[Summary] = []
    balanced: list[Summary] = []
    for field in group_fields:
        cells: dict[tuple[str, str, int], list[Summary]] = defaultdict(list)
        for row in prepared:
            cells[(row["model"], _group_value(row, field), row["target_cohort_year"])].append(row)
        summaries: dict[tuple[str, str], list[Summary]] = defaultdict(list)
        for (model, value, year), rows in sorted(cells.items()):
            summary = {
                "model": model,
                "group_field": field,
                "group_value": value,
                "target_year": year,
                **_describe(rows, tolerances),
            }
            groups.append(summary)
            summaries[(model, value)].append(summary)
        for (model, value), rows in sorted(summaries.items()):
            balanced.append(
                {
                    "model": model,
                    "group_field": field,
                    "group_value": value,
                    "years": [row["target_year"] for row in rows],
                    **_year_balanced(rows),
                }
            )
    return groups, balanced


def summarize_predictions(
    records: Sequence[Record],
    *,
    models: Sequence[str],
    years: Sequence[int],
    tolerances: Sequence[float] = (0.1, 0.25, 0.5),
    group_fields: Sequence[str] = (),
) -> Summary:
    """Describe identical model populations by year, then by equal-year averages.

    Missing targets and analytically ineligible rows are counted once per program-year.
    The secondary pooled distributions count repeated program-years as rows, not independent people.
    """
    if any(not isfinite(q) or not 0 < q < 1 for q in tolerances):
        raise DiagnosticError(
            "Relative tolerances must be finite and strictly between zero and one."
        )
    prepared, exclusions = _prepare(records, models, years)
    by_year: list[Summary] = []
    balanced: list[Summary] = []
    pooled: list[Summary] = []
    for model in models:
        model_rows = [row for row in prepared if row["model"] == model]
        yearly = [
            {
                "model": model,
                "target_year": year,
                **_describe(
                    [row for row in model_rows if row["target_cohort_year"] == year],
                    tolerances,
                ),
            }
            for year in years
        ]
        by_year.extend(yearly)
        balanced.append({"model": model, "years": list(years), **_year_balanced(yearly)})
        pooled.append({"model": model, "years": list(years), **_describe(model_rows, tolerances)})
    groups, group_balanced = _group_summaries(prepared, group_fields, tolerances)
    return {
        "by_year": by_year,
        "year_balanced": balanced,
        "pooled_secondary": pooled,
        "groups": groups,
        "group_year_balanced": group_balanced,
        "exclusions": exclusions,
        "distribution_note": "Pooled quantiles are secondary; programs repeat across years.",
    }


def _paired_description(rows: Sequence[Summary], scale: str) -> Summary:
    values = [row[f"difference_{scale}"] for row in rows]
    return {
        "scale": scale,
        "n": len(rows),
        "program_count": len({row["program_key"] for row in rows}),
        "wins": sum(value < 0 for value in values),
        "ties": sum(value == 0 for value in values),
        "losses": sum(value > 0 for value in values),
        "win_fraction": sum(value < 0 for value in values) / len(rows),
        "tie_fraction": sum(value == 0 for value in values) / len(rows),
        "loss_fraction": sum(value > 0 for value in values) / len(rows),
        **_distribution(values, "difference"),
    }


def paired_comparison(
    records: Sequence[Record],
    *,
    candidate: str,
    comparator: str,
    years: Sequence[int],
) -> Summary:
    """Count exact, unrounded wins on each named scale for the same program-years."""
    prepared, exclusions = _prepare(
        [row for row in records if _text(row, "model") in (candidate, comparator)],
        (candidate, comparator),
        years,
    )
    indexed = {(_identity(row), row["model"]): row for row in prepared}
    differences: list[Summary] = []
    for row in prepared:
        if row["model"] == candidate:
            other = indexed[(_identity(row), comparator)]
            differences.append(
                {
                    "program_key": row["program_key"],
                    "target_cohort_year": row["target_cohort_year"],
                    **{
                        f"difference_{scale}": row[f"absolute_{scale}_error"]
                        - other[f"absolute_{scale}_error"]
                        for scale in _SCALES
                    },
                }
            )
    by_year: list[Summary] = []
    balanced: list[Summary] = []
    pooled: list[Summary] = []
    for scale in _SCALES:
        yearly = [
            {
                "target_year": year,
                **_paired_description(
                    [row for row in differences if row["target_cohort_year"] == year],
                    scale,
                ),
            }
            for year in years
        ]
        by_year.extend(yearly)
        balanced.append({"scale": scale, "years": list(years), **_year_balanced(yearly)})
        pooled.append({"years": list(years), **_paired_description(differences, scale)})
    return {
        "candidate": candidate,
        "comparator": comparator,
        "by_year": by_year,
        "year_balanced": balanced,
        "pooled_secondary": pooled,
        "exclusions": exclusions,
        "difference_direction": "candidate minus comparator absolute error; negative is a win",
    }


def _band_description(rows: Sequence[Summary]) -> Summary:
    widths: list[float] = []
    covered = 0
    for row in rows:
        lower, upper = row.get("band_lower_oar"), row.get("band_upper_oar")
        if lower is None and upper is None:
            continue
        low = _positive(lower, "Band lower bound")
        high = _positive(upper, "Band upper bound")
        if low > high:
            raise DiagnosticError("Band lower bound cannot exceed its upper bound.")
        widths.append(high - low)
        covered += low <= row["target_oar"] <= high
    return {
        "n": len(rows),
        "band_available": len(widths),
        "band_unavailable": len(rows) - len(widths),
        "covered": covered,
        "coverage": covered / len(widths) if widths else None,
        "mean_width_ratio": fmean(widths) if widths else None,
    }


def summarize_bands(
    records: Sequence[Record],
    *,
    models: Sequence[str],
    years: Sequence[int],
    group_fields: Sequence[str] = (),
) -> list[Summary]:
    """Describe saved forecast bands separately from SRTR credible intervals."""
    prepared, _ = _prepare(records, models, years)
    summaries: list[Summary] = []
    for model in models:
        for year in years:
            rows = [
                row
                for row in prepared
                if row["model"] == model and row["target_cohort_year"] == year
            ]
            summaries.append({"model": model, "target_year": year, **_band_description(rows)})
            for field in group_fields:
                for value in sorted({_group_value(row, field) for row in rows}):
                    summaries.append(
                        {
                            "model": model,
                            "target_year": year,
                            "group_field": field,
                            "group_value": value,
                            **_band_description(
                                [row for row in rows if _group_value(row, field) == value]
                            ),
                        }
                    )
    return summaries
