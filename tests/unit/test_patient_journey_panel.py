from __future__ import annotations

import math
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from kasm.config import DataSourceManifest, SourceRecord, load_data_source_manifest
from kasm.data.parse import ParsedRelease, ProgramSignal
from kasm.patient_journey.config import (
    PatientJourneyConfig,
    PatientJourneyEligibility,
    PatientJourneyOutputPaths,
    PatientJourneyPair,
    PatientJourneyTemporalDesign,
    load_patient_journey_config,
)
from kasm.patient_journey.ledger import (
    MethodologyLedger,
    MetricMethodology,
    ReleaseMethodology,
    SheetContract,
    load_methodology_ledger,
)
from kasm.patient_journey.panel import (
    PATIENT_JOURNEY_PANEL_SCHEMA,
    PatientJourneyPanelError,
    build_cached_patient_journey_panel,
    build_patient_journey_panel,
    patient_journey_panel_table,
    strict_vintage_folds,
    validate_temporal_design,
)
from kasm.patient_journey.parse import (
    ParsedPatientJourneyRelease,
    PatientJourneyOutcome,
    ProgramIdentity,
    TransplantRate,
    WaitTime,
)

PROJECT_ROOT = Path(__file__).parents[2]


def _source(
    release_code: str,
    published_value: str,
    cohort_year: int,
    *,
    precision: str = "month",
) -> SourceRecord:
    return SourceRecord(
        release_code=release_code,
        release_label=release_code,
        published_value=published_value,
        published_precision=precision,  # type: ignore[arg-type]
        cohort_year=cohort_year,
        expected_rows=5,
        expected_columns=125,
        sheet_name="Acceptance",
        transport="xls",
        url=f"https://example.test/{release_code}.xls",
        download_bytes=100,
        download_sha256=release_code[0] * 64,
    )


def _metric(
    family: str,
    *,
    start: date,
    end: date,
    follow_up_end: date,
) -> MetricMethodology:
    return MetricMethodology(
        family=family,  # type: ignore[arg-type]
        sheet=SheetContract(
            name=family,
            expected_rows=5,
            expected_columns=7,
            required_fields=("field",),
        ),
        measurement_start=start,
        measurement_end=end,
        follow_up_end=follow_up_end,
        timing_source_url="https://example.test/timing",
        definition_notes=("Fixture definition.",),
        method_changes=(),
        policy_context=(),
    )


def _release_method(
    source: SourceRecord,
    *,
    outcome_start: date,
    outcome_end: date,
    outcome_follow_up: date,
) -> ReleaseMethodology:
    feature_end = date(source.cohort_year, 12, 31)
    return ReleaseMethodology(
        release_code=source.release_code,
        published_value=source.published_value,
        published_precision=source.published_precision,
        source_url=source.url,
        source_sha256=source.download_sha256,
        identity_sheet=SheetContract(
            name="Tiers",
            expected_rows=5,
            expected_columns=7,
            required_fields=("field",),
        ),
        metrics=(
            _metric(
                "patient_outcome",
                start=outcome_start,
                end=outcome_end,
                follow_up_end=outcome_follow_up,
            ),
            _metric(
                "transplant_rate",
                start=date(source.cohort_year - 1, 1, 1),
                end=feature_end,
                follow_up_end=feature_end,
            ),
            _metric(
                "wait_time",
                start=date(source.cohort_year - 5, 1, 1),
                end=feature_end,
                follow_up_end=feature_end,
            ),
        ),
    )


def _identity(program_key: str) -> ProgramIdentity:
    center_code, center_type = program_key.split(":")
    return ProgramIdentity(
        program_key=program_key,
        center_code=center_code,
        center_type=center_type,
        center_name=f"Program {center_code}",
        city="Boston",
        state="MA",
        zip_code="01234",
    )


