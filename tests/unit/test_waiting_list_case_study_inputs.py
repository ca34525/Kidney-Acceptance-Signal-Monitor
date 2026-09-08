"""Trusted case-study records retain counts, source identity and exclusion meaning."""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from kasm.config import load_data_source_manifest
from kasm.waiting_list.build import _coverage
from kasm.waiting_list.parse import REMOVAL_FIELDS, AnnualRecord
from kasm.waiting_list.screen import compare_years, summarize, summarize_counts
from kasm.waiting_list_case_study.config import (
    CaseStudyConfig,
    CaseStudyError,
    bounded_bytes,
    load_config,
)
from kasm.waiting_list_case_study.inputs import load_inputs


def _json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _annual(row: AnnualRecord) -> dict[str, Any]:
    return asdict(row) | {"growth": row.growth, "residual": row.residual, "clean": row.clean}


def _fixture(root: Path) -> tuple[CaseStudyConfig, Path]:
    names = (
        "configs/waiting_list/experiment.json",
        "configs/waiting_list/sources.json",
        "docs/specs/waiting-list-0025.md",
        "configs/data_sources.yaml",
        "uv.lock",
    )
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Path(name).read_bytes())
    ledger_path = root / names[1]
    ledger = json.loads(ledger_path.read_bytes())
    for release in ledger["releases"]:
        release["expected_rows"] = 3
    ledger_path.write_bytes(_json(ledger))
    sources = {r.release_code: r for r in load_data_source_manifest(root / names[3]).sources}
    records = []
    for year in range(2017, 2026):
        binding = next(r for r in ledger["releases"] if r["verified"] and year in r["years"])
        source = sources[binding["release_code"]]
        for index, key in enumerate(("AAAA:TX1", "AAAA:VA", "BBBB:TX1")):
            start = 100 + (year - 2017) * 5 + index
            records.append(
                AnnualRecord(
                    key,
                    source.release_code,
                    year,
                    start,
                    start + 5,
                    15,
                    (10, 0, 0, 0, 0, 0, 0, 0),
                    source.published_value,
                    source.published_precision,
                    source.url,
                    source.download_sha256,
                )
            )
    records[-1] = replace(records[-1], end=None)
    annual = tuple(records)
    canonical = next(
        r
        for r in annual
        if sum(
            release["verified"] and r.year in (release["years"] or [])
            for release in ledger["releases"]
        )
        > 1
    )
    later_binding = next(
        r
        for r in ledger["releases"]
        if r["verified"]
        and canonical.year in r["years"]
        and r["release_code"] != canonical.release_code
    )
    later_source = sources[later_binding["release_code"]]
    later = replace(
        canonical,
        release_code=later_source.release_code,
        published_value=later_source.published_value,
        published_precision=later_source.published_precision,
        source_url=later_source.url,
        source_sha256=later_source.download_sha256,
    )
    revisions = [
        {
            "program_key": canonical.program_key,
            "year": canonical.year,
            "canonical_release": canonical.release_code,
            "later_release": later.release_code,
            "canonical": asdict(canonical),
            "later": asdict(later),
            "changed_fields": [],
        }
    ]
    pairs, exclusions = compare_years(annual)
    common = set.intersection(
        *({r.program_key for r in pairs if r.year == y} for y in (2023, 2024, 2025))
    )
    recent = tuple(r for r in pairs if r.year in (2023, 2024, 2025))
    summary = {
        "verdict": "continue",
        "reason": "Retained fixture result.",
        "annual": {y: summarize(tuple(r for r in pairs if r.year == y)) for y in range(2018, 2026)},
        "pooled": summarize(pairs),
        "recurrence_years": [2023, 2024, 2025],
        "common_programs": len(common),
        "common_annual": {
            y: summarize(tuple(r for r in recent if r.year == y and r.program_key in common))
            for y in (2023, 2024, 2025)
        },
        "size": {
            "under_100": summarize(()),
            "100_to_499": summarize(recent),
            "500_or_more": summarize(()),
        },
        "primary_material_by_year": {y: True for y in (2023, 2024, 2025)},
        "common_material_by_year": {y: True for y in (2023, 2024, 2025)},
    }
    qa = {
        "annual": _coverage(annual),
        "excluded_releases": [r for r in ledger["releases"] if not r["verified"]],
        "absent_candidate_years": [2016],
        "exclusions": exclusions,
        "exclusion_counts": dict(Counter(r["reason"] for r in exclusions)),
        "revision_comparisons": len(revisions),
        "revision_disagreements": 0,
        "shrinking": summarize_counts(tuple(r for r in pairs if r.growth < 0)),
    }
    provenance = {
        "analysis_id": "waiting_list_0025_v1",
        "input_sha256": {name: sha256((root / name).read_bytes()).hexdigest() for name in names},
        "git_commit": "a" * 40,
        "git_worktree_dirty": False,
        "build_time_utc": "2026-09-08T12:00:00+00:00",
        "python_version": "3.12.11",
        "years": list(range(2017, 2026)),
        "source_releases": ledger["releases"],
        "model_parameters": None,
        "feature_schema": None,
        "calculation_schema": {
            "unit": "program and calendar year; registration/removal events",
            "transplant_categories": ["REMTXC", "REMTXL"],
            "removal_order": REMOVAL_FIELDS,
            "normalization": "100 * count / current.start",
            "growth": "end - start",
            "change_in_growth": "growth - previous.growth",
        },
        "verification": "Synthetic bounded input fixture.",
    }
    config = replace(
        CaseStudyConfig(),
        input_run=sha256(_json(provenance["input_sha256"])).hexdigest(),
        common_programs=len(common),
    )
    run = root / "data/research/waiting-list-0025" / config.input_run
    run.mkdir(parents=True)
    payloads = {
        "annual.json": [_annual(r) for r in annual],
        "comparisons.json": [
            asdict(r)
            | {
                "growth_per100": r.growth_per100,
                "change_in_growth_per100": r.change_in_growth_per100,
                "transplant_increased": r.transplant_increased,
            }
            for r in pairs
        ],
        "revisions.json": revisions,
        "summary.json": summary,
        "qa.json": qa,
        "provenance.json": provenance,
    }
    for name, value in payloads.items():
        (run / name).write_bytes(_json(value))
    return _repin(config, run), run


