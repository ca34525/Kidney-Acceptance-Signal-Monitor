"""Explain a partial outcome composition with separate, nonadditive program medians."""

from __future__ import annotations

from collections.abc import Mapping

from matplotlib import rc_context
from matplotlib.figure import Figure

from kasm.patient_journey.component_config import COMPONENT_FIELDS, ERROR_MODELS, ComponentError
from kasm.patient_journey.followup_report import _figure_files, _items, _mapping, _numeric, _section

LABELS = {
    "SAL_CTXFNC_C18": "Deceased donor: functioning and alive",
    "SAL_LTXFNC_C18": "Living donor: functioning and alive",
    "SAL_CTXUNK_C18": "Deceased donor: status yet unknown",
    "SAL_LTXUNK_C18": "Living donor: status yet unknown",
    "combined_unknown": "Combined post-transplant unknown",
    "published_total": "Published functioning-transplant total",
}
MODEL_LABELS = {
    "persistence": "Carry forward latest outcome",
    "available_cohort_reference": "Available-cohort reference",
    "historical_mean": "Simple historical mean",
    "history": "Original Ridge: history",
    "history_acceptance": "Original Ridge: history + acceptance",
    "history_access": "Original Ridge: history + access",
    "history_access_acceptance": "Original Ridge: history + access + acceptance",
    "history_access_acceptance_safety": "Original Ridge: history + access + acceptance + safety",
}


def _summary(population: Mapping[str, object], field: str) -> Mapping[str, object]:
    return (
        _section(_section(population, "components"), field)
        if field in COMPONENT_FIELDS
        else _section(population, field)
    )


def _percent_text(summary: Mapping[str, object]) -> str:
    value = summary.get("median_percent")
    return "Not reported" if value is None else f"{_numeric(summary, 'median_percent'):.2f}%"


def _correlation_text(result: Mapping[str, object]) -> str:
    value = result.get("pearson_r")
    if value is None:
        return "Unavailable: " + str(result.get("reason")).replace("_", " ")
    return f"{_numeric(result, 'pearson_r'):.3f}"


