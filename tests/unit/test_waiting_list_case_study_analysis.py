"""The case study keeps event changes, annual growth and acceleration distinct."""

from dataclasses import replace

import pytest

from kasm.waiting_list.parse import REMOVAL_FIELDS, AnnualRecord
from kasm.waiting_list.screen import Comparison, compare_years
from kasm.waiting_list_case_study.analysis import (
    program_brief,
    select_examples,
    summarize_distributions,
)
from kasm.waiting_list_case_study.config import CaseStudyError


def annual(
    year: int,
    *,
    key: str = "AAAA:TX",
    start: int = 100,
    additions: int = 60,
    removals: tuple[int | None, ...] = (20, 10, 2, 3, 4, 5, 1, 5),
) -> AnnualRecord:
    return AnnualRecord(
        key,
        str(year),
        year,
        start,
        start + additions - sum(value for value in removals if value is not None),
        additions,
        removals,
        f"{year + 1}-07",
        "month",
        "https://example.org/report.xls",
        "a" * 64,
    )


def comparison(
    key: str,
    change: int,
    *,
    year: int = 2023,
    start: int = 100,
    growth: int = 10,
) -> Comparison:
    previous_transplants = max(0, -change)
    current_transplants = max(0, change)
    earlier = annual(
        year - 1,
        key=key,
        start=start,
        additions=previous_transplants,
        removals=(previous_transplants, 0, 0, 0, 0, 0, 0, 0),
    )
    current = annual(
        year,
        key=key,
        start=start,
        additions=current_transplants + max(growth, 0),
        removals=(current_transplants, 0, 0, 0, max(-growth, 0), 0, 0, 0),
    )
    return compare_years((earlier, current))[0][0]


def test_signed_distribution_retains_zero_ties_extreme_and_correct_denominator() -> None:
    pairs = tuple(
        comparison(f"AA{i:02}:TX", change, start=start)
        for i, (change, start) in enumerate(((-20, 100), (0, 100), (0, 1), (10, 10), (1000, 100)))
    )
    excluded = comparison("BBBB:TX", 5000, growth=0)
    earlier = comparison("CCCC:TX", 5000, year=2022)
    result = summarize_distributions((*pairs, excluded, earlier))
    assert result["years"] == [2023, 2024, 2025]
    first = result["annual"]["2023"]
    assert first["eligible_programs"] == 6
    assert first["growing_programs"] == 5
    assert first["frequency"] == {
        "increased": {"numerator": 2, "denominator": 5, "percent": 40.0},
        "unchanged": {"numerator": 2, "denominator": 5, "percent": 40.0},
        "decreased": {"numerator": 1, "denominator": 5, "percent": 20.0},
    }
    assert first["groups"]["all_growing"]["change_transplants"] == {
        "n": 5,
        "minimum": -20.0,
        "lower_quartile": 0.0,
        "median": 0.0,
        "upper_quartile": 10.0,
        "maximum": 1000.0,
    }
    increased = first["groups"]["increased"]
    assert increased["programs"] == 2
    assert increased["change_transplants"]["lower_quartile"] == 257.5
    assert increased["change_transplants"]["median"] == 505.0
    assert increased["change_transplants_per100"]["median"] == 550.0
    assert first["groups"]["all_growing"]["change_transplants_per100"]["upper_quartile"] == 100


def test_empty_population_is_unknown_distribution_not_zero() -> None:
    result = summarize_distributions(())["annual"]["2025"]
    assert result["frequency"]["increased"] == {
        "numerator": 0,
        "denominator": 0,
        "percent": None,
    }
    assert result["groups"]["increased"]["change_transplants"]["n"] == 0
    assert result["groups"]["increased"]["change_transplants"]["median"] is None


def test_selection_uses_common_programs_lower_middle_and_composite_key() -> None:
    pairs = tuple(
        comparison(key, change, year=year, start=start, growth=growth)
        for key, start, growth, change in (
            ("AAAA:TX", 100, 10, 1),
            ("AAAA:VA", 100, 10, 1),
            ("BBBB:TX", 200, 10, 2),
            ("CCCC:TX", 300, 10, 3),
            ("DDDD:TX", 100, 10, 0),
            ("EEEE:TX", 200, 10, -1),
            ("FFFF:TX", 100, -10, 1),
            ("GGGG:TX", 200, -10, -1),
            ("HHHH:TX", 300, -10, 0),
            ("IIII:TX", 400, 0, 1),
        )
        for year in (2023, 2024, 2025)
    )
    latest_only = comparison("0000:TX", 1, year=2025, start=1)
    result = select_examples((*pairs, latest_only))
    assert [item["program_key"] for item in result] == ["AAAA:VA", "DDDD:TX", "GGGG:TX"]
    assert [item["candidates"] for item in result] == [4, 2, 3]
    assert [item["selection_index"] for item in result] == [1, 0, 1]
    assert all(item["common_programs"] == 10 for item in result)
    assert result == select_examples(tuple(reversed((*pairs, latest_only))))