def _outcome(
    source: SourceRecord,
    methodology: ReleaseMethodology,
    program_key: str,
    n: int,
    percent: float,
) -> PatientJourneyOutcome:
    successes = math.floor(n * percent / 100 + 0.5)
    smoothed = (successes + 0.5) / (n + 1)
    return PatientJourneyOutcome(
        program_key=program_key,
        release_code=source.release_code,
        published_value=source.published_value,
        published_precision=source.published_precision,
        listing_cohort_start=methodology.metric("patient_outcome").measurement_start,
        listing_cohort_end=methodology.metric("patient_outcome").measurement_end,
        follow_up_end=methodology.metric("patient_outcome").follow_up_end,
        target_n=n,
        published_percent=percent,
        target_proportion=percent / 100,
        reconstructed_successes=successes,
        target_logit=math.log(smoothed / (1 - smoothed)),
        source_url=source.url,
        source_sha256=source.download_sha256,
    )


def _patient_release(
    source: SourceRecord,
    methodology: ReleaseMethodology,
    identities: tuple[str, ...],
    outcomes: tuple[PatientJourneyOutcome, ...],
    *,
    suppressed_wait_for: str | None = None,
) -> ParsedPatientJourneyRelease:
    first = identities[0]
    return ParsedPatientJourneyRelease(
        release_code=source.release_code,
        identities=tuple(_identity(key) for key in identities),
        outcomes=outcomes,
        transplant_rates=(
            TransplantRate(
                program_key=first,
                release_code=source.release_code,
                measurement_start=methodology.metric("transplant_rate").measurement_start,
                measurement_end=methodology.metric("transplant_rate").measurement_end,
                person_years=120.0,
                transplant_rate_ratio=1.2,
            ),
        ),
        wait_times=(
            WaitTime(
                program_key=first,
                release_code=source.release_code,
                measurement_start=methodology.metric("wait_time").measurement_start,
                measurement_end=methodology.metric("wait_time").measurement_end,
                follow_up_end=methodology.metric("wait_time").follow_up_end,
                months_25th_percentile=(None if first == suppressed_wait_for else 8.0),
                raw_value=(">72" if first == suppressed_wait_for else "8"),
            ),
        ),
    )


def _acceptance_release(
    source: SourceRecord, program_key: str, *, overall_oar: float
) -> ParsedRelease:
    center_code, center_type = program_key.split(":")
    groups = ("overall", "low", "medium", "high", "hard-to-place")
    signals = tuple(
        ProgramSignal(
            program_key=program_key,
            center_code=center_code,
            center_type=center_type,
            center_name=f"Program {center_code}",
            release_code=source.release_code,
            published_value=source.published_value,
            published_precision=source.published_precision,
            cohort_year=source.cohort_year,
            cohort_start=date(source.cohort_year, 1, 1),
            cohort_end=date(source.cohort_year, 12, 31),
            offer_group=group,  # type: ignore[arg-type]
            offers=100,
            acceptances=10,
            expected_acceptances=9.0,
            oar_mean=overall_oar if group == "overall" else 1.0,
            oar_lower=0.8,
            oar_upper=1.4,
            source_url=source.url,
            source_sha256=source.download_sha256,
        )
        for group in groups
    )
    return ParsedRelease(
        release_code=source.release_code,
        cohort_year=source.cohort_year,
        sheet_name="Acceptance",
        source_rows=1,
        source_columns=125,
        signals=signals,
    )


