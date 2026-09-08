"""Programs are chosen at the origin, and later reports never enter earlier fits."""

from dataclasses import replace
from datetime import date

import pytest

from kasm.config import SourceRecord
from kasm.data.parse import ParsedRelease, ProgramSignal
from kasm.patient_journey.ledger import MetricMethodology, ReleaseMethodology, SheetContract
from kasm.patient_journey.parse import ProgramIdentity, TransplantRate, WaitTime
from kasm.patient_journey.receipt_accounting import DECEASED_FIELDS, parse_receipt_values
from kasm.patient_journey.receipt_config import ReceiptError
from kasm.patient_journey.receipt_panel import build_receipt_panel, publication_available
from kasm.patient_journey.receipt_sources import (
    ReceiptOutcome,
    ReceiptRelease,
    ReceiptSources,
    SourcePeriods,
)


def release(
    code: str, year: int, programs: tuple[str, ...] = ("AAAA:TX1", "AAAA:VA")
) -> ReceiptRelease:
    source = SourceRecord(
        code,
        year - 1,
        "xls",
        f"https://example.test/{code}.xls",
        100,
        "a" * 64,
        published_value=f"{year}-07",
        published_precision="month",
    )
    periods = SourcePeriods(
        date(year - 3, 7, 1),
        date(year - 2, 6, 30),
        date(year - 1, 12, 31),
        date(year - 6, 1, 1),
        date(year - 1, 6, 30),
        date(year - 1, 12, 31),
    )
    identities = tuple(
        ProgramIdentity(key, *key.split(":"), key, None, None, None) for key in programs
    )
    values = {field: 0.0 for field in DECEASED_FIELDS}
    values.update(SAL_N_C=100, SAL_CTXFNC_C18=20, SAL_CTXUNK_C18=10)
    outcomes = tuple(ReceiptOutcome(key, parse_receipt_values(values)) for key in programs)
    shape = SheetContract("fixture", 1, 1, ("field",))
    metrics = tuple(
        MetricMethodology(family, shape, start, end, follow_up, source.url, (), (), ())
        for family, start, end, follow_up in (
            (
                "patient_outcome",
                periods.listing_start,
                periods.listing_end,
                periods.outcome_follow_up_bound,
            ),
            (
                "transplant_rate",
                date(year - 2, 1, 1),
                date(year - 1, 12, 31),
                date(year - 1, 12, 31),
            ),
            ("wait_time", periods.wait_start, periods.wait_end, periods.wait_follow_up_end),
        )
    )
    methodology = ReleaseMethodology(
        code, source.published_value, "month", source.url, source.download_sha256, shape, metrics
    )
    return ReceiptRelease(
        source,
        periods,
        identities,
        outcomes,
        (),
        (),
        ParsedRelease(code, year - 1, "fixture", 0, 0, ()),
        methodology,
    )


def sources() -> ReceiptSources:
    releases = (release("1905", 2019), release("2205", 2022), release("2505", 2025))
    pairs = (("1905", "2205"), ("2205", "2505"))
    return ReceiptSources(releases, pairs, ((pairs[1], (pairs[0],)),), {}, "a" * 64)


def test_origin_population_keeps_missing_future_and_separates_types() -> None:
    data = sources()
    future = release("2505", 2025, ("AAAA:TX1", "BBBB:TX1"))
    data = replace(data, releases=(*data.releases[:-1], future))
    panel = build_receipt_panel(data)
    rows = [row for row in panel.rows if row["target_release_code"] == "2505"]
    assert {row["program_key"] for row in rows} == {"AAAA:TX1", "AAAA:VA"}
    missing = next(row for row in rows if row["program_key"] == "AAAA:VA")
    assert missing["target_proportion"] is None
    assert not missing["primary_analytic_eligible"]
    assert "missing_future_report" in missing["eligibility_reasons"]
    assert panel.qa["pairs"]["2205->2505"]["target_only_programs"] == ["BBBB:TX1"]


def test_history_is_origin_available_and_uses_own_n() -> None:
    panel = build_receipt_panel(sources())
    row = next(row for row in panel.rows if row["target_release_code"] == "2505")
    assert row["history_release_codes"] == ["1905", "2205"]
    assert row["prior_target_n"] == 100
    assert row["prior_target_proportion"] == pytest.approx(0.3)
    assert row["missing_transplant_rate_ratio"] is True
    assert row["primary_analytic_eligible"] is True


def test_unpublished_training_outcome_cannot_enter() -> None:
    data = sources()
    illegal = replace(data, folds=((data.pairs[0], (data.pairs[1],)),))
    with pytest.raises(ReceiptError, match="public|training"):
        build_receipt_panel(illegal)


