"""Fix the separate report-count investigation before looking at revised results.

Only the five original input groups with report count removed are permitted.
The local output boundary protects both completed studies, including their
generated inputs. This module does not relax the original V2 configuration.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from kasm.patient_journey.config import CONTRASTS, FEATURE_GROUPS

ANALYSIS_ID = "kidney_patient_journey_v2_followup_report_count_v1"
OUTPUT_ROOT = Path("data/patient_journey_v2_followup/report_count_v1")
ORIGINAL_BUNDLE_SHA256 = "ce2844edbcec92c09d0053720d5331dd37ed43ab75de7aa4dd1de431c79a9eee"
ORIGINAL_EXPERIMENT_SHA256 = "ab8c01453c36039b293a8e7453b17b2b326faf734a081a4b67f8bfe132b1de79"
REVISED_GROUPS = tuple(
    (name, tuple(feature for feature in features if feature != "historical_target_count"))
    for name, features in FEATURE_GROUPS
)
FOLLOWUP_CONTRASTS = (
    (("original_history_acceptance", "historical_mean"),)
    + tuple((f"revised_{name}", f"original_{name}") for name, _ in FEATURE_GROUPS)
    + tuple((f"revised_{a}", f"revised_{b}") for a, b in CONTRASTS)
    + (("revised_history_acceptance", "historical_mean"),)
)


class FollowupConfigError(ValueError):
    """Raised when a setting or destination would change the agreed investigation."""


@dataclass(frozen=True)
class FollowupConfig:
    """Validated settings for the single count-removal comparison; no tuning knobs."""

    analysis_id: str = ANALYSIS_ID
    original_bundle_sha256: str = ORIGINAL_BUNDLE_SHA256
    original_experiment_sha256: str = ORIGINAL_EXPERIMENT_SHA256
    output_root: Path = OUTPUT_ROOT
    prediction_absolute_tolerance: float = 1e-10
    contribution_absolute_tolerance: float = 1e-10
    feature_groups: tuple[tuple[str, tuple[str, ...]], ...] = REVISED_GROUPS
    contrasts: tuple[tuple[str, str], ...] = FOLLOWUP_CONTRASTS


def validate_followup_config(config: FollowupConfig) -> None:
    """Reject an altered typed object as well as an altered YAML configuration."""
    if config != FollowupConfig():
        raise FollowupConfigError("Settings disagree with the fixed follow-up contract.")


def _expected_configuration() -> dict[str, object]:
    return {
        "schema_version": 1,
        "analysis_id": ANALYSIS_ID,
        "original_bundle_sha256": ORIGINAL_BUNDLE_SHA256,
        "original_experiment_sha256": ORIGINAL_EXPERIMENT_SHA256,
        "output_root": OUTPUT_ROOT.as_posix(),
        "removed_feature": "historical_target_count",
        "prediction_absolute_tolerance": 1e-10,
        "prediction_relative_tolerance": 0.0,
        "contribution_absolute_tolerance": 1e-10,
        "promotion_allowed": False,
        "future_forecast_available": False,
        "training_pairs": [["1905", "2205"]],
        "evaluation_pair": ["2205", "2505"],
        "feature_groups": [
            {"name": name, "features": list(features)} for name, features in REVISED_GROUPS
        ],
        "bootstrap": {
            "resamples": 2000,
            "seed": 20260904,
            "cluster": "program_key",
            "percentiles": [2.5, 97.5],
            "quantile_method": "linear",
            "contrast": "challenger_minus_comparator_balanced_mae",
        },
        "contrasts": [list(pair) for pair in FOLLOWUP_CONTRASTS],
    }


def load_followup_config(path: Path) -> FollowupConfig:
    """Read only the fixed experiment; reject missing, extra or changed choices.

    JSON comparison distinguishes booleans from numbers, so ``0`` cannot
    silently stand in for an explicit prohibition on promotion.
    """
    try:
        raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
        encoded = json.dumps(raw, sort_keys=True, allow_nan=False)
    except (OSError, UnicodeError, yaml.YAMLError, TypeError, ValueError) as exc:
        raise FollowupConfigError("Cannot read the fixed follow-up contract.") from exc
    if encoded != json.dumps(_expected_configuration(), sort_keys=True, allow_nan=False):
        raise FollowupConfigError("Settings disagree with the fixed follow-up contract.")
    return FollowupConfig()


def validate_followup_destination(path: Path, *, repository_root: Path) -> Path:
    """Allow only one run hash directly under the agreed ignored output root.

    Check the lexical path before resolving it, then reject links in every
    output ancestor. This prevents traversal and junctions from redirecting a
    staged write into either original study or outside the repository.
    """
    if (
        path.is_absolute()
        or path.drive
        or ".." in path.parts
        or path.parent != OUTPUT_ROOT
        or re.fullmatch(r"[0-9a-f]{64}", path.name) is None
    ):
        raise FollowupConfigError("Output must be a relative run hash under the fixed output root.")
    root = repository_root.resolve()
    destination = root / path
    for current in (destination, *destination.parents):
        if current == root:
            break
        if current.is_symlink() or current.is_junction():
            raise FollowupConfigError("Follow-up output cannot traverse a filesystem link.")
    if not destination.resolve().is_relative_to(root / OUTPUT_ROOT):
        raise FollowupConfigError("Resolved follow-up output escapes the fixed output root.")
    return destination
