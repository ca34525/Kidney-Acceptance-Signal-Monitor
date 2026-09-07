"""Fix which reported outcome components may describe the original evaluation period."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from kasm.patient_journey.followup_config import (
    ORIGINAL_BUNDLE_SHA256,
    ORIGINAL_EXPERIMENT_SHA256,
)

COMPONENT_FIELDS = ("SAL_CTXFNC_C18", "SAL_LTXFNC_C18", "SAL_CTXUNK_C18", "SAL_LTXUNK_C18")
OUTPUT_ROOT = Path("data/patient_journey_v2_followup/outcome_components_v1")
ANALYSIS_ID = "kidney_patient_journey_v2_followup_outcome_components_v1"
ERROR_MODELS = (
    "persistence",
    "available_cohort_reference",
    "historical_mean",
    "history",
    "history_acceptance",
    "history_access",
    "history_access_acceptance",
    "history_access_acceptance_safety",
)


class ComponentError(ValueError):
    """Raised when the source, calculation or output would change the agreed description."""


@dataclass(frozen=True)
class ComponentConfig:
    """One listing group, published percentages and stored errors; no fitting choices."""

    schema_version: int = 1
    analysis_id: str = ANALYSIS_ID
    original_bundle_sha256: str = ORIGINAL_BUNDLE_SHA256
    original_experiment_sha256: str = ORIGINAL_EXPERIMENT_SHA256
    output_root: str = OUTPUT_ROOT.as_posix()
    release_code: str = "2505"
    feature_release_code: str = "2205"
    listing_cohort_start: str = "2022-07-01"
    listing_cohort_end: str = "2023-06-30"
    follow_up_end: str = "2024-12-30"
    published_value: str = "2025-07-08"
    published_precision: str = "day"
    denominator: str = "SAL_N_C"
    months_after_listing: int = 18
    source_min_n: int = 10
    pdf_percentage_quantum: float = 0.1
    arithmetic_tolerance: float = 1e-12
    missing_markers: tuple[str, ...] = ("", "-", "--", "NOT REPORTED", "NOT OBSERVED")
    component_fields: tuple[str, ...] = COMPONENT_FIELDS
    published_total: str = "SAL_TOTFTX_C18"
    summary: str = "unweighted_program_median"
    association: str = "pearson_complete_pairs"
    minimum_association_pairs: int = 3
    error_models: tuple[str, ...] = ERROR_MODELS
    fit_models: bool = False
    promotion_allowed: bool = False
    future_forecast_available: bool = False


def validate_component_config(config: ComponentConfig) -> None:
    """Require the exact contract, including boolean prohibitions."""
    if json.dumps(asdict(config), sort_keys=True) != json.dumps(
        asdict(ComponentConfig()), sort_keys=True
    ):
        raise ComponentError("Settings disagree with the fixed outcome-component contract.")


def load_component_config(path: Path) -> ComponentConfig:
    """Reject missing, extra or changed YAML settings before any calculation."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        actual = json.dumps(raw, sort_keys=True, allow_nan=False)
    except (OSError, UnicodeError, yaml.YAMLError, ValueError, TypeError) as exc:
        raise ComponentError("Cannot read the fixed outcome-component contract.") from exc
    if actual != json.dumps(asdict(ComponentConfig()), sort_keys=True):
        raise ComponentError("Settings disagree with the fixed outcome-component contract.")
    return ComponentConfig()


def validate_component_destination(path: Path, *, repository_root: Path) -> Path:
    """Permit a direct run hash only, without traversal or filesystem redirects."""
    if (
        path.is_absolute()
        or path.drive
        or ".." in path.parts
        or path.parent != OUTPUT_ROOT
        or re.fullmatch(r"[0-9a-f]{64}", path.name) is None
    ):
        raise ComponentError("Output must be a relative run hash under the fixed component root.")
    root = repository_root.resolve()
    destination = root / path
    for current in (destination, *destination.parents):
        if current == root:
            break
        if current.is_symlink() or current.is_junction():
            raise ComponentError("Component output cannot traverse a filesystem link.")
    if not destination.resolve().is_relative_to(root / OUTPUT_ROOT):
        raise ComponentError("Resolved component output escapes the fixed root.")
    return destination
