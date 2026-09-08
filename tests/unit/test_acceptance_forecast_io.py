"""Protect the preserved V1 evidence and the separate research destination."""

import json
import shutil
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from kasm.acceptance_forecast.config import ForecastError, load_diagnostic_config, read_settings
from kasm.acceptance_forecast.inputs import decorate, read_inputs
from kasm.acceptance_forecast.runs import publish_run
from kasm.modeling.features import MODEL_FEATURE_COLUMNS

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/acceptance_forecast/diagnostics.json"


def test_fixed_diagnostic_config_and_trusted_inputs() -> None:
    config = load_diagnostic_config(CONFIG)
    inputs = read_inputs(ROOT, config)
    assert config.years == (2021, 2022, 2023, 2024, 2025)
    assert inputs.panel
    assert set(inputs.release["files"][0]) >= {"path", "sha256"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("years", [2025]),
        ("percentile_method", "nearest"),
        ("output_root", "artifacts/release"),
        ("tolerances", [0.25]),
    ],
)
def test_settings_cannot_silently_change_meaning(tmp_path: Path, field: str, value: object) -> None:
    settings = json.loads(CONFIG.read_text())
    settings[field] = value
    path = tmp_path / "config.json"
    path.write_text(json.dumps(settings))
    with pytest.raises(ForecastError):
        load_diagnostic_config(path)


def test_missing_choice_and_input_corruption_fail(tmp_path: Path) -> None:
    settings = json.loads(CONFIG.read_text())
    del settings["years"]
    path = tmp_path / "config.json"
    path.write_text(json.dumps(settings))
    with pytest.raises(ForecastError):
        load_diagnostic_config(path)
    config = load_diagnostic_config(CONFIG)
    with pytest.raises(ForecastError, match="missing|fingerprint|unreadable"):
        read_inputs(tmp_path, config)


def test_publish_is_write_once_and_rejects_path_escape(tmp_path: Path) -> None:
    provenance = {"study_id": "acceptance-forecast-0027"}
    files = {"report.json": b"{}"}
    result = publish_run(tmp_path, "diagnostics-test", files, provenance)
    assert (result / "completion.json").is_file()
    with pytest.raises(ForecastError, match="exists"):
        publish_run(tmp_path, "diagnostics-test", files, provenance)
    for name in ("../release", "C:/elsewhere", "bad/name", ".."):
        with pytest.raises(ForecastError):
            publish_run(tmp_path, name, files, provenance)
    with pytest.raises(ForecastError):
        publish_run(tmp_path, "bad-payload", {"../escape": b"x"}, provenance)


def test_cli_accepts_separate_diagnostic_command() -> None:
    from kasm.cli import build_parser

    args = build_parser().parse_args(["acceptance-forecast", "diagnose", "--run-id", "test"])
    assert args.run_id == "test"


def test_nested_boolean_cannot_replace_a_fixed_numeric_choice(tmp_path: Path) -> None:
    settings = json.loads(CONFIG.read_text())
    settings["earlier_oar_cutpoints"][1] = True
    path = tmp_path / "config.json"
    path.write_text(json.dumps(settings))
    with pytest.raises(ForecastError, match="earlier_oar_cutpoints"):
        load_diagnostic_config(path)


def test_duplicate_setting_keys_are_ambiguous(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"years": [2025], "years": [2021, 2022, 2023, 2024, 2025]}')
    with pytest.raises(ForecastError, match="duplicate|invalid"):
        read_settings(path)


def test_missing_share_predictor_is_counted_even_without_a_missing_indicator() -> None:
    row: dict[str, Any] = {
        key: False if key.startswith("missing_") else 0.0 for key in MODEL_FEATURE_COLUMNS
    }
    assert decorate(row)["predictor_missingness"] == "none_missing"
    row["high_offers_share"] = None
    assert decorate(row)["predictor_missingness"] == "some_missing"


