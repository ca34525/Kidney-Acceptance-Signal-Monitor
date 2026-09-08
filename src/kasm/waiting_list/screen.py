"""Compare growing lists with increasing and nonincreasing transplant removals.

One observation joins consecutive calendar years for the same program. Every
contribution to the change in growth uses the current year's starting list.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, median
from typing import Any

from kasm.waiting_list.config import ScreenConfig, ScreenError
from kasm.waiting_list.parse import AnnualRecord


@dataclass(frozen=True)
class Comparison:
    """Calculated counts, retaining every removal reason separately."""

    program_key: str
    year: int
    previous_release: str
    current_release: str
    start: int
    growth: int
    change_in_growth: int
    additions: int
    removals: tuple[int, ...]
    change_additions: int
    removal_contributions: tuple[int, ...]

    @property
    def transplant_increased(self) -> bool:
        return sum(self.removal_contributions[:2]) < 0

    @property
    def growth_per100(self) -> float:
        return 100 * self.growth / self.start

    @property
    def change_in_growth_per100(self) -> float:
        return 100 * self.change_in_growth / self.start


def _exclusion(previous: AnnualRecord, current: AnnualRecord) -> str | None:
    if previous.residual is None or current.residual is None:
        return "missing"
    if not previous.clean or not current.clean:
        return "residual"
    if previous.end != current.start:
        return "boundary"
    if current.start == 0:
        return "zero"
    return None


def compare_years(
    records: tuple[AnnualRecord, ...],
) -> tuple[tuple[Comparison, ...], tuple[dict[str, Any], ...]]:
    """Exclude unreported, unreconciled, discontinuous or zero-denominator pairs."""
    lookup = {(row.program_key, row.year): row for row in records}
    if len(lookup) != len(records):
        raise ScreenError("Cannot compare duplicate program years.")
    pairs: list[Comparison] = []
    exclusions: list[dict[str, Any]] = []
    for current in sorted(records, key=lambda row: (row.year, row.program_key)):
        previous = lookup.get((current.program_key, current.year - 1))
        if previous is None:
            continue
        reason = _exclusion(previous, current)
        if reason:
            exclusions.append(
                {
                    "program_key": current.program_key,
                    "year": current.year,
                    "reason": reason,
                    "previous_release": previous.release_code,
                    "current_release": current.release_code,
                    "previous_end": previous.end,
                    "current_start": current.start,
                }
            )
            continue
        # Exact reconciliation established all counts are present.
        if (
            current.start is None
            or current.additions is None
            or previous.additions is None
            or current.growth is None
            or previous.growth is None
        ):
            raise ScreenError("Clean accounting unexpectedly lacks a count.")
        removals = tuple(int(value) for value in current.removals if value is not None)
        earlier = tuple(int(value) for value in previous.removals if value is not None)
        contributions = tuple(old - new for old, new in zip(earlier, removals, strict=True))
        pairs.append(
            Comparison(
                current.program_key,
                current.year,
                previous.release_code,
                current.release_code,
                current.start,
                current.growth,
                current.growth - previous.growth,
                current.additions,
                removals,
                current.additions - previous.additions,
                contributions,
            )
        )
    return tuple(pairs), tuple(exclusions)


def _metrics(row: Comparison) -> dict[str, float]:
    values = {
        "growth": float(row.growth),
        "change_in_growth": float(row.change_in_growth),
        "additions": float(row.additions),
        "change_additions": float(row.change_additions),
        "transplant": float(sum(row.removals[:2])),
        "change_transplant": float(-sum(row.removal_contributions[:2])),
    }
    names = (
        "deceased",
        "living",
        "elsewhere",
        "transfer",
        "deaths",
        "deterioration",
        "recovery",
        "other",
    )
    for index, name in enumerate(names):
        values[name] = float(row.removals[index])
        values[f"change_{name}"] = float(-row.removal_contributions[index])
    return values | {f"{key}_per100": 100 * value / row.start for key, value in values.items()}


def summarize_counts(rows: tuple[Comparison, ...]) -> dict[str, Any]:
    """Describe counts for a stated group, including shrinking lists."""
    by_program: dict[str, list[dict[str, float]]] = defaultdict(list)
    for row in rows:
        by_program[row.program_key].append(_metrics(row))
    summary: dict[str, Any] = {"programs": len(by_program), "observations": len(rows)}
    if not rows:
        return summary
    for key in _metrics(rows[0]):
        summary[key] = median(
            median(values[key] for values in history) for history in by_program.values()
        )
    return summary


def summarize(pairs: tuple[Comparison, ...]) -> dict[str, Any]:
    """Give each program one weight, including when it supplies several years."""
    growing = tuple(row for row in pairs if row.growth > 0)
    by_program: dict[str, list[bool]] = defaultdict(list)
    for row in growing:
        by_program[row.program_key].append(row.transplant_increased)
    return {
        "eligible_observations": len(pairs),
        "eligible_programs": len({row.program_key for row in pairs}),
        "growing_observations": len(growing),
        "growing_programs": len(by_program),
        "increase_prevalence": mean(mean(history) for history in by_program.values())
        if by_program
        else None,
        "groups": {
            "increase": summarize_counts(tuple(row for row in growing if row.transplant_increased)),
            "no_increase": summarize_counts(
                tuple(row for row in growing if not row.transplant_increased)
            ),
        },
    }


def _material(summary: dict[str, Any], config: ScreenConfig) -> bool:
    group = summary["groups"]["increase"]
    return (
        summary["increase_prevalence"] is not None
        and summary["increase_prevalence"] >= config.minimum_prevalence
        and group.get("growth", 0) >= config.minimum_growth_count
        and group.get("growth_per100", 0) >= config.minimum_growth_per100
    )


def verdict(
    pairs: tuple[Comparison, ...],
    matched_by_year: dict[int, int],
    config: ScreenConfig,
) -> dict[str, Any]:
    """Select recurrence years from coverage alone, then apply every fixed check."""
    annual = {
        year: summarize(tuple(row for row in pairs if row.year == year))
        for year in config.source_years[1:]
    }
    usable = [
        year
        for year, summary in annual.items()
        if summary["eligible_observations"] >= config.minimum_pairs
        and matched_by_year.get(year, 0) >= summary["eligible_observations"]
        and summary["eligible_observations"] / matched_by_year[year] >= config.minimum_pair_coverage
        and summary["growing_programs"] >= config.minimum_growing
    ]
    runs = [
        tuple(range(year - config.minimum_years + 1, year + 1))
        for year in usable
        if all(prior in usable for prior in range(year - config.minimum_years + 1, year + 1))
    ]
    result: dict[str, Any] = {
        "verdict": "inconclusive",
        "annual": annual,
        "pooled": summarize(pairs),
        "recurrence_years": [],
    }
    if not runs:
        return result | {"reason": "Fewer than three consecutive years meet fixed coverage."}
    selected = runs[-1]
    recent = tuple(row for row in pairs if row.year in selected)
    common = set.intersection(
        *({row.program_key for row in recent if row.year == year} for year in selected)
    )
    common_annual = {
        year: summarize(
            tuple(row for row in recent if row.year == year and row.program_key in common)
        )
        for year in selected
    }
    lower, upper = config.size_boundaries
    size = {
        "under_100": summarize(tuple(row for row in recent if row.start < lower)),
        "100_to_499": summarize(tuple(row for row in recent if lower <= row.start < upper)),
        "500_or_more": summarize(tuple(row for row in recent if row.start >= upper)),
    }
    result.update(
        recurrence_years=selected,
        common_programs=len(common),
        common_annual=common_annual,
        size=size,
    )
    if (
        len(common) < config.minimum_common_programs
        or any(
            s["growing_programs"] < config.minimum_common_growing for s in common_annual.values()
        )
        or any(s["growing_programs"] < config.minimum_size_growing_programs for s in size.values())
    ):
        return result | {"reason": "The fixed common-program or size check lacks coverage."}
    passes = (
        all(_material(annual[year], config) for year in selected)
        and all(_material(s, config) for s in common_annual.values())
        and all(
            s["increase_prevalence"] >= config.minimum_size_prevalence
            and s["groups"]["increase"].get("growth_per100", 0) >= config.minimum_growth_per100
            for s in size.values()
        )
    )
    return result | {
        "verdict": "continue" if passes else "stop",
        "reason": "All fixed descriptive criteria pass."
        if passes
        else "Adequate coverage, but the fixed magnitude or recurrence criteria fail.",
        "primary_material_by_year": {year: _material(annual[year], config) for year in selected},
        "common_material_by_year": {
            year: _material(s, config) for year, s in common_annual.items()
        },
    }
