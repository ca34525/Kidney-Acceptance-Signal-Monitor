"""Render trusted precomputed records as offline briefs and exportable figures.

The caller validates the analytical records and owns all filesystem operations.
Rendering keeps published counts separate from calculated changes and rates.
"""

from __future__ import annotations

import csv
import io
from html import escape
from typing import Any

from matplotlib import rc_context
from matplotlib.figure import Figure

from kasm.reporting.history import format_publication_value
from kasm.waiting_list.parse import REMOVAL_FIELDS
from kasm.waiting_list.screen import Comparison

LABELS = {
    "ADDCEN": "Additions",
    "REMTXC": "Deceased donor",
    "REMTXL": "Living donor",
    "REMTXOC": "Transplant elsewhere",
    "REMTFER": "Transfer to another program",
    "REMDIED": "Deaths",
    "REMDET": "Deterioration",
    "REMREC": "Recovery",
    "REMOTH": "Other removals",
}
_BANNER = "Public aggregate prototype — not clinical or regulatory decision support."
_COLORS = ("#27667b", "#a6afb4", "#b77b32")
_CSS = """*{box-sizing:border-box}body{margin:0;color:#172d3a;background:#e8ecec;
font:15px/1.46 Arial,sans-serif}main{max-width:1000px;margin:auto}
.page{background:white;padding:38px 48px;margin:24px 0;break-after:page}
.page:last-child{break-after:auto}.eyebrow{font-size:12px;letter-spacing:.14em;
text-transform:uppercase;color:#416b78}h1{font-size:31px;line-height:1.13;margin:12px 0}
h2{font-size:20px;margin:22px 0 10px}h3{font-size:16px;margin:16px 0 7px}
p{margin:10px 0}.lead{font-size:18px;line-height:1.4}.muted,.meta{color:#50616a;
font-size:12px}.banner{border-top:2px solid #27667b;padding-top:8px;font-size:12px}
.callout{background:#edf5f6;border-left:4px solid #27667b;padding:10px 14px;margin:14px 0}
table{border-collapse:collapse;width:100%;font-size:13px;margin:10px 0}
th,td{padding:6px 9px;border-bottom:1px solid #d6dfe1;text-align:right}
th:first-child,td:first-child{text-align:left}th{background:#edf2f3;font-weight:600}
.equation{font:16px/1.5 Consolas,monospace;background:#f2f5f5;padding:9px 12px}
svg{width:100%;height:auto;display:block}figure{margin:12px 0}figcaption{font-size:12px}
.source{font-size:11px;overflow-wrap:anywhere}.support table{font-size:11px}
@page{size:A4;margin:12mm}@media print{body{background:white;font-size:10pt;line-height:1.32}
main{max-width:none}.page{padding:0;margin:0;min-height:267mm}h1{font-size:23pt}
h2{font-size:14pt;margin-top:14px}.lead{font-size:12pt}table{font-size:9pt}
th,td{padding:4px 7px}.meta,.muted,.banner{font-size:8pt}.source{font-size:7pt}
.case-study figure{margin:5px 0}.case-study h2{margin:10px 0 5px}
.case-study p{margin:6px 0}.case-study .meta{font-size:7pt}}
"""


def _text(value: object) -> str:
    return escape(str(value), quote=True)


def _number(value: Any, *, digits: int = 0, signed: bool = False) -> str:
    if value is None:
        return "Not reported"
    return format(value, f"{'+' if signed else ''},.{digits}f").replace("-", "−")


def _document(title: str, body: str, *, css_class: str = "") -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'unsafe-inline'; img-src data:; font-src 'none'\">"
        f"<title>{_text(title)}</title><style>{_CSS}</style></head>"
        f'<body><main class="{css_class}">{body}</main></body></html>'
    )


def _metadata(provenance: dict[str, Any]) -> str:
    return (
        f'<p class="banner">{_BANNER}</p><p class="meta">'
        "Source: Scientific Registry of Transplant Recipients (SRTR), public Table B1. "
        f"Artifact version: {_text(provenance.get('run_id', 'Not reported'))}. "
        f"Built UTC: {_text(provenance.get('build_time_utc', 'Not reported'))}.</p>"
    )


