from __future__ import annotations

from pathlib import Path
from typing import cast

import pyarrow as pa
import streamlit as st

from kasm.patient_journey.product import (
    PatientJourneyProduct,
    PatientJourneyProductError,
    load_patient_journey_product,
    measurement_segments_text,
    program_options,
    program_panel,
    program_predictions,
    program_safety,
    publication_value_text,
    published_date_text,
    reported_value,
)

PROJECT_ROOT = Path(__file__).parents[1]
RELEASE_DIR = PROJECT_ROOT / "artifacts" / "patient_journey_v2"
MODEL_ORDER = (
    "persistence",
    "available_cohort_reference",
    "historical_mean",
    "history",
    "history_acceptance",
    "history_access",
    "history_access_acceptance",
    "history_access_acceptance_safety",
)
MODEL_LABELS = {
    "persistence": "Persistence baseline",
    "available_cohort_reference": "Available-cohort reference",
    "historical_mean": "Historical-mean baseline",
    "history": "Ridge: history",
    "history_acceptance": "Ridge: history + acceptance",
    "history_access": "Ridge: history + access",
    "history_access_acceptance": "Ridge: history + access + acceptance",
    "history_access_acceptance_safety": "Ridge: full + safety",
}
SAFETY_LABELS = {
    "waiting_list_mortality": "Waiting-list mortality",
    "mortality_after_listing": "Mortality after listing",
    "graft_failure_90_day": "90-day graft failure",
    "graft_failure_1_year_conditional": "One-year graft failure, conditional on day 90",
}


@st.cache_resource(show_spinner=False)
def load_release() -> PatientJourneyProduct:
    return load_patient_journey_product(RELEASE_DIR)


st.set_page_config(
    page_title="Patient journey research view",
    page_icon=":material/route:",
    layout="wide",
)

st.title("Patient journey research view")
st.caption("Kidney program history, exploratory evaluation, and separately timed safety context")
st.warning(
    "Public aggregate prototype; not patient-level and not causal decision support. Nonclinical "
    "and nonregulatory research view. The patient-journey target is an observed published "
    "percentage and is not officially risk adjusted. No model promoted; no future forecast is "
    "available from this one-fold retrospective study."
)

try:
    product = load_release()
except PatientJourneyProductError as error:
    st.error(f"The trusted offline V2 release could not be loaded: {error}")
    st.stop()

options = program_options(product)
if not options:
    st.error("The trusted V2 release has no program history rows.")
    st.stop()
labels = [option.label for option in options]
option_by_label = {option.label: option for option in options}

with st.sidebar:
    st.subheader("Research filters")
    selected_label = st.selectbox(
        "Kidney transplant program",
        labels,
        key="program_selector",
    )
    st.caption("Selection changes program-level context only; it does not create a score.")

selected = option_by_label[selected_label]
panel = program_panel(product, selected.program_key)
predictions = program_predictions(product, selected.program_key)
safety = program_safety(product, selected.program_key)
panel_rows = panel.to_pylist()
prediction_rows = predictions.to_pylist()
safety_rows = safety.to_pylist()
latest = panel_rows[-1]

st.header(cast(str, latest["center_name"]))
location = ", ".join(
    cast(str, value) for value in (latest.get("city"), latest.get("state")) if value
)
st.caption(f"{location} · Program key {selected.program_key}" if location else selected.program_key)

manifest_provenance = cast(dict[str, object], product.manifest["provenance"])
with st.container(horizontal=True):
    st.metric("Historical feature–target pairs", len(panel_rows), border=True)
    st.metric(
        "Published outcomes available",
        sum(row["target_published_percent"] is not None for row in panel_rows),
        border=True,
    )
    st.metric(
        "Safety families available",
        len({row["family"] for row in safety_rows}),
        border=True,
    )
    st.metric("Promoted models", "0", border=True)

st.caption(
    "Trusted offline artifact v1 · "
    f"bundle {str(product.release.bundle_content_sha256)[:12]}… · "
    "primary target releases 2205, 2305, 2405, and 2505"
)

history_tab, evidence_tab, safety_tab, methods_tab = st.tabs(
    [
        ":material/route: Program history",
        ":material/analytics: Model evidence",
        ":material/health_metrics: Safety context",
        ":material/fact_check: Methods and provenance",
    ]
)

