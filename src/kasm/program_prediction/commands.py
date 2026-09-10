"""Run the sprint in separate, traceable discovery and later-assessment stages."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from kasm.acceptance_forecast.inputs import ensure_local_path, file_hash
from kasm.acceptance_forecast.runs import json_bytes
from kasm.program_prediction.runs import (
    load_run,
    provenance,
    publish_run,
    validate_destination,
)


def add_parser(commands: Any) -> None:
    """Expose explicit dependencies so later scoring cannot skip a saved choice."""
    parser = commands.add_parser("program-prediction")
    stages = parser.add_subparsers(dest="prediction_command", required=True)
    for name in ("build", "screen", "shortlist", "assess", "report", "reassess"):
        stage = stages.add_parser(name)
        stage.add_argument("--run-id", required=True)
        stage.add_argument(
            "--config", type=Path, default=Path("configs/program_prediction/experiment.json")
        )
        if name in ("screen", "assess"):
            stage.add_argument("--panel-run", required=True)
        if name in ("shortlist", "report"):
            stage.add_argument("--discovery-run", required=True)
        if name == "shortlist":
            stage.add_argument("--selection", type=Path, required=True)
        if name in ("assess", "report"):
            stage.add_argument("--shortlist-run", required=True)
        if name == "report":
            stage.add_argument("--assessment-run", required=True)


def validate_selection(
    selection: dict[str, Any], discovery: dict[str, Any]
) -> list[dict[str, str]]:
    """Require a written decision question and complete discovery forecast coverage."""
    questions = selection.get("questions")
    if not isinstance(questions, list) or len(questions) > 2:
        raise ValueError("The shortlist must contain at most two questions.")
    result: list[dict[str, str]] = []
    for question in questions:
        fields = ("target", "model", "direction", "question", "rationale")
        if not isinstance(question, dict) or any(
            not isinstance(question.get(key), str) or not question[key].strip() for key in fields
        ):
            raise ValueError(
                "Each shortlist question needs target, model, direction and rationale."
            )
        if question["direction"] not in ("growth", "decline"):
            raise ValueError("A shortlist question must specify growth or decline.")
        rows = [
            row
            for row in discovery["predictions.json"]
            if row["target"] == question["target"]
            and row["model"] == question["model"]
            and row["eligible"]
        ]
        if not rows or {row["target_year"] for row in rows} != {2021, 2022, 2023}:
            raise ValueError("Shortlist candidate needs coverage of all three discovery years.")
        if any(
            row.get("prediction") is None
            or not math.isfinite(row["prediction"])
            or row.get("status") != "ok"
            for row in rows
        ):
            raise ValueError(
                "Incomplete forecast coverage or a model failure prevents shortlisting."
            )
        if question["target"] not in discovery["comparators.json"]:
            raise ValueError("The shortlist target has no saved discovery baseline comparator.")
        if any(item["target"] == question["target"] for item in result):
            raise ValueError("Each shortlist question must have a distinct target.")
        result.append({key: question[key] for key in fields})
    return result


def _same_config(run: dict[str, Any], config_path: Path) -> None:
    if run["completion.json"]["provenance"]["configuration_sha256"] != file_hash(config_path):
        raise ValueError("Configuration identity differs from the saved stage; build a new run.")


def _build(root: Path, args: argparse.Namespace) -> tuple[dict[str, bytes], dict[str, str]]:
    from kasm.program_prediction.config import load_config
    from kasm.program_prediction.panel import build_panel

    config = load_config(args.config)
    panel = build_panel(root, config)
    return {
        "panel.json": json_bytes(panel.rows),
        "feature-map.json": json_bytes(panel.feature_map),
        "source-ledger.json": json_bytes(panel.source_ledger),
        "panel-qa.json": json_bytes(panel.qa),
    }, validate_followup(root, config)


def validate_followup(root: Path, config: Any, shortlist: str | None = None) -> dict[str, str]:
    """Bind an adapted round to its preserved preceding assessment and discovery choice."""
    if config.round_id == "initial":
        return {}
    previous = load_run(root, config.parent_run, stage="assess")
    if shortlist is not None:
        saved = previous["completion.json"]["provenance"].get("parents", {}).get("shortlist", {})
        if saved.get("run_id") != shortlist:
            raise ValueError("Follow-up shortlist differs from its configured parent assessment.")
    return {"prior_assessment": config.parent_run}


def _screen(root: Path, args: argparse.Namespace) -> tuple[dict[str, bytes], dict[str, str]]:
    from kasm.program_prediction.config import load_config
    from kasm.program_prediction.metrics import freeze_comparators, summarize
    from kasm.program_prediction.modeling import evaluate

    config = load_config(args.config)
    panel = load_run(root, args.panel_run, stage="build")
    _same_config(panel, args.config)
    parents = validate_followup(root, config)
    evaluation = evaluate(
        panel["panel.json"], config, config.discovery_years, panel["feature-map.json"]
    )
    predictions = evaluation["predictions"]
    comparators = freeze_comparators(predictions)
    return {
        "predictions.json": json_bytes(predictions),
        "folds.json": json_bytes(evaluation["folds"]),
        "failures.json": json_bytes(evaluation["failures"]),
        "exclusions.json": json_bytes(evaluation["exclusions"]),
        "metrics.json": json_bytes(summarize(predictions)),
        "comparators.json": json_bytes(comparators),
        "error-differences.json": json_bytes(_error_intervals(predictions, comparators, config)),
    }, {"panel": args.panel_run, **parents}


def _error_intervals(
    predictions: list[dict[str, Any]], comparators: dict[str, str], config: Any
) -> list[dict[str, Any]]:
    from kasm.program_prediction.metrics import bootstrap_error_difference

    differences = []
    for target, comparator in comparators.items():
        for model in sorted({row["model"] for row in predictions if row["target"] == target}):
            if model != comparator:
                differences.append(
                    bootstrap_error_difference(
                        predictions,
                        target=target,
                        candidate=model,
                        comparator=comparator,
                        resamples=config.bootstrap_resamples,
                        seed=config.seed,
                    )
                )
    return differences


def _shortlist(root: Path, args: argparse.Namespace) -> tuple[dict[str, bytes], dict[str, str]]:
    discovery = load_run(root, args.discovery_run, stage="screen")
    _same_config(discovery, args.config)
    ensure_local_path(args.selection.resolve(), root)
    selection = json.loads(args.selection.read_bytes())
    if not isinstance(selection, dict):
        raise ValueError("Shortlist selection must be a JSON object.")
    questions = validate_selection(selection, discovery)
    return {
        "shortlist.json": json_bytes({"questions": questions, "selection": selection}),
        "comparators.json": json_bytes(discovery["comparators.json"]),
    }, {"discovery": args.discovery_run}


def _assess(root: Path, args: argparse.Namespace) -> tuple[dict[str, bytes], dict[str, str]]:
    from kasm.program_prediction.config import load_config
    from kasm.program_prediction.metrics import (
        bootstrap_decision_difference,
        review_budget,
        summarize,
    )
    from kasm.program_prediction.modeling import evaluate

    config = load_config(args.config)
    panel = load_run(root, args.panel_run, stage="build")
    _same_config(panel, args.config)
    choice = load_run(root, args.shortlist_run, stage="shortlist")
    parents = validate_followup(root, config, args.shortlist_run)
    questions = choice["shortlist.json"]["questions"]
    # A later exploratory feature-removal round retains the original discovery questions.
    if config.raw["round_id"] == "initial":
        _same_config(choice, args.config)
    evaluation = evaluate(
        panel["panel.json"],
        config,
        config.later_years,
        panel["feature-map.json"],
        prioritized_targets=tuple(
            question["target"] for question in questions if question["target"] in config.targets
        ),
    )
    predictions = evaluation["predictions"]
    reviews, decision_differences = [], []
    for question in questions:
        target, model = question["target"], question["model"]
        if not any(row["target"] == target for row in predictions):
            continue
        comparator = choice["comparators.json"][target]
        reviews.append(
            {
                "question": question,
                **review_budget(
                    predictions,
                    target=target,
                    model=model,
                    direction=question["direction"],
                    budgets=config.budgets,
                    seed=config.seed,
                    comparator=comparator,
                ),
            }
        )
        review = reviews[-1]
        for review_comparator in dict.fromkeys(("last_change", "latest_level", comparator)):
            if model == review_comparator:
                continue
            for budget in config.budgets:
                try:
                    difference = bootstrap_decision_difference(
                        review["selections"],
                        target=target,
                        candidate=model,
                        comparator=review_comparator,
                        budget=budget,
                        years=config.later_years,
                        resamples=config.bootstrap_resamples,
                        seed=config.seed,
                    )
                except ValueError as exc:
                    difference = {
                        "target": target,
                        "candidate": model,
                        "comparator": review_comparator,
                        "budget": budget,
                        "status": "unavailable",
                        "error": str(exc),
                    }
                decision_differences.append(difference)
    return {
        "predictions.json": json_bytes(predictions),
        "folds.json": json_bytes(evaluation["folds"]),
        "failures.json": json_bytes(evaluation["failures"]),
        "exclusions.json": json_bytes(evaluation["exclusions"]),
        "metrics.json": json_bytes(summarize(predictions)),
        "comparators.json": json_bytes(choice["comparators.json"]),
        "reviews.json": json_bytes(reviews),
        "error-differences.json": json_bytes(
            _error_intervals(predictions, choice["comparators.json"], config)
        ),
        "decision-differences.json": json_bytes(decision_differences),
        "shortlist.json": json_bytes(choice["shortlist.json"]),
    }, {"panel": args.panel_run, "shortlist": args.shortlist_run, **parents}


def run_command(args: argparse.Namespace) -> int:
    """Publish successful stages atomically and return actionable errors to the CLI."""
    root = Path.cwd()
    try:
        validate_destination(root, args.run_id)
        ensure_local_path(args.config.resolve(), root)
        settings = args.config.read_bytes()
        before = provenance(root, args.config, stage=args.prediction_command, parents={})
        if args.prediction_command == "report":
            from kasm.program_prediction.reporting import report_files

            files, parents = report_files(root, args)
        elif args.prediction_command == "reassess":
            from kasm.program_prediction.reassessment import reassess

            files, parents = reassess(root, args.config)
        else:
            functions = {
                "build": _build,
                "screen": _screen,
                "shortlist": _shortlist,
                "assess": _assess,
            }
            files, parents = functions[args.prediction_command](root, args)
        after = provenance(root, args.config, stage=args.prediction_command, parents=parents)
        stable_fields = set(before) - {"build_timestamp_utc", "parents"}
        if any(before[field] != after[field] for field in stable_fields):
            raise ValueError("Code, settings or revision changed during the run; use a new run ID.")
        files["settings.json"] = settings
        metadata = {
            **before,
            "parents": after["parents"],
            "completed_timestamp_utc": after.get("build_timestamp_utc"),
        }
        destination = publish_run(root, args.run_id, files, metadata)
    except (ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps({"ok": True, "output_directory": str(destination)}))
    return 0
