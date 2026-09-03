from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from math import log
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import kasm.data.build as build_module
from kasm.config import SourceRecord
from kasm.data.build import (
    MODEL_FEATURE_COLUMNS,
    MODEL_PANEL_SCHEMA,
    PROGRAM_SIGNALS_SCHEMA,
    BuildError,
    DirectoryEntry,
    build_model_panel,
    build_qa_report,
    canonical_signals_table,
    join_current_directory,
    model_panel_table,
    parse_current_directory,
    write_data_artifacts,
)
from kasm.data.parse import ProgramSignal, WorkbookSheet


def _source(*, year: int = 2025, release_code: str = "2605") -> SourceRecord:
    return SourceRecord(
        release_code=release_code,
        release_label="Fixture release",
        published_value=f"{year + 1}-07-07",
        published_precision="day",
        cohort_year=year,
        expected_rows=2,
        expected_columns=35,
        sheet_name="Table B11 & Figures B10-B14",
        transport="xls",
        url=f"https://example.test/{release_code}.xls",
        download_bytes=1,
        download_sha256="0" * 64,
    )


def _signal(
    *,
    program_key: str = "ABCD:TX1",
    center_name: str = "Historical name",
    year: int = 2025,
    offer_group: str = "overall",
    offers: int | None = 100,
    acceptances: int | None = 10,
    expected_acceptances: float | None = 12.5,
    oar_mean: float | None = 0.83,
    oar_lower: float | None = 0.65,
    oar_upper: float | None = 1.04,
) -> ProgramSignal:
    center_code, center_type = program_key.split(":")
    return ProgramSignal(
        program_key=program_key,
        center_code=center_code,
        center_type=center_type,
        center_name=center_name,
        release_code=str(year),
        published_value=f"{year + 1}-07-07",
        published_precision="day",
        cohort_year=year,
        cohort_start=date(year, 1, 1),
        cohort_end=date(year, 12, 31),
        offer_group=offer_group,  # type: ignore[arg-type]
        offers=offers,
        acceptances=acceptances,
        expected_acceptances=expected_acceptances,
        oar_mean=oar_mean,
        oar_lower=oar_lower,
        oar_upper=oar_upper,
        source_url=f"https://example.test/{year}.xls",
        source_sha256="0" * 64,
    )


def _tiers_sheet() -> WorkbookSheet:
    headers = (
        "PRIMARY_ZIP",
        "ORGAN",
        "CTR_TY",
        "ENTIRE_NAME",
        "PRIMARY_STATE",
        "CTR_CD",
        "PRIMARY_CITY",
    )
    descriptions = (
        "Primary Zip",
        "Organ",
        "Center Type",
        "Center Name",
        "Primary State",
        "Center Code",
        "Primary City",
    )
    return WorkbookSheet(
        name="Tiers",
        rows=(
            headers,
            descriptions,
            ("01234", "Kidney", "TX1", "Current name", "MA", "ABCD", "Boston"),
            ("99999", "Heart", "TX1", "Other organ", "MA", "WXYZ", "Boston"),
            ("20500", "Kidney", "TX1", "Directory only", "DC", "EFGH", "Washington"),
        ),
        column_count=len(headers),
    )


def test_current_directory_joins_by_composite_key_and_preserves_zip() -> None:
    directory = parse_current_directory(_source(), (_tiers_sheet(),))

    assert directory["ABCD:TX1"].zip == "01234"
    assert "WXYZ:TX1" not in directory

    canonical = join_current_directory(
        (_signal(), _signal(program_key="IJKL:VA1", center_name="Fallback name")), directory
    )

    assert canonical[0].center_name == "Current name"
    assert canonical[0].city == "Boston"
    assert canonical[0].state == "MA"
    assert canonical[0].zip == "01234"
    assert canonical[1].center_name == "Fallback name"
    assert canonical[1].city is None
    assert canonical[1].state is None
    assert canonical[1].zip is None


def _program_year(
    program_key: str,
    year: int,
    *,
    overall_oar: float,
    missing_low: bool = False,
) -> tuple[ProgramSignal, ...]:
    groups = (
        ("overall", 100, overall_oar),
        ("low", 25, None if missing_low else overall_oar + 0.1),
        ("medium", 30, overall_oar + 0.2),
        ("high", 45, overall_oar + 0.3),
        ("hard-to-place", 10, overall_oar + 0.4),
    )
    signals: list[ProgramSignal] = []
    for group, offers, ratio in groups:
        signals.append(
            _signal(
                program_key=program_key,
                year=year,
                offer_group=group,
                offers=offers,
                acceptances=offers // 10,
                expected_acceptances=12.5 if group == "overall" else offers / 8,
                oar_mean=ratio,
                oar_lower=None if ratio is None else ratio * 0.8,
                oar_upper=None if ratio is None else ratio * 1.2,
            )
        )
    return tuple(signals)


