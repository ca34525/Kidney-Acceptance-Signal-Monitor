"""Waiting-list growth and its acceleration have different meanings."""

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from kasm.waiting_list.config import ScreenConfig, ScreenError, load_config
from kasm.waiting_list.parse import AnnualRecord
from kasm.waiting_list.screen import compare_years, summarize, summarize_counts, verdict


def annual(
    year: int,
    *,
    key: str = "AAAA:TX",
    start: int = 100,
    additions: int = 50,
    transplant: int = 20,
    deaths: int = 10,
) -> AnnualRecord:
    return AnnualRecord(
        program_key=key,
        release_code=str(year),
        year=year,
        start=start,
        end=start + additions - transplant - deaths,
        additions=additions,
        removals=(transplant, 0, 0, 0, deaths, 0, 0, 0),
        published_value=f"{year + 1}-07",
        published_precision="month",
        source_url="https://example.org/report.xls",
        source_sha256="a" * 64,
    )


def test_growth_can_slow_while_transplant_removals_increase() -> None:
    earlier = annual(2020)
    later = annual(2021, start=120, transplant=30)
    pairs, exclusions = compare_years((earlier, later))
    assert not exclusions
    row = pairs[0]
    assert row.growth == 10
    assert row.change_in_growth == -10
    assert row.transplant_increased
    assert row.change_additions == 0
    assert row.removal_contributions == (-10, 0, 0, 0, 0, 0, 0, 0)
    assert row.change_in_growth_per100 == pytest.approx(-1000 / 120)
    assert row.change_in_growth == row.change_additions + sum(row.removal_contributions)


def test_both_growing_groups_and_death_changes_remain_visible() -> None:
    rows = (
        annual(2020),
        annual(2021, start=120, transplant=30),
        annual(2020, key="BBBB:TX"),
        annual(2021, key="BBBB:TX", start=120, transplant=10, deaths=20),
    )
    pairs, _ = compare_years(rows)
    result = summarize(pairs)
    assert result["growing_programs"] == 2
    assert result["increase_prevalence"] == 0.5
    groups = result["groups"]
    assert groups["increase"]["programs"] == 1
    assert groups["no_increase"]["change_deaths"] == 10
    assert groups["increase"]["change_transplant"] == 10
    assert groups["no_increase"]["change_transplant"] == -10


@pytest.mark.parametrize("kind", ["boundary", "missing", "residual", "zero"])
def test_unusable_pairs_are_excluded_with_reason(kind: str) -> None:
    previous = annual(2020)
    current = annual(2021, start=120)
    if kind == "boundary":
        current = annual(2021, start=121)
    elif kind == "missing":
        current = replace(current, additions=None)
    elif kind == "residual":
        current = replace(current, end=999)
    else:
        previous = annual(2020, start=0, additions=30, transplant=20)
        current = annual(2021, start=0)
    pairs, excluded = compare_years((previous, current))
    assert not pairs
    assert excluded[0]["reason"] == kind


def test_gaps_do_not_become_consecutive_and_duplicate_keys_fail() -> None:
    assert compare_years((annual(2018), annual(2020)))[0] == ()
    with pytest.raises(ScreenError, match="duplicate"):
        compare_years((annual(2020), annual(2020)))


def test_pooled_prevalence_weights_programs_equally() -> None:
    rows = (
        annual(2019),
        annual(2020, start=120, transplant=30),
        annual(2021, start=130, transplant=40),
        annual(2020, key="BBBB:TX"),
        annual(2021, key="BBBB:TX", start=120),
    )
    pairs, _ = compare_years(rows)
    # AAAA has one growing increase observation (2021 has zero growth), BBBB none.
    assert summarize(pairs)["increase_prevalence"] == 0.5


def test_settings_reject_changed_threshold_types_and_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    raw = asdict(ScreenConfig())
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert load_config(path) == ScreenConfig()
    for key, value in (
        ("minimum_prevalence", 0.24),
        ("promotion_allowed", 0),
        ("unexpected", True),
    ):
        changed = {**raw, key: value}
        path.write_text(json.dumps(changed), encoding="utf-8")
        with pytest.raises(ScreenError, match="fixed"):
            load_config(path)


def test_insufficient_history_is_inconclusive() -> None:
    assert verdict((), {}, ScreenConfig())["verdict"] == "inconclusive"


def test_shrinking_counts_keep_deaths_and_deterioration_visible() -> None:
    pairs, _ = compare_years((annual(2020), annual(2021, start=120, deaths=40)))
    summary = summarize_counts(pairs)
    assert summary["growth"] == -10
    assert summary["deaths"] == 40
    assert summary["change_deaths"] == 30
