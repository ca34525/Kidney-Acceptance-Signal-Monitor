from __future__ import annotations

from datetime import date
from math import exp
from pathlib import Path
from subprocess import CompletedProcess

import pytest
import yaml

import kasm.modeling.replay as replay_module
from kasm.modeling.activation import BandPromotion, PointPromotion
from kasm.modeling.experiment import load_frozen_experiment_config
from kasm.modeling.replay import (
    evaluate_frozen_replay,
    frozen_replay_predictions_table,
    generate_frozen_replay_predictions,
    resolve_release_decision,
)


def _row(program_key: str, target_year: int, offset: float) -> dict[str, object]:
    current = (target_year - 2020) / 10 + offset
    target_log = current * 0.75 + 0.02
    return {
        "program_key": program_key,
        "feature_cohort_year": target_year - 1,
        "target_cohort_year": target_year,
        "prediction_as_of": f"{target_year}-07-01",
        "prediction_as_of_precision": "day",
        "target_cohort_end": date(target_year, 12, 31),
        "truth_published_value": f"{target_year + 1}-07-01",
        "truth_published_precision": "day",
        "elapsed_target_cohort_fraction_at_prediction": 0.5,
        "current_log_overall_oar": current,
        "previous_annual_log_overall_oar": current - 0.1,
        "one_year_change_log_overall_oar": 0.1,
        "log1p_overall_expected_acceptances": 3.0 + offset,
        "log_credible_interval_width": 0.4,
        "current_log_low_oar": current - 0.1,
        "current_log_medium_oar": current,
        "current_log_high_oar": current + 0.1,
        "current_log_hard_to_place_oar": current + 0.2,
        "high_offers_share": 0.4,
        "hard_to_place_offers_share": 0.1,
        "missing_previous_annual_log_overall_oar": False,
        "missing_one_year_change_log_overall_oar": False,
        "missing_current_log_low_oar": False,
        "missing_current_log_medium_oar": False,
        "missing_current_log_high_oar": False,
        "missing_current_log_hard_to_place_oar": False,
        "target_log_oar": target_log,
        "target_oar": exp(target_log),
        "analytic_eligible": True,
        "public_forecast_eligible": target_year > 2018,
        "first_observed_program": target_year == 2018,
    }


def _rows(program_count: int = 8) -> tuple[dict[str, object], ...]:
    return tuple(
        _row(f"{index:04d}:TX1", target_year, index / 100)
        for target_year in range(2018, 2026)
        for index in range(program_count)
    )


def test_replay_fit_excludes_2024_outcomes_and_evaluates_only_2025() -> None:
    config = load_frozen_experiment_config(Path("configs/frozen_experiment.yaml"))
    rows = _rows()
    mutated_rows = tuple(dict(row) for row in rows)
    for row in mutated_rows:
        if row["target_cohort_year"] == 2024:
            row["target_log_oar"] = 1000.0
            row["target_oar"] = exp(10.0)

    original = generate_frozen_replay_predictions(rows, config=config)
    mutated = generate_frozen_replay_predictions(mutated_rows, config=config)

    assert original.training_target_years == (2018, 2019, 2020, 2021, 2022, 2023)
    assert original.evaluation_target_year == 2025
    assert original.predictions == mutated.predictions
    assert {row.target_cohort_year for row in original.predictions} == {2025}


