from pathlib import Path
from typing import Any

from kasm.cli import main


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
