from __future__ import annotations

from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from kasm.data.build import MODEL_PANEL_SCHEMA, PROGRAM_SIGNALS_SCHEMA
from kasm.reporting.history import (
    HistoricalDataError,
    interval_status,
    latest_overall_status,
    latest_persistence_projection,
    latest_public_forecast_eligibility,
    latest_subgroup_rows,
    latest_volume_context,
    load_historical_artifacts,
    overall_history,
    program_options,
    subgroup_history,
)


def _signal_row(
    *,
    program_key: str = "ABCD:TX1",
    year: int,
    offer_group: str = "overall",
    center_name: str = "Example Transplant Center",
    city: str | None = "Boston",
    state: str | None = "MA",
    offers: int | None = 100,
    expected_acceptances: float | None = 12.5,
    oar_mean: float | None = 0.9,
    oar_lower: float | None = 0.7,
    oar_upper: float | None = 1.1,
) -> dict[str, object]:
    center_code, center_type = program_key.split(":")
    return {
        "program_key": program_key,
        "center_code": center_code,
        "center_type": center_type,
        "center_name": center_name,
        "city": city,
        "state": state,
        "zip": "01234",
        "release_code": str(year),
        "published_value": "2025-07" if year == 2024 else f"{year + 1}-07-07",
        "published_precision": "month" if year == 2024 else "day",
        "cohort_year": year,
        "cohort_start": date(year, 1, 1),
        "cohort_end": date(year, 12, 31),
        "offer_group": offer_group,
        "offers": offers,
        "acceptances": None if offers is None else offers // 10,
        "expected_acceptances": expected_acceptances,
        "oar_mean": oar_mean,
        "oar_lower": oar_lower,
        "oar_upper": oar_upper,
        "source_url": f"https://example.test/{year}.xls",
        "source_sha256": "0" * 64,
    }


def _panel_row(
    *, program_key: str = "ABCD:TX1", feature_year: int, public_eligible: bool
) -> dict[str, object]:
    return {
        "program_key": program_key,
        "feature_cohort_year": feature_year,
        "target_cohort_year": feature_year + 1,
        "prediction_as_of": f"{feature_year + 1}-07-07",
        "prediction_as_of_precision": "day",
        "target_cohort_end": date(feature_year + 1, 12, 31),
        "truth_published_value": None,
        "truth_published_precision": None,
        "elapsed_target_cohort_fraction_at_prediction": 0.52,
        "current_log_overall_oar": -0.1,
        "previous_annual_log_overall_oar": -0.2,
        "one_year_change_log_overall_oar": 0.1,
        "log1p_overall_expected_acceptances": 2.6,
        "log_credible_interval_width": 0.45,
        "current_log_low_oar": None,
        "current_log_medium_oar": -0.1,
        "current_log_high_oar": -0.2,
        "current_log_hard_to_place_oar": -0.3,
        "high_offers_share": 0.4,
        "hard_to_place_offers_share": 0.1,
        "missing_previous_annual_log_overall_oar": False,
        "missing_one_year_change_log_overall_oar": False,
        "missing_current_log_low_oar": True,
        "missing_current_log_medium_oar": False,
        "missing_current_log_high_oar": False,
        "missing_current_log_hard_to_place_oar": False,
        "target_oar": None,
        "target_log_oar": None,
        "analytic_eligible": False,
        "public_forecast_eligible": public_eligible,
        "first_observed_program": False,
    }


def _write_artifacts(
    artifact_dir: Path,
    signal_rows: list[dict[str, object]],
    panel_rows: list[dict[str, object]],
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.Table.from_pylist(signal_rows, schema=PROGRAM_SIGNALS_SCHEMA),
        artifact_dir / "program_signals.parquet",
    )
    pq.write_table(
        pa.Table.from_pylist(panel_rows, schema=MODEL_PANEL_SCHEMA),
        artifact_dir / "model_panel.parquet",
    )


def test_loader_rejects_missing_or_schema_incompatible_artifacts(tmp_path: Path) -> None:
    with pytest.raises(HistoricalDataError, match="program_signals.parquet"):
        load_historical_artifacts(tmp_path)

    _write_artifacts(
        tmp_path,
        [_signal_row(year=2025)],
        [_panel_row(feature_year=2025, public_eligible=False)],
    )
    incompatible = pq.read_table(tmp_path / "program_signals.parquet").drop(["source_sha256"])
    pq.write_table(incompatible, tmp_path / "program_signals.parquet")

    with pytest.raises(HistoricalDataError, match="canonical schema"):
        load_historical_artifacts(tmp_path)


def test_program_options_use_display_fields_and_composite_identity(tmp_path: Path) -> None:
    _write_artifacts(
        tmp_path,
        [
            _signal_row(year=2025, program_key="ABCD:VA1", center_name="VA Program"),
            _signal_row(year=2025, program_key="ABCD:TX1", center_name="Community Program"),
        ],
        [
            _panel_row(program_key="ABCD:VA1", feature_year=2025, public_eligible=False),
            _panel_row(program_key="ABCD:TX1", feature_year=2025, public_eligible=True),
        ],
    )

    choices = program_options(load_historical_artifacts(tmp_path))

    assert [(choice.program_key, choice.label) for choice in choices] == [
        ("ABCD:TX1", "Community Program — Boston, MA"),
        ("ABCD:VA1", "VA Program — Boston, MA"),
    ]


