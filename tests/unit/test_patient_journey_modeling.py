from pathlib import Path

import pytest

from kasm.patient_journey.config import load_patient_journey_config
from kasm.patient_journey.modeling import (
    PatientJourneyModelError,
    build_feature_matrix,
    generate_baseline_predictions,
    generate_ridge_predictions,
)

PROJECT_ROOT = Path(__file__).parents[2]


def _row(
    program_key: str,
    feature_release: str,
    target_release: str,
    *,
    prior: float,
    target: float,
    target_n: int = 40,
) -> dict[str, object]:
    return {
        "program_key": program_key,
        "center_code": program_key.split(":")[0],
        "center_type": program_key.split(":")[1],
        "feature_release_code": feature_release,
        "target_release_code": target_release,
        "primary_analytic_eligible": True,
        "prior_target_logit": prior,
        "prior_target_proportion": 1 / (1 + __import__("math").exp(-prior)),
        "prior_target_n": 30,
        "historical_mean_target_proportion": 0.45,
        "historical_target_count": 2,
        "available_cohort_target_proportion": 0.40,
        "transplant_rate_ratio": 1.1,
        "transplant_rate_person_years": 100.0,
        "wait_time_months_25th_percentile": 8.0,
        "acceptance_overall_expected_acceptances": 20.0,
        "acceptance_overall_oar": 1.05,
        "acceptance_overall_oar_lower": 0.8,
        "acceptance_overall_oar_upper": 1.3,
        "acceptance_low_oar": 1.0,
        "acceptance_medium_oar": 1.1,
        "acceptance_high_oar": None,
        "acceptance_hard_to_place_oar": 0.9,
        "waiting_list_mortality_ratio": 0.95,
        "waiting_list_mortality_lower": 0.7,
        "waiting_list_mortality_upper": 1.2,
        "missing_transplant_rate_ratio": False,
        "missing_transplant_rate_person_years": False,
        "missing_wait_time": False,
        "missing_acceptance_expected_acceptances": False,
        "missing_acceptance_overall_oar": False,
        "missing_acceptance_interval": False,
        "missing_acceptance_low_oar": False,
        "missing_acceptance_medium_oar": False,
        "missing_acceptance_high_oar": True,
        "missing_acceptance_hard_to_place_oar": False,
        "missing_waiting_list_mortality_ratio": False,
        "missing_waiting_list_mortality_interval": False,
        "target_logit": target,
        "target_proportion": 1 / (1 + __import__("math").exp(-target)),
        "target_published_percent": 100 / (1 + __import__("math").exp(-target)),
        "target_n": target_n,
        "first_observed_program": False,
    }


def _config():
    return load_patient_journey_config(
        PROJECT_ROOT / "configs" / "patient_journey_v2" / "experiment.yaml",
        repository_root=PROJECT_ROOT,
    )


def test_v2_model_matrix_rejects_identity_location_and_future_fields() -> None:
    rows = [_row("AAAA:TX1", "1905", "2205", prior=-0.2, target=-0.1)]

    for prohibited in ("center_code", "center_name", "target_proportion"):
        with pytest.raises(PatientJourneyModelError, match="frozen feature allowlist"):
            build_feature_matrix(rows, (prohibited,))


def test_v2_log_transform_rejects_nonpositive_reported_ratio() -> None:
    row = _row("AAAA:TX1", "1905", "2205", prior=-0.2, target=-0.1)
    row["acceptance_overall_oar"] = 0.0

    with pytest.raises(PatientJourneyModelError, match="positive"):
        build_feature_matrix([row], ("log_acceptance_overall_oar",))


def test_v2_baselines_use_only_values_available_at_prediction_origin() -> None:
    row = _row("AAAA:TX1", "1905", "2205", prior=-0.2, target=0.2)

    predictions = generate_baseline_predictions([row], _config())

    by_model = {prediction.model: prediction for prediction in predictions}
    assert by_model["persistence"].predicted_proportion == pytest.approx(
        row["prior_target_proportion"]
    )
    assert by_model["available_cohort_reference"].predicted_proportion == 0.40
    assert by_model["historical_mean"].predicted_proportion == 0.45
    assert all(
        prediction.target_published_percent == row["target_published_percent"]
        for prediction in predictions
    )


def test_v2_ridge_uses_only_frozen_strict_vintage_fold_and_bounds_predictions() -> None:
    rows = [
        _row("AAAA:TX1", "1905", "2205", prior=-0.8, target=-0.5),
        _row("BBBB:TX1", "1905", "2205", prior=-0.2, target=-0.1),
        _row("CCCC:TX1", "1905", "2205", prior=0.4, target=0.3),
        _row("AAAA:TX1", "2205", "2505", prior=-0.5, target=-0.3),
        _row("BBBB:TX1", "2205", "2505", prior=-0.1, target=0.0),
        _row("CCCC:TX1", "2205", "2505", prior=0.3, target=0.5),
        _row("DDDD:TX1", "2105", "2405", prior=0.1, target=0.2),
    ]

    predictions = generate_ridge_predictions(rows, _config())

    assert len(predictions) == 3 * 5
    assert {prediction.feature_release_code for prediction in predictions} == {"2205"}
    assert {prediction.target_release_code for prediction in predictions} == {"2505"}
    assert {prediction.training_pairs for prediction in predictions} == {(("1905", "2205"),)}
    assert all(0.0 <= prediction.predicted_proportion <= 1.0 for prediction in predictions)
    programs_by_group = {
        group: {prediction.program_key for prediction in predictions if prediction.model == group}
        for group in {prediction.model for prediction in predictions}
    }
    assert len(set(map(frozenset, programs_by_group.values()))) == 1


def test_v2_ridge_refuses_fold_without_published_training_truth() -> None:
    config = _config()
    rows = [_row("AAAA:TX1", "2205", "2505", prior=-0.2, target=-0.1)]

    with pytest.raises(PatientJourneyModelError, match="training pair"):
        generate_ridge_predictions(rows, config)