@pytest.mark.parametrize("name", ["report.json.", "con.json", "nul.png"])
def test_publish_rejects_windows_filename_aliases(tmp_path: Path, name: str) -> None:
    with pytest.raises(ForecastError, match="filename"):
        publish_run(tmp_path, "alias-test", {name: b"{}"}, {})
    assert not (tmp_path / "data").exists()


def test_payload_redirect_is_rejected_before_release_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    target = ROOT / "artifacts/release/modeling/ridge_predictions.parquet"
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == target or original(path))
    with pytest.raises(ForecastError, match="link|redirect"):
        read_inputs(ROOT, load_diagnostic_config(CONFIG))


def test_output_junction_is_rejected_without_host_link_privilege(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "is_junction", lambda path: path.name == "research")
    with pytest.raises(ForecastError, match="link|redirect"):
        publish_run(tmp_path, "junction-test", {"report.json": b"{}"}, {})
    assert not (tmp_path / "data").exists()


def test_corrupt_payload_fails_its_hash_before_parquet_parsing(tmp_path: Path) -> None:
    # Only the first two payloads are needed: the second must fail before later reads.
    bundle = tmp_path / "artifacts/release"
    (bundle / "modeling").mkdir(parents=True)
    for name in (
        "release_manifest.json",
        "modeling/baseline_metrics.json",
        "modeling/baseline_predictions.parquet",
    ):
        shutil.copyfile(ROOT / "artifacts/release" / name, bundle / name)
    (tmp_path / "configs").mkdir()
    for name in ("data_sources.yaml", "experiment.yaml", "frozen_experiment.yaml"):
        shutil.copyfile(ROOT / "configs" / name, tmp_path / "configs" / name)
    payload = bundle / "modeling/baseline_predictions.parquet"
    content = payload.read_bytes()
    payload.write_bytes(bytes([content[0] ^ 1]) + content[1:])
    with pytest.raises(ForecastError, match="checksum"):
        read_inputs(tmp_path, load_diagnostic_config(CONFIG))


def test_duplicate_run_fails_before_any_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from kasm.acceptance_forecast import commands

    publish_run(tmp_path, "existing", {"report.json": b"{}"}, {})
    monkeypatch.chdir(tmp_path)

    def unexpected_analysis(*args: object) -> None:
        pytest.fail("An existing run must be rejected before analysis or model fitting.")

    monkeypatch.setattr(commands, "diagnostic_report", unexpected_analysis)
    assert commands.run_command("diagnose", CONFIG, "existing") == 1
    assert "exists" in capsys.readouterr().out


def test_saved_prediction_cannot_change_a_panel_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    from kasm.acceptance_forecast import inputs

    original = inputs.pq.read_table

    def altered_read(path: Path) -> Any:
        table = original(path)
        if path.name == "ridge_predictions.parquet":
            records = table.to_pylist()
            records[0]["first_observed_program"] = not records[0]["first_observed_program"]
            return SimpleNamespace(to_pylist=lambda: records)
        return table

    monkeypatch.setattr(inputs.pq, "read_table", altered_read)
    with pytest.raises(ForecastError, match="first_observed_program|disagree"):
        read_inputs(ROOT, load_diagnostic_config(CONFIG))


def test_cli_input_error_is_structured_and_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from kasm.acceptance_forecast.commands import run_command

    monkeypatch.chdir(tmp_path)
    assert run_command("diagnose", tmp_path / "missing.json", "input-error") == 1
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert "Settings" in result["error"]
    assert not (tmp_path / "data").exists()


def test_release_identity_mismatch_is_not_accepted() -> None:
    config = replace(load_diagnostic_config(CONFIG), release_identity="0" * 64)
    with pytest.raises(ForecastError, match="identity"):
        read_inputs(ROOT, config)


def test_nonfinite_metadata_cannot_leave_a_partial_run(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="JSON"):
        publish_run(tmp_path, "invalid-metadata", {"report.json": b"{}"}, {"n": float("nan")})
    parent = tmp_path / "data/research/acceptance-forecast-0027"
    assert not list(parent.iterdir())
