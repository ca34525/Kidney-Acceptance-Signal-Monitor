"""Fixed sprint choices cannot silently change the initial comparison."""

import json
from pathlib import Path

import pytest

from kasm.program_prediction.config import SprintConfig, SprintError, load_config


def test_checked_in_initial_settings_match_contract() -> None:
    config = load_config(Path("configs/program_prediction/experiment.json"))
    assert config.targets == (
        "registrations",
        "ddkt_removals",
        "ldkt_removals",
        "ending_list",
        "overall_oar",
    )
    assert len(config.pipelines) == 4
    assert config.discovery_years == (2021, 2022, 2023)
    assert config.later_years == (2024, 2025)
    assert config.seed == 20260909
    assert config.bootstrap_resamples == 2000


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("seed", True),
        ("discovery_years", [2022, 2023]),
        ("omit_oar_features", True),
        ("unknown", 1),
    ],
)
def test_initial_settings_cannot_drift(tmp_path: Path, field: str, value: object) -> None:
    raw = SprintConfig().raw | {field: value}
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SprintError):
        load_config(path)


def test_followup_requires_question_and_preserved_parent(tmp_path: Path) -> None:
    raw = SprintConfig().raw | {"round_id": "followup_1", "omit_oar_features": True}
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SprintError, match="question|parent"):
        load_config(path)
    raw.update(question="Does excluding OAR change the count findings?", parent_run="initial-run")
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert load_config(path).omit_oar_features


def test_unknown_and_malformed_settings_fail(tmp_path: Path) -> None:
    with pytest.raises(SprintError):
        load_config(tmp_path / "missing.json")
    path = tmp_path / "settings.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(SprintError):
        load_config(path)


def test_duplicate_json_settings_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    encoded = json.dumps(SprintConfig().raw)
    path.write_text(encoded[:-1] + ', "seed": 20260909}', encoding="utf-8")
    with pytest.raises(SprintError, match="Duplicate"):
        load_config(path)


def test_followup_can_focus_existing_targets_only(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    raw = SprintConfig().raw | {
        "round_id": "followup_1",
        "parent_run": "initial",
        "question": "Does activity retain its gains without OAR?",
        "targets": ["ddkt_removals"],
        "omit_oar_features": True,
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert load_config(path).targets == ("ddkt_removals",)
    for targets in ([], ["new_target"], ["ddkt_removals", "ddkt_removals"]):
        path.write_text(json.dumps(raw | {"targets": targets}), encoding="utf-8")
        with pytest.raises(SprintError, match="target"):
            load_config(path)
