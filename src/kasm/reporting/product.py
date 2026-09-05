"""Validated product-view services over frozen, precomputed model artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from math import isclose, isfinite
from pathlib import Path
from typing import Literal, cast


class ProductDataError(ValueError):
    """Raised when precomputed model artifacts cannot safely support the product view."""


@dataclass(frozen=True)
class TemporalModelComparison:
    """One rolling target year's four prespecified model errors."""

    target_year: int
    n: int
    neutral_mae_log_oar: float
    persistence_mae_log_oar: float
    historical_mean_mae_log_oar: float
    ridge_mae_log_oar: float
    ridge_skill_over_persistence: float


@dataclass(frozen=True)
class ReplayEvaluation:
    """Frozen 2025 descriptive replay evidence used for the product decision."""

    target_year: int
    n: int
    ridge_mae_log_oar: float
    persistence_mae_log_oar: float
    skill_over_persistence: float
    ridge_mean_signed_log_error: float
    persistence_mean_signed_log_error: float
    bootstrap_interval: tuple[float, float] | None


@dataclass(frozen=True)
class ModelEvaluation:
    """Complete, effective model state for an offline analytical view."""

    activation_status: Literal["not_attempted", "attempted_not_promoted", "promoted"]
    displayed_model: Literal["persistence", "ridge"]
    point_failed_criteria: tuple[str, ...]
    ridge_band_gate_passed: bool
    display_band: bool
    band_suppression_reason: str | None
    band_coverage: float | None
    band_coverage_interval: tuple[float, float] | None
    band_mean_width_relative_to_persistence: float | None
    temporal_comparisons: tuple[TemporalModelComparison, ...]
    replay: ReplayEvaluation
    evidence_classification: str
    prospective_validation: bool
    selected_alpha: float
    model_version: str
    panel_version: str
    source_manifest_version: str
    git_commit_sha: str


JsonObject = dict[str, object]


