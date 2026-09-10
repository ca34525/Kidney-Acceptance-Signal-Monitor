"""A revised review question reuses saved predictions without rewriting earlier choices."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from kasm.acceptance_forecast.inputs import file_hash
from kasm.acceptance_forecast.runs import json_bytes
from kasm.program_prediction import reassessment
from kasm.program_prediction.config import SprintConfig
from kasm.program_prediction.runs import OUTPUT_ROOT, publish_run


def _settings() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "study_id": "program-prediction-0031",
        "round_id": "followup_2",
        "question": "Can the saved registration Ridge predictions improve growth-review selection?",
        "parent_run": "followup-1-later",
        "target": "registrations",
        "model": "ridge_broader",
        "direction": "growth",
        "budgets": [10, 15, 25],
        "seed": 20260909,
        "bootstrap_resamples": 2000,
        "output_root": "data/research/program-prediction-0031",
    }


def _config(root: Path, **changes: Any) -> Path:
    path = root / "decision.json"
    path.write_bytes(json_bytes(_settings() | changes))
    return path


def _fingerprint(root: Path, run: str) -> dict[str, str]:
    return {
        "run_id": run,
        "completion_sha256": file_hash(root / OUTPUT_ROOT / run / "completion.json"),
    }


def _parent(
    root: Path,
    *,
    parent_id: str = "followup-1-later",
    prior_id: str = "initial-later",
    **changes: Any,
) -> dict[str, Any]:
    settings = replace(
        SprintConfig(),
        round_id="followup_1",
        targets=("registrations",),
        omit_oar_features=True,
        parent_run=prior_id,
        question="Does removing OAR matter?",
    ).raw
    choice = {
        "questions": [
            {
                "target": "registrations",
                "model": "extra_trees_broader",
                "direction": "growth",
                "question": "Original discovery question",
                "rationale": "Saved before later scores",
            }
        ]
    }
    publish_run(
        root,
        "initial-shortlist",
        {
            "shortlist.json": json_bytes(choice),
            "comparators.json": json_bytes({"registrations": "persistence"}),
        },
        {"stage": "shortlist"},
    )
    publish_run(
        root,
        prior_id,
        {
            "settings.json": json_bytes(SprintConfig().raw),
            "shortlist.json": json_bytes(choice),
            "comparators.json": json_bytes({"registrations": "persistence"}),
        },
        {
            "stage": "assess",
            "parents": {
                "shortlist": _fingerprint(root, "initial-shortlist"),
            },
        },
    )
    publish_run(
        root,
        "followup-1-panel",
        {
            "settings.json": json_bytes(settings),
            "feature-map.json": json_bytes({"h_latest": {}, "b1_start": {}}),
            "source-ledger.json": json_bytes({"source": "fixture verified sources"}),
        },
        {"stage": "build"},
    )
    predictions = [
        {
            "target": "registrations",
            "target_year": year,
            "program_key": f"P{i:03}:TX1",
            "model": model,
            "latest": float(10 + i),
            "previous": float(11 + i),
            "observed": None if i == 29 else float(20 + i),
            "prediction": float(20 + i) if model == "ridge_broader" else float(10 + i),
            "eligible": True,
            "status": "ok",
            "earlier_list_size": 100 + i,
        }
        for year in (2024, 2025)
        for model in ("persistence", "recent_mean", "damped_trend", *SprintConfig().pipelines)
        for i in range(30)
    ]
    payload: dict[str, Any] = {
        "settings.json": settings,
        "predictions.json": predictions,
        "shortlist.json": choice,
        "comparators.json": {"registrations": "persistence"},
        "metrics.json": {"retained_original_metrics": True},
        "error-differences.json": [{"candidate": "ridge_broader", "comparator": "persistence"}],
        "folds.json": [
            {
                "target": "registrations",
                "target_year": year,
                "model": "ridge_broader",
                "feature_columns": ["h_latest", "b1_start"],
            }
            for year in (2024, 2025)
        ],
    }
    payload.update(changes)
    publish_run(
        root,
        parent_id,
        {name: json_bytes(value) for name, value in payload.items()},
        {
            "stage": "assess",
            "parents": {
                "panel": _fingerprint(root, "followup-1-panel"),
                "shortlist": _fingerprint(root, "initial-shortlist"),
                "prior_assessment": _fingerprint(root, prior_id),
            },
        },
    )
    return payload


@pytest.mark.parametrize(
    "changes",
    [
        {"model": "extra_trees_broader"},
        {"seed": 1},
        {"budgets": [15]},
        {"parent_run": ""},
        {"output_root": "../outside"},
        {"question": " "},
        {"schema_version": True},
        {"extra": "unknown"},
    ],
)
def test_config_rejects_undocumented_decision_changes(
    tmp_path: Path, changes: dict[str, Any]
) -> None:
    with pytest.raises(ValueError, match="settings|question|configuration"):
        reassessment.load_config(_config(tmp_path, **changes))


def test_reassessment_preserves_predictions_shortlist_and_comparator_without_fit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kasm.program_prediction import modeling

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Decision reassessment must not refit a model")

    monkeypatch.setattr(modeling, "evaluate", forbidden)
    parent = _parent(tmp_path)
    files, parents = reassessment.reassess(tmp_path, _config(tmp_path))
    assert parents["assessment"] == "followup-1-later"
    assert parents["shortlist"] == "initial-shortlist"
    assert json.loads(files["predictions.json"]) == parent["predictions.json"]
    assert json.loads(files["shortlist.json"]) == parent["shortlist.json"]
    assert json.loads(files["inherited-metrics.json"]) == parent["metrics.json"]
    assert json.loads(files["question.json"])["model"] == "ridge_broader"
    assert json.loads(files["comparators.json"])["registrations"] == "persistence"
    review = json.loads(files["reviews.json"])[0]
    assert {row["method"] for row in review["metrics"]} == {
        "ridge_broader",
        "last_change",
        "latest_level",
        "persistence",
        "random_expectation",
    }
    assert any(row["observed"] is None for row in review["selections"])
    assert len(json.loads(files["decision-differences.json"])) == 9
    assert files["review-budget.png"].startswith(b"\x89PNG\r\n\x1a\n")
    html = files["report.html"].decode()
    assert "P000" not in html
    assert "adapted" in html
    assert "not independent" in html


def test_missing_or_changed_completed_parent_fails(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with pytest.raises(ValueError, match="missing|unreadable"):
        reassessment.reassess(tmp_path, config)
    _parent(tmp_path)
    (tmp_path / OUTPUT_ROOT / "followup-1-later" / "predictions.json").write_text("[]")
    with pytest.raises(ValueError, match="hash|identity"):
        reassessment.reassess(tmp_path, config)


def test_distinct_audit_run_ids_preserve_the_same_recorded_ancestry(tmp_path: Path) -> None:
    _parent(tmp_path, parent_id="audit-followup-1-later", prior_id="audit-initial-later")
    files, parents = reassessment.reassess(
        tmp_path, _config(tmp_path, parent_run="audit-followup-1-later")
    )
    assert parents["assessment"] == "audit-followup-1-later"
    assert json.loads(files["report.json"])["new_model_fits"] == 0


@pytest.mark.parametrize(
    "case", ["round", "features", "question", "shortlist", "comparator", "years"]
)
def test_parent_must_retain_the_specified_question_and_lineage(tmp_path: Path, case: str) -> None:
    changes: dict[str, Any] = {}
    if case in {"round", "features", "question"}:
        settings = replace(
            SprintConfig(),
            round_id="followup_1",
            targets=("registrations",),
            omit_oar_features=True,
            parent_run="initial-later",
            question="Prior question",
        ).raw
        settings[
            {"round": "round_id", "features": "omit_oar_features", "question": "question"}[case]
        ] = {"round": "initial", "features": False, "question": ""}[case]
        changes["settings.json"] = settings
    elif case == "shortlist":
        changes["shortlist.json"] = {"questions": []}
    elif case == "comparator":
        changes["comparators.json"] = {"registrations": "recent_mean"}
    else:
        changes["predictions.json"] = []
    _parent(tmp_path, **changes)
    with pytest.raises(ValueError, match="parent|Parent|lineage|shortlist|coverage|settings"):
        reassessment.reassess(tmp_path, _config(tmp_path))