def _fixture() -> tuple[
    PatientJourneyConfig,
    MethodologyLedger,
    tuple[SourceRecord, ...],
    tuple[ParsedPatientJourneyRelease, ...],
    tuple[ParsedRelease, ...],
]:
    earlier = _source("1808", "2018-10", 2017)
    feature = _source("1905", "2019-07", 2018)
    target = _source("2205", "2022-07", 2021)
    methods = (
        _release_method(
            earlier,
            outcome_start=date(2015, 7, 1),
            outcome_end=date(2016, 6, 30),
            outcome_follow_up=date(2017, 12, 30),
        ),
        _release_method(
            feature,
            outcome_start=date(2016, 7, 1),
            outcome_end=date(2017, 6, 30),
            outcome_follow_up=date(2018, 12, 30),
        ),
        _release_method(
            target,
            outcome_start=date(2019, 7, 1),
            outcome_end=date(2020, 6, 30),
            outcome_follow_up=date(2021, 12, 30),
        ),
    )
    ledger = MethodologyLedger(
        schema_version=1,
        analysis_id="kidney_patient_journey_v2",
        source_manifest="configs/data_sources.yaml",
        releases=methods,
    )
    config = PatientJourneyConfig(
        schema_version=2,
        analysis_id="kidney_patient_journey_v2",
        target_column="SAL_TOTFTX_C18",
        paths=PatientJourneyOutputPaths(Path("processed"), Path("modeling"), Path("release")),
        temporal_design=PatientJourneyTemporalDesign(
            evaluation_mode="strict_vintage",
            max_prediction_origin_month_offset=1,
            primary_pairs=(PatientJourneyPair("1905", "2205"),),
            excluded_candidates=(),
        ),
        eligibility=PatientJourneyEligibility(
            primary_min_target_n=10,
            sensitivity_min_target_n=(20, 30),
        ),
    )
    keys = ("ABCD:TX1", "BCD1:TX1", "BCD2:TX1", "BCD3:TX1", "EFGH:TX1")
    earlier_release = _patient_release(
        earlier,
        methods[0],
        ("ABCD:TX1",),
        (_outcome(earlier, methods[0], "ABCD:TX1", 10, 30.0),),
    )
    feature_outcomes = tuple(
        _outcome(feature, methods[1], key, 10, 40.0) for key in keys if key != "EFGH:TX1"
    )
    feature_release = _patient_release(
        feature,
        methods[1],
        keys,
        feature_outcomes,
        suppressed_wait_for="ABCD:TX1",
    )
    target_keys = (*keys, "IJKL:TX1", "MNOP:TX1")
    target_outcomes = (
        _outcome(target, methods[2], "ABCD:TX1", 10, 50.0),
        _outcome(target, methods[2], "BCD1:TX1", 9, 44.4),
        _outcome(target, methods[2], "BCD2:TX1", 20, 50.0),
        _outcome(target, methods[2], "BCD3:TX1", 30, 50.0),
        _outcome(target, methods[2], "IJKL:TX1", 20, 60.0),
    )
    target_release = _patient_release(target, methods[2], target_keys, target_outcomes)
    acceptance = (
        _acceptance_release(feature, "ABCD:TX1", overall_oar=1.1),
        _acceptance_release(target, "ABCD:TX1", overall_oar=9.9),
    )
    return (
        config,
        ledger,
        (earlier, feature, target),
        (
            earlier_release,
            feature_release,
            target_release,
        ),
        acceptance,
    )


def _build_fixture():  # type: ignore[no-untyped-def]
    config, ledger, sources, patient_releases, acceptance = _fixture()
    return build_patient_journey_panel(
        patient_releases=patient_releases,
        acceptance_releases=acceptance,
        config=config,
        ledger=ledger,
        sources=sources,
    )


def test_primary_target_cohorts_are_pairwise_nonoverlapping() -> None:
    manifest = load_data_source_manifest(PROJECT_ROOT / "configs" / "data_sources.yaml")
    ledger = load_methodology_ledger(
        PROJECT_ROOT / "configs" / "patient_journey_v2" / "methodology.yaml",
        manifest=manifest,
    )
    config = load_patient_journey_config(
        PROJECT_ROOT / "configs" / "patient_journey_v2" / "experiment.yaml",
        repository_root=PROJECT_ROOT,
    )

    validate_temporal_design(config, ledger, manifest.sources)

    overlapping = replace(
        config,
        temporal_design=replace(
            config.temporal_design,
            primary_pairs=(
                *config.temporal_design.primary_pairs,
                PatientJourneyPair("2305", "2605"),
            ),
            max_prediction_origin_month_offset=12,
        ),
    )
    with pytest.raises(PatientJourneyPanelError, match="overlap"):
        validate_temporal_design(overlapping, ledger, manifest.sources)


