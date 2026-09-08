"""Verify the completed screen before using its precomputed registration records."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from kasm.config import load_data_source_manifest
from kasm.data.parse import ParseError
from kasm.waiting_list.build import _coverage
from kasm.waiting_list.parse import REMOVAL_FIELDS, AnnualRecord, _changed_fields
from kasm.waiting_list.screen import Comparison, compare_years
from kasm.waiting_list_case_study.config import (
    INPUT_ROOT,
    CaseStudyConfig,
    CaseStudyError,
    bounded_bytes,
    read_json,
    same_json,
)

_PAYLOADS = {
    "annual.json",
    "comparisons.json",
    "revisions.json",
    "summary.json",
    "qa.json",
    "provenance.json",
}
_BOUND_FILES = (
    "configs/waiting_list/experiment.json",
    "configs/waiting_list/sources.json",
    "docs/specs/waiting-list-0025.md",
    "configs/data_sources.yaml",
)
_ANNUAL_FIELDS = {f.name for f in fields(AnnualRecord)} | {"growth", "residual", "clean"}
_PROVENANCE_FIELDS = {
    "analysis_id",
    "input_sha256",
    "git_commit",
    "git_worktree_dirty",
    "build_time_utc",
    "python_version",
    "years",
    "source_releases",
    "model_parameters",
    "feature_schema",
    "calculation_schema",
    "verification",
}
_QA_FIELDS = {
    "annual",
    "excluded_releases",
    "absent_candidate_years",
    "exclusions",
    "exclusion_counts",
    "revision_comparisons",
    "revision_disagreements",
    "shrinking",
}
_SUMMARY_FIELDS = {
    "annual",
    "pooled",
    "recurrence_years",
    "verdict",
    "reason",
    "common_programs",
    "common_annual",
    "size",
    "primary_material_by_year",
    "common_material_by_year",
}
_METRICS = {
    "growth",
    "change_in_growth",
    "additions",
    "change_additions",
    "transplant",
    "change_transplant",
    "deceased",
    "living",
    "elsewhere",
    "transfer",
    "deaths",
    "deterioration",
    "recovery",
    "other",
    "change_deceased",
    "change_living",
    "change_elsewhere",
    "change_transfer",
    "change_deaths",
    "change_deterioration",
    "change_recovery",
    "change_other",
}


@dataclass(frozen=True)
class TrustedInputs:
    """Validated annual counts, comparisons and unchanged prior-study findings."""

    annual: tuple[AnnualRecord, ...]
    comparisons: tuple[Comparison, ...]
    summary: dict[str, Any]
    qa: dict[str, Any]
    provenance: dict[str, Any]
    fingerprints: dict[str, str]


def _object(value: Any, names: set[str] | None = None, label: str = "Input") -> dict[str, Any]:
    if not isinstance(value, dict) or (names is not None and set(value) != names):
        raise CaseStudyError(f"{label} object schema changed; restore the completed run.")
    return value


def _hash(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _match(actual: object, expected: object, label: str) -> None:
    if not same_json(actual, expected):
        raise CaseStudyError(f"{label} disagrees with trusted source records or accounting.")


def _payloads(root: Path, config: CaseStudyConfig) -> tuple[dict[str, Any], dict[str, str]]:
    if not _hash(config.input_run) or not _hash(config.input_complete_sha256):
        raise CaseStudyError("Input run identity and completion fingerprint must be SHA-256.")
    run = root / INPUT_ROOT / config.input_run
    marker_bytes = bounded_bytes(run / "complete.json", 2 * 1024 * 1024)
    if sha256(marker_bytes).hexdigest() != config.input_complete_sha256:
        raise CaseStudyError("Input completion fingerprint changed; restore the pinned run.")
    marker = _object(read_json(marker_bytes), {"run_identity", "sha256"}, "Completion")
    _match(marker["run_identity"], config.input_run, "Completion run identity")
    hashes = _object(marker["sha256"], _PAYLOADS, "Completion payload")
    if not all(_hash(value) for value in hashes.values()):
        raise CaseStudyError("Completion payload fingerprint schema is invalid.")
    result = {}
    for name in sorted(_PAYLOADS):
        content = bounded_bytes(run / name, 20 * 1024 * 1024)
        if sha256(content).hexdigest() != hashes[name]:
            raise CaseStudyError(f"Input fingerprint changed for {name}; restore the pinned run.")
        result[name] = read_json(content)
    return result, {"complete.json": config.input_complete_sha256, **hashes}


def _provenance(root: Path, raw: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    provenance = _object(raw, _PROVENANCE_FIELDS, "Provenance")
    hashes = _object(provenance["input_sha256"], label="Original input fingerprints")
    if not all(_hash(value) for value in hashes.values()):
        raise CaseStudyError("Original input fingerprints must contain SHA-256 values.")
    for name in _BOUND_FILES:
        if (
            name not in hashes
            or sha256(bounded_bytes(root / name, 2 * 1024 * 1024)).hexdigest() != hashes[name]
        ):
            raise CaseStudyError(f"Original contract fingerprint changed: {name}.")
    ledger = _object(read_json(bounded_bytes(root / _BOUND_FILES[1], 2 * 1024 * 1024)))
    _match(ledger["source_manifest_sha256"], hashes["configs/data_sources.yaml"], "Source ledger")
    _match(provenance["source_releases"], ledger["releases"], "Provenance source ledger")
    _match(provenance["analysis_id"], "waiting_list_0025_v1", "Original study identity")
    _match(provenance["years"], list(range(2017, 2026)), "Original source years")
    _match(provenance["model_parameters"], None, "Original model parameters")
    _match(provenance["feature_schema"], None, "Original feature schema")
    _match(
        provenance["calculation_schema"],
        {
            "unit": "program and calendar year; registration/removal events",
            "transplant_categories": ["REMTXC", "REMTXL"],
            "removal_order": list(REMOVAL_FIELDS),
            "normalization": "100 * count / current.start",
            "growth": "end - start",
            "change_in_growth": "growth - previous.growth",
        },
        "Original calculation schema",
    )
    if (
        not isinstance(provenance["git_commit"], str)
        or re.fullmatch(r"[a-f0-9]{40}", provenance["git_commit"]) is None
        or type(provenance["git_worktree_dirty"]) is not bool
        or not isinstance(provenance["python_version"], str)
        or not isinstance(provenance["verification"], str)
    ):
        raise CaseStudyError("Original provenance metadata schema changed.")
    stamp = datetime.fromisoformat(provenance["build_time_utc"])
    offset = stamp.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise CaseStudyError("Original build time must retain UTC.")
    return provenance, ledger


def _annual(
    raw: Any, sources: dict[str, Any], earliest: dict[int, dict[str, Any]], *, derived: bool = True
) -> AnnualRecord:
    names = _ANNUAL_FIELDS if derived else {f.name for f in fields(AnnualRecord)}
    value = _object(raw, names, "Annual row")
    key, year = value["program_key"], value["year"]
    if (
        not isinstance(key, str)
        or re.fullmatch(r"[A-Z0-9]{4}:[A-Z0-9]+", key) is None
        or type(year) is not int
        or year not in earliest
    ):
        raise CaseStudyError("Annual program identity or calendar-year schema is invalid.")
    binding = earliest[year]
    source = sources[binding["release_code"]]
    for field, expected in {
        "release_code": source.release_code,
        "published_value": source.published_value,
        "published_precision": source.published_precision,
        "source_url": source.url,
        "source_sha256": source.download_sha256,
    }.items():
        _match(value[field], expected, f"Annual {field} / earliest verified vintage")
    if not isinstance(value["removals"], list):
        raise CaseStudyError("Annual removal schema must contain eight published counts.")
    constructor = {f.name: value[f.name] for f in fields(AnnualRecord)}
    constructor["removals"] = tuple(value["removals"])
    row = AnnualRecord(**constructor)
    expected_values = asdict(row)
    if derived:
        expected_values.update(growth=row.growth, residual=row.residual, clean=row.clean)
    _match(value, expected_values, "Annual derived fields")
    return row


def _annual_records(root: Path, raw: Any, ledger: dict[str, Any]) -> tuple[AnnualRecord, ...]:
    if not isinstance(raw, list) or not 0 < len(raw) <= 100_000:
        raise CaseStudyError("Annual schema requires a bounded nonempty list.")
    sources = {
        row.release_code: row
        for row in load_data_source_manifest(root / "configs/data_sources.yaml").sources
    }
    earliest: dict[int, dict[str, Any]] = {}
    for binding in ledger["releases"]:
        if binding["verified"] is True:
            for year in binding["years"]:
                earliest.setdefault(year, binding)
    rows = tuple(_annual(value, sources, earliest) for value in raw)
    if len({(row.program_key, row.year) for row in rows}) != len(rows):
        raise CaseStudyError("Annual records contain duplicate composite program-year identities.")
    _match(
        dict(Counter(row.year for row in rows)),
        {year: binding["expected_rows"] for year, binding in earliest.items()},
        "Annual source population",
    )
    return rows


def _comparisons(
    raw: Any, rows: tuple[AnnualRecord, ...]
) -> tuple[tuple[Comparison, ...], tuple[dict[str, Any], ...]]:
    pairs, exclusions = compare_years(rows)
    expected = [
        asdict(row)
        | {
            "growth_per100": row.growth_per100,
            "change_in_growth_per100": row.change_in_growth_per100,
            "transplant_increased": row.transplant_increased,
        }
        for row in pairs
    ]
    _match(raw, expected, "Cached comparisons and derived fields")
    return pairs, exclusions


def _counts(raw: Any, rows: tuple[Comparison, ...]) -> None:
    """Check retained summary shape and counts without rerunning its continuation rule."""
    count = len(rows)
    expected = {"programs": len({r.program_key for r in rows}), "observations": count}
    names = set(expected) | (_METRICS | {f"{name}_per100" for name in _METRICS} if count else set())
    values = _object(raw, names, "Retained count summary")
    for field, value in expected.items():
        _match(values[field], value, f"Retained {field}")
    if any(type(values[field]) not in (int, float) for field in names - set(expected)):
        raise CaseStudyError("Retained distribution values must be finite numbers.")


def _summary_population(raw: Any, rows: tuple[Comparison, ...]) -> None:
    value = _object(
        raw,
        {
            "eligible_observations",
            "eligible_programs",
            "growing_observations",
            "growing_programs",
            "increase_prevalence",
            "groups",
        },
        "Retained population summary",
    )
    growing = tuple(r for r in rows if r.growth > 0)
    for prefix, selected in (("eligible", rows), ("growing", growing)):
        _match(value[f"{prefix}_observations"], len(selected), f"Retained {prefix} observations")
        _match(
            value[f"{prefix}_programs"],
            len({r.program_key for r in selected}),
            f"Retained {prefix} programs",
        )
    prevalence = value["increase_prevalence"]
    if (growing and (type(prevalence) not in (int, float) or not 0 <= prevalence <= 1)) or (
        not growing and prevalence is not None
    ):
        raise CaseStudyError("Retained prevalence must match population missingness and bounds.")
    groups = _object(value["groups"], {"increase", "no_increase"}, "Retained groups")
    _counts(groups["increase"], tuple(r for r in growing if r.transplant_increased))
    _counts(groups["no_increase"], tuple(r for r in growing if not r.transplant_increased))


def _summary(raw: Any, pairs: tuple[Comparison, ...], config: CaseStudyConfig) -> dict[str, Any]:
    result = _object(raw, _SUMMARY_FIELDS, "Retained summary")
    _match(result["recurrence_years"], config.years, "Fixed comparison years")
    common = set.intersection(
        *({r.program_key for r in pairs if r.year == y} for y in config.years)
    )
    _match(result["common_programs"], config.common_programs, "Fixed common-program count")
    _match(len(common), config.common_programs, "Retained common-program population")
    annual = _object(
        result["annual"], {str(y) for y in range(2018, 2026)}, "Retained annual summaries"
    )
    common_annual = _object(
        result["common_annual"], {str(y) for y in config.years}, "Retained common summaries"
    )
    for year in range(2018, 2026):
        _summary_population(annual[str(year)], tuple(r for r in pairs if r.year == year))
    for year in config.years:
        _summary_population(
            common_annual[str(year)],
            tuple(r for r in pairs if r.year == year and r.program_key in common),
        )
    _summary_population(result["pooled"], pairs)
    size = _object(
        result["size"], {"under_100", "100_to_499", "500_or_more"}, "Retained size groups"
    )
    for key, lower, upper in (
        ("under_100", 0, 100),
        ("100_to_499", 100, 500),
        ("500_or_more", 500, float("inf")),
    ):
        _summary_population(
            size[key],
            tuple(r for r in pairs if r.year in config.years and lower <= r.start < upper),
        )
    for key in ("primary_material_by_year", "common_material_by_year"):
        flags = _object(result[key], {str(y) for y in config.years}, "Retained criterion results")
        if not all(type(v) is bool for v in flags.values()):
            raise CaseStudyError("Retained criterion results must be booleans.")
    if result["verdict"] != "continue" or not isinstance(result["reason"], str):
        raise CaseStudyError("The retained completed-screen result changed.")
    return result


def _revisions(
    root: Path, raw: Any, annual: tuple[AnnualRecord, ...], ledger: dict[str, Any]
) -> list[dict[str, Any]]:
    """Keep revised records bound to their later source and retained earlier count."""
    if not isinstance(raw, list) or len(raw) > 100_000:
        raise CaseStudyError("Revision schema must be a bounded list.")
    sources = {
        row.release_code: row
        for row in load_data_source_manifest(root / "configs/data_sources.yaml").sources
    }
    bindings = {r["release_code"]: r for r in ledger["releases"] if r["verified"]}
    order = {code: i for i, code in enumerate(bindings)}
    retained = {(r.program_key, r.year): r for r in annual}
    names = {
        "program_key",
        "year",
        "canonical_release",
        "later_release",
        "canonical",
        "later",
        "changed_fields",
    }
    seen = set()
    result = []
    for value in raw:
        row = _object(value, names, "Revision row")
        key, year = row["program_key"], row["year"]
        canonical_release, later_release = row["canonical_release"], row["later_release"]
        identity = (key, year, later_release)
        if (
            not isinstance(key, str)
            or re.fullmatch(r"[A-Z0-9]{4}:[A-Z0-9]+", key) is None
            or type(year) is not int
            or canonical_release not in bindings
            or later_release not in bindings
            or order[later_release] <= order[canonical_release]
            or identity in seen
        ):
            raise CaseStudyError("Revision identity, order or uniqueness is invalid.")
        seen.add(identity)
        earliest = next((b for b in bindings.values() if year in b["years"]), None)
        if earliest is None or earliest["release_code"] != canonical_release:
            raise CaseStudyError("Revision canonical release must retain the earliest vintage.")
        first = retained.get((key, year))
        _match(
            row["canonical"],
            asdict(first) if first is not None else None,
            "Revision retained record",
        )
        later = None
        if row["later"] is not None:
            binding = bindings[later_release]
            later = _annual(
                row["later"], sources, {y: binding for y in binding["years"]}, derived=False
            )
            _match((later.program_key, later.year), (key, year), "Revision nested identity")
        if first is None and later is None:
            raise CaseStudyError("A revision cannot omit both annual records.")
        _match(row["changed_fields"], _changed_fields(first, later), "Revision changed fields")
        result.append(row)
    return result


def _qa(
    root: Path,
    raw: Any,
    annual: tuple[AnnualRecord, ...],
    pairs: tuple[Comparison, ...],
    exclusions: tuple[dict[str, Any], ...],
    revisions: Any,
    ledger: dict[str, Any],
) -> dict[str, Any]:
    qa = _object(raw, _QA_FIELDS, "QA")
    _match(qa["annual"], _coverage(annual), "Annual QA accounting")
    _match(qa["exclusions"], exclusions, "Comparison QA exclusions")
    _match(
        qa["exclusion_counts"],
        dict(Counter(r["reason"] for r in exclusions)),
        "QA exclusion totals",
    )
    _match(
        qa["excluded_releases"],
        [r for r in ledger["releases"] if not r["verified"]],
        "Excluded releases",
    )
    _match(qa["absent_candidate_years"], [2016], "Absent candidate years")
    revisions = _revisions(root, revisions, annual, ledger)
    _match(qa["revision_comparisons"], len(revisions), "Revision QA count")
    _match(
        qa["revision_disagreements"],
        sum(bool(r["changed_fields"]) for r in revisions),
        "Revision QA disagreements",
    )
    _counts(qa["shrinking"], tuple(r for r in pairs if r.growth < 0))
    return qa


def load_inputs(root: Path, config: CaseStudyConfig) -> TrustedInputs:
    """Validate cached counts and fingerprints; never parse sources or rerun the old gate."""
    try:
        payloads, fingerprints = _payloads(root, config)
        provenance, ledger = _provenance(root, payloads["provenance.json"])
        identity_content = (
            json.dumps(provenance["input_sha256"], sort_keys=True, indent=2, allow_nan=False) + "\n"
        ).encode("utf-8")
        _match(sha256(identity_content).hexdigest(), config.input_run, "Original run identity")
        annual = _annual_records(root, payloads["annual.json"], ledger)
        comparisons, exclusions = _comparisons(payloads["comparisons.json"], annual)
        summary = _summary(payloads["summary.json"], comparisons, config)
        qa = _qa(
            root,
            payloads["qa.json"],
            annual,
            comparisons,
            exclusions,
            payloads["revisions.json"],
            ledger,
        )
        return TrustedInputs(annual, comparisons, summary, qa, provenance, fingerprints)
    except CaseStudyError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError, ParseError) as exc:
        raise CaseStudyError(
            "Input schema or accounting is invalid; restore the completed run."
        ) from exc