def _report(evidence: Mapping[str, object]) -> bytes:
    populations = _section(evidence, "populations")
    source = _section(populations, "source_n_at_least_10")
    evaluation = _section(populations, "original_evaluation")
    audit = _section(evidence, "audit")
    lines = [
        "# V2 follow-up: what is reported in the outcome?",
        "",
        "Public aggregate prototype — not clinical or regulatory decision support.",
        "",
        f"Exploratory analysis `{evidence['analysis_id']}`; "
        f"source release {evidence['release_code']}.",
        f"Listing cohort: {evidence['listing_cohort_start']} "
        f"through {evidence['listing_cohort_end']}; "
        f"status {evidence['months_after_listing']} months after listing. "
        f"Follow-up end: {evidence['follow_up_end']}.",
        f"Published: {evidence['published_value']} ({evidence['published_precision']} precision).",
        "",
        "Every percentage uses the original listing group (SAL_N_C), including candidates "
        "who never received a transplant. Living-donor outcomes here concern candidates "
        "from the waiting list.",
        "",
        f"The source has {audit['source_count']} programs; "
        f"{source['program_count']} have at least ten listed candidates. "
        f"The original evaluation has {evaluation['program_count']} matched eligible "
        f"programs from {audit['panel_count']} original prediction-universe records.",
        f"Source-only programs: {len(_items(audit['source_only_keys'], 'source keys'))}; "
        f"panel-only programs: {len(_items(audit['panel_only_keys'], 'panel keys'))}; "
        f"originally excluded panel programs: "
        f"{len(_items(audit['excluded_panel_rows'], 'excluded rows'))}.",
        "Exact keys, original exclusions, missing components and rounding evidence are saved "
        "in analysis.json; parsed values and raw missing markers are saved in components.json.",
        "",
        "## Percentages across programs",
        "",
        "Each median is the middle program's percentage for that component. "
        "Medians are not additive and do not pool candidate counts. "
        "The four donor components are a partial outcome description; "
        "they omit waiting, deaths and other statuses. "
        "The published total overlaps its donor components and is reported separately. "
        "Combined unknown describes only post-transplant unknown status.",
        "",
        "| Measure | Source N≥10 median | Reported / missing programs | "
        "Original evaluation median | Reported / missing programs |",
        "|---|---:|---:|---:|---:|",
    ]
    for field, label in LABELS.items():
        a, b = _summary(source, field), _summary(evaluation, field)
        lines.append(
            f"| {label} | {_percent_text(a)} | {a['programs']} / {a['missing_programs']} | "
            f"{_percent_text(b)} | {b['programs']} / {b['missing_programs']} |"
        )
    lines.extend(
        [
            "",
            "![Four separately summarized donor components](outcome_components.png)",
            "",
            "## Unknown status and recorded prediction errors",
            "",
            "Pearson r describes whether larger percentages tend to occur together across the same "
            "programs (−1 to +1); it is unitless. Errors are in percentage points. Positive signed "
            "error means the prediction was too high. Only complete pairs enter each calculation.",
            "",
            "| Compared with combined post-transplant unknown | Pearson r | "
            "Complete / missing pairs |",
            "|---|---:|---:|",
        ]
    )
    associations = _section(evidence, "associations")
    observed = _section(associations, "published_outcome")
    lines.append(
        f"| Published functioning-transplant percentage | {_correlation_text(observed)} | "
        f"{observed['pairs']} / {observed['missing_pairs']} |"
    )
    for model in ERROR_MODELS:
        results = _section(_section(associations, "errors"), model)
        for kind in ("signed", "absolute"):
            result = _section(results, kind)
            lines.append(
                f"| {MODEL_LABELS[model]}: {kind} error | {_correlation_text(result)} | "
                f"{result['pairs']} / {result['missing_pairs']} |"
            )
    lines.extend(
        [
            "",
            "## What remains unknown",
            "",
            "These are all eight stored original approaches on already-inspected outcomes. "
            "No model "
            "was refitted, promoted or given these target-period components as earlier inputs.",
            "",
            "Unknown status is not evidence of health, death or graft failure. It can reflect an "
            "incomplete follow-up form, including one not yet due. "
            "Functioning and unknown percentages share a denominator and mutually exclusive "
            "statuses; signed error contains the observed outcome algebraically. "
            "Their association cannot establish that reporting caused an error. "
            "There is no new time-period validation, survival correction or scenario "
            "assigning outcomes to unknown patients here.",
            "",
            "Donor functioning sums are checked by overlapping rounding intervals at the PDF's "
            "one-decimal display precision (±0.05 percentage points per value). The workbook's "
            "additional digits and published total remain unchanged; "
            "missing operands leave the check "
            "unavailable. Exact workbook differences are saved as QA.",
            "",
            "Sources: [archived July 2025 report, Table B7, page 9]"
            "(https://www.srtr.org/PDFs/072025_release/pdfPSR/NYNSTX1KI202505PNEW.pdf), "
            "[SRTR Table B7 methods](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/technical-methods-for-the-program-specific-reports/).",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _figure(evidence: Mapping[str, object]) -> Figure:
    population = _section(_section(evidence, "populations"), "original_evaluation")
    figure = Figure(figsize=(11, 6.5), facecolor="white")
    axes = figure.add_axes((0.38, 0.29, 0.55, 0.44))
    colors = ("#287C8E", "#287C8E", "#7A648F", "#7A648F")
    observed = [_summary(population, field) for field in COMPONENT_FIELDS]
    maximum = max(
        [
            1.0,
            *(
                _numeric(row, "median_percent")
                for row in observed
                if row["median_percent"] is not None
            ),
        ]
    )
    for index, field in enumerate(COMPONENT_FIELDS):
        summary = _summary(population, field)
        if summary["median_percent"] is not None:
            value = _numeric(summary, "median_percent")
            axes.barh(index, value, height=0.55, color=colors[index])
            axes.text(value + maximum * 0.025, index, f"{value:.2f}%", va="center")
        else:
            axes.text(0, index, "Not reported", va="center")
    axes.set_yticks(range(4), [LABELS[field] for field in COMPONENT_FIELDS])
    axes.invert_yaxis()
    axes.set_xlim(0, maximum * 1.3)
    axes.set_xlabel("Median program percentage of the original listing group")
    axes.spines[["top", "right", "left"]].set_visible(False)
    axes.tick_params(axis="y", length=0, pad=10)
    figure.text(
        0.055, 0.91, "What is reported 18 months after listing?", fontsize=18, weight="bold"
    )
    figure.text(
        0.055,
        0.85,
        f"V2 outcome-component follow-up • {population['program_count']} "
        "original evaluation programs",
        fontsize=12,
    )
    missing = ", ".join(
        str(_summary(population, field)["missing_programs"]) for field in COMPONENT_FIELDS
    )
    figure.text(
        0.055,
        0.18,
        f"Missing programs by bar, top to bottom: {missing}. Each bar uses its reported values.",
        fontsize=10,
    )
    figure.text(
        0.055,
        0.13,
        "Separate medians cannot be added. "
        "These four statuses are only part of the listing outcome.",
        fontsize=10,
    )
    figure.text(
        0.055,
        0.08,
        "Listed July 2022–June 2023 • SRTR Table B7, published July 8, 2025 "
        "• Exploratory description",
        fontsize=10,
    )
    figure.text(
        0.055,
        0.035,
        "Public aggregate prototype — not clinical or regulatory decision support",
        fontsize=9,
    )
    return figure


def render_component_report(evidence: Mapping[str, object]) -> dict[str, bytes]:
    """Render one source-grounded partial composition without altering its statistics."""
    if (
        evidence.get("promotion_allowed") is not False
        or evidence.get("future_forecast_available") is not False
    ):
        raise ComponentError("Component reporting cannot permit promotion or future forecasts.")
    _mapping(evidence.get("populations"), "populations")
    with rc_context(
        {
            "svg.hashsalt": "kasm-v2-outcome-components-v1",
            "svg.fonttype": "none",
            "font.family": "DejaVu Sans",
            "font.size": 10,
        }
    ):
        return {
            "report.md": _report(evidence),
            **_figure_files(_figure(evidence), "outcome_components"),
        }
