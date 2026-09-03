"""Command-line entry point for reproducible project workflows."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from kasm.config import load_data_source_manifest
from kasm.data.build import BuildError, build_cached_data
from kasm.data.cache import verify_cache
from kasm.data.download import sync_cache
from kasm.data.parse import ParseError, inspect_source_cache
from kasm.modeling.backtest import BacktestError, run_baseline_backtest
from kasm.modeling.challenger import ChallengerError, run_ridge_backtest
from kasm.modeling.experiment import ExperimentConfigError
from kasm.modeling.replay import FrozenReplayError, run_frozen_replay


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser."""
    parser = argparse.ArgumentParser(prog="kasm")
    commands = parser.add_subparsers(dest="command", required=True)
    data_parser = commands.add_parser("data")
    data_commands = data_parser.add_subparsers(dest="data_command", required=True)
    sync_parser = data_commands.add_parser("sync")
    sync_parser.add_argument("--manifest", type=Path, default=Path("configs/data_sources.yaml"))
    sync_parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/srtr"))
    verify_parser = data_commands.add_parser("verify-cache")
    verify_parser.add_argument("--manifest", type=Path, default=Path("configs/data_sources.yaml"))
    verify_parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/srtr"))
    inspect_parser = data_commands.add_parser("inspect-sources")
    inspect_parser.add_argument("--manifest", type=Path, default=Path("configs/data_sources.yaml"))
    inspect_parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/srtr"))
    build_data_parser = data_commands.add_parser("build")
    build_data_parser.add_argument(
        "--manifest", type=Path, default=Path("configs/data_sources.yaml")
    )
    build_data_parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/srtr"))
    build_data_parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    model_parser = commands.add_parser("model")
    model_commands = model_parser.add_subparsers(dest="model_command", required=True)
    backtest_parser = model_commands.add_parser("backtest")
    backtest_parser.add_argument(
        "--panel-path", type=Path, default=Path("data/processed/model_panel.parquet")
    )
    backtest_parser.add_argument("--config", type=Path, default=Path("configs/experiment.yaml"))
    backtest_parser.add_argument("--output-dir", type=Path, default=Path("data/modeling"))
    replay_parser = model_commands.add_parser("evaluate-frozen-replay")
    replay_parser.add_argument(
        "--confirm",
        action="store_true",
        required=True,
        help="Confirm the one-time, write-once retrospective replay.",
    )
    replay_parser.add_argument(
        "--panel-path", type=Path, default=Path("data/processed/model_panel.parquet")
    )
    replay_parser.add_argument(
        "--config", type=Path, default=Path("configs/frozen_experiment.yaml")
    )
    replay_parser.add_argument(
        "--source-manifest", type=Path, default=Path("configs/data_sources.yaml")
    )
    replay_parser.add_argument(
        "--output-root", type=Path, default=Path("data/modeling/frozen-replay")
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a command and return a process exit code."""
    args = build_parser().parse_args(argv)
    if args.command == "model":
        if args.model_command == "evaluate-frozen-replay":
            try:
                replay_result = run_frozen_replay(
                    panel_path=args.panel_path,
                    config_path=args.config,
                    source_manifest_path=args.source_manifest,
                    output_root=args.output_root,
                )
            except (FrozenReplayError, ExperimentConfigError, OSError) as error:
                print(json.dumps({"error": str(error), "ok": False}, indent=2, sort_keys=True))
                return 1
            print(
                json.dumps(
                    {
                        "completion_path": str(replay_result.completion_path),
                        "display_band": replay_result.display_band,
                        "displayed_model": replay_result.displayed_model,
                        "metrics_path": str(replay_result.metrics_path),
                        "ok": True,
                        "output_directory": str(replay_result.output_directory),
                        "prediction_rows": replay_result.prediction_rows,
                        "predictions_path": str(replay_result.predictions_path),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        try:
            baseline_result = run_baseline_backtest(args.panel_path, args.config, args.output_dir)
            ridge_result = run_ridge_backtest(args.panel_path, args.config, args.output_dir)
        except (BacktestError, ChallengerError, ExperimentConfigError, OSError) as error:
            print(json.dumps({"error": str(error), "ok": False}, indent=2, sort_keys=True))
            return 1
        print(
            json.dumps(
                {
                    "folds_path": str(baseline_result.folds_path),
                    "metrics_path": str(baseline_result.metrics_path),
                    "ok": True,
                    "prediction_rows": baseline_result.prediction_rows,
                    "predictions_path": str(baseline_result.predictions_path),
                    "ridge_candidate_gate_passed": ridge_result.candidate_gate_passed,
                    "ridge_metrics_path": str(ridge_result.metrics_path),
                    "ridge_prediction_rows": ridge_result.prediction_rows,
                    "ridge_predictions_path": str(ridge_result.predictions_path),
                    "ridge_selected_alpha": ridge_result.selected_alpha,
                    "ridge_selection_path": str(ridge_result.selection_path),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    manifest = load_data_source_manifest(args.manifest)
    if args.data_command == "sync":
        sync_result = sync_cache(manifest, args.cache_dir)
        print(
            json.dumps(
                {
                    "checked_sources": sync_result.checked_sources,
                    "downloaded_release_codes": sync_result.downloaded_release_codes,
                    "issues": [asdict(issue) for issue in sync_result.issues],
                    "ok": sync_result.ok,
                    "skipped_release_codes": sync_result.skipped_release_codes,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if sync_result.ok else 1

    if args.data_command == "inspect-sources":
        try:
            inventory = inspect_source_cache(manifest, args.cache_dir)
        except ParseError as error:
            print(json.dumps({"error": str(error), "ok": False}, indent=2, sort_keys=True))
            return 1
        print(
            json.dumps(
                {
                    "checked_sources": len(inventory),
                    "ok": True,
                    "releases": [asdict(entry) for entry in inventory],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.data_command == "build":
        try:
            build_result = build_cached_data(manifest, args.cache_dir, args.output_dir)
        except (BuildError, ParseError, OSError) as error:
            print(json.dumps({"error": str(error), "ok": False}, indent=2, sort_keys=True))
            return 1
        print(
            json.dumps(
                {
                    "model_panel_path": str(build_result.model_panel_path),
                    "model_panel_rows": build_result.model_panel_rows,
                    "ok": True,
                    "program_signal_rows": build_result.program_signal_rows,
                    "program_signals_path": str(build_result.program_signals_path),
                    "qa_report_path": str(build_result.qa_report_path),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    result = verify_cache(manifest, args.cache_dir)
    print(
        json.dumps(
            {
                "checked_sources": result.checked_sources,
                "issues": [asdict(issue) for issue in result.issues],
                "ok": result.ok,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.ok else 1


def entrypoint() -> None:
    """Console-script adapter."""
    raise SystemExit(main())
