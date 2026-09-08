"""Generate write-once offline reports from the completed waiting-list records."""

from __future__ import annotations

import argparse
import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from kasm.patient_journey.artifacts import current_patient_journey_build_context
from kasm.waiting_list_case_study.config import OUTPUT_ROOT, bounded_bytes, read_json

_CONFIG = Path("configs/waiting_list_case_study/experiment.json")
_SPEC = Path("docs/specs/waiting-list-case-study-0026.md")
_NAME = r"[a-z][a-z0-9_]*\.(json|html|svg|png|csv)"


def _json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _destination(root: Path, identity: str) -> Path:
    if re.fullmatch(r"[a-f0-9]{64}", identity) is None:
        raise ValueError("Run identity must be a lowercase SHA-256 fingerprint.")
    if any(path.is_symlink() or path.is_junction() for path in (root, *root.parents)):
        raise ValueError("Case-study root cannot follow a filesystem link or redirect.")
    root = root.resolve()
    destination = root / OUTPUT_ROOT / identity
    for current in (destination, *destination.parents):
        if current == root:
            break
        if current.is_symlink() or current.is_junction():
            raise ValueError("Case-study output cannot follow a filesystem link or redirect.")
    if not destination.resolve().is_relative_to(root / OUTPUT_ROOT):
        raise ValueError("Case-study output must remain inside its fixed root.")
    return destination


def write_run(
    root: Path, identity: str, payloads: dict[str, bytes], provenance: dict[str, Any]
) -> Path:
    """Write a new report and fingerprint every payload before marking completion."""
    if not payloads or any(
        re.fullmatch(_NAME, name) is None or name in {"complete.json", "provenance.json"}
        for name in payloads
    ):
        raise ValueError("Invalid case-study output filename.")
    destination = _destination(root, identity)
    contents = payloads | {"provenance.json": _json(provenance)}
    if any(not isinstance(value, bytes) or not value for value in contents.values()):
        raise ValueError("Case-study output must contain nonempty bytes.")
    try:
        destination.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise ValueError("This run already exists; preserve its evidence.") from exc
    hashes = {}
    for name, content in contents.items():
        with (destination / name).open("xb") as stream:
            stream.write(content)
        hashes[name] = sha256(content).hexdigest()
    with (destination / "complete.json").open("xb") as stream:
        stream.write(_json({"run_identity": identity, "sha256": hashes}))
    return destination


def _read_output(destination: Path, name: str) -> bytes:
    path = destination / name
    if path.is_symlink() or path.is_junction():
        raise ValueError("Case-study output cannot follow a filesystem link.")
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= 30 * 1024 * 1024:
            raise ValueError(f"Case-study output {name} is missing or has invalid size.")
        return bounded_bytes(path, 30 * 1024 * 1024)
    except OSError as exc:
        raise ValueError(f"Cannot read case-study output {name}.") from exc


