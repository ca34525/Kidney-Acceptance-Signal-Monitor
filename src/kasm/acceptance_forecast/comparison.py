"""Run the single fixed retrospective comparison using only trusted public inputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kasm.acceptance_forecast.config import (
    GROUP_FIELDS,
    ComparisonConfig,
    ForecastError,
    load_comparison_config,
    load_diagnostic_config,
)
from kasm.acceptance_forecast.diagnostics import (
    paired_comparison,
    summarize_bands,
    summarize_predictions,
)
from kasm.acceptance_forecast.inputs import ForecastInputs, file_hash, read_inputs
from kasm.config import load_data_source_manifest


def verify_comparison_inputs(root: Path, config: ComparisonConfig) -> ForecastInputs:
    """Reject a changed diagnostic contract before loading its trusted release."""
    diagnostic_path = root / "configs/acceptance_forecast/diagnostics.json"
    if file_hash(diagnostic_path) != config.diagnostic_config_sha256:
        raise ForecastError("Comparison diagnostic configuration fingerprint disagrees.")
    return read_inputs(root, load_diagnostic_config(diagnostic_path))


def comparison_report(
    root: Path, config_path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Evaluate every enumerated procedure once, retaining favorable and unfavorable results."""
    from kasm.acceptance_forecast.policy import evaluate_policy
    from kasm.acceptance_forecast.procedures import generate_predictions

    config = load_comparison_config(config_path)
    inputs = verify_comparison_inputs(root, config)
    manifest = load_data_source_manifest(root / "configs/data_sources.yaml")
    records, fits = generate_predictions(inputs.panel, manifest, config)
    report = summarize_predictions(
        records, models=config.models, years=config.years, group_fields=GROUP_FIELDS
    )
    report["paired"] = {
        model: paired_comparison(
            records, candidate=model, comparator="persistence", years=config.years
        )
        for model in config.models
        if model != "persistence"
    }
    report["bands"] = summarize_bands(
        records, models=config.models, years=config.years, group_fields=GROUP_FIELDS
    )
    report["decision"] = evaluate_policy(records, config)
    report["fits"] = fits
    report["settings"] = config.raw
    report["panel_population"] = [
        {
            "target_year": year,
            "panel_rows": sum(r["target_cohort_year"] == year for r in inputs.panel),
            "missing_target": sum(
                r["target_cohort_year"] == year and r["target_oar"] is None for r in inputs.panel
            ),
            "analytic_rows": sum(
                r["target_cohort_year"] == year and r["analytic_eligible"] for r in inputs.panel
            ),
            "public_forecast_rows": sum(
                r["target_cohort_year"] == year
                and r["analytic_eligible"]
                and r["public_forecast_eligible"]
                for r in inputs.panel
            ),
        }
        for year in config.years
    ]
    report["original_frozen_decision"] = {
        "selected_model": "persistence",
        "ridge_point_promoted": False,
        "failed_criterion": "bias_must_not_exceed_persistence",
        "ridge_absolute_signed_log_bias": 0.01145157524309132,
        "persistence_absolute_signed_log_bias": 0.008854836374016146,
        "training_target_year_end": 2023,
        "source": "preserved_original_release",
    }
    return report, records, inputs.release
