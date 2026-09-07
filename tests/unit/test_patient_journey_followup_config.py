from pathlib import Path

import pytest
import yaml

from kasm.patient_journey.config import FEATURE_GROUPS, load_patient_journey_config
from kasm.patient_journey.followup_config import (
    OUTPUT_ROOT,
    FollowupConfigError,
    load_followup_config,
    validate_followup_destination,
)

ROOT = Path(__file__).parents[2]
CONFIG = ROOT / "configs/patient_journey_v2_followup/experiment.yaml"


def test_followup_removes_only_count_and_preserves_original_contract() -> None:
    followup = load_followup_config(CONFIG)
    original = load_patient_journey_config(
        ROOT / "configs/patient_journey_v2/experiment.yaml", repository_root=ROOT
    )
    assert followup.feature_groups == tuple(
        (name, tuple(f for f in features if f != "historical_target_count"))
        for name, features in FEATURE_GROUPS
    )
    assert all(
        "historical_target_count" in g.features for g in original.model_design.feature_groups
    )
    assert len(followup.contrasts) == 12


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("promotion_allowed", True),
        ("promotion_allowed", 0),
        ("future_forecast_available", True),
        ("prediction_absolute_tolerance", 1.0),
        ("prediction_relative_tolerance", 1e-5),
        ("analysis_id", "kidney_patient_journey_v2"),
        ("original_bundle_sha256", "0" * 64),
        ("training_pairs", [["2105", "2405"]]),
        ("output_root", "artifacts/patient_journey_v2"),
        ("extra", "unexpected"),
    ],
)
def test_followup_rejects_changed_fixed_contract(tmp_path: Path, key: str, value: object) -> None:
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    raw[key] = value
    path = tmp_path / "experiment.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(FollowupConfigError, match="fixed follow-up contract"):
        load_followup_config(path)


@pytest.mark.parametrize("feature", ["historical_target_count", "center_code", "target_n"])
def test_followup_rejects_count_identity_and_future_features(tmp_path: Path, feature: str) -> None:
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    raw["feature_groups"][0]["features"].append(feature)
    path = tmp_path / "experiment.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(FollowupConfigError, match="fixed follow-up contract"):
        load_followup_config(path)


@pytest.mark.parametrize("contents", ["[", "[]", "null", "schema_version: 2026-09-05", "\xff"])
def test_followup_unreadable_or_malformed_config(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "experiment.yaml"
    path.write_bytes(contents.encode("latin1"))
    with pytest.raises(FollowupConfigError):
        load_followup_config(path)


@pytest.mark.parametrize(
    "path",
    [
        ".",
        "data",
        "data/processed/x",
        "data/modeling/x",
        "artifacts/release/x",
        "data/patient_journey_v2/processed",
        "artifacts/patient_journey_v2",
        "../outside",
        "data/patient_journey_v2_followup/report_count_v1/../escape",
        "data/patient_journey_v2_followup/report_count_v1/not-a-run",
    ],
)
def test_followup_path_rejected_before_mutation(tmp_path: Path, path: str) -> None:
    with pytest.raises(FollowupConfigError):
        validate_followup_destination(Path(path), repository_root=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_followup_destination_is_fixed_relative_hash_address(tmp_path: Path) -> None:
    relative = OUTPUT_ROOT / ("a" * 64)
    assert validate_followup_destination(relative, repository_root=tmp_path) == tmp_path / relative
    with pytest.raises(FollowupConfigError):
        validate_followup_destination(tmp_path / relative, repository_root=tmp_path)


def test_followup_rejects_symlinked_output_ancestor(tmp_path: Path, monkeypatch) -> None:
    ancestor = tmp_path / "data"
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda p: p == ancestor or original(p))
    with pytest.raises(FollowupConfigError, match="link"):
        validate_followup_destination(OUTPUT_ROOT / ("a" * 64), repository_root=tmp_path)
    assert list(tmp_path.iterdir()) == []
