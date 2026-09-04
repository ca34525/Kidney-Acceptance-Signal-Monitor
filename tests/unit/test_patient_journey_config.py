from pathlib import Path

import pytest

from kasm.patient_journey.config import (
    PatientJourneyConfigError,
    load_patient_journey_config,
)

PROJECT_ROOT = Path(__file__).parents[2]


def _config_text(
    *,
    processed_dir: str = "data/patient_journey_v2/processed",
    modeling_dir: str = "data/patient_journey_v2/modeling",
    release_dir: str = "artifacts/patient_journey_v2",
    risk_adjusted: bool = False,
) -> str:
    risk_adjusted_yaml = str(risk_adjusted).lower()
    return f"""
schema_version: 2
analysis_id: kidney_patient_journey_v2
target:
  column: SAL_TOTFTX_C18
  canonical_scale: proportion
  officially_risk_adjusted: {risk_adjusted_yaml}
temporal_design:
  evaluation_mode: strict_vintage
  max_prediction_origin_month_offset: 1
  primary_pairs:
    - feature_release_code: "1905"
      target_release_code: "2205"
    - feature_release_code: "2006"
      target_release_code: "2305"
    - feature_release_code: "2105"
      target_release_code: "2405"
    - feature_release_code: "2205"
      target_release_code: "2505"
  excluded_candidates:
    - feature_release_code: "1808"
      target_release_code: "2105"
      reason: prediction_origin_more_than_one_month_after_target_start
    - feature_release_code: "2305"
      target_release_code: "2605"
      reason: overlapping_target_cohort
eligibility:
  primary_min_target_n: 10
  sensitivity_min_target_n: [20, 30]
paths:
  processed_dir: {processed_dir}
  modeling_dir: {modeling_dir}
  release_dir: {release_dir}
protected_v1_roots:
  - data/processed
  - data/modeling
  - artifacts/release
""".strip()


def test_patient_journey_config_rejects_v1_release_output(tmp_path: Path) -> None:
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(_config_text(release_dir="artifacts/release"), encoding="utf-8")

    with pytest.raises(PatientJourneyConfigError, match="protected v1 root"):
        load_patient_journey_config(config_path, repository_root=PROJECT_ROOT)


def test_project_patient_journey_config_uses_isolated_roots() -> None:
    config = load_patient_journey_config(
        PROJECT_ROOT / "configs" / "patient_journey_v2" / "experiment.yaml",
        repository_root=PROJECT_ROOT,
    )

    assert config.analysis_id == "kidney_patient_journey_v2"
    assert config.target_column == "SAL_TOTFTX_C18"
    assert config.paths.processed_dir == PROJECT_ROOT / "data/patient_journey_v2/processed"
    assert config.paths.modeling_dir == PROJECT_ROOT / "data/patient_journey_v2/modeling"
    assert config.paths.release_dir == PROJECT_ROOT / "artifacts/patient_journey_v2"


def test_project_config_fixes_nonoverlapping_primary_pairs_and_exclusions() -> None:
    config = load_patient_journey_config(
        PROJECT_ROOT / "configs" / "patient_journey_v2" / "experiment.yaml",
        repository_root=PROJECT_ROOT,
    )

    assert tuple(
        (pair.feature_release_code, pair.target_release_code)
        for pair in config.temporal_design.primary_pairs
    ) == (
        ("1905", "2205"),
        ("2006", "2305"),
        ("2105", "2405"),
        ("2205", "2505"),
    )
    assert tuple(
        (pair.feature_release_code, pair.target_release_code, pair.reason)
        for pair in config.temporal_design.excluded_candidates
    ) == (
        ("1808", "2105", "prediction_origin_more_than_one_month_after_target_start"),
        ("2305", "2605", "overlapping_target_cohort"),
    )
    assert config.temporal_design.evaluation_mode == "strict_vintage"
    assert config.temporal_design.max_prediction_origin_month_offset == 1
    assert config.eligibility.primary_min_target_n == 10
    assert config.eligibility.sensitivity_min_target_n == (20, 30)