@pytest.mark.parametrize("retain_calibration", [False, True])
def test_no_activation_replay_preserves_points_without_uncertainty_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    retain_calibration: bool,
) -> None:
    raw = yaml.safe_load(Path("configs/frozen_experiment.yaml").read_text(encoding="utf-8"))
    raw["forecast_activation_attempted"] = False
    raw["pre_replay_freeze"]["candidate_gate_passed"] = False
    if not retain_calibration:
        raw["empirical_band"]["calibration_evidence"] = None
    config_path = tmp_path / "disabled.yaml"
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    config = load_frozen_experiment_config(config_path)

    def reject_uncertainty(*args: object, **kwargs: object) -> None:
        raise AssertionError("Skipped activation must not calculate uncertainty evidence")

    monkeypatch.setattr(
        replay_module, "paired_bootstrap_mae_difference_interval", reject_uncertainty
    )
    monkeypatch.setattr(replay_module, "clopper_pearson_interval", reject_uncertainty)
    rows = _rows(4)
    fit = generate_frozen_replay_predictions(rows, config=config)
    assert fit.training_target_years[-1] == 2023
    assert all(row.ridge_band_lower_oar is None for row in fit.predictions)
    assert all(row.persistence_band_covered is None for row in fit.predictions)
    with pytest.raises(replay_module.FrozenReplayError, match="activation state"):
        frozen_replay_predictions_table(fit.predictions)
    table = frozen_replay_predictions_table(fit.predictions, activation_attempted=False)
    for field in table.schema:
        if "_band_" in field.name:
            assert field.nullable
            assert table[field.name].null_count == 4
    report = evaluate_frozen_replay(fit, rows=rows, config=config)
    assert report["overall"]["n"] == 4
    assert report["overall"]["ridge_mae_log_oar"] >= 0
    assert report["overall"]["ridge_band_coverage"] is None
    assert report["bootstrap"] is None
    assert report["band_promotion"] is None
    assert report["calibration_target_year"] is None
    assert report["release_decision"]["activation_status"] == "not_attempted"
    assert report["release_decision"]["displayed_model"] == "persistence"
    assert report["release_decision"]["display_band"] is False


def test_replay_report_contains_frozen_gates_diagnostics_and_sensitivities() -> None:
    config = load_frozen_experiment_config(Path("configs/frozen_experiment.yaml"))
    rows = _rows(program_count=120)
    replay = generate_frozen_replay_predictions(rows, config=config)

    report = evaluate_frozen_replay(replay, rows=rows, config=config)

    assert report["frozen_replay_evaluated"] is True
    assert report["training_target_years"] == [2018, 2019, 2020, 2021, 2022, 2023]
    assert report["replay_target_year"] == 2025
    assert report["bootstrap"]["resamples"] == 10_000
    assert report["bootstrap"]["resampling_unit"] == "program_key"
    assert report["point_promotion"]["displayed_model"] in {"ridge", "persistence"}
    assert isinstance(report["band_promotion"]["display_band"], bool)
    assert len(report["by_expected_acceptance_quartile"]) == 4
    assert report["by_expected_acceptance_quartile"][0]["n"] == 30
    assert {item["name"] for item in report["sensitivities"]} == {
        "exclude_transitions_touching_2020",
        "exclude_transitions_touching_2021",
    }
    assert {item["stratum"] for item in report["missingness_and_entry_diagnostics"]} == {
        "first_observed_program",
        "established_program",
        "any_predictor_missing",
        "no_predictor_missing",
    }


def test_passing_ridge_band_gate_cannot_expose_an_unpromoted_ridge_forecast() -> None:
    decision = resolve_release_decision(
        point=PointPromotion(
            promoted=False,
            displayed_model="persistence",
            skill_over_persistence=0.10,
            failed_criteria=("bias_not_exceed_persistence",),
        ),
        band=BandPromotion(
            display_band=True,
            coverage=0.81,
            exact_interval_lower=0.76,
            exact_interval_upper=0.86,
            mean_width_relative_to_persistence=0.90,
            failed_criteria=(),
        ),
    )

    assert decision.activation_status == "attempted_not_promoted"
    assert decision.displayed_model == "persistence"
    assert decision.ridge_band_gate_passed is True
    assert decision.display_band is False


def test_replay_rejects_a_frozen_config_that_differs_from_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = tmp_path / "repository"
    config_path = repository_root / "configs" / "frozen_experiment.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("changed: true\n", encoding="utf-8")

    def fake_git(root: Path, arguments: tuple[str, ...]) -> CompletedProcess[bytes]:
        if arguments[:2] == ("rev-parse", "--show-toplevel"):
            return CompletedProcess(arguments, 0, f"{repository_root}\n".encode(), b"")
        if arguments[0] == "ls-files":
            return CompletedProcess(arguments, 0, b"configs/frozen_experiment.yaml\n", b"")
        if arguments[0] == "diff":
            return CompletedProcess(arguments, 1, b"", b"")
        raise AssertionError(f"Unexpected Git call: {arguments}")

    monkeypatch.setattr(replay_module, "_run_git", fake_git)

    with pytest.raises(replay_module.FrozenReplayError, match="differs from HEAD"):
        replay_module.run_frozen_replay(
            panel_path=tmp_path / "unused.parquet",
            config_path=config_path,
            source_manifest_path=tmp_path / "unused.yaml",
            output_root=tmp_path / "output",
        )
