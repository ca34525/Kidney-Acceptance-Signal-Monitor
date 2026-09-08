"""Fix the separate receipt question and prevent writes to completed studies."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from kasm.patient_journey.config import ACCEPTANCE_FEATURES, ACCESS_FEATURES

ANALYSIS_ID = "kidney_deceased_donor_receipt_0023_v1"
OUTPUT_ROOT = Path("data/receipt-study/v1")
DEFAULT_CONFIG = Path("configs/receipt_study/experiment.yaml")
SOURCE_CONFIG = Path("configs/receipt_study/sources.json")
HISTORY_FEATURES = (
    "prior_target_logit",
    "historical_mean_target_proportion",
    "log1p_prior_target_n",
)
FEATURE_GROUPS = (
    ("history", HISTORY_FEATURES),
    ("history_access", HISTORY_FEATURES + ACCESS_FEATURES),
    ("history_access_acceptance", HISTORY_FEATURES + ACCESS_FEATURES + ACCEPTANCE_FEATURES),
)
BASELINES = ("persistence", "historical_mean")
CONTRASTS = tuple((name, baseline) for name, _ in FEATURE_GROUPS for baseline in BASELINES) + (
    ("history_access", "history"),
    ("history_access_acceptance", "history"),
    ("history_access_acceptance", "history_access"),
)


class ReceiptError(ValueError):
    """Raised when receipt-study inputs or execution violate the separate contract."""


@dataclass(frozen=True)
class ReceiptConfig:
    """Prespecified choices; source feasibility is fixed separately before fitting."""

    schema_version: int = 1
    analysis_id: str = ANALYSIS_ID
    target_scale: str = "derived_deceased_donor_receipt_percent"
    target_transform: str = "log((N*p+0.5)/(N*(1-p)+0.5))"
    denominator: str = "SAL_N_C"
    months_after_listing: int = 18
    primary_min_target_n: int = 10
    sensitivity_min_target_n: tuple[int, ...] = (20, 30)
    max_prediction_origin_month_offset: int = 1
    baselines: tuple[str, ...] = BASELINES
    feature_groups: tuple[tuple[str, tuple[str, ...]], ...] = FEATURE_GROUPS
    contrasts: tuple[tuple[str, str], ...] = CONTRASTS
    alpha: float = 1.0
    solver: str = "lsqr"
    tolerance: float = 1e-8
    max_iterations: int = 10000
    imputation: str = "training_fold_median_keep_empty"
    scaling: str = "training_fold_standard"
    primary_aggregation: str = "equal_origin_mean_absolute_error_percentage_points"
    signed_error: str = "prediction_minus_observed_equal_origin"
    volume_weighting: str = "within_origin_listing_n_then_equal_origin"
    bootstrap_resamples: int = 2000
    bootstrap_seed: int = 20260908
    bootstrap_percentiles: tuple[float, float] = (2.5, 97.5)
    bootstrap_max_attempt_factor: int = 100
    minimum_improvement_points: float = 0.5
    minimum_relative_improvement: float = 0.05
    maximum_absolute_bias_points: float = 2.0
    maximum_bias_worsening_points: float = 0.5
    minimum_evaluation_origins: int = 2
    output_root: str = OUTPUT_ROOT.as_posix()
    promotion_allowed: bool = False
    future_forecast_available: bool = False


def validate_receipt_config(config: ReceiptConfig) -> None:
    """Reject changed settings, including integer substitutes for booleans."""
    try:
        actual = json.dumps(asdict(config), sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ReceiptError("Settings disagree with the fixed receipt-study contract.") from exc
    if actual != json.dumps(asdict(ReceiptConfig()), sort_keys=True):
        raise ReceiptError("Settings disagree with the fixed receipt-study contract.")


def load_receipt_config(path: Path) -> ReceiptConfig:
    """Require every fixed choice explicitly in the human-readable configuration."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        actual = json.dumps(raw, sort_keys=True, allow_nan=False)
    except (OSError, UnicodeError, yaml.YAMLError, ValueError, TypeError) as exc:
        raise ReceiptError("Cannot read the fixed receipt-study configuration.") from exc
    if actual != json.dumps(asdict(ReceiptConfig()), sort_keys=True):
        raise ReceiptError("Settings disagree with the fixed receipt-study contract.")
    return ReceiptConfig()


def validate_receipt_destination(path: Path, *, repository_root: Path) -> Path:
    """Permit one run hash inside the study root without filesystem redirects."""
    if (
        path.is_absolute()
        or path.drive
        or ".." in path.parts
        or path.parent != OUTPUT_ROOT
        or re.fullmatch(r"[0-9a-f]{64}", path.name) is None
    ):
        raise ReceiptError("Output must be a relative run hash under data/receipt-study/v1.")
    root = repository_root.resolve()
    destination = root / path
    for current in (destination, *destination.parents):
        if current == root:
            break
        if current.is_symlink() or current.is_junction():
            raise ReceiptError("Output cannot traverse a filesystem link.")
    if not destination.resolve().is_relative_to(root / OUTPUT_ROOT):
        raise ReceiptError("Output escapes the fixed receipt-study root.")
    return destination
