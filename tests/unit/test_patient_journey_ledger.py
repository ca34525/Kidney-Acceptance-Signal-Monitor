from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from kasm.config import DataSourceManifest, SourceRecord, load_data_source_manifest
from kasm.patient_journey.ledger import (
    MethodologyLedgerError,
    load_methodology_ledger,
)

PROJECT_ROOT = Path(__file__).parents[2]


def _source(release_code: str = "fixture") -> SourceRecord:
    return SourceRecord(
        release_code=release_code,
        release_label="Fixture",
        published_value="2025-07-08",
        published_precision="day",
        cohort_year=2024,
        expected_rows=230,
        expected_columns=143,
        sheet_name="Table B11 & Figures B10-B14",
        transport="xls",
        url=f"https://example.test/{release_code}.xls",
        download_bytes=100,
        download_sha256="a" * 64,
    )


def _ledger_text(*, release_code: str = "fixture", published_value: str = "2025-07-08") -> str:
    return f"""
schema_version: 1
analysis_id: kidney_patient_journey_v2
source_manifest: configs/data_sources.yaml
releases:
  - release_code: {release_code}
    published_value: {published_value}
    published_precision: day
    source_url: https://example.test/{release_code}.xls
    source_sha256: {"a" * 64}
    identity:
      sheet_name: Tiers
      expected_rows: 1
      expected_columns: 7
      required_fields:
        [ENTIRE_NAME, PRIMARY_CITY, PRIMARY_STATE, PRIMARY_ZIP, CTR_CD, CTR_TY, ORGAN]
    metrics:
      - family: patient_outcome
        sheet_name: Table B7
        expected_rows: 1
        expected_columns: 7
        required_fields: [ENTIRE_NAME, CTR_CD, CTR_TY, RELEASE_DATE, ORG, SAL_N_C, SAL_TOTFTX_C18]
        measurement_start: 2022-07-01
        measurement_end: 2023-06-30
        follow_up_end: 2024-12-30
        timing_source_url: https://example.test/outcome
        definition_notes: [Observed percentage at 18 months.]
        method_changes: []
        policy_context: []
      - family: transplant_rate
        sheet_name: Access
        expected_rows: 1
        expected_columns: 7
        required_fields: [center, RELEASE_DATE, wl_org, begdate, enddate, TMR_TxPy_c, TX_RR]
        measurement_start: 2023-01-01
        measurement_end: 2024-12-31
        follow_up_end: 2024-12-31
        timing_source_url: https://example.test/access
        definition_notes: [Published access context.]
        method_changes: []
        policy_context: []
      - family: wait_time
        sheet_name: Table B10
        expected_rows: 1
        expected_columns: 6
        required_fields: [ENTIRE_NAME, CTR_CD, CTR_TY, RELEASE_DATE, ORG, TTT_25_C]
        measurement_start: 2019-01-01
        measurement_end: 2024-06-30
        follow_up_end: 2025-04-30
        timing_source_url: https://example.test/wait-time
        definition_notes: [Published 25th percentile in months.]
        method_changes: []
        policy_context: []
""".strip()


def test_project_ledger_covers_manifest_and_exposes_latest_cohort_overlap() -> None:
    manifest = load_data_source_manifest(PROJECT_ROOT / "configs" / "data_sources.yaml")
    ledger = load_methodology_ledger(
        PROJECT_ROOT / "configs" / "patient_journey_v2" / "methodology.yaml",
        manifest=manifest,
    )

    assert tuple(release.release_code for release in ledger.releases) == tuple(
        source.release_code for source in manifest.sources
    )
    assert ledger.release("1808").metric("patient_outcome").sheet.name == "Table B6"
    assert ledger.release("2205").metric("patient_outcome").sheet.name == "Table B7"
    assert ledger.release("1808").metric("wait_time").sheet.name == "Table B9"
    assert ledger.release("2205").metric("wait_time").sheet.name == "Table B10"
    assert "TX_RR" not in ledger.release("1808").metric("transplant_rate").sheet.required_fields
    assert ledger.overlapping_outcome_cohorts() == (("2505", "2605"),)


