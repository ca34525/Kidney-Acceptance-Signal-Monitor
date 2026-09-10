"""The report renders meaningful units without exposing a program ranking."""

from kasm.program_prediction.reporting import error_points, render_figures


def test_error_plot_does_not_rank_a_partial_success_model() -> None:
    metrics = [
        {
            "target": "registrations",
            "target_year": 2024,
            "model": "persistence",
            "mae": 50.5,
            "complete_forecast_coverage": True,
        },
        {
            "target": "registrations",
            "target_year": 2024,
            "model": "ridge_history",
            "mae": 1.0,
            "complete_forecast_coverage": False,
        },
    ]
    assert error_points(metrics, "registrations", "ridge_history", "persistence") == []


def test_render_exploratory_figures_with_missing_truth() -> None:
    rows = [
        {
            "target": "ddkt_removals",
            "target_year": year,
            "program_key": f"{i}:TX1",
            "model": model,
            "latest": 10.0,
            "previous": 11.0,
            "prediction": value,
            "observed": None if i == 1 else 8.0,
            "eligible": True,
            "origin_eligible": True,
            "status": "ok",
            "earlier_list_size": 50,
        }
        for year in (2021, 2022, 2023, 2024, 2025)
        for i in range(2)
        for model, value in (("persistence", 10.0), ("ridge_history", 9.0))
    ]
    questions = [{"target": "ddkt_removals", "model": "ridge_history", "direction": "decline"}]
    figures = render_figures(rows, {"ddkt_removals": "persistence"}, [], questions)
    assert set(figures) == {"error-improvement.png", "review-budget.png", "changes.png"}
    assert all(content.startswith(b"\x89PNG\r\n\x1a\n") for content in figures.values())
