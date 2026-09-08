"""Fixed choices for a descriptive review of registration events."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

OUTPUT_ROOT = Path("data/research/waiting-list-0025")


class ScreenError(ValueError):
    """The waiting-list screen cannot proceed with these inputs."""


@dataclass(frozen=True)
class ScreenConfig:
    """Practical review thresholds fixed before comparative summaries."""

    analysis_id: str = "waiting_list_0025_v1"
    schema_version: int = 1
    source_years: tuple[int, ...] = tuple(range(2017, 2026))
    transplant_categories: tuple[str, ...] = ("REMTXC", "REMTXL")
    minimum_years: int = 3
    minimum_pairs: int = 100
    minimum_pair_coverage: float = 0.8
    minimum_growing: int = 30
    minimum_prevalence: float = 0.25
    minimum_growth_count: int = 10
    minimum_growth_per100: float = 5.0
    minimum_common_programs: int = 80
    minimum_common_growing: int = 20
    size_boundaries: tuple[int, int] = (100, 500)
    minimum_size_growing_programs: int = 10
    minimum_size_prevalence: float = 0.15
    output_root: str = OUTPUT_ROOT.as_posix()
    promotion_allowed: bool = False


def load_config(path: Path) -> ScreenConfig:
    """Require the exact settings and types; the run cannot tune this screen."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        actual = json.dumps(raw, sort_keys=True, allow_nan=False)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ScreenError("Cannot read fixed waiting-list settings.") from exc
    if actual != json.dumps(asdict(ScreenConfig()), sort_keys=True):
        raise ScreenError("Settings disagree with the fixed waiting-list contract.")
    return ScreenConfig()
