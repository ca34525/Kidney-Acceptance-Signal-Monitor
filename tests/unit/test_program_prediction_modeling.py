from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from math import exp, log, log1p
from typing import Any

import numpy as np
import pytest

from kasm.program_prediction import modeling
from kasm.program_prediction.config import SprintConfig


def _config() -> SprintConfig:
    return replace(
        SprintConfig(),
        targets=("registrations", "overall_oar"),
        round_id="followup_1",
        question="Do fixed fixture values preserve the research rules?",
        parent_run="fixture",
    )


def _row(year: int, program: int = 0, target: str = "registrations") -> dict[str, Any]:
    latest = 2.0 + program
    previous = 1.0 + program
    transform = log if target == "overall_oar" else log1p
    return {
        "program_key": f"P{program:03}:TX1",
        "target": target,
        "target_year": year,
        "feature_year": year - 1,
        "origin_release": f"r{year}",
        "origin_value": f"{year}-07",
        "origin_precision": "month",
        "truth_release": f"r{year + 1}",
        "truth_published_value": f"{year + 1}-07",
        "truth_published_precision": "month",
        "eligible": True,
        "first_observed": False,
        "exclusion_reason": None,
        "latest": latest,
        "previous": previous,
        "recent_values": [latest, previous],
        "mean2": (latest + previous) / 2,
        "last_change": latest - previous,
        "observed": 1.2 * latest,
        "h_latest": transform(latest),
        "h_previous": transform(previous),
        "h_mean3": (transform(latest) + transform(previous)) / 2,
        "h_change": transform(latest) - transform(previous),
        "earlier_list_size": 50.0 + program,
    }


def _feature_map() -> dict[str, dict[str, str]]:
    return {
        field: {"block": "history", "source": "past target", "transform": "log/log1p"}
        for field in ("h_latest", "h_previous", "h_mean3", "h_change")
    }


def _fixture() -> list[dict[str, Any]]:
    return [
        _row(year, program, target)
        for target in _config().targets
        for year in (2019, 2020, 2021)
        for program in range(24)
    ]


def test_baselines_use_count_units_and_log_oar_with_gap_fallback() -> None:
    row = _row(2021)
    row.update(latest=10.0, previous=4.0, recent_values=[10.0, 4.0], last_change=6.0)
    assert modeling.baseline_score(row, "persistence") == 10.0
    assert modeling.baseline_score(row, "recent_mean") == 7.0
    assert modeling.baseline_score(row, "damped_trend") == 13.0
    row.update(previous=None, recent_values=[10.0, 4.0], last_change=None)
    assert modeling.baseline_score(row, "recent_mean") == 7.0
    assert modeling.baseline_score(row, "damped_trend") == 10.0
    row.update(target="overall_oar", latest=4.0, previous=1.0, recent_values=[4.0, 1.0])
    assert modeling.baseline_score(row, "recent_mean") == pytest.approx(log(2))
    assert modeling.baseline_score(row, "damped_trend") == pytest.approx(log(8))
    row.update(target="registrations", latest=0.0, previous=10.0, recent_values=[0.0, 10.0])
    assert modeling.baseline_score(row, "damped_trend") == 0.0


def test_all_models_keep_missing_truth_and_exclude_first_observed() -> None:
    rows = _fixture()
    rows.append({**_row(2021, 99), "observed": None})
    rows.append({**_row(2021, 98), "eligible": False, "first_observed": True})
    result = modeling.evaluate(rows, _config(), (2021,), _feature_map())
    missing = [row for row in result["predictions"] if row["program_key"] == "P099:TX1"]
    assert len(missing) == 7
    assert all(row["observed"] is None and row["status"] == "ok" for row in missing)
    assert not any(row["program_key"] == "P098:TX1" for row in result["predictions"])
    assert any(row["program_key"] == "P098:TX1" for row in result["exclusions"])
    assert {row["model"] for row in result["predictions"]} == {
        "persistence",
        "recent_mean",
        "damped_trend",
        "adjusted_persistence",
        *_config().pipelines,
    }
    assert result["failures"] == []


def test_same_release_training_labels_allowed_but_later_publication_excluded() -> None:
    rows = _fixture()
    for row in rows:
        if row["target_year"] == 2019 and row["program_key"] == "P000:TX1":
            row.update(truth_release="delayed", truth_published_value="2021-08")
    result = modeling.evaluate(rows, _config(), (2021,), _feature_map())
    fits = [row for row in result["folds"] if row["model"] == "ridge_history"]
    assert len(fits) == 2
    assert all(row["training_n"] == 47 for row in fits)
    assert all(row["training_target_years"] == [2019, 2020] for row in fits)
    assert all(row["training_year_counts"] == {"2019": 23, "2020": 24} for row in fits)
    assert any(row["reason"] == "training_label_not_public" for row in result["exclusions"])


@pytest.mark.parametrize("bad", ["already_public", "feature_period", "split_cohort"])
def test_invalid_temporal_panel_is_a_hard_error(bad: str) -> None:
    rows = _fixture()
    if bad == "already_public":
        rows[0].update(truth_release="r2019", truth_published_value="2019-07")
    elif bad == "feature_period":
        rows[0]["feature_year"] = rows[0]["target_year"]
    else:
        rows[0].update(origin_release="other", origin_value="2019-08")
    with pytest.raises(modeling.ModelingError):
        modeling.evaluate(rows, _config(), (2021,), _feature_map())


