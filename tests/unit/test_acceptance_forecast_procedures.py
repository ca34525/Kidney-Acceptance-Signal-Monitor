from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
from math import ceil, exp, sin
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from kasm.acceptance_forecast import procedures
from kasm.acceptance_forecast.config import ForecastError
from kasm.acceptance_forecast.procedures import generate_predictions
from kasm.config import DataSourceManifest, SourceRecord
from kasm.modeling.features import MODEL_FEATURE_COLUMNS

if TYPE_CHECKING:
    from kasm.acceptance_forecast.config import ComparisonConfig


def _config() -> ComparisonConfig:
    return cast(
        "ComparisonConfig",
        SimpleNamespace(
            years=(2021, 2022, 2023, 2024, 2025),
            models=(
                "persistence",
                "historical_mean",
                "ridge",
                "ridge_recent3",
                "adjusted_persistence",
            ),
            alpha=10.0,
            seed=20260903,
            training_start=2018,
            warmup_year=2020,
            recent_window=3,
        ),
    )


def _fixture(n: int = 32) -> tuple[list[dict[str, object]], DataSourceManifest]:
    sources = tuple(
        SourceRecord(
            release_code=f"r{year}",
            cohort_year=year,
            transport="xls",
            url=f"https://example.org/{year}.xls",
            download_bytes=1,
            download_sha256="0" * 64,
            published_value=f"{year + 1}-07",
            published_precision="month",
        )
        for year in range(2017, 2026)
    )
    rows: list[dict[str, object]] = []
    for target_year in range(2018, 2027):
        for program in range(n):
            feature_year = target_year - 1
            current = 0.2 * sin(feature_year - 2017) + program * 0.03
            previous = 0.2 * sin(feature_year - 2018) + program * 0.03
            target = 0.2 * sin(target_year - 2017) + program * 0.03
            row: dict[str, object] = dict.fromkeys(MODEL_FEATURE_COLUMNS, 0.0)
            row.update(
                {
                    "program_key": f"P{program:03}:TX1",
                    "feature_cohort_year": feature_year,
                    "target_cohort_year": target_year,
                    "prediction_as_of": f"{target_year}-07",
                    "prediction_as_of_precision": "month",
                    "truth_published_value": f"{target_year + 1}-07"
                    if target_year <= 2025
                    else None,
                    "truth_published_precision": "month" if target_year <= 2025 else None,
                    "target_cohort_end": date(target_year, 12, 31),
                    "current_log_overall_oar": current,
                    "previous_annual_log_overall_oar": previous if target_year > 2018 else None,
                    "one_year_change_log_overall_oar": current - previous
                    if target_year > 2018
                    else None,
                    "log1p_overall_expected_acceptances": 2.0 + program * 0.1,
                    "log_credible_interval_width": 0.5,
                    "target_log_oar": target if target_year <= 2025 else None,
                    "target_oar": exp(target) if target_year <= 2025 else None,
                    "analytic_eligible": target_year <= 2025,
                    "first_observed_program": target_year == 2018,
                    "public_forecast_eligible": target_year > 2018,
                }
            )
            for column in MODEL_FEATURE_COLUMNS:
                if column.startswith("missing_"):
                    row[column] = row[column.removeprefix("missing_")] is None
            rows.append(row)
    return rows, DataSourceManifest(schema_version=2, sources=sources)


def test_all_methods_share_rows_and_reassess_bands_from_prior_predictions() -> None:
    panel, manifest = _fixture()
    predictions, fits = generate_predictions(panel, manifest, _config())

    assert len(predictions) == 32 * 5 * 5
    assert len(fits) == 6 * 5
    assert {row["target_cohort_year"] for row in predictions} == set(range(2021, 2026))
    assert all(row["calibration_n"] == 32 for row in predictions)
    assert all(row["public_forecast_eligible"] is True for row in predictions)
    for model in _config().models:
        assert (
            len(
                {
                    (r["program_key"], r["target_cohort_year"])
                    for r in predictions
                    if r["model"] == model
                }
            )
            == 32 * 5
        )
    persistence = [row for row in predictions if row["model"] == "persistence"]
    assert all(row["predicted_log_oar"] == row["current_log_overall_oar"] for row in persistence)
    residuals = sorted(
        abs(cast(float, row["current_log_overall_oar"]) - cast(float, row["target_log_oar"]))
        for row in panel
        if row["target_cohort_year"] == 2020
    )
    radius = residuals[min(len(residuals), ceil((len(residuals) + 1) * 0.8)) - 1]
    assert {
        row["band_radius_log_oar"] for row in persistence if row["target_cohort_year"] == 2021
    } == {radius}
    ridge = next(
        row for row in fits if row["model"] == "ridge" and row["target_cohort_year"] == 2025
    )
    recent = next(
        row for row in fits if row["model"] == "ridge_recent3" and row["target_cohort_year"] == 2025
    )
    adjusted = next(row for row in fits if row["model"] == "adjusted_persistence")
    assert ridge["training_target_years"] == list(range(2018, 2025))
    assert recent["training_target_years"] == [2022, 2023, 2024]
    assert len(cast(list[float], ridge["coefficients"])) == len(MODEL_FEATURE_COLUMNS)
    assert adjusted["feature_columns"] == ["current_log_overall_oar"]
    assert isinstance(adjusted["intercept"], float)


def test_comparison_records_retain_fixed_earlier_groups_for_every_method() -> None:
    panel, manifest = _fixture()
    predictions, _ = generate_predictions(panel, manifest, _config())
    assert {row["expected_acceptance_quartile"] for row in predictions} == {1, 2, 3, 4}
    assert all(row["earlier_oar_group"] for row in predictions)
    assert all(row["predictor_missingness"] == "none_missing" for row in predictions)


