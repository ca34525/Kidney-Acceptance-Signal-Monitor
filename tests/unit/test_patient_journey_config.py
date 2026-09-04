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
schema_version: 1
analysis_id: kidney_patient_journey_v2
target:
  column: SAL_TOTFTX_C18
  canonical_scale: proportion
  officially_risk_adjusted: {risk_adjusted_yaml}
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
