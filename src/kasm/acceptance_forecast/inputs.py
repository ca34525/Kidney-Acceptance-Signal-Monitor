"""Load saved V1 predictions only after verifying their preserved release identity."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from math import exp
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from kasm.acceptance_forecast.config import DiagnosticConfig, ForecastError
from kasm.data.build import MODEL_PANEL_SCHEMA
from kasm.modeling.features import MODEL_FEATURE_COLUMNS
from kasm.reporting.artifacts import ReleaseBundleError, validate_release_bundle


def file_hash(path: Path) -> str:
    try:
        return sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ForecastError(f"Required input is missing or unreadable: {path}") from exc


def ensure_local_path(path: Path, root: Path) -> None:
    """Reject filesystem redirects before reading or publishing trusted evidence."""
    if any(part.is_symlink() or part.is_junction() for part in (path, *path.parents)):
        raise ForecastError(
            "Research inputs and outputs cannot follow a filesystem link or redirect."
        )
    if not path.resolve().is_relative_to(root.resolve()):
        raise ForecastError("Research input or output path escapes its approved root.")


@dataclass(frozen=True)
class ForecastInputs:
    panel: list[dict[str, Any]]
    predictions: list[dict[str, Any]]
    release: dict[str, Any]


def decorate(row: dict[str, Any]) -> dict[str, Any]:
    """Attach fixed groups based only on the earlier report, retaining unknown values."""
    current = exp(row["current_log_overall_oar"])
    group = (
        "below_0.5"
        if current < 0.5
        else ("0.5_to_below_1" if current < 1 else "1_to_below_2" if current < 2 else "2_or_more")
    )
    missing = any(
        row.get(key) is None or (key.startswith("missing_") and row[key] is True)
        for key in MODEL_FEATURE_COLUMNS
    )
    return {
        **row,
        "earlier_oar_group": group,
        "predictor_missingness": "some_missing" if missing else "none_missing",
    }


def _matching_panel_row(
    index: dict[tuple[str, int], dict[str, Any]], prediction: dict[str, Any]
) -> dict[str, Any]:
    key = (prediction["program_key"], prediction["target_cohort_year"])
    if key not in index:
        raise ForecastError("Saved prediction has no matching trusted program-year.")
    source = index[key]
    for field in MODEL_PANEL_SCHEMA.names:
        if field in prediction and prediction[field] != source[field]:
            raise ForecastError(f"Saved prediction {field} disagrees with its trusted panel.")
    return source


def _saved_predictions(
    bundle: Path, panel: list[dict[str, Any]], config: DiagnosticConfig
) -> list[dict[str, Any]]:
    index = {(r["program_key"], r["target_cohort_year"]): decorate(r) for r in panel}
    records: list[dict[str, Any]] = []
    paths = [
        bundle / "modeling/baseline_predictions.parquet",
        bundle / "modeling/ridge_predictions.parquet",
    ]
    for path in paths:
        for pred in pq.read_table(path).to_pylist():
            if pred["model"] not in config.models:
                continue
            source = _matching_panel_row(index, pred)
            role = (
                "saved_validation_backtest"
                if pred["target_cohort_year"] == 2024
                else "saved_selection_backtest"
            )
            records.append({**source, **pred, "evidence_role": role})
    replay_path = next((bundle / "modeling/frozen-replay").glob("*/replay_predictions.parquet"))
    replay = pq.read_table(replay_path).to_pylist()
    for pred in replay:
        source = _matching_panel_row(index, pred)
        for model in config.models:
            records.append(
                {
                    **source,
                    "model": model,
                    "predicted_oar": pred[f"{model}_predicted_oar"],
                    "predicted_log_oar": pred[f"{model}_predicted_log_oar"],
                    "expected_acceptance_quartile": pred["expected_acceptance_quartile"],
                    "band_lower_oar": pred[f"{model}_band_lower_oar"],
                    "band_upper_oar": pred[f"{model}_band_upper_oar"],
                    "evidence_role": "original_frozen_replay",
                }
            )
    actual = {(r["program_key"], r["target_cohort_year"], r["model"]) for r in records}
    expected = {
        (r["program_key"], r["target_cohort_year"], model)
        for r in panel
        if r["target_cohort_year"] in config.years and r["analytic_eligible"]
        for model in config.models
    }
    if actual != expected or len(actual) != len(records):
        raise ForecastError("Saved forecasts must exactly cover every required program-year.")
    return records


def read_inputs(root: Path, config: DiagnosticConfig) -> ForecastInputs:
    """Verify hashes before Parquet parsing; never refresh or repair a saved source."""
    for relative, expected in config.input_sha256.items():
        path = root / relative
        ensure_local_path(path, root)
        if file_hash(path) != expected:
            raise ForecastError(f"Input fingerprint or path disagrees: {relative}")
    bundle = root / "artifacts/release"
    try:
        manifest = json.loads((bundle / "release_manifest.json").read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            ensure_local_path(bundle / entry["path"], bundle)
        result = validate_release_bundle(bundle)
    except (ReleaseBundleError, OSError) as exc:
        raise ForecastError(f"Preserved release failed verification: {exc}") from exc
    if result.bundle_content_sha256 != config.release_identity:
        raise ForecastError("Preserved release identity disagrees with the diagnostic settings.")
    table = pq.read_table(bundle / "processed/model_panel.parquet")
    if table.schema != MODEL_PANEL_SCHEMA:
        raise ForecastError("Trusted model panel schema has changed.")
    panel = table.to_pylist()
    release = json.loads(result.manifest_path.read_text())
    return ForecastInputs(panel, _saved_predictions(bundle, panel, config), release)