def _read_json_object(path: Path) -> JsonObject:
    if not path.is_file():
        raise ProductDataError(f"Trusted modeling artifact is missing: {path.name}.")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductDataError(f"Trusted modeling artifact {path.name} is invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ProductDataError(f"Trusted modeling artifact {path.name} must contain an object.")
    return cast(JsonObject, parsed)


def _object(value: object, field: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ProductDataError(f"Trusted model field {field!r} must be an object.")
    return cast(JsonObject, value)


def _array(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise ProductDataError(f"Trusted model field {field!r} must be an array.")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProductDataError(f"Trusted model field {field!r} must be nonempty text.")
    return value


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProductDataError(f"Trusted model field {field!r} must be an integer.")
    return value


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ProductDataError(f"Trusted model field {field!r} must be numeric.")
    result = float(value)
    if not isfinite(result):
        raise ProductDataError(f"Trusted model field {field!r} must be finite.")
    return result


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ProductDataError(f"Trusted model field {field!r} must be boolean.")
    return value


def _record_array(container: Mapping[str, object], field: str) -> tuple[JsonObject, ...]:
    records: list[JsonObject] = []
    for index, value in enumerate(_array(container.get(field), field)):
        records.append(_object(value, f"{field}[{index}]"))
    return tuple(records)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ProductDataError(f"Trusted modeling artifact is unreadable: {path.name}.") from exc
    return digest.hexdigest()


def _validated_replay_bundle(
    modeling_dir: Path,
) -> tuple[Path, JsonObject, JsonObject, str]:
    completion_paths = tuple(sorted((modeling_dir / "frozen-replay").glob("*/completion.json")))
    if len(completion_paths) != 1:
        raise ProductDataError(
            f"Expected exactly one completed frozen replay bundle, found {len(completion_paths)}."
        )
    completion_path = completion_paths[0]
    bundle = completion_path.parent
    completion = _read_json_object(completion_path)
    if completion.get("status") != "complete":
        raise ProductDataError("Frozen replay completion ledger is not complete.")

    config_hash = _text(completion.get("frozen_experiment_sha256"), "frozen_experiment_sha256")
    source_hash = _text(completion.get("source_manifest_sha256"), "source_manifest_sha256")
    panel_hash = _text(completion.get("input_panel_sha256"), "input_panel_sha256")
    if bundle.name != f"{config_hash}_{source_hash}":
        raise ProductDataError("Frozen replay directory does not match its provenance hashes.")

    artifacts = _object(completion.get("artifacts"), "artifacts")
    checksums = _object(completion.get("artifact_sha256"), "artifact_sha256")
    expected_names = {
        "metrics": "replay_metrics.json",
        "predictions": "replay_predictions.parquet",
    }
    paths: dict[str, Path] = {}
    for artifact, expected_name in expected_names.items():
        name = _text(artifacts.get(artifact), f"artifacts.{artifact}")
        if name != expected_name:
            raise ProductDataError(
                f"Frozen replay {artifact} artifact must be named {expected_name}."
            )
        path = bundle / name
        expected_checksum = _text(checksums.get(artifact), f"artifact_sha256.{artifact}")
        if _file_sha256(path) != expected_checksum:
            raise ProductDataError(f"Frozen replay {artifact} checksum does not match its ledger.")
        paths[artifact] = path

    metrics = _read_json_object(paths["metrics"])
    provenance = _object(metrics.get("provenance"), "provenance")
    for field, expected in (
        ("frozen_experiment_sha256", config_hash),
        ("source_manifest_sha256", source_hash),
        ("input_panel_sha256", panel_hash),
    ):
        if _text(provenance.get(field), f"provenance.{field}") != expected:
            raise ProductDataError(f"Frozen replay {field} disagrees with its completion ledger.")
    return bundle, completion, metrics, panel_hash


def _temporal_comparisons(
    modeling_dir: Path, *, expected_panel_sha256: str
) -> tuple[TemporalModelComparison, ...]:
    baseline = _read_json_object(modeling_dir / "baseline_metrics.json")
    ridge = _read_json_object(modeling_dir / "ridge_metrics.json")
    if baseline.get("frozen_replay_evaluated") is not False:
        raise ProductDataError("Baseline metrics must remain pre-replay evidence.")
    if ridge.get("frozen_replay_evaluated") is not False:
        raise ProductDataError("Ridge rolling metrics must remain pre-replay evidence.")
    for name, artifact in (("baseline", baseline), ("ridge", ridge)):
        if _text(artifact.get("input_panel_sha256"), f"{name}.input_panel_sha256") != (
            expected_panel_sha256
        ):
            raise ProductDataError(f"{name.title()} metrics use a different model panel checksum.")

    baseline_by_key: dict[tuple[int, str], JsonObject] = {}
    for record in _record_array(baseline, "by_target_year"):
        year = _integer(record.get("target_year"), "baseline.target_year")
        model = _text(record.get("model"), "baseline.model")
        key = (year, model)
        if key in baseline_by_key:
            raise ProductDataError(f"Duplicate baseline metric for {year} and {model}.")
        baseline_by_key[key] = record

    ridge_by_year: dict[int, JsonObject] = {}
    for record in _record_array(ridge, "by_target_year"):
        year = _integer(record.get("target_year"), "ridge.target_year")
        if year in ridge_by_year:
            raise ProductDataError(f"Duplicate ridge metric for target year {year}.")
        ridge_by_year[year] = record

    required_years = tuple(range(2021, 2025))
    expected_baseline_keys = {
        (year, model)
        for year in required_years
        for model in ("neutral", "persistence", "historical_mean")
    }
    if set(baseline_by_key) != expected_baseline_keys or set(ridge_by_year) != set(required_years):
        raise ProductDataError(
            "Model evaluation requires complete 2021–2024 neutral, persistence, "
            "historical-mean, and ridge metrics."
        )

    result: list[TemporalModelComparison] = []
    for year in required_years:
        neutral = baseline_by_key[(year, "neutral")]
        persistence = baseline_by_key[(year, "persistence")]
        historical_mean = baseline_by_key[(year, "historical_mean")]
        ridge_record = ridge_by_year[year]
        counts = {
            _integer(record.get("n"), f"{year}.n")
            for record in (neutral, persistence, historical_mean, ridge_record)
        }
        if len(counts) != 1 or next(iter(counts)) <= 0:
            raise ProductDataError(f"Target year {year} has inconsistent model row counts.")
        persistence_mae = _number(persistence.get("mae_log_oar"), f"{year}.persistence_mae_log_oar")
        ridge_persistence_mae = _number(
            ridge_record.get("persistence_mae_log_oar"),
            f"{year}.ridge.persistence_mae_log_oar",
        )
        if not isclose(persistence_mae, ridge_persistence_mae, rel_tol=0, abs_tol=1e-12):
            raise ProductDataError(
                f"Target year {year} persistence metrics disagree across artifacts."
            )
        result.append(
            TemporalModelComparison(
                target_year=year,
                n=next(iter(counts)),
                neutral_mae_log_oar=_number(
                    neutral.get("mae_log_oar"), f"{year}.neutral_mae_log_oar"
                ),
                persistence_mae_log_oar=persistence_mae,
                historical_mean_mae_log_oar=_number(
                    historical_mean.get("mae_log_oar"),
                    f"{year}.historical_mean_mae_log_oar",
                ),
                ridge_mae_log_oar=_number(
                    ridge_record.get("mae_log_oar"), f"{year}.ridge_mae_log_oar"
                ),
                ridge_skill_over_persistence=_number(
                    ridge_record.get("skill_over_persistence"),
                    f"{year}.ridge_skill_over_persistence",
                ),
            )
        )
    return tuple(result)


def _point_state(
    point: Mapping[str, object],
) -> tuple[
    Literal["not_attempted", "attempted_not_promoted", "promoted"], tuple[str, ...], bool, str
]:
    failed = tuple(
        _text(value, "point_promotion.failed_criteria")
        for value in _array(point.get("failed_criteria"), "point_promotion.failed_criteria")
    )
    promoted = _boolean(point.get("promoted"), "point_promotion.promoted")
    displayed_model = _text(point.get("displayed_model"), "point_promotion.displayed_model")
    expected_displayed_model = "ridge" if promoted else "persistence"
    if displayed_model != expected_displayed_model:
        raise ProductDataError("Point promotion state disagrees with the displayed model.")
    activation_status: Literal["not_attempted", "attempted_not_promoted", "promoted"]
    if "forecast_activation_not_attempted" in failed:
        if promoted:
            raise ProductDataError("Activation was not attempted but point promotion is claimed.")
        activation_status = "not_attempted"
    elif promoted:
        activation_status = "promoted"
    else:
        activation_status = "attempted_not_promoted"

    return activation_status, failed, promoted, displayed_model


def _uncertainty_evidence(
    metrics: Mapping[str, object],
    *,
    activation_status: str,
) -> tuple[JsonObject | None, JsonObject | None]:
    if activation_status == "not_attempted":
        if metrics.get("band_promotion") is not None or metrics.get("bootstrap") is not None:
            raise ProductDataError(
                "Activation was not attempted but uncertainty evidence is present."
            )
        return None, None
    return (
        _object(metrics.get("band_promotion"), "band_promotion"),
        _object(metrics.get("bootstrap"), "bootstrap"),
    )


def load_model_evaluation(modeling_dir: Path, *, expected_panel_sha256: str) -> ModelEvaluation:
    """Load the complete frozen product decision after ledger and schema validation."""
    _, completion, metrics, replay_panel_sha256 = _validated_replay_bundle(modeling_dir)
    if replay_panel_sha256 != expected_panel_sha256:
        raise ProductDataError(
            "Frozen replay model panel checksum does not match the historical artifacts."
        )
    if metrics.get("frozen_replay_evaluated") is not True:
        raise ProductDataError("Frozen replay metrics are not marked evaluated.")
    evidence = _text(metrics.get("evidence_classification"), "evidence_classification")
    if evidence != "descriptive_retrospective_product_selection":
        raise ProductDataError("Frozen replay evidence classification is not recognized.")
    prospective = _boolean(metrics.get("prospective_validation"), "prospective_validation")
    if prospective:
        raise ProductDataError("The frozen retrospective replay cannot be prospective validation.")

    overall = _object(metrics.get("overall"), "overall")
    point = _object(metrics.get("point_promotion"), "point_promotion")
    provenance = _object(metrics.get("provenance"), "provenance")
    activation_status, failed, promoted, displayed_model = _point_state(point)
    band, bootstrap = _uncertainty_evidence(metrics, activation_status=activation_status)
    raw_band_display = (
        False if band is None else _boolean(band.get("display_band"), "band_promotion.display_band")
    )
    effective_band_display = promoted and raw_band_display
    suppression_reason = (
        "forecast_activation_not_attempted"
        if activation_status == "not_attempted"
        else None
        if effective_band_display
        else "ridge_point_not_promoted"
        if not promoted
        else "ridge_band_gate_failed"
    )
    n = _integer(overall.get("n"), "overall.n")
    if n != _integer(completion.get("prediction_rows"), "completion.prediction_rows"):
        raise ProductDataError("Replay metric row count disagrees with its completion ledger.")

    replay = ReplayEvaluation(
        target_year=_integer(metrics.get("replay_target_year"), "replay_target_year"),
        n=n,
        ridge_mae_log_oar=_number(overall.get("ridge_mae_log_oar"), "ridge_mae_log_oar"),
        persistence_mae_log_oar=_number(
            overall.get("persistence_mae_log_oar"), "persistence_mae_log_oar"
        ),
        skill_over_persistence=_number(
            overall.get("skill_over_persistence"), "skill_over_persistence"
        ),
        ridge_mean_signed_log_error=_number(
            overall.get("ridge_mean_signed_log_error"), "ridge_mean_signed_log_error"
        ),
        persistence_mean_signed_log_error=_number(
            overall.get("persistence_mean_signed_log_error"),
            "persistence_mean_signed_log_error",
        ),
        bootstrap_interval=None
        if bootstrap is None
        else (
            _number(bootstrap.get("lower"), "bootstrap.lower"),
            _number(bootstrap.get("upper"), "bootstrap.upper"),
        ),
    )
    config_hash = _text(
        provenance.get("frozen_experiment_sha256"), "provenance.frozen_experiment_sha256"
    )
    source_hash = _text(
        provenance.get("source_manifest_sha256"), "provenance.source_manifest_sha256"
    )
    return ModelEvaluation(
        activation_status=activation_status,
        displayed_model=cast(Literal["persistence", "ridge"], displayed_model),
        point_failed_criteria=failed,
        ridge_band_gate_passed=raw_band_display,
        display_band=effective_band_display,
        band_suppression_reason=suppression_reason,
        band_coverage=None
        if band is None
        else _number(band.get("coverage"), "band_promotion.coverage"),
        band_coverage_interval=None
        if band is None
        else (
            _number(band.get("exact_interval_lower"), "band_promotion.exact_interval_lower"),
            _number(band.get("exact_interval_upper"), "band_promotion.exact_interval_upper"),
        ),
        band_mean_width_relative_to_persistence=None
        if band is None
        else _number(
            band.get("mean_width_relative_to_persistence"),
            "band_promotion.mean_width_relative_to_persistence",
        ),
        temporal_comparisons=_temporal_comparisons(
            modeling_dir, expected_panel_sha256=expected_panel_sha256
        ),
        replay=replay,
        evidence_classification=evidence,
        prospective_validation=prospective,
        selected_alpha=_number(metrics.get("selected_alpha"), "selected_alpha"),
        model_version=config_hash[:12],
        panel_version=replay_panel_sha256[:12],
        source_manifest_version=source_hash[:12],
        git_commit_sha=_text(provenance.get("git_commit_sha"), "provenance.git_commit_sha"),
    )