def test_prediction_origin_offset_rejects_1808_to_2105_without_inventing_a_day() -> None:
    manifest = load_data_source_manifest(PROJECT_ROOT / "configs" / "data_sources.yaml")
    ledger = load_methodology_ledger(
        PROJECT_ROOT / "configs" / "patient_journey_v2" / "methodology.yaml",
        manifest=manifest,
    )
    config = load_patient_journey_config(
        PROJECT_ROOT / "configs" / "patient_journey_v2" / "experiment.yaml",
        repository_root=PROJECT_ROOT,
    )
    prohibited = replace(
        config,
        temporal_design=replace(
            config.temporal_design,
            primary_pairs=(PatientJourneyPair("1808", "2105"),),
            excluded_candidates=tuple(
                pair
                for pair in config.temporal_design.excluded_candidates
                if pair.target_release_code != "2105"
            ),
        ),
    )

    with pytest.raises(PatientJourneyPanelError, match="offset 3 months.*maximum of 1"):
        validate_temporal_design(prohibited, ledger, manifest.sources)


def test_strict_vintage_folds_never_use_unpublished_training_truth() -> None:
    manifest = load_data_source_manifest(PROJECT_ROOT / "configs" / "data_sources.yaml")
    ledger = load_methodology_ledger(
        PROJECT_ROOT / "configs" / "patient_journey_v2" / "methodology.yaml",
        manifest=manifest,
    )
    config = load_patient_journey_config(
        PROJECT_ROOT / "configs" / "patient_journey_v2" / "experiment.yaml",
        repository_root=PROJECT_ROOT,
    )

    folds = strict_vintage_folds(config, ledger)

    assert tuple(len(fold.training_pairs) for fold in folds) == (0, 0, 0, 1)
    assert folds[-1].evaluation_pair == PatientJourneyPair("2205", "2505")
    assert folds[-1].training_pairs == (PatientJourneyPair("1905", "2205"),)


def test_panel_uses_feature_release_universe_and_keeps_missing_target_null() -> None:
    panel = _build_fixture()

    assert tuple(row.program_key for row in panel.rows) == (
        "ABCD:TX1",
        "BCD1:TX1",
        "BCD2:TX1",
        "BCD3:TX1",
        "EFGH:TX1",
    )
    missing = next(row for row in panel.rows if row.program_key == "EFGH:TX1")
    assert missing.target_proportion is None
    assert missing.missing_target is True
    assert missing.primary_analytic_eligible is False
    assert panel.pair_summaries[0].missing_target_rows == 1
    assert panel.pair_summaries[0].target_only_additions == 1


def test_primary_and_sensitivity_threshold_boundaries_are_fixed() -> None:
    rows = {row.program_key: row for row in _build_fixture().rows}

    assert rows["BCD1:TX1"].primary_analytic_eligible is False
    assert rows["ABCD:TX1"].primary_analytic_eligible is True
    assert rows["ABCD:TX1"].sensitivity_n20_eligible is False
    assert rows["BCD2:TX1"].sensitivity_n20_eligible is True
    assert rows["BCD2:TX1"].sensitivity_n30_eligible is False
    assert rows["BCD3:TX1"].sensitivity_n30_eligible is True


def test_history_uses_only_outcomes_public_by_prediction_origin() -> None:
    row = next(row for row in _build_fixture().rows if row.program_key == "ABCD:TX1")

    assert row.prediction_origin_value == "2019-07"
    assert row.prediction_origin_precision == "month"
    assert row.prediction_origin_month_offset_from_target_start == 0
    assert row.prior_target_release_code == "1905"
    assert row.prior_target_proportion == 0.4
    assert row.historical_target_count == 2
    assert row.historical_mean_target_proportion == pytest.approx(0.35)
    assert row.target_proportion == 0.5