def _table(headings: list[str], rows: list[list[str]]) -> str:
    return (
        "<table><thead><tr>"
        + "".join(f'<th scope="col">{_text(value)}</th>' for value in headings)
        + "</tr></thead><tbody>"
        + "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
        + "</tbody></table>"
    )


def _publication(row: dict[str, Any]) -> str:
    return format_publication_value(row["published_value"], row["published_precision"])


def _source_rows(rows: list[dict[str, Any]]) -> str:
    return "".join(
        f'<p class="source">Calendar year {_text(row["year"])} '
        f"(January 1–December 31); release {_text(row['release_code'])}; "
        f"published {_text(_publication(row))}. "
        f"Source: {_text(row['source_url'])}. "
        f"SHA-256: {_text(row.get('source_sha256', 'Not reported'))}.</p>"
        for row in rows
    )


def _source_summary(rows: list[dict[str, Any]]) -> str:
    return (
        '<p class="meta">Calendar-year source publications: '
        + "; ".join(
            f"{row['year']}: {_text(_publication(row))} (release {_text(row['release_code'])})"
            for row in rows
        )
        + ". Exact source URLs and hashes are in the supporting material.</p>"
    )


def _annual_table(brief: dict[str, Any]) -> str:
    annual = [brief.get("previous"), brief.get("current")]
    rows = []
    fields = [("Starting registrations", "start"), ("Additions", "additions")]
    fields += [(LABELS[field], field) for field in REMOVAL_FIELDS]
    fields += [("Ending registrations", "end"), ("Annual list growth (calculated)", "growth")]
    for label, field in fields:
        cells = [label]
        for row in annual:
            value = (
                None if row is None else row.get(field, row.get("removals_by_field", {}).get(field))
            )
            cells.append(_number(value))
        rows.append(cells)
    return _table(
        ["Published count / calculated growth", str(brief["year"] - 1), str(brief["year"])], rows
    )


def _annual_equations(brief: dict[str, Any]) -> str:
    equations = []
    for row in (brief.get("previous"), brief.get("current")):
        if row is None:
            continue
        if row.get("annual_equation", {}).get("residual") != 0:
            equations.append(
                f'<p class="muted">{row["year"]}: equation unavailable; counts are missing '
                "or do not reconcile.</p>"
            )
            continue
        values = (row.get("end"), row.get("start"), row.get("additions"), row.get("removal_total"))
        equation = (
            f"{_number(values[0])} = {_number(values[1])} + "
            f"{_number(values[2])} − {_number(values[3])}"
        )
        equations.append(f'<p class="equation">{row["year"]}: {equation}</p>')
    return "".join(equations)


def _change_section(brief: dict[str, Any]) -> str:
    change = brief["change"]
    contributions = {"ADDCEN": change["change_additions"], **change["removal_contributions"]}
    rows = [
        [
            LABELS[field],
            _number(value, signed=True),
            _number(change["contributions_per100"][field], digits=2, signed=True),
        ]
        for field, value in contributions.items()
    ]
    rows.append(
        [
            "Change in annual growth",
            _number(change["change_in_growth"], signed=True),
            _number(change["change_in_growth_per100"], digits=2, signed=True),
        ]
    )
    terms = " + ".join(f"({_number(value)})" for value in contributions.values())
    return (
        "<h2>Why annual growth changed</h2>"
        "<p>Change in growth = change in additions − changes in each removal category. "
        "A positive contribution makes growth larger; a negative contribution makes it smaller. "
        "More removals therefore contribute a negative count.</p>"
        f'<p class="equation">{_number(change["growth"])} − '
        f"{_number(change['previous_growth'])} = {_number(change['change_in_growth'])}</p>"
        + _table(
            ["Contribution to change in growth", "Events", "Per 100 starting registrations"], rows
        )
        + f'<p class="equation">{terms} = {_number(change["change_in_growth"])}</p>'
        + f'<p class="muted">All normalized contributions use the same '
        f"{_number(change['denominator'])} current starting registrations: events ÷ "
        f"{_number(change['denominator'])} × 100. The unit is events per 100 current starting "
        "registrations, not a patient probability or a rate per patient-year.</p>"
        "<h2>What to review next</h2><p>Compare the additions with the program's referral and "
        "listing records. Compare deceased- and living-donor removals with transplant activity "
        "and its recorded circumstances. Review transfers, transplant elsewhere, deaths, "
        "deterioration, recovery and other removals in their own records.</p>"
        "<p>These are questions for internal review. The arithmetic accounts for recorded changes; "
        "it does not establish clinical causes, capacity strain or an intervention effect. "
        "A shrinking list alone does not establish improved access.</p>"
    )