def _canonical_panel_fixture() -> tuple[tuple[object, ...], tuple[SourceRecord, ...]]:
    signals = (
        *_program_year("ABCD:TX1", 2022, overall_oar=0.7),
        *_program_year("ABCD:TX1", 2023, overall_oar=0.8),
        *_program_year("EXIT:TX1", 2023, overall_oar=0.6),
        *_program_year("ABCD:TX1", 2024, overall_oar=0.9, missing_low=True),
        *_program_year("NEW1:TX1", 2024, overall_oar=1.1),
        *_program_year("ABCD:TX1", 2025, overall_oar=1.0),
        *_program_year("NEW1:TX1", 2025, overall_oar=1.2),
    )
    canonical = join_current_directory(signals, {})
    sources = tuple(_source(year=year, release_code=str(year)) for year in range(2022, 2026))
    return canonical, sources


def test_annual_transitions_and_features_use_only_adjacent_years() -> None:
    canonical, sources = _canonical_panel_fixture()

    rows = build_model_panel(canonical, sources)
    row = next(
        item for item in rows if item.program_key == "ABCD:TX1" and item.feature_cohort_year == 2024
    )

    assert row.target_cohort_year == 2025
    assert row.current_log_overall_oar == pytest.approx(log(0.9))
    assert row.previous_annual_log_overall_oar == pytest.approx(log(0.8))
    assert row.one_year_change_log_overall_oar == pytest.approx(log(0.9) - log(0.8))
    assert row.target_oar == 1.0
    assert row.target_log_oar == 0.0
    assert row.current_log_low_oar is None
    assert row.missing_current_log_low_oar is True
    assert row.high_offers_share == 0.45
    assert row.hard_to_place_offers_share == 0.1
    assert set(MODEL_FEATURE_COLUMNS).isdisjoint(
        {"center_name", "city", "state", "zip", "target_oar", "target_log_oar"}
    )


def test_program_exit_has_missing_target_not_negative_label() -> None:
    canonical, sources = _canonical_panel_fixture()

    rows = build_model_panel(canonical, sources)
    exited = next(item for item in rows if item.program_key == "EXIT:TX1")

    assert exited.target_cohort_year == 2024
    assert exited.truth_published_value == "2025-07-07"
    assert exited.target_oar is None
    assert exited.target_log_oar is None
    assert exited.analytic_eligible is False


def test_forecast_eligibility_is_explicit_and_withholds_first_observation() -> None:
    canonical, sources = _canonical_panel_fixture()

    rows = build_model_panel(canonical, sources)
    new_2024 = next(
        item for item in rows if item.program_key == "NEW1:TX1" and item.feature_cohort_year == 2024
    )
    new_2025 = next(
        item for item in rows if item.program_key == "NEW1:TX1" and item.feature_cohort_year == 2025
    )

    assert new_2024.first_observed_program is True
    assert new_2024.analytic_eligible is True
    assert new_2024.public_forecast_eligible is False
    assert new_2025.first_observed_program is False
    assert new_2025.analytic_eligible is False
    assert new_2025.public_forecast_eligible is True


def test_month_precision_prediction_origin_never_invents_a_day() -> None:
    canonical, sources = _canonical_panel_fixture()
    month_sources = tuple(
        replace(source, published_value="2025-07", published_precision="month")
        if source.cohort_year == 2024
        else source
        for source in sources
    )

    rows = build_model_panel(canonical, month_sources)
    row = next(
        item for item in rows if item.program_key == "ABCD:TX1" and item.feature_cohort_year == 2024
    )

    assert row.prediction_as_of == "2025-07"
    assert row.prediction_as_of_precision == "month"
    assert row.elapsed_target_cohort_fraction_at_prediction == 0.5


def test_non_calendar_or_overlapping_cohort_is_rejected() -> None:
    canonical, sources = _canonical_panel_fixture()
    invalid = tuple(
        replace(item, cohort_end=date(item.cohort_year + 1, 1, 1))
        if item.program_key == "ABCD:TX1" and item.cohort_year == 2023
        else item
        for item in canonical
    )

    with pytest.raises(BuildError, match="full calendar year"):
        build_model_panel(invalid, sources)


