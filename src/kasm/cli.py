"""Command-line entry point for reproducible project workflows."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from kasm.config import load_data_source_manifest
from kasm.data.cache import verify_cache
from kasm.data.download import sync_cache


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
