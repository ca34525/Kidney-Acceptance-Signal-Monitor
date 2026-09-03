"""Offline Streamlit view over trusted Kidney Acceptance Signal Monitor artifacts."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from kasm.reporting.history import (
    HistoricalDataError,
    HistoricalPoint,
    SubgroupPoint,
    latest_overall_status,
    latest_persistence_projection,
    latest_subgroup_rows,
    latest_volume_context,
    load_historical_artifacts,
    overall_history,
    program_options,
    subgroup_history,
)
from kasm.reporting.product import ModelEvaluation, ProductDataError, load_model_evaluation

_NONCLINICAL_BANNER = "Public aggregate prototype — not clinical or regulatory decision support"


def _artifact_dir() -> Path:
    configured = os.environ.get("KASM_ARTIFACT_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "data" / "processed"


def _modeling_dir() -> Path:
    configured = os.environ.get("KASM_MODELING_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "data" / "modeling"


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


def _subgroup_chart(points: tuple[SubgroupPoint, ...]) -> dict[str, object]:
    values = [
        {
            "cohort_year": point.cohort_year,
            "offer_group": point.offer_group,
            "label": point.label,
            "oar_mean": point.oar_mean,
            "oar_lower": point.oar_lower,
            "oar_upper": point.oar_upper,
            "offers": point.offers,
            "expected_acceptances": point.expected_acceptances,
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
        "facet": {
            "field": "label",
            "type": "nominal",
            "columns": 2,
            "title": "Published donor stratum",
            "sort": ["Low KDRI", "Medium KDRI", "High KDRI", "Hard-to-place"],
        },
        "spec": {
            "width": 330,
            "height": 165,
            "layer": [
                {
                    "mark": {"type": "rule", "color": "#59636e", "strokeDash": [5, 4]},
                    "encoding": {"y": {"datum": 1}},
                },
                {
                    "mark": {"type": "rule", "color": "#7a5195", "strokeWidth": 2},
                    "encoding": {
                        "x": x_encoding,
                        "y": {
                            "field": "oar_lower",
                            "type": "quantitative",
                            "title": "Published OAR",
                            "scale": {"zero": False},
                        },
                        "y2": {"field": "oar_upper"},
                    },
                },
                {
                    "mark": {
                        "type": "line",
                        "color": "#315f7d",
                        "point": {"filled": True, "size": 65},
                    },
                    "encoding": {
                        "x": x_encoding,
                        "y": {
                            "field": "oar_mean",
                            "type": "quantitative",
                            "title": "Published OAR",
                            "scale": {"zero": False},
                        },
                        "tooltip": [
                            {"field": "label", "title": "Stratum"},
                            {"field": "cohort_year", "title": "Cohort"},
                            {"field": "oar_mean", "title": "Published OAR", "format": ".2f"},
                            {"field": "oar_lower", "title": "95% lower", "format": ".2f"},
                            {"field": "oar_upper", "title": "95% upper", "format": ".2f"},
                            {"field": "offers", "title": "Offers", "format": ",d"},
                            {
                                "field": "expected_acceptances",
                                "title": "Expected acceptances",
                                "format": ".2f",
                            },
                        ],
                    },
                },
            ],
        },
        "resolve": {"scale": {"y": "independent"}},
        "config": {"view": {"stroke": None}},
    }


def _model_status_message(evaluation: ModelEvaluation) -> str:
    if evaluation.activation_status == "not_attempted":
        return "Persistence retained because forecast activation was not attempted."
    if evaluation.activation_status == "promoted":
        return "The ridge point model passed the frozen promotion criteria."
    reasons = {
        "minimum_skill": "ridge skill was below the frozen minimum",
        "bootstrap_interval_below_zero": "the paired-bootstrap interval did not stay below zero",
        "maximum_absolute_bias": "ridge absolute mean signed bias exceeded the frozen limit",
        "bias_not_exceed_persistence": "ridge absolute mean signed bias exceeded persistence",
        "lowest_quartile_relative_worsening": "lowest-volume performance missed its frozen limit",
        "minimum_lowest_quartile_rows": "lowest-volume evidence was too sparse",
    }
    rendered = [
        reasons.get(reason, reason.replace("_", " ")) for reason in evaluation.point_failed_criteria
    ]
    return "Persistence retained after the frozen 2025 replay because " + "; ".join(rendered) + "."


def _comparison_rows(evaluation: ModelEvaluation) -> list[dict[str, object]]:
    return [
        {
            "Target year": row.target_year,
            "Programs": row.n,
            "Neutral MAE": f"{row.neutral_mae_log_oar:.3f}",
            "Persistence MAE": f"{row.persistence_mae_log_oar:.3f}",
            "Historical mean MAE": f"{row.historical_mean_mae_log_oar:.3f}",
            "Ridge MAE": f"{row.ridge_mae_log_oar:.3f}",
            "Ridge skill vs persistence": f"{row.ridge_skill_over_persistence:.1%}",
        }
        for row in evaluation.temporal_comparisons
    ]


st.set_page_config(page_title="Kidney Acceptance Signal Monitor", layout="wide")
st.warning(_NONCLINICAL_BANNER)
st.title("Kidney Acceptance Signal Monitor")
st.caption(
    "Historical public SRTR screening signals for quality-improvement review. "
    "Published ratios and intervals are descriptive, not program ratings."
)

try:
    artifacts = load_historical_artifacts(_artifact_dir())
    evaluation = load_model_evaluation(
        _modeling_dir(), expected_panel_sha256=artifacts.panel_sha256
    )
    choices = program_options(artifacts)
except (HistoricalDataError, ProductDataError) as exc:
    st.error(f"Trusted offline artifacts are unavailable: {exc}")
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
subgroup_points = subgroup_history(artifacts, selected_key)
projection = latest_persistence_projection(artifacts, selected_key)

st.header(labels[selected_key])
st.caption(
    f"Source cohort: {latest.cohort_year} "
    f"({latest.cohort_start.isoformat()} to {latest.cohort_end.isoformat()}) · "
    f"Published: {latest.publication_display} · "
    f"Data version: {artifacts.artifact_version} · "
    f"Model version: {evaluation.model_version} · "
    f"Source-manifest version: {evaluation.source_manifest_version}"
)

program_tab, evaluation_tab = st.tabs(["Program monitor", "Model evaluation and methodology"])

with program_tab:
    st.subheader("Published overall OAR history")
    st.vega_lite_chart(_history_chart(history), width="stretch")
    st.caption(
        "Points are SRTR-published offer-acceptance ratios; vertical marks are SRTR 95% credible "
        "intervals. The dashed reference is 1. Cohorts are non-overlapping calendar years. "
        "Source: Scientific Registry of Transplant Recipients."
    )

    oar_display = "Not reported" if latest.oar_mean is None else f"{latest.oar_mean:.2f}"
    first_metric, second_metric, third_metric = st.columns(3)
    first_metric.metric("Latest published OAR", oar_display)
    second_metric.metric("Overall offers", volume.offers_display)
    third_metric.metric("Expected acceptances", volume.expected_acceptances_display)
    st.info(f"Latest historical interval status: {status.label}.")

    st.subheader("Donor-stratum history")
    st.vega_lite_chart(_subgroup_chart(subgroup_points), width="stretch")
    st.caption(
        "Points and vertical marks are published donor-stratum OARs and SRTR 95% credible "
        "intervals by calendar-year cohort. Gaps mean Not reported; they are never plotted as "
        "zero. Source: Scientific Registry of Transplant Recipients."
    )

    st.subheader(f"Latest donor-stratum detail — {latest.cohort_year} cohort")
    st.table(
        [
            {
                "Published stratum": subgroup.label,
                "OAR (SRTR 95% credible interval)": subgroup.oar_display,
                "Offers": subgroup.offers_display,
                "Expected acceptances": subgroup.expected_acceptances_display,
            }
            for subgroup in subgroups
        ]
    )
    st.caption(
        "Hard-to-place offers can overlap KDRI strata. These rows must not be summed or "
        "interpreted as explaining the overall signal."
    )

    st.subheader("Next-calendar-year PSR projection")
    if projection.eligible:
        if evaluation.displayed_model == "persistence" and projection.point_oar is not None:
            forecast_metric, target_metric = st.columns(2)
            forecast_metric.metric("Persistence projection", f"{projection.point_oar:.2f}")
            target_metric.metric("Target calendar-year cohort", str(projection.target_cohort_year))
            st.caption(
                f"The displayed screening signal carries the {projection.feature_cohort_year} "
                f"published OAR forward. Prediction origin: {projection.prediction_as_of_display}; "
                f"{projection.elapsed_target_cohort_fraction:.1%} of the target cohort had "
                "elapsed. "
                "This is a delayed-report nowcast, not a clean 12-month-ahead forecast."
            )
        else:
            st.info(
                "The trusted artifact marks this program eligible, but no activated ridge point "
                "artifact is available for display."
            )
        st.info(_model_status_message(evaluation))
        if not evaluation.display_band:
            if evaluation.band_suppression_reason == "ridge_point_not_promoted":
                st.info(
                    "No nominal 80% empirical forecast band is displayed because the ridge point "
                    "model was not promoted. The ridge band gate was evaluated separately."
                )
            else:
                st.info(
                    "No nominal 80% empirical forecast band is displayed because its separate "
                    "frozen display gate did not pass."
                )
    else:
        st.info(
            "Insufficient history or artifact ineligibility: no projection is displayed. "
            "Eligibility comes from the trusted public_forecast_eligible artifact field."
        )

with evaluation_tab:
    st.subheader("Model evaluation")
    st.info(_model_status_message(evaluation))
    st.table(_comparison_rows(evaluation))
    st.caption(
        "Rolling-origin errors are mean absolute error on published log OAR. Each target year is "
        "kept intact, and preprocessing is fit only on prior-year training rows."
    )

    replay = evaluation.replay
    st.subheader(f"Frozen {replay.target_year} implementation replay")
    ridge_metric, persistence_metric, skill_metric = st.columns(3)
    ridge_metric.metric("Ridge log-OAR MAE", f"{replay.ridge_mae_log_oar:.3f}")
    persistence_metric.metric("Persistence log-OAR MAE", f"{replay.persistence_mae_log_oar:.3f}")
    skill_metric.metric("Ridge skill vs persistence", f"{replay.skill_over_persistence:.1%}")
    st.caption(
        f"Descriptive retrospective product-selection evidence across {replay.n} programs. "
        f"Paired-bootstrap interval for ridge minus persistence absolute error: "
        f"{replay.bootstrap_interval[0]:.3f} to {replay.bootstrap_interval[1]:.3f}. "
        "The replay was previously inspected during planning and is not an independent test; "
        "the ridge model remains prospectively unvalidated."
    )
    st.write(
        f"Mean signed log error: ridge {replay.ridge_mean_signed_log_error:.3f}; "
        f"persistence {replay.persistence_mean_signed_log_error:.3f}. The frozen point gate "
        "uses absolute bias as a separate criterion from MAE."
    )

    with st.expander("Methodology and limitations"):
        st.write(
            "The modeling unit is a kidney transplant program-year, and the target is the next "
            "same-cadence calendar-year published log OAR. Rolling target years stay intact; no "
            "random row split is used. The frozen replay fit uses target years 2018–2023, while "
            "2024 remains excluded from fitting because it calibrates the separate residual band."
        )
        st.write(
            "Historical vertical marks are SRTR 95% credible intervals for published ratios. An "
            "empirical forecast band is a different quantity: it is marginal across programs and "
            "does not provide center-conditional coverage. No empirical band is active in this "
            "release."
        )
        st.write(
            "This public aggregate screening signal can support quality-improvement review but "
            "cannot determine whether an individual offer should have been accepted, identify a "
            "causal driver, or provide clinical or allocation advice. Cross-year change may also "
            "reflect national-practice and SRTR model-vintage changes."
        )

    with st.expander("Artifact provenance"):
        st.write(
            f"Data version: {artifacts.artifact_version}; model version: "
            f"{evaluation.model_version}; source manifest: "
            f"{evaluation.source_manifest_version}; frozen ridge alpha: "
            f"{evaluation.selected_alpha:g}; replay Git commit: {evaluation.git_commit_sha}."
        )