def test_v2_model_config_freezes_baselines_features_metrics_bootstrap_and_nonpromotion() -> None:
    config = load_patient_journey_config(
        PROJECT_ROOT / "configs" / "patient_journey_v2" / "experiment.yaml",
        repository_root=PROJECT_ROOT,
    )

    design = config.model_design
    assert design.baselines == (
        "persistence",
        "available_cohort_reference",
        "historical_mean",
    )
    assert design.ridge.alpha == 1.0
    assert design.ridge.solver == "lsqr"
    assert design.ridge.tolerance == 1e-8
    assert design.ridge.max_iterations == 10_000
    assert design.ridge.promotion_allowed is False
    assert design.ridge.evaluation_pair == ("2205", "2505")
    assert design.ridge.training_pairs == (("1905", "2205"),)
    assert tuple(group.name for group in design.feature_groups) == (
        "history",
        "history_acceptance",
        "history_access",
        "history_access_acceptance",
        "history_access_acceptance_safety",
    )
    assert design.metrics.error_scale == "percentage_points"
    assert design.metrics.signed_error == "prediction_minus_observed"
    assert design.metrics.primary_aggregation == "unweighted_mean_target_release_mae"
    assert design.metrics.calibration_equation == (
        "observed_percentage_points=intercept+slope*predicted_percentage_points"
    )
    assert design.volume_strata.method == "within_release_sorted_quartiles"
    assert design.volume_strata.tie_breaker == "program_key"
    assert design.bootstrap.resamples == 2_000
    assert design.bootstrap.seed == 20_260_904
    assert design.bootstrap.cluster == "program_key"
    assert design.bootstrap.percentiles == (2.5, 97.5)
    assert design.bootstrap.quantile_method == "linear"
    assert design.bootstrap.contrast == "challenger_minus_comparator_balanced_mae"


@pytest.mark.parametrize(
    "release_dir",
    [
        "artifacts/release/future-v2",
        "artifacts",
    ],
)
def test_patient_journey_config_rejects_v1_ancestor_or_descendant_output(
    tmp_path: Path, release_dir: str
) -> None:
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(_config_text(release_dir=release_dir), encoding="utf-8")

    with pytest.raises(PatientJourneyConfigError, match="protected v1 root"):
        load_patient_journey_config(config_path, repository_root=PROJECT_ROOT)


def test_patient_journey_config_rejects_absolute_output(tmp_path: Path) -> None:
    config_path = tmp_path / "experiment.yaml"
    absolute_output = (PROJECT_ROOT / "data/patient_journey_v2/processed").as_posix()
    config_path.write_text(_config_text(processed_dir=absolute_output), encoding="utf-8")

    with pytest.raises(PatientJourneyConfigError, match="repository-relative"):
        load_patient_journey_config(config_path, repository_root=PROJECT_ROOT)


def test_patient_journey_config_rejects_parent_traversal(tmp_path: Path) -> None:
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(
        _config_text(processed_dir="data/patient_journey_v2/../processed"), encoding="utf-8"
    )

    with pytest.raises(PatientJourneyConfigError, match="parent traversal"):
        load_patient_journey_config(config_path, repository_root=PROJECT_ROOT)


def test_patient_journey_config_requires_separate_v2_output_roots(tmp_path: Path) -> None:
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(
        _config_text(
            processed_dir="data/patient_journey_v2",
            modeling_dir="data/patient_journey_v2/modeling",
        ),
        encoding="utf-8",
    )

    with pytest.raises(PatientJourneyConfigError, match="must be separate roots"):
        load_patient_journey_config(config_path, repository_root=PROJECT_ROOT)


def test_patient_journey_config_rejects_risk_adjusted_target_claim(tmp_path: Path) -> None:
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(_config_text(risk_adjusted=True), encoding="utf-8")

    with pytest.raises(PatientJourneyConfigError, match="not officially risk-adjusted"):
        load_patient_journey_config(config_path, repository_root=PROJECT_ROOT)