def test_later_outcomes_do_not_enter_earlier_fits_or_band_calibration() -> None:
    panel, manifest = _fixture()
    changed = deepcopy(panel)
    for row in changed:
        if row["target_cohort_year"] in {2024, 2025}:
            row["target_log_oar"] = cast(float, row["target_log_oar"]) + 2.0
            row["target_oar"] = exp(cast(float, row["target_log_oar"]))
    original_predictions, original_fits = generate_predictions(panel, manifest, _config())
    changed_predictions, changed_fits = generate_predictions(changed, manifest, _config())
    assert [row for row in original_predictions if cast(int, row["target_cohort_year"]) < 2024] == [
        row for row in changed_predictions if cast(int, row["target_cohort_year"]) < 2024
    ]
    assert [row for row in original_fits if cast(int, row["target_cohort_year"]) <= 2024] == [
        row for row in changed_fits if cast(int, row["target_cohort_year"]) <= 2024
    ]
    assert original_fits != changed_fits


def test_unavailable_outcomes_and_forged_origins_are_rejected() -> None:
    panel, manifest = _fixture()
    panel[0]["prediction_as_of"] = "2035-07"
    with pytest.raises(ForecastError, match="publication|origin"):
        generate_predictions(panel, manifest, _config())

    panel, manifest = _fixture()
    delayed = replace(manifest.sources[1], published_value="2035-07")
    manifest = replace(manifest, sources=(manifest.sources[0], delayed, *manifest.sources[2:]))
    for row in panel:
        if row["feature_cohort_year"] == 2018:
            row["prediction_as_of"] = "2035-07"
        if row["target_cohort_year"] == 2018:
            row["truth_published_value"] = "2035-07"
    with pytest.raises(ForecastError, match="not public"):
        generate_predictions(panel, manifest, _config())


def test_bands_are_suppressed_when_prior_year_has_fewer_than_thirty_programs() -> None:
    panel, manifest = _fixture(n=29)
    predictions, _ = generate_predictions(panel, manifest, _config())
    assert all(row["calibration_n"] == 29 for row in predictions)
    assert all(row["band_radius_log_oar"] is None for row in predictions)
    assert all(row["band_covered"] is None for row in predictions)


@pytest.mark.parametrize("invalid", [None, 0.0, float("inf"), float("nan")])
def test_invalid_observed_targets_fail_without_dropping_rows(invalid: float | None) -> None:
    panel, manifest = _fixture()
    panel[0]["target_oar"] = invalid
    with pytest.raises(ForecastError, match="target"):
        generate_predictions(panel, manifest, _config())


def test_missing_target_and_public_ineligibility_keep_their_declared_meaning() -> None:
    panel, manifest = _fixture()
    eligible = next(row for row in panel if row["target_cohort_year"] == 2023)
    eligible["first_observed_program"] = True
    eligible["public_forecast_eligible"] = False
    excluded = next(row for row in panel if row["target_cohort_year"] == 2024)
    excluded.update({"analytic_eligible": False, "target_oar": None, "target_log_oar": None})
    predictions, _ = generate_predictions(panel, manifest, _config())
    rows = [
        row
        for row in predictions
        if row["program_key"] == eligible["program_key"] and row["target_cohort_year"] == 2023
    ]
    assert len(rows) == 5
    assert all(row["public_forecast_eligible"] is False for row in rows)
    assert not any(
        row["program_key"] == excluded["program_key"] and row["target_cohort_year"] == 2024
        for row in predictions
    )


def test_a_source_cannot_make_unfinished_measurements_available() -> None:
    panel, manifest = _fixture()
    premature = replace(manifest.sources[1], published_value="2018-07")
    manifest = replace(manifest, sources=(manifest.sources[0], premature, *manifest.sources[2:]))
    for row in panel:
        if row["feature_cohort_year"] == 2018:
            row["prediction_as_of"] = "2018-07"
            row["previous_annual_log_overall_oar"] = None
            row["one_year_change_log_overall_oar"] = None
            row["missing_previous_annual_log_overall_oar"] = True
            row["missing_one_year_change_log_overall_oar"] = True
        if row["target_cohort_year"] == 2018:
            row["truth_published_value"] = "2018-07"
    with pytest.raises(ForecastError, match="cohort.*complete"):
        generate_predictions(panel, manifest, _config())


def test_incomplete_candidate_predictions_are_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    panel, manifest = _fixture()
    monkeypatch.setattr(procedures, "_predict_model", lambda *_args: ([], {}))
    with pytest.raises(ForecastError, match="Every required row"):
        generate_predictions(panel, manifest, _config())


def test_history_and_preprocessing_exclude_later_feature_values() -> None:
    panel, manifest = _fixture()
    changed = deepcopy(panel)
    for row in changed:
        if row["target_cohort_year"] == 2021:
            row["log1p_overall_expected_acceptances"] = 50.0
    predictions, fits = generate_predictions(panel, manifest, _config())
    _, changed_fits = generate_predictions(changed, manifest, _config())
    assert [row for row in fits if row["target_cohort_year"] == 2021] == [
        row for row in changed_fits if row["target_cohort_year"] == 2021
    ]
    row = next(
        row
        for row in predictions
        if row["target_cohort_year"] == 2021 and row["model"] == "historical_mean"
    )
    history = [
        cast(float, p["current_log_overall_oar"])
        for p in panel
        if p["program_key"] == row["program_key"] and cast(int, p["feature_cohort_year"]) <= 2020
    ]
    assert row["predicted_log_oar"] == pytest.approx(sum(history) / len(history))
