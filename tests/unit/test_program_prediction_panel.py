"""Historical source vintages and unknown outcomes survive forecast construction."""

import json
from dataclasses import replace
from datetime import date
from hashlib import sha256
from math import log1p
from pathlib import Path
from typing import Any

import pytest

from kasm.config import SourceRecord, load_data_source_manifest
from kasm.data.parse import ParsedRelease, ProgramSignal, WorkbookSheet
from kasm.program_prediction import panel as panel_module
from kasm.program_prediction.config import SprintConfig, SprintError
from kasm.program_prediction.panel import assemble_panel
from kasm.waiting_list.parse import AnnualRecord


def source(release: str, year: int, published: str) -> SourceRecord:
    return SourceRecord(
        release_code=release,
        cohort_year=year,
        transport="xls",
        url="https://example.org/source.xls",
        download_bytes=1,
        download_sha256="a" * 64,
        published_value=published,
        published_precision="month" if len(published) == 7 else "day",
    )


SOURCES = (
    source("1905", 2018, "2019-07"),
    source("2105", 2020, "2021-07"),
    source("2205", 2021, "2022-07"),
    source("2305", 2022, "2023-07-06"),
)


def annual(release: int, year: int, value: int | None, key: str = "AB12:TX1") -> AnnualRecord:
    origin = SOURCES[release]
    return AnnualRecord(
        key,
        origin.release_code,
        year,
        100,
        value,
        value,
        (value, 2, 3, 4, 5, 6, 7, 8),
        origin.published_value,
        origin.published_precision,
        origin.url,
        origin.download_sha256,
    )


def records() -> tuple[AnnualRecord, ...]:
    return (
        annual(0, 2017, 8),
        annual(0, 2018, 10),
        annual(1, 2019, 12),
        annual(1, 2020, 20),
        annual(2, 2020, 24),
        annual(2, 2021, 0),
        annual(3, 2021, 999),
        annual(3, 2022, None),
    )


def test_own_origin_vintage_stays_fixed_and_truth_uses_earliest_release() -> None:
    panel = assemble_panel(SOURCES, records(), (), SprintConfig())
    rows = {r["target_year"]: r for r in panel.rows if r["target"] == "registrations"}
    assert rows[2019]["latest"] == 10
    assert rows[2019]["observed"] == 12
    assert rows[2021]["latest"] == 20
    assert rows[2021]["observed"] == 0
    assert rows[2021]["truth_release"] == "2205"
    assert rows[2021]["h_previous"] == log1p(12)
    assert rows[2022]["previous"] == 24
    assert rows[2022]["observed"] is None
    assert rows[2022]["eligible"]
    assert rows[2021]["origin_value"] == "2021-07"
    assert rows[2021]["elapsed_target_year_fraction"] == 0.5
    assert rows[2019]["left_censored_history"]
    assert not rows[2019]["first_observed"]
    assert panel.feature_map["b1_additions"]["source"] == "WLA_ADDCEN_NC1 / WLA_ADDCEN_NC2"
    assert panel.feature_map["oar_overall_ratio"]["source"] == "OA_OVERALL_HR_MN_CENTER"


def test_absent_future_program_is_unknown_and_new_program_is_separate() -> None:
    changed = records() + (annual(1, 2019, 9, "ZZ99:TX2"), annual(1, 2020, 10, "ZZ99:TX2"))
    panel = assemble_panel(SOURCES, changed, (), SprintConfig())
    row = next(
        r
        for r in panel.rows
        if r["target"] == "registrations"
        and r["target_year"] == 2021
        and r["program_key"] == "ZZ99:TX2"
    )
    assert row["observed"] is None
    assert row["first_observed"]
    assert not row["eligible"]
    assert row["exclusion_reason"] == "first_observed_program"


def test_vintage_is_selected_globally_not_per_program() -> None:
    changed = records() + (
        annual(1, 2019, 9, "ZZ99:TX1"),
        annual(1, 2020, 10, "ZZ99:TX1"),
        annual(3, 2021, 99, "ZZ99:TX1"),
    )
    panel = assemble_panel(SOURCES, changed, (), SprintConfig())
    row = next(
        r
        for r in panel.rows
        if r["target"] == "registrations"
        and r["target_year"] == 2021
        and r["program_key"] == "ZZ99:TX1"
    )
    assert row["observed"] is None
    assert row["truth_release"] == "2205"


def test_preserve_gaps_and_target_specific_missingness() -> None:
    changed = tuple(r for r in records() if not (r.release_code == "2105" and r.year == 2019))
    panel = assemble_panel(SOURCES, changed, (), SprintConfig())
    row = next(r for r in panel.rows if r["target"] == "registrations" and r["target_year"] == 2021)
    assert row["previous"] is None
    assert row["last_change"] is None
    assert row["recent_values"] == [20.0, 10.0, 8.0]


def test_future_measurement_or_duplicate_records_fail() -> None:
    with pytest.raises(SprintError, match="Duplicate"):
        assemble_panel(SOURCES, records() + (records()[0],), (), SprintConfig())
    with pytest.raises(SprintError, match="measurement|year"):
        assemble_panel(SOURCES, records() + (annual(1, 2021, 5),), (), SprintConfig())


@pytest.mark.parametrize("kind", ["unknown_source", "publication", "duplicate_source"])
def test_source_metadata_drift_fails(kind: str) -> None:
    rows = records()
    sources = SOURCES
    if kind == "unknown_source":
        rows = (replace(rows[0], release_code="unknown"), *rows[1:])
    elif kind == "publication":
        rows = (replace(rows[0], published_value="2019-08"), *rows[1:])
    else:
        sources = (*sources, sources[0])
    with pytest.raises(SprintError):
        assemble_panel(sources, rows, (), SprintConfig())


