"""Ask one recorded follow-up question of saved predictions without fitting again."""

from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from kasm.acceptance_forecast.inputs import ensure_local_path
from kasm.acceptance_forecast.runs import json_bytes
from kasm.program_prediction.config import SprintConfig, validate_config
from kasm.program_prediction.metrics import bootstrap_decision_difference, review_budget
from kasm.program_prediction.reporting import _csv, _review_figure, _table
from kasm.program_prediction.runs import load_run


@dataclass(frozen=True)
class DecisionFollowupConfig:
    """The single adapted review question fixed before its queues are examined."""

    question: str
    schema_version: int = 1
    study_id: str = "program-prediction-0031"
    round_id: str = "followup_2"
    parent_run: str = "followup-1-later"
    target: str = "registrations"
    model: str = "ridge_broader"
    direction: str = "growth"
    budgets: tuple[int, ...] = (10, 15, 25)
    seed: int = 20260909
    bootstrap_resamples: int = 2000
    output_root: str = "data/research/program-prediction-0031"

    @property
    def raw(self) -> dict[str, Any]:
        """Return JSON-ready settings without changing their values."""
        return dict(json.loads(json.dumps(asdict(self))))


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Decision settings contain a duplicate field.")
        result[key] = value
    return result


def load_config(path: Path) -> DecisionFollowupConfig:
    """Reject undocumented model, budget, lineage or output-path changes."""
    try:
        raw = json.loads(path.read_bytes(), object_pairs_hook=_unique)
        if not isinstance(raw, dict) or set(raw) != set(DecisionFollowupConfig("").raw):
            raise ValueError("Decision settings must contain exactly the recorded fields.")
        question = raw["question"]
        if not isinstance(question, str) or not question.strip():
            raise ValueError("The adapted decision question must be nonempty text.")
        if not isinstance(raw["parent_run"], str) or not raw["parent_run"].strip():
            raise ValueError("Decision settings require a recorded parent run identity.")
        expected = DecisionFollowupConfig(question, parent_run=raw["parent_run"])
        if json.dumps(raw, sort_keys=True) != json.dumps(expected.raw, sort_keys=True):
            raise ValueError(
                "Decision settings disagree with the recorded follow-up configuration."
            )
        return expected
    except (OSError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Cannot read the fixed decision-follow-up settings.") from exc


def _sprint_settings(raw: Any) -> SprintConfig:
    if not isinstance(raw, dict) or set(raw) != set(SprintConfig().raw):
        raise ValueError("Parent settings do not describe the completed first follow-up.")
    values = dict(raw)
    try:
        for name in ("targets", "pipelines", "discovery_years", "later_years", "budgets"):
            values[name] = tuple(values[name])
        prior = SprintConfig(**values)
        validate_config(prior)
    except (TypeError, ValueError) as exc:
        raise ValueError("Parent settings violate the recorded preceding question.") from exc
    return prior


def _prior_settings(raw: Any) -> SprintConfig:
    prior = _sprint_settings(raw)
    if (
        prior.round_id != "followup_1"
        or prior.targets != ("registrations",)
        or not prior.omit_oar_features
    ):
        raise ValueError(
            "Parent settings must retain the registration follow-up without OAR inputs."
        )
    return prior


def _role(parent: dict[str, Any], role: str) -> str:
    identity = parent["completion.json"]["provenance"].get("parents", {}).get(role, {})
    if not isinstance(identity, dict) or not isinstance(identity.get("run_id"), str):
        raise ValueError(f"Parent lineage lacks its {role} identity.")
    return str(identity["run_id"])


def _load_parent(
    root: Path, config: DecisionFollowupConfig
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    parent = load_run(root, config.parent_run, stage="assess")
    prior = _prior_settings(parent.get("settings.json"))
    panel_id, shortlist_id = _role(parent, "panel"), _role(parent, "shortlist")
    if _role(parent, "prior_assessment") != prior.parent_run:
        raise ValueError("Parent lineage differs from the preceding configured assessment.")
    initial = load_run(root, _role(parent, "prior_assessment"), stage="assess")
    if (
        _sprint_settings(initial.get("settings.json")).round_id != "initial"
        or _role(initial, "shortlist") != shortlist_id
        or initial.get("shortlist.json") != parent.get("shortlist.json")
        or initial.get("comparators.json") != parent.get("comparators.json")
    ):
        raise ValueError(
            "Parent lineage must preserve the initial assessment and its saved choice."
        )
    panel = load_run(root, panel_id, stage="build")
    choice = load_run(root, shortlist_id, stage="shortlist")
    if panel.get("settings.json") != parent["settings.json"]:
        raise ValueError("Parent panel settings differ from the saved fitted assessment.")
    features = panel.get("feature-map.json")
    if (
        not isinstance(features, dict)
        or not features
        or any(not isinstance(field, str) or field.startswith("oar_") for field in features)
    ):
        raise ValueError("Parent panel must record the omission of all OAR feature fields.")
    if not isinstance(panel.get("source-ledger.json"), dict) or not panel["source-ledger.json"]:
        raise ValueError("Parent panel must retain its source provenance ledger.")
    for name in ("shortlist.json", "comparators.json"):
        if parent.get(name) != choice.get(name) or name not in parent:
            raise ValueError("Parent shortlist or comparator differs from its preserved choice.")
    if parent["comparators.json"].get(config.target) != "persistence":
        raise ValueError("Parent comparator must retain the original frozen persistence reference.")
    rows = parent.get("predictions.json")
    if (
        not isinstance(rows, list)
        or not rows
        or any(not isinstance(row, dict) for row in rows)
        or {row.get("target") for row in rows} != {config.target}
        or {row.get("target_year") for row in rows} != {2024, 2025}
        or {row.get("model") for row in rows}
        != {"persistence", "recent_mean", "damped_trend", *prior.pipelines}
    ):
        raise ValueError("Parent prediction coverage must retain both years and every procedure.")
    fitted = [
        row
        for row in parent.get("folds.json", [])
        if row.get("model") == config.model and row.get("target") == config.target
    ]
    if {row.get("target_year") for row in fitted} != {2024, 2025} or any(
        set(row.get("feature_columns", [])) != set(features)
        or any(field.startswith("oar_") for field in row["feature_columns"])
        for row in fitted
    ):
        raise ValueError("Parent fitted-model ledger does not confirm the OAR feature omission.")
    for name in ("metrics.json", "error-differences.json"):
        if name not in parent:
            raise ValueError("Parent must retain its complete original error evidence.")
    return (
        parent,
        panel,
        {"assessment": config.parent_run, "shortlist": shortlist_id, "panel": panel_id},
    )


def _differences(review: dict[str, Any], config: DecisionFollowupConfig) -> list[dict[str, Any]]:
    results = []
    for comparator in ("last_change", "latest_level", "persistence"):
        for budget in config.budgets:
            try:
                result = bootstrap_decision_difference(
                    review["selections"],
                    target=config.target,
                    candidate=config.model,
                    comparator=comparator,
                    budget=budget,
                    years=(2024, 2025),
                    resamples=config.bootstrap_resamples,
                    seed=config.seed,
                )
            except ValueError as exc:
                result = {
                    "target": config.target,
                    "candidate": config.model,
                    "comparator": comparator,
                    "budget": budget,
                    "status": "unavailable",
                    "error": str(exc),
                }
            results.append(result)
    return results


def _html(config: DecisionFollowupConfig, metrics: list[dict[str, Any]]) -> bytes:
    table = _table(
        metrics,
        (
            "target_year",
            "method",
            "budget",
            "captured_share",
            "selected_precision",
            "n_selected_observed",
            "n_selected_missing_outcome",
            "n_false_alarms",
            "missed_observed_change",
        ),
    )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Adapted registration review question</title>
<style>body{{font:16px system-ui;max-width:1150px;margin:40px auto;padding:0 24px;color:#183043}}
img{{max-width:100%}}table{{border-collapse:collapse;font-size:12px;width:100%;margin:24px 0}}
th,td{{padding:7px;border-bottom:1px solid #ddd;text-align:left}}th{{background:#edf3f5}}</style>
<h1>Registration growth review: adapted follow-up 2</h1>
<p>{html.escape(config.question)}</p>
<p>Public aggregate research; no clinical or regulatory decision support. This adapted
question was selected after inspecting historical errors. It is not independent validation.
It reuses saved Ridge predictions from {html.escape(config.parent_run)}, without fitting again.
The original discovery shortlist and unsuccessful Extra Trees findings remain preserved.</p>
<p>Each record is one program and target calendar year. The outcome is annual registration
events, not distinct people or staffing hours. Origin reports in July 2024 and July 2025
describe the preceding calendar year; outcomes were reported in July 2025 and July 2026.
These are delayed-report nowcasts. Public reports lag programs' own internal information.</p>
<img src="review-budget.png"
alt="Captured observed registration growth by review budget, 2024 and 2025">
<p>Queues use the origin-eligible universe before checking later outcome availability.
Unknown selected outcomes remain unscorable, and the queue is never refilled. Captured share
is selected observed growth divided by all observed growth in that universe. The random
expectation is K/N. Budgets of 10, 15 and 25 are illustrations, not established staffing limits.</p>
{table}
<p>Persistence remains the strongest simple forecasting reference fixed on initial discovery.
Review comparisons also use the last consecutive change, largest latest registration count
and random selection. Error summaries are inherited unchanged from the preceding assessment.</p>
<p>Intervals resample whole programs while keeping historical selection flags fixed. They
describe cross-program variation conditional on these queues and exclude fitting, selecting
this question, queue selection and new-year uncertainty. OAR features were omitted; the
optional candidate-characteristic block remains unavailable. Better historical targeting
could motivate analyst review, but intervention benefit and operational usefulness
remain untested.</p>
<p>Source: verified SRTR annual workbooks; exact hashes, publication precision and feature
identities are preserved in the parent panel and <a href="source-ledger.json">source ledger</a>.</p>
<p>Read <a href="report.json">aggregate results</a>, <a href="review-metrics.csv">review table</a>,
<a href="decision-differences.json">conditional decision intervals</a>,
<a href="inherited-metrics.json">unchanged error metrics</a>,
<a href="error-differences.json">unchanged error comparisons</a>,
<a href="question.json">recorded adapted question</a>,
<a href="shortlist.json">unchanged original shortlist</a> and
<a href="references.json">source-run references</a>.</p></html>""".encode()


def reassess(root: Path, config_path: Path) -> tuple[dict[str, bytes], dict[str, str]]:
    """Build a review-only report from verified saved outcomes, predictions and choices."""
    ensure_local_path(config_path, root)
    config = load_config(config_path)
    parent, panel, parents = _load_parent(root, config)
    question = {
        "target": config.target,
        "model": config.model,
        "direction": config.direction,
        "question": config.question,
        "rationale": "Adapted question prompted by inspected registration errors; no refit.",
    }
    review = {
        "question": question,
        **review_budget(
            parent["predictions.json"],
            target=config.target,
            model=config.model,
            direction=config.direction,
            budgets=config.budgets,
            seed=config.seed,
            comparator=parent["comparators.json"][config.target],
        ),
    }
    differences = _differences(review, config)
    report = {
        "question": question,
        "settings": config.raw,
        "parents": parents,
        "adapted_after_inspected_errors": True,
        "new_model_fits": 0,
        "original_shortlist_preserved": True,
        "years": [2024, 2025],
        "review_metrics": review["metrics"],
        "decision_differences": differences,
        "error_metrics": "Inherited unchanged from the completed parent assessment.",
    }
    files = {
        "question.json": json_bytes(config.raw),
        "report.json": json_bytes(report),
        "reviews.json": json_bytes([review]),
        "review-selections.json": json_bytes(review["selections"]),
        "review-metrics.csv": _csv(review["metrics"]),
        "decision-differences.json": json_bytes(differences),
        "review-budget.png": _review_figure([review], [question]),
        "report.html": _html(config, review["metrics"]),
        "inherited-metrics.json": json_bytes(parent["metrics.json"]),
        "references.json": json_bytes(
            {
                "parents": parents,
                "parent_completion": parent["completion.json"],
                "parent_settings": parent["settings.json"],
            }
        ),
        "source-ledger.json": json_bytes(panel["source-ledger.json"]),
    }
    for name in (
        "predictions.json",
        "shortlist.json",
        "comparators.json",
        "error-differences.json",
    ):
        files[name] = json_bytes(parent[name])
    return files, parents
