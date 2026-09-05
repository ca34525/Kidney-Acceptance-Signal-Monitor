"""Command-line entry point for reproducible project workflows."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from kasm.config import ManifestError, load_data_source_manifest
from kasm.data.build import BuildError, build_cached_data
from kasm.data.cache import verify_cache
from kasm.data.download import sync_cache
from kasm.data.parse import ParseError, inspect_source_cache
from kasm.modeling.backtest import BacktestError, run_baseline_backtest
from kasm.modeling.challenger import ChallengerError, run_ridge_backtest
from kasm.modeling.experiment import ExperimentConfigError
from kasm.modeling.replay import FrozenReplayError, run_frozen_replay
from kasm.patient_journey.artifacts import (
    PatientJourneyArtifactError,
    build_cached_patient_journey_artifacts,
)
from kasm.patient_journey.config import PatientJourneyConfigError
from kasm.patient_journey.followup_analysis import FollowupAnalysisError
from kasm.patient_journey.followup_artifacts import FollowupArtifactError, build_followup
from kasm.patient_journey.followup_config import FollowupConfigError
from kasm.patient_journey.ledger import MethodologyLedgerError
from kasm.patient_journey.model_artifacts import (
    PatientJourneyModelArtifactError,
    build_patient_journey_model_artifacts,
)
from kasm.patient_journey.modeling import PatientJourneyModelError
from kasm.patient_journey.panel import PatientJourneyPanelError
from kasm.patient_journey.parse import PatientJourneyParseError
from kasm.patient_journey.release import (
    PatientJourneyReleaseError,
    build_patient_journey_release_bundle,
)
from kasm.reporting.artifacts import ReleaseBundleError, build_release_bundle


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
    patient_journey_parser = commands.add_parser("patient-journey")
    patient_journey_commands = patient_journey_parser.add_subparsers(
        dest="patient_journey_command", required=True
    )
    followup_parser = patient_journey_commands.add_parser("follow-up")
    followup_parser.add_argument(
        "--config", type=Path, default=Path("configs/patient_journey_v2_followup/experiment.yaml")
    )
    patient_journey_data_parser = patient_journey_commands.add_parser("data")
    patient_journey_data_commands = patient_journey_data_parser.add_subparsers(
        dest="patient_journey_data_command", required=True
    )
    patient_journey_build_parser = patient_journey_data_commands.add_parser("build")
    patient_journey_build_parser.add_argument(
        "--manifest", type=Path, default=Path("configs/data_sources.yaml")
    )
    patient_journey_build_parser.add_argument(
        "--methodology",
        type=Path,
        default=Path("configs/patient_journey_v2/methodology.yaml"),
    )
    patient_journey_build_parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/patient_journey_v2/experiment.yaml"),
    )
    patient_journey_build_parser.add_argument(
        "--cache-dir", type=Path, default=Path("data/raw/srtr")
    )
    patient_journey_build_parser.add_argument("--lock", type=Path, default=Path("uv.lock"))
    patient_journey_model_parser = patient_journey_commands.add_parser("model")
    patient_journey_model_commands = patient_journey_model_parser.add_subparsers(
        dest="patient_journey_model_command", required=True
    )
    patient_journey_evaluate_parser = patient_journey_model_commands.add_parser("evaluate")
    patient_journey_evaluate_parser.add_argument(
        "--manifest", type=Path, default=Path("configs/data_sources.yaml")
    )
    patient_journey_evaluate_parser.add_argument(
        "--methodology",
        type=Path,
        default=Path("configs/patient_journey_v2/methodology.yaml"),
    )
    patient_journey_evaluate_parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/patient_journey_v2/experiment.yaml"),
    )
    patient_journey_evaluate_parser.add_argument("--lock", type=Path, default=Path("uv.lock"))
    patient_journey_artifact_parser = patient_journey_commands.add_parser("artifacts")
    patient_journey_artifact_commands = patient_journey_artifact_parser.add_subparsers(
        dest="patient_journey_artifact_command", required=True
    )
    patient_journey_release_parser = patient_journey_artifact_commands.add_parser("build")
    patient_journey_release_parser.add_argument(
        "--manifest", type=Path, default=Path("configs/data_sources.yaml")
    )
    patient_journey_release_parser.add_argument(
        "--methodology",
        type=Path,
        default=Path("configs/patient_journey_v2/methodology.yaml"),
    )
    patient_journey_release_parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/patient_journey_v2/experiment.yaml"),
    )
    patient_journey_release_parser.add_argument("--lock", type=Path, default=Path("uv.lock"))
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
    artifacts_parser = commands.add_parser("artifacts")
    artifacts_commands = artifacts_parser.add_subparsers(dest="artifacts_command", required=True)
    release_parser = artifacts_commands.add_parser("build")
    release_parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    release_parser.add_argument("--modeling-dir", type=Path, default=Path("data/modeling"))
    release_parser.add_argument(
        "--source-manifest", type=Path, default=Path("configs/data_sources.yaml")
    )
    release_parser.add_argument(
        "--experiment-config", type=Path, default=Path("configs/experiment.yaml")
    )
    release_parser.add_argument(
        "--frozen-experiment", type=Path, default=Path("configs/frozen_experiment.yaml")
    )
    release_parser.add_argument("--lock", type=Path, default=Path("uv.lock"))
    release_parser.add_argument("--output-dir", type=Path, default=Path("artifacts/release"))
    return parser


def _print_command_error(error: Exception) -> int:
    print(json.dumps({"error": str(error), "ok": False}, indent=2, sort_keys=True))
    return 1


def _run_patient_journey_command(args: argparse.Namespace) -> int:
    if args.patient_journey_command == "follow-up":
        try:
            output = build_followup(repository_root=Path.cwd(), config_path=args.config)
        except (
            FollowupAnalysisError,
            FollowupArtifactError,
            FollowupConfigError,
            PatientJourneyModelError,
            PatientJourneyArtifactError,
        ) as exc:
            return _print_command_error(exc)
        print(json.dumps({"ok": True, "output_directory": str(output)}, indent=2, sort_keys=True))
        return 0
    if args.patient_journey_command == "artifacts":
        try:
            release_result = build_patient_journey_release_bundle(
                repository_root=Path.cwd(),
                source_manifest_path=args.manifest,
                experiment_config_path=args.config,
                methodology_path=args.methodology,
                lock_path=args.lock,
            )
        except (
            ManifestError,
            MethodologyLedgerError,
            PatientJourneyArtifactError,
            PatientJourneyConfigError,
            PatientJourneyModelArtifactError,
            PatientJourneyModelError,
            PatientJourneyReleaseError,
            OSError,
        ) as error:
            return _print_command_error(error)
        payload = {
            "bundle_content_sha256": release_result.bundle_content_sha256,
            "file_count": release_result.file_count,
            "manifest_path": str(release_result.manifest_path),
            "ok": True,
            "output_directory": str(release_result.output_directory),
            "total_bytes": release_result.total_bytes,
        }
    elif args.patient_journey_command == "model":
        try:
            model_result = build_patient_journey_model_artifacts(
                repository_root=Path.cwd(),
                source_manifest_path=args.manifest,
                experiment_config_path=args.config,
                methodology_path=args.methodology,
                lock_path=args.lock,
            )
        except (
            ManifestError,
            MethodologyLedgerError,
            PatientJourneyArtifactError,
            PatientJourneyConfigError,
            PatientJourneyModelArtifactError,
            PatientJourneyModelError,
            OSError,
        ) as error:
            return _print_command_error(error)
        payload = {
            "artifact_set_sha256": model_result.artifact_set_sha256,
            "evaluation_path": str(model_result.evaluation_path),
            "manifest_path": str(model_result.manifest_path),
            "ok": True,
            "output_directory": str(model_result.output_directory),
            "prediction_rows": model_result.prediction_rows,
            "predictions_path": str(model_result.predictions_path),
        }
    else:
        try:
            data_result = build_cached_patient_journey_artifacts(
                repository_root=Path.cwd(),
                source_manifest_path=args.manifest,
                experiment_config_path=args.config,
                methodology_path=args.methodology,
                cache_dir=args.cache_dir,
                lock_path=args.lock,
            )
        except (
            ManifestError,
            MethodologyLedgerError,
            ParseError,
            PatientJourneyArtifactError,
            PatientJourneyConfigError,
            PatientJourneyPanelError,
            PatientJourneyParseError,
            OSError,
        ) as error:
            return _print_command_error(error)
        payload = {
            "artifact_set_sha256": data_result.artifact_set_sha256,
            "manifest_path": str(data_result.manifest_path),
            "ok": True,
            "output_directory": str(data_result.output_directory),
            "panel_path": str(data_result.panel_path),
            "panel_rows": data_result.panel_rows,
            "qa_report_path": str(data_result.qa_report_path),
            "safety_path": str(data_result.safety_path),
            "safety_rows": data_result.safety_rows,
        }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run a command and return a process exit code."""
    args = build_parser().parse_args(argv)
    if args.command == "patient-journey":
        return _run_patient_journey_command(args)
    if args.command == "artifacts":
        try:
            release_result = build_release_bundle(
                processed_dir=args.processed_dir,
                modeling_dir=args.modeling_dir,
                source_manifest_path=args.source_manifest,
                experiment_config_path=args.experiment_config,
                frozen_experiment_path=args.frozen_experiment,
                lock_path=args.lock,
                output_dir=args.output_dir,
            )
        except (ReleaseBundleError, OSError) as error:
            print(json.dumps({"error": str(error), "ok": False}, indent=2, sort_keys=True))
            return 1
        print(
            json.dumps(
                {
                    "bundle_content_sha256": release_result.bundle_content_sha256,
                    "file_count": release_result.file_count,
                    "manifest_path": str(release_result.manifest_path),
                    "ok": True,
                    "output_directory": str(release_result.output_directory),
                    "total_bytes": release_result.total_bytes,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
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
