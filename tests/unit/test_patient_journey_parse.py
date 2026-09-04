from __future__ import annotations

import math
from dataclasses import replace
from datetime import date, datetime

import pytest

from kasm.config import SourceRecord
from kasm.data.parse import WorkbookSheet
from kasm.patient_journey.ledger import (
    MetricMethodology,
    ReleaseMethodology,
    SafetyMethodology,
    SheetContract,
)
from kasm.patient_journey.parse import PatientJourneyParseError, parse_patient_journey_workbook


def _source() -> SourceRecord:
    return SourceRecord(
        release_code="2505",
        release_label="July 2025",
        published_value="2025-07-08",
        published_precision="day",
        cohort_year=2024,
        expected_rows=230,
        expected_columns=143,
        sheet_name="Table B11 & Figures B10-B14",
        transport="xls",
        url="https://example.test/2505.xls",
        download_bytes=100,
        download_sha256="a" * 64,
    )


def _metric(
    family: str,
    name: str,
    fields: tuple[str, ...],
    *,
    start: date,
    end: date,
    follow_up_end: date,
) -> MetricMethodology:
    return MetricMethodology(
        family=family,  # type: ignore[arg-type]
        sheet=SheetContract(
            name=name,
            expected_rows=1,
            expected_columns=len(fields),
            required_fields=fields,
        ),
        measurement_start=start,
        measurement_end=end,
        follow_up_end=follow_up_end,
        timing_source_url="https://example.test/timing",
        definition_notes=("Fixture definition.",),
        method_changes=(),
        policy_context=(),
    )


def _methodology() -> ReleaseMethodology:
    return ReleaseMethodology(
        release_code="2505",
        published_value="2025-07-08",
        published_precision="day",
        source_url="https://example.test/2505.xls",
        source_sha256="a" * 64,
        identity_sheet=SheetContract(
            name="Tiers",
            expected_rows=1,
            expected_columns=7,
            required_fields=(
                "ENTIRE_NAME",
                "PRIMARY_CITY",
                "PRIMARY_STATE",
                "PRIMARY_ZIP",
                "CTR_CD",
                "CTR_TY",
                "ORGAN",
            ),
        ),
        metrics=(
            _metric(
                "patient_outcome",
                "Table B7",
                (
                    "ENTIRE_NAME",
                    "CTR_CD",
                    "CTR_TY",
                    "RELEASE_DATE",
                    "ORG",
                    "SAL_N_C",
                    "SAL_TOTFTX_C18",
                ),
                start=date(2022, 7, 1),
                end=date(2023, 6, 30),
                follow_up_end=date(2024, 12, 30),
            ),
            _metric(
                "transplant_rate",
                "Access",
                (
                    "center",
                    "RELEASE_DATE",
                    "wl_org",
                    "begdate",
                    "enddate",
                    "TMR_TxPy_c",
                    "TX_RR",
                ),
                start=date(2023, 1, 1),
                end=date(2024, 12, 31),
                follow_up_end=date(2024, 12, 31),
            ),
            _metric(
                "wait_time",
                "Table B10",
                ("ENTIRE_NAME", "CTR_CD", "CTR_TY", "RELEASE_DATE", "ORG", "TTT_25_C"),
                start=date(2019, 1, 1),
                end=date(2024, 6, 30),
                follow_up_end=date(2025, 4, 30),
            ),
        ),
    )


def _sheet(name: str, headers: tuple[str, ...], row: tuple[object, ...]) -> WorkbookSheet:
    descriptions = tuple(
        "Center Code"
        if header == "CTR_CD"
        else "Center Type"
        if header == "CTR_TY"
        else "Center Name"
        if header == "center"
        else f"Description {header}"
        for header in headers
    )
    return WorkbookSheet(
        name=name,
        rows=(headers, descriptions, row),
        column_count=len(headers),
    )