def test_empty_example_group_is_explicitly_unavailable() -> None:
    for item in select_examples(()):
        assert item["available"] is False
        assert item["reason"]
        assert item["candidates"] == 0
        assert item["program_key"] is None
        assert item["selection_index"] is None


def test_program_brief_keeps_both_equations_and_source_rows() -> None:
    previous = annual(2024)
    current = annual(2025, start=110, removals=(30, 10, 2, 3, 4, 5, 1, 5))
    pairs, excluded = compare_years((previous, current))
    assert not excluded
    result = program_brief((previous, current), pairs, "AAAA:TX", 2025)
    assert result["available"]
    assert result["previous"]["start"] == 100
    assert result["previous"]["growth"] == 10
    assert result["current"]["growth"] == 0
    assert result["previous"]["published_value"] == "2025-07"
    assert result["previous"]["published_precision"] == "month"
    assert result["current"]["removals_by_field"] == dict(
        zip(REMOVAL_FIELDS, current.removals, strict=True)
    )
    for name in ("previous", "current"):
        equation = result[name]["annual_equation"]
        assert (
            equation["end"] == equation["start"] + equation["additions"] - equation["removal_total"]
        )
        assert equation["residual"] == 0
    change = result["change"]
    assert change["growth"] == 0
    assert change["previous_growth"] == 10
    assert change["change_in_growth"] == -10
    assert change["change_transplants"] == 10
    assert change["denominator"] == 110
    assert change["removal_contributions"]["REMTXC"] == -10
    assert change["contributions_per100"]["REMTXC"] == pytest.approx(-1000 / 110)
    assert sum(change["contributions_per100"].values()) == pytest.approx(-1000 / 110)
    assert change["change_additions"] + sum(change["removal_contributions"].values()) == -10


@pytest.mark.parametrize("reason", ["missing", "residual", "boundary", "zero"])
def test_excluded_program_brief_preserves_unavailable_reason(reason: str) -> None:
    previous = annual(2024)
    current = annual(2025, start=110)
    if reason == "missing":
        current = replace(current, removals=(None, *current.removals[1:]))
    elif reason == "residual":
        current = replace(current, end=999)
    elif reason == "boundary":
        current = annual(2025, start=111)
    else:
        previous = annual(2024, start=0, additions=50)
        current = annual(2025, start=0)
    pairs, _ = compare_years((previous, current))
    result = program_brief((previous, current), pairs, "AAAA:TX", 2025)
    assert result["available"] is False
    assert result["reason_code"] == reason
    assert result["reason"]
    assert result["change"] is None
    if reason == "missing":
        assert result["current"]["removals_by_field"]["REMTXC"] is None


def test_missing_program_years_and_unsupported_year_are_explicit() -> None:
    row = annual(2025)
    assert program_brief((row,), (), "AAAA:TX", 2025)["reason_code"] == "missing_previous"
    assert program_brief((row,), (), "AAAA:VA", 2025)["reason_code"] == "missing_current"
    assert program_brief((row,), (), "AAAA:TX", 2022)["reason_code"] == "unsupported_year"


@pytest.mark.parametrize(
    "changes",
    [
        {"start": 0},
        {"start": True},
        {"removals": (1,)},
        {"removal_contributions": (1,)},
        {"growth": 11},
        {"change_in_growth": 11},
        {"program_key": "AAAA"},
        {"additions": -1},
    ],
)
def test_invalid_comparison_fails_before_calculation(changes: dict[str, object]) -> None:
    row = replace(comparison("AAAA:TX", 5), **changes)  # type: ignore[arg-type]
    with pytest.raises(CaseStudyError, match="comparison|accounting|program"):
        summarize_distributions((row,))


def test_duplicate_pairs_and_mismatched_source_counts_fail() -> None:
    row = comparison("AAAA:TX", 5)
    with pytest.raises(CaseStudyError, match="duplicate"):
        select_examples((row, row))
    previous = annual(2024)
    current = annual(2025, start=110)
    pairs, _ = compare_years((previous, current))
    different = annual(2025, start=110, additions=61)
    with pytest.raises(CaseStudyError, match="annual|match"):
        program_brief((previous, different), pairs, "AAAA:TX", 2025)
    with pytest.raises(CaseStudyError, match="duplicate"):
        program_brief((previous, previous, current), pairs, "AAAA:TX", 2025)