def test_qa_report_reconciles_program_movement_and_missing_subgroups() -> None:
    canonical, sources = _canonical_panel_fixture()
    panel = build_model_panel(canonical, sources)
    directory = {
        "ABCD:TX1": DirectoryEntry("ABCD:TX1", "Current name", "Boston", "MA", "01234"),
        "ONLY:TX1": DirectoryEntry("ONLY:TX1", "Directory only", "Austin", "TX", "78701"),
    }

    report = build_qa_report(canonical, panel, sources, directory)

    transition = next(
        item for item in report["annual_transitions"] if item["feature_cohort_year"] == 2023
    )
    assert transition["target_cohort_year"] == 2024
    assert transition["added_program_keys"] == ["NEW1:TX1"]
    assert transition["closed_program_keys"] == ["EXIT:TX1"]
    assert transition["matched_programs"] == 1
    missing = next(
        item
        for item in report["missing_subgroup_oar"]
        if item["cohort_year"] == 2024 and item["offer_group"] == "low"
    )
    assert missing["missing_rows"] == 1
    assert report["directory"]["directory_only_program_keys"] == ["ONLY:TX1"]
    assert len(report["cohort_date_normalizations"]) == 7


def test_published_ratio_is_authoritative_when_rounding_diagnostic_disagrees() -> None:
    canonical, sources = _canonical_panel_fixture()
    changed = tuple(
        replace(item, oar_mean=9.0, oar_upper=10.0)
        if item.program_key == "ABCD:TX1"
        and item.cohort_year == 2024
        and item.offer_group == "overall"
        else item
        for item in canonical
    )
    panel = build_model_panel(canonical, sources)

    report = build_qa_report(changed, panel, sources, {})

    discrepancy = next(
        item
        for item in report["rounding_discrepancies"]
        if item["program_key"] == "ABCD:TX1"
        and item["cohort_year"] == 2024
        and item["offer_group"] == "overall"
    )
    published = next(
        item
        for item in changed
        if item.program_key == "ABCD:TX1"
        and item.cohort_year == 2024
        and item.offer_group == "overall"
    )
    assert discrepancy["published_oar"] == 9.0
    assert published.oar_mean == 9.0


def test_parquet_tables_have_exact_typed_schemas_and_logical_order() -> None:
    canonical, sources = _canonical_panel_fixture()
    panel = build_model_panel(canonical, sources)

    signal_table = canonical_signals_table(tuple(reversed(canonical)))
    panel_table = model_panel_table(tuple(reversed(panel)))

    assert signal_table.schema == PROGRAM_SIGNALS_SCHEMA
    assert panel_table.schema == MODEL_PANEL_SCHEMA
    assert pa.types.is_dictionary(signal_table.schema.field("offer_group").type)
    assert pa.types.is_dictionary(signal_table.schema.field("published_precision").type)
    assert signal_table.column("cohort_year").to_pylist() == sorted(
        signal_table.column("cohort_year").to_pylist()
    )
    assert panel_table.column("feature_cohort_year").to_pylist() == sorted(
        panel_table.column("feature_cohort_year").to_pylist()
    )


def test_artifact_output_is_logically_deterministic(tmp_path: Path) -> None:
    canonical, sources = _canonical_panel_fixture()
    panel = build_model_panel(canonical, sources)
    qa = build_qa_report(canonical, panel, sources, {})

    first = write_data_artifacts(canonical, panel, qa, tmp_path / "first")
    second = write_data_artifacts(canonical, panel, qa, tmp_path / "second")

    assert pq.read_table(first.program_signals_path).equals(
        pq.read_table(second.program_signals_path)
    )
    assert pq.read_table(first.model_panel_path).equals(pq.read_table(second.model_panel_path))
    assert json.loads(first.qa_report_path.read_text(encoding="utf-8")) == json.loads(
        second.qa_report_path.read_text(encoding="utf-8")
    )
    assert first.program_signal_rows == len(canonical)
    assert first.model_panel_rows == len(panel)


def test_failed_serialization_does_not_publish_partial_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical, sources = _canonical_panel_fixture()
    panel = build_model_panel(canonical, sources)
    output_dir = tmp_path / "processed"

    def fail_qa_write(_report: dict[str, object], _path: Path) -> None:
        raise OSError("fixture serialization failure")

    monkeypatch.setattr(build_module, "_write_qa_json", fail_qa_write)

    with pytest.raises(OSError, match="fixture serialization failure"):
        write_data_artifacts(canonical, panel, {}, output_dir)

    assert not output_dir.exists()
