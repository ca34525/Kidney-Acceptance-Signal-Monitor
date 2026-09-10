"""A saved discovery choice must precede any later-period comparison."""

import json
from pathlib import Path
from typing import Any

import pytest

from kasm.cli import build_parser
from kasm.program_prediction.commands import validate_selection


def _discovery() -> dict[str, Any]:
    return {
        "metrics.json": {
            "summary_metrics": [
                {"target": "ddkt_removals", "model": "ridge_history", "coverage": 1.0}
            ]
        },
        "comparators.json": {"ddkt_removals": "persistence"},
        "predictions.json": [
            {
                "target": "ddkt_removals",
                "model": "ridge_history",
                "target_year": year,
                "eligible": True,
                "prediction": 2.0,
                "status": "ok",
            }
            for year in (2021, 2022, 2023)
        ],
    }


def test_shortlist_requires_discovery_coverage_and_written_question() -> None:
    choice = {
        "questions": [
            {
                "target": "ddkt_removals",
                "model": "ridge_history",
                "direction": "decline",
                "question": "Prioritize activity decline review?",
                "rationale": "Earlier error and review comparisons motivate this question.",
            }
        ]
    }
    assert validate_selection(choice, _discovery())[0]["target"] == "ddkt_removals"
    with pytest.raises(ValueError, match="question|shortlist"):
        validate_selection({"questions": [{}]}, _discovery())
    bad = _discovery()
    bad["predictions.json"][0]["prediction"] = None
    with pytest.raises(ValueError, match="coverage|failure"):
        validate_selection(choice, bad)
    with pytest.raises(ValueError, match="two|2"):
        validate_selection({"questions": choice["questions"] * 3}, _discovery())


def test_cli_separates_build_discovery_choice_and_later_scoring() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "program-prediction",
            "assess",
            "--run-id",
            "later",
            "--panel-run",
            "panel",
            "--shortlist-run",
            "choice",
        ]
    )
    assert args.prediction_command == "assess"
    assert args.shortlist_run == "choice"
    with pytest.raises(SystemExit):
        parser.parse_args(["program-prediction", "assess", "--run-id", "later"])


def test_stages_preserve_inputs_and_later_cannot_run_without_saved_choice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kasm.cli import main
    from kasm.program_prediction import commands, modeling, panel
    from kasm.program_prediction.config import SprintConfig
    from kasm.program_prediction.runs import load_run

    config = SprintConfig()
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config.raw))
    monkeypatch.setattr(
        commands,
        "provenance",
        lambda root, config_path, **kwargs: {
            "stage": kwargs["stage"],
            "configuration_sha256": commands.file_hash(config_path),
            "parents": {
                role: {
                    "run_id": run,
                    "completion_sha256": commands.file_hash(
                        root / "data/research/program-prediction-0031" / run / "completion.json"
                    ),
                }
                for role, run in kwargs["parents"].items()
            },
        },
    )
    monkeypatch.setattr(
        panel,
        "build_panel",
        lambda root, config: panel.PanelBuild(
            [{"retained_input": True}], {"h_latest": {"block": "history"}}, {}, {}
        ),
    )
    calls = []

    def fake_evaluate(rows: Any, config: Any, years: Any, features: Any, **kwargs: Any) -> Any:
        calls.append(years)
        predictions = [
            {
                "target": "ddkt_removals",
                "target_year": year,
                "program_key": f"{i}:TX1",
                "model": model,
                "latest": 10.0,
                "previous": 12.0,
                "last_change": -2.0,
                "prediction": prediction,
                "observed": None if i == 3 else 5.0,
                "eligible": True,
                "origin_eligible": True,
                "status": "ok",
                "earlier_list_size": 50,
                "origin_release": str(year),
            }
            for year in years
            for i in range(4)
            for model, prediction in (
                ("persistence", 10.0),
                ("recent_mean", 11.0),
                ("damped_trend", 9.0),
                ("ridge_history", 6.0),
            )
        ]
        return {"predictions": predictions, "folds": [], "failures": [], "exclusions": []}

    monkeypatch.setattr(modeling, "evaluate", fake_evaluate)

    def run(stage: str, run_id: str, *options: str) -> int:
        return main(
            ["program-prediction", stage, "--run-id", run_id, "--config", str(path), *options]
        )

    assert run("build", "panel") == 0
    assert run("assess", "premature", "--panel-run", "panel", "--shortlist-run", "absent") == 1
    assert not calls
    assert run("screen", "discovery", "--panel-run", "panel") == 0
    selection = tmp_path / "selection.json"
    selection.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "target": "ddkt_removals",
                        "model": "ridge_history",
                        "direction": "decline",
                        "question": "Review declines?",
                        "rationale": "Fixed fixture discovery improvement",
                    }
                ]
            }
        )
    )
    assert (
        run("shortlist", "choice", "--discovery-run", "discovery", "--selection", str(selection))
        == 0
    )
    assert run("assess", "later", "--panel-run", "panel", "--shortlist-run", "choice") == 0
    assert calls == [(2021, 2022, 2023), (2024, 2025)]
    later = load_run(tmp_path, "later", stage="assess")
    assert any(row["observed"] is None for row in later["predictions.json"])
    assert len(later["decision-differences.json"]) == 9
    assert (
        run(
            "report",
            "report",
            "--discovery-run",
            "discovery",
            "--assessment-run",
            "later",
            "--shortlist-run",
            "choice",
        )
        == 0
    )
    assert load_run(tmp_path, "report", stage="report")["report.html"].startswith(b"<!doctype")
    assert run("screen", "other-discovery", "--panel-run", "panel") == 0
    assert (
        run(
            "report",
            "mixed-report",
            "--discovery-run",
            "other-discovery",
            "--assessment-run",
            "later",
            "--shortlist-run",
            "choice",
        )
        == 1
    )
    assert run("screen", "discovery", "--panel-run", "panel") == 1
    path.write_text(path.read_text() + " ")
    assert run("screen", "changed", "--panel-run", "panel") == 1


def test_followup_cannot_name_a_different_parent_shortlist(tmp_path: Path) -> None:
    from dataclasses import replace

    from kasm.program_prediction.commands import validate_followup
    from kasm.program_prediction.config import SprintConfig
    from kasm.program_prediction.runs import publish_run

    config = replace(
        SprintConfig(),
        round_id="followup_1",
        question="Remove OAR inputs?",
        parent_run="earlier",
        omit_oar_features=True,
    )
    publish_run(tmp_path, "earlier", {"shortlist.json": b"{}"}, {"stage": "assess", "parents": {}})
    with pytest.raises(ValueError, match="shortlist"):
        validate_followup(tmp_path, config, "unrelated")


def test_cli_accepts_explicit_final_review_followup() -> None:
    args = build_parser().parse_args(
        [
            "program-prediction",
            "reassess",
            "--run-id",
            "followup-2-review",
            "--config",
            "configs/program_prediction/followup_2_review.json",
        ]
    )
    assert args.prediction_command == "reassess"
