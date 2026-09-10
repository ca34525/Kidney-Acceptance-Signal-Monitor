"""Render aggregate historical error and review comparisons in their stated units."""

from __future__ import annotations

import argparse
import csv
import html
import io
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from kasm.acceptance_forecast.runs import json_bytes
from kasm.program_prediction.runs import load_run

LABELS = {
    "registrations": "New registrations",
    "ddkt_removals": "DDKT removal events",
    "ldkt_removals": "LDKT removal events",
    "ending_list": "Year-end registrations",
    "overall_oar": "Published acceptance ratio",
}
COLORS = ("#087E8B", "#B45309", "#6D28D9", "#C24165", "#334155", "#64748B")


def _png(figure: Any) -> bytes:
    stream = io.BytesIO()
    figure.savefig(stream, format="png", dpi=170, facecolor="white", bbox_inches="tight")
    plt.close(figure)
    return stream.getvalue()


def _error_figure(metrics: list[dict[str, Any]], comparators: dict[str, str]) -> bytes:
    targets = list(comparators)
    figure, axes = plt.subplots(
        len(targets), 1, figsize=(10, max(3, 2.35 * len(targets))), squeeze=False, sharex=True
    )
    for axis, target in zip(axes[:, 0], targets, strict=True):
        records = [row for row in metrics if row["target"] == target]
        models = sorted({r["model"] for r in records if r["model"] != comparators[target]})
        for index, model in enumerate(models):
            points = error_points(records, target, model, comparators[target])
            if points:
                axis.plot(
                    *zip(*points, strict=True),
                    marker="o",
                    markersize=4,
                    color=COLORS[index % len(COLORS)],
                    label=model.replace("_", " "),
                )
        axis.axhline(0, color="#334155", linewidth=0.8)
        axis.axvspan(2023.5, 2025.4, color="#EEF2F6", zorder=0)
        axis.set_title(
            f"{LABELS[target]} | reference: {comparators[target].replace('_', ' ')}",
            loc="left",
            fontsize=11,
        )
        axis.set_ylabel("Error reduction (%)")
        axis.set_xticks([2021, 2022, 2023, 2024, 2025])
        axis.grid(alpha=0.18)
        axis.legend(fontsize=7, ncol=3, loc="best")
    axes[-1, 0].set_xlabel("Target calendar year (shading: later historical comparison)")
    figure.suptitle(
        "Fixed methods against the discovery-selected simple reference",
        fontsize=14,
        y=1.005,
    )
    figure.tight_layout()
    return _png(figure)


def error_points(
    metrics: list[dict[str, Any]], target: str, model: str, comparator: str
) -> list[tuple[int, float]]:
    """Only plot full-coverage methods, which share the same observed-program denominator."""
    baseline = {
        r["target_year"]: r["mae"]
        for r in metrics
        if r["target"] == target and r["model"] == comparator and r["complete_forecast_coverage"]
    }
    return sorted(
        (r["target_year"], 100 * (1 - r["mae"] / baseline[r["target_year"]]))
        for r in metrics
        if r["target"] == target
        and r["model"] == model
        and r["complete_forecast_coverage"]
        and r["mae"] is not None
        and baseline.get(r["target_year"]) not in (None, 0)
    )


def _review_figure(reviews: list[dict[str, Any]], questions: list[dict[str, str]]) -> bytes:
    figure, axes = plt.subplots(
        max(1, len(questions)), 2, figsize=(11, max(3.5, 3.2 * len(questions))), squeeze=False
    )
    for index, question in enumerate(questions):
        review = next((r for r in reviews if r["question"]["target"] == question["target"]), {})
        for axis, year in zip(axes[index], (2024, 2025), strict=True):
            metrics = [r for r in review.get("metrics", []) if r["target_year"] == year]
            methods = sorted({r["method"] for r in metrics})
            for number, method in enumerate(methods):
                points = sorted(
                    (r["budget"], 100 * r["captured_share"])
                    for r in metrics
                    if r["method"] == method and r.get("captured_share") is not None
                )
                if points:
                    axis.plot(
                        *zip(*points, strict=True),
                        marker="o",
                        markersize=4,
                        color=COLORS[number % len(COLORS)],
                        linestyle="--" if method == "random_expectation" else "-",
                        label=method.replace("_", " "),
                    )
            axis.set_title(
                f"{LABELS[question['target']]}: {question['direction']} | {year}",
                fontsize=10,
                loc="left",
            )
            axis.set_xticks([10, 15, 25])
            axis.set_ylabel("Observed directional change captured (%)")
            axis.set_xlabel("Programs selected for review")
            axis.set_ylim(bottom=0)
            axis.grid(alpha=0.18)
            if methods:
                axis.legend(fontsize=7)
    if not questions:
        axes[0, 0].text(0.5, 0.5, "No discovery question shortlisted", ha="center")
    figure.suptitle(
        "Illustrative review budgets | queues selected before later outcome availability",
        fontsize=13,
        y=1.01,
    )
    figure.tight_layout()
    return _png(figure)


