"""Offline entry points for the two fixed Plan 0027 research stages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kasm.acceptance_forecast.config import GROUP_FIELDS, ForecastError, load_diagnostic_config
from kasm.acceptance_forecast.diagnostics import (
    paired_comparison,
    summarize_bands,
    summarize_predictions,
)
from kasm.acceptance_forecast.inputs import read_inputs
from kasm.acceptance_forecast.runs import json_bytes, provenance, publish_run, validate_destination


def diagnostic_report(
    root: Path, config_path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Describe saved predictions without fitting or changing any original evidence."""
    config = load_diagnostic_config(config_path)
    inputs = read_inputs(root, config)
    records = inputs.predictions
    report = summarize_predictions(
        records,
        models=config.models,
        years=config.years,
        tolerances=config.tolerances,
        group_fields=GROUP_FIELDS,
    )
    report["paired"] = paired_comparison(
        records, candidate="ridge", comparator="persistence", years=config.years
    )
    report["bands"] = summarize_bands(
        [r for r in records if r["target_cohort_year"] == 2025],
        models=config.models,
        years=(2025,),
        group_fields=GROUP_FIELDS,
    )
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
    report["settings"] = config.raw
    return report, records, inputs.release


def run_command(command: str, config_path: Path, run_id: str) -> int:
    """Return a structured domain error instead of partially publishing a run."""
    root = Path.cwd()
    try:
        validate_destination(root, run_id)
        if command == "diagnose":
            report, records, release = diagnostic_report(root, config_path)
        else:
            from kasm.acceptance_forecast.comparison import comparison_report

            report, records, release = comparison_report(root, config_path)
        metadata = provenance(root, config_path, release, run_id)
        from kasm.acceptance_forecast.plots import render_error_plots

        files = {
            "report.json": json_bytes(report),
            "predictions.json": json_bytes(records),
            **render_error_plots(records, metadata),
        }
        destination = publish_run(root, run_id, files, metadata)
    except (ForecastError, ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps({"ok": True, "output_directory": str(destination)}))
    return 0