with history_tab:
    st.subheader("Published patient-journey history")
    st.caption(
        "Each row links a feature-release snapshot to a later, nonoverlapping listing cohort. "
        "Missing future reports remain missing; they are not treated as negative outcomes."
    )
    history_records = [
        {
            "Feature release": row["feature_release_code"],
            "Prediction origin": publication_value_text(
                row["prediction_origin_value"], row["prediction_origin_precision"]
            ),
            "Target release": row["target_release_code"],
            "Target publication": publication_value_text(
                row["target_published_value"], row["target_published_precision"]
            ),
            "Listing cohort": (
                f"{published_date_text(row['target_listing_cohort_start'])} to "
                f"{published_date_text(row['target_listing_cohort_end'])}"
            ),
            "Published outcome (%)": reported_value(row["target_published_percent"]),
            "Candidate N": reported_value(row["target_n"], digits=0),
            "Prior published outcome (%)": reported_value(row["prior_target_published_percent"]),
            "Eligibility": str(row["eligibility_status"]).replace("_", " "),
        }
        for row in panel_rows
    ]
    st.dataframe(history_records, hide_index=True)

    observed_chart_rows = [
        {
            "Target release": row["target_release_code"],
            "Published outcome (%)": row["target_published_percent"],
        }
        for row in panel_rows
        if row["target_published_percent"] is not None
    ]
    if observed_chart_rows:
        st.line_chart(
            pa.Table.from_pylist(observed_chart_rows),
            x="Target release",
            y="Published outcome (%)",
        )

    st.subheader("Feature-release access and acceptance context")
    feature_records = [
        {
            "Feature release": row["feature_release_code"],
            "Transplant-rate ratio": reported_value(row["transplant_rate_ratio"], digits=2),
            "Transplant person-years": reported_value(
                row["transplant_rate_person_years"], digits=1
            ),
            "25th-percentile wait (months)": reported_value(
                row["wait_time_months_25th_percentile"], digits=1
            ),
            "Published offer-acceptance ratio": reported_value(
                row["acceptance_overall_oar"], digits=2
            ),
            "Expected acceptances": reported_value(
                row["acceptance_overall_expected_acceptances"], digits=1
            ),
        }
        for row in panel_rows
    ]
    st.dataframe(feature_records, hide_index=True)

    st.subheader("Historical evaluation for this program")
    st.caption(
        "These are predictions for cohorts whose outcomes are already published. They are "
        "evaluation evidence, not a next-cohort projection."
    )
    if prediction_rows:
        panel_by_target_release = {row["target_release_code"]: row for row in panel_rows}
        prediction_records = []
        for row in prediction_rows:
            timing = panel_by_target_release[row["target_release_code"]]
            prediction_records.append(
                {
                    "Target release": row["target_release_code"],
                    "Prediction origin": publication_value_text(
                        timing["prediction_origin_value"],
                        timing["prediction_origin_precision"],
                    ),
                    "Target publication": publication_value_text(
                        timing["target_published_value"],
                        timing["target_published_precision"],
                    ),
                    "Model": MODEL_LABELS.get(cast(str, row["model"]), cast(str, row["model"])),
                    "Observed (%)": reported_value(row["target_published_percent"]),
                    "Evaluated prediction (%)": reported_value(row["predicted_percent"]),
                    "Absolute error (percentage points)": reported_value(
                        row["absolute_error_percentage_points"]
                    ),
                }
            )
        st.dataframe(prediction_records, hide_index=True)
    else:
        st.info("Insufficient history for an eligible retrospective evaluation row.")

