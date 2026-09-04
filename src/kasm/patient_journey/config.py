"""Typed configuration for the isolated patient-journey v2 study."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import yaml

ANALYSIS_ID = "kidney_patient_journey_v2"
TARGET_COLUMN = "SAL_TOTFTX_C18"
PROTECTED_V1_ROOTS = (
    Path("data/processed"),
    Path("data/modeling"),
    Path("artifacts/release"),
)
BASELINES = ("persistence", "available_cohort_reference", "historical_mean")
HISTORY_FEATURES = (
    "prior_target_logit",
    "historical_mean_target_proportion",
    "log1p_prior_target_n",
    "historical_target_count",
)
ACCESS_FEATURES = (
    "log_transplant_rate_ratio",
    "log1p_transplant_rate_person_years",
    "log1p_wait_time_months_25th_percentile",
    "missing_transplant_rate_ratio",
    "missing_transplant_rate_person_years",
    "missing_wait_time",
)
ACCEPTANCE_FEATURES = (
    "log1p_acceptance_overall_expected_acceptances",
    "log_acceptance_overall_oar",
    "acceptance_interval_log_width",
    "log_acceptance_low_oar",
    "log_acceptance_medium_oar",
    "log_acceptance_high_oar",
    "log_acceptance_hard_to_place_oar",
    "missing_acceptance_expected_acceptances",
    "missing_acceptance_overall_oar",
    "missing_acceptance_interval",
    "missing_acceptance_low_oar",
    "missing_acceptance_medium_oar",
    "missing_acceptance_high_oar",
    "missing_acceptance_hard_to_place_oar",
)
SAFETY_FEATURES = (
    "log_waiting_list_mortality_ratio",
    "waiting_list_mortality_interval_log_width",
    "missing_waiting_list_mortality_ratio",
    "missing_waiting_list_mortality_interval",
)
FEATURE_GROUPS = (
    ("history", HISTORY_FEATURES),
    ("history_acceptance", HISTORY_FEATURES + ACCEPTANCE_FEATURES),
    ("history_access", HISTORY_FEATURES + ACCESS_FEATURES),
    (
        "history_access_acceptance",
        HISTORY_FEATURES + ACCESS_FEATURES + ACCEPTANCE_FEATURES,
    ),
    (
        "history_access_acceptance_safety",
        HISTORY_FEATURES + ACCESS_FEATURES + ACCEPTANCE_FEATURES + SAFETY_FEATURES,
    ),
)
CONTRASTS = (
    ("history_access", "history"),
    ("history_acceptance", "history"),
    ("history_access_acceptance", "history_access"),
    ("history_access_acceptance", "history_acceptance"),
    ("history_access_acceptance_safety", "history_access_acceptance"),
)


class PatientJourneyConfigError(ValueError):
    """Raised when v2 configuration could weaken scientific or path isolation."""


@dataclass(frozen=True)
class PatientJourneyOutputPaths:
    """Resolved repository-local roots owned by patient-journey v2."""

    processed_dir: Path
    modeling_dir: Path
    release_dir: Path


@dataclass(frozen=True)
class PatientJourneyPair:
    """One feature-release to target-release relationship."""

    feature_release_code: str
    target_release_code: str


@dataclass(frozen=True)
class PatientJourneyExcludedPair:
    """A reviewed candidate pair deliberately excluded from the primary panel."""

    feature_release_code: str
    target_release_code: str
    reason: str


@dataclass(frozen=True)
class PatientJourneyTemporalDesign:
    """Non-overlapping release pairs and publication-vintage evaluation mode."""

    evaluation_mode: Literal["strict_vintage"]
    max_prediction_origin_month_offset: int
    primary_pairs: tuple[PatientJourneyPair, ...]
    excluded_candidates: tuple[PatientJourneyExcludedPair, ...]


@dataclass(frozen=True)
class PatientJourneyEligibility:
    """Prespecified primary and sensitivity target-size thresholds."""

    primary_min_target_n: int
    sensitivity_min_target_n: tuple[int, int]


@dataclass(frozen=True)
class PatientJourneyFeatureGroup:
    """One frozen ordered V2 Ridge feature allowlist."""

    name: str
    features: tuple[str, ...]


@dataclass(frozen=True)
class PatientJourneyRidgeDesign:
    """Fixed Ridge settings and the sole strict-vintage evaluation fold."""

    alpha: float
    solver: Literal["lsqr"]
    tolerance: float
    max_iterations: int
    promotion_allowed: bool
    evaluation_pair: tuple[str, str]
    training_pairs: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class PatientJourneyMetricDesign:
    """Named V2 evaluation scale, orientation, and aggregation."""

    error_scale: Literal["percentage_points"]
    signed_error: Literal["prediction_minus_observed"]
    primary_aggregation: Literal["unweighted_mean_target_release_mae"]
    calibration_equation: str


@dataclass(frozen=True)
class PatientJourneyVolumeStrata:
    """Deterministic within-release volume quartiles."""

    method: Literal["within_release_sorted_quartiles"]
    tie_breaker: Literal["program_key"]
    labels: tuple[str, str, str, str]


@dataclass(frozen=True)
class PatientJourneyBootstrapDesign:
    """Frozen program-clustered paired-bootstrap settings."""

    resamples: int
    seed: int
    cluster: Literal["program_key"]
    percentiles: tuple[float, float]
    quantile_method: Literal["linear"]
    contrast: Literal["challenger_minus_comparator_balanced_mae"]


@dataclass(frozen=True)
class PatientJourneyModelDesign:
    """Complete frozen analytical contract for the retrospective V2 study."""

    baselines: tuple[str, str, str]
    feature_groups: tuple[PatientJourneyFeatureGroup, ...]
    ridge: PatientJourneyRidgeDesign
    metrics: PatientJourneyMetricDesign
    volume_strata: PatientJourneyVolumeStrata
    bootstrap: PatientJourneyBootstrapDesign
    contrasts: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class PatientJourneyConfig:
    """Validated patient-journey v2 foundation configuration."""

    schema_version: int
    analysis_id: str
    target_column: str
    paths: PatientJourneyOutputPaths
    temporal_design: PatientJourneyTemporalDesign
    eligibility: PatientJourneyEligibility
    model_design: PatientJourneyModelDesign


def _mapping(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PatientJourneyConfigError(f"{context} must be a mapping with string keys.")
    return cast(dict[str, object], value)


def _required_string(values: dict[str, object], key: str, context: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PatientJourneyConfigError(f"{context}.{key} must be a non-empty string.")
    return value


def _required_integer(values: dict[str, object], key: str, context: str) -> int:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PatientJourneyConfigError(f"{context}.{key} must be an integer.")
    return value


def _required_number(values: dict[str, object], key: str, context: str) -> float:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise PatientJourneyConfigError(f"{context}.{key} must be numeric.")
    return float(value)


def _required_boolean(values: dict[str, object], key: str, context: str) -> bool:
    value = values.get(key)
    if not isinstance(value, bool):
        raise PatientJourneyConfigError(f"{context}.{key} must be a boolean.")
    return value


def _path_strings(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise PatientJourneyConfigError(f"{context} must be a non-empty list of paths.")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise PatientJourneyConfigError(f"{context} must contain only non-empty path strings.")
    return tuple(cast(list[str], value))


def _object_sequence(value: object, context: str, *, allow_empty: bool = False) -> list[object]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise PatientJourneyConfigError(f"{context} must be {qualifier}.")
    return value


def _string_sequence(value: object, context: str) -> tuple[str, ...]:
    values = _object_sequence(value, context)
    if not all(isinstance(item, str) and item for item in values):
        raise PatientJourneyConfigError(f"{context} must contain non-empty strings.")
    return tuple(cast(list[str], values))


def _pair_sequence(value: object, context: str) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    for index, item in enumerate(_object_sequence(value, context)):
        raw_pair = _object_sequence(item, f"{context}[{index}]")
        if len(raw_pair) != 2 or not all(isinstance(code, str) and code for code in raw_pair):
            raise PatientJourneyConfigError(
                f"{context}[{index}] must contain exactly two release codes."
            )
        result.append((cast(str, raw_pair[0]), cast(str, raw_pair[1])))
    return tuple(result)


def _release_pair(value: object, context: str) -> tuple[str, str]:
    pairs = _pair_sequence([value], context)
    return pairs[0]


def _exact_keys(values: dict[str, object], expected: set[str], context: str) -> None:
    observed = set(values)
    if observed != expected:
        missing = sorted(expected - observed)
        unexpected = sorted(observed - expected)
        raise PatientJourneyConfigError(
            f"{context} keys disagree; missing={missing}, unexpected={unexpected}."
        )


def _pair(value: object, context: str) -> PatientJourneyPair:
    values = _mapping(value, context)
    feature = _required_string(values, "feature_release_code", context)
    target = _required_string(values, "target_release_code", context)
    if feature == target:
        raise PatientJourneyConfigError(f"{context} must use distinct feature and target releases.")
    return PatientJourneyPair(feature_release_code=feature, target_release_code=target)


def _temporal_design(value: object) -> PatientJourneyTemporalDesign:
    values = _mapping(value, "temporal_design")
    evaluation_mode = _required_string(values, "evaluation_mode", "temporal_design")
    if evaluation_mode != "strict_vintage":
        raise PatientJourneyConfigError("temporal_design.evaluation_mode must be 'strict_vintage'.")
    max_origin_offset = _required_integer(
        values,
        "max_prediction_origin_month_offset",
        "temporal_design",
    )
    if max_origin_offset != 1:
        raise PatientJourneyConfigError(
            "temporal_design.max_prediction_origin_month_offset must remain 1."
        )
    primary_pairs = tuple(
        _pair(item, f"temporal_design.primary_pairs[{index}]")
        for index, item in enumerate(
            _object_sequence(values.get("primary_pairs"), "temporal_design.primary_pairs")
        )
    )
    if len(primary_pairs) != len(set(primary_pairs)):
        raise PatientJourneyConfigError("temporal_design.primary_pairs must be unique.")
    target_codes = tuple(pair.target_release_code for pair in primary_pairs)
    if len(target_codes) != len(set(target_codes)):
        raise PatientJourneyConfigError(
            "temporal_design.primary_pairs must use unique target releases."
        )

    excluded: list[PatientJourneyExcludedPair] = []
    for index, item in enumerate(
        _object_sequence(
            values.get("excluded_candidates"),
            "temporal_design.excluded_candidates",
            allow_empty=True,
        )
    ):
        context = f"temporal_design.excluded_candidates[{index}]"
        item_values = _mapping(item, context)
        parsed = _pair(item_values, context)
        excluded.append(
            PatientJourneyExcludedPair(
                feature_release_code=parsed.feature_release_code,
                target_release_code=parsed.target_release_code,
                reason=_required_string(item_values, "reason", context),
            )
        )
    excluded_pairs = tuple(excluded)
    excluded_keys = tuple(
        (pair.feature_release_code, pair.target_release_code) for pair in excluded_pairs
    )
    if len(excluded_keys) != len(set(excluded_keys)):
        raise PatientJourneyConfigError("temporal_design.excluded_candidates must be unique.")
    primary_keys = {(pair.feature_release_code, pair.target_release_code) for pair in primary_pairs}
    if primary_keys.intersection(excluded_keys):
        raise PatientJourneyConfigError(
            "A temporal pair cannot be both primary and explicitly excluded."
        )
    return PatientJourneyTemporalDesign(
        evaluation_mode="strict_vintage",
        max_prediction_origin_month_offset=max_origin_offset,
        primary_pairs=primary_pairs,
        excluded_candidates=excluded_pairs,
    )


def _eligibility(value: object) -> PatientJourneyEligibility:
    values = _mapping(value, "eligibility")
    primary = _required_integer(values, "primary_min_target_n", "eligibility")
    raw_sensitivity = _object_sequence(
        values.get("sensitivity_min_target_n"), "eligibility.sensitivity_min_target_n"
    )
    sensitivity = tuple(
        _required_integer(
            {"value": item}, "value", f"eligibility.sensitivity_min_target_n[{index}]"
        )
        for index, item in enumerate(raw_sensitivity)
    )
    if primary != 10 or sensitivity != (20, 30):
        raise PatientJourneyConfigError(
            "Eligibility thresholds must remain fixed at primary N>=10 and sensitivities N>=20/30."
        )
    return PatientJourneyEligibility(
        primary_min_target_n=primary,
        sensitivity_min_target_n=(20, 30),
    )


def _model_design(value: object) -> PatientJourneyModelDesign:
    values = _mapping(value, "model_design")
    _exact_keys(
        values,
        {
            "baselines",
            "preprocessing",
            "ridge",
            "feature_groups",
            "metrics",
            "volume_strata",
            "bootstrap",
            "contrasts",
        },
        "model_design",
    )
    baselines = _string_sequence(values.get("baselines"), "model_design.baselines")
    if baselines != BASELINES:
        raise PatientJourneyConfigError(
            "model_design.baselines must preserve the frozen baseline order and names."
        )

    preprocessing = _mapping(values.get("preprocessing"), "model_design.preprocessing")
    _exact_keys(
        preprocessing,
        {"imputation", "keep_empty_features", "scaling", "fit_scope"},
        "model_design.preprocessing",
    )
    expected_preprocessing = {
        "imputation": "median",
        "keep_empty_features": True,
        "scaling": "standard",
        "fit_scope": "training_fold_only",
    }
    if preprocessing != expected_preprocessing:
        raise PatientJourneyConfigError(
            "model_design.preprocessing must preserve the frozen fold-local pipeline."
        )

    ridge_values = _mapping(values.get("ridge"), "model_design.ridge")
    _exact_keys(
        ridge_values,
        {
            "target_scale",
            "alpha",
            "solver",
            "tolerance",
            "max_iterations",
            "inverse_link",
            "promotion_allowed",
            "evaluation_pair",
            "training_pairs",
        },
        "model_design.ridge",
    )
    alpha = _required_number(ridge_values, "alpha", "model_design.ridge")
    solver = _required_string(ridge_values, "solver", "model_design.ridge")
    tolerance = _required_number(ridge_values, "tolerance", "model_design.ridge")
    max_iterations = _required_integer(ridge_values, "max_iterations", "model_design.ridge")
    promotion_allowed = _required_boolean(ridge_values, "promotion_allowed", "model_design.ridge")
    evaluation_pair = _release_pair(
        ridge_values.get("evaluation_pair"), "model_design.ridge.evaluation_pair"
    )
    training_pairs = _pair_sequence(
        ridge_values.get("training_pairs"), "model_design.ridge.training_pairs"
    )
    if (
        _required_string(ridge_values, "target_scale", "model_design.ridge") != "empirical_logit"
        or alpha != 1.0
        or solver != "lsqr"
        or tolerance != 1e-8
        or max_iterations != 10_000
        or _required_string(ridge_values, "inverse_link", "model_design.ridge") != "logistic"
        or promotion_allowed
        or evaluation_pair != ("2205", "2505")
        or training_pairs != (("1905", "2205"),)
    ):
        raise PatientJourneyConfigError(
            "model_design.ridge must preserve the frozen one-fold nonpromotion contract."
        )
    ridge = PatientJourneyRidgeDesign(
        alpha=alpha,
        solver="lsqr",
        tolerance=tolerance,
        max_iterations=max_iterations,
        promotion_allowed=False,
        evaluation_pair=evaluation_pair,
        training_pairs=training_pairs,
    )

    feature_groups: list[PatientJourneyFeatureGroup] = []
    for index, item in enumerate(
        _object_sequence(values.get("feature_groups"), "model_design.feature_groups")
    ):
        context = f"model_design.feature_groups[{index}]"
        group_values = _mapping(item, context)
        _exact_keys(group_values, {"name", "features"}, context)
        feature_groups.append(
            PatientJourneyFeatureGroup(
                name=_required_string(group_values, "name", context),
                features=_string_sequence(group_values.get("features"), f"{context}.features"),
            )
        )
    observed_groups = tuple((group.name, group.features) for group in feature_groups)
    if observed_groups != FEATURE_GROUPS:
        raise PatientJourneyConfigError(
            "model_design.feature_groups must exactly match the frozen ordered allowlists."
        )

    metric_values = _mapping(values.get("metrics"), "model_design.metrics")
    _exact_keys(
        metric_values,
        {
            "error_scale",
            "signed_error",
            "primary_aggregation",
            "calibration_equation",
            "combined_release_weighting",
            "secondary",
        },
        "model_design.metrics",
    )
    expected_metric_text = (
        _required_string(metric_values, "error_scale", "model_design.metrics"),
        _required_string(metric_values, "signed_error", "model_design.metrics"),
        _required_string(metric_values, "primary_aggregation", "model_design.metrics"),
        _required_string(metric_values, "calibration_equation", "model_design.metrics"),
        _required_string(metric_values, "combined_release_weighting", "model_design.metrics"),
        _string_sequence(metric_values.get("secondary"), "model_design.metrics.secondary"),
    )
    if expected_metric_text != (
        "percentage_points",
        "prediction_minus_observed",
        "unweighted_mean_target_release_mae",
        "observed_percentage_points=intercept+slope*predicted_percentage_points",
        "equal_total_weight_per_target_release",
        ("candidate_volume_weighted_mae", "median_absolute_error"),
    ):
        raise PatientJourneyConfigError(
            "model_design.metrics must preserve the frozen percentage-point definitions."
        )
    metrics = PatientJourneyMetricDesign(
        error_scale="percentage_points",
        signed_error="prediction_minus_observed",
        primary_aggregation="unweighted_mean_target_release_mae",
        calibration_equation=expected_metric_text[3],
    )

    strata_values = _mapping(values.get("volume_strata"), "model_design.volume_strata")
    _exact_keys(
        strata_values,
        {"method", "tie_breaker", "labels"},
        "model_design.volume_strata",
    )
    labels = _string_sequence(strata_values.get("labels"), "model_design.volume_strata.labels")
    if (
        _required_string(strata_values, "method", "model_design.volume_strata")
        != "within_release_sorted_quartiles"
        or _required_string(strata_values, "tie_breaker", "model_design.volume_strata")
        != "program_key"
        or labels != ("q1_lowest", "q2", "q3", "q4_highest")
    ):
        raise PatientJourneyConfigError(
            "model_design.volume_strata must preserve the frozen target-N quartiles."
        )
    volume_strata = PatientJourneyVolumeStrata(
        method="within_release_sorted_quartiles",
        tie_breaker="program_key",
        labels=("q1_lowest", "q2", "q3", "q4_highest"),
    )

    bootstrap_values = _mapping(values.get("bootstrap"), "model_design.bootstrap")
    _exact_keys(
        bootstrap_values,
        {
            "resamples",
            "seed",
            "cluster",
            "percentiles",
            "quantile_method",
            "contrast",
        },
        "model_design.bootstrap",
    )
    raw_percentiles = _object_sequence(
        bootstrap_values.get("percentiles"), "model_design.bootstrap.percentiles"
    )
    if len(raw_percentiles) != 2:
        raise PatientJourneyConfigError(
            "model_design.bootstrap.percentiles must contain two values."
        )
    percentiles = tuple(
        _required_number({"value": item}, "value", f"model_design.bootstrap.percentiles[{index}]")
        for index, item in enumerate(raw_percentiles)
    )
    bootstrap_contract = (
        _required_integer(bootstrap_values, "resamples", "model_design.bootstrap"),
        _required_integer(bootstrap_values, "seed", "model_design.bootstrap"),
        _required_string(bootstrap_values, "cluster", "model_design.bootstrap"),
        percentiles,
        _required_string(bootstrap_values, "quantile_method", "model_design.bootstrap"),
        _required_string(bootstrap_values, "contrast", "model_design.bootstrap"),
    )
    if bootstrap_contract != (
        2_000,
        20_260_904,
        "program_key",
        (2.5, 97.5),
        "linear",
        "challenger_minus_comparator_balanced_mae",
    ):
        raise PatientJourneyConfigError(
            "model_design.bootstrap must preserve the frozen program-clustered design."
        )
    bootstrap = PatientJourneyBootstrapDesign(
        resamples=2_000,
        seed=20_260_904,
        cluster="program_key",
        percentiles=(2.5, 97.5),
        quantile_method="linear",
        contrast="challenger_minus_comparator_balanced_mae",
    )

    contrasts = _pair_sequence(values.get("contrasts"), "model_design.contrasts")
    if contrasts != CONTRASTS:
        raise PatientJourneyConfigError(
            "model_design.contrasts must preserve the frozen incremental comparisons."
        )
    return PatientJourneyModelDesign(
        baselines=("persistence", "available_cohort_reference", "historical_mean"),
        feature_groups=tuple(feature_groups),
        ridge=ridge,
        metrics=metrics,
        volume_strata=volume_strata,
        bootstrap=bootstrap,
        contrasts=contrasts,
    )


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first.is_relative_to(second) or second.is_relative_to(first)


def _resolve_v2_output(
    value: str,
    *,
    key: str,
    repository_root: Path,
    protected_roots: tuple[Path, ...],
) -> Path:
    configured = Path(value)
    if configured.is_absolute():
        raise PatientJourneyConfigError(f"paths.{key} must be repository-relative.")
    if ".." in configured.parts:
        raise PatientJourneyConfigError(f"paths.{key} must not contain parent traversal.")

    resolved = (repository_root / configured).resolve()
    if not resolved.is_relative_to(repository_root):
        raise PatientJourneyConfigError(f"paths.{key} must remain inside the repository.")
    for protected in protected_roots:
        if _paths_overlap(resolved, protected):
            protected_relative = protected.relative_to(repository_root)
            raise PatientJourneyConfigError(
                f"paths.{key} overlaps protected v1 root {protected_relative.as_posix()!r}."
            )
    return resolved


def load_patient_journey_config(path: Path, *, repository_root: Path) -> PatientJourneyConfig:
    """Load v2 configuration and reject any path capable of writing into v1."""
    root = repository_root.resolve()
    raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    values = _mapping(raw, "Config root")

    schema_version = _required_integer(values, "schema_version", "Config root")
    if schema_version != 2:
        raise PatientJourneyConfigError(
            f"Unsupported patient-journey schema_version {schema_version}; expected 2."
        )

    analysis_id = _required_string(values, "analysis_id", "Config root")
    if analysis_id != ANALYSIS_ID:
        raise PatientJourneyConfigError(f"Config root.analysis_id must be {ANALYSIS_ID!r}.")

    target = _mapping(values.get("target"), "target")
    target_column = _required_string(target, "column", "target")
    if target_column != TARGET_COLUMN:
        raise PatientJourneyConfigError(f"target.column must be {TARGET_COLUMN!r}.")
    if _required_string(target, "canonical_scale", "target") != "proportion":
        raise PatientJourneyConfigError("target.canonical_scale must be 'proportion'.")
    if _required_boolean(target, "officially_risk_adjusted", "target"):
        raise PatientJourneyConfigError(
            "The patient-journey target is observed, not officially risk-adjusted."
        )

    temporal_design = _temporal_design(values.get("temporal_design"))
    eligibility = _eligibility(values.get("eligibility"))

    configured_protected = tuple(
        Path(value)
        for value in _path_strings(values.get("protected_v1_roots"), "protected_v1_roots")
    )
    if configured_protected != PROTECTED_V1_ROOTS:
        raise PatientJourneyConfigError(
            "protected_v1_roots must exactly match the code-owned v1 protection contract."
        )
    protected_roots = tuple((root / protected).resolve() for protected in PROTECTED_V1_ROOTS)

    path_values = _mapping(values.get("paths"), "paths")
    output_paths = PatientJourneyOutputPaths(
        processed_dir=_resolve_v2_output(
            _required_string(path_values, "processed_dir", "paths"),
            key="processed_dir",
            repository_root=root,
            protected_roots=protected_roots,
        ),
        modeling_dir=_resolve_v2_output(
            _required_string(path_values, "modeling_dir", "paths"),
            key="modeling_dir",
            repository_root=root,
            protected_roots=protected_roots,
        ),
        release_dir=_resolve_v2_output(
            _required_string(path_values, "release_dir", "paths"),
            key="release_dir",
            repository_root=root,
            protected_roots=protected_roots,
        ),
    )
    named_outputs = (
        ("processed_dir", output_paths.processed_dir),
        ("modeling_dir", output_paths.modeling_dir),
        ("release_dir", output_paths.release_dir),
    )
    for index, (name, output) in enumerate(named_outputs):
        for other_name, other_output in named_outputs[index + 1 :]:
            if _paths_overlap(output, other_output):
                raise PatientJourneyConfigError(
                    f"paths.{name} and paths.{other_name} must be separate roots."
                )

    model_design = _model_design(values.get("model_design"))

    return PatientJourneyConfig(
        schema_version=schema_version,
        analysis_id=analysis_id,
        target_column=target_column,
        paths=output_paths,
        temporal_design=temporal_design,
        eligibility=eligibility,
        model_design=model_design,
    )
