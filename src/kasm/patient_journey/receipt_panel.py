"""Line up origin-visible programs with later receipt, enforcing public-data timing."""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from statistics import mean
from typing import cast

from kasm.config import SourceRecord
from kasm.data.parse import ProgramSignal
from kasm.patient_journey.ledger import MetricFamily
from kasm.patient_journey.panel import (
    PatientJourneyPanelError,
    _index_acceptance_release,
    _validate_rate_rows,
    _validate_wait_rows,
)
from kasm.patient_journey.receipt_config import ReceiptConfig, ReceiptError, validate_receipt_config
from kasm.patient_journey.receipt_sources import ReceiptOutcome, ReceiptRelease, ReceiptSources

_DEFAULT_CONFIG = ReceiptConfig()


@dataclass(frozen=True)
class ReceiptPanel:
    """One row per program and fixed listing cohort, including unknown later outcomes."""

    rows: tuple[dict[str, object], ...]
    qa: dict[str, object]


def _publication_bounds(source: SourceRecord) -> tuple[date, date]:
    """Use conservative internal bounds without changing the source's displayed precision."""
    if source.published_precision == "day":
        day = date.fromisoformat(source.published_value)
        return day, day
    year, month = (int(part) for part in source.published_value.split("-"))
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def publication_available(source: SourceRecord, origin: SourceRecord) -> bool:
    """A report at the prediction origin is available, as are definitely earlier reports."""
    if source.release_code == origin.release_code:
        return source == origin
    return _publication_bounds(source)[1] <= _publication_bounds(origin)[0]


def _unique[T](values: Sequence[T], keys: Sequence[str], context: str) -> dict[str, T]:
    if len(keys) != len(set(keys)):
        raise ReceiptError(f"{context} has duplicate program records.")
    return dict(zip(keys, values, strict=True))


def _validate_release(release: ReceiptRelease) -> None:
    identities = _unique(
        release.identities, [row.program_key for row in release.identities], "Directory"
    )
    _unique(release.outcomes, [row.program_key for row in release.outcomes], "Receipt outcome")
    rates = _unique(
        release.transplant_rates,
        [row.program_key for row in release.transplant_rates],
        "Transplant rate",
    )
    waits = _unique(
        release.wait_times, [row.program_key for row in release.wait_times], "Wait time"
    )
    signal_keys = [f"{row.program_key}/{row.offer_group}" for row in release.acceptance.signals]
    if len(signal_keys) != len(set(signal_keys)):
        raise ReceiptError("Acceptance has duplicate program/group records.")
    for records in (
        release.outcomes,
        release.transplant_rates,
        release.wait_times,
        release.acceptance.signals,
    ):
        if any(row.program_key not in identities for row in records):
            raise ReceiptError("Source measurement belongs to a program outside its directory.")
    for row in release.identities:
        if row.program_key != f"{row.center_code}:{row.center_type}":
            raise ReceiptError("Composite program identity disagrees with code and type.")
    _validate_methodology(release)
    try:
        _validate_rate_rows(release.source.release_code, rates, release.methodology)
        _validate_wait_rows(release.source.release_code, waits, release.methodology)
        _index_acceptance_release(release.acceptance, identities, release.source)
    except PatientJourneyPanelError as exc:
        raise ReceiptError(str(exc)) from exc