@pytest.mark.parametrize(
    ("lower", "upper", "expected"),
    [
        (0.5, 0.9, "95% interval entirely below 1"),
        (0.8, 1.2, "95% interval includes 1"),
        (1.1, 1.4, "95% interval entirely above 1"),
        (None, None, "Not reported"),
    ],
)
def test_interval_status_uses_only_mechanical_labels(
    lower: float | None, upper: float | None, expected: str
) -> None:
    assert interval_status(lower, upper) == expected


def test_history_status_volume_and_subgroups_preserve_source_meaning(tmp_path: Path) -> None:
    rows = [
        _signal_row(year=2025, oar_mean=0.8, oar_lower=0.6, oar_upper=0.9),
        _signal_row(year=2024, oar_mean=0.7, oar_lower=0.5, oar_upper=1.0),
        _signal_row(
            year=2025,
            offer_group="low",
            offers=20,
            expected_acceptances=3.5,
            oar_mean=None,
            oar_lower=None,
            oar_upper=None,
        ),
        _signal_row(year=2025, offer_group="medium", offers=30, oar_mean=0.9),
        _signal_row(
            year=2025,
            offer_group="high",
            offers=0,
            expected_acceptances=0.0,
            oar_mean=None,
            oar_lower=None,
            oar_upper=None,
        ),
        _signal_row(year=2025, offer_group="hard-to-place", offers=10, oar_mean=1.2),
    ]
    _write_artifacts(tmp_path, rows, [_panel_row(feature_year=2025, public_eligible=False)])
    artifacts = load_historical_artifacts(tmp_path)

    history = overall_history(artifacts, "ABCD:TX1")
    status = latest_overall_status(artifacts, "ABCD:TX1")
    volume = latest_volume_context(artifacts, "ABCD:TX1")
    subgroups = latest_subgroup_rows(artifacts, "ABCD:TX1")

    assert [point.cohort_year for point in history] == [2024, 2025]
    assert history[0].publication_display == "July 2025"
    assert len(artifacts.panel_sha256) == 64
    assert history[1].publication_display == "July 7, 2026"
    assert status.label == "95% interval entirely below 1"
    assert volume.offers == 100
    assert volume.expected_acceptances == 12.5
    assert [row.label for row in subgroups] == [
        "Low KDRI",
        "Medium KDRI",
        "High KDRI",
        "Hard-to-place",
    ]
    assert subgroups[0].oar_display == "Not reported"
    assert subgroups[2].offers_display == "0"
    assert subgroups[2].oar_display == "Not reported"


def test_forecast_eligibility_is_read_from_latest_panel_row(tmp_path: Path) -> None:
    _write_artifacts(
        tmp_path,
        [_signal_row(year=2024), _signal_row(year=2025)],
        [
            _panel_row(feature_year=2024, public_eligible=True),
            _panel_row(feature_year=2025, public_eligible=False),
        ],
    )

    eligibility = latest_public_forecast_eligibility(
        load_historical_artifacts(tmp_path), "ABCD:TX1"
    )

    assert eligibility.feature_cohort_year == 2025
    assert eligibility.target_cohort_year == 2026
    assert eligibility.eligible is False


def test_persistence_projection_reads_latest_trusted_panel_state(tmp_path: Path) -> None:
    latest_panel = _panel_row(feature_year=2025, public_eligible=True)
    latest_panel["current_log_overall_oar"] = -0.10536051565782628
    latest_panel["prediction_as_of"] = "2026-07"
    latest_panel["prediction_as_of_precision"] = "month"
    latest_panel["elapsed_target_cohort_fraction_at_prediction"] = 0.515
    _write_artifacts(
        tmp_path,
        [
            _signal_row(year=2024),
            _signal_row(year=2025, oar_mean=0.9),
            _signal_row(year=2024, offer_group="low", oar_mean=0.8),
            _signal_row(year=2025, offer_group="low", oar_mean=None),
        ],
        [
            _panel_row(feature_year=2024, public_eligible=False),
            latest_panel,
        ],
    )
    artifacts = load_historical_artifacts(tmp_path)

    projection = latest_persistence_projection(artifacts, "ABCD:TX1")
    subgroups = subgroup_history(artifacts, "ABCD:TX1")

    assert projection.eligible is True
    assert projection.feature_cohort_year == 2025
    assert projection.target_cohort_year == 2026
    assert projection.prediction_as_of_display == "July 2026"
    assert projection.elapsed_target_cohort_fraction == pytest.approx(0.515)
    assert projection.point_oar == pytest.approx(0.9)
    assert [(row.cohort_year, row.offer_group, row.oar_mean) for row in subgroups] == [
        (2024, "low", 0.8),
        (2025, "low", None),
    ]


def test_ineligible_projection_is_unavailable(tmp_path: Path) -> None:
    _write_artifacts(
        tmp_path,
        [_signal_row(year=2025)],
        [_panel_row(feature_year=2025, public_eligible=False)],
    )

    projection = latest_persistence_projection(load_historical_artifacts(tmp_path), "ABCD:TX1")

    assert projection.eligible is False
    assert projection.point_oar is None
