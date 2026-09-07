from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

import kasm.patient_journey.followup_analysis as followup_analysis
from kasm.patient_journey.config import FEATURE_GROUPS, load_patient_journey_config
from kasm.patient_journey.followup_analysis import FollowupAnalysisError, evaluate_followup
from kasm.patient_journey.followup_config import FollowupConfig
from kasm.patient_journey.model_artifacts import patient_journey_prediction_table
from kasm.patient_journey.modeling import (
    generate_baseline_predictions,
    generate_ridge_predictions,
)

ROOT = Path(__file__).parents[2]


def _row(program: str, pair: tuple[str, str], count: int, target: float) -> dict[str, object]:
    row: dict[str, object] = {
        "program_key": program,
        "feature_release_code": pair[0],
        "target_release_code": pair[1],
        "primary_analytic_eligible": True,
        "prior_target_logit": 0.0,
        "prior_target_proportion": 0.5,
        "prior_target_n": 30,
        "historical_mean_target_proportion": 0.5,
        "historical_target_count": count,
        "available_cohort_target_proportion": 0.4,
        "transplant_rate_ratio": 1.0,
        "transplant_rate_person_years": 100.0,
        "wait_time_months_25th_percentile": 8.0,
        "acceptance_overall_expected_acceptances": 20.0,
        "acceptance_overall_oar": 1.0,
        "acceptance_overall_oar_lower": 0.8,
        "acceptance_overall_oar_upper": 1.3,
        "acceptance_low_oar": 1.0,
        "acceptance_medium_oar": 1.0,
        "acceptance_high_oar": None,
        "acceptance_hard_to_place_oar": 1.0,
        "waiting_list_mortality_ratio": 1.0,
        "waiting_list_mortality_lower": 0.7,
        "waiting_list_mortality_upper": 1.2,
        "target_logit": target,
        "target_proportion": 1 / (1 + math.exp(-target)),
        "target_published_percent": 100 / (1 + math.exp(-target)),
        "target_n": 40,
        "first_observed_program": False,
    }
    for _, features in FEATURE_GROUPS:
        row.update({feature: False for feature in features if feature.startswith("missing_")})
    row["missing_acceptance_high_oar"] = True
    return row


@pytest.fixture
def original():
    return load_patient_journey_config(
        ROOT / "configs/patient_journey_v2/experiment.yaml", repository_root=ROOT
    )


@pytest.fixture
def config(original):
    groups = tuple(
        (name, tuple(feature for feature in features if feature != "historical_target_count"))
        for name, features in FEATURE_GROUPS
    )
    contrasts = (
        ("original_history_acceptance", "historical_mean"),
        *((f"revised_{name}", f"original_{name}") for name, _ in groups),
        *(
            (f"revised_{left}", f"revised_{right}")
            for left, right in original.model_design.contrasts
        ),
        ("revised_history_acceptance", "historical_mean"),
    )
    return FollowupConfig(
        analysis_id="kidney_patient_journey_v2_followup_report_count_v1",
        original_bundle_sha256="ce2844edbcec92c09d0053720d5331dd37ed43ab75de7aa4dd1de431c79a9eee",
        original_experiment_sha256="ab8c01453c36039b293a8e7453b17b2b326faf734a081a4b67f8bfe132b1de79",
        output_root=Path("data/patient_journey_v2_followup/report_count_v1"),
        prediction_absolute_tolerance=1e-10,
        contribution_absolute_tolerance=1e-10,
        feature_groups=groups,
        contrasts=contrasts,
    )


@pytest.fixture
def rows():
    return tuple(
        _row(program, pair, count, target)
        for pair in (("1905", "2205"), ("2205", "2505"))
        for program, count, target in (
            ("AAAA:TX1", 1 if pair[0] == "1905" else 5, -1.0),
            ("BBBB:TX1", 2 if pair[0] == "1905" else 5, 0.0),
            ("CCCC:TX1", 3 if pair[0] == "1905" else 5, 1.0),
        )
    )


def _stored(rows, original):
    predictions = (
        *generate_baseline_predictions(rows, original),
        *generate_ridge_predictions(rows, original),
    )
    return patient_journey_prediction_table(predictions).to_pylist()