def verify_run(root: Path, identity: str) -> dict[str, Any]:
    """Check the saved run's file inventory and every payload fingerprint offline."""
    destination = _destination(root, identity)
    try:
        marker = read_json(_read_output(destination, "complete.json"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Case-study completion marker is missing or malformed.") from exc
    if (
        not isinstance(marker, dict)
        or set(marker) != {"run_identity", "sha256"}
        or marker["run_identity"] != identity
        or not isinstance(marker["sha256"], dict)
        or "provenance.json" not in marker["sha256"]
    ):
        raise ValueError("Case-study completion marker schema or identity changed.")
    for name, fingerprint in marker["sha256"].items():
        if (
            re.fullmatch(_NAME, name) is None
            or name == "complete.json"
            or not isinstance(fingerprint, str)
            or re.fullmatch(r"[a-f0-9]{64}", fingerprint) is None
        ):
            raise ValueError("Invalid case-study completion filename or fingerprint.")
        if sha256(_read_output(destination, name)).hexdigest() != fingerprint:
            raise ValueError(f"Case-study output fingerprint changed: {name}.")
    if {path.name for path in destination.iterdir()} != set(marker["sha256"]) | {"complete.json"}:
        raise ValueError("Case-study output inventory differs from the completion marker.")
    return cast(dict[str, Any], marker)


def _implementation_hashes(root: Path) -> dict[str, str]:
    paths = [
        _CONFIG,
        _SPEC,
        Path("uv.lock"),
        Path("src/kasm/patient_journey/artifacts.py"),
        Path("src/kasm/reporting/history.py"),
        Path("src/kasm/config.py"),
        Path("src/kasm/data/parse.py"),
    ]
    for folder in ("src/kasm/waiting_list_case_study", "src/kasm/waiting_list"):
        paths.extend(
            path.relative_to(root)
            for path in sorted((root / folder).iterdir())
            if path.suffix in {".py", ".html"}
        )
    return {path.as_posix(): sha256((root / path).read_bytes()).hexdigest() for path in paths}


def build(root: Path, program_key: str | None = None, year: int = 2025) -> Path:
    """Build the case study, or use the same template for a requested comparison."""
    from kasm.waiting_list_case_study.analysis import (
        program_brief,
        select_examples,
        summarize_distributions,
    )
    from kasm.waiting_list_case_study.config import load_config
    from kasm.waiting_list_case_study.inputs import load_inputs
    from kasm.waiting_list_case_study.render import render_case_study, render_program_brief

    config = load_config(root / _CONFIG)
    trusted = load_inputs(root, config)
    root = root.resolve()
    hashes = _implementation_hashes(root)
    request = {"program_key": program_key, "year": year if program_key is not None else None}
    identity = sha256(
        _json({"files": hashes, "inputs": trusted.fingerprints, "request": request})
    ).hexdigest()
    if _destination(root, identity).exists():
        raise ValueError("This run already exists; preserve its evidence.")
    context = current_patient_journey_build_context(root)
    vintages = {}
    for row in trusted.annual:
        if 2022 <= row.year <= 2025:
            vintages[row.year] = {
                "year": row.year,
                "cohort_start": f"{row.year}-01-01",
                "cohort_end": f"{row.year}-12-31",
                "release_code": row.release_code,
                "published_value": row.published_value,
                "published_precision": row.published_precision,
                "source_url": row.source_url,
                "source_sha256": row.source_sha256,
            }
    provenance: dict[str, Any] = {
        "analysis_id": config.analysis_id,
        "run_id": identity,
        "input_run": config.input_run,
        "input_complete_sha256": config.input_complete_sha256,
        "input_payload_sha256": trusted.fingerprints,
        "input_sha256": hashes,
        "git_commit": context.git_commit_sha,
        "git_worktree_dirty": context.git_worktree_dirty,
        "build_time_utc": context.build_timestamp_utc.isoformat(),
        "python_version": context.python_version,
        "years": config.years,
        "source_vintages": list(vintages.values()),
        "source_releases": trusted.provenance["source_releases"],
        "exclusions": trusted.qa["exclusions"],
        "request": request,
        "model_parameters": None,
        "feature_schema": None,
        "calculation_schema": {
            "version": 1,
            "unit": "program/calendar year; registration and removal events",
            "years": config.years,
            "transplant_change": "current (REMTXC + REMTXL) - previous (REMTXC + REMTXL)",
            "normalization": "100 * signed count / current starting registrations",
            "percentile_method": config.percentile_method,
            "selection": config.selection_rule,
            "growth": "end - start",
            "change_in_growth": "change in additions - sum(changes in all eight removals)",
        },
    }
    if program_key is not None:
        brief = program_brief(trusted.annual, trusted.comparisons, program_key, year)
        payloads = {
            "program_brief.html": render_program_brief(brief, provenance).encode("utf-8"),
            "program_brief.json": _json(brief),
        }
    else:
        summary = summarize_distributions(trusted.comparisons)
        examples = select_examples(trusted.comparisons)
        briefs = [
            program_brief(trusted.annual, trusted.comparisons, example["program_key"], 2025)
            if example["available"]
            else {
                "available": False,
                "reason": example["reason"],
                "program_key": "Unavailable",
                "year": 2025,
            }
            for example in examples
        ]
        provenance["previous_summary"] = trusted.summary
        provenance["previous_qa"] = trusted.qa
        payloads = render_case_study(summary, examples, briefs, trusted.comparisons, provenance)
        payloads.update(
            {
                "distributions.json": _json(summary),
                "examples.json": _json(examples),
                "program_briefs.json": _json(briefs),
                "previous_summary.json": _json(trusted.summary),
                "previous_qa.json": _json(trusted.qa),
            }
        )
        for index, brief in enumerate(briefs, start=1):
            payloads[f"program_{index}.html"] = render_program_brief(brief, provenance).encode(
                "utf-8"
            )
    destination = write_run(root, identity, payloads, provenance)
    verify_run(root, identity)
    return destination


def main() -> None:
    """Expose offline report generation and output verification from the project root."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program-key", help="Composite key, for example ABCD:TX1")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--verify-run", help="Verify an existing case-study run's SHA-256 identity")
    args = parser.parse_args()
    try:
        if args.verify_run is not None:
            verify_run(Path.cwd(), args.verify_run)
            print("All case-study output fingerprints verified.")
        else:
            print(build(Path.cwd(), args.program_key, args.year))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Case study unavailable: {exc}\n")


if __name__ == "__main__":
    main()