def render_program_brief(brief: dict[str, Any], provenance: dict[str, Any]) -> str:
    """Present both annual records and an eligible count breakdown without I/O."""
    title = f"Waiting-list records · {brief['program_key']} · {brief['year']}"
    first = (
        '<section class="page"><p class="eyebrow">Waiting-list case study · program brief</p>'
        f"<h1>{_text(brief['program_key'])}: follow the counts</h1>"
        f'<p class="lead">Calendar years {brief["year"] - 1} and {brief["year"]}. '
        "One record describes a kidney program's registration and removal events, "
        "not nationally unique people.</p>"
        + _metadata(provenance)
        + _source_summary([row for row in (brief.get("previous"), brief.get("current")) if row])
    )
    if not brief["available"]:
        first += (
            f'<div class="callout"><strong>Unavailable.</strong> {_text(brief["reason"])}</div>'
        )
    first += (
        "<h2>What was reported in each year</h2>"
        "<p>Deceased- and living-donor transplant removals concern the reporting program. "
        "Transplant elsewhere remains separate. Zero is a reported count; “Not reported” "
        "means a count is unknown.</p>"
        + _annual_table(brief)
        + "<h2>Each year's accounting</h2><p>Ending list = starting list + additions − "
        "all eight removal categories. Annual list growth = ending list − starting list.</p>"
        + _annual_equations(brief)
        + "</section>"
    )
    second = (
        '<section class="page"><p class="eyebrow">Program brief · change and interpretation</p>'
    )
    if brief["available"]:
        change = brief["change"]
        second += (
            f"<h1>Annual growth: {_number(change['growth'], signed=True)} registrations</h1>"
            f'<p class="lead">Growth changed by {_number(change["change_in_growth"], signed=True)} '
            f"compared with the preceding year. Transplant removals changed by "
            f"{_number(change['change_transplants'], signed=True)} events.</p>"
            + _change_section(brief)
        )
    else:
        second += (
            "<h1>Comparison unavailable</h1>"
            "<p>Insufficient eligible history for a count breakdown.</p>"
        )
    second += _metadata(provenance)
    second += _source_rows([row for row in (brief.get("previous"), brief.get("current")) if row])
    second += "</section>"
    return _document(title, first + second)


def _figure_files(figure: Figure, stem: str) -> dict[str, bytes]:
    files = {}
    for suffix in ("svg", "png"):
        buffer = io.BytesIO()
        metadata = {"Date": None} if suffix == "svg" else {"Software": "KASM Plan 0026"}
        figure.savefig(buffer, format=suffix, dpi=170, metadata=metadata, facecolor="white")
        files[f"{stem}.{suffix}"] = buffer.getvalue()
    return files


def _figure_footer(figure: Figure, provenance: dict[str, Any]) -> None:
    publications = "; ".join(
        f"{row['year']}: {_publication(row)}" for row in provenance.get("source_vintages", [])
    )
    figure.text(
        0.03, 0.092, f"Calendar-year publications — {publications or 'Not reported'}.", fontsize=7
    )
    figure.text(
        0.03,
        0.065,
        "Source: SRTR public Table B1; calendar years 2022–2025. "
        "One observation per eligible program in each comparison year.",
        fontsize=8,
    )
    figure.text(
        0.03, 0.038, f"Artifact version: {provenance.get('run_id', 'Not reported')}", fontsize=8
    )
    figure.text(0.03, 0.011, _BANNER, fontsize=8)