def _repin(config: CaseStudyConfig, run: Path) -> CaseStudyConfig:
    marker = {
        "run_identity": config.input_run,
        "sha256": {
            p.name: sha256(p.read_bytes()).hexdigest()
            for p in run.glob("*.json")
            if p.name != "complete.json"
        },
    }
    content = _json(marker)
    (run / "complete.json").write_bytes(content)
    return replace(config, input_complete_sha256=sha256(content).hexdigest())


def test_load_fixed_config_and_reject_tuning(tmp_path: Path) -> None:
    path = tmp_path / "experiment.json"
    path.write_bytes(_json(asdict(CaseStudyConfig())))
    assert load_config(path) == CaseStudyConfig()
    for change in (
        {"schema_version": True},
        {"years": [2022, 2023, 2024]},
        {"promotion_allowed": 0},
        {"percentile_method": "nearest"},
    ):
        path.write_bytes(_json(asdict(CaseStudyConfig()) | change))
        with pytest.raises(CaseStudyError, match="fixed|contract"):
            load_config(path)


def test_load_preserves_missing_counts_composite_identity_and_exclusions(tmp_path: Path) -> None:
    config, _ = _fixture(tmp_path)
    result = load_inputs(tmp_path, config)
    assert len(result.annual) == 27
    assert result.annual[-1].end is None
    assert {r.program_key for r in result.comparisons} == {"AAAA:TX1", "AAAA:VA", "BBBB:TX1"}
    assert result.qa["exclusion_counts"] == {"missing": 1}
    assert len(result.fingerprints) == 7


@pytest.mark.parametrize(
    "name",
    [
        "complete.json",
        "annual.json",
        "comparisons.json",
        "qa.json",
        "summary.json",
        "revisions.json",
        "provenance.json",
    ],
)
def test_reject_missing_or_tampered_payload(tmp_path: Path, name: str) -> None:
    config, run = _fixture(tmp_path)
    path = run / name
    original = path.read_bytes()
    path.unlink()
    with pytest.raises(CaseStudyError, match="missing|read"):
        load_inputs(tmp_path, config)
    path.write_bytes(original + b" ")
    with pytest.raises(CaseStudyError, match="fingerprint"):
        load_inputs(tmp_path, config)


@pytest.mark.parametrize("content", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b"[]", b"{"])
def test_reject_invalid_json_even_with_matching_hash(tmp_path: Path, content: bytes) -> None:
    config, run = _fixture(tmp_path)
    (run / "provenance.json").write_bytes(content)
    with pytest.raises(CaseStudyError, match="JSON|schema|object|finite|duplicate"):
        load_inputs(tmp_path, _repin(config, run))


