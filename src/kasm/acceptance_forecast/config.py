"""Require complete, fixed choices before describing or comparing predictions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STUDY_ID = "acceptance-forecast-0027"
OUTPUT_ROOT = "data/research/acceptance-forecast-0027"
GROUP_FIELDS = (
    "expected_acceptance_quartile",
    "earlier_oar_group",
    "predictor_missingness",
    "public_forecast_eligible",
    "first_observed_program",
)

POLICY_DEFAULTS = {
    "minimum_log_mae_improvement": 0.05,
    "maximum_year_mae_worsening": 0.10,
    "minimum_improved_years": 4,
    "maximum_absolute_log_bias": 0.05,
    "maximum_year_absolute_log_bias": 0.15,
    "maximum_tail_ratio": 1.10,
    "minimum_group_n": 30,
    "maximum_group_mae_worsening": 0.10,
    "large_worsening_log_threshold": 0.25,
    "maximum_large_worsening_fraction": 0.10,
    "band_nominal_coverage": 0.80,
    "band_confidence": 0.95,
    "maximum_band_width_ratio": 1.0,
}
COMPARISON_MODELS = (
    "persistence",
    "historical_mean",
    "ridge",
    "ridge_recent3",
    "adjusted_persistence",
)


class ForecastError(ValueError):
    """A required study choice or trusted input is missing or inconsistent."""


@dataclass(frozen=True)
class DiagnosticConfig:
    years: tuple[int, ...]
    models: tuple[str, ...]
    tolerances: tuple[float, ...]
    input_sha256: dict[str, str]
    release_identity: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class ComparisonConfig:
    years: tuple[int, ...]
    models: tuple[str, ...]
    alpha: float
    seed: int
    training_start: int
    warmup_year: int
    recent_window: int
    bootstrap_resamples: int
    bootstrap_seed: int
    policy: dict[str, Any]
    diagnostic_config_sha256: str
    raw: dict[str, Any]


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ForecastError(f"Settings contain a duplicate key: {key!r}.")
        result[key] = value
    return result


def read_settings(path: Path) -> dict[str, Any]:
    """Read an explicit JSON object, rejecting malformed external configuration."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ForecastError(f"Settings are missing, unreadable or invalid: {path}") from exc
    if not isinstance(value, dict):
        raise ForecastError("Settings must be a JSON object.")
    return value


def _same_choice(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            _same_choice(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _same_choice(left, right) for left, right in zip(actual, expected, strict=True)
        )
    return bool(actual == expected)


def require_exact(settings: dict[str, Any], expected: dict[str, Any]) -> None:
    """Prevent absent choices or unimplemented alternatives from silently changing the study."""
    for key, value in expected.items():
        if key not in settings or not _same_choice(settings[key], value):
            raise ForecastError(f"Settings field {key!r} must be exactly {value!r}.")


def load_diagnostic_config(path: Path) -> DiagnosticConfig:
    """Bind the original saved forecasts, their populations and error definitions."""
    raw = read_settings(path)
    fixed = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "phase": "saved_diagnostics",
        "years": [2021, 2022, 2023, 2024, 2025],
        "models": ["persistence", "ridge"],
        "tolerances": [0.1, 0.25, 0.5],
        "percentile_method": "linear",
        "output_root": OUTPUT_ROOT,
        "population": "original_analytic_with_public_subset",
        "aggregation": "equal_year_means_secondary_row_pooled_quantiles",
        "earlier_oar_cutpoints": [0.5, 1.0, 2.0],
        "groups": list(GROUP_FIELDS),
        "training_roles": {
            "2021": "2018-2020_alpha_selected_on_2021-2023",
            "2022": "2018-2021_alpha_selected_on_2021-2023",
            "2023": "2018-2022_alpha_selected_on_2021-2023",
            "2024": "2018-2023_validation_and_band_calibration",
            "2025": "2018-2023_original_frozen_fit_2024_band_only",
        },
        "percentage_denominator": "published_target_oar",
        "missing_targets": "count_exclude_never_zero",
        "pairing": "exact_program_year_unrounded_absolute_error_difference",
    }
    require_exact(raw, fixed)
    if set(raw) != set(fixed) | {"input_sha256", "release_identity"}:
        raise ForecastError("Diagnostic settings contain missing or unknown choices.")
    hashes = raw["input_sha256"]
    required = {
        "artifacts/release/release_manifest.json",
        "configs/data_sources.yaml",
        "configs/experiment.yaml",
        "configs/frozen_experiment.yaml",
    }
    if not isinstance(hashes, dict) or set(hashes) != required:
        raise ForecastError("Diagnostic input fingerprint set is incomplete.")
    for value in [*hashes.values(), raw["release_identity"]]:
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
        ):
            raise ForecastError("Input fingerprints must be lowercase SHA-256 values.")
    return DiagnosticConfig(
        tuple(raw["years"]),
        tuple(raw["models"]),
        tuple(raw["tolerances"]),
        hashes,
        raw["release_identity"],
        raw,
    )


def load_comparison_config(path: Path) -> ComparisonConfig:
    """Require the single enumerated comparison fixed after diagnosis, before scoring."""
    raw = read_settings(path)
    fixed = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "phase": "comparison_v1",
        "years": [2021, 2022, 2023, 2024, 2025],
        "models": list(COMPARISON_MODELS),
        "alpha": 10.0,
        "seed": 20260903,
        "training_start": 2018,
        "warmup_year": 2020,
        "recent_window": 3,
        "output_root": OUTPUT_ROOT,
        "bootstrap_resamples": 10000,
        "bootstrap_seed": 20260908,
        "bootstrap": "whole_program_paired_equal_year_percentile_linear_95_skip_empty_year",
        "policy": POLICY_DEFAULTS,
        "band": {
            "calibration": "previous_year_complete_procedure_out_of_sample",
            "minimum_n": 30,
            "nominal": 0.8,
            "rank": "min(n,ceil((n+1)*0.8))",
            "refit": "expanding_at_each_origin",
        },
        "tuning": "none_alpha10_inherited_retrospective_choice",
        "population": "original_analytic_with_public_subset",
        "publication": "same_release_or_latest_publication_before_earliest_origin",
        "selection_order": ["ridge", "adjusted_persistence", "ridge_recent3"],
        "stopping_rule": "report_all_five_once_no_design_revision",
    }
    require_exact(raw, fixed)
    if set(raw) != set(fixed) | {"diagnostic_config_sha256"}:
        raise ForecastError("Comparison settings contain missing or unknown choices.")
    fingerprint = raw["diagnostic_config_sha256"]
    if (
        not isinstance(fingerprint, str)
        or len(fingerprint) != 64
        or any(c not in "0123456789abcdef" for c in fingerprint)
    ):
        raise ForecastError("Comparison must pin the diagnostic input contract.")
    return ComparisonConfig(
        tuple(raw["years"]),
        tuple(raw["models"]),
        raw["alpha"],
        raw["seed"],
        raw["training_start"],
        raw["warmup_year"],
        raw["recent_window"],
        raw["bootstrap_resamples"],
        raw["bootstrap_seed"],
        raw["policy"],
        fingerprint,
        raw,
    )