def test_followup_quantifies_count_shift_and_all_fixed_comparisons(rows, original, config):
    result = evaluate_followup(rows, _stored(rows, original), original, config)

    assert len(result.predictions) == 13 * 3
    assert len(result.evidence["contrasts"]) == 12
    assert result.evidence["promotion_allowed"] is False
    assert result.evidence["future_forecast_available"] is False
    counts = result.evidence["report_count"]
    assert counts["training"]["frequencies"] == {"1": 1, "2": 1, "3": 1}
    assert counts["evaluation"]["frequencies"] == {"5": 3}
    assert counts["mean_shift_training_standard_deviations"] == pytest.approx(3 / math.sqrt(2 / 3))
    model = result.evidence["models"]["original_history"]
    assert model["contributions"]["by_feature"]["historical_target_count"] == pytest.approx(2.25)
    assert model["contributions"]["sum"] == pytest.approx(2.25)
    assert model["contributions"]["mean_predicted_logit_change"] == pytest.approx(2.25)
    assert result.evidence["reconstruction"]["prediction_rows"] == 8 * 3
    assert result.evidence["reconstruction"]["max_absolute_difference"] == 0.0
    for name, payload in result.evidence["models"].items():
        assert payload["summary"]["n"] == 3
        if name.startswith("revised_"):
            assert "historical_target_count" not in payload["features"]


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("predicted_proportion", 0.99, "prediction"),
        ("predicted_proportion", float("nan"), "finite"),
        ("predicted_proportion", float("inf"), "finite"),
        ("predicted_proportion", None, "numeric"),
        ("target_n", 99, "target"),
        ("target_published_percent", 99.0, "target"),
        ("model", "unrecognized_model", "keys"),
        ("program_key", "ZZZZ:TX1", "keys"),
        ("program_key", None, "text"),
        ("feature_release_code", "2105", "keys"),
        ("target_release_code", "2405", "keys"),
    ],
)
def test_followup_rejects_changed_stored_evidence(rows, original, config, field, value, match):
    stored = _stored(rows, original)
    selected = next(row for row in stored if row["model"] == "history")
    selected[field] = value
    with pytest.raises(FollowupAnalysisError, match=match):
        evaluate_followup(rows, stored, original, config)


@pytest.mark.parametrize("change", ["duplicate", "missing"])
def test_followup_requires_complete_unique_stored_keys(rows, original, config, change):
    stored = _stored(rows, original)
    selected = next(row for row in stored if row["model"] == "history")
    if change == "duplicate":
        stored.append(selected.copy())
    else:
        stored.remove(selected)
    with pytest.raises(FollowupAnalysisError, match="keys"):
        evaluate_followup(rows, stored, original, config)


def test_followup_is_order_independent_and_preserves_excluded_rows(rows, original, config):
    excluded = _row("DDDD:TX1", ("2205", "2505"), 5, 0.0)
    excluded["primary_analytic_eligible"] = False
    other = _row("EEEE:TX1", ("2006", "2305"), 3, 0.0)
    all_rows = (*rows, excluded, other)
    stored = _stored(all_rows, original)
    first = evaluate_followup(all_rows, stored, original, config)
    second = evaluate_followup(all_rows[::-1], stored[::-1], original, config)
    assert first == second
    exclusions = first.evidence["populations"]["excluded"]
    assert {row["program_key"] for row in exclusions} == {"DDDD:TX1", "EEEE:TX1"}


def test_revised_predictions_ignore_count_and_preprocessing_uses_training_only(
    rows, original, config
):
    first = evaluate_followup(rows, _stored(rows, original), original, config)
    changed = tuple(row.copy() for row in rows)
    for row in changed:
        if row["feature_release_code"] == "2205":
            row["historical_target_count"] = 99
            row["target_logit"] = 999.0
    second = evaluate_followup(changed, _stored(changed, original), original, config)
    assert tuple(p for p in first.predictions if p.model.startswith("revised_")) == tuple(
        p for p in second.predictions if p.model.startswith("revised_")
    )
    assert (
        first.evidence["models"]["original_history"]["parameters"]
        == (second.evidence["models"]["original_history"]["parameters"])
    )


