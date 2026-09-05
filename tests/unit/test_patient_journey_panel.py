from __future__ import annotations

import json
import math
from dataclasses import replace
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from kasm.config import DataSourceManifest, SourceRecord, load_data_source_manifest
from kasm.data.parse import ParsedRelease, ProgramSignal
from kasm.patient_journey.artifacts import (
    PatientJourneyArtifactError,
    PatientJourneyArtifactResult,
    PatientJourneyBuildContext,
    build_cached_patient_journey_artifacts,
    validate_patient_journey_artifacts,
    write_patient_journey_artifacts,
)
from kasm.patient_journey.config import (
    PatientJourneyConfig,
    PatientJourneyConfigError,
    PatientJourneyEligibility,
    PatientJourneyOutputPaths,
    PatientJourneyPair,
    PatientJourneyTemporalDesign,
    load_patient_journey_config,
)
from kasm.patient_journey.ledger import (
    MethodologyLedger,
    MethodologyLedgerError,
    MetricMethodology,
    ReleaseMethodology,
    SafetyMethodology,
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
    PublishedSafetyMeasure,
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
        expected_rows=200,
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
    safety_families = {
        "1905": ("waiting_list_mortality",),
        "2205": (
            "waiting_list_mortality",
            "mortality_after_listing",
            "graft_failure_90_day",
            "graft_failure_1_year_conditional",
        ),
    }.get(source.release_code, ())
    safety_metrics = tuple(
        SafetyMethodology(
            family=family,  # type: ignore[arg-type]
            sheet=SheetContract(
                name=family,
                expected_rows=5,
                expected_columns=12,
                required_fields=("field",),
            ),
            measurement_start=date(source.cohort_year - 1, 1, 1),
            measurement_end=feature_end,
            included_segments=((date(source.cohort_year - 1, 1, 1), feature_end),),
            follow_up_end=feature_end,
            timing_source_url="https://example.test/safety-timing",
            population="fixture_kidney_population",
            event="fixture_event",
            denominator=(
                "adult_recipients_with_functioning_graft_at_day_90"
                if family == "graft_failure_1_year_conditional"
                else "candidate_person_years"
                if family == "waiting_list_mortality"
                else "listed_candidate_person_years"
                if family == "mortality_after_listing"
                else "adult_kidney_transplants"
            ),
            direction="lower_ratio_is_better",
            interval_kind="bayesian_credible_interval",
            interval_level=0.95,
            definition_notes=("Fixture safety definition.",),
        )
        for family in safety_families
    )
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
        safety_metrics=safety_metrics,
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
        model_design=load_patient_journey_config(
            PROJECT_ROOT / "configs" / "patient_journey_v2" / "experiment.yaml",
            repository_root=PROJECT_ROOT,
        ).model_design,
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
    assert panel.pair_summaries[0].target_only_program_keys == ("IJKL:TX1",)
    assert panel.pair_summaries[0].target_program_keys == (
        "ABCD:TX1",
        "BCD1:TX1",
        "BCD2:TX1",
        "BCD3:TX1",
        "IJKL:TX1",
    )
    assert panel.pair_summaries[0].available_cohort_target_successes == 16
    assert panel.pair_summaries[0].available_cohort_target_n == 40
    history = {
        evidence.program_key: evidence for evidence in panel.pair_summaries[0].row_history_evidence
    }
    assert history["ABCD:TX1"].release_codes == ("1808", "1905")
    assert history["ABCD:TX1"].target_proportions == (0.3, 0.4)
    assert history["ABCD:TX1"].earliest_identity_release_code == "1808"


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

    assert row.center_name == "Program ABCD"
    assert row.state == "MA"
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


def test_waiting_list_safety_uses_feature_release_only_with_missing_flags() -> None:
    config, ledger, sources, patient_releases, acceptance = _fixture()
    feature_source = sources[1]
    safety_method = SafetyMethodology(
        family="waiting_list_mortality",
        sheet=SheetContract(
            name="waiting_list_mortality",
            expected_rows=1,
            expected_columns=12,
            required_fields=("field",),
        ),
        measurement_start=date(2017, 1, 1),
        measurement_end=date(2018, 12, 31),
        included_segments=((date(2017, 1, 1), date(2018, 12, 31)),),
        follow_up_end=date(2018, 12, 31),
        timing_source_url="https://example.test/wlm",
        population="kidney_candidates_after_listing",
        event="death_before_transplant_or_removal_for_other_reasons",
        denominator="candidate_person_years",
        direction="lower_ratio_is_better",
        interval_kind="bayesian_credible_interval",
        interval_level=0.95,
        definition_notes=("Fixture waiting-list mortality.",),
    )
    changed_methods = (
        ledger.releases[0],
        replace(ledger.releases[1], safety_metrics=(safety_method,)),
        ledger.releases[2],
    )
    safety = PublishedSafetyMeasure(
        program_key="ABCD:TX1",
        release_code="1905",
        published_value=feature_source.published_value,
        published_precision=feature_source.published_precision,
        family="waiting_list_mortality",
        measurement_start=safety_method.measurement_start,
        measurement_end=safety_method.measurement_end,
        included_segments=safety_method.included_segments,
        follow_up_end=safety_method.follow_up_end,
        population=safety_method.population,
        event=safety_method.event,
        denominator_name=safety_method.denominator,
        denominator_value=125.5,
        population_count=None,
        observed_events=4,
        expected_events=None,
        observed_rate=3.2,
        expected_rate=4.0,
        ratio=0.8,
        lower=0.6,
        upper=1.05,
        direction=safety_method.direction,
        interval_kind=safety_method.interval_kind,
        interval_level=safety_method.interval_level,
        source_url=feature_source.url,
        source_sha256=feature_source.download_sha256,
    )
    changed_releases = (
        patient_releases[0],
        replace(patient_releases[1], safety_measures=(safety,)),
        patient_releases[2],
    )

    panel = build_patient_journey_panel(
        patient_releases=changed_releases,
        acceptance_releases=acceptance,
        config=config,
        ledger=replace(ledger, releases=changed_methods),
        sources=sources,
    )
    rows = {row.program_key: row for row in panel.rows}

    assert rows["ABCD:TX1"].waiting_list_mortality_ratio == 0.8
    assert rows["ABCD:TX1"].waiting_list_mortality_interval_log_width == pytest.approx(
        math.log(1.05) - math.log(0.6)
    )
    assert rows["ABCD:TX1"].missing_waiting_list_mortality_ratio is False
    assert rows["ABCD:TX1"].missing_waiting_list_mortality_interval is False
    assert rows["BCD1:TX1"].waiting_list_mortality_ratio is None
    assert rows["BCD1:TX1"].missing_waiting_list_mortality_ratio is True
    assert rows["BCD1:TX1"].missing_waiting_list_mortality_interval is True


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


def _artifact_manifest(sources: tuple[SourceRecord, ...]) -> DataSourceManifest:
    return DataSourceManifest(
        schema_version=2,
        sources=sources,
        required_machine_columns=("ENTIRE_NAME",),
        optional_recent_machine_columns=(),
    )


def _sheet_config(sheet: SheetContract) -> dict[str, object]:
    return {
        "sheet_name": sheet.name,
        "expected_rows": sheet.expected_rows,
        "expected_columns": sheet.expected_columns,
        "required_fields": list(sheet.required_fields),
    }


def _methodology_config(ledger: MethodologyLedger) -> dict[str, object]:
    releases = []
    for release in ledger.releases:
        metrics = []
        for metric in release.metrics:
            metrics.append(
                {
                    "family": metric.family,
                    **_sheet_config(metric.sheet),
                    "measurement_start": metric.measurement_start.isoformat(),
                    "measurement_end": metric.measurement_end.isoformat(),
                    "follow_up_end": metric.follow_up_end.isoformat(),
                    "timing_source_url": metric.timing_source_url,
                    "definition_notes": list(metric.definition_notes),
                    "method_changes": list(metric.method_changes),
                    "policy_context": list(metric.policy_context),
                }
            )
        safety_metrics = []
        for metric in release.safety_metrics:
            safety_metrics.append(
                {
                    "family": metric.family,
                    **_sheet_config(metric.sheet),
                    "measurement_start": metric.measurement_start.isoformat(),
                    "measurement_end": metric.measurement_end.isoformat(),
                    "included_segments": [
                        {"start": start.isoformat(), "end": end.isoformat()}
                        for start, end in metric.included_segments
                    ],
                    "follow_up_end": metric.follow_up_end.isoformat(),
                    "timing_source_url": metric.timing_source_url,
                    "population": metric.population,
                    "event": metric.event,
                    "denominator": metric.denominator,
                    "direction": metric.direction,
                    "interval_kind": metric.interval_kind,
                    "interval_level": metric.interval_level,
                    "definition_notes": list(metric.definition_notes),
                }
            )
        releases.append(
            {
                "release_code": release.release_code,
                "published_value": release.published_value,
                "published_precision": release.published_precision,
                "source_url": release.source_url,
                "source_sha256": release.source_sha256,
                "identity": _sheet_config(release.identity_sheet),
                "metrics": metrics,
                "safety_metrics": safety_metrics,
            }
        )
    return {
        "schema_version": ledger.schema_version,
        "analysis_id": ledger.analysis_id,
        "source_manifest": ledger.source_manifest,
        "releases": releases,
    }


def _artifact_paths(
    tmp_path: Path,
    *,
    manifest: DataSourceManifest,
    config: PatientJourneyConfig,
    ledger: MethodologyLedger,
) -> dict[str, Path]:
    paths = {
        "source_manifest_path": tmp_path / "configs" / "data_sources.yaml",
        "experiment_config_path": tmp_path / "configs" / "patient_journey_v2" / "experiment.yaml",
        "methodology_path": tmp_path / "configs" / "patient_journey_v2" / "methodology.yaml",
        "lock_path": tmp_path / "uv.lock",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    sources = []
    for source in manifest.sources:
        sources.append(
            {
                "release_code": source.release_code,
                "release_label": source.release_label,
                "release_date_value": source.published_value,
                "release_date_precision": source.published_precision,
                "cohort_year": source.cohort_year,
                "expected_rows": source.expected_rows,
                "expected_columns": source.expected_columns,
                "sheet_name": source.sheet_name,
                "transport": source.transport,
                "url": source.url,
                "download_bytes": source.download_bytes,
                "download_sha256": source.download_sha256,
            }
        )
    paths["source_manifest_path"].write_text(
        yaml.safe_dump(
            {
                "schema_version": manifest.schema_version,
                "required_machine_columns": list(manifest.required_machine_columns),
                "optional_recent_machine_columns": list(manifest.optional_recent_machine_columns),
                "sources": sources,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    processed_relative = config.paths.processed_dir.resolve().relative_to(tmp_path.resolve())
    paths["experiment_config_path"].write_text(
        yaml.safe_dump(
            {
                "schema_version": config.schema_version,
                "analysis_id": config.analysis_id,
                "target": {
                    "column": config.target_column,
                    "canonical_scale": "proportion",
                    "officially_risk_adjusted": False,
                },
                "temporal_design": {
                    "evaluation_mode": config.temporal_design.evaluation_mode,
                    "max_prediction_origin_month_offset": (
                        config.temporal_design.max_prediction_origin_month_offset
                    ),
                    "primary_pairs": [
                        {
                            "feature_release_code": pair.feature_release_code,
                            "target_release_code": pair.target_release_code,
                        }
                        for pair in config.temporal_design.primary_pairs
                    ],
                    "excluded_candidates": [
                        {
                            "feature_release_code": pair.feature_release_code,
                            "target_release_code": pair.target_release_code,
                            "reason": pair.reason,
                        }
                        for pair in config.temporal_design.excluded_candidates
                    ],
                },
                "eligibility": {
                    "primary_min_target_n": config.eligibility.primary_min_target_n,
                    "sensitivity_min_target_n": list(config.eligibility.sensitivity_min_target_n),
                },
                "model_design": yaml.safe_load(
                    (PROJECT_ROOT / "configs" / "patient_journey_v2" / "experiment.yaml").read_text(
                        encoding="utf-8"
                    )
                )["model_design"],
                "paths": {
                    "processed_dir": processed_relative.as_posix(),
                    "modeling_dir": "data/patient_journey_v2/modeling",
                    "release_dir": "artifacts/patient_journey_v2",
                },
                "protected_v1_roots": [
                    "data/processed",
                    "data/modeling",
                    "artifacts/release",
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    paths["methodology_path"].write_text(
        yaml.safe_dump(_methodology_config(ledger), sort_keys=False),
        encoding="utf-8",
    )
    paths["lock_path"].write_text("fixture-lock\n", encoding="utf-8")
    return paths


def _artifact_context() -> PatientJourneyBuildContext:
    return PatientJourneyBuildContext(
        build_timestamp_utc=datetime(2026, 9, 4, 18, 0, tzinfo=UTC),
        git_commit_sha="a" * 40,
        git_worktree_dirty=False,
        python_version="3.12.10",
    )


def _refresh_artifact_manifest(result: PatientJourneyArtifactResult) -> None:
    build_manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    for key, path in (
        ("panel", result.panel_path),
        ("qa_report", result.qa_report_path),
    ):
        record = build_manifest["artifacts"][key]
        record["bytes"] = path.stat().st_size
        record["sha256"] = sha256(path.read_bytes()).hexdigest()
    normalized = {
        name: {"bytes": record["bytes"], "sha256": record["sha256"]}
        for name, record in sorted(build_manifest["artifacts"].items())
    }
    build_manifest["artifact_set_sha256"] = sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    result.manifest_path.write_text(
        json.dumps(build_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_patient_journey_writer_publishes_exact_manifest_bound_artifacts(
    tmp_path: Path,
) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(
        config,
        paths=replace(config.paths, processed_dir=output_dir),
    )
    panel = _build_fixture()
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)

    result = write_patient_journey_artifacts(
        panel,
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )

    assert {path.name for path in output_dir.iterdir()} == {
        "build_manifest.json",
        "patient_journey_panel.parquet",
        "qa_report.json",
        "safety_measures.parquet",
    }
    assert result.panel_rows == 5
    assert result.output_directory == output_dir
    table = pq.read_table(result.panel_path)
    assert table.schema.remove_metadata() == PATIENT_JOURNEY_PANEL_SCHEMA
    assert result.safety_path.exists()
    assert table.schema.metadata is not None
    provenance = json.loads(table.schema.metadata[b"kasm_provenance"])
    assert provenance["analysis_id"] == "kidney_patient_journey_v2"
    assert provenance["model_fitted"] is False
    assert provenance["model_parameters"] == {}
    assert provenance["git_worktree_dirty"] is False
    assert provenance["canonical_build"] is True
    assert provenance["methodology_ledger_identity"] == panel.methodology_ledger_identity
    assert provenance["source_sha256"] == {
        source.release_code: source.download_sha256 for source in sources
    }

    qa = json.loads(result.qa_report_path.read_text(encoding="utf-8"))
    assert qa["row_count"] == 5
    assert qa["pair_summaries"][0]["missing_target_rows"] == 1
    assert qa["pair_summaries"][0]["target_only_additions"] == 1
    assert qa["strict_vintage_folds"][0]["training_pairs"] == []
    assert qa["eligibility_status_counts"] == {
        "eligible": 3,
        "missing_prior_target": 0,
        "missing_target": 1,
        "target_n_below_10": 1,
    }
    assert qa["eligibility_thresholds"] == {
        "primary_min_target_n": 10,
        "sensitivity_min_target_n": [20, 30],
    }

    validated = validate_patient_journey_artifacts(
        output_dir,
        repository_root=tmp_path,
        **input_paths,
    )
    assert validated.artifact_set_sha256 == result.artifact_set_sha256
    assert validated.panel_rows == 5


def test_patient_journey_writer_failure_leaves_prior_bundle_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import kasm.patient_journey.artifacts as artifact_module

    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    panel = _build_fixture()
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    first = write_patient_journey_artifacts(
        panel,
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )
    original = first.manifest_path.read_bytes()

    def fail_json(_path: Path, _value: object) -> None:
        raise OSError("fixture serialization failure")

    monkeypatch.setattr(artifact_module, "_write_json", fail_json)
    with pytest.raises(OSError, match="fixture serialization failure"):
        write_patient_journey_artifacts(
            panel,
            repository_root=tmp_path,
            build_context=_artifact_context(),
            **input_paths,
        )

    assert first.manifest_path.read_bytes() == original
    assert {path.name for path in output_dir.iterdir()} == {
        "build_manifest.json",
        "patient_journey_panel.parquet",
        "qa_report.json",
        "safety_measures.parquet",
    }


def test_patient_journey_publication_failure_rolls_back_prior_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import kasm.patient_journey.artifacts as artifact_module

    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    panel = _build_fixture()
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    first = write_patient_journey_artifacts(
        panel,
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )
    original = first.manifest_path.read_bytes()
    real_replace = artifact_module.os.replace
    failed = False

    def fail_staging_publish(source: Path, destination: Path) -> None:
        nonlocal failed
        source_path = Path(source)
        if source_path.name.startswith(".processed-staging-") and not failed:
            failed = True
            raise OSError("fixture publication failure")
        real_replace(source, destination)

    monkeypatch.setattr(artifact_module.os, "replace", fail_staging_publish)
    with pytest.raises(OSError, match="fixture publication failure"):
        write_patient_journey_artifacts(
            panel,
            repository_root=tmp_path,
            build_context=_artifact_context(),
            **input_paths,
        )

    assert first.manifest_path.read_bytes() == original
    assert not (output_dir.parent / ".processed-backup").exists()


def test_patient_journey_writer_rechecks_protected_v1_destination(tmp_path: Path) -> None:
    config, ledger, sources, _, _ = _fixture()
    protected_output = tmp_path / "data" / "processed" / "patient_journey_v2"
    config = replace(config, paths=replace(config.paths, processed_dir=protected_output))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)

    with pytest.raises(
        (PatientJourneyArtifactError, PatientJourneyConfigError), match="protected v1 root"
    ):
        write_patient_journey_artifacts(
            _build_fixture(),
            repository_root=tmp_path,
            build_context=_artifact_context(),
            **input_paths,
        )

    assert not protected_output.exists()


def test_patient_journey_writer_rejects_unconfigured_same_schema_pair(tmp_path: Path) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    panel = _build_fixture()
    changed = replace(
        panel,
        rows=(
            replace(
                panel.rows[0],
                feature_release_code="1808",
                target_release_code="2105",
            ),
            *panel.rows[1:],
        ),
    )
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)

    with pytest.raises(PatientJourneyArtifactError, match="configured primary pair"):
        write_patient_journey_artifacts(
            changed,
            repository_root=tmp_path,
            build_context=_artifact_context(),
            **input_paths,
        )


def test_patient_journey_writer_recomputes_eligibility_from_values(tmp_path: Path) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    panel = _build_fixture()
    eligible_index = next(
        index for index, row in enumerate(panel.rows) if row.primary_analytic_eligible
    )
    changed_rows = list(panel.rows)
    changed_rows[eligible_index] = replace(
        changed_rows[eligible_index],
        primary_analytic_eligible=False,
    )
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)

    with pytest.raises(PatientJourneyArtifactError, match="eligibility"):
        write_patient_journey_artifacts(
            replace(panel, rows=tuple(changed_rows)),
            repository_root=tmp_path,
            build_context=_artifact_context(),
            **input_paths,
        )


def test_patient_journey_artifact_payload_is_deterministic_with_fixed_build_context(
    tmp_path: Path,
) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    panel = _build_fixture()
    first = write_patient_journey_artifacts(
        panel,
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )
    first_bytes = (
        first.panel_path.read_bytes(),
        first.qa_report_path.read_bytes(),
        first.manifest_path.read_bytes(),
    )
    second = write_patient_journey_artifacts(
        panel,
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )

    assert first_bytes[0] == second.panel_path.read_bytes()
    assert first_bytes[1] == second.qa_report_path.read_bytes()
    assert first_bytes[2] == second.manifest_path.read_bytes()
    assert first.artifact_set_sha256 == second.artifact_set_sha256


def test_patient_journey_artifact_validator_rejects_tampered_hash_or_schema(
    tmp_path: Path,
) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    panel = _build_fixture()
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    result = write_patient_journey_artifacts(
        panel,
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )
    tampered = result.qa_report_path.read_bytes()
    result.qa_report_path.write_bytes(b"[" + tampered[1:])

    with pytest.raises(PatientJourneyArtifactError, match="checksum"):
        validate_patient_journey_artifacts(
            output_dir,
            repository_root=tmp_path,
            **input_paths,
        )


def test_patient_journey_artifact_validator_rejects_rehashed_schema_drift(
    tmp_path: Path,
) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    result = write_patient_journey_artifacts(
        _build_fixture(),
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )
    table = pq.read_table(result.panel_path).drop(["target_logit"])
    pq.write_table(table, result.panel_path)
    build_manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    panel_record = build_manifest["artifacts"]["panel"]
    panel_record["bytes"] = result.panel_path.stat().st_size
    panel_record["sha256"] = sha256(result.panel_path.read_bytes()).hexdigest()
    normalized = {
        name: {"bytes": record["bytes"], "sha256": record["sha256"]}
        for name, record in sorted(build_manifest["artifacts"].items())
    }
    build_manifest["artifact_set_sha256"] = sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    result.manifest_path.write_text(
        json.dumps(build_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(PatientJourneyArtifactError, match="schema"):
        validate_patient_journey_artifacts(
            output_dir,
            repository_root=tmp_path,
            **input_paths,
        )


def test_patient_journey_validator_rejects_rehashed_scientific_mutation(
    tmp_path: Path,
) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    result = write_patient_journey_artifacts(
        _build_fixture(),
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )
    table = pq.read_table(result.panel_path)
    flags = table.column("primary_analytic_eligible").to_pylist()
    changed_index = next(index for index, value in enumerate(flags) if value)
    flags[changed_index] = False
    field_index = table.schema.get_field_index("primary_analytic_eligible")
    table = table.set_column(
        field_index,
        table.schema.field(field_index),
        pa.array(flags, type=pa.bool_()),
    )
    pq.write_table(table, result.panel_path)
    build_manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    panel_record = build_manifest["artifacts"]["panel"]
    panel_record["bytes"] = result.panel_path.stat().st_size
    panel_record["sha256"] = sha256(result.panel_path.read_bytes()).hexdigest()
    normalized = {
        name: {"bytes": record["bytes"], "sha256": record["sha256"]}
        for name, record in sorted(build_manifest["artifacts"].items())
    }
    build_manifest["artifact_set_sha256"] = sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    result.manifest_path.write_text(
        json.dumps(build_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(PatientJourneyArtifactError, match="eligibility"):
        validate_patient_journey_artifacts(
            output_dir,
            repository_root=tmp_path,
            **input_paths,
        )


def test_patient_journey_validator_rejects_rehashed_risk_adjustment_claim(
    tmp_path: Path,
) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    result = write_patient_journey_artifacts(
        _build_fixture(),
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )

    build_manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    build_manifest["provenance"]["target_officially_risk_adjusted"] = True
    qa = json.loads(result.qa_report_path.read_text(encoding="utf-8"))
    qa["provenance"]["target_officially_risk_adjusted"] = True
    result.qa_report_path.write_text(
        json.dumps(qa, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    table = pq.read_table(result.panel_path)
    provenance = json.loads((table.schema.metadata or {})[b"kasm_provenance"])
    provenance["target_officially_risk_adjusted"] = True
    pq.write_table(
        table.replace_schema_metadata(
            {b"kasm_provenance": json.dumps(provenance, sort_keys=True).encode()}
        ),
        result.panel_path,
    )
    result.manifest_path.write_text(
        json.dumps(build_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _refresh_artifact_manifest(result)

    with pytest.raises(PatientJourneyArtifactError, match="risk-adjustment claim"):
        validate_patient_journey_artifacts(
            output_dir,
            repository_root=tmp_path,
            **input_paths,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("transplant_rate_person_years", -1.0),
        ("transplant_rate_ratio", -0.1),
        ("wait_time_months_25th_percentile", -1.0),
        ("acceptance_overall_expected_acceptances", -1.0),
        ("acceptance_overall_oar", -0.1),
    ],
)
def test_patient_journey_writer_rejects_negative_model_features(
    tmp_path: Path,
    field: str,
    value: float,
) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    panel = _build_fixture()
    row_index = next(
        (index for index, row in enumerate(panel.rows) if getattr(row, field) is not None),
        0,
    )
    changed_rows = list(panel.rows)
    changes: dict[str, object] = {field: value}
    if field == "wait_time_months_25th_percentile":
        changes["missing_wait_time"] = False
    changed_rows[row_index] = replace(changed_rows[row_index], **changes)
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)

    with pytest.raises(PatientJourneyArtifactError, match="nonnegative"):
        write_patient_journey_artifacts(
            replace(panel, rows=tuple(changed_rows)),
            repository_root=tmp_path,
            build_context=_artifact_context(),
            **input_paths,
        )


def test_patient_journey_writer_requires_reconstructed_target_successes(tmp_path: Path) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    panel = _build_fixture()
    row_index = next(index for index, row in enumerate(panel.rows) if not row.missing_target)
    changed_rows = list(panel.rows)
    changed_rows[row_index] = replace(changed_rows[row_index], target_reconstructed_successes=None)
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)

    with pytest.raises(PatientJourneyArtifactError, match="reconstructed successes"):
        write_patient_journey_artifacts(
            replace(panel, rows=tuple(changed_rows)),
            repository_root=tmp_path,
            build_context=_artifact_context(),
            **input_paths,
        )


def test_patient_journey_writer_rejects_inconsistent_history_fields(tmp_path: Path) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    panel = _build_fixture()
    row_index = next(
        index for index, row in enumerate(panel.rows) if row.historical_target_count > 0
    )
    changed_rows = list(panel.rows)
    changed_rows[row_index] = replace(changed_rows[row_index], historical_target_count=-1)
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)

    with pytest.raises(PatientJourneyArtifactError, match="Historical target"):
        write_patient_journey_artifacts(
            replace(panel, rows=tuple(changed_rows)),
            repository_root=tmp_path,
            build_context=_artifact_context(),
            **input_paths,
        )


def test_patient_journey_writer_recomputes_first_observed_from_history(tmp_path: Path) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    panel = _build_fixture()
    row_index = next(
        index for index, row in enumerate(panel.rows) if row.historical_target_count > 1
    )
    changed_rows = list(panel.rows)
    changed_rows[row_index] = replace(changed_rows[row_index], first_observed_program=True)
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    changed_panel = replace(
        panel,
        rows=tuple(changed_rows),
        pair_summaries=(
            replace(
                panel.pair_summaries[0],
                first_observed_rows=panel.pair_summaries[0].first_observed_rows + 1,
            ),
        ),
    )

    with pytest.raises(PatientJourneyArtifactError, match="First-observed status"):
        write_patient_journey_artifacts(
            changed_panel,
            repository_root=tmp_path,
            build_context=_artifact_context(),
            **input_paths,
        )


def test_patient_journey_writer_recomputes_multi_release_history_mean(tmp_path: Path) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    panel = _build_fixture()
    row_index = next(
        index for index, row in enumerate(panel.rows) if row.historical_target_count > 1
    )
    changed_rows = list(panel.rows)
    changed_rows[row_index] = replace(
        changed_rows[row_index], historical_mean_target_proportion=0.99
    )
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)

    with pytest.raises(PatientJourneyArtifactError, match="historical target mean"):
        write_patient_journey_artifacts(
            replace(panel, rows=tuple(changed_rows)),
            repository_root=tmp_path,
            build_context=_artifact_context(),
            **input_paths,
        )


def test_patient_journey_writer_recomputes_available_cohort_target(tmp_path: Path) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    panel = _build_fixture()
    changed_rows = tuple(
        replace(row, available_cohort_target_proportion=0.99) for row in panel.rows
    )
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)

    with pytest.raises(PatientJourneyArtifactError, match="cohort target proportion"):
        write_patient_journey_artifacts(
            replace(panel, rows=changed_rows),
            repository_root=tmp_path,
            build_context=_artifact_context(),
            **input_paths,
        )


def test_patient_journey_writer_recomputes_first_observed_without_outcome_history(
    tmp_path: Path,
) -> None:
    config, ledger, sources, patient_releases, acceptance = _fixture()
    earlier = patient_releases[0]
    patient_releases = (
        replace(
            earlier,
            identities=(*earlier.identities, _identity("BCD1:TX1")),
        ),
        *patient_releases[1:],
    )
    panel = build_patient_journey_panel(
        patient_releases=patient_releases,
        acceptance_releases=acceptance,
        config=config,
        ledger=ledger,
        sources=sources,
    )
    row_index = next(index for index, row in enumerate(panel.rows) if row.program_key == "BCD1:TX1")
    assert panel.rows[row_index].historical_target_count == 1
    assert panel.rows[row_index].first_observed_program is False
    changed_rows = list(panel.rows)
    changed_rows[row_index] = replace(changed_rows[row_index], first_observed_program=True)
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    changed_panel = replace(
        panel,
        rows=tuple(changed_rows),
        pair_summaries=(
            replace(
                panel.pair_summaries[0],
                first_observed_rows=panel.pair_summaries[0].first_observed_rows + 1,
            ),
        ),
    )

    with pytest.raises(PatientJourneyArtifactError, match="First-observed status"):
        write_patient_journey_artifacts(
            changed_panel,
            repository_root=tmp_path,
            build_context=_artifact_context(),
            **input_paths,
        )


def test_patient_journey_validator_binds_target_only_program_evidence(tmp_path: Path) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    result = write_patient_journey_artifacts(
        _build_fixture(),
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )
    qa = json.loads(result.qa_report_path.read_text(encoding="utf-8"))
    summary = qa["pair_summaries"][0]
    summary["target_only_additions"] += 1
    summary["target_table_rows"] += 1
    result.qa_report_path.write_text(
        json.dumps(qa, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _refresh_artifact_manifest(result)

    with pytest.raises(PatientJourneyArtifactError, match="target-only program evidence"):
        validate_patient_journey_artifacts(
            output_dir,
            repository_root=tmp_path,
            **input_paths,
        )


def test_patient_journey_validator_binds_target_only_keys_to_target_roster(
    tmp_path: Path,
) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    result = write_patient_journey_artifacts(
        _build_fixture(),
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )
    qa = json.loads(result.qa_report_path.read_text(encoding="utf-8"))
    qa["pair_summaries"][0]["target_only_program_keys"] = ["ZZZZ:TX1"]
    result.qa_report_path.write_text(
        json.dumps(qa, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _refresh_artifact_manifest(result)

    with pytest.raises(PatientJourneyArtifactError, match="target source roster"):
        validate_patient_journey_artifacts(
            output_dir,
            repository_root=tmp_path,
            **input_paths,
        )


def test_patient_journey_inputs_are_loaded_from_recorded_files(tmp_path: Path) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    source_path = input_paths["source_manifest_path"]
    source_path.write_text(
        source_path.read_text(encoding="utf-8").replace(
            sources[0].download_sha256,
            "f" * 64,
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(MethodologyLedgerError, match="source URL and SHA-256 disagree"):
        write_patient_journey_artifacts(
            _build_fixture(),
            repository_root=tmp_path,
            build_context=_artifact_context(),
            **input_paths,
        )


def test_patient_journey_build_rejects_input_changed_during_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import kasm.patient_journey.artifacts as artifact_module

    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    real_load = artifact_module.load_data_source_manifest

    def load_then_change(path: Path) -> DataSourceManifest:
        loaded = real_load(path)
        path.write_text(path.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
        return loaded

    monkeypatch.setattr(artifact_module, "load_data_source_manifest", load_then_change)

    with pytest.raises(PatientJourneyArtifactError, match="changed while"):
        write_patient_journey_artifacts(
            _build_fixture(),
            repository_root=tmp_path,
            build_context=_artifact_context(),
            **input_paths,
        )


def test_patient_journey_writer_recovers_stranded_valid_backup(tmp_path: Path) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    first = write_patient_journey_artifacts(
        _build_fixture(),
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )
    original = first.manifest_path.read_bytes()
    backup = output_dir.parent / ".processed-backup"
    output_dir.replace(backup)
    assert not output_dir.exists()

    recovered = write_patient_journey_artifacts(
        _build_fixture(),
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )

    assert recovered.manifest_path.read_bytes() == original
    assert not backup.exists()


def test_patient_journey_validator_is_limited_to_configured_root(tmp_path: Path) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    write_patient_journey_artifacts(
        _build_fixture(),
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )

    with pytest.raises(PatientJourneyArtifactError, match="configured v2 processed output"):
        validate_patient_journey_artifacts(
            output_dir.parent,
            repository_root=tmp_path,
            **input_paths,
        )


def test_cached_patient_journey_artifact_wrapper_binds_loaded_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import kasm.patient_journey.artifacts as artifact_module

    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    monkeypatch.setattr(
        artifact_module,
        "build_cached_patient_journey_panel",
        lambda **kwargs: _build_fixture(),
    )
    monkeypatch.setattr(
        artifact_module,
        "current_patient_journey_build_context",
        lambda repository_root: _artifact_context(),
    )

    result = build_cached_patient_journey_artifacts(
        repository_root=tmp_path,
        cache_dir=tmp_path / "cache",
        **input_paths,
    )

    assert result.panel_rows == 5
    assert result.output_directory == output_dir


def test_cached_patient_journey_artifact_wrapper_rejects_snapshot_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import kasm.patient_journey.artifacts as artifact_module

    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)

    def build_then_change(**kwargs: object):  # type: ignore[no-untyped-def]
        input_paths["lock_path"].write_text("changed-lock\n", encoding="utf-8")
        return _build_fixture()

    monkeypatch.setattr(
        artifact_module,
        "build_cached_patient_journey_panel",
        build_then_change,
    )
    monkeypatch.setattr(
        artifact_module,
        "current_patient_journey_build_context",
        lambda repository_root: _artifact_context(),
    )

    with pytest.raises(PatientJourneyArtifactError, match="changed during panel construction"):
        build_cached_patient_journey_artifacts(
            repository_root=tmp_path,
            cache_dir=tmp_path / "cache",
            **input_paths,
        )


def test_patient_journey_artifact_validator_rejects_unexpected_file(tmp_path: Path) -> None:
    config, ledger, sources, _, _ = _fixture()
    output_dir = tmp_path / "data" / "patient_journey_v2" / "processed"
    config = replace(config, paths=replace(config.paths, processed_dir=output_dir))
    manifest = _artifact_manifest(sources)
    input_paths = _artifact_paths(tmp_path, manifest=manifest, config=config, ledger=ledger)
    write_patient_journey_artifacts(
        _build_fixture(),
        repository_root=tmp_path,
        build_context=_artifact_context(),
        **input_paths,
    )
    (output_dir / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")

    with pytest.raises(PatientJourneyArtifactError, match="file set"):
        validate_patient_journey_artifacts(
            output_dir,
            repository_root=tmp_path,
            **input_paths,
        )


def test_git_provenance_failure_is_actionable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import kasm.patient_journey.artifacts as artifact_module

    def fail_git(*args: object, **kwargs: object) -> object:
        raise artifact_module.subprocess.TimeoutExpired("git", 10)

    monkeypatch.setattr(artifact_module.subprocess, "run", fail_git)

    with pytest.raises(PatientJourneyArtifactError, match="Git provenance"):
        artifact_module.current_patient_journey_build_context(tmp_path)
