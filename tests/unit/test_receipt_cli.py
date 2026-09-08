"""The source-only command never invokes a model fit."""

from pathlib import Path
from types import SimpleNamespace

from kasm.cli import main
from kasm.patient_journey.receipt_config import ReceiptError


def test_source_only_cli_reports_population_without_fitting(monkeypatch, capsys) -> None:
    calls = []

    def prepare(root: Path):
        calls.append("prepare")
        return None, None, SimpleNamespace(qa={"origin_programs": 2})

    def forbidden(root: Path):
        raise AssertionError("Source-only preflight must not fit")

    monkeypatch.setattr("kasm.cli.prepare_receipt_study", prepare)
    monkeypatch.setattr("kasm.cli.build_receipt_study", forbidden)
    assert main(["patient-journey", "receipt-study", "--check-sources"]) == 0
    assert calls == ["prepare"]
    assert '"models_fitted": false' in capsys.readouterr().out


def test_receipt_cli_surfaces_source_gate_failure(monkeypatch, capsys) -> None:
    def fail(root: Path):
        raise ReceiptError("Independent source dates are missing")

    monkeypatch.setattr("kasm.cli.prepare_receipt_study", fail)
    assert main(["patient-journey", "receipt-study", "--check-sources"]) == 1
    assert "Independent source dates are missing" in capsys.readouterr().out


def test_receipt_cli_returns_verified_result_location(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setattr("kasm.cli.build_receipt_study", lambda root: tmp_path / "study")
    assert main(["patient-journey", "receipt-study"]) == 0
    assert '"output_directory"' in capsys.readouterr().out
