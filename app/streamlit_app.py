"""Offline Streamlit view over trusted Kidney Acceptance Signal Monitor artifacts."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from kasm.reporting.history import (
    HistoricalDataError,
    HistoricalPoint,
    latest_overall_status,
    latest_public_forecast_eligibility,
    latest_subgroup_rows,
    latest_volume_context,
    load_historical_artifacts,
    overall_history,
    program_options,
)

_NONCLINICAL_BANNER = "Public aggregate prototype — not clinical or regulatory decision support"


def _artifact_dir() -> Path:
    configured = os.environ.get("KASM_ARTIFACT_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "data" / "processed"


def _history_chart(points: tuple[HistoricalPoint, ...]) -> dict[str, object]:
    values = [
        {
            "cohort_year": point.cohort_year,
            "oar_mean": point.oar_mean,
            "oar_lower": point.oar_lower,
            "oar_upper": point.oar_upper,
            "publication": point.publication_display,
        }
        for point in points
    ]
    x_encoding = {
        "field": "cohort_year",
        "type": "ordinal",
        "title": "Calendar-year offer cohort",
    }
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
        "data": {"values": values},
        "height": 320,
        "layer": [
            {
                "mark": {"type": "rule", "color": "#59636e", "strokeDash": [5, 4]},
                "encoding": {"y": {"datum": 1}},
            },
            {
                "mark": {"type": "rule", "color": "#315f7d", "strokeWidth": 3},
                "encoding": {
                    "x": x_encoding,
                    "y": {
                        "field": "oar_lower",
                        "type": "quantitative",
                        "title": "Published offer-acceptance ratio",
                        "scale": {"zero": False},
                    },
                    "y2": {"field": "oar_upper"},
                    "tooltip": [
                        {"field": "cohort_year", "title": "Cohort"},
                        {"field": "oar_lower", "title": "95% lower", "format": ".2f"},
                        {"field": "oar_upper", "title": "95% upper", "format": ".2f"},
                    ],
                },
            },
            {
                "mark": {
                    "type": "line",
                    "color": "#315f7d",
                    "point": {"filled": True, "size": 90},
                },
                "encoding": {
                    "x": x_encoding,
                    "y": {
                        "field": "oar_mean",
                        "type": "quantitative",
                        "title": "Published offer-acceptance ratio",
                        "scale": {"zero": False},
                    },
                    "tooltip": [
                        {"field": "cohort_year", "title": "Cohort"},
                        {"field": "oar_mean", "title": "Published OAR", "format": ".2f"},
                        {"field": "publication", "title": "Published"},
                    ],
                },
            },
        ],
        "config": {"view": {"stroke": None}},
    }


st.set_page_config(page_title="Kidney Acceptance Signal Monitor", layout="wide")
st.warning(_NONCLINICAL_BANNER)
st.title("Kidney Acceptance Signal Monitor")
st.caption(
    "Historical public SRTR screening signals for quality-improvement review. "
    "Published ratios and intervals are descriptive, not program ratings."
)

try:
    artifacts = load_historical_artifacts(_artifact_dir())
    choices = program_options(artifacts)
except HistoricalDataError as exc:
    st.error(f"Historical artifacts are unavailable: {exc}")
    st.stop()

if not choices:
    st.error("Historical artifacts contain no selectable kidney transplant programs.")
    st.stop()

labels = {choice.program_key: choice.label for choice in choices}
selected_key = st.selectbox(
    "Kidney transplant program",
    options=tuple(labels),
    format_func=labels.__getitem__,
)

history = overall_history(artifacts, selected_key)
latest = history[-1]
status = latest_overall_status(artifacts, selected_key)
volume = latest_volume_context(artifacts, selected_key)
subgroups = latest_subgroup_rows(artifacts, selected_key)
eligibility = latest_public_forecast_eligibility(artifacts, selected_key)

st.header(labels[selected_key])
st.caption(
    f"Source cohort: {latest.cohort_year} "
    f"({latest.cohort_start.isoformat()} to {latest.cohort_end.isoformat()}) · "
    f"Published: {latest.publication_display} · "
    f"Artifact version: {artifacts.artifact_version}"
)

st.subheader("Published overall OAR history")
st.vega_lite_chart(_history_chart(history), width="stretch")
st.caption(
    "Points are SRTR-published offer-acceptance ratios; vertical marks are SRTR 95% credible "
    "intervals. The dashed reference is 1. Source: Scientific Registry of Transplant Recipients."
)

oar_display = "Not reported" if latest.oar_mean is None else f"{latest.oar_mean:.2f}"
first_metric, second_metric, third_metric = st.columns(3)
first_metric.metric("Latest published OAR", oar_display)
second_metric.metric("Overall offers", volume.offers_display)
third_metric.metric("Expected acceptances", volume.expected_acceptances_display)
st.info(f"Latest historical interval status: {status.label}.")

st.subheader(f"Donor strata — {latest.cohort_year} cohort")
st.table(
    [
        {
            "Published stratum": subgroup.label,
            "OAR (95% credible interval)": subgroup.oar_display,
            "Offers": subgroup.offers_display,
            "Expected acceptances": subgroup.expected_acceptances_display,
        }
        for subgroup in subgroups
    ]
)
st.caption(
    "Hard-to-place offers can overlap KDRI strata. These rows must not be summed or interpreted "
    "as explaining the overall signal."
)

st.subheader("Next-calendar-year PSR projection")
if eligibility.eligible:
    st.info(
        f"The trusted artifact marks this program eligible for a {eligibility.target_cohort_year} "
        "next-calendar-year PSR projection. Model output is not included in this historical "
        "walking skeleton."
    )
else:
    st.info(
        "Insufficient history or artifact ineligibility: no projection is displayed. "
        "Eligibility comes from the trusted public_forecast_eligible artifact field."
    )

with st.expander("Methodology and limitations"):
    st.write(
        "The modeling unit is a kidney transplant program-year. Historical values are published "
        "SRTR aggregate offer-acceptance ratios; this view does not recreate SRTR's offer-level "
        "model. A signal can support quality-improvement review but cannot determine whether an "
        "individual offer should have been accepted."
    )
