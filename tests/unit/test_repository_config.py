from __future__ import annotations

import shlex
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def test_pytest_basetemp_is_creatable_in_a_fresh_checkout() -> None:
    config = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    addopts = shlex.split(config["tool"]["pytest"]["ini_options"]["addopts"])
    basetemp_option = next(option for option in addopts if option.startswith("--basetemp="))
    basetemp = Path(basetemp_option.partition("=")[2])

    assert not basetemp.is_absolute()
    assert basetemp.parent == Path("."), (
        "pytest creates --basetemp without parent directories, so a nested path fails when its "
        "ignored parent is absent from a fresh checkout"
    )
