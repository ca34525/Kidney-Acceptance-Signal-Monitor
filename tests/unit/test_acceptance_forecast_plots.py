"""Forecast figures retain every error and keep retrospective evidence labeled."""

from typing import Any

import pytest

from kasm.acceptance_forecast.plots import _error_figure, render_error_plots


def _records() -> list[dict[str, Any]]:
    records = []
    for year, role in (
        (2024, "saved_validation_backtest"),
        (2025, "original_frozen_replay"),
    ):
        for model in ("persistence", "ridge"):
            for index, (truth, prediction) in enumerate(((0.01, 2.0), (2.0, 0.5), (1.0, 1.0))):
                records.append(
                    {
                        "program_key": f"NAME{index}:TX",
                        "target_cohort_year": year,
                        "evidence_role": role,
                        "model": model,
                        "target_oar": truth,
                        "predicted_oar": prediction,
                    }
                )
    return records


def test_figures_include_extremes_shared_scales_counts_and_saved_replay_role() -> None:
    figure = _error_figure(_records(), "percentage", {"run_id": "synthetic"})
    signed = figure.axes[::2]
    absolute = figure.axes[1::2]
    assert len(signed) == len(absolute) == 2
    assert signed[0].get_xlim() == signed[1].get_xlim()
    assert absolute[0].get_xlim() == absolute[1].get_xlim()
    assert signed[0].get_xlim()[0] <= -75.0
    assert signed[0].get_xlim()[1] >= 19900.0
    assert absolute[0].get_xlim()[1] >= 19900.0
    for axis in figure.axes:
        model_lines = [line for line in axis.lines if "n=3" in line.get_label()]
        assert len(model_lines) == 2
        assert {line.get_linestyle() for line in model_lines} == {"-", "--"}
        assert all(max(line.get_ydata()) == 100 for line in model_lines)
        assert all(len(line.get_xdata()) == 4 for line in model_lines)
    assert "2025" in signed[1].get_title(loc="left")
    assert "original frozen replay" in signed[1].get_title(loc="left")
    assert "published ratio" in signed[-1].get_xlabel()
    all_text = " ".join(text.get_text() for text in figure.texts)
    assert "synthetic" in all_text
    assert "not clinical or regulatory" in all_text
    assert "NAME" not in all_text


def test_render_returns_three_full_pngs_without_writing_to_disk() -> None:
    files = render_error_plots(_records(), {"run_id": "synthetic"})
    assert set(files) == {
        "error_distributions_ratio.png",
        "error_distributions_percentage.png",
        "error_distributions_log.png",
    }
    for payload in files.values():
        assert payload.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(payload) > 1000


def test_zero_errors_still_have_visible_axes_and_reach_all_programs() -> None:
    records = _records()[:1]
    records[0]["predicted_oar"] = records[0]["target_oar"]
    figure = _error_figure(records, "ratio", {})
    for axis in figure.axes:
        low, high = axis.get_xlim()
        assert low < high
        line = next(line for line in axis.lines if "n=1" in line.get_label())
        assert list(line.get_xdata()) == [0.0, 0.0]
        assert list(line.get_ydata()) == [0.0, 100.0]


@pytest.mark.parametrize("bad_value", [None, 0, -1, float("nan"), float("inf")])
def test_invalid_ratios_fail_before_rendering(bad_value: object) -> None:
    records = _records()
    records[-1]["target_oar"] = bad_value
    with pytest.raises(ValueError, match="ratio|positive|finite"):
        render_error_plots(records, {})


def test_empty_records_unknown_units_and_mixed_year_roles_fail() -> None:
    with pytest.raises(ValueError, match="record"):
        render_error_plots([], {})
    with pytest.raises(ValueError, match="unit"):
        _error_figure(_records(), "acceptance_rate", {})
    records = _records()
    records[0]["evidence_role"] = "retrospective_refit"
    with pytest.raises(ValueError, match="role"):
        render_error_plots(records, {})
