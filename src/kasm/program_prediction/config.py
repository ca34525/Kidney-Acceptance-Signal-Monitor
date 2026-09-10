"""Read the choices fixed before the program prediction experiments are run."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

OUTPUT_ROOT = Path("data/research/program-prediction-0031")
TARGETS = ("registrations", "ddkt_removals", "ldkt_removals", "ending_list", "overall_oar")
PIPELINES = ("ridge_history", "ridge_broader", "boosting_broader", "extra_trees_broader")
BASELINES = ("persistence", "recent_mean", "damped_trend", "adjusted_persistence")
B1_PAIRS = (
    ("1905", 2018, 2019, "2105"),
    ("2105", 2020, 2021, "2205"),
    ("2205", 2021, 2022, "2305"),
    ("2305", 2022, 2023, "2405"),
    ("2405", 2023, 2024, "2505"),
    ("2505", 2024, 2025, "2605"),
)


class SprintError(ValueError):
    """The sprint cannot proceed without changing a documented research rule."""


@dataclass(frozen=True)
class SprintConfig:
    """Fixed initial comparison; follow-ups name their question and preceding run."""

    schema_version: int = 1
    study_id: str = "program-prediction-0031"
    round_id: str = "initial"
    question: str = "Which annual prediction could help allocate limited review time?"
    parent_run: str | None = None
    targets: tuple[str, ...] = TARGETS
    pipelines: tuple[str, ...] = PIPELINES
    discovery_years: tuple[int, ...] = (2021, 2022, 2023)
    later_years: tuple[int, ...] = (2024, 2025)
    seed: int = 20260909
    bootstrap_resamples: int = 2000
    budgets: tuple[int, ...] = (10, 15, 25)
    omit_oar_features: bool = False
    candidate_features: str = "omit_without_release_period_and_denominator_binding"
    ridge_alpha: float = 10.0
    boosting_iterations: int = 150
    boosting_learning_rate: float = 0.05
    boosting_max_leaf_nodes: int = 7
    boosting_min_samples_leaf: int = 20
    boosting_l2_regularization: float = 1.0
    boosting_early_stopping: bool = False
    extra_trees_estimators: int = 300
    extra_trees_max_depth: int = 6
    extra_trees_min_samples_leaf: int = 8
    extra_trees_max_features: float = 1.0
    primary_summary: str = "equal_year_mean_of_equal_program_absolute_error"
    count_fit_transform: str = "log1p"
    oar_fit_transform: str = "log"
    feature_vintage: str = "latest_public_vintage_per_past_year_global_across_programs"
    truth_vintage: str = "earliest_verified_vintage_per_target_year_global_across_programs"
    output_root: str = OUTPUT_ROOT.as_posix()
    promotion_allowed: bool = False

    @property
    def raw(self) -> dict[str, Any]:
        """JSON-ready settings retained verbatim in each run's evidence."""
        return dict(json.loads(json.dumps(asdict(self))))


def validate_config(config: SprintConfig) -> None:
    """Limit optional OAR ablation to separately identified, documented follow-ups."""
    raw = config.raw
    initial = SprintConfig().raw
    if config.round_id not in {"initial", "followup_1", "followup_2"}:
        raise SprintError("Only the initial sprint and two versioned follow-up rounds are allowed.")
    variable = {"round_id", "question", "parent_run", "omit_oar_features", "targets"}
    expected = (
        initial if config.round_id == "initial" else initial | {key: raw[key] for key in variable}
    )
    if json.dumps(raw, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise SprintError("Settings disagree with the fixed initial comparison contract.")
    if config.round_id != "initial" and (
        not isinstance(config.question, str)
        or not config.question.strip()
        or config.question == initial["question"]
        or not isinstance(config.parent_run, str)
        or not config.parent_run.strip()
    ):
        raise SprintError("A follow-up requires its own question and preserved parent run.")
    if type(config.omit_oar_features) is not bool:
        raise SprintError("OAR feature omission must be a boolean setting.")
    if (
        not config.targets
        or any(target not in TARGETS for target in config.targets)
        or len(set(config.targets)) != len(config.targets)
    ):
        raise SprintError("A follow-up must select distinct targets from the initial screen.")


def _unique_settings(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name, value in pairs:
        if name in values:
            raise SprintError(f"Duplicate settings key: {name}.")
        values[name] = value
    return values


def load_config(path: Path) -> SprintConfig:
    """Reject malformed, unknown or silently changed executable settings."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_settings)
        if not isinstance(raw, dict) or set(raw) != set(SprintConfig().raw):
            raise SprintError("Settings must contain exactly the documented fields.")
        values = dict(raw)
        for name in ("targets", "pipelines", "discovery_years", "later_years", "budgets"):
            values[name] = tuple(values[name])
        config = SprintConfig(**values)
        validate_config(config)
    except (OSError, UnicodeError, TypeError, ValueError) as exc:
        if isinstance(exc, SprintError):
            raise
        raise SprintError("Cannot read fixed program prediction settings.") from exc
    return config