def _frequency_figure(summary: dict[str, Any], provenance: dict[str, Any]) -> Figure:
    figure = Figure(figsize=(10.5, 3.6))
    ax = figure.add_subplot()
    ax.set_position((0.08, 0.24, 0.88, 0.53))
    labels = ("increased", "unchanged", "decreased")
    for index, year in enumerate(summary["years"]):
        left = 0.0
        annual = summary["annual"][str(year)]
        for direction, color in zip(labels, _COLORS, strict=True):
            frequency = annual["frequency"][direction]
            width = frequency["percent"] or 0
            ax.barh(
                index,
                width,
                left=left,
                color=color,
                height=0.63,
                label=direction.capitalize() if index == 0 else None,
            )
            if width > 0:
                label = f"{frequency['numerator']}/{frequency['denominator']}\n{width:.1f}%"
                ax.text(
                    left + width / 2,
                    index,
                    label,
                    ha="center",
                    va="center",
                    color="white" if direction == "increased" else "#172d3a",
                    fontsize=7 if width < 9 else 9,
                )
            left += width
    ax.set_yticks(range(len(summary["years"])), [str(year) for year in summary["years"]])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of eligible programs whose waiting lists grew (%)")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.03), ncol=3, frameon=False)
    figure.suptitle(
        "List growth and increased transplant removals can occur together",
        x=0.03,
        ha="left",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    _figure_footer(figure, provenance)
    return figure


def _distribution_figure(
    pairs: tuple[Comparison, ...], years: list[int], provenance: dict[str, Any]
) -> Figure:
    """Show every signed observation, with a shared scale across years for each unit."""
    figure = Figure(figsize=(10.5, 4.0))
    for panel, normalized in enumerate((False, True)):
        ax = figure.add_subplot(1, 2, panel + 1)
        ax.set_position((0.075 + panel * 0.49, 0.23, 0.41, 0.51))
        for index, year in enumerate(years):
            selected = sorted(
                (row for row in pairs if row.year == year and row.growth > 0),
                key=lambda row: row.program_key,
            )
            values = [
                -sum(row.removal_contributions[:2]) * (100 / row.start if normalized else 1)
                for row in selected
            ]
            # Deterministic vertical offsets separate ties without changing values on the x-axis.
            offsets = [index + ((position % 11) - 5) * 0.035 for position in range(len(values))]
            ax.scatter(values, offsets, s=11, color=_COLORS[0], alpha=0.62, edgecolors="none")
        ax.axvline(0, color="#637983", lw=0.8)
        ax.set_yticks(range(len(years)), [str(year) for year in years])
        ax.invert_yaxis()
        ax.set_xlabel(
            "Change per 100 current starting registrations"
            if normalized
            else "Change in recorded transplant removals (events)",
            fontsize=9,
        )
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.grid(axis="x", alpha=0.15)
    figure.suptitle(
        "Changes vary: include decreases, zeros and the full observed range",
        x=0.03,
        ha="left",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    figure.text(
        0.03,
        0.85,
        "Each dot is one growing-list program. Left of zero: fewer removals; "
        "right: more. Panels use different units.",
        fontsize=9,
    )
    _figure_footer(figure, provenance)
    return figure


def _worked_figure(brief: dict[str, Any], provenance: dict[str, Any]) -> Figure:
    figure = Figure(figsize=(10.5, 4.6))
    if not brief["available"]:
        figure.text(0.1, 0.5, f"Worked example unavailable: {brief['reason']}")
        _figure_footer(figure, provenance)
        return figure
    change = brief["change"]
    contributions = {"ADDCEN": change["change_additions"], **change["removal_contributions"]}
    ax = figure.add_subplot()
    ax.set_position((0.24, 0.22, 0.63, 0.57))
    values = list(contributions.values())
    bars = ax.barh(list(LABELS.values()), values, color=_COLORS[0], height=0.62)
    ax.invert_yaxis()
    ax.axvline(0, color="#637983", lw=0.8)
    ax.bar_label(
        bars, labels=[_number(value, signed=True) for value in values], padding=4, fontsize=9
    )
    ax.margins(x=0.22)
    ax.set_xlabel("Contribution to change in annual growth (events)")
    ax.spines[["top", "right", "left"]].set_visible(False)
    figure.suptitle(
        f"{brief['program_key']}: the recorded counts explain the change in growth",
        x=0.03,
        ha="left",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    figure.text(
        0.03,
        0.88,
        f"{brief['year']} growth {_number(change['growth'], signed=True)} minus "
        f"{brief['year'] - 1} growth {_number(change['previous_growth'], signed=True)} "
        f"= {_number(change['change_in_growth'], signed=True)} registrations. "
        "More removals contribute a negative count.",
        fontsize=9,
    )
    _figure_footer(figure, provenance)
    return figure


def _inline_figure(files: dict[str, bytes], stem: str, caption: str) -> str:
    svg = files[f"{stem}.svg"].decode("utf-8")
    svg = svg[svg.index("<svg") :]
    return f"<figure>{svg}<figcaption>{caption}</figcaption></figure>"


def _frequency_table(summary: dict[str, Any]) -> str:
    rows = []
    for year in summary["years"]:
        annual = summary["annual"][str(year)]
        row = [str(year), _number(annual["eligible_programs"]), _number(annual["growing_programs"])]
        for direction in ("increased", "unchanged", "decreased"):
            result = annual["frequency"][direction]
            row.append(
                f"{result['numerator']}/{result['denominator']} "
                f"({_number(result['percent'], digits=1)}%)"
            )
        rows.append(row)
    return _table(["Year", "Eligible", "Growing", "Increased", "Unchanged", "Decreased"], rows)


def _distribution_table(summary: dict[str, Any]) -> str:
    rows = []
    for year in summary["years"]:
        for group in ("all_growing", "increased"):
            result = summary["annual"][str(year)]["groups"][group]
            for field in ("change_transplants", "change_transplants_per100"):
                statistics = result[field]
                rows.append(
                    [
                        str(year),
                        "All growing" if group == "all_growing" else "Increased only",
                        "Events" if field == "change_transplants" else "Per 100 starting",
                        str(statistics["n"]),
                    ]
                    + [
                        _number(statistics[name], digits=2)
                        for name in (
                            "minimum",
                            "lower_quartile",
                            "median",
                            "upper_quartile",
                            "maximum",
                        )
                    ]
                )
    return _table(
        [
            "Year",
            "Programs",
            "Unit",
            "n",
            "Minimum",
            "Lower quartile",
            "Median",
            "Upper quartile",
            "Maximum",
        ],
        rows,
    )


def _example_table(examples: list[dict[str, Any]]) -> str:
    labels = {
        "growing_increased": "Growing; more transplant removals",
        "growing_not_increased": "Growing; same or fewer transplant removals",
        "shrinking": "Shrinking list",
    }
    return _table(
        ["Illustration", "Composite program key", "Candidates", "Selected index"],
        [
            [
                labels[row["group"]],
                _text(row["program_key"])
                if row["available"]
                else f"Unavailable: {_text(row['reason'])}",
                _number(row["candidates"]),
                _number(row["selection_index"]),
            ]
            for row in examples
        ],
    )


def _observations_csv(pairs: tuple[Comparison, ...], years: list[int]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "program_key",
            "year",
            "current_start",
            "annual_growth",
            "change_in_growth",
            "change_transplants",
            "change_transplants_per100",
        ]
    )
    for row in sorted(pairs, key=lambda row: (row.year, row.program_key)):
        if row.year in years and row.growth > 0:
            change = -sum(row.removal_contributions[:2])
            writer.writerow(
                [
                    row.program_key,
                    row.year,
                    row.start,
                    row.growth,
                    row.change_in_growth,
                    change,
                    100 * change / row.start,
                ]
            )
    return buffer.getvalue().encode("utf-8")


def _size_narrative(summary: dict[str, Any]) -> str:
    phrases = []
    for year in summary["years"]:
        annual = summary["annual"][str(year)]
        group = annual["groups"]["increased"]
        raw, normalized = group["change_transplants"], group["change_transplants_per100"]
        phrases.append(
            f"{year}: {_number(raw['median'], digits=1)} events "
            f"({_number(normalized['median'], digits=2)} per 100 starting registrations; "
            f"n = {group['programs']})"
        )
    return (
        "<p>Among programs with increased removals, the median increase was "
        + "; ".join(phrases)
        + ". These are separate program medians in each unit. The original screen's magnitude "
        "rules concerned list growth; they did not establish that every transplant-removal "
        "increase was substantial.</p>"
    )


def _coverage_narrative(summary: dict[str, Any], provenance: dict[str, Any]) -> str:
    previous = provenance.get("previous_summary", {})
    coverage = provenance.get("previous_qa", {}).get("annual", {})
    counts = []
    for year in summary["years"]:
        eligible = summary["annual"][str(year)]["eligible_programs"]
        matched = coverage.get(str(year), {}).get("matched_previous_programs")
        counts.append(
            f"{year}: {eligible}" + (f"/{matched} matched programs" if matched else " programs")
        )
    return (
        '<p class="muted">Eligible coverage — '
        + "; ".join(counts)
        + ". Eligibility requires complete, exact annual accounting, continuous year boundaries "
        "and a positive current starting list. Missing reports or excluded records do not mean "
        "zero activity. "
        + (
            f"Plan 0025 retained {previous['common_programs']} programs "
            "eligible in all three years; "
            f"its fixed common-program and starting-list-size checks supported "
            f"{_text(previous['verdict'])}. Those findings are retained without a new gate."
            if previous
            else "Earlier-screen coverage details are unavailable in this rendering."
        )
        + "</p>"
    )


def _retained_tables(provenance: dict[str, Any]) -> str:
    previous = provenance.get("previous_summary", {})
    common = []
    for year, result in previous.get("common_annual", {}).items():
        growing, increased = result["growing_programs"], result["groups"]["increase"]["programs"]
        common.append(
            [
                str(year),
                str(growing),
                f"{increased}/{growing}",
                f"{100 * result['increase_prevalence']:.1f}%",
            ]
        )
    sizes = []
    labels = {
        "under_100": "Starting lists under 100",
        "100_to_499": "Starting lists 100–499",
        "500_or_more": "Starting lists 500 or more",
    }
    for group, result in previous.get("size", {}).items():
        sizes.append(
            [
                labels[group],
                str(result["growing_programs"]),
                f"{100 * result['increase_prevalence']:.1f}%",
                _number(result["groups"]["increase"]["growth_per100"], digits=2),
            ]
        )
    return (
        "<h2>Retained common-program results</h2>"
        "<p>These values are copied from the completed Plan 0025 screen, without repeating "
        "its continuation decision. Each common program was eligible in all three years.</p>"
        + _table(["Year", "Growing programs", "Increased / growing", "Percentage"], common)
        + "<h2>Retained starting-list-size results</h2>"
        "<p>The percentage first averages each program's increase indicator over its growing "
        "years, then averages across programs. Its denominator is the displayed number of "
        "distinct growing programs; it is not a simple pooled event percentage. Growth "
        "per 100 is the median of program medians among increased-removal observations.</p>"
        + _table(
            [
                "Current starting list",
                "Distinct growing programs",
                "Program-weighted percentage",
                "Median list growth per 100",
            ],
            sizes,
        )
    )


def _case_study_html(
    summary: dict[str, Any],
    examples: list[dict[str, Any]],
    briefs: list[dict[str, Any]],
    provenance: dict[str, Any],
    files: dict[str, bytes],
) -> str:
    first = (
        '<section class="page"><p class="eyebrow">Descriptive case study · '
        "public kidney program records</p>"
        "<h1>A larger waiting list can coexist with more transplant removals</h1>"
        '<p class="lead">Read additions and all removal categories together before interpreting '
        "a growing or shrinking list.</p>"
        + _metadata(provenance)
        + _source_summary(provenance.get("source_vintages", []))
        + "<p>This case study asks how often waiting-list growth accompanied increased transplant "
        "removals, how large those changes were, and how actual program counts account for growth. "
        "One record is a program and calendar year; it counts registration and removal events, "
        "not nationally unique people. Transplant removals combine deceased and living donors "
        "at the reporting program; transplant elsewhere remains separate.</p>"
        + _inline_figure(
            files,
            "frequency",
            "The denominator is eligible programs whose lists grew "
            "during the year. Transplant-removal change compares that year "
            "with the preceding year.",
        )
        + _frequency_table(summary)
        + _coverage_narrative(summary, provenance)
        + _inline_figure(
            files,
            "signed_changes",
            "Observed changes retain the full range. Vertical "
            "offsets separate dots only; they carry no extra meaning. No curve is fitted.",
        )
        + _size_narrative(summary)
        + "</section>"
    )
    second = (
        '<section class="page"><p class="eyebrow">From the national description to one program</p>'
        "<h1>Follow the recorded additions and removals</h1>"
        "<p>Annual growth is ending minus starting registrations. "
        "<strong>Change in growth</strong> "
        "is this year's growth minus last year's: change in additions minus changes in all eight "
        "removal categories. A growing list can be growing more slowly.</p>"
        + _inline_figure(
            files,
            "worked_counts",
            "The first fixed example illustrates exact accounting. "
            "Positive contributions increase annual growth; negative contributions reduce it.",
        )
    )
    if briefs and briefs[0]["available"]:
        second += "<h2>Both annual equations</h2>" + _annual_equations(briefs[0])
    second += (
        "<h2>Three illustrations, chosen before viewing individual records</h2>"
        "<p>Within each group, sort the programs eligible in all three comparison years by "
        "2025 starting registrations and composite program key. Choose the lower middle record, "
        "at zero-based index floor((n − 1) / 2). An empty group stays unavailable. These examples "
        "illustrate arithmetic; they are not a representative sample or "
        "a comparison of quality.</p>"
        + _example_table(examples)
        + "<h2>Practical interpretation and limits</h2>"
        "<p>Review referral and listing records alongside additions, and transplant activity "
        "alongside transplant removals. Examine transplant elsewhere, transfers, deaths, "
        "deterioration, recovery and other removals separately. The counts suggest records to "
        "review; they do not establish causes or prescribe an intervention.</p>"
        "<p>Per-100 values divide each program's change by its current starting registrations, "
        "then multiply by 100. They are not a patient probability, a percent increase from "
        "last year's transplants or a rate per patient-year. Each program has one weight per "
        "year; repeated years are not independent. Quartiles mark the middle half of programs, "
        "calculated with linear interpolation. Full tables and the reusable program briefs "
        "retain exact counts, zero values and exclusions.</p>"
        "<p>This is further description of already-inspected public data. Earlier forecasting "
        "studies are project history; this case study adds no model, fresh validation, claim of "
        "novelty or demonstrated decision benefit.</p>"
        + _metadata(provenance)
        + _source_summary(provenance.get("source_vintages", []))
        + "</section>"
    )
    return _document("Waiting-list analytical case study", first + second, css_class="case-study")


def render_case_study(
    summary: dict[str, Any],
    examples: list[dict[str, Any]],
    briefs: list[dict[str, Any]],
    pairs: tuple[Comparison, ...],
    provenance: dict[str, Any],
) -> dict[str, bytes]:
    """Return standalone HTML, full distribution tables, observations and three figures."""
    with rc_context(
        {
            "svg.hashsalt": "kasm-waiting-list-0026-v1",
            "svg.fonttype": "none",
            "font.family": "DejaVu Sans",
            "font.size": 10,
        }
    ):
        figures = {
            **_figure_files(_frequency_figure(summary, provenance), "frequency"),
            **_figure_files(
                _distribution_figure(pairs, summary["years"], provenance), "signed_changes"
            ),
            **_figure_files(
                _worked_figure(
                    briefs[0] if briefs else {"available": False, "reason": "No selected example."},
                    provenance,
                ),
                "worked_counts",
            ),
        }
    support = (
        '<section class="page support"><p class="eyebrow">Case study · supporting tables</p>'
        "<h1>Frequency, observed changes and selected examples</h1>"
        + _metadata(provenance)
        + "<h2>Frequency among growing-list programs</h2>"
        + _frequency_table(summary)
        + _coverage_narrative(summary, provenance)
        + "<h2>Signed change in recorded transplant removals</h2>"
        "<p>Quartiles mark the middle half of programs using linear interpolation. The median "
        "is the middle value. Each program has one weight within a year. All growing programs "
        "include decreases, unchanged counts and increases; the increased subgroup is separate.</p>"
        + _distribution_table(summary)
        + "<p>Per 100 means events divided by that program's current starting registrations × 100. "
        "It is not a patient probability or a rate per patient-year.</p>"
        + "<h2>Fixed example selection</h2>"
        + _example_table(examples)
        + _retained_tables(provenance)
        + _source_rows(provenance.get("source_vintages", []))
        + "</section>"
    )
    return figures | {
        "case_study.html": _case_study_html(
            summary, examples, briefs, provenance, figures
        ).encode(),
        "supporting_tables.html": _document("Case study supporting tables", support).encode(),
        "observations.csv": _observations_csv(pairs, summary["years"]),
    }
