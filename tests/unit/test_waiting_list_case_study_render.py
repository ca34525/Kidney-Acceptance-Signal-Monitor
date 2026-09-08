"""Briefs preserve source counts and distribution figures retain every observation."""

from copy import deepcopy
from typing import Any

from kasm.waiting_list.parse import REMOVAL_FIELDS
from kasm.waiting_list.screen import Comparison
from kasm.waiting_list_case_study.render import (
    _distribution_figure,
    _frequency_figure,
    render_case_study,
    render_program_brief,
)


def brief_fixture() -> dict[str, Any]:
    previous = {
        "year": 2024,
        "start": 100,
        "end": 120,
        "additions": 50,
        "removals_by_field": dict(zip(REMOVAL_FIELDS, (10, 5, 2, 3, 4, 2, 0, 4), strict=True)),
        "growth": 20,
        "removal_total": 30,
        "annual_equation": {"residual": 0},
        "published_value": "2025-07",
        "published_precision": "month",
        "release_code": "2505",
        "source_url": "https://srtr.hrsa.gov/example",
        "source_sha256": "a" * 64,
    }
    current = previous | {
        "year": 2025,
        "start": 120,
        "end": 130,
        "additions": 60,
        "removals_by_field": dict(zip(REMOVAL_FIELDS, (30, 5, 2, 3, 4, 2, 0, 4), strict=True)),
        "growth": 10,
        "removal_total": 50,
        "annual_equation": {"residual": 0},
        "published_value": "2026-07-07",
        "published_precision": "day",
        "release_code": "2605",
    }
    contributions = dict(zip(REMOVAL_FIELDS, (-20, 0, 0, 0, 0, 0, 0, 0), strict=True))
    return {
        "available": True,
        "reason": None,
        "program_key": "TEST:TX",
        "year": 2025,
        "previous": previous,
        "current": current,
        "change": {
            "growth": 10,
            "previous_growth": 20,
            "change_in_growth": -10,
            "change_transplants": 20,
            "denominator": 120,
            "change_additions": 10,
            "removal_contributions": contributions,
            "contributions_per100": {
                key: 100 * value / 120 for key, value in {"ADDCEN": 10, **contributions}.items()
            },
            "growth_per100": 100 * 10 / 120,
            "change_in_growth_per100": -100 * 10 / 120,
            "change_transplants_per100": 100 * 20 / 120,
        },
    }


def test_brief_distinguishes_growth_from_slowing_and_keeps_all_categories() -> None:
    html = render_program_brief(brief_fixture(), {"run_id": "synthetic"})
    assert "120 = 100 + 50 − 30" in html
    assert "130 = 120 + 60 − 50" in html
    assert "10 − 20 = −10" in html
    assert "July 2025" in html
    assert "July 1, 2025" not in html
    assert "July 7, 2026" in html
    assert "per 100 current starting registrations" in html
    assert "120" in html
    assert "−16.67" in html
    for label in (
        "Deceased donor",
        "Living donor",
        "Transplant elsewhere",
        "Transfer",
        "Deaths",
        "Deterioration",
        "Recovery",
        "Other removals",
    ):
        assert label in html
    assert "not clinical or regulatory decision support" in html
    assert "synthetic" in html
    assert "<script" not in html
    assert "<link" not in html


def test_unavailable_brief_keeps_reported_zero_and_unknown_distinct_and_escapes() -> None:
    brief = deepcopy(brief_fixture())
    brief.update(available=False, reason="Missing count <source>", program_key="<script>x</script>")
    brief["current"]["removals_by_field"]["REMREC"] = None
    brief["change"] = None
    html = render_program_brief(brief, {"run_id": "unsafe <value>"})
    assert "Unavailable" in html
    assert "Missing count &lt;source&gt;" in html
    assert "Not reported" in html
    assert ">0<" in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "unsafe &lt;value&gt;" in html
    assert "<script" not in html


def test_unsupported_brief_has_explicit_unavailable_explanation() -> None:
    brief = {
        "available": False,
        "reason": "Only 2023–2025 comparisons are supported.",
        "program_key": "TEST:TX",
        "year": 2020,
        "previous": None,
        "current": None,
        "change": None,
    }
    html = render_program_brief(brief, {"run_id": "synthetic"})
    assert "Unavailable" in html
    assert "Only 2023–2025" in html
    assert "Not reported" in html


def test_unreconciled_annual_record_does_not_display_a_false_equation() -> None:
    brief = brief_fixture()
    brief.update(available=False, reason="Annual counts do not reconcile.", change=None)
    brief["current"]["end"] = 131
    brief["current"]["annual_equation"] = {"residual": 1}
    html = render_program_brief(brief, {})
    assert "131 = 120 + 60 − 50" not in html
    assert "counts do not reconcile" in html


