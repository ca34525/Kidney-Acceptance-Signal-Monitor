from pathlib import Path
from typing import Any

import kasm.cli
from kasm.cli import main
from kasm.data.download import CacheSync


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
