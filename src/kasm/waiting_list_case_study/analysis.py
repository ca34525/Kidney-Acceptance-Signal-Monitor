"""Describe event changes and reconcile two published annual program records."""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

import numpy as np

from kasm.waiting_list.config import ScreenError
from kasm.waiting_list.parse import REMOVAL_FIELDS, AnnualRecord
from kasm.waiting_list.screen import Comparison, compare_years
from kasm.waiting_list_case_study.config import CaseStudyError

YEARS = (2023, 2024, 2025)
EXAMPLE_YEAR = 2025
_UNAVAILABLE = {
    "unsupported_year": "Comparison year is unsupported; choose 2023, 2024 or 2025.",
    "missing_previous": "The preceding annual program record is not available.",
    "missing_current": "The current annual program record is not available.",
    "missing": "A required annual count is not reported; the comparison is unavailable.",
    "residual": "Published annual counts do not reconcile exactly; the comparison is excluded.",
    "boundary": "The preceding ending count differs from the current starting count.",
    "zero": "The current starting count is zero; a per-100 comparison is unavailable.",
    "missing_comparison": "This program-year is not included in the trusted eligible comparisons.",
}


def _validate_comparison(row: Comparison) -> None:
    """Reject impossible event counts before division or signed decomposition."""
    values = (
        row.year,
        row.start,
        row.growth,
        row.change_in_growth,
        row.additions,
        row.change_additions,
        *row.removals,
        *row.removal_contributions,
    )
    if (
        not isinstance(row.program_key, str)
        or re.fullmatch(r"[A-Z0-9]{4}:[A-Z0-9]+", row.program_key) is None
        or any(type(value) is not int for value in values)
        or row.start <= 0
        or len(row.removals) != len(REMOVAL_FIELDS)
        or len(row.removal_contributions) != len(REMOVAL_FIELDS)
    ):
        raise CaseStudyError("Invalid comparison identity, integer counts or positive denominator.")
    previous_removals = tuple(
        now + contribution
        for now, contribution in zip(row.removals, row.removal_contributions, strict=True)
    )
    nonnegative = (
        row.additions,
        row.additions - row.change_additions,
        row.start + row.growth,
        row.start - (row.growth - row.change_in_growth),
        *row.removals,
        *previous_removals,
    )
    if (
        any(value < 0 for value in nonnegative)
        or row.growth != row.additions - sum(row.removals)
        or row.change_in_growth != row.change_additions + sum(row.removal_contributions)
    ):
        raise CaseStudyError("Comparison accounting does not reconcile with nonnegative counts.")


def _validate_pairs(pairs: tuple[Comparison, ...]) -> None:
    seen: set[tuple[str, int]] = set()
    for row in pairs:
        _validate_comparison(row)
        key = (row.program_key, row.year)
        if key in seen:
            raise CaseStudyError("Cannot describe duplicate comparison program years.")
        seen.add(key)


def _six_numbers(values: tuple[float, ...]) -> dict[str, int | float | None]:
    names = ("minimum", "lower_quartile", "median", "upper_quartile", "maximum")
    if not values:
        return {"n": 0} | dict.fromkeys(names)
    quantiles = np.percentile(values, (0, 25, 50, 75, 100), method="linear")
    return {"n": len(values)} | {
        name: float(value) for name, value in zip(names, quantiles, strict=True)
    }


def _distribution(pairs: tuple[Comparison, ...]) -> dict[str, Any]:
    raw = tuple(float(-sum(row.removal_contributions[:2])) for row in pairs)
    relative = tuple(100 * value / row.start for row, value in zip(pairs, raw, strict=True))
    return {
        "programs": len(pairs),
        "change_transplants": _six_numbers(raw),
        "change_transplants_per100": _six_numbers(relative),
    }


def summarize_distributions(pairs: tuple[Comparison, ...]) -> dict[str, Any]:
    """Summarize each fixed year with one weight per eligible growing program."""
    _validate_pairs(pairs)
    annual: dict[str, Any] = {}
    for year in YEARS:
        eligible = tuple(row for row in pairs if row.year == year)
        growing = tuple(row for row in eligible if row.growth > 0)
        increased = tuple(row for row in growing if row.transplant_increased)
        counts = {
            "increased": len(increased),
            "unchanged": sum(sum(row.removal_contributions[:2]) == 0 for row in growing),
            "decreased": sum(sum(row.removal_contributions[:2]) > 0 for row in growing),
        }
        annual[str(year)] = {
            "eligible_programs": len(eligible),
            "growing_programs": len(growing),
            "frequency": {
                group: {
                    "numerator": count,
                    "denominator": len(growing),
                    "percent": 100 * count / len(growing) if growing else None,
                }
                for group, count in counts.items()
            },
            "groups": {
                "all_growing": _distribution(growing),
                "increased": _distribution(increased),
            },
        }
    return {"years": list(YEARS), "annual": annual}