def _change_figure(rows: list[dict[str, Any]], questions: list[dict[str, str]]) -> bytes:
    figure, axes = plt.subplots(
        max(1, len(questions)), 2, figsize=(11, max(3.5, 3.5 * len(questions))), squeeze=False
    )
    for index, question in enumerate(questions):
        for axis, year in zip(axes[index], (2024, 2025), strict=True):
            observed_changes, predicted_changes = [], []
            for row in rows:
                if (
                    row["target"] != question["target"]
                    or row["model"] != question["model"]
                    or row["target_year"] != year
                    or not row["eligible"]
                    or row.get("observed") is None
                    or row.get("prediction") is None
                ):
                    continue
                observed_changes.append(row["observed"] - row["latest"])
                predicted_changes.append(row["prediction"] - row["latest"])
            axis.scatter(observed_changes, predicted_changes, alpha=0.55, s=14, color=COLORS[0])
            extent = max([abs(v) for v in (*observed_changes, *predicted_changes)], default=1)
            axis.plot([-extent, extent], [-extent, extent], color="#64748B", linewidth=0.8)
            axis.axhline(0, color="#CBD5E1", linewidth=0.7)
            axis.axvline(0, color="#CBD5E1", linewidth=0.7)
            units = "ratio units" if question["target"] == "overall_oar" else "events/registrations"
            axis.set_title(f"{LABELS[question['target']]} | {year}", fontsize=11, loc="left")
            axis.set_xlabel(f"Reported outcome minus latest ({units})")
            axis.set_ylabel(f"Prediction minus latest ({units})")
    figure.suptitle(
        "Each dot is one program | shortlisted method, original units, no identity labels",
        fontsize=13,
        y=1.005,
    )
    figure.tight_layout()
    return _png(figure)


def render_figures(
    predictions: list[dict[str, Any]],
    comparators: dict[str, str],
    reviews: list[dict[str, Any]],
    questions: list[dict[str, str]],
) -> dict[str, bytes]:
    """Plot aggregate comparisons and anonymous changes, never named program rankings."""
    from kasm.program_prediction.metrics import summarize

    if not predictions or not comparators:
        raise ValueError("Figures require prediction records and fixed simple comparators.")
    metrics = summarize(predictions)["period_metrics"]
    with plt.rc_context(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    ):
        return {
            "error-improvement.png": _error_figure(metrics, comparators),
            "review-budget.png": _review_figure(reviews, questions),
            "changes.png": _change_figure(predictions, questions),
        }


