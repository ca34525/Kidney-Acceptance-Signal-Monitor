"""Bind the new comparison to its fixed inputs without changing the frozen release."""

import json
from pathlib import Path

import pytest

from kasm.acceptance_forecast.comparison import verify_comparison_inputs
from kasm.acceptance_forecast.config import ForecastError, load_comparison_config

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/acceptance_forecast/comparison.json"


def test_comparison_requires_its_exact_diagnostic_contract(tmp_path: Path) -> None:
    settings = json.loads(CONFIG.read_text())
    settings["diagnostic_config_sha256"] = "0" * 64
    path = tmp_path / "comparison.json"
    path.write_text(json.dumps(settings))
    config = load_comparison_config(path)
    with pytest.raises(ForecastError, match="diagnostic"):
        verify_comparison_inputs(ROOT, config)


@pytest.mark.parametrize("field", ["policy", "band", "models", "tuning", "publication"])
def test_comparison_missing_design_choice_fails(tmp_path: Path, field: str) -> None:
    settings = json.loads(CONFIG.read_text())
    del settings[field]
    path = tmp_path / "comparison.json"
    path.write_text(json.dumps(settings))
    with pytest.raises(ForecastError):
        load_comparison_config(path)
