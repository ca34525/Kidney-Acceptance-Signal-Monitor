"""Leakage-safe canonical panel construction for the patient-journey v2 study."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from statistics import fmean
from typing import Literal, TypeGuard

import pyarrow as pa  # type: ignore[import-untyped]

from kasm.config import DataSourceManifest, PublishedPrecision, SourceRecord
from kasm.data.parse import (
    OfferGroup,
    ParsedRelease,
    ProgramSignal,
    load_workbook_payload,
    parse_offer_acceptance_workbook,
    read_workbook_sheets,
)
from kasm.patient_journey.config import (
    PatientJourneyConfig,
    PatientJourneyExcludedPair,
    PatientJourneyPair,
)
from kasm.patient_journey.ledger import MethodologyLedger, ReleaseMethodology
from kasm.patient_journey.parse import (
    ParsedPatientJourneyRelease,
    PatientJourneyOutcome,
    ProgramIdentity,
    TransplantRate,
    WaitTime,
    parse_patient_journey_workbook,
)

EligibilityStatus = Literal[
    "eligible",
    "missing_target",
    "target_n_below_10",
    "missing_prior_target",
]

_ACCEPTANCE_GROUPS: tuple[OfferGroup, ...] = (
    "overall",
    "low",
    "medium",
    "high",
    "hard-to-place",
)

_CATEGORY = pa.dictionary(pa.int8(), pa.string())


class PatientJourneyPanelError(ValueError):
    """Raised when panel construction would weaken a v2 scientific contract."""


@dataclass(frozen=True)
class StrictVintageFold:
    """One evaluation pair and labels genuinely available at its origin."""

    evaluation_pair: PatientJourneyPair
    training_pairs: tuple[PatientJourneyPair, ...]


@dataclass(frozen=True)
class PatientJourneyPanelRow:
    """One feature-release program and its later published patient-journey target."""

    program_key: str
    center_code: str
    center_type: str
    feature_release_code: str
    target_release_code: str
    prediction_origin_value: str
    prediction_origin_precision: PublishedPrecision
    prediction_origin_month_offset_from_target_start: int
    target_published_value: str
    target_published_precision: PublishedPrecision
    target_listing_cohort_start: date
    target_listing_cohort_end: date
    target_follow_up_end: date
    methodology_ledger_identity: str
    prior_target_release_code: str | None
    prior_target_published_value: str | None
    prior_target_published_precision: PublishedPrecision | None
    prior_target_listing_cohort_start: date | None
    prior_target_listing_cohort_end: date | None
    prior_target_follow_up_end: date | None
    prior_target_n: int | None
    prior_target_published_percent: float | None
    prior_target_proportion: float | None
    prior_target_logit: float | None
    historical_target_count: int
    historical_mean_target_proportion: float | None
    available_cohort_target_proportion: float | None
    transplant_rate_measurement_start: date
    transplant_rate_measurement_end: date
    transplant_rate_person_years: float | None
    transplant_rate_ratio: float | None
    wait_time_measurement_start: date
    wait_time_measurement_end: date
    wait_time_follow_up_end: date
    wait_time_months_25th_percentile: float | None
    wait_time_raw_value: str | None
    acceptance_cohort_start: date
    acceptance_cohort_end: date
    acceptance_overall_expected_acceptances: float | None
    acceptance_overall_oar: float | None
    acceptance_overall_oar_lower: float | None
    acceptance_overall_oar_upper: float | None
    acceptance_low_oar: float | None
    acceptance_medium_oar: float | None
    acceptance_high_oar: float | None
    acceptance_hard_to_place_oar: float | None
    missing_prior_target: bool
    missing_transplant_rate_person_years: bool
    missing_transplant_rate_ratio: bool
    missing_wait_time: bool
    missing_acceptance_expected_acceptances: bool
    missing_acceptance_overall_oar: bool
    missing_acceptance_interval: bool
    missing_acceptance_low_oar: bool
    missing_acceptance_medium_oar: bool
    missing_acceptance_high_oar: bool
    missing_acceptance_hard_to_place_oar: bool
    target_n: int | None
    target_published_percent: float | None
    target_proportion: float | None
    target_reconstructed_successes: int | None
    target_logit: float | None
    missing_target: bool
    first_observed_program: bool
    primary_analytic_eligible: bool
    sensitivity_n20_eligible: bool
    sensitivity_n30_eligible: bool
    eligibility_status: EligibilityStatus
    feature_source_url: str
    feature_source_sha256: str
    target_source_url: str
    target_source_sha256: str


@dataclass(frozen=True)
class PatientJourneyPairSummary:
    """Pair-level QA for prediction-universe and target availability."""

    feature_release_code: str
    target_release_code: str
    prediction_universe_rows: int
    target_table_rows: int
    matched_target_rows: int
    missing_target_rows: int
    target_only_additions: int
    primary_eligible_rows: int
    sensitivity_n20_eligible_rows: int
    sensitivity_n30_eligible_rows: int
    first_observed_rows: int


@dataclass(frozen=True)
class PatientJourneyPanel:
    """Canonical rows plus the exact temporal design and QA evidence."""

    rows: tuple[PatientJourneyPanelRow, ...]
    pair_summaries: tuple[PatientJourneyPairSummary, ...]
    strict_vintage_folds: tuple[StrictVintageFold, ...]
    excluded_candidates: tuple[PatientJourneyExcludedPair, ...]
    methodology_ledger_identity: str


PATIENT_JOURNEY_PANEL_SCHEMA = pa.schema(
    [
        pa.field("program_key", pa.string(), nullable=False),
        pa.field("center_code", pa.string(), nullable=False),
        pa.field("center_type", pa.string(), nullable=False),
        pa.field("feature_release_code", pa.string(), nullable=False),
        pa.field("target_release_code", pa.string(), nullable=False),
        pa.field("prediction_origin_value", pa.string(), nullable=False),
        pa.field("prediction_origin_precision", _CATEGORY, nullable=False),
        pa.field(
            "prediction_origin_month_offset_from_target_start",
            pa.int8(),
            nullable=False,
        ),
        pa.field("target_published_value", pa.string(), nullable=False),
        pa.field("target_published_precision", _CATEGORY, nullable=False),
        pa.field("target_listing_cohort_start", pa.date32(), nullable=False),
        pa.field("target_listing_cohort_end", pa.date32(), nullable=False),
        pa.field("target_follow_up_end", pa.date32(), nullable=False),
        pa.field("methodology_ledger_identity", pa.string(), nullable=False),
        pa.field("prior_target_release_code", pa.string()),
        pa.field("prior_target_published_value", pa.string()),
        pa.field("prior_target_published_precision", _CATEGORY),
        pa.field("prior_target_listing_cohort_start", pa.date32()),
        pa.field("prior_target_listing_cohort_end", pa.date32()),
        pa.field("prior_target_follow_up_end", pa.date32()),
        pa.field("prior_target_n", pa.int64()),
        pa.field("prior_target_published_percent", pa.float64()),
        pa.field("prior_target_proportion", pa.float64()),
        pa.field("prior_target_logit", pa.float64()),
        pa.field("historical_target_count", pa.int16(), nullable=False),
        pa.field("historical_mean_target_proportion", pa.float64()),
        pa.field("available_cohort_target_proportion", pa.float64()),
        pa.field("transplant_rate_measurement_start", pa.date32(), nullable=False),
        pa.field("transplant_rate_measurement_end", pa.date32(), nullable=False),
        pa.field("transplant_rate_person_years", pa.float64()),
        pa.field("transplant_rate_ratio", pa.float64()),
        pa.field("wait_time_measurement_start", pa.date32(), nullable=False),
        pa.field("wait_time_measurement_end", pa.date32(), nullable=False),
        pa.field("wait_time_follow_up_end", pa.date32(), nullable=False),
        pa.field("wait_time_months_25th_percentile", pa.float64()),
        pa.field("wait_time_raw_value", pa.string()),
        pa.field("acceptance_cohort_start", pa.date32(), nullable=False),
        pa.field("acceptance_cohort_end", pa.date32(), nullable=False),
        pa.field("acceptance_overall_expected_acceptances", pa.float64()),
        pa.field("acceptance_overall_oar", pa.float64()),
        pa.field("acceptance_overall_oar_lower", pa.float64()),
        pa.field("acceptance_overall_oar_upper", pa.float64()),
        pa.field("acceptance_low_oar", pa.float64()),
        pa.field("acceptance_medium_oar", pa.float64()),
        pa.field("acceptance_high_oar", pa.float64()),
        pa.field("acceptance_hard_to_place_oar", pa.float64()),
        pa.field("missing_prior_target", pa.bool_(), nullable=False),
        pa.field("missing_transplant_rate_person_years", pa.bool_(), nullable=False),
        pa.field("missing_transplant_rate_ratio", pa.bool_(), nullable=False),
        pa.field("missing_wait_time", pa.bool_(), nullable=False),
        pa.field("missing_acceptance_expected_acceptances", pa.bool_(), nullable=False),
        pa.field("missing_acceptance_overall_oar", pa.bool_(), nullable=False),
        pa.field("missing_acceptance_interval", pa.bool_(), nullable=False),
        pa.field("missing_acceptance_low_oar", pa.bool_(), nullable=False),
        pa.field("missing_acceptance_medium_oar", pa.bool_(), nullable=False),
        pa.field("missing_acceptance_high_oar", pa.bool_(), nullable=False),
        pa.field("missing_acceptance_hard_to_place_oar", pa.bool_(), nullable=False),
        pa.field("target_n", pa.int64()),
        pa.field("target_published_percent", pa.float64()),
        pa.field("target_proportion", pa.float64()),
        pa.field("target_reconstructed_successes", pa.int64()),
        pa.field("target_logit", pa.float64()),
        pa.field("missing_target", pa.bool_(), nullable=False),
        pa.field("first_observed_program", pa.bool_(), nullable=False),
        pa.field("primary_analytic_eligible", pa.bool_(), nullable=False),
        pa.field("sensitivity_n20_eligible", pa.bool_(), nullable=False),
        pa.field("sensitivity_n30_eligible", pa.bool_(), nullable=False),
        pa.field("eligibility_status", _CATEGORY, nullable=False),
        pa.field("feature_source_url", pa.string(), nullable=False),
        pa.field("feature_source_sha256", pa.string(), nullable=False),
        pa.field("target_source_url", pa.string(), nullable=False),
        pa.field("target_source_sha256", pa.string(), nullable=False),
    ]
)


def _release_maps(
    ledger: MethodologyLedger, sources: tuple[SourceRecord, ...]
) -> tuple[dict[str, int], dict[str, ReleaseMethodology], dict[str, SourceRecord]]:
    ledger_codes = tuple(release.release_code for release in ledger.releases)
    source_codes = tuple(source.release_code for source in sources)
    if ledger_codes != source_codes:
        raise PatientJourneyPanelError(
            "Panel sources must exactly cover methodology releases in ledger order."
        )
    return (
        {code: index for index, code in enumerate(ledger_codes)},
        {release.release_code: release for release in ledger.releases},
        {source.release_code: source for source in sources},
    )


def _cohorts_overlap(first: tuple[date, date], second: tuple[date, date]) -> bool:
    return first[0] <= second[1] and second[0] <= first[1]


def _prediction_origin_month_offset(source: SourceRecord, target_start: date) -> int:
    try:
        published_year = int(source.published_value[:4])
        published_month = int(source.published_value[5:7])
    except ValueError as error:
        raise PatientJourneyPanelError(
            f"Release {source.release_code!r} has an invalid publication value."
        ) from error
    if (
        len(source.published_value) < 7
        or source.published_value[4] != "-"
        or not (1 <= published_month <= 12)
    ):
        raise PatientJourneyPanelError(
            f"Release {source.release_code!r} has an invalid publication value."
        )
    return (published_year - target_start.year) * 12 + published_month - target_start.month


def validate_temporal_design(
    config: PatientJourneyConfig,
    ledger: MethodologyLedger,
    sources: tuple[SourceRecord, ...],
) -> None:
    """Reject unknown, leaky, or overlapping primary release pairs."""
    order, releases, source_by_code = _release_maps(ledger, sources)
    target_cohorts: list[tuple[PatientJourneyPair, tuple[date, date]]] = []
    for pair in config.temporal_design.primary_pairs:
        if pair.feature_release_code not in order or pair.target_release_code not in order:
            raise PatientJourneyPanelError(f"Unknown primary temporal pair {pair!r}.")
        if order[pair.feature_release_code] >= order[pair.target_release_code]:
            raise PatientJourneyPanelError(
                f"Primary pair {pair!r} must place the feature release before the target release."
            )
        feature_method = releases[pair.feature_release_code]
        target_method = releases[pair.target_release_code].metric("patient_outcome")
        origin_offset = _prediction_origin_month_offset(
            source_by_code[pair.feature_release_code], target_method.measurement_start
        )
        max_offset = config.temporal_design.max_prediction_origin_month_offset
        if origin_offset > max_offset:
            raise PatientJourneyPanelError(
                f"Primary pair {pair!r} prediction-origin offset {origin_offset} months "
                f"exceeds the configured maximum of {max_offset}."
            )
        for metric in feature_method.metrics:
            if metric.measurement_end >= target_method.measurement_start:
                raise PatientJourneyPanelError(
                    f"Primary pair {pair!r} has {metric.family} measurement overlap with target."
                )
            if metric.follow_up_end >= target_method.measurement_start:
                raise PatientJourneyPanelError(
                    f"Primary pair {pair!r} has {metric.family} follow-up overlap with target."
                )
        source = source_by_code[pair.feature_release_code]
        acceptance_end = date(source.cohort_year, 12, 31)
        if acceptance_end >= target_method.measurement_start:
            raise PatientJourneyPanelError(
                f"Primary pair {pair!r} has acceptance measurement overlap with target."
            )
        target_cohorts.append(
            (pair, (target_method.measurement_start, target_method.measurement_end))
        )

    for index, (pair, cohort) in enumerate(target_cohorts):
        for other_pair, other_cohort in target_cohorts[index + 1 :]:
            if _cohorts_overlap(cohort, other_cohort):
                raise PatientJourneyPanelError(
                    f"Primary target cohorts for {pair!r} and {other_pair!r} overlap."
                )

    excluded_overlap_targets = {
        pair.target_release_code
        for pair in config.temporal_design.excluded_candidates
        if pair.reason == "overlapping_target_cohort"
    }
    primary_targets = {pair.target_release_code for pair in config.temporal_design.primary_pairs}
    for _, overlapping_release in ledger.overlapping_outcome_cohorts():
        if overlapping_release in primary_targets:
            raise PatientJourneyPanelError(
                f"Overlapping outcome release {overlapping_release!r} cannot be a primary target."
            )
        if overlapping_release not in excluded_overlap_targets:
            raise PatientJourneyPanelError(
                f"Overlapping outcome release {overlapping_release!r} lacks an explicit exclusion."
            )


def strict_vintage_folds(
    config: PatientJourneyConfig, ledger: MethodologyLedger
) -> tuple[StrictVintageFold, ...]:
    """Derive training pairs whose truth was public at each evaluation origin."""
    order = {release.release_code: index for index, release in enumerate(ledger.releases)}
    folds: list[StrictVintageFold] = []
    for evaluation_pair in config.temporal_design.primary_pairs:
        if evaluation_pair.feature_release_code not in order:
            raise PatientJourneyPanelError(
                f"Unknown evaluation feature release {evaluation_pair.feature_release_code!r}."
            )
        evaluation_target = ledger.release(evaluation_pair.target_release_code).metric(
            "patient_outcome"
        )
        available: list[PatientJourneyPair] = []
        for candidate in config.temporal_design.primary_pairs:
            if candidate == evaluation_pair or candidate.target_release_code not in order:
                continue
            candidate_target = ledger.release(candidate.target_release_code).metric(
                "patient_outcome"
            )
            truth_is_public = (
                order[candidate.target_release_code] <= order[evaluation_pair.feature_release_code]
            )
            cohort_is_prior = candidate_target.measurement_end < evaluation_target.measurement_start
            if truth_is_public and cohort_is_prior:
                available.append(candidate)
        folds.append(
            StrictVintageFold(
                evaluation_pair=evaluation_pair,
                training_pairs=tuple(available),
            )
        )
    return tuple(folds)


def _unique_by_program(
    rows: tuple[ProgramIdentity | PatientJourneyOutcome | TransplantRate | WaitTime, ...],
    *,
    context: str,
) -> dict[str, ProgramIdentity | PatientJourneyOutcome | TransplantRate | WaitTime]:
    result: dict[str, ProgramIdentity | PatientJourneyOutcome | TransplantRate | WaitTime] = {}
    for row in rows:
        if row.program_key in result:
            raise PatientJourneyPanelError(f"{context} duplicates program {row.program_key!r}.")
        result[row.program_key] = row
    return result


def _canonical_json_value(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Unsupported methodology identity value {type(value).__name__}.")


def _methodology_ledger_identity(ledger: MethodologyLedger) -> str:
    payload = json.dumps(
        asdict(ledger),
        default=_canonical_json_value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


@dataclass(frozen=True)
class _PatientReleaseIndex:
    identities: dict[str, ProgramIdentity]
    outcomes: dict[str, PatientJourneyOutcome]
    transplant_rates: dict[str, TransplantRate]
    wait_times: dict[str, WaitTime]


def _validate_identity_rows(
    release_code: str,
    identities: dict[str, ProgramIdentity],
) -> None:
    for identity in identities.values():
        expected_key = f"{identity.center_code}:{identity.center_type}"
        if identity.program_key != expected_key:
            raise PatientJourneyPanelError(
                f"{release_code} identity key {identity.program_key!r} "
                f"disagrees with code and type {expected_key!r}."
            )


def _validate_outcome_rows(
    release_code: str,
    outcomes: dict[str, PatientJourneyOutcome],
    methodology: ReleaseMethodology,
    source: SourceRecord,
) -> None:
    timing = methodology.metric("patient_outcome")
    for outcome in outcomes.values():
        if outcome.release_code != release_code:
            raise PatientJourneyPanelError(
                f"{release_code} outcome row release {outcome.release_code!r} disagrees."
            )
        if (
            outcome.published_value != source.published_value
            or outcome.published_precision != source.published_precision
            or outcome.source_url != source.url
            or outcome.source_sha256 != source.download_sha256
        ):
            raise PatientJourneyPanelError(
                f"{release_code} outcome row publication or source provenance disagrees."
            )
        if (
            outcome.listing_cohort_start != timing.measurement_start
            or outcome.listing_cohort_end != timing.measurement_end
            or outcome.follow_up_end != timing.follow_up_end
        ):
            raise PatientJourneyPanelError(
                f"{release_code} outcome row timing disagrees with methodology."
            )


def _validate_rate_rows(
    release_code: str,
    rates: dict[str, TransplantRate],
    methodology: ReleaseMethodology,
) -> None:
    timing = methodology.metric("transplant_rate")
    for rate in rates.values():
        if rate.release_code != release_code:
            raise PatientJourneyPanelError(f"{release_code} transplant-rate row release disagrees.")
        if (
            rate.measurement_start != timing.measurement_start
            or rate.measurement_end != timing.measurement_end
        ):
            raise PatientJourneyPanelError(
                f"{release_code} transplant-rate row timing disagrees with methodology."
            )


def _validate_wait_rows(
    release_code: str,
    wait_times: dict[str, WaitTime],
    methodology: ReleaseMethodology,
) -> None:
    timing = methodology.metric("wait_time")
    for wait_time in wait_times.values():
        if wait_time.release_code != release_code:
            raise PatientJourneyPanelError(f"{release_code} wait-time row release disagrees.")
        if (
            wait_time.measurement_start != timing.measurement_start
            or wait_time.measurement_end != timing.measurement_end
            or wait_time.follow_up_end != timing.follow_up_end
        ):
            raise PatientJourneyPanelError(
                f"{release_code} wait-time row timing disagrees with methodology."
            )


def _index_patient_release(
    release: ParsedPatientJourneyRelease,
    methodology: ReleaseMethodology,
    source: SourceRecord,
) -> _PatientReleaseIndex:
    if not (release.release_code == source.release_code == methodology.release_code):
        raise PatientJourneyPanelError(
            f"Patient release {release.release_code!r} disagrees with its source or methodology."
        )
    identities = {identity.program_key: identity for identity in release.identities}
    if len(identities) != len(release.identities):
        raise PatientJourneyPanelError(f"{release.release_code} identities contain duplicates.")
    _validate_identity_rows(release.release_code, identities)

    outcomes = {row.program_key: row for row in release.outcomes}
    rates = {row.program_key: row for row in release.transplant_rates}
    wait_times = {row.program_key: row for row in release.wait_times}
    collections = (("outcomes", outcomes), ("transplant rates", rates), ("wait times", wait_times))
    for label, values in collections:
        expected_length = {
            "outcomes": len(release.outcomes),
            "transplant rates": len(release.transplant_rates),
            "wait times": len(release.wait_times),
        }[label]
        if len(values) != expected_length:
            raise PatientJourneyPanelError(
                f"{release.release_code} {label} contains duplicate programs."
            )
        unknown = set(values) - set(identities)
        if unknown:
            raise PatientJourneyPanelError(
                f"{release.release_code} {label} contains unknown same-release identity "
                f"{sorted(unknown)[0]!r}."
            )

    _validate_outcome_rows(release.release_code, outcomes, methodology, source)
    _validate_rate_rows(release.release_code, rates, methodology)
    _validate_wait_rows(release.release_code, wait_times, methodology)
    return _PatientReleaseIndex(
        identities=identities,
        outcomes=outcomes,
        transplant_rates=rates,
        wait_times=wait_times,
    )


def _index_acceptance_release(
    release: ParsedRelease,
    identities: dict[str, ProgramIdentity],
    source: SourceRecord,
) -> dict[tuple[str, OfferGroup], ProgramSignal]:
    if release.release_code != source.release_code or release.cohort_year != source.cohort_year:
        raise PatientJourneyPanelError(
            f"Acceptance release {release.release_code!r} disagrees with its source."
        )
    result: dict[tuple[str, OfferGroup], ProgramSignal] = {}
    for signal in release.signals:
        if signal.release_code != release.release_code:
            raise PatientJourneyPanelError(
                f"Acceptance signal release disagrees with {release.release_code!r}."
            )
        expected_key = f"{signal.center_code}:{signal.center_type}"
        if (
            signal.program_key != expected_key
            or signal.published_value != source.published_value
            or signal.published_precision != source.published_precision
            or signal.cohort_year != source.cohort_year
            or signal.cohort_start != date(source.cohort_year, 1, 1)
            or signal.cohort_end != date(source.cohort_year, 12, 31)
            or signal.source_url != source.url
            or signal.source_sha256 != source.download_sha256
        ):
            raise PatientJourneyPanelError(
                f"Acceptance signal {signal.program_key!r} disagrees with source provenance."
            )
        if signal.program_key not in identities:
            raise PatientJourneyPanelError(
                f"Acceptance program {signal.program_key!r} is not a same-release identity."
            )
        key = (signal.program_key, signal.offer_group)
        if key in result:
            raise PatientJourneyPanelError(f"Acceptance key {key!r} is not unique.")
        result[key] = signal
    return result


def _valid_outcome(
    outcome: PatientJourneyOutcome | None,
) -> TypeGuard[PatientJourneyOutcome]:
    return (
        outcome is not None
        and outcome.target_n is not None
        and outcome.published_percent is not None
        and outcome.target_proportion is not None
        and outcome.reconstructed_successes is not None
        and outcome.target_logit is not None
    )


def _history(
    program_key: str,
    *,
    feature_index: int,
    ordered_releases: tuple[ParsedPatientJourneyRelease, ...],
    indexes: dict[str, _PatientReleaseIndex],
) -> tuple[PatientJourneyOutcome | None, tuple[PatientJourneyOutcome, ...]]:
    observed: list[PatientJourneyOutcome] = []
    for release in ordered_releases[: feature_index + 1]:
        outcome = indexes[release.release_code].outcomes.get(program_key)
        if _valid_outcome(outcome):
            observed.append(outcome)
    return (observed[-1] if observed else None), tuple(observed)


def _available_cohort_proportion(index: _PatientReleaseIndex) -> float | None:
    outcomes = tuple(outcome for outcome in index.outcomes.values() if _valid_outcome(outcome))
    total_n = sum(outcome.target_n or 0 for outcome in outcomes)
    if total_n == 0:
        return None
    successes = sum(outcome.reconstructed_successes or 0 for outcome in outcomes)
    return successes / total_n


def _eligibility(
    target: PatientJourneyOutcome | None,
    prior: PatientJourneyOutcome | None,
    config: PatientJourneyConfig,
) -> tuple[bool, bool, bool, EligibilityStatus]:
    if not _valid_outcome(target):
        return False, False, False, "missing_target"
    target_n = target.target_n
    if target_n is None or target_n < config.eligibility.primary_min_target_n:
        return False, False, False, "target_n_below_10"
    if not _valid_outcome(prior):
        return False, False, False, "missing_prior_target"
    n20, n30 = config.eligibility.sensitivity_min_target_n
    return True, target_n >= n20, target_n >= n30, "eligible"


def _first_observed(
    program_key: str,
    *,
    feature_index: int,
    ordered_releases: tuple[ParsedPatientJourneyRelease, ...],
    indexes: dict[str, _PatientReleaseIndex],
) -> bool:
    return not any(
        program_key in indexes[release.release_code].identities
        for release in ordered_releases[:feature_index]
    )


def _row_for_program(
    identity: ProgramIdentity,
    *,
    pair: PatientJourneyPair,
    feature_source: SourceRecord,
    target_source: SourceRecord,
    feature_method: ReleaseMethodology,
    target_method: ReleaseMethodology,
    feature_index: int,
    ordered_releases: tuple[ParsedPatientJourneyRelease, ...],
    indexes: dict[str, _PatientReleaseIndex],
    acceptance: dict[tuple[str, OfferGroup], ProgramSignal],
    config: PatientJourneyConfig,
    methodology_ledger_identity: str,
) -> PatientJourneyPanelRow:
    feature = indexes[pair.feature_release_code]
    target_index = indexes[pair.target_release_code]
    prior, history = _history(
        identity.program_key,
        feature_index=feature_index,
        ordered_releases=ordered_releases,
        indexes=indexes,
    )
    target = target_index.outcomes.get(identity.program_key)
    rate = feature.transplant_rates.get(identity.program_key)
    wait_time = feature.wait_times.get(identity.program_key)
    groups: dict[OfferGroup, ProgramSignal | None] = {
        group: acceptance.get((identity.program_key, group)) for group in _ACCEPTANCE_GROUPS
    }
    overall = groups["overall"]
    primary, sensitivity_n20, sensitivity_n30, status = _eligibility(target, prior, config)
    target_timing = target_method.metric("patient_outcome")
    rate_timing = feature_method.metric("transplant_rate")
    wait_timing = feature_method.metric("wait_time")
    history_values = tuple(
        outcome.target_proportion for outcome in history if outcome.target_proportion is not None
    )
    return PatientJourneyPanelRow(
        program_key=identity.program_key,
        center_code=identity.center_code,
        center_type=identity.center_type,
        feature_release_code=pair.feature_release_code,
        target_release_code=pair.target_release_code,
        prediction_origin_value=feature_source.published_value,
        prediction_origin_precision=feature_source.published_precision,
        prediction_origin_month_offset_from_target_start=_prediction_origin_month_offset(
            feature_source, target_timing.measurement_start
        ),
        target_published_value=target_source.published_value,
        target_published_precision=target_source.published_precision,
        target_listing_cohort_start=target_timing.measurement_start,
        target_listing_cohort_end=target_timing.measurement_end,
        target_follow_up_end=target_timing.follow_up_end,
        methodology_ledger_identity=methodology_ledger_identity,
        prior_target_release_code=prior.release_code if prior else None,
        prior_target_published_value=prior.published_value if prior else None,
        prior_target_published_precision=prior.published_precision if prior else None,
        prior_target_listing_cohort_start=prior.listing_cohort_start if prior else None,
        prior_target_listing_cohort_end=prior.listing_cohort_end if prior else None,
        prior_target_follow_up_end=prior.follow_up_end if prior else None,
        prior_target_n=prior.target_n if prior else None,
        prior_target_published_percent=prior.published_percent if prior else None,
        prior_target_proportion=prior.target_proportion if prior else None,
        prior_target_logit=prior.target_logit if prior else None,
        historical_target_count=len(history_values),
        historical_mean_target_proportion=(fmean(history_values) if history_values else None),
        available_cohort_target_proportion=_available_cohort_proportion(feature),
        transplant_rate_measurement_start=rate_timing.measurement_start,
        transplant_rate_measurement_end=rate_timing.measurement_end,
        transplant_rate_person_years=rate.person_years if rate else None,
        transplant_rate_ratio=rate.transplant_rate_ratio if rate else None,
        wait_time_measurement_start=wait_timing.measurement_start,
        wait_time_measurement_end=wait_timing.measurement_end,
        wait_time_follow_up_end=wait_timing.follow_up_end,
        wait_time_months_25th_percentile=(wait_time.months_25th_percentile if wait_time else None),
        wait_time_raw_value=wait_time.raw_value if wait_time else None,
        acceptance_cohort_start=date(feature_source.cohort_year, 1, 1),
        acceptance_cohort_end=date(feature_source.cohort_year, 12, 31),
        acceptance_overall_expected_acceptances=(overall.expected_acceptances if overall else None),
        acceptance_overall_oar=overall.oar_mean if overall else None,
        acceptance_overall_oar_lower=overall.oar_lower if overall else None,
        acceptance_overall_oar_upper=overall.oar_upper if overall else None,
        acceptance_low_oar=groups["low"].oar_mean if groups["low"] else None,
        acceptance_medium_oar=(groups["medium"].oar_mean if groups["medium"] else None),
        acceptance_high_oar=groups["high"].oar_mean if groups["high"] else None,
        acceptance_hard_to_place_oar=(
            groups["hard-to-place"].oar_mean if groups["hard-to-place"] else None
        ),
        missing_prior_target=prior is None,
        missing_transplant_rate_person_years=rate is None or rate.person_years is None,
        missing_transplant_rate_ratio=rate is None or rate.transplant_rate_ratio is None,
        missing_wait_time=wait_time is None or wait_time.months_25th_percentile is None,
        missing_acceptance_expected_acceptances=(
            overall is None or overall.expected_acceptances is None
        ),
        missing_acceptance_overall_oar=overall is None or overall.oar_mean is None,
        missing_acceptance_interval=(
            overall is None or overall.oar_lower is None or overall.oar_upper is None
        ),
        missing_acceptance_low_oar=groups["low"] is None or groups["low"].oar_mean is None,
        missing_acceptance_medium_oar=(
            groups["medium"] is None or groups["medium"].oar_mean is None
        ),
        missing_acceptance_high_oar=(groups["high"] is None or groups["high"].oar_mean is None),
        missing_acceptance_hard_to_place_oar=(
            groups["hard-to-place"] is None or groups["hard-to-place"].oar_mean is None
        ),
        target_n=target.target_n if target else None,
        target_published_percent=target.published_percent if target else None,
        target_proportion=target.target_proportion if target else None,
        target_reconstructed_successes=target.reconstructed_successes if target else None,
        target_logit=target.target_logit if target else None,
        missing_target=not _valid_outcome(target),
        first_observed_program=_first_observed(
            identity.program_key,
            feature_index=feature_index,
            ordered_releases=ordered_releases,
            indexes=indexes,
        ),
        primary_analytic_eligible=primary,
        sensitivity_n20_eligible=sensitivity_n20,
        sensitivity_n30_eligible=sensitivity_n30,
        eligibility_status=status,
        feature_source_url=feature_source.url,
        feature_source_sha256=feature_source.download_sha256,
        target_source_url=target_source.url,
        target_source_sha256=target_source.download_sha256,
    )


def _pair_summary(
    pair: PatientJourneyPair,
    rows: tuple[PatientJourneyPanelRow, ...],
    *,
    target_table_rows: int,
    target_only_additions: int,
) -> PatientJourneyPairSummary:
    return PatientJourneyPairSummary(
        feature_release_code=pair.feature_release_code,
        target_release_code=pair.target_release_code,
        prediction_universe_rows=len(rows),
        target_table_rows=target_table_rows,
        matched_target_rows=sum(not row.missing_target for row in rows),
        missing_target_rows=sum(row.missing_target for row in rows),
        target_only_additions=target_only_additions,
        primary_eligible_rows=sum(row.primary_analytic_eligible for row in rows),
        sensitivity_n20_eligible_rows=sum(row.sensitivity_n20_eligible for row in rows),
        sensitivity_n30_eligible_rows=sum(row.sensitivity_n30_eligible for row in rows),
        first_observed_rows=sum(row.first_observed_program for row in rows),
    )


def build_patient_journey_panel(
    *,
    patient_releases: tuple[ParsedPatientJourneyRelease, ...],
    acceptance_releases: tuple[ParsedRelease, ...],
    config: PatientJourneyConfig,
    ledger: MethodologyLedger,
    sources: tuple[SourceRecord, ...],
) -> PatientJourneyPanel:
    """Build v2 rows from feature-release programs without conditioning on future reports."""
    validate_temporal_design(config, ledger, sources)
    order, methods, source_by_code = _release_maps(ledger, sources)
    patient_by_code: dict[str, ParsedPatientJourneyRelease] = {}
    for patient_release in patient_releases:
        if patient_release.release_code in patient_by_code:
            raise PatientJourneyPanelError(
                f"Patient release {patient_release.release_code!r} is duplicated."
            )
        patient_by_code[patient_release.release_code] = patient_release
    if tuple(patient_by_code) != tuple(release.release_code for release in ledger.releases):
        raise PatientJourneyPanelError(
            "Parsed patient releases must exactly cover the methodology ledger in order."
        )
    indexes = {
        code: _index_patient_release(release, methods[code], source_by_code[code])
        for code, release in patient_by_code.items()
    }
    acceptance_by_code: dict[str, ParsedRelease] = {}
    for acceptance_release in acceptance_releases:
        if acceptance_release.release_code in acceptance_by_code:
            raise PatientJourneyPanelError(
                f"Acceptance release {acceptance_release.release_code!r} is duplicated."
            )
        acceptance_by_code[acceptance_release.release_code] = acceptance_release

    all_rows: list[PatientJourneyPanelRow] = []
    summaries: list[PatientJourneyPairSummary] = []
    methodology_identity = _methodology_ledger_identity(ledger)
    for pair in config.temporal_design.primary_pairs:
        if pair.feature_release_code not in acceptance_by_code:
            raise PatientJourneyPanelError(
                f"Primary feature release {pair.feature_release_code!r} lacks acceptance rows."
            )
        feature = indexes[pair.feature_release_code]
        target = indexes[pair.target_release_code]
        acceptance = _index_acceptance_release(
            acceptance_by_code[pair.feature_release_code],
            feature.identities,
            source_by_code[pair.feature_release_code],
        )
        pair_rows = tuple(
            _row_for_program(
                identity,
                pair=pair,
                feature_source=source_by_code[pair.feature_release_code],
                target_source=source_by_code[pair.target_release_code],
                feature_method=methods[pair.feature_release_code],
                target_method=methods[pair.target_release_code],
                feature_index=order[pair.feature_release_code],
                ordered_releases=patient_releases,
                indexes=indexes,
                acceptance=acceptance,
                config=config,
                methodology_ledger_identity=methodology_identity,
            )
            for identity in sorted(feature.identities.values(), key=lambda row: row.program_key)
        )
        all_rows.extend(pair_rows)
        summaries.append(
            _pair_summary(
                pair,
                pair_rows,
                target_table_rows=len(target.outcomes),
                target_only_additions=len(set(target.outcomes) - set(feature.identities)),
            )
        )
    return PatientJourneyPanel(
        rows=tuple(all_rows),
        pair_summaries=tuple(summaries),
        strict_vintage_folds=strict_vintage_folds(config, ledger),
        excluded_candidates=config.temporal_design.excluded_candidates,
        methodology_ledger_identity=methodology_identity,
    )


def build_cached_patient_journey_panel(
    *,
    manifest: DataSourceManifest,
    ledger: MethodologyLedger,
    config: PatientJourneyConfig,
    cache_dir: Path,
) -> PatientJourneyPanel:
    """Parse each verified cache payload once and build the v2 panel without writing artifacts."""
    patient_releases: list[ParsedPatientJourneyRelease] = []
    acceptance_releases: list[ParsedRelease] = []
    for source in manifest.sources:
        payload = load_workbook_payload(source, cache_dir)
        sheets = read_workbook_sheets(payload)
        patient_releases.append(
            parse_patient_journey_workbook(source, ledger.release(source.release_code), sheets)
        )
        acceptance_releases.append(parse_offer_acceptance_workbook(manifest, source, sheets))
    return build_patient_journey_panel(
        patient_releases=tuple(patient_releases),
        acceptance_releases=tuple(acceptance_releases),
        config=config,
        ledger=ledger,
        sources=manifest.sources,
    )


def patient_journey_panel_table(rows: tuple[PatientJourneyPanelRow, ...]) -> pa.Table:
    """Return the exact v2 panel schema in stable target-cohort and program order."""
    keys = [(row.feature_release_code, row.target_release_code, row.program_key) for row in rows]
    if len(keys) != len(set(keys)):
        raise PatientJourneyPanelError("Patient-journey panel keys must be unique.")
    ordered = tuple(
        sorted(
            rows,
            key=lambda row: (
                row.target_listing_cohort_start,
                row.target_release_code,
                row.program_key,
            ),
        )
    )
    arrays = [
        pa.array([getattr(row, field.name) for row in ordered], type=field.type)
        for field in PATIENT_JOURNEY_PANEL_SCHEMA
    ]
    return pa.Table.from_arrays(arrays, schema=PATIENT_JOURNEY_PANEL_SCHEMA)