def test_suppressed_wait_time_stays_null_with_missing_indicator() -> None:
    row = next(row for row in _build_fixture().rows if row.program_key == "ABCD:TX1")

    assert row.wait_time_months_25th_percentile is None
    assert row.wait_time_raw_value == ">72"
    assert row.missing_wait_time is True


def test_acceptance_join_uses_composite_identity_and_feature_release_only() -> None:
    panel = _build_fixture()
    row = next(row for row in panel.rows if row.program_key == "ABCD:TX1")
    assert row.acceptance_overall_oar == 1.1

    config, ledger, sources, patient_releases, acceptance = _fixture()
    bad = replace(
        acceptance[0],
        signals=(
            replace(
                acceptance[0].signals[0],
                program_key="ABCD:TX2",
                center_type="TX2",
            ),
        ),
    )
    with pytest.raises(PatientJourneyPanelError, match="same-release identity"):
        build_patient_journey_panel(
            patient_releases=patient_releases,
            acceptance_releases=(bad, acceptance[1]),
            config=config,
            ledger=ledger,
            sources=sources,
        )


def test_panel_schema_and_order_are_deterministic() -> None:
    rows = _build_fixture().rows

    first = patient_journey_panel_table(rows)
    second = patient_journey_panel_table(tuple(reversed(rows)))

    assert first.schema == PATIENT_JOURNEY_PANEL_SCHEMA
    assert first.equals(second)
    assert _build_fixture().methodology_ledger_identity.startswith("sha256:")
    assert all(
        row.methodology_ledger_identity == _build_fixture().methodology_ledger_identity
        for row in rows
    )
    with pytest.raises(PatientJourneyPanelError, match="keys must be unique"):
        patient_journey_panel_table((*rows, rows[0]))


def test_patient_row_release_and_timing_metadata_cannot_smuggle_future_history() -> None:
    config, ledger, sources, patient_releases, acceptance = _fixture()
    future_labeled = replace(
        patient_releases[1].outcomes[0],
        release_code="2205",
        published_value="2022-07",
    )
    changed_feature = replace(
        patient_releases[1],
        outcomes=(future_labeled, *patient_releases[1].outcomes[1:]),
    )

    with pytest.raises(PatientJourneyPanelError, match="outcome row release"):
        build_patient_journey_panel(
            patient_releases=(patient_releases[0], changed_feature, patient_releases[2]),
            acceptance_releases=acceptance,
            config=config,
            ledger=ledger,
            sources=sources,
        )


def test_cached_panel_reads_each_verified_source_once(monkeypatch: pytest.MonkeyPatch) -> None:
    config, ledger, sources, patient_releases, acceptance = _fixture()
    patient_by_code = {release.release_code: release for release in patient_releases}
    acceptance_by_code = {
        "1808": _acceptance_release(sources[0], "ABCD:TX1", overall_oar=1.0),
        **{release.release_code: release for release in acceptance},
    }
    loaded: list[str] = []

    def fake_load(source: SourceRecord, cache_dir: Path) -> bytes:
        loaded.append(source.release_code)
        return source.release_code.encode()

    monkeypatch.setattr("kasm.patient_journey.panel.load_workbook_payload", fake_load)
    monkeypatch.setattr("kasm.patient_journey.panel.read_workbook_sheets", lambda payload: ())
    monkeypatch.setattr(
        "kasm.patient_journey.panel.parse_patient_journey_workbook",
        lambda source, methodology, sheets: patient_by_code[source.release_code],
    )
    monkeypatch.setattr(
        "kasm.patient_journey.panel.parse_offer_acceptance_workbook",
        lambda manifest, source, sheets: acceptance_by_code[source.release_code],
    )

    panel = build_cached_patient_journey_panel(
        manifest=DataSourceManifest(schema_version=2, sources=sources),
        ledger=ledger,
        config=config,
        cache_dir=Path("unused"),
    )

    assert loaded == ["1808", "1905", "2205"]
    assert len(panel.rows) == 5
