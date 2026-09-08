"""Choices fixed before describing the completed waiting-list screen further."""

from __future__ import annotations

import json
import math
import os
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

OUTPUT_ROOT = Path("data/research/waiting-list-case-study-0026")
INPUT_ROOT = Path("data/research/waiting-list-0025")


class CaseStudyError(ValueError):
    """The case study cannot safely use or publish these records."""


@dataclass(frozen=True)
class CaseStudyConfig:
    """One fixed description of previously inspected program-year records."""

    analysis_id: str = "waiting_list_case_study_0026_v1"
    schema_version: int = 1
    years: tuple[int, ...] = (2023, 2024, 2025)
    example_year: int = 2025
    percentile_method: str = "linear"
    selection_rule: str = "lower_middle_start_then_program_key"
    common_programs: int = 169
    output_root: str = OUTPUT_ROOT.as_posix()
    input_run: str = "ad9a92cc0d20d407ab118f6b171e24bd9182a35557f149285a36035c45106cc4"
    input_complete_sha256: str = "2b24e865f2247fe11d190f7f89b8f49aa1da530ad2756f485ff7831b00bf243e"
    promotion_allowed: bool = False


def bounded_bytes(path: Path, limit: int) -> bytes:
    """Read a bounded regular file while rejecting links and concurrent replacement."""
    try:
        if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
            raise CaseStudyError(f"Input cannot follow a filesystem link: {path.name}.")
        before = path.stat()
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= limit:
            raise CaseStudyError(f"Input has invalid regular-file size: {path.name}.")
        descriptor = os.open(
            path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                raise CaseStudyError(f"Input changed before reading: {path.name}.")
            content = stream.read(limit + 1)
            closed = os.fstat(stream.fileno())
        after = path.stat()
        if (
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            != (closed.st_dev, closed.st_ino, closed.st_size, closed.st_mtime_ns)
            or len(content) != before.st_size
            or len(content) > limit
            or any(p.is_symlink() or p.is_junction() for p in (path, *path.parents))
        ):
            raise CaseStudyError(f"Input changed while reading: {path.name}.")
        return content
    except OSError as exc:
        raise CaseStudyError(
            f"Cannot read required input {path.name}; restore the trusted cache."
        ) from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CaseStudyError("Input JSON contains duplicate object keys.")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise CaseStudyError("Input JSON numbers must be finite.")
    return result


def _invalid_constant(value: str) -> None:
    raise CaseStudyError(f"Input JSON contains nonfinite value {value}.")


def read_json(content: bytes) -> Any:
    """Reject ambiguous keys, nonfinite numbers and malformed JSON at the boundary."""
    try:
        return json.loads(
            content,
            object_pairs_hook=_unique_object,
            parse_float=_finite_float,
            parse_constant=_invalid_constant,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise CaseStudyError(f"Cannot read valid input JSON: {exc}") from exc


def same_json(first: object, second: object) -> bool:
    """Compare values and JSON number types, keeping booleans distinct from counts."""
    return json.dumps(first, sort_keys=True, allow_nan=False) == json.dumps(
        second, sort_keys=True, allow_nan=False
    )


def load_config(path: Path) -> CaseStudyConfig:
    """Reject tuning, added settings and type coercion in this fixed contract."""
    raw = read_json(bounded_bytes(path, 2 * 1024 * 1024))
    if not same_json(raw, asdict(CaseStudyConfig())):
        raise CaseStudyError("Settings disagree with the fixed case-study contract.")
    return CaseStudyConfig()