def _validate_methodology(release: ReceiptRelease) -> None:
    """Bind parsed measurement records to the independently checked source dates."""
    method, source, periods = release.methodology, release.source, release.periods
    if (
        method.release_code != source.release_code
        or method.published_value != source.published_value
        or method.published_precision != source.published_precision
        or method.source_url != source.url
        or method.source_sha256 != source.download_sha256
    ):
        raise ReceiptError("Release methodology disagrees with source identity or publication.")
    families = tuple(metric.family for metric in method.metrics)
    if len(families) != 3 or set(families) != {"patient_outcome", "transplant_rate", "wait_time"}:
        raise ReceiptError("Receipt methodology needs exactly its three dated metric families.")
    expected_periods: tuple[tuple[MetricFamily, tuple[date, date, date]], ...] = (
        (
            "patient_outcome",
            (periods.listing_start, periods.listing_end, periods.outcome_follow_up_bound),
        ),
        ("wait_time", (periods.wait_start, periods.wait_end, periods.wait_follow_up_end)),
    )
    for family, expected in expected_periods:
        metric = method.metric(family)
        if (metric.measurement_start, metric.measurement_end, metric.follow_up_end) != expected:
            raise ReceiptError(
                f"{family} methodology dates disagree with independent period evidence."
            )
    for metric in method.metrics:
        if not metric.measurement_start <= metric.measurement_end <= metric.follow_up_end:
            raise ReceiptError("Source measurement and follow-up dates are reversed.")


def _check_pair(feature: ReceiptRelease, target: ReceiptRelease, config: ReceiptConfig) -> None:
    start = target.periods.listing_start
    origin_start, _ = _publication_bounds(feature.source)
    offset = (origin_start.year - start.year) * 12 + origin_start.month - start.month
    if not 0 <= offset <= config.max_prediction_origin_month_offset:
        raise ReceiptError("Prediction origin is outside the allowed target-start months.")
    if publication_available(target.source, feature.source):
        raise ReceiptError("The target report must be published after the prediction origin.")
    metric_ends = (
        feature.periods.outcome_follow_up_bound,
        feature.periods.wait_end,
        feature.periods.wait_follow_up_end,
        feature.methodology.metric("transplant_rate").measurement_end,
        feature.methodology.metric("transplant_rate").follow_up_end,
        date(feature.source.cohort_year, 12, 31),
    )
    if any(end >= start for end in metric_ends):
        raise ReceiptError(
            "Every predictor measurement and follow-up must end before target listing."
        )


def validate_receipt_timing(
    sources: ReceiptSources, config: ReceiptConfig
) -> dict[str, ReceiptRelease]:
    """Reject overlapping cohorts and training labels unavailable at the evaluated origin."""
    validate_receipt_config(config)
    releases = _unique(
        sources.releases,
        [release.source.release_code for release in sources.releases],
        "Source release",
    )
    if not sources.pairs or len(set(sources.pairs)) != len(sources.pairs):
        raise ReceiptError("Study pairs must be nonempty and unique.")
    cohorts: list[tuple[date, date]] = []
    for release in sources.releases:
        _validate_release(release)
        start, end = release.periods.listing_start, release.periods.listing_end
        if (start.month, start.day, end.month, end.day, end.year) != (7, 1, 6, 30, start.year + 1):
            raise ReceiptError("Each source listing cohort must be a full July-June year.")
        cohorts.append((start, end))
    if any(
        left[1] >= right[0]
        for left, right in zip(sorted(cohorts), sorted(cohorts)[1:], strict=False)
    ):
        raise ReceiptError("Source listing cohorts overlap; their outcomes cannot be pooled.")
    for feature, target in sources.pairs:
        if feature not in releases or target not in releases:
            raise ReceiptError("Study pair references a source without independently bound dates.")
        _check_pair(releases[feature], releases[target], config)
    evaluations = [evaluation for evaluation, _ in sources.folds]
    if not evaluations or len(evaluations) != len(set(evaluations)):
        raise ReceiptError("Evaluation origins must be nonempty and unique.")
    for evaluation, training in sources.folds:
        if evaluation not in sources.pairs or not training or len(set(training)) != len(training):
            raise ReceiptError("Every evaluation needs unique configured training pairs.")
        for pair in training:
            if pair not in sources.pairs or pair == evaluation:
                raise ReceiptError("An evaluation pair cannot enter its own training data.")
            if not publication_available(releases[pair[1]].source, releases[evaluation[0]].source):
                raise ReceiptError("A training outcome was not public at the prediction origin.")
            if (
                releases[pair[1]].periods.listing_end
                >= releases[evaluation[1]].periods.listing_start
            ):
                raise ReceiptError("Training and evaluation listing cohorts must not overlap.")
    return releases