def select_examples(pairs: tuple[Comparison, ...]) -> list[dict[str, Any]]:
    """Take the lower middle starting-list size within each fixed illustration group."""
    _validate_pairs(pairs)
    common = set.intersection(
        *({row.program_key for row in pairs if row.year == year} for year in YEARS)
    )
    groups: dict[str, list[Comparison]] = {
        "growing_increased": [],
        "growing_not_increased": [],
        "shrinking": [],
    }
    for row in pairs:
        if row.year != EXAMPLE_YEAR or row.program_key not in common or row.growth == 0:
            continue
        group = (
            "shrinking"
            if row.growth < 0
            else ("growing_increased" if row.transplant_increased else "growing_not_increased")
        )
        groups[group].append(row)
    selected: list[dict[str, Any]] = []
    for group, rows in groups.items():
        rows.sort(key=lambda row: (row.start, row.program_key))
        index = (len(rows) - 1) // 2 if rows else None
        chosen = rows[index] if index is not None else None
        selected.append(
            {
                "group": group,
                "available": chosen is not None,
                "reason": None if chosen else "No common program belongs to this example group.",
                "common_programs": len(common),
                "candidates": len(rows),
                "selection_index": index,
                "program_key": chosen.program_key if chosen else None,
                "year": EXAMPLE_YEAR,
                "start": chosen.start if chosen else None,
            }
        )
    return selected


def _annual_values(row: AnnualRecord | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return asdict(row) | {
        "removals_by_field": dict(zip(REMOVAL_FIELDS, row.removals, strict=True)),
        "growth": row.growth,
        "removal_total": row.removal_total,
        "annual_equation": {
            "end": row.end,
            "start": row.start,
            "additions": row.additions,
            "removal_total": row.removal_total,
            "residual": row.residual,
        },
    }


def _change_values(row: Comparison) -> dict[str, Any]:
    contributions = dict(zip(REMOVAL_FIELDS, row.removal_contributions, strict=True))
    raw = {"ADDCEN": row.change_additions} | contributions
    transplants = -sum(row.removal_contributions[:2])
    return {
        "growth": row.growth,
        "previous_growth": row.growth - row.change_in_growth,
        "change_in_growth": row.change_in_growth,
        "change_transplants": transplants,
        "denominator": row.start,
        "change_additions": row.change_additions,
        "removal_contributions": contributions,
        "contributions_per100": {field: 100 * value / row.start for field, value in raw.items()},
        "growth_per100": row.growth_per100,
        "change_in_growth_per100": row.change_in_growth_per100,
        "change_transplants_per100": 100 * transplants / row.start,
    }


def program_brief(
    records: tuple[AnnualRecord, ...],
    pairs: tuple[Comparison, ...],
    program_key: str,
    year: int,
) -> dict[str, Any]:
    """Retain both source rows and explain why an unusable comparison is unavailable."""
    _validate_pairs(pairs)
    try:
        checked_pairs, exclusions = compare_years(records)
    except ScreenError as exc:
        raise CaseStudyError(f"Cannot prepare annual program brief: {exc}") from exc
    lookup = {(row.program_key, row.year): row for row in records}
    previous = lookup.get((program_key, year - 1))
    current = lookup.get((program_key, year))
    result: dict[str, Any] = {
        "available": False,
        "reason": None,
        "reason_code": None,
        "program_key": program_key,
        "year": year,
        "previous": _annual_values(previous),
        "current": _annual_values(current),
        "change": None,
    }
    if year not in YEARS:
        reason = "unsupported_year"
    elif current is None:
        reason = "missing_current"
    elif previous is None:
        reason = "missing_previous"
    else:
        reason = next(
            (
                item["reason"]
                for item in exclusions
                if item["program_key"] == program_key and item["year"] == year
            ),
            "missing_comparison",
        )
        supplied = next(
            (row for row in pairs if row.program_key == program_key and row.year == year), None
        )
        expected = next(
            (row for row in checked_pairs if row.program_key == program_key and row.year == year),
            None,
        )
        if supplied is not None:
            if supplied != expected:
                raise CaseStudyError("Trusted comparison does not match its published annual rows.")
            return result | {"available": True, "change": _change_values(supplied)}
    return result | {"reason": _UNAVAILABLE[reason], "reason_code": reason}
