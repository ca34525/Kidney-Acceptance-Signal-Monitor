"""Apply the fixed rules for displaying a V1 prediction and its uncertainty band.

The point prediction and band must pass separate checks. Their 2025 evidence is
descriptive: neither passing nor failing these rules establishes clinical safety.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil, isfinite

import numpy as np
from scipy.stats import beta  # type: ignore[import-untyped]

from kasm.modeling.challenger import RidgePrediction
from kasm.modeling.experiment import ExperimentConfig


@dataclass(frozen=True)
class ResidualBandCalibration:
    """Band half-width on the log-OAR scale, chosen from one held-out year's errors."""

    calibration_target_year: int
    nominal_coverage: float
    sample_size: int
    order_statistic_rank: int
    absolute_log_residual_radius: float


@dataclass(frozen=True)
class PairedAbsoluteErrors:
    """Program-key-paired challenger and persistence errors."""

    program_key: str
    challenger_absolute_error: float
    persistence_absolute_error: float


@dataclass(frozen=True)
class BootstrapInterval:
    """Descriptive percentile interval for paired MAE differences."""

    observed_mean_difference: float
    lower: float
    upper: float
    resamples: int
    seed: int
    percentiles: tuple[float, ...]
    percentile_method: str


@dataclass(frozen=True)
class PointPromotion:
    """Replay point-promotion result, independent of band visibility."""

    promoted: bool
    displayed_model: str
    skill_over_persistence: float
    failed_criteria: tuple[str, ...]


@dataclass(frozen=True)
class BandPromotion:
    """Replay empirical-band display result."""

    display_band: bool
    coverage: float
    exact_interval_lower: float
    exact_interval_upper: float
    mean_width_relative_to_persistence: float
    failed_criteria: tuple[str, ...]


def _finite_nonnegative(value: float, context: str) -> float:
    result = float(value)
    if not isfinite(result) or result < 0:
        raise ValueError(f"{context} must be finite and nonnegative.")
    return result


def calibrate_empirical_band(
    predictions: Sequence[RidgePrediction], *, config: ExperimentConfig
) -> ResidualBandCalibration:
    """Choose band half-width from absolute log-OAR errors in held-out 2024 only.

    The sorted-error position is min(n, ceil((n + 1) * nominal_coverage)). The
    resulting band describes coverage across programs, not a guarantee for one program.
    """
    if not predictions:
        raise ValueError("Empirical-band calibration requires held-out predictions.")
    expected_year = config.band_calibration_target_year
    if any(row.target_cohort_year != expected_year for row in predictions):
        raise ValueError(
            f"Empirical-band calibration requires exactly target year {expected_year}."
        )
    residuals = sorted(
        _finite_nonnegative(row.absolute_error_log_oar, "Absolute log residual")
        for row in predictions
    )
    sample_size = len(residuals)
    rank = min(sample_size, ceil((sample_size + 1) * config.band_nominal_coverage))
    return ResidualBandCalibration(
        calibration_target_year=expected_year,
        nominal_coverage=config.band_nominal_coverage,
        sample_size=sample_size,
        order_statistic_rank=rank,
        absolute_log_residual_radius=residuals[rank - 1],
    )


def paired_bootstrap_mae_difference_interval(
    pairs: Sequence[PairedAbsoluteErrors], *, config: ExperimentConfig
) -> BootstrapInterval:
    """Resample programs to describe uncertainty in the two models' error difference.

    Each row pairs one program's absolute log-OAR errors. Challenger minus persistence
    is negative when the challenger errs less. The bootstrap uses the fixed random
    seed and resample count; it provides no new time period for validation.
    """
    if not pairs:
        raise ValueError("Paired bootstrap requires at least one program key.")
    ordered = sorted(pairs, key=lambda row: row.program_key)
    keys = [row.program_key for row in ordered]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise ValueError("Paired bootstrap requires a unique program_key for every pair.")
    differences = np.asarray(
        [
            _finite_nonnegative(row.challenger_absolute_error, "Challenger absolute error")
            - _finite_nonnegative(row.persistence_absolute_error, "Persistence absolute error")
            for row in ordered
        ],
        dtype=np.float64,
    )
    rng = np.random.default_rng(config.bootstrap_seed)
    sampled_indices = rng.integers(
        0,
        len(differences),
        size=(config.bootstrap_resamples, len(differences)),
    )
    sampled_means = differences[sampled_indices].mean(axis=1)
    bounds = np.percentile(
        sampled_means,
        config.bootstrap_percentiles,
        method="linear",
    )
    return BootstrapInterval(
        observed_mean_difference=float(differences.mean()),
        lower=float(bounds[0]),
        upper=float(bounds[1]),
        resamples=config.bootstrap_resamples,
        seed=config.bootstrap_seed,
        percentiles=config.bootstrap_percentiles,
        percentile_method=config.bootstrap_percentile_method,
    )


def _relative_worsening(challenger: float, persistence: float) -> float:
    if persistence == 0:
        return 0.0 if challenger == 0 else float("inf")
    return challenger / persistence - 1