@pytest.mark.parametrize(
    ("name", "field", "value"),
    [
        ("annual.json", "start", True),
        ("annual.json", "start", -1),
        ("annual.json", "growth", 5.0),
        ("annual.json", "clean", 1),
        ("annual.json", "program_key", "AAAA"),
        ("annual.json", "release_code", "2605"),
        ("annual.json", "published_value", "2019-07-01"),
        ("comparisons.json", "start", 0),
        ("comparisons.json", "growth_per100", 999.0),
        ("comparisons.json", "transplant_increased", 0),
    ],
)
def test_reject_semantic_drift_after_repin(
    tmp_path: Path, name: str, field: str, value: Any
) -> None:
    config, run = _fixture(tmp_path)
    payload = json.loads((run / name).read_bytes())
    payload[0][field] = value
    (run / name).write_bytes(_json(payload))
    with pytest.raises(CaseStudyError):
        load_inputs(tmp_path, _repin(config, run))


@pytest.mark.parametrize("change", ["duplicate", "omission", "exclusion", "common", "binding"])
def test_reject_population_or_original_contract_drift(tmp_path: Path, change: str) -> None:
    config, run = _fixture(tmp_path)
    name = {
        "duplicate": "annual.json",
        "omission": "comparisons.json",
        "exclusion": "qa.json",
        "common": "summary.json",
        "binding": "provenance.json",
    }[change]
    payload = json.loads((run / name).read_bytes())
    if change == "duplicate":
        payload.append(payload[0])
    elif change == "omission":
        payload.pop()
    elif change == "exclusion":
        payload["exclusions"] = []
    elif change == "common":
        payload["common_programs"] = 3
    else:
        payload["input_sha256"]["docs/specs/waiting-list-0025.md"] = "0" * 64
    (run / name).write_bytes(_json(payload))
    with pytest.raises(CaseStudyError):
        load_inputs(tmp_path, _repin(config, run))


def test_reject_unsafe_run_and_marker_member(tmp_path: Path) -> None:
    config, run = _fixture(tmp_path)
    with pytest.raises(CaseStudyError, match="identity"):
        load_inputs(tmp_path, replace(config, input_run="../outside"))
    marker = json.loads((run / "complete.json").read_bytes())
    marker["sha256"]["../outside.json"] = "a" * 64
    content = _json(marker)
    (run / "complete.json").write_bytes(content)
    with pytest.raises(CaseStudyError, match="payload|schema"):
        load_inputs(tmp_path, replace(config, input_complete_sha256=sha256(content).hexdigest()))


def test_reject_links_and_oversized_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, run = _fixture(tmp_path)
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda p: p == run or original(p))
    with pytest.raises(CaseStudyError, match="link"):
        load_inputs(tmp_path, config)
    monkeypatch.undo()
    (run / "complete.json").write_bytes(b" " * (2 * 1024 * 1024 + 1))
    with pytest.raises(CaseStudyError, match="size"):
        load_inputs(tmp_path, config)


def test_reject_replaced_open_handle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, replacement = tmp_path / "source.json", tmp_path / "replacement.json"
    source.write_bytes(b"safe")
    replacement.write_bytes(b"evil")
    original_open = os.open

    def redirected(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        return original_open(replacement if path == source else path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", redirected)
    with pytest.raises(CaseStudyError, match="changed"):
        bounded_bytes(source, 100)


def test_run_identity_must_bind_original_provenance(tmp_path: Path) -> None:
    config, run = _fixture(tmp_path)
    provenance = json.loads((run / "provenance.json").read_bytes())
    provenance["input_sha256"]["uv.lock"] = "0" * 64
    (run / "provenance.json").write_bytes(_json(provenance))
    with pytest.raises(CaseStudyError, match="identity"):
        load_inputs(tmp_path, _repin(config, run))


@pytest.mark.parametrize(
    ("field", "value"), [("start", True), ("source_url", "untrusted"), ("program_key", "CCCC:TX1")]
)
def test_revision_nested_records_keep_source_and_count_schema(
    tmp_path: Path, field: str, value: Any
) -> None:
    config, run = _fixture(tmp_path)
    revisions = json.loads((run / "revisions.json").read_bytes())
    revisions[0]["later"][field] = value
    (run / "revisions.json").write_bytes(_json(revisions))
    with pytest.raises(CaseStudyError):
        load_inputs(tmp_path, _repin(config, run))