def _history(
    program: str,
    feature: ReceiptRelease,
    target: ReceiptRelease,
    releases: Sequence[ReceiptRelease],
) -> tuple[tuple[ReceiptRelease, ReceiptOutcome], ...]:
    result: list[tuple[ReceiptRelease, ReceiptOutcome]] = []
    for earlier in sorted(releases, key=lambda item: _publication_bounds(item.source)[0]):
        if not publication_available(earlier.source, feature.source):
            continue
        if earlier.periods.outcome_follow_up_bound >= target.periods.listing_start:
            raise ReceiptError("Historical outcome follow-up must end before target listing.")
        outcome = next((row for row in earlier.outcomes if row.program_key == program), None)
        if (
            outcome is not None
            and outcome.values.target_n is not None
            and outcome.values.target_n > 0
            and outcome.values.target_proportion is not None
        ):
            result.append((earlier, outcome))
    return tuple(result)


def _access_values(program: str, feature: ReceiptRelease) -> dict[str, object]:
    rate = next((row for row in feature.transplant_rates if row.program_key == program), None)
    wait = next((row for row in feature.wait_times if row.program_key == program), None)
    result: dict[str, object] = {
        "transplant_rate_ratio": rate.transplant_rate_ratio if rate else None,
        "transplant_rate_person_years": rate.person_years if rate else None,
        "wait_time_months_25th_percentile": wait.months_25th_percentile if wait else None,
        "wait_time_raw_value": wait.raw_value if wait else None,
    }
    result["missing_transplant_rate_ratio"] = result["transplant_rate_ratio"] is None
    result["missing_transplant_rate_person_years"] = result["transplant_rate_person_years"] is None
    result["missing_wait_time"] = result["wait_time_months_25th_percentile"] is None
    signals: dict[str, ProgramSignal] = {
        row.offer_group: row for row in feature.acceptance.signals if row.program_key == program
    }
    for group, label in (
        ("overall", "overall"),
        ("low", "low"),
        ("medium", "medium"),
        ("high", "high"),
        ("hard-to-place", "hard_to_place"),
    ):
        signal = signals.get(group)
        value = signal.oar_mean if signal else None
        result[f"acceptance_{label}_oar"] = value
        result[f"missing_acceptance_{label}_oar"] = value is None
    overall = signals.get("overall")
    result["acceptance_overall_expected_acceptances"] = (
        overall.expected_acceptances if overall else None
    )
    result["acceptance_overall_oar_lower"] = overall.oar_lower if overall else None
    result["acceptance_overall_oar_upper"] = overall.oar_upper if overall else None
    result["missing_acceptance_expected_acceptances"] = (
        result["acceptance_overall_expected_acceptances"] is None
    )
    result["missing_acceptance_interval"] = (
        result["acceptance_overall_oar_lower"] is None
        or result["acceptance_overall_oar_upper"] is None
    )
    return result