def assess_point_promotion(
    *,
    challenger_mae: float,
    persistence_mae: float,
    bootstrap_lower: float,
    bootstrap_upper: float,
    challenger_bias: float,
    persistence_bias: float,
    challenger_low_volume_mae: float,
    persistence_low_volume_mae: float,
    low_volume_rows: int,
    config: ExperimentConfig,
) -> PointPromotion:
    """Apply every prespecified 2025 replay point-promotion criterion."""
    challenger = _finite_nonnegative(challenger_mae, "Challenger MAE")
    persistence = _finite_nonnegative(persistence_mae, "Persistence MAE")
    challenger_low = _finite_nonnegative(challenger_low_volume_mae, "Low-volume challenger MAE")
    persistence_low = _finite_nonnegative(persistence_low_volume_mae, "Low-volume persistence MAE")
    finite_values = (bootstrap_lower, bootstrap_upper, challenger_bias, persistence_bias)
    if not all(isfinite(value) for value in finite_values):
        raise ValueError("Bootstrap bounds and biases must be finite.")
    if bootstrap_lower > bootstrap_upper:
        raise ValueError("Bootstrap lower bound cannot exceed its upper bound.")
    if isinstance(low_volume_rows, bool) or low_volume_rows < 0:
        raise ValueError("Low-volume row count must be a nonnegative integer.")

    skill = 0.0 if persistence == 0 else 1 - challenger / persistence
    failed: list[str] = []
    if not config.forecast_activation_attempted:
        failed.append("forecast_activation_not_attempted")
    if skill < config.point_minimum_skill_over_persistence:
        failed.append("minimum_skill_over_persistence")
    if config.point_bootstrap_interval_must_be_below_zero and bootstrap_upper >= 0:
        failed.append("bootstrap_interval_below_zero")
    if abs(challenger_bias) > config.point_maximum_absolute_mean_signed_log_error:
        failed.append("maximum_absolute_mean_signed_log_error")
    if config.point_bias_must_not_exceed_persistence and abs(challenger_bias) > abs(
        persistence_bias
    ):
        failed.append("bias_not_exceed_persistence")
    if low_volume_rows < config.minimum_lowest_quartile_rows:
        failed.append("lowest_quartile_minimum_rows")
    if _relative_worsening(challenger_low, persistence_low) > (
        config.point_maximum_lowest_quartile_relative_worsening
    ):
        failed.append("lowest_quartile_relative_worsening")
    promoted = not failed
    return PointPromotion(
        promoted=promoted,
        displayed_model="ridge" if promoted else "persistence",
        skill_over_persistence=skill,
        failed_criteria=tuple(failed),
    )


def clopper_pearson_interval(
    *, successes: int, trials: int, confidence_level: float
) -> tuple[float, float]:
    """Describe uncertainty in a covered fraction using an exact binomial interval.

    Here successes count covered outcomes and trials count all evaluated outcomes.
    The two-sided Clopper-Pearson limits are proportions between zero and one.
    """
    if isinstance(successes, bool) or isinstance(trials, bool):
        raise ValueError("Successes and trials must be integers.")
    if trials <= 0 or successes < 0 or successes > trials:
        raise ValueError("Require 0 <= successes <= trials and trials > 0.")
    if not isfinite(confidence_level) or not 0 < confidence_level < 1:
        raise ValueError("Confidence level must lie strictly between zero and one.")
    alpha = 1 - confidence_level
    lower = 0.0 if successes == 0 else float(beta.ppf(alpha / 2, successes, trials - successes + 1))
    upper = (
        1.0
        if successes == trials
        else float(beta.ppf(1 - alpha / 2, successes + 1, trials - successes))
    )
    return lower, upper


def assess_band_promotion(
    *,
    covered: int,
    total: int,
    challenger_mean_width: float,
    persistence_mean_width: float,
    config: ExperimentConfig,
) -> BandPromotion:
    """Apply the exact-coverage and relative-width band display gate."""
    interval_lower, interval_upper = clopper_pearson_interval(
        successes=covered, trials=total, confidence_level=0.95
    )
    challenger_width = _finite_nonnegative(challenger_mean_width, "Challenger mean width")
    persistence_width = _finite_nonnegative(persistence_mean_width, "Persistence mean width")
    relative_width = _relative_worsening(challenger_width, persistence_width) + 1
    failed: list[str] = []
    if not config.forecast_activation_attempted:
        failed.append("forecast_activation_not_attempted")
    nominal = config.band_nominal_coverage
    if config.band_exact_interval_must_include_nominal_coverage and not (
        interval_lower <= nominal <= interval_upper
    ):
        failed.append("exact_interval_includes_nominal_coverage")
    if relative_width > config.band_maximum_mean_width_relative_to_persistence:
        failed.append("maximum_mean_width_relative_to_persistence")
    return BandPromotion(
        display_band=not failed,
        coverage=covered / total,
        exact_interval_lower=interval_lower,
        exact_interval_upper=interval_upper,
        mean_width_relative_to_persistence=relative_width,
        failed_criteria=tuple(failed),
    )
