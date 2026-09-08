"""Show every forecast error on common scales without ranking named programs.

Figures use cumulative shares so extreme observations remain visible without an
assumed distribution or a chosen histogram width. The trusted caller writes PNG
payloads to its isolated run; this module performs no filesystem or source reads.
"""

from __future__ import annotations

import io
from collections import defaultdict
from typing import Any

from matplotlib import rc_context
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from kasm.acceptance_forecast.diagnostics import error_values

_UNITS = {
    "ratio": "ratio units",
    "percentage": "% of the published ratio",
    "log": "natural-log ratio units",
}
_ROLES = {
    "saved_selection_backtest": "saved selection backtest",
    "saved_validation_backtest": "saved validation backtest",
    "original_frozen_replay": "original frozen replay",
    "retrospective_refit": "retrospective refit",
}
_COLORS = ("#164d70", "#b5671f", "#337d69", "#805e9b", "#a94154", "#4e5961")
_STYLES = ("-", "--", "-.", ":", (0, (5, 1, 1, 1)), (0, (3, 1, 1, 1, 1, 1)))


def _prepared_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reject ambiguous year roles or invalid ratios before creating any figure."""
    if not records:
        raise ValueError("Error plots require at least one eligible prediction record.")
    roles: dict[int, str] = {}
    prepared = []
    for record in records:
        year = record.get("target_cohort_year")
        role = record.get("evidence_role")
        model = record.get("model")
        if isinstance(year, bool) or not isinstance(year, int):
            raise ValueError("Each plot record requires an integer target cohort year.")
        if not isinstance(role, str) or role not in _ROLES:
            raise ValueError("Each plot record requires a recognized evidence role.")
        if year in roles and roles[year] != role:
            raise ValueError("A cohort year cannot combine different evidence roles in one plot.")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Each plot record requires a model name.")
        roles[year] = role
        prepared.append(
            record | error_values(record.get("target_oar"), record.get("predicted_oar"))
        )
    return prepared


def _draw_year(
    axis: Axes,
    records: list[dict[str, Any]],
    models: list[str],
    error_key: str,
) -> None:
    """The last step reaches every program, including any extreme error."""
    by_model: dict[str, list[float]] = defaultdict(list)
    for record in records:
        by_model[record["model"]].append(record[error_key])
    for index, model in enumerate(models):
        values = sorted(by_model[model])
        if not values:
            continue
        shares = [0.0, *(100 * (i + 1) / len(values) for i in range(len(values)))]
        axis.step(
            [values[0], *values],
            shares,
            where="post",
            color=_COLORS[index % len(_COLORS)],
            linestyle=_STYLES[index % len(_STYLES)],
            linewidth=1.65,
            label=f"{model.replace('_', ' ')} (n={len(values)})",
        )
    axis.set_ylim(0, 102)
    axis.set_yticks([0, 25, 50, 75, 100])
    axis.set_ylabel("Programs at or below error (%)")
    axis.grid(alpha=0.2)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(loc="lower right", fontsize=8, framealpha=0.9)


def _error_figure(records: list[dict[str, Any]], unit: str, provenance: dict[str, Any]) -> Figure:
    """Pair signed and absolute cumulative distributions for each outcome year."""
    if unit not in _UNITS:
        raise ValueError("Error plot unit must be ratio, percentage or log.")
    prepared = _prepared_records(records)
    years = sorted({row["target_cohort_year"] for row in prepared})
    models = sorted({row["model"] for row in prepared})
    signed_key = f"signed_{unit}_error"
    absolute_key = f"absolute_{unit}_error"
    largest = max(row[absolute_key] for row in prepared)
    limit = largest * 1.04 if largest else 1.0
    figure = Figure(figsize=(12, 2.75 * len(years) + 2.4), facecolor="white")
    axes = figure.subplots(len(years), 2, squeeze=False)
    for index, year in enumerate(years):
        year_records = [row for row in prepared if row["target_cohort_year"] == year]
        role = _ROLES[year_records[0]["evidence_role"]]
        for column, key in enumerate((signed_key, absolute_key)):
            axis = axes[index, column]
            _draw_year(axis, year_records, models, key)
            axis.set_xlim((-limit, limit) if column == 0 else (0, limit))
            kind = "Signed error" if column == 0 else "Absolute error"
            axis.set_title(f"{year} · {role}\n{kind}", loc="left", fontsize=10)
            axis.set_xlabel(f"{kind} ({_UNITS[unit]})")
        axes[index, 0].axvline(0, color="#53616b", linewidth=0.8, alpha=0.6)
    figure.suptitle(
        f"Next-calendar-year PSR projection errors · {_UNITS[unit]}",
        x=0.07,
        y=0.98,
        ha="left",
        fontsize=15,
        fontweight="bold",
    )
    figure.text(
        0.07,
        0.94,
        "Each line includes every eligible program in that year. Positive signed errors "
        "mean overprediction.\nScales match across years; extreme errors are retained. "
        "Previously inspected outcomes are exploratory evidence.",
        ha="left",
        va="top",
        fontsize=9,
        linespacing=1.5,
    )
    publication = provenance.get("publication_label", "Publication dates: see run provenance.")
    figure.text(
        0.07,
        0.022,
        "Source: published SRTR program ratios. "
        f"{publication}\nArtifact: {provenance.get('run_id', 'Not reported')}. "
        "Public aggregate prototype; not clinical or regulatory decision support.",
        fontsize=8,
        va="bottom",
        linespacing=1.5,
    )
    figure.subplots_adjust(top=0.85, bottom=0.14, left=0.07, right=0.98, hspace=0.68, wspace=0.22)
    return figure


def render_error_plots(
    records: list[dict[str, Any]], provenance: dict[str, Any]
) -> dict[str, bytes]:
    """Return three offline PNG files; the trusted run boundary owns publication."""
    _prepared_records(records)
    files = {}
    with rc_context({"font.family": "DejaVu Sans", "font.size": 9}):
        for unit in _UNITS:
            figure = _error_figure(records, unit, provenance)
            buffer = io.BytesIO()
            figure.savefig(buffer, format="png", dpi=160, facecolor="white")
            files[f"error_distributions_{unit}.png"] = buffer.getvalue()
            figure.clear()
    return files
