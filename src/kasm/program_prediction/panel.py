"""Build prediction records from the source version available at each historical origin.

One row is a program, target and target calendar year. Metadata and source identities
travel with each row but only the explicit feature allowlist can enter a model.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
from math import isfinite, log, log1p
from pathlib import Path
from statistics import mean
from typing import Any

from kasm.config import SourceRecord, load_data_source_manifest
from kasm.data.build import _elapsed_target_fraction
from kasm.data.parse import (
    ProgramSignal,
    load_workbook_payload,
    parse_offer_acceptance_workbook,
    read_workbook_sheets,
)
from kasm.patient_journey.receipt_panel import publication_available
from kasm.program_prediction.config import B1_PAIRS, SprintConfig, SprintError, validate_config
from kasm.waiting_list.build import _bind_report, load_sources, verify_reference
from kasm.waiting_list.parse import REMOVAL_FIELDS, AnnualRecord, parse_release

HISTORY_FEATURES = ("h_latest", "h_previous", "h_mean3", "h_change")
B1_NAMES = ("start", "end", "additions", *tuple(name.lower() for name in REMOVAL_FIELDS))
B1_FIELD_NAMES = {"start": "ST", "end": "END", "additions": "ADDCEN"} | {
    name.lower(): name for name in REMOVAL_FIELDS
}
TARGET_FIELDS = {
    "registrations": {"source": "WLA_ADDCEN_NC1 / WLA_ADDCEN_NC2", "units": "registration events"},
    "ddkt_removals": {"source": "WLA_REMTXC_NC1 / WLA_REMTXC_NC2", "units": "DDKT removal events"},
    "ldkt_removals": {"source": "WLA_REMTXL_NC1 / WLA_REMTXL_NC2", "units": "LDKT removal events"},
    "ending_list": {"source": "WLA_END_NC1 / WLA_END_NC2", "units": "registrations at year end"},
    "overall_oar": {"source": "OA_OVERALL_HR_MN_CENTER", "units": "published acceptance ratio"},
}
OAR_GROUPS = ("overall", "low", "medium", "high", "hard-to-place")
OAR_FEATURES = tuple(
    f"oar_{group.replace('-', '_')}_{measure}"
    for group in OAR_GROUPS
    for measure in ("ratio", "offers", "expected")
)
BROADER_FEATURES = HISTORY_FEATURES + tuple(f"b1_{name}" for name in B1_NAMES) + OAR_FEATURES


@dataclass(frozen=True)
class PanelBuild:
    """Historical source rows, explicit inputs and source/coverage evidence."""

    rows: list[dict[str, Any]]
    feature_map: dict[str, dict[str, str]]
    source_ledger: dict[str, Any]
    qa: dict[str, Any]


@dataclass(frozen=True)
class _Index:
    sources: dict[str, SourceRecord]
    annual: dict[tuple[str, int, str], AnnualRecord]
    signals: dict[tuple[str, int, str, str], ProgramSignal]
    annual_vintages: dict[int, list[str]]
    signal_vintages: dict[int, list[str]]


def _checked_index(
    sources: tuple[SourceRecord, ...],
    annual: tuple[AnnualRecord, ...],
    signals: tuple[ProgramSignal, ...],
) -> _Index:
    source_map = {s.release_code: s for s in sources}
    if len(source_map) != len(sources):
        raise SprintError("Duplicate source releases.")
    annual_map: dict[tuple[str, int, str], AnnualRecord] = {}
    signal_map: dict[tuple[str, int, str, str], ProgramSignal] = {}
    annual_vintages: dict[int, list[str]] = {}
    signal_vintages: dict[int, list[str]] = {}
    for row in annual:
        _validate_record(
            source_map, row.release_code, row.year, row.published_value, row.published_precision
        )
        key = row.release_code, row.year, row.program_key
        if key in annual_map:
            raise SprintError("Duplicate annual program-year within a release.")
        annual_map[key] = row
        annual_vintages.setdefault(row.year, []).append(row.release_code)
    for signal in signals:
        _validate_record(
            source_map,
            signal.release_code,
            signal.cohort_year,
            signal.published_value,
            signal.published_precision,
        )
        signal_key = signal.release_code, signal.cohort_year, signal.program_key, signal.offer_group
        if signal_key in signal_map:
            raise SprintError("Duplicate OAR program-year/group within a release.")
        signal_map[signal_key] = signal
        signal_vintages.setdefault(signal.cohort_year, []).append(signal.release_code)
    for vintages in (annual_vintages, signal_vintages):
        for year, releases in vintages.items():
            vintages[year] = sorted(
                set(releases), key=lambda code: source_map[code].published_value
            )
    return _Index(source_map, annual_map, signal_map, annual_vintages, signal_vintages)


def _validate_record(
    sources: dict[str, SourceRecord], release: str, year: int, published: str, precision: str
) -> None:
    if release not in sources:
        raise SprintError("Record uses an unknown source release.")
    source = sources[release]
    if published != source.published_value or precision != source.published_precision:
        raise SprintError("Record publication metadata disagrees with its source.")
    if year > source.cohort_year:
        raise SprintError("A measurement year cannot extend beyond its bound historical source.")


def _available_vintages(
    index: _Index, origin: SourceRecord, target_year: int, is_oar: bool
) -> dict[int, str]:
    vintages = index.signal_vintages if is_oar else index.annual_vintages
    selected = {}
    for year, releases in vintages.items():
        public = [
            release for release in releases if publication_available(index.sources[release], origin)
        ]
        if year < target_year and public:
            selected[year] = public[-1]
    return selected


def _target_value(
    index: _Index, release: str, year: int, program: str, target: str
) -> float | None:
    if target == "overall_oar":
        signal = index.signals.get((release, year, program, "overall"))
        value = None if signal is None else signal.oar_mean
        return float(value) if value is not None and value > 0 and isfinite(value) else None
    row = index.annual.get((release, year, program))
    if row is None:
        return None
    value = {
        "registrations": row.additions,
        "ending_list": row.end,
        "ddkt_removals": row.removals[0],
        "ldkt_removals": row.removals[1],
    }[target]
    return None if value is None else float(value)


def _universe(index: _Index, release: str, year: int, is_oar: bool) -> set[str]:
    if is_oar:
        return {
            key[2] for key in index.signals if key[:2] == (release, year) and key[3] == "overall"
        }
    return {key[2] for key in index.annual if key[:2] == (release, year)}


def _history(
    index: _Index, vintages: dict[int, str], program: str, target: str, feature_year: int
) -> dict[str, Any]:
    values = {
        year: _target_value(index, release, year, program, target)
        for year, release in vintages.items()
    }
    recent = [
        value for year in sorted(values, reverse=True) if (value := values[year]) is not None
    ][:3]
    latest, previous = values.get(feature_year), values.get(feature_year - 1)
    transform = log if target == "overall_oar" else log1p
    transformed = [transform(value) for value in recent]
    return {
        "latest": latest,
        "previous": previous,
        "recent_values": recent,
        "mean2": mean(recent[:2]) if recent else None,
        "last_change": latest - previous if latest is not None and previous is not None else None,
        "h_latest": None if latest is None else transform(latest),
        "h_previous": None if previous is None else transform(previous),
        "h_mean3": mean(transformed) if transformed else None,
        "h_change": transform(latest) - transform(previous)
        if latest is not None and previous is not None
        else None,
        "history_vintages": {str(year): release for year, release in vintages.items()},
    }


def _broader(
    index: _Index, annual_vintages: dict[int, str], signal_vintages: dict[int, str], program: str
) -> dict[str, Any]:
    result: dict[str, Any] = dict.fromkeys(BROADER_FEATURES[len(HISTORY_FEATURES) :])
    result.update(
        earlier_list_size=None,
        latest_list_size=None,
        b1_feature_year=None,
        b1_feature_release=None,
        oar_feature_year=None,
        oar_feature_release=None,
        b1_accounting_residual=None,
        b1_boundary_difference=None,
    )
    if annual_vintages:
        year = max(annual_vintages)
        release = annual_vintages[year]
        row = index.annual.get((release, year, program))
        result.update(b1_feature_year=year, b1_feature_release=release)
        if row is not None:
            values = (row.start, row.end, row.additions, *row.removals)
            result.update(
                {
                    f"b1_{name}": None if value is None else log1p(value)
                    for name, value in zip(B1_NAMES, values, strict=True)
                }
            )
            result.update(
                earlier_list_size=row.end,
                latest_list_size=row.end,
                b1_accounting_residual=row.residual,
            )
            previous_release = annual_vintages.get(year - 1)
            previous = index.annual.get((previous_release or "", year - 1, program))
            if previous is not None and previous.end is not None and row.start is not None:
                result["b1_boundary_difference"] = row.start - previous.end
    if signal_vintages:
        year = max(signal_vintages)
        release = signal_vintages[year]
        result.update(oar_feature_year=year, oar_feature_release=release)
        for group in OAR_GROUPS:
            signal = index.signals.get((release, year, program, group))
            if signal is None:
                continue
            prefix = f"oar_{group.replace('-', '_')}"
            ratio = signal.oar_mean
            result[f"{prefix}_ratio"] = log(ratio) if ratio is not None and ratio > 0 else None
            result[f"{prefix}_offers"] = None if signal.offers is None else log1p(signal.offers)
            result[f"{prefix}_expected"] = (
                None if signal.expected_acceptances is None else log1p(signal.expected_acceptances)
            )
    return result


def _feature_map(config: SprintConfig) -> dict[str, dict[str, str]]:
    history_definitions = {
        "h_latest": "latest target calendar-year value, transformed",
        "h_previous": "consecutive preceding calendar-year value, transformed; gaps stay missing",
        "h_mean3": "arithmetic mean of up to three separately transformed available annual values",
        "h_change": "transformed latest minus transformed consecutive preceding annual value",
    }
    result = {
        name: {
            "block": "history",
            "transform": "log1p counts; log OAR",
            "units": "transformed own target history",
            "population": "program's reported annual target",
            "source": "target_fields in source ledger; historical vintages fixed at each origin",
            "definition": history_definitions[name],
        }
        for name in HISTORY_FEATURES
    }
    result.update(
        {
            f"b1_{name}": {
                "block": "broader",
                "transform": "log1p",
                "units": "registrations"
                if name in {"start", "end"}
                else "events during calendar year",
                "population": "program registration events",
                "source": " / ".join(
                    f"WLA_{B1_FIELD_NAMES[name]}_{suffix}" for suffix in ("NC1", "NC2")
                ),
            }
            for name in B1_NAMES
        }
    )
    if not config.omit_oar_features:
        result.update(
            {
                name: {
                    "block": "broader",
                    "transform": "log" if name.endswith("ratio") else "log1p",
                    "units": "published ratio"
                    if name.endswith("ratio")
                    else ("offers" if name.endswith("offers") else "expected acceptances"),
                    "population": "program offers in the named donor stratum",
                    "source": _oar_machine_field(name),
                }
                for name in OAR_FEATURES
            }
        )
    return result


def _oar_machine_field(feature: str) -> str:
    group, measure = feature.removeprefix("oar_").rsplit("_", 1)
    prefix = {
        "overall": "OVERALL",
        "low": "LOWRISK",
        "medium": "MEDIUMRISK",
        "high": "HIGHRISK",
        "hard_to_place": "HARDTOPLACE100",
    }[group]
    suffix = {"ratio": "HR_MN_CENTER", "offers": "OFFERS_CENTER", "expected": "EXP_ACCEPTS_CENTER"}[
        measure
    ]
    return f"OA_{prefix}_{suffix}"


def _pair_rows(
    index: _Index,
    target: str,
    origin: SourceRecord,
    feature_year: int,
    target_year: int,
    truth_release: str | None,
) -> list[dict[str, Any]]:
    is_oar = target == "overall_oar"
    truth = index.sources.get(truth_release or "")
    if truth is not None and publication_available(truth, origin):
        raise SprintError("A target outcome was already public at its own forecast origin.")
    annual_vintages = _available_vintages(index, origin, target_year, False)
    signal_vintages = _available_vintages(index, origin, target_year, True)
    vintages = signal_vintages if is_oar else annual_vintages
    family = index.signal_vintages if is_oar else index.annual_vintages
    earlier_releases = {
        release
        for releases in family.values()
        for release in releases
        if release != origin.release_code and publication_available(index.sources[release], origin)
    }
    earlier_programs = {
        program
        for year, releases in family.items()
        for release in releases
        if release in earlier_releases
        for program in _universe(index, release, year, is_oar)
    }
    rows = []
    for program in sorted(_universe(index, origin.release_code, feature_year, is_oar)):
        history = _history(index, vintages, program, target, feature_year)
        first = bool(earlier_releases) and program not in earlier_programs
        reason = (
            "first_observed_program"
            if first
            else ("latest_target_missing_or_invalid" if history["latest"] is None else None)
        )
        observed = (
            None
            if truth_release is None
            else _target_value(index, truth_release, target_year, program, target)
        )
        rows.append(
            {
                "program_key": program,
                "target": target,
                "target_year": target_year,
                "origin_release": origin.release_code,
                "origin_value": origin.published_value,
                "origin_precision": origin.published_precision,
                "truth_release": truth_release,
                "truth_published_value": None if truth is None else truth.published_value,
                "truth_published_precision": None if truth is None else truth.published_precision,
                "feature_year": feature_year,
                "elapsed_target_year_fraction": _elapsed_target_fraction(origin, target_year),
                "eligible": reason is None,
                "origin_eligible": reason is None,
                "exclusion_reason": reason,
                "first_observed": first,
                "left_censored_history": not earlier_releases,
                "observed": observed,
                "outcome_status": "reported" if observed is not None else "unknown_or_invalid",
                **history,
                **_broader(index, annual_vintages, signal_vintages, program),
            }
        )
    return rows


def assemble_panel(
    sources: tuple[SourceRecord, ...],
    annual: tuple[AnnualRecord, ...],
    signals: tuple[ProgramSignal, ...],
    config: SprintConfig,
) -> PanelBuild:
    """Use global source vintages, preserving gaps, entries and missing future reports."""
    validate_config(config)
    index = _checked_index(sources, annual, signals)
    rows = []
    for target in config.targets:
        if target == "overall_oar":
            pairs = [
                (
                    s.release_code,
                    s.cohort_year,
                    s.cohort_year + 1,
                    index.signal_vintages.get(s.cohort_year + 1, [None])[0],
                )
                for s in sources
                if 2017 <= s.cohort_year <= 2024
            ]
        else:
            pairs = list(B1_PAIRS)
        for origin_code, feature_year, target_year, truth_release in pairs:
            if origin_code in index.sources:
                rows.extend(
                    _pair_rows(
                        index,
                        target,
                        index.sources[origin_code],
                        feature_year,
                        target_year,
                        truth_release,
                    )
                )
    summary = []
    for target, year in sorted({(r["target"], r["target_year"]) for r in rows}):
        group = [r for r in rows if r["target"] == target and r["target_year"] == year]
        summary.append(
            {
                "target": target,
                "target_year": year,
                "origin_programs": len(group),
                "eligible_programs": sum(r["eligible"] for r in group),
                "reported_outcomes": sum(r["observed"] is not None for r in group),
                "eligible_reported_outcomes": sum(
                    r["eligible"] and r["observed"] is not None for r in group
                ),
                "first_observed": sum(r["first_observed"] for r in group),
                "left_censored_history": sum(r["left_censored_history"] for r in group),
                "exclusions": dict(
                    Counter(
                        r["exclusion_reason"] for r in group if r["exclusion_reason"] is not None
                    )
                ),
            }
        )
    source_ledger = {
        "target_fields": TARGET_FIELDS,
        "releases": [asdict(s) for s in sources],
        "annual_vintages": index.annual_vintages,
        "oar_vintages": index.signal_vintages,
        "annual_records": [asdict(r) for r in annual],
        "candidate_block": {
            "status": "omitted",
            "reason": "NEWC2 annual periods and denominators are not bound across releases; "
            "workbook headers lack dates. Existing 0022 audit binds only July 2026, "
            "which is an outcome report rather than a forecast origin.",
        },
    }
    return PanelBuild(
        rows,
        _feature_map(config),
        source_ledger,
        {
            "coverage": summary,
            "annual_source_rows": len(annual),
            "oar_source_rows": len(signals),
            "accounting_residual_rows": sum(r.residual not in (None, 0) for r in annual),
            "restriction": "No clean-accounting or positive-start restriction applied.",
        },
    )


def build_panel(root: Path, config: SprintConfig) -> PanelBuild:
    """Read verified cache and seven reviewed B1 period bindings, without downloading."""
    validate_config(config)
    manifest_path = root / "configs/data_sources.yaml"
    manifest = load_data_source_manifest(manifest_path)
    ledger = load_sources(root / "configs/waiting_list/sources.json")
    if sha256(manifest_path.read_bytes()).hexdigest() != ledger["source_manifest_sha256"]:
        raise SprintError("Source manifest changed since B1 period verification.")
    bindings = {entry["release_code"]: entry for entry in ledger["releases"]}
    if len(bindings) != 9 or set(bindings) != {s.release_code for s in manifest.sources}:
        raise SprintError("The B1 ledger must contain the nine pinned releases once each.")
    annual: list[AnnualRecord] = []
    signals: list[ProgramSignal] = []
    candidate_checks = []
    for source in manifest.sources:
        sheets = read_workbook_sheets(load_workbook_payload(source, root / "data/raw/srtr"))
        signals.extend(parse_offer_acceptance_workbook(manifest, source, sheets).signals)
        candidate = next((s for s in sheets if s.name == "Tables B2-B3 Center"), None)
        candidate_checks.append(
            {
                "release_code": source.release_code,
                "sheet_present": candidate is not None,
                "new_registration_denominator_field": candidate is not None
                and "WLC_N_NEWC2" in candidate.rows[0],
                "binding": "omitted; no reviewed origin-period binding",
            }
        )
        binding = bindings[source.release_code]
        if binding["verified"] is not True:
            continue
        verify_reference(root, binding["evidence_path"], binding["evidence_sha256"])
        if binding["original_pdf_path"] is not None:
            verify_reference(root, binding["original_pdf_path"], binding["report_sha256"])
        years = binding["years"]
        if not isinstance(years, list) or len(years) != 2:
            raise SprintError("B1 source must have two reviewed calendar years.")
        records = parse_release(source, sheets, (years[0], years[1]))
        if len(records) != 2 * binding["expected_rows"]:
            raise SprintError("B1 program population changed since source verification.")
        _bind_report(records, binding)
        annual.extend(records)
    panel = assemble_panel(manifest.sources, tuple(annual), tuple(signals), config)
    panel.source_ledger["b1_period_ledger_sha256"] = sha256(
        (root / "configs/waiting_list/sources.json").read_bytes()
    ).hexdigest()
    panel.source_ledger["candidate_source_check"] = candidate_checks
    return panel