def test_already_public_outcome_cannot_be_own_origin_target() -> None:
    shifted = replace(SOURCES[1], published_value="2019-06")
    changed = tuple(
        replace(r, published_value="2019-06") if r.release_code == "2105" else r for r in records()
    )
    with pytest.raises(SprintError, match="already public"):
        assemble_panel((SOURCES[0], shifted, *SOURCES[2:]), changed, (), SprintConfig())


def test_oar_nonpositive_target_is_missing_and_b1_is_optional() -> None:
    def signal(index: int, ratio: float) -> ProgramSignal:
        s = SOURCES[index]
        return ProgramSignal(
            "AB12:TX1",
            "AB12",
            "TX1",
            "Example",
            s.release_code,
            s.published_value,
            s.published_precision,
            s.cohort_year,
            date(s.cohort_year, 1, 1),
            date(s.cohort_year, 12, 31),
            "overall",
            10,
            1,
            1.0,
            ratio,
            0.0,
            3.0,
            s.url,
            s.download_sha256,
        )

    panel = assemble_panel(SOURCES, (), (signal(0, 1), signal(1, 2), signal(2, 0)), SprintConfig())
    row = next(r for r in panel.rows if r["target"] == "overall_oar" and r["target_year"] == 2021)
    assert row["observed"] is None
    assert row["latest"] == 2
    assert row["b1_end"] is None
    assert row["previous"] is None
    assert "program_key" not in panel.feature_map
    without = assemble_panel(
        SOURCES,
        (),
        (signal(0, 1), signal(1, 2), signal(2, 0)),
        replace(
            SprintConfig(),
            round_id="followup_1",
            omit_oar_features=True,
            question="Remove OAR inputs",
            parent_run="initial",
        ),
    )
    assert not any(name.startswith("oar_") for name in without.feature_map)


def _mock_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Any], list[str]]:
    manifest_path = tmp_path / "configs/data_sources.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_bytes(Path("configs/data_sources.yaml").read_bytes())
    manifest = load_data_source_manifest(manifest_path)
    ledger_path = tmp_path / "configs/waiting_list/sources.json"
    ledger_path.parent.mkdir()
    ledger_path.write_bytes(Path("configs/waiting_list/sources.json").read_bytes())
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert ledger["source_manifest_sha256"] == sha256(manifest_path.read_bytes()).hexdigest()
    for binding in ledger["releases"]:
        binding["expected_rows"] = 1
    bindings = {r["release_code"]: r for r in ledger["releases"]}
    calls: list[str] = []

    def payload(source: SourceRecord, path: Path) -> bytes:
        calls.append(source.release_code)
        assert path == tmp_path / "data/raw/srtr"
        return b"verified by reused source loader"

    def parse_b1(
        source: SourceRecord, sheets: object, years: tuple[int, int]
    ) -> tuple[AnnualRecord, ...]:
        assert years == tuple(bindings[source.release_code]["years"])
        return tuple(
            AnnualRecord(
                "AB12:TX1",
                source.release_code,
                year,
                100,
                101,
                20,
                (5, 1, 2, 3, 2, 2, 2, 2),
                source.published_value,
                source.published_precision,
                source.url,
                source.download_sha256,
            )
            for year in years
        )

    monkeypatch.setattr(panel_module, "load_data_source_manifest", lambda path: manifest)
    monkeypatch.setattr(panel_module, "load_sources", lambda path: ledger)
    monkeypatch.setattr(panel_module, "load_workbook_payload", payload)
    monkeypatch.setattr(
        panel_module,
        "read_workbook_sheets",
        lambda payload: (WorkbookSheet("Tables B2-B3 Center", (("WLC_N_NEWC2",),), 1),),
    )
    monkeypatch.setattr(
        panel_module,
        "parse_offer_acceptance_workbook",
        lambda manifest, source, sheets: ParsedRelease(
            source.release_code, source.cohort_year, "OAR", 0, 0, ()
        ),
    )
    monkeypatch.setattr(panel_module, "parse_release", parse_b1)
    monkeypatch.setattr(panel_module, "verify_reference", lambda root, path, fingerprint: None)
    monkeypatch.setattr(panel_module, "_bind_report", lambda rows, binding: None)
    return ledger, calls


def test_build_reuses_all_verified_inputs_but_only_bound_b1_periods(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, calls = _mock_build(tmp_path, monkeypatch)
    result = panel_module.build_panel(tmp_path, SprintConfig())
    assert len(calls) == 9
    assert result.qa["annual_source_rows"] == 14
    assert len(result.rows) == 24
    assert result.source_ledger["candidate_block"]["status"] == "omitted"
    assert len(result.source_ledger["candidate_source_check"]) == 9


@pytest.mark.parametrize("kind", ["manifest_hash", "release_set", "years", "population"])
def test_build_rejects_changed_source_bindings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    ledger, _ = _mock_build(tmp_path, monkeypatch)
    if kind == "manifest_hash":
        ledger["source_manifest_sha256"] = "b" * 64
    elif kind == "release_set":
        ledger["releases"] = ledger["releases"][:-1]
    elif kind == "years":
        ledger["releases"][1]["years"] = [2018]
    else:
        ledger["releases"][1]["expected_rows"] = 999
    with pytest.raises(SprintError):
        panel_module.build_panel(tmp_path, SprintConfig())