def test_late_predictor_followup_and_overlapping_cohorts_fail() -> None:
    data = sources()
    initial = data.releases[0]
    late = replace(initial, periods=replace(initial.periods, wait_follow_up_end=date(2019, 7, 1)))
    with pytest.raises(ReceiptError, match="before|dates"):
        build_receipt_panel(replace(data, releases=(late, *data.releases[1:])))
    future = replace(data.releases[-1], periods=data.releases[1].periods)
    with pytest.raises(ReceiptError, match="overlap|origin|before|dates"):
        build_receipt_panel(replace(data, releases=(*data.releases[:-1], future)))


def test_duplicate_programs_are_rejected() -> None:
    data = sources()
    initial = data.releases[0]
    duplicate = replace(initial, outcomes=(*initial.outcomes, initial.outcomes[0]))
    with pytest.raises(ReceiptError, match="duplicate"):
        build_receipt_panel(replace(data, releases=(duplicate, *data.releases[1:])))


def measured(item):
    source = item.source
    rate = item.methodology.metric("transplant_rate")
    key = item.identities[0].program_key
    signal = ProgramSignal(
        key,
        *key.split(":"),
        "Example",
        source.release_code,
        source.published_value,
        source.published_precision,
        source.cohort_year,
        date(source.cohort_year, 1, 1),
        date(source.cohort_year, 12, 31),
        "overall",
        100,
        10,
        12.0,
        0.85,
        0.5,
        1.2,
        source.url,
        source.download_sha256,
    )
    return replace(
        item,
        transplant_rates=(
            TransplantRate(
                key, source.release_code, rate.measurement_start, rate.measurement_end, 100.0, 1.2
            ),
        ),
        wait_times=(
            WaitTime(
                key,
                source.release_code,
                item.periods.wait_start,
                item.periods.wait_end,
                item.periods.wait_follow_up_end,
                12.0,
                "12",
            ),
        ),
        acceptance=replace(item.acceptance, signals=(signal,)),
    )


@pytest.mark.parametrize("family", ["transplant_rates", "wait_times", "acceptance"])
def test_future_measurement_cannot_be_mislabeled_as_an_earlier_release(family):
    data = sources()
    initial = measured(data.releases[0])
    if family == "acceptance":
        changed = replace(initial.acceptance.signals[0], cohort_end=date(2020, 12, 31))
        initial = replace(initial, acceptance=replace(initial.acceptance, signals=(changed,)))
    else:
        changed = replace(getattr(initial, family)[0], measurement_end=date(2020, 12, 31))
        initial = replace(initial, **{family: (changed,)})
    with pytest.raises(ReceiptError, match="timing|provenance|date"):
        build_receipt_panel(replace(data, releases=(initial, *data.releases[1:])))


@pytest.mark.parametrize("family", ["transplant_rates", "wait_times", "acceptance"])
def test_measurements_must_belong_to_their_claimed_source_release(family):
    data = sources()
    initial = measured(data.releases[0])
    if family == "acceptance":
        initial = replace(initial, acceptance=replace(initial.acceptance, release_code="2605"))
    else:
        changed = replace(getattr(initial, family)[0], release_code="2605")
        initial = replace(initial, **{family: (changed,)})
    with pytest.raises(ReceiptError, match="release|source"):
        build_receipt_panel(replace(data, releases=(initial, *data.releases[1:])))


def test_release_methodology_and_independent_periods_must_agree():
    data = sources()
    initial = data.releases[0]
    metrics = tuple(
        replace(metric, measurement_start=date(2010, 1, 1))
        if metric.family == "wait_time"
        else metric
        for metric in initial.methodology.metrics
    )
    initial = replace(initial, methodology=replace(initial.methodology, metrics=metrics))
    with pytest.raises(ReceiptError, match="period|evidence|date"):
        build_receipt_panel(replace(data, releases=(initial, *data.releases[1:])))


def test_transplant_rate_followup_cannot_reach_target_listing():
    data = sources()
    initial = data.releases[0]
    metrics = tuple(
        replace(metric, follow_up_end=date(2019, 7, 1))
        if metric.family == "transplant_rate"
        else metric
        for metric in initial.methodology.metrics
    )
    initial = replace(initial, methodology=replace(initial.methodology, metrics=metrics))
    with pytest.raises(ReceiptError, match="before|follow-up"):
        build_receipt_panel(replace(data, releases=(initial, *data.releases[1:])))


