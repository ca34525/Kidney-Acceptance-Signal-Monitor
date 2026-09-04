from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from kasm.patient_journey.config import load_patient_journey_config
from kasm.patient_journey.model_artifacts import (
    PatientJourneyModelArtifactError,
    evaluate_patient_journey_rows,
    validate_model_evaluation_directory,
    write_model_evaluation_directory,
)

PROJECT_ROOT = Path(__file__).parents[2]


def _row(
    program: str,
    feature: str,
    target_release: str,
    *,
    prior: float,
    target: float,
    target_n: int,
) -> dict[str, object]:
    def logistic(value: float) -> float:
        return 1 / (1 + math.exp(-value))

    return {
        "program_key": program,
        "feature_release_code": feature,
        "target_release_code": target_release,
        "primary_analytic_eligible": True,
        "prior_target_logit": prior,
        "prior_target_proportion": logistic(prior),
        "prior_target_n": 35,
        "historical_mean_target_proportion": 0.45,
        "historical_target_count": 2,
        "available_cohort_target_proportion": 0.42,
        "transplant_rate_ratio": 1.05,
        "transplant_rate_person_years": 120.0,
        "wait_time_months_25th_percentile": 8.0,
        "acceptance_overall_expected_acceptances": 22.0,
        "acceptance_overall_oar": 1.02,
        "acceptance_overall_oar_lower": 0.8,
        "acceptance_overall_oar_upper": 1.3,
        "acceptance_low_oar": 1.0,
        "acceptance_medium_oar": 1.1,
        "acceptance_high_oar": 0.9,
        "acceptance_hard_to_place_oar": 0.85,
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
        "missing_acceptance_high_oar": False,
        "missing_acceptance_hard_to_place_oar": False,
        "missing_waiting_list_mortality_ratio": False,
        "missing_waiting_list_mortality_interval": False,
        "target_logit": target,
        "target_proportion": logistic(target),
        "target_published_percent": logistic(target) * 100,
        "target_n": target_n,
        "first_observed_program": False,
    }


def _rows() -> tuple[dict[str, object], ...]:
    pairs = (
        ("1905", "2205", -0.7, -0.5),
        ("2006", "2305", -0.5, -0.3),
        ("2105", "2405", -0.3, -0.1),
        ("2205", "2505", -0.1, 0.1),
    )
    return tuple(
        _row(
            f"{program}:TX1",
            feature,
            target_release,
            prior=prior + offset,
            target=target + offset,
            target_n=20 + index * 10,
        )
        for feature, target_release, prior, target in pairs
        for index, (program, offset) in enumerate((("AAAA", 0.0), ("BBBB", 0.2)))
    )


def test_v2_evaluation_is_complete_but_permanently_nonpromotional() -> None:
    config = load_patient_journey_config(
        PROJECT_ROOT / "configs" / "patient_journey_v2" / "experiment.yaml",
        repository_root=PROJECT_ROOT,
    )

    result = evaluate_patient_journey_rows(_rows(), config)

    assert result.evidence["promotion_allowed"] is False
    assert result.evidence["promoted_model"] is None
    assert result.evidence["ridge_training_pairs"] == [["1905", "2205"]]
    assert result.evidence["ridge_evaluation_pair"] == ["2205", "2505"]
    assert set(result.evidence["models"]) == {
        "persistence",
        "available_cohort_reference",
        "historical_mean",
        "history",
        "history_acceptance",
        "history_access",
        "history_access_acceptance",
        "history_access_acceptance_safety",
    }
    assert len(result.evidence["contrasts"]) == 5
    baseline_targets = {
        prediction.target_release_code
        for prediction in result.predictions
        if prediction.model == "persistence"
    }
    ridge_targets = {
        prediction.target_release_code
        for prediction in result.predictions
        if prediction.model == "history_access_acceptance_safety"
    }
    assert baseline_targets == {"2205", "2305", "2405", "2505"}
    assert ridge_targets == {"2505"}


def test_v2_model_writer_is_atomic_and_tamper_evident(tmp_path: Path) -> None:
    config = load_patient_journey_config(
        PROJECT_ROOT / "configs" / "patient_journey_v2" / "experiment.yaml",
        repository_root=PROJECT_ROOT,
    )
    evaluation = evaluate_patient_journey_rows(_rows(), config)
    provenance = {
        "analysis_id": config.analysis_id,
        "processed_artifact_set_sha256": "a" * 64,
        "experiment_config_sha256": "b" * 64,
        "methodology_config_sha256": "c" * 64,
        "dependency_lock_sha256": "d" * 64,
        "git_commit_sha": "e" * 40,
        "git_worktree_dirty": False,
        "build_timestamp_utc": "2026-09-04T18:00:00Z",
    }
    output_dir = tmp_path / "modeling"

    result = write_model_evaluation_directory(
        evaluation,
        output_dir=output_dir,
        provenance=provenance,
    )

    assert {path.name for path in output_dir.iterdir()} == {
        "build_manifest.json",
        "evaluation.json",
        "predictions.parquet",
    }
    assert result.prediction_rows == len(evaluation.predictions)
    validated = validate_model_evaluation_directory(
        output_dir,
        expected=evaluation,
        expected_provenance=provenance,
    )
    assert validated.artifact_set_sha256 == result.artifact_set_sha256

    payload = json.loads(result.evaluation_path.read_text(encoding="utf-8"))
    payload["promotion_allowed"] = True
    result.evaluation_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PatientJourneyModelArtifactError, match="checksum"):
        validate_model_evaluation_directory(
            output_dir,
            expected=evaluation,
            expected_provenance=provenance,
        )
