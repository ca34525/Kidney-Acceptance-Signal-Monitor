"""Synthetic screens exercise the fixed decision without inspecting study results."""

from collections.abc import Callable
from dataclasses import replace

import pytest

from kasm.waiting_list.config import ScreenConfig
from kasm.waiting_list.screen import Comparison, summarize, verdict

YEARS = (2023, 2024, 2025)


def comparison(
    key: str,
    year: int,
    *,
    start: int = 200,
    growth: int = 10,
    increase: bool = True,
) -> Comparison:
    """Represent a reconciled growing list with a one-event transplant change."""
    contribution = -1 if increase else 0
    return Comparison(
        program_key=key,
        year=year,
        previous_release=str(year),
        current_release=str(year + 1),
        start=start,
        growth=growth,
        change_in_growth=contribution,
        additions=growth + 20,
        removals=(20, 0, 0, 0, 0, 0, 0, 0),
        change_additions=0,
        removal_contributions=(contribution, 0, 0, 0, 0, 0, 0, 0),
    )


def panel(
    years: tuple[int, ...] = YEARS,
    *,
    increased: Callable[[int, int], bool] = lambda _size, index: index % 4 == 0,
) -> tuple[Comparison, ...]:
    """Forty programs in each size group provide enough history for every check."""
    return tuple(
        comparison(
            f"{size}{index:03}:TX",
            year,
            start=start,
            growth=growth,
            increase=increased(size, index),
        )
        for year in years
        for size, (start, growth) in enumerate(((50, 10), (200, 10), (500, 25)))
        for index in range(40)
    )


def test_continue_includes_equality_at_prevalence_magnitude_and_coverage_limits() -> None:
    result = verdict(panel(), dict.fromkeys(YEARS, 150), ScreenConfig())

    assert result["verdict"] == "continue"
    assert result["recurrence_years"] == YEARS
    assert result["common_programs"] == 120
    for year in YEARS:
        annual = result["annual"][year]
        assert annual["increase_prevalence"] == 0.25
        assert annual["groups"]["increase"]["growth"] == 10
        assert annual["groups"]["increase"]["growth_per100"] == 5
        assert result["primary_material_by_year"][year]
        assert result["common_material_by_year"][year]


def test_adequate_screen_stops_when_primary_prevalence_is_too_small() -> None:
    rows = panel(increased=lambda _size, index: index % 5 == 0)
    result = verdict(rows, dict.fromkeys(YEARS, 120), ScreenConfig())

    assert result["verdict"] == "stop"
    assert not any(result["primary_material_by_year"].values())
    assert all(summary["growing_programs"] == 40 for summary in result["size"].values())


def test_adequate_screen_stops_when_growth_count_is_below_fixed_magnitude() -> None:
    rows = tuple(
        replace(row, start=100 if row.start == 200 else row.start, growth=9, additions=29)
        if row.start < 500
        else row
        for row in panel()
    )
    result = verdict(rows, dict.fromkeys(YEARS, 120), ScreenConfig())

    assert result["verdict"] == "stop"
    assert result["annual"][2025]["groups"]["increase"]["growth"] == 9
    assert all(
        summary["groups"]["increase"]["growth_per100"] >= 5 for summary in result["size"].values()
    )


def test_adequate_screen_stops_when_pattern_is_absent_in_one_size_group() -> None:
    rows = panel(increased=lambda size, index: size > 0 and index % 2 == 0)
    result = verdict(rows, dict.fromkeys(YEARS, 120), ScreenConfig())

    assert result["verdict"] == "stop"
    assert all(result["primary_material_by_year"].values())
    assert all(result["common_material_by_year"].values())
    assert result["size"]["under_100"]["growing_programs"] == 40
    assert result["size"]["under_100"]["groups"]["increase"]["programs"] == 0