def test_directory_additions_and_exits_are_distinct_from_missing_outcome_rows():
    data = sources()
    future = release("2505", 2025, ("AAAA:TX1", "BBBB:TX1"))
    future = replace(future, outcomes=())
    panel = build_receipt_panel(replace(data, releases=(*data.releases[:-1], future)))
    qa = panel.qa["pairs"]["2205->2505"]
    assert qa["target_only_programs"] == ["BBBB:TX1"]
    assert qa["programs_absent_from_target_directory"] == ["AAAA:VA"]
    assert qa["missing_outcome_in_target_directory"] == ["AAAA:TX1"]


def test_publication_precision_uses_conservative_bounds_without_changing_labels():
    month = release("1905", 2019).source
    day = replace(
        month, release_code="1906", published_value="2019-07-15", published_precision="day"
    )
    assert not publication_available(month, day)
    assert not publication_available(day, month)
    assert publication_available(month, month)
    assert publication_available(month, replace(day, published_value="2019-08-01"))
    assert month.published_value == "2019-07"


def test_missing_latest_receipt_uses_an_earlier_complete_report_without_future_values():
    data = sources()
    current = measured(data.releases[1])
    values = {field: 0.0 for field in DECEASED_FIELDS}
    values.update(SAL_N_C=100, SAL_CTXFNC_C18=None)
    outcomes = tuple(replace(row, values=parse_receipt_values(values)) for row in current.outcomes)
    current = replace(current, outcomes=outcomes)
    future = measured(data.releases[-1])
    future = replace(
        future, transplant_rates=(replace(future.transplant_rates[0], transplant_rate_ratio=9.9),)
    )
    panel = build_receipt_panel(replace(data, releases=(data.releases[0], current, future)))
    row = next(
        row
        for row in panel.rows
        if row["target_release_code"] == "2505" and row["program_key"] == "AAAA:TX1"
    )
    assert row["prior_target_release_code"] == "1905"
    assert row["history_release_codes"] == ["1905"]
    assert row["historical_mean_target_proportion"] == pytest.approx(0.3)
    assert row["transplant_rate_ratio"] == 1.2
    assert row["wait_time_months_25th_percentile"] == 12.0
    assert row["acceptance_overall_oar"] == 0.85
    assert row["missing_transplant_rate_ratio"] is False
    assert row["missing_wait_time"] is False
    assert row["missing_acceptance_interval"] is False
    assert row["prediction_origin_value"] == "2022-07"


def test_low_listing_count_and_missing_history_have_separate_exclusion_reasons():
    data = sources()
    earlier = replace(data.releases[0], outcomes=())
    current = replace(data.releases[1], outcomes=())
    values = {field: 0.0 for field in DECEASED_FIELDS}
    values.update(SAL_N_C=9, SAL_CTXFNC_C18=30.0)
    future = replace(
        data.releases[-1],
        outcomes=tuple(
            replace(row, values=parse_receipt_values(values)) for row in data.releases[-1].outcomes
        ),
    )
    panel = build_receipt_panel(replace(data, releases=(earlier, current, future)))
    row = next(row for row in panel.rows if row["target_release_code"] == "2505")
    assert row["eligibility_reasons"] == ["target_n_below_10", "missing_prior_receipt"]
    assert row["target_proportion"] == pytest.approx(0.3)
    assert row["prior_target_proportion"] is None
    assert row["primary_analytic_eligible"] is False


@pytest.mark.parametrize(
    "change",
    [
        "unknown_program",
        "mismatched_identity",
        "duplicate_directory",
        "duplicate_release",
        "duplicate_pair",
        "unknown_pair",
        "duplicate_fold",
        "same_training_pair",
    ],
)
def test_program_and_pair_anomalies_cannot_silently_change_the_population(change):
    data = sources()
    current = data.releases[0]
    if change == "unknown_program":
        current = replace(current, outcomes=(replace(current.outcomes[0], program_key="ZZZZ:TX1"),))
    elif change == "mismatched_identity":
        current = replace(current, identities=(replace(current.identities[0], center_type="VA"),))
    elif change == "duplicate_directory":
        current = replace(current, identities=(*current.identities, current.identities[0]))
    elif change == "duplicate_release":
        data = replace(data, releases=(*data.releases, current))
    elif change == "duplicate_pair":
        data = replace(data, pairs=(*data.pairs, data.pairs[0]))
    elif change == "unknown_pair":
        data = replace(data, pairs=(*data.pairs, ("1808", "2105")))
    elif change == "duplicate_fold":
        data = replace(data, folds=(*data.folds, data.folds[0]))
    else:
        data = replace(data, folds=((data.pairs[1], (data.pairs[1],)),))
    if change in {"unknown_program", "mismatched_identity", "duplicate_directory"}:
        data = replace(data, releases=(current, *data.releases[1:]))
    with pytest.raises(ReceiptError):
        build_receipt_panel(data)