def _sheets(
    *,
    center_name: object = "Program ABCD",
    access_center: str = "ABCDTX1",
    target_percent: object = 37.5,
    wait_time: object = "8.4",
    access_start: object = datetime(2023, 1, 1),
    access_end: object = datetime(2024, 12, 31),
) -> tuple[WorkbookSheet, ...]:
    identity_fields = _methodology().identity_sheet.required_fields
    outcome_fields = _methodology().metric("patient_outcome").sheet.required_fields
    access_fields = _methodology().metric("transplant_rate").sheet.required_fields
    wait_fields = _methodology().metric("wait_time").sheet.required_fields
    release_date = datetime(2025, 7, 8, 19)
    return (
        _sheet(
            "Tiers",
            identity_fields,
            (center_name, "Boston", "MA", "01234", "ABCD", "TX1", "Kidney"),
        ),
        _sheet(
            "Table B7",
            outcome_fields,
            ("Stale source label", "ABCD", "TX1", release_date, "KI", 40, target_percent),
        ),
        _sheet(
            "Access",
            access_fields,
            (access_center, release_date, "KI", access_start, access_end, 123.5, "1.12"),
        ),
        _sheet(
            "Table B10",
            wait_fields,
            ("Another stale label", "ABCD", "TX1", release_date, "KI", wait_time),
        ),
    )


def test_parser_builds_observed_target_and_reconciles_combined_identity() -> None:
    parsed = parse_patient_journey_workbook(_source(), _methodology(), _sheets())

    assert parsed.identities[0].program_key == "ABCD:TX1"
    assert parsed.identities[0].center_name == "Program ABCD"
    outcome = parsed.outcomes[0]
    assert outcome.program_key == "ABCD:TX1"
    assert outcome.target_n == 40
    assert outcome.published_percent == 37.5
    assert outcome.target_proportion == 0.375
    assert outcome.reconstructed_successes == 15
    assert outcome.target_logit == pytest.approx(math.log(15.5 / 25.5))
    assert outcome.listing_cohort_start == date(2022, 7, 1)
    assert outcome.follow_up_end == date(2024, 12, 30)
    assert parsed.transplant_rates[0].program_key == "ABCD:TX1"
    assert parsed.transplant_rates[0].transplant_rate_ratio == 1.12
    assert parsed.transplant_rates[0].person_years == 123.5
    assert parsed.wait_times[0].months_25th_percentile == 8.4
    assert parsed.wait_times[0].raw_value == "8.4"


def test_missing_directory_name_uses_nonidentifying_display_fallback() -> None:
    parsed = parse_patient_journey_workbook(_source(), _methodology(), _sheets(center_name=None))

    assert parsed.identities[0].center_name == "Program ABCD"


@pytest.mark.parametrize("suppressed", [">72", "Not Observed", "-"])
def test_suppressed_wait_time_stays_null_and_preserves_source_text(suppressed: str) -> None:
    parsed = parse_patient_journey_workbook(
        _source(), _methodology(), _sheets(wait_time=suppressed)
    )

    assert parsed.wait_times[0].months_25th_percentile is None
    assert parsed.wait_times[0].raw_value == suppressed


def test_combined_access_identity_must_match_same_release_registry() -> None:
    with pytest.raises(PatientJourneyParseError, match="identity registry"):
        parse_patient_journey_workbook(_source(), _methodology(), _sheets(access_center="WXYZTX1"))


@pytest.mark.parametrize("value", [-0.1, 100.1, float("nan")])
def test_target_percentage_must_be_finite_and_bounded(value: float) -> None:
    with pytest.raises(PatientJourneyParseError, match="SAL_TOTFTX_C18"):
        parse_patient_journey_workbook(_source(), _methodology(), _sheets(target_percent=value))


def test_parser_rejects_sheet_shape_drift() -> None:
    methodology = _methodology()
    outcome = methodology.metric("patient_outcome")
    changed = replace(
        methodology,
        metrics=tuple(
            replace(
                metric,
                sheet=replace(metric.sheet, expected_columns=metric.sheet.expected_columns + 1),
            )
            if metric.family == outcome.family
            else metric
            for metric in methodology.metrics
        ),
    )

    with pytest.raises(PatientJourneyParseError, match="column count changed"):
        parse_patient_journey_workbook(_source(), changed, _sheets())