def test_training_medians_and_empty_columns_retain_missing_evaluation_rows(rows, original, config):
    changed = tuple(row.copy() for row in rows)
    for index, row in enumerate(changed[:3]):
        row["acceptance_overall_expected_acceptances"] = (None, 10.0, 30.0)[index]
        row["missing_acceptance_expected_acceptances"] = index == 0
    for row in changed[3:]:
        row["acceptance_overall_expected_acceptances"] = None
        row["missing_acceptance_expected_acceptances"] = True
    result = evaluate_followup(changed, _stored(changed, original), original, config)
    model = result.evidence["models"]["revised_history_acceptance"]
    field = "log1p_acceptance_overall_expected_acceptances"
    assert model["parameters"]["imputation_values"][field] == pytest.approx(
        (math.log1p(10.0) + math.log1p(30.0)) / 2
    )
    assert model["parameters"]["imputation_values"]["log_acceptance_high_oar"] == 0.0
    assert model["missingness"]["evaluation_counts"][field] == 3
    assert model["summary"]["n"] == 3


def test_zero_training_count_variance_is_explicitly_unavailable(rows, original, config):
    changed = tuple(row.copy() for row in rows)
    for row in changed[:3]:
        row["historical_target_count"] = 2
    result = evaluate_followup(changed, _stored(changed, original), original, config)
    count = result.evidence["report_count"]
    assert count["mean_shift_training_standard_deviations"] is None
    assert count["unavailable_reason"] == "training_report_count_has_zero_variance"


def test_followup_refuses_reintroduced_count_before_fitting(rows, original, config):
    groups = (("history", (*config.feature_groups[0][1], "historical_target_count")),)
    invalid = replace(config, feature_groups=groups)
    with pytest.raises(FollowupAnalysisError, match="feature groups"):
        evaluate_followup(rows, _stored(rows, original), original, invalid)


def test_followup_rejects_duplicate_panel_keys(rows, original, config):
    with pytest.raises(FollowupAnalysisError, match="duplicate"):
        evaluate_followup((*rows, rows[0]), _stored(rows, original), original, config)


@pytest.mark.parametrize("field", ["alpha", "training_pairs", "promotion_allowed"])
def test_followup_rejects_changed_original_fit_contract(rows, original, config, field):
    changes = {"alpha": 2.0, "training_pairs": (("2006", "2305"),), "promotion_allowed": True}
    changed_ridge = replace(original.model_design.ridge, **{field: changes[field]})
    changed = replace(original, model_design=replace(original.model_design, ridge=changed_ridge))
    with pytest.raises(FollowupAnalysisError, match="Original V2 settings"):
        evaluate_followup(rows, _stored(rows, original), changed, config)


@pytest.mark.parametrize("field", ["historical_target_count", "primary_analytic_eligible"])
def test_followup_rejects_malformed_panel_fields(rows, original, config, field):
    stored = _stored(rows, original)
    changed = tuple(row.copy() for row in rows)
    changed[0][field] = True if field == "historical_target_count" else 1
    with pytest.raises(FollowupAnalysisError, match="numeric|boolean"):
        evaluate_followup(changed, stored, original, config)


def test_followup_requires_both_prespecified_populations(rows, original, config):
    with pytest.raises(FollowupAnalysisError, match="Both fixed"):
        evaluate_followup(rows[3:], _stored(rows, original), original, config)


def test_followup_records_original_eligibility_for_included_populations(rows, original, config):
    result = evaluate_followup(rows, _stored(rows, original), original, config)
    for population in ("training", "evaluation"):
        included = result.evidence["populations"][population]
        assert len(included) == 3
        assert all(record["primary_analytic_eligible"] is True for record in included)


def test_followup_rejects_unpaired_revised_comparison(rows, original, config, monkeypatch):
    real_fit = followup_analysis._fit_groups

    def missing_program(*args, **kwargs):
        predictions, evidence = real_fit(*args, **kwargs)
        if args[3] == "revised":
            predictions = predictions[1:]
        return predictions, evidence

    monkeypatch.setattr(followup_analysis, "_fit_groups", missing_program)
    with pytest.raises(FollowupAnalysisError, match="identical program/release rows"):
        evaluate_followup(rows, _stored(rows, original), original, config)


def test_followup_stops_before_revision_when_reconstruction_fails(
    rows, original, config, monkeypatch
):
    def should_not_fit(*args, **kwargs):
        pytest.fail("Diagnostics and revised models must follow successful reconstruction.")

    stored = _stored(rows, original)
    next(row for row in stored if row["model"] == "history")["predicted_proportion"] = 0.99
    monkeypatch.setattr(followup_analysis, "_fit_groups", should_not_fit)
    with pytest.raises(FollowupAnalysisError, match="prediction exceeds tolerance"):
        evaluate_followup(rows, stored, original, config)