def test_project_ledger_records_separately_timed_safety_families() -> None:
    manifest = load_data_source_manifest(PROJECT_ROOT / "configs" / "data_sources.yaml")
    ledger = load_methodology_ledger(
        PROJECT_ROOT / "configs" / "patient_journey_v2" / "methodology.yaml",
        manifest=manifest,
    )

    assert ledger.release("1808").safety_metrics == ()
    waiting_list = ledger.release("1905").safety_metric("waiting_list_mortality")
    assert waiting_list.sheet.name == "Tbls B4-B5 & Fig B1-B6 - All"
    assert waiting_list.denominator == "candidate_person_years"
    assert waiting_list.direction == "lower_ratio_is_better"
    assert waiting_list.interval_kind == "bayesian_credible_interval"
    assert waiting_list.included_segments == ((date(2017, 1, 1), date(2018, 12, 31)),)

    assert ledger.release("2006").safety_metrics[0].family == "waiting_list_mortality"
    assert {metric.family for metric in ledger.release("2105").safety_metrics} == {
        "waiting_list_mortality",
        "mortality_after_listing",
    }
    covid_modified = ledger.release("2105").safety_metric("waiting_list_mortality")
    assert covid_modified.measurement_end == date(2020, 12, 31)
    assert covid_modified.included_segments[-1][1] == date(2020, 3, 12)
    assert {metric.family for metric in ledger.release("2205").safety_metrics} == {
        "waiting_list_mortality",
        "mortality_after_listing",
        "graft_failure_90_day",
        "graft_failure_1_year_conditional",
    }
    graft = ledger.release("2505").safety_metric("graft_failure_1_year_conditional")
    assert graft.denominator == "adult_recipients_with_functioning_graft_at_day_90"
    assert graft.follow_up_end == date(2024, 12, 31)


def test_ledger_rejects_release_omitted_from_manifest(tmp_path: Path) -> None:
    manifest = DataSourceManifest(schema_version=2, sources=(_source(), _source("missing")))
    path = tmp_path / "methodology.yaml"
    path.write_text(_ledger_text(), encoding="utf-8")

    with pytest.raises(MethodologyLedgerError, match="exactly cover manifest releases"):
        load_methodology_ledger(path, manifest=manifest)


def test_ledger_rejects_publication_value_that_disagrees_with_manifest(tmp_path: Path) -> None:
    manifest = DataSourceManifest(schema_version=2, sources=(_source(),))
    path = tmp_path / "methodology.yaml"
    path.write_text(_ledger_text(published_value="2025-07-09"), encoding="utf-8")

    with pytest.raises(MethodologyLedgerError, match="publication value and precision"):
        load_methodology_ledger(path, manifest=manifest)


def test_ledger_rejects_follow_up_before_measurement_end(tmp_path: Path) -> None:
    manifest = DataSourceManifest(schema_version=2, sources=(_source(),))
    path = tmp_path / "methodology.yaml"
    path.write_text(
        _ledger_text().replace("follow_up_end: 2024-12-30", "follow_up_end: 2023-01-01", 1),
        encoding="utf-8",
    )

    with pytest.raises(MethodologyLedgerError, match="follow_up_end cannot precede"):
        load_methodology_ledger(path, manifest=manifest)


def test_ledger_rejects_duplicate_metric_family(tmp_path: Path) -> None:
    manifest = DataSourceManifest(schema_version=2, sources=(_source(),))
    duplicate = _ledger_text().replace("family: wait_time", "family: transplant_rate")
    path = tmp_path / "methodology.yaml"
    path.write_text(duplicate, encoding="utf-8")

    with pytest.raises(MethodologyLedgerError, match="duplicate metric family"):
        load_methodology_ledger(path, manifest=manifest)


def test_ledger_rejects_manifest_publication_precision_change(tmp_path: Path) -> None:
    source = replace(_source(), published_precision="month", published_value="2025-07")
    manifest = DataSourceManifest(schema_version=2, sources=(source,))
    path = tmp_path / "methodology.yaml"
    path.write_text(_ledger_text(), encoding="utf-8")

    with pytest.raises(MethodologyLedgerError, match="publication value and precision"):
        load_methodology_ledger(path, manifest=manifest)


def test_ledger_rejects_source_hash_that_disagrees_with_manifest(tmp_path: Path) -> None:
    manifest = DataSourceManifest(schema_version=2, sources=(_source(),))
    path = tmp_path / "methodology.yaml"
    path.write_text(_ledger_text().replace("a" * 64, "b" * 64), encoding="utf-8")

    with pytest.raises(MethodologyLedgerError, match="source URL and SHA-256"):
        load_methodology_ledger(path, manifest=manifest)