def test_adequate_screen_stops_when_turnover_hides_weak_common_program_pattern() -> None:
    stable = panel(increased=lambda _size, index: index % 5 == 0)
    newcomers = tuple(
        comparison(
            f"new-{year}-{size}-{index}:TX",
            year,
            start=start,
            growth=growth,
        )
        for year in YEARS
        for size, (start, growth) in enumerate(((50, 10), (200, 10), (500, 25)))
        for index in range(10)
    )
    result = verdict(stable + newcomers, dict.fromkeys(YEARS, 150), ScreenConfig())

    assert result["verdict"] == "stop"
    assert all(result["primary_material_by_year"].values())
    assert not any(result["common_material_by_year"].values())
    assert result["common_programs"] == 120
    assert all(summary["increase_prevalence"] >= 0.15 for summary in result["size"].values())


@pytest.mark.parametrize("insufficiency", ["eligible", "fraction", "growing", "gap"])
def test_inadequate_annual_coverage_is_inconclusive(insufficiency: str) -> None:
    rows = panel()
    matched = dict.fromkeys(YEARS, 120)
    if insufficiency == "eligible":
        rows = tuple(row for row in rows if int(row.program_key[1:4]) < 30)
    elif insufficiency == "fraction":
        matched[2025] = 151
    elif insufficiency == "growing":
        rows = tuple(
            replace(row, growth=0, additions=20) if int(row.program_key[1:4]) >= 9 else row
            for row in rows
        )
    else:
        rows = tuple(row for row in rows if row.year != 2024)

    result = verdict(rows, matched, ScreenConfig())
    assert result["verdict"] == "inconclusive"
    assert result["recurrence_years"] == []


def test_missing_matched_source_denominator_cannot_pass_coverage() -> None:
    result = verdict(panel(), {2023: 120, 2024: 120}, ScreenConfig())

    assert result["verdict"] == "inconclusive"
    assert result["recurrence_years"] == []


@pytest.mark.parametrize("check", ["common_programs", "common_growing", "size_programs"])
def test_inadequate_sensitivity_population_is_inconclusive(check: str) -> None:
    rows = panel()
    if check == "common_programs":
        rows = tuple(
            replace(row, program_key=f"{row.program_key}-{row.year}")
            if int(row.program_key[0]) * 40 + int(row.program_key[1:4]) >= 79
            else row
            for row in rows
        )
    elif check == "common_growing":
        rows = tuple(
            replace(row, growth=0, additions=20) if int(row.program_key[1:4]) >= 6 else row
            for row in rows
        ) + tuple(
            comparison(f"new-{year}-{size}-{index}:TX", year, start=start, growth=growth)
            for year in YEARS
            for size, (start, growth) in enumerate(((50, 10), (200, 10), (500, 25)))
            for index in range(5)
        )
    else:
        rows = tuple(
            replace(row, start=200) if row.start < 100 and int(row.program_key[1:4]) >= 9 else row
            for row in rows
        )

    matched = {year: sum(row.year == year for row in rows) for year in YEARS}
    result = verdict(rows, matched, ScreenConfig())
    assert result["verdict"] == "inconclusive"
    assert result["recurrence_years"] == YEARS


def test_latest_covered_years_are_selected_even_when_earlier_pattern_is_stronger() -> None:
    rows = tuple(
        replace(row, removal_contributions=(0,) * 8, change_in_growth=0)
        if row.year >= 2024
        else row
        for row in panel((2021, 2022, 2023, 2024, 2025))
    )
    result = verdict(rows, dict.fromkeys(range(2021, 2026), 120), ScreenConfig())

    assert result["verdict"] == "stop"
    assert result["recurrence_years"] == YEARS
    assert result["annual"][2021]["increase_prevalence"] == 0.25
    assert result["annual"][2025]["increase_prevalence"] == 0


def test_pooled_prevalence_and_growth_give_short_and_long_histories_equal_weight() -> None:
    rows = (
        comparison("AAAA:TX", 2023, growth=10),
        comparison("AAAA:TX", 2024, growth=10),
        comparison("AAAA:TX", 2025, growth=10),
        comparison("BBBB:TX", 2025, growth=100),
        comparison("CCCC:TX", 2025, growth=10, increase=False),
    )
    result = summarize(rows)

    assert result["growing_observations"] == 5
    assert result["growing_programs"] == 3
    assert result["increase_prevalence"] == pytest.approx(2 / 3)
    assert result["groups"]["increase"]["growth"] == 55
    assert result["groups"]["increase"]["growth_per100"] == 27.5