with evidence_tab:
    st.subheader("Prespecified retrospective evaluation")
    st.info(
        "The three baselines cover four target releases. Ridge is limited to one strict-vintage "
        "fold: train on 1905→2205 and evaluate on 2205→2505. Their aggregate scopes differ."
    )
    models = cast(dict[str, object], product.evaluation["models"])
    metric_records = []
    for model in MODEL_ORDER:
        model_payload = cast(dict[str, object], models[model])
        primary = cast(dict[str, object], model_payload["primary"])
        metric_records.append(
            {
                "Model": MODEL_LABELS[model],
                "Scope": ", ".join(cast(list[str], primary["target_releases"])),
                "N": primary["n"],
                "MAE (percentage points)": round(
                    cast(float, primary["target_release_balanced_mae_percentage_points"]), 2
                ),
                "Volume-weighted MAE": round(
                    cast(float, primary["candidate_volume_weighted_mae_percentage_points"]), 2
                ),
                "Median absolute error": round(
                    cast(float, primary["median_absolute_error_percentage_points"]), 2
                ),
                "Mean signed error": round(
                    cast(float, primary["mean_signed_error_percentage_points"]), 2
                ),
            }
        )
    st.dataframe(metric_records, hide_index=True)
    st.caption(
        "Rows follow the prespecified model order. No post-result tuning, feature selection, or "
        "winner designation is performed."
    )

    st.subheader("Paired feature-group contrasts")
    contrast_records = [
        {
            "Challenger": MODEL_LABELS[cast(str, row["challenger"])],
            "Comparator": MODEL_LABELS[cast(str, row["comparator"])],
            "MAE difference": round(cast(float, row["point_estimate"]), 2),
            "Program-clustered 95% interval": (
                f"{cast(float, row['lower']):.2f} to {cast(float, row['upper']):.2f}"
            ),
        }
        for row in cast(list[dict[str, object]], product.evaluation["contrasts"])
    ]
    st.dataframe(contrast_records, hide_index=True)
    st.caption(
        "Difference is challenger minus comparator in percentage-point MAE; negative favors the "
        "challenger within this sole retrospective fold."
    )

with safety_tab:
    st.subheader("Separately timed published safety context")
    st.warning(
        "Safety ratios are not the patient-journey target and are not evidence of causation, "
        "clinical quality, regulatory status, or an intervention effect. Lower ratios indicate "
        "lower published event rates relative to expected within each measure's own definition."
    )
    if safety_rows:
        safety_records = [
            {
                "Release": row["release_code"],
                "Published": publication_value_text(
                    row["published_value"], row["published_precision"]
                ),
                "Measure": SAFETY_LABELS[cast(str, row["family"])],
                "Included measurement segments": measurement_segments_text(
                    row["included_segments_json"]
                ),
                "Measurement period": (
                    f"{published_date_text(row['measurement_start'])} to "
                    f"{published_date_text(row['measurement_end'])}"
                ),
                "Published ratio": reported_value(row["ratio"], digits=2),
                "95% Bayesian credible interval": (
                    f"{reported_value(row['lower'], digits=2)} to "
                    f"{reported_value(row['upper'], digits=2)}"
                    if row["lower"] is not None and row["upper"] is not None
                    else "Not reported"
                ),
                "Denominator": str(row["denominator_name"]).replace("_", " "),
                "Denominator value": reported_value(row["denominator_value"], digits=1),
                "Observed events": reported_value(row["observed_events"], digits=0),
            }
            for row in safety_rows
        ]
        st.dataframe(safety_records, hide_index=True)
    else:
        st.info("No published safety context is available for this program in the pinned releases.")

with methods_tab:
    st.subheader("Interpretation boundary")
    for limitation in cast(list[str], product.evaluation["limitations"]):
        st.markdown(f"- {limitation}")
    st.subheader("Artifact provenance")
    st.table(
        [
            {
                "Field": "Bundle content SHA-256",
                "Value": product.release.bundle_content_sha256,
            },
            {
                "Field": "Processed artifact SHA-256",
                "Value": str(manifest_provenance["processed_artifact_set_sha256"]),
            },
            {
                "Field": "Modeling artifact SHA-256",
                "Value": str(manifest_provenance["modeling_artifact_set_sha256"]),
            },
            {
                "Field": "Git commit",
                "Value": str(manifest_provenance["git_commit_sha"]),
            },
            {
                "Field": "Worktree dirty at build",
                "Value": str(manifest_provenance["git_worktree_dirty"]),
            },
            {
                "Field": "Build time (UTC)",
                "Value": str(manifest_provenance["build_timestamp_utc"]),
            },
        ],
        border="horizontal",
        width="content",
    )
    with st.expander("Source checksums"):
        st.json(manifest_provenance.get("source_sha256", {}), expanded=False)
    with st.expander("Exact model freeze"):
        st.json(product.evaluation["ridge_parameters"], expanded=False)
    with st.expander("Release display contract"):
        st.json(product.manifest["display_contract"], expanded=False)