def test_identity_future_features_and_duplicates_are_hard_errors() -> None:
    rows = _fixture()
    for prohibited in ("center_code", "target_year", "future_available", "h_program_key"):
        feature_map = {**_feature_map(), prohibited: {"block": "broader"}}
        with pytest.raises(modeling.ModelingError, match="feature"):
            modeling.evaluate(rows, _config(), (2021,), feature_map)
    with pytest.raises(modeling.ModelingError, match="duplicate"):
        modeling.evaluate([*rows, rows[0]], _config(), (2021,), _feature_map())


def test_fold_local_medians_and_indicators_cannot_learn_from_evaluation() -> None:
    rows = _fixture()
    for row in rows:
        row["h_previous"] = None
        if row["target_year"] == 2021:
            row["h_previous"] = 123456.0
    result = modeling.evaluate(rows, _config(), (2021,), _feature_map())
    fit = next(row for row in result["folds"] if row["model"] == "ridge_history")
    assert fit["entirely_missing_features"] == ["h_previous"]
    assert fit["parameters"]["imputer_statistics"][1] == 0.0
    assert fit["parameters"]["indicator_features"] == list(_feature_map())
    assert fit["parameters"]["scaler_mean"][1] == 0.0
    changed = deepcopy(rows)
    for row in changed:
        if row["target_year"] == 2021:
            row["observed"] = 1e12
    changed_result = modeling.evaluate(changed, _config(), (2021,), _feature_map())
    assert [row["prediction"] for row in result["predictions"]] == [
        row["prediction"] for row in changed_result["predictions"]
    ]


def test_backtransform_clips_counts_and_rejects_nonfinite_and_oar_underflow() -> None:
    assert modeling.backtransform(-1000.0, "registrations") == (0.0, 0.0)
    assert modeling.backtransform(log1p(5), "registrations") == pytest.approx((5.0, 5.0))
    assert modeling.backtransform(log(5), "overall_oar") == pytest.approx((5.0, log(5)))
    for bad in (float("nan"), float("inf"), 10000.0):
        with pytest.raises(modeling.ModelingError):
            modeling.backtransform(bad, "registrations")
    with pytest.raises(modeling.ModelingError):
        modeling.backtransform(-1000.0, "overall_oar")


def test_failed_fit_preserves_every_prediction_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise ValueError("fixture rejected fit")

    monkeypatch.setattr(modeling, "fit_pipeline", fail)
    result = modeling.evaluate(_fixture(), _config(), (2021,), _feature_map())
    failed = [row for row in result["predictions"] if row["status"] == "fit_failed"]
    assert len(failed) == 24 * 4 * 2
    assert all(row["prediction"] is None for row in failed)
    assert len(result["failures"]) == 8
    assert all("fixture rejected fit" in row["error"] for row in result["failures"])


def test_one_bad_prediction_keeps_other_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    original = modeling.fit_pipeline

    def contaminated(*args: Any, **kwargs: Any) -> Any:
        pipeline = original(*args, **kwargs)

        def predict(matrix: Any) -> Any:
            values = np.ones(len(matrix))
            values[0] = np.inf
            return values

        pipeline.predict = predict
        return pipeline

    monkeypatch.setattr(modeling, "fit_pipeline", contaminated)
    result = modeling.evaluate(_fixture(), _config(), (2021,), _feature_map())
    assert sum(row["status"] == "prediction_failed" for row in result["predictions"]) == 8
    assert len(result["predictions"]) == 24 * (7 + 8)


def test_adjusted_persistence_learns_intercept_and_slope_in_log_units() -> None:
    rows = [_row(year, program, "overall_oar") for year in (2019, 2021) for program in range(24)]
    for row in rows:
        row["observed"] = exp(0.3 + 0.5 * log(row["latest"]))
    result = modeling.evaluate(rows, _config(), (2021,), _feature_map())
    fitted = [row for row in result["predictions"] if row["model"] == "adjusted_persistence"]
    assert all(row["prediction"] == pytest.approx(row["observed"]) for row in fitted)
    fit = next(row for row in result["folds"] if row["model"] == "adjusted_persistence")
    assert fit["parameters"]["coefficients"] == pytest.approx([0.5])
    assert fit["parameters"]["intercept"] == pytest.approx(0.3)


def test_shortlist_can_be_assessed_first_without_dropping_other_targets() -> None:
    result = modeling.evaluate(
        _fixture(), _config(), (2021,), _feature_map(), prioritized_targets=("overall_oar",)
    )
    assert result["predictions"][0]["target"] == "overall_oar"
    assert {row["target"] for row in result["predictions"]} == set(_config().targets)
    with pytest.raises(modeling.ModelingError):
        modeling.evaluate(
            _fixture(), _config(), (2021,), _feature_map(), prioritized_targets=("future",)
        )


def test_empty_fold_retains_each_planned_procedure() -> None:
    result = modeling.evaluate([], _config(), (2021,), _feature_map())
    assert len(result["folds"]) == 15
    assert len(result["failures"]) == 15
    assert all(row["evaluation_n"] == 0 for row in result["folds"])


def test_execution_rejects_silently_changed_settings_and_future_feature_metadata() -> None:
    with pytest.raises(ValueError, match="fixed initial"):
        modeling.evaluate(_fixture(), replace(_config(), ridge_alpha=0.01), (2021,), _feature_map())
    for field in ("b1_feature_year", "oar_feature_year"):
        rows = _fixture()
        rows[0][field] = rows[0]["target_year"]
        with pytest.raises(modeling.ModelingError, match="Feature period"):
            modeling.evaluate(rows, _config(), (2021,), _feature_map())
