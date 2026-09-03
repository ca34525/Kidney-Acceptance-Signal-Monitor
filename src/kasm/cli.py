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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a command and return a process exit code."""
    args = build_parser().parse_args(argv)
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