def _row(
    program: str,
    feature: ReceiptRelease,
    target: ReceiptRelease,
    releases: Sequence[ReceiptRelease],
    config: ReceiptConfig,
) -> dict[str, object]:
    history = _history(program, feature, target, releases)
    prior_source, prior_outcome = history[-1] if history else (None, None)
    prior = prior_outcome.values if prior_outcome else None
    outcome = next((row for row in target.outcomes if row.program_key == program), None)
    values = outcome.values if outcome else None
    reasons: list[str] = []
    if outcome is None:
        reasons.append("missing_future_report")
    elif values is not None and (values.target_proportion is None or values.target_n is None):
        reasons.append("missing_target_component_or_denominator")
    if (
        values is not None
        and values.target_n is not None
        and values.target_n < config.primary_min_target_n
    ):
        reasons.append("target_n_below_10")
    if not history:
        reasons.append("missing_prior_receipt")
    identity = next(row for row in feature.identities if row.program_key == program)
    origin_start, _ = _publication_bounds(feature.source)
    result: dict[str, object] = {
        "program_key": program,
        "center_code": identity.center_code,
        "center_type": identity.center_type,
        "feature_release_code": feature.source.release_code,
        "target_release_code": target.source.release_code,
        "prediction_origin_value": feature.source.published_value,
        "prediction_origin_precision": feature.source.published_precision,
        "prediction_origin_month_offset": (origin_start.year - target.periods.listing_start.year)
        * 12
        + origin_start.month
        - target.periods.listing_start.month,
        "target_published_value": target.source.published_value,
        "target_published_precision": target.source.published_precision,
        "target_listing_start": target.periods.listing_start.isoformat(),
        "target_listing_end": target.periods.listing_end.isoformat(),
        "target_follow_up_bound": target.periods.outcome_follow_up_bound.isoformat(),
        "target_n": values.target_n if values else None,
        "derived_receipt_percent": values.derived_receipt_percent if values else None,
        "target_proportion": values.target_proportion if values else None,
        "target_logit": values.target_logit if values else None,
        "target_label": "Derived from published deceased-donor components",
        "primary_analytic_eligible": not reasons,
        "eligibility_reasons": reasons,
        "prior_target_n": prior.target_n if prior else None,
        "prior_target_proportion": prior.target_proportion if prior else None,
        "prior_target_logit": prior.target_logit if prior else None,
        "prior_target_release_code": prior_source.source.release_code if prior_source else None,
        "history_release_codes": [release.source.release_code for release, _ in history],
        "historical_mean_target_proportion": mean(
            outcome.values.target_proportion
            for _, outcome in history
            if outcome.values.target_proportion is not None
        )
        if history
        else None,
        "feature_source_sha256": feature.source.download_sha256,
        "target_source_sha256": target.source.download_sha256,
    }
    result.update(_access_values(program, feature))
    return result


def build_receipt_panel(
    sources: ReceiptSources, config: ReceiptConfig = _DEFAULT_CONFIG
) -> ReceiptPanel:
    """Keep every origin-visible program and attach unknown future targets without guessing."""
    releases = validate_receipt_timing(sources, config)
    rows: list[dict[str, object]] = []
    pair_qa: dict[str, object] = {}
    for feature_code, target_code in sources.pairs:
        feature, target = releases[feature_code], releases[target_code]
        origin_keys = {row.program_key for row in feature.identities}
        target_keys = {row.program_key for row in target.outcomes}
        target_directory = {row.program_key for row in target.identities}
        pair_rows = [
            _row(key, feature, target, sources.releases, config) for key in sorted(origin_keys)
        ]
        rows.extend(pair_rows)
        reasons: dict[str, int] = {}
        for row in pair_rows:
            for reason in cast(list[str], row["eligibility_reasons"]):
                reasons[reason] = reasons.get(reason, 0) + 1
        pair_qa[f"{feature_code}->{target_code}"] = {
            "origin_programs": len(origin_keys),
            "eligible_rows": sum(row["primary_analytic_eligible"] is True for row in pair_rows),
            "missing_future_programs": sorted(origin_keys - target_keys),
            "target_only_programs": sorted(target_directory - origin_keys),
            "programs_absent_from_target_directory": sorted(origin_keys - target_directory),
            "missing_outcome_in_target_directory": sorted(
                (origin_keys & target_directory) - target_keys
            ),
            "exclusion_reasons": reasons,
        }
    return ReceiptPanel(
        tuple(rows),
        {
            "pairs": pair_qa,
            "source_exclusions": dict(sources.exclusions),
            "source_config_sha256": sources.config_sha256,
        },
    )