def distribution_pairs() -> tuple[Comparison, ...]:
    return tuple(
        Comparison(
            f"T{index:03}:TX",
            year,
            "old",
            "new",
            start,
            growth,
            0,
            0,
            (0,) * 8,
            0,
            (-change,) + (0,) * 7,
        )
        for year in (2023, 2024, 2025)
        for index, (start, growth, change) in enumerate(
            ((10, 1, -2000), (100, 1, 0), (100, 1, 1), (1, 1, 9000), (1, -1, 99000))
        )
    )


def test_distribution_draws_every_growing_program_with_full_signed_extent() -> None:
    figure = _distribution_figure(distribution_pairs(), [2023, 2024, 2025], {})
    assert len(figure.axes) == 2
    for axis, expected in zip(
        figure.axes, ([-2000, 0, 1, 9000], [-20000, 0, 1, 900000]), strict=True
    ):
        assert len(axis.collections) == 3
        for points in axis.collections:
            assert sorted(points.get_offsets()[:, 0]) == expected
        lower, upper = axis.get_xlim()
        assert lower <= min(expected)
        assert upper >= max(expected)


def test_frequency_labels_small_unchanged_group_with_its_denominator() -> None:
    summary = {
        "years": [2025],
        "annual": {
            "2025": {
                "frequency": {
                    "increased": {"numerator": 58, "denominator": 137, "percent": 100 * 58 / 137},
                    "unchanged": {"numerator": 5, "denominator": 137, "percent": 100 * 5 / 137},
                    "decreased": {"numerator": 74, "denominator": 137, "percent": 100 * 74 / 137},
                }
            }
        },
    }
    labels = [label.get_text() for label in _frequency_figure(summary, {}).axes[0].texts]
    assert "5/137\n3.6%" in labels


def test_case_study_is_self_contained_has_exact_tables_and_reproducible_figures() -> None:
    statistic = {
        "n": 4,
        "minimum": -2000,
        "lower_quartile": -500,
        "median": 0.5,
        "upper_quartile": 2250.75,
        "maximum": 9000,
    }
    summary = {
        "years": [2023, 2024, 2025],
        "annual": {
            str(year): {
                "eligible_programs": 5,
                "growing_programs": 4,
                "frequency": {
                    direction: {"numerator": count, "denominator": 4, "percent": 25 * count}
                    for direction, count in (("increased", 2), ("unchanged", 1), ("decreased", 1))
                },
                "groups": {
                    group: {
                        "programs": 4 if group == "all_growing" else 2,
                        "change_transplants": statistic,
                        "change_transplants_per100": statistic,
                    }
                    for group in ("all_growing", "increased")
                },
            }
            for year in (2023, 2024, 2025)
        },
    }
    example = {
        "group": "growing_increased",
        "available": True,
        "reason": None,
        "program_key": "TEST:TX",
        "candidates": 5,
        "selection_index": 2,
        "common_programs": 7,
    }
    provenance = {
        "run_id": "synthetic",
        "build_time_utc": "2026-09-08T00:00:00Z",
        "source_vintages": [brief_fixture()["previous"], brief_fixture()["current"]],
        "previous_summary": {
            "common_programs": 7,
            "verdict": "continue",
            "common_annual": {
                "2025": {
                    "growing_programs": 4,
                    "increase_prevalence": 0.5,
                    "groups": {"increase": {"programs": 2}},
                }
            },
            "size": {
                "under_100": {
                    "growing_programs": 3,
                    "increase_prevalence": 0.5,
                    "groups": {"increase": {"growth_per100": 12.0}},
                }
            },
        },
    }
    args = (summary, [example], [brief_fixture()], distribution_pairs(), provenance)
    output = render_case_study(*args)
    assert output == render_case_study(*args)
    html = output["case_study.html"].decode()
    assert html.count("<svg") == 3
    assert "2/4 (50.0%)" in html
    assert "middle half" in html
    assert "patient probability" in html
    assert "TEST:TX" in html
    assert "lower middle" in html
    assert "July 2025" in html
    assert "July 7, 2026" in html
    assert "9000" in output["observations.csv"].decode()
    assert "99000" not in output["observations.csv"].decode()
    assert "Decreased" in output["supporting_tables.html"].decode()
    assert "Retained common-program results" in output["supporting_tables.html"].decode()
    assert "Starting lists under 100" in output["supporting_tables.html"].decode()
    assert len([name for name in output if name.endswith(".svg")]) == 3
    assert all(output[name].startswith(b"\x89PNG") for name in output if name.endswith(".png"))
