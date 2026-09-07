"""Compare V2 predictions with published outcomes in percentage points.

One prediction represents a program and listing cohort, not a patient. In a
hypothetical example, predicting 40% against a published 35% gives an absolute
error of 5 percentage points and a signed error of +5. Summaries and program
resampling describe the original exploratory study; they do not establish
future accuracy.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median

import numpy as np


class PatientJourneyEvaluationError(ValueError):
    """Raised when V2 metric evidence is missing, unpaired, or ill-defined."""


@dataclass(frozen=True)
class EvaluationPrediction:
    """One program/listing cohort prediction and its calculated percentage-point error."""

    program_key: str
    feature_release_code: str
    target_release_code: str
    model: str
    training_pairs: tuple[tuple[str, str], ...]
    target_n: int
    target_published_percent: float
    predicted_proportion: float
    predicted_percent: float
    absolute_error_percentage_points: float
    signed_error_percentage_points: float
    volume_quartile: int
    first_observed_program: bool
    any_model_feature_missing: bool


@dataclass(frozen=True)
class EvaluationSummary:
    """Error sizes and prediction-versus-outcome agreement for one model.

    Error measures use percentage points. ``n`` counts program/cohort rows;
    candidate-volume weighting emphasizes larger listing groups without
    measuring patient-level prediction accuracy.
    """

    n: int
    target_releases: tuple[str, ...]
    target_release_balanced_mae_percentage_points: float
    row_pooled_mae_percentage_points: float
    candidate_volume_weighted_mae_percentage_points: float
    median_absolute_error_percentage_points: float
    mean_signed_error_percentage_points: float
    calibration_intercept: float | None
    calibration_slope: float | None
    calibration_scale: str
    calibration_unavailable_reason: str | None


@dataclass(frozen=True)
class BootstrapInterval:
    """Interval for the difference in average absolute error on the same programs.

    Values are challenger minus comparator in percentage points, so negative
    values favor the challenger. Whole programs are resampled, keeping all of
    each program's repeated cohort rows together.
    """

    point_estimate: float
    lower: float
    upper: float
    resamples: int
    seed: int


def _text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise PatientJourneyEvaluationError(f"Evaluation field {field!r} must be text.")
    return value


def _integer(row: Mapping[str, object], field: str) -> int:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PatientJourneyEvaluationError(f"Evaluation field {field!r} must be an integer.")
    return value


def assign_within_release_volume_quartiles(
    rows: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], int]:
    """Group each release's programs into four ordered listing-count groups.

    Sort by ``target_n`` (listed candidates) and then program key to break ties.
    These quartiles describe volume, not program performance.
    """
    if not rows:
        raise PatientJourneyEvaluationError("Volume strata require at least one row.")
    by_release: dict[str, list[Mapping[str, object]]] = {}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        program = _text(row, "program_key")
        release = _text(row, "target_release_code")
        target_n = _integer(row, "target_n")
        if target_n < 0:
            raise PatientJourneyEvaluationError("Target N must be nonnegative.")
        key = (program, release)
        if key in seen:
            raise PatientJourneyEvaluationError(f"Volume rows duplicate {key!r}.")
        seen.add(key)
        by_release.setdefault(release, []).append(row)

    assignments: dict[tuple[str, str], int] = {}
    for release in sorted(by_release):
        ordered = sorted(
            by_release[release],
            key=lambda row: (_integer(row, "target_n"), _text(row, "program_key")),
        )
        count = len(ordered)
        for rank, row in enumerate(ordered):
            quartile = min(4, 1 + math.floor(4 * rank / count))
            assignments[(_text(row, "program_key"), release)] = quartile
    return assignments


def _mean(values: Sequence[float], *, context: str) -> float:
    if not values:
        raise PatientJourneyEvaluationError(f"{context} cannot be empty.")
    if any(not math.isfinite(value) for value in values):
        raise PatientJourneyEvaluationError(f"{context} must contain finite values.")
    return sum(values) / len(values)


def _balanced_mae(predictions: Sequence[EvaluationPrediction]) -> float:
    by_release: dict[str, list[float]] = {}
    for row in predictions:
        by_release.setdefault(row.target_release_code, []).append(
            row.absolute_error_percentage_points
        )
    return _mean(
        [
            _mean(by_release[release], context=f"Target release {release} errors")
            for release in sorted(by_release)
        ],
        context="Target-release MAEs",
    )


def _calibration(
    predictions: Sequence[EvaluationPrediction],
) -> tuple[float | None, float | None, str | None]:
    counts: dict[str, int] = {}
    for row in predictions:
        counts[row.target_release_code] = counts.get(row.target_release_code, 0) + 1
    weights = np.asarray(
        [1.0 / counts[row.target_release_code] for row in predictions], dtype=np.float64
    )
    predicted = np.asarray([row.predicted_percent for row in predictions], dtype=np.float64)
    observed = np.asarray([row.target_published_percent for row in predictions], dtype=np.float64)
    weight_sum = float(weights.sum())
    predicted_mean = float(np.dot(weights, predicted) / weight_sum)
    observed_mean = float(np.dot(weights, observed) / weight_sum)
    centered = predicted - predicted_mean
    denominator = float(np.dot(weights, centered * centered))
    if denominator <= np.finfo(np.float64).eps:
        return None, None, "predicted_percentage_points_have_zero_variance"
    slope = float(np.dot(weights, centered * (observed - observed_mean)) / denominator)
    intercept = observed_mean - slope * predicted_mean
    return intercept, slope, None


def summarize_predictions(
    predictions: Sequence[EvaluationPrediction],
) -> EvaluationSummary:
    """Measure one model's errors using the original fixed averaging rules.

    The primary mean absolute error (MAE) averages each target release's MAE
    equally. Other summaries pool rows or weight errors by listed-candidate
    count. Positive signed error means predictions are too high on average.
    Calibration fits observed = intercept + slope * predicted in percentage
    points, with each release given equal total weight; constant predictions
    leave this check unavailable with a reason.
    """
    if not predictions:
        raise PatientJourneyEvaluationError("Prediction summary requires at least one row.")
    if len({row.model for row in predictions}) != 1:
        raise PatientJourneyEvaluationError("Prediction summary requires exactly one model.")
    if any(row.target_n <= 0 for row in predictions):
        raise PatientJourneyEvaluationError("Prediction target N must be positive.")
    absolute = [row.absolute_error_percentage_points for row in predictions]
    signed = [row.signed_error_percentage_points for row in predictions]
    weighted_n = sum(row.target_n for row in predictions)
    intercept, slope, unavailable_reason = _calibration(predictions)
    return EvaluationSummary(
        n=len(predictions),
        target_releases=tuple(sorted({row.target_release_code for row in predictions})),
        target_release_balanced_mae_percentage_points=_balanced_mae(predictions),
        row_pooled_mae_percentage_points=_mean(absolute, context="Absolute errors"),
        candidate_volume_weighted_mae_percentage_points=(
            sum(row.target_n * row.absolute_error_percentage_points for row in predictions)
            / weighted_n
        ),
        median_absolute_error_percentage_points=median(absolute),
        mean_signed_error_percentage_points=_mean(signed, context="Signed errors"),
        calibration_intercept=intercept,
        calibration_slope=slope,
        calibration_scale="percentage_points",
        calibration_unavailable_reason=unavailable_reason,
    )


def _paired_rows(
    challenger: Sequence[EvaluationPrediction], comparator: Sequence[EvaluationPrediction]
) -> tuple[
    dict[tuple[str, str, str], EvaluationPrediction],
    dict[tuple[str, str, str], EvaluationPrediction],
]:
    def index(
        rows: Sequence[EvaluationPrediction], context: str
    ) -> dict[tuple[str, str, str], EvaluationPrediction]:
        result: dict[tuple[str, str, str], EvaluationPrediction] = {}
        for row in rows:
            key = (row.program_key, row.feature_release_code, row.target_release_code)
            if key in result:
                raise PatientJourneyEvaluationError(f"{context} duplicates paired key {key!r}.")
            result[key] = row
        return result

    challenger_by_key = index(challenger, "Challenger")
    comparator_by_key = index(comparator, "Comparator")
    if set(challenger_by_key) != set(comparator_by_key):
        raise PatientJourneyEvaluationError(
            "Paired comparison requires identical program/release rows."
        )
    for key in challenger_by_key:
        left = challenger_by_key[key]
        right = comparator_by_key[key]
        if (
            left.target_n != right.target_n
            or left.target_published_percent != right.target_published_percent
        ):
            raise PatientJourneyEvaluationError(f"Paired target evidence disagrees for {key!r}.")
    return challenger_by_key, comparator_by_key


def paired_clustered_bootstrap_interval(
    challenger: Sequence[EvaluationPrediction],
    comparator: Sequence[EvaluationPrediction],
    *,
    resamples: int,
    seed: int,
    percentiles: tuple[float, float],
) -> BootstrapInterval:
    """Resample whole programs to describe uncertainty in their paired error difference.

    Each sampled program brings all its cohort rows into both models' samples.
    For each sample, subtract comparator from challenger MAE, giving each target
    release equal weight. The resulting percentile interval stays descriptive;
    resampling these programs does not create a new evaluation period.
    """
    if resamples <= 0:
        raise PatientJourneyEvaluationError("Bootstrap resamples must be positive.")
    lower_percentile, upper_percentile = percentiles
    if not 0 <= lower_percentile < upper_percentile <= 100:
        raise PatientJourneyEvaluationError("Bootstrap percentiles must be ordered in [0, 100].")
    challenger_by_key, comparator_by_key = _paired_rows(challenger, comparator)
    keys_by_program: dict[str, list[tuple[str, str, str]]] = {}
    for key in sorted(challenger_by_key):
        keys_by_program.setdefault(key[0], []).append(key)
    programs = tuple(sorted(keys_by_program))
    if not programs:
        raise PatientJourneyEvaluationError("Bootstrap comparison requires at least one program.")

    point_estimate = _balanced_mae(tuple(challenger_by_key.values())) - _balanced_mae(
        tuple(comparator_by_key.values())
    )
    generator = np.random.default_rng(seed)
    differences = np.empty(resamples, dtype=np.float64)
    for index in range(resamples):
        sampled = generator.choice(programs, size=len(programs), replace=True)
        challenger_sample: list[EvaluationPrediction] = []
        comparator_sample: list[EvaluationPrediction] = []
        for program in sampled:
            for key in keys_by_program[str(program)]:
                challenger_sample.append(challenger_by_key[key])
                comparator_sample.append(comparator_by_key[key])
        differences[index] = _balanced_mae(challenger_sample) - _balanced_mae(comparator_sample)
    lower, upper = np.percentile(
        differences,
        [lower_percentile, upper_percentile],
        method="linear",
    )
    return BootstrapInterval(
        point_estimate=point_estimate,
        lower=float(lower),
        upper=float(upper),
        resamples=resamples,
        seed=seed,
    )