def _csv(rows: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    keys = sorted({key for row in rows for key in row})
    writer = csv.DictWriter(buffer, fieldnames=keys)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def _table(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> str:
    def cell(value: Any) -> str:
        if isinstance(value, float):
            return f"{value:.4f}" if math.isfinite(value) else "Unavailable"
        return "Unavailable" if value is None else html.escape(str(value))

    header = "".join(f"<th>{html.escape(field.replace('_', ' '))}</th>" for field in fields)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell(row.get(f))}</td>" for f in fields) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def report_files(root: Path, args: argparse.Namespace) -> tuple[dict[str, bytes], dict[str, str]]:
    """Rebuild figures and complete tables from saved predictions without another fit."""
    from kasm.program_prediction.commands import _same_config, validate_followup
    from kasm.program_prediction.config import load_config
    from kasm.program_prediction.metrics import summarize

    discovery = load_run(root, args.discovery_run, stage="screen")
    later = load_run(root, args.assessment_run, stage="assess")
    choice = load_run(root, args.shortlist_run, stage="shortlist")
    config = load_config(args.config)
    _same_config(discovery, args.config)
    _same_config(later, args.config)
    if (
        discovery["completion.json"]["provenance"]["parents"]["panel"]["run_id"]
        != later["completion.json"]["provenance"]["parents"]["panel"]["run_id"]
    ):
        raise ValueError("Report discovery and later assessment use different panel identities.")
    if config.round_id == "initial":
        _same_config(choice, args.config)
        if (
            choice["completion.json"]["provenance"]["parents"]["discovery"]["run_id"]
            != args.discovery_run
        ):
            raise ValueError("Report discovery differs from the saved shortlist's discovery run.")
    else:
        validate_followup(root, config, args.shortlist_run)
    if (
        later["completion.json"]["provenance"]["parents"]["shortlist"]["run_id"]
        != args.shortlist_run
    ):
        raise ValueError("Report shortlist differs from the recorded later assessment choice.")
    predictions = discovery["predictions.json"] + later["predictions.json"]
    metrics = summarize(predictions)
    questions = choice["shortlist.json"]["questions"]
    comparators = choice["comparators.json"]
    active = {
        target: model
        for target, model in comparators.items()
        if any(row["target"] == target for row in predictions)
    }
    reviews = later["reviews.json"]
    files = render_figures(predictions, active, reviews, questions)
    files["complete-results.json"] = json_bytes(metrics)
    files["period-metrics.csv"] = _csv(metrics["period_metrics"])
    files["summary-metrics.csv"] = _csv(metrics["summary_metrics"])
    files["review-metrics.csv"] = _csv([r for review in reviews for r in review["metrics"]])
    files["predictions.json"] = json_bytes(predictions)
    files["error-differences.json"] = json_bytes(later["error-differences.json"])
    files["decision-differences.json"] = json_bytes(later["decision-differences.json"])
    review_rows = [row for review in reviews for row in review["metrics"]]
    table = _table(
        metrics["period_metrics"],
        (
            "target",
            "target_year",
            "model",
            "mae",
            "signed_error",
            "p90_absolute_error",
            "forecast_coverage",
            "n_observed",
        ),
    )
    review_table = _table(
        review_rows,
        (
            "target",
            "target_year",
            "method",
            "budget",
            "captured_share",
            "selected_precision",
            "n_selected_observed",
            "missed_observed_change",
        ),
    )
    content = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Program prediction sprint: complete historical comparisons</title>
<style>body{{font:16px system-ui;color:#183043;max-width:1200px;margin:40px auto;padding:0 24px}}
img{{max-width:100%}}table{{border-collapse:collapse;font-size:12px;width:100%;margin:24px 0}}
th,td{{padding:7px;text-align:left;border-bottom:1px solid #ddd}}th{{background:#edf3f5}}
.note{{padding:18px;background:#eef4f6}}h1{{font-size:32px}}</style>
<h1>Program prediction sprint: {html.escape(config.round_id)}</h1>
<p class="note">Public aggregate research — no clinical or regulatory decision support.
Exploratory historical delayed-report nowcasts. These years were previously inspected;
later comparisons are not independent validation.</p>
<p>Each record is one program, target and calendar year. Origins are public reports during
the target year; outcomes are published later. Counts describe registration/removal events,
not distinct people or proven clinical benefit. OAR is a published risk-adjusted ratio.
Primary errors use count units or log OAR, with equal weight per year.</p>
<p>Source: pinned SRTR workbooks, origin reports 2018–2025, outcomes through July 2026.
The source ledger retains exact publication values and month/day precision. The 2024/2025
OAR outcomes span documented offer-definition changes. Unknown outcomes stay unknown.</p>
<p>Reference baselines were selected using discovery years 2021–2023. The saved shortlist
precedes 2024–2025 scoring. Bootstrap intervals resample whole programs and describe
cross-program variation; they do not account for new years or selecting the best experiment.</p>
<img src="error-improvement.png" alt="Error reduction by target and calendar year">
<img src="review-budget.png" alt="Observed directional change captured by review budget">
<p>Queues are selected before checking outcome availability. Unknown outcomes are unscorable
and queues are never refilled. Captured share divides observed directional change selected by
that among all eligible programs with observed outcomes. Random expectation is K/N over the
origin-eligible universe. Budgets are illustrative. Improved targeting would motivate analyst
review; intervention benefits and actual staffing value remain untested.</p>
<img src="changes.png" alt="Anonymous predicted and observed changes in original units">
<h2>Every target, method and year</h2>{table}
<h2>Review comparisons</h2>{review_table}
<p>Download <a href="complete-results.json">complete metrics</a>,
<a href="period-metrics.csv">per-year CSV</a>, <a href="summary-metrics.csv">summary CSV</a>,
<a href="review-metrics.csv">review CSV</a>, and
<a href="error-differences.json">descriptive error intervals</a> and
<a href="decision-differences.json">fixed-queue decision intervals</a>.</p></html>"""
    files["report.html"] = content.encode()
    return files, {
        "discovery": args.discovery_run,
        "assessment": args.assessment_run,
        "shortlist": args.shortlist_run,
    }