def test_access_dates_accept_excel_serials_and_normalize_to_ledger() -> None:
    parsed = parse_patient_journey_workbook(
        _source(),
        _methodology(),
        _sheets(access_start=44927.75, access_end=45657.75),
    )

    assert parsed.transplant_rates[0].measurement_start == date(2023, 1, 1)
    assert parsed.transplant_rates[0].measurement_end == date(2024, 12, 31)


def _waiting_list_safety() -> SafetyMethodology:
    fields = (
        "center",
        "RELEASE_DATE",
        "wl_org",
        "begdate",
        "enddate",
        "TMR_DthPy_c",
        "TMR_DthN_c",
        "TMR_DthR_c",
        "TMR_DthER_c",
        "WLM_RR",
        "WLM_RR_CREDLO",
        "WLM_RR_CREDHI",
    )
    return SafetyMethodology(
        family="waiting_list_mortality",
        sheet=SheetContract(
            name="Safety WLM",
            expected_rows=1,
            expected_columns=len(fields),
            required_fields=fields,
        ),
        measurement_start=date(2023, 1, 1),
        measurement_end=date(2024, 12, 31),
        included_segments=((date(2023, 1, 1), date(2024, 12, 31)),),
        follow_up_end=date(2024, 12, 31),
        timing_source_url="https://example.test/wlm",
        population="kidney_candidates_after_listing",
        event="death_before_transplant_or_removal_for_other_reasons",
        denominator="candidate_person_years",
        direction="lower_ratio_is_better",
        interval_kind="bayesian_credible_interval",
        interval_level=0.95,
        definition_notes=("Published waiting-list mortality ratio.",),
    )


def _safety_sheet(
    *,
    center: str = "ABCDTX1",
    ratio: object = "0.84",
    lower: object = "0.62",
    upper: object = "1.11",
) -> WorkbookSheet:
    metric = _waiting_list_safety()
    release_date = datetime(2025, 7, 8, 19)
    return _sheet(
        metric.sheet.name,
        metric.sheet.required_fields,
        (
            center,
            release_date,
            "KI",
            "01/01/2023",
            "12/31/2024",
            287.5,
            7,
            2.43,
            2.89,
            ratio,
            lower,
            upper,
        ),
    )


def test_parser_keeps_published_safety_ratio_interval_and_denominator_distinct() -> None:
    methodology = replace(_methodology(), safety_metrics=(_waiting_list_safety(),))

    parsed = parse_patient_journey_workbook(_source(), methodology, (*_sheets(), _safety_sheet()))

    safety = parsed.safety_measures[0]
    assert safety.program_key == "ABCD:TX1"
    assert safety.family == "waiting_list_mortality"
    assert safety.denominator_name == "candidate_person_years"
    assert safety.denominator_value == 287.5
    assert safety.observed_events == 7
    assert safety.ratio == 0.84
    assert safety.lower == 0.62
    assert safety.upper == 1.11
    assert safety.direction == "lower_ratio_is_better"
    assert safety.included_segments == ((date(2023, 1, 1), date(2024, 12, 31)),)


def test_parser_rejects_partially_reported_safety_interval() -> None:
    methodology = replace(_methodology(), safety_metrics=(_waiting_list_safety(),))

    with pytest.raises(PatientJourneyParseError, match="jointly reported"):
        parse_patient_journey_workbook(
            _source(),
            methodology,
            (*_sheets(), _safety_sheet(lower=None)),
        )


def test_safety_roster_can_include_program_absent_from_same_release_directory() -> None:
    methodology = replace(_methodology(), safety_metrics=(_waiting_list_safety(),))

    parsed = parse_patient_journey_workbook(
        _source(),
        methodology,
        (*_sheets(), _safety_sheet(center="WXYZTX1")),
    )

    assert parsed.safety_measures[0].program_key == "WXYZ:TX1"
