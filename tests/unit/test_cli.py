from pathlib import Path
from typing import Any

import kasm.cli
from kasm.cli import main
from kasm.data.build import DataBuildResult
from kasm.data.download import CacheSync
from kasm.data.parse import ParseError, SourceInventoryEntry
from kasm.modeling.backtest import BaselineBacktestResult
from kasm.modeling.challenger import RidgeBacktestResult


def test_verify_cache_command_returns_failure_and_names_missing_release(
    tmp_path: Path, capsys: Any
) -> None:
    exit_code = main(
        [
            "data",
            "verify-cache",
            "--manifest",
            "configs/data_sources.yaml",
            "--cache-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert '"release_code": "1808"' in captured.out


def test_sync_command_reports_downloaded_and_skipped_sources(
    tmp_path: Path, capsys: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(
        kasm.cli,
        "sync_cache",
        lambda manifest, cache_dir: CacheSync(
            checked_sources=len(manifest.sources),
            downloaded_release_codes=("1808",),
            skipped_release_codes=("1905",),
            issues=(),
        ),
    )
    exit_code = main(
        [
            "data",
            "sync",
            "--manifest",
            "configs/data_sources.yaml",
            "--cache-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert '"downloaded_release_codes": [\n    "1808"' in captured.out
    assert '"skipped_release_codes": [\n    "1905"' in captured.out


def test_inspect_sources_command_reports_parser_inventory(
    tmp_path: Path, capsys: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(
        kasm.cli,
        "inspect_source_cache",
        lambda manifest, cache_dir: (
            SourceInventoryEntry(
                release_code="1808",
                cohort_year=2017,
                sheet_name="Table B10 & Figures B7-B11",
                source_rows=238,
                source_columns=125,
                signal_rows=1190,
            ),
        ),
    )

    exit_code = main(
        [
            "data",
            "inspect-sources",
            "--manifest",
            "configs/data_sources.yaml",
            "--cache-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert '"release_code": "1808"' in captured.out
    assert '"signal_rows": 1190' in captured.out
    assert '"ok": true' in captured.out


def test_inspect_sources_command_reports_contract_failure(
    tmp_path: Path, capsys: Any, monkeypatch: Any
) -> None:
    def fail_inspection(manifest: object, cache_dir: Path) -> tuple[SourceInventoryEntry, ...]:
        raise ParseError("Release '1808' row count changed")

    monkeypatch.setattr(kasm.cli, "inspect_source_cache", fail_inspection)

    exit_code = main(
        [
            "data",
            "inspect-sources",
            "--manifest",
            "configs/data_sources.yaml",
            "--cache-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert '"ok": false' in captured.out
    assert "row count changed" in captured.out


def test_data_build_command_reports_canonical_paths_and_counts(
    tmp_path: Path, capsys: Any, monkeypatch: Any
) -> None:
    output_dir = tmp_path / "processed"
    monkeypatch.setattr(
        kasm.cli,
        "build_cached_data",
        lambda manifest, cache_dir, destination: DataBuildResult(
            program_signals_path=destination / "program_signals.parquet",
            model_panel_path=destination / "model_panel.parquet",
            qa_report_path=destination / "qa_report.json",
            program_signal_rows=10515,
            model_panel_rows=2103,
        ),
    )

    exit_code = main(
        [
            "data",
            "build",
            "--manifest",
            "configs/data_sources.yaml",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert '"program_signal_rows": 10515' in captured.out
    assert '"model_panel_rows": 2103' in captured.out
    assert str(output_dir / "qa_report.json").replace("\\", "\\\\") in captured.out


def test_model_backtest_command_reports_artifacts_without_loading_source_cache(
    tmp_path: Path, capsys: Any, monkeypatch: Any
) -> None:
    output_dir = tmp_path / "modeling"
    monkeypatch.setattr(
        kasm.cli,
        "run_baseline_backtest",
        lambda panel_path, config_path, destination: BaselineBacktestResult(
            predictions_path=destination / "baseline_predictions.parquet",
            metrics_path=destination / "baseline_metrics.json",
            folds_path=destination / "temporal_folds.json",
            prediction_rows=2760,
        ),
    )
    monkeypatch.setattr(
        kasm.cli,
        "run_ridge_backtest",
        lambda panel_path, config_path, destination: RidgeBacktestResult(
            predictions_path=destination / "ridge_predictions.parquet",
            metrics_path=destination / "ridge_metrics.json",
            selection_path=destination / "ridge_selection.json",
            prediction_rows=920,
            selected_alpha=10.0,
            candidate_gate_passed=True,
        ),
    )

    exit_code = main(
        [
            "model",
            "backtest",
            "--panel-path",
            str(tmp_path / "model_panel.parquet"),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert '"prediction_rows": 2760' in captured.out
    assert '"ridge_prediction_rows": 920' in captured.out
    assert '"ridge_selected_alpha": 10.0' in captured.out
    assert str(output_dir / "baseline_metrics.json").replace("\\", "\\\\") in captured.out
