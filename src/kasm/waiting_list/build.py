"""Build isolated, reproducible descriptive evidence from verified cached workbooks."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from kasm.config import load_data_source_manifest
from kasm.data.parse import load_workbook_payload, read_workbook_sheets
from kasm.patient_journey.artifacts import current_patient_journey_build_context
from kasm.waiting_list.config import OUTPUT_ROOT, ScreenError, load_config
from kasm.waiting_list.parse import REMOVAL_FIELDS, AnnualRecord, parse_release, select_vintages
from kasm.waiting_list.screen import compare_years, summarize_counts, verdict

_CONFIG = Path("configs/waiting_list/experiment.json")
_SOURCES = Path("configs/waiting_list/sources.json")
_SPEC = Path("docs/specs/waiting-list-0025.md")
_SOURCE_LEDGER_HASH = "274dd40bb00b79f3ab456ba5ca97f334e86e98f6f7a0a438d93ba654f36833eb"


def _json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def load_sources(path: Path) -> dict[str, Any]:
    """Keep the reviewed dates, bindings, categories and excluded releases fixed."""
    content = path.read_bytes()
    if sha256(content).hexdigest() != _SOURCE_LEDGER_HASH:
        raise ScreenError("The reviewed source ledger changed; do not reinterpret its years.")
    return cast(dict[str, Any], json.loads(content))


def verify_reference(root: Path, name: str, fingerprint: str) -> None:
    """Require the unchanged local evidence used to establish the year mapping."""
    relative = Path(name)
    if relative.is_absolute() or relative.drive or ".." in relative.parts:
        raise ScreenError("Source evidence must use a confined relative path.")
    root = root.resolve()
    path = root / relative
    if not path.resolve().is_relative_to(root / "data"):
        raise ScreenError("Source evidence must remain in the local data cache.")
    for current in (path, *path.parents):
        if current == root:
            break
        if current.is_symlink() or current.is_junction():
            raise ScreenError("Source evidence cannot follow a filesystem link.")
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= 20 * 1024 * 1024:
            raise ScreenError("Source evidence file is missing or has an invalid size.")
        if sha256(path.read_bytes()).hexdigest() != fingerprint:
            raise ScreenError("Source evidence fingerprint changed.")
    except OSError as exc:
        raise ScreenError("Cannot read required source evidence.") from exc


def prepare_destination(root: Path, identity: str) -> Path:
    """Create one new run, confined to this study and without directory redirects."""
    if re.fullmatch(r"[a-f0-9]{64}", identity) is None:
        raise ScreenError("Run identity must be a lowercase SHA-256 fingerprint.")
    root = root.resolve()
    destination = root / OUTPUT_ROOT / identity
    for current in (destination, *destination.parents):
        if current == root:
            break
        if current.is_symlink() or current.is_junction():
            raise ScreenError("Research output cannot follow a filesystem link.")
    if not destination.resolve().is_relative_to(root / OUTPUT_ROOT):
        raise ScreenError("Research output escapes the fixed root.")
    try:
        destination.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise ScreenError("This run already exists; preserve its evidence.") from exc
    return destination


def write_evidence(
    root: Path,
    identity: str,
    payloads: dict[str, object],
    provenance: dict[str, Any],
) -> Path:
    """Write hashes and a final completion marker; never overwrite a completed run."""
    if any(
        re.fullmatch(r"[a-z_]+\.json", name) is None or name in {"provenance.json", "complete.json"}
        for name in payloads
    ):
        raise ScreenError("Invalid research evidence filename.")
    destination = prepare_destination(root, identity)
    hashes = {}
    for name, value in (payloads | {"provenance.json": provenance}).items():
        content = _json(value)
        with (destination / name).open("xb") as stream:
            stream.write(content)
        hashes[name] = sha256(content).hexdigest()
    with (destination / "complete.json").open("xb") as stream:
        stream.write(_json({"run_identity": identity, "sha256": hashes}))
    return destination


def _bind_report(rows: tuple[AnnualRecord, ...], binding: dict[str, Any]) -> None:
    """Match all published B1 example counts, including column-year direction."""
    expected = binding["report_counts"]
    actual = {}
    for row in rows:
        if row.program_key != binding["matched_program_key"]:
            continue
        suffix = f"NC{binding['years'].index(row.year) + 1}"
        values = {"ST": row.start, "END": row.end, "ADDCEN": row.additions}
        values.update(zip(REMOVAL_FIELDS, row.removals, strict=True))
        actual.update({f"WLA_{key}_{suffix}": value for key, value in values.items()})
    if len(expected) != 22 or actual != expected:
        raise ScreenError(f"Release {binding['release_code']} report/workbook binding failed.")


def _read_releases(root: Path, ledger: dict[str, Any]) -> tuple[AnnualRecord, ...]:
    manifest = load_data_source_manifest(root / "configs/data_sources.yaml")
    if (
        ledger["source_manifest_sha256"]
        != sha256((root / "configs/data_sources.yaml").read_bytes()).hexdigest()
    ):
        raise ScreenError("Source manifest changed since the B1 evidence review.")
    bindings = {row["release_code"]: row for row in ledger["releases"]}
    if len(bindings) != 9 or set(bindings) != {s.release_code for s in manifest.sources}:
        raise ScreenError("Source ledger must contain the nine pinned releases exactly once.")
    records: list[AnnualRecord] = []
    for source in manifest.sources:
        binding = bindings[source.release_code]
        payload = load_workbook_payload(source, root / "data/raw/srtr")
        if binding["verified"] is not True:
            continue
        verify_reference(root, binding["evidence_path"], binding["evidence_sha256"])
        if binding["original_pdf_path"] is not None:
            verify_reference(root, binding["original_pdf_path"], binding["report_sha256"])
        sheets = read_workbook_sheets(payload)
        years = tuple(binding["years"])
        if len(years) != 2:
            raise ScreenError("Source ledger requires two verified B1 calendar years.")
        rows = parse_release(source, sheets, (years[0], years[1]))
        if len(rows) != 2 * binding["expected_rows"]:
            raise ScreenError(f"Release {source.release_code} Table B1 population changed.")
        _bind_report(rows, binding)
        records.extend(rows)
    return tuple(records)


def _coverage(records: tuple[AnnualRecord, ...]) -> dict[int, Any]:
    years = sorted({row.year for row in records})
    lookup = {year: {row.program_key for row in records if row.year == year} for year in years}
    annual = {}
    seen: set[str] = set()
    for year in years:
        rows = tuple(row for row in records if row.year == year)
        previous = lookup.get(year - 1, set())
        annual[year] = {
            "source_programs": len(rows),
            "clean_programs": sum(row.clean for row in rows),
            "missing_cells": sum(
                value is None
                for row in rows
                for value in (row.start, row.end, row.additions, *row.removals)
            ),
            "residual_programs": sum(row.residual not in (0, None) for row in rows),
            "zero_start_programs": sum(row.start == 0 for row in rows),
            "newly_observed": sorted(lookup[year] - seen),
            "apparent_exits": sorted(previous - lookup[year]),
            "matched_previous_programs": len(previous & lookup[year]),
        }
        seen.update(lookup[year])
    return annual


def build(root: Path) -> Path:
    """Read trusted settings, verify sources, and save this screen without any fit."""
    root = root.resolve()
    config = load_config(root / _CONFIG)
    ledger = load_sources(root / _SOURCES)
    context = current_patient_journey_build_context(root)
    paths = [_CONFIG, _SOURCES, _SPEC, Path("configs/data_sources.yaml"), Path("uv.lock")]
    paths.extend(
        path.relative_to(root)
        for folder in ("src/kasm/waiting_list", "src/kasm/data")
        for path in sorted((root / folder).glob("*.py"))
    )
    paths.extend((Path("src/kasm/config.py"), Path("src/kasm/patient_journey/artifacts.py")))
    hashes = {path.as_posix(): sha256((root / path).read_bytes()).hexdigest() for path in paths}
    identity = sha256(_json(hashes)).hexdigest()
    # Fail before reading comparative outputs if this immutable run already exists.
    if (root / OUTPUT_ROOT / identity).exists():
        raise ScreenError("This run already exists; preserve its evidence.")
    all_records = _read_releases(root, ledger)
    release_order = tuple(row["release_code"] for row in ledger["releases"] if row["verified"])
    records, revisions = select_vintages(all_records, release_order)
    if tuple(sorted({row.year for row in records})) != config.source_years:
        raise ScreenError("Verified calendar years disagree with the fixed screen.")
    coverage = _coverage(records)
    pairs, exclusions = compare_years(records)
    matched = {year: values["matched_previous_programs"] for year, values in coverage.items()}
    result = verdict(pairs, matched, config)
    qa = {
        "annual": coverage,
        "excluded_releases": [row for row in ledger["releases"] if not row["verified"]],
        "absent_candidate_years": [2016],
        "exclusions": exclusions,
        "exclusion_counts": dict(Counter(row["reason"] for row in exclusions)),
        "revision_comparisons": len(revisions),
        "revision_disagreements": sum(bool(row.changed_fields) for row in revisions),
        "shrinking": summarize_counts(tuple(row for row in pairs if row.growth < 0)),
    }
    provenance = {
        "analysis_id": config.analysis_id,
        "input_sha256": hashes,
        "git_commit": context.git_commit_sha,
        "git_worktree_dirty": context.git_worktree_dirty,
        "build_time_utc": context.build_timestamp_utc.isoformat(),
        "python_version": context.python_version,
        "years": config.source_years,
        "source_releases": ledger["releases"],
        "model_parameters": None,
        "feature_schema": None,
        "calculation_schema": {
            "unit": "program and calendar year; registration/removal events",
            "transplant_categories": config.transplant_categories,
            "removal_order": REMOVAL_FIELDS,
            "normalization": "100 * count / current.start",
            "growth": "end - start",
            "change_in_growth": "growth - previous.growth",
        },
        "verification": "Build completion only; required code checks are recorded in the plan.",
    }
    annual = [
        asdict(row) | {"growth": row.growth, "residual": row.residual, "clean": row.clean}
        for row in records
    ]
    comparisons = [
        asdict(row)
        | {
            "growth_per100": row.growth_per100,
            "change_in_growth_per100": row.change_in_growth_per100,
            "transplant_increased": row.transplant_increased,
        }
        for row in pairs
    ]
    return write_evidence(
        root,
        identity,
        {
            "annual.json": annual,
            "revisions.json": [asdict(row) for row in revisions],
            "comparisons.json": comparisons,
            "summary.json": result,
            "qa.json": qa,
        },
        provenance,
    )


if __name__ == "__main__":
    print(build(Path.cwd()))
