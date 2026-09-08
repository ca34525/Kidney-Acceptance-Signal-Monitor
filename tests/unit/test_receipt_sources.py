"""Receipt timing is checked against source text, not copied from its ledger."""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import date
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from kasm.config import load_data_source_manifest
from kasm.data.parse import WorkbookSheet
from kasm.patient_journey.parse import ProgramIdentity
from kasm.patient_journey.receipt_config import ReceiptError
from kasm.patient_journey.receipt_sources import (
    _load_release,
    _methodology,
    _receipt_rows,
    load_receipt_sources,
    parse_source_periods,
    read_source_evidence,
)

REPORT_TABLE = """Table B7. Waiting list candidate status after listing
Candidates registered on waiting list between 07/01/2023 and 06/30/2024
This Center (N=200) U.S. (N=12,345)
Waiting list status (survival status) Months Since Listing Months Since Listing
6 12 18 6 12 18
Transplant (living donor from waiting list only) (%):
Functioning (alive) 2.0 5.0 10.0 1.0 2.0 3.0
Failed-Retransplanted (alive) 0.0 0.0 0.0 0.0 0.0 0.0
Failed-alive not retransplanted 0.0 0.0 0.0 0.0 0.0 0.0
Died 0.0 0.0 0.0 0.0 0.0 0.0
Status Yet Unknown** 0.0 0.0 0.0 0.0 0.0 0.0
Transplant (deceased donor) (%):
Functioning (alive) 5.0 10.0 20.0 1.0 2.0 3.0
Failed-Retransplanted (alive) 0.0 0.0 0.0 0.0 0.0 0.0
Failed-alive not retransplanted 0.0 0.0 0.0 0.0 0.0 0.0
Died 0.0 0.0 0.0 0.0 0.0 0.0
Status Yet Unknown* 0.0 5.0 10.0 0.0 0.0 0.0
Lost or Transferred (status unknown) (%) 0.0 0.0 0.0 0.0 0.0 0.0
Total % removed for transplant 7.0 20.0 40.0 2.0 3.0 6.0
Total % with known functioning transplant (alive) 7.0 15.0 30.0 2.0 3.0 6.0
"""

SOURCE_TEXT = """Center Code: NYNS
Transplant Program (Organ): Kidney
Release Date: July 7, 2026
Table B7. Outcomes for candidates
Candidates registered on waiting list between 07/01/2023 and 06/30/2024
Months Since Listing 6 12 18
Table B10. Time to transplant for waiting list candidates*
Candidates registered on the waiting list between 01/01/2020 and 06/30/2025
** Censored on 12/31/2025.
"""


def test_source_dates_disagree_with_wrong_original_newest_cohort() -> None:
    periods = parse_source_periods(
        SOURCE_TEXT, SOURCE_TEXT, program_key="NYNS:TX1", published_value="2026-07-07"
    )
    assert periods.listing_start == date(2023, 7, 1)
    assert periods.listing_end == date(2024, 6, 30)
    assert periods.outcome_follow_up_bound == date(2025, 12, 31)
    with pytest.raises(ReceiptError, match="disagree"):
        periods.require_listing_dates(date(2023, 1, 1), date(2023, 12, 31))


@pytest.mark.parametrize("replacement", ["Liver", "Kidney-Pancreas", ""])
def test_wrong_organ_is_not_kidney_evidence(replacement: str) -> None:
    text = SOURCE_TEXT.replace("Kidney", replacement)
    with pytest.raises(ReceiptError, match="identity"):
        parse_source_periods(text, text, program_key="NYNS:TX1", published_value="2026-07-07")


def test_missing_and_wrong_release_evidence_fail() -> None:
    with pytest.raises(ReceiptError, match="listing"):
        parse_source_periods(
            SOURCE_TEXT.replace("registered on waiting list", "absent"),
            SOURCE_TEXT,
            program_key="NYNS:TX1",
            published_value="2026-07-07",
        )
    with pytest.raises(ReceiptError, match="publication"):
        parse_source_periods(
            SOURCE_TEXT, SOURCE_TEXT, program_key="NYNS:TX1", published_value="2025-07"
        )
    with pytest.raises(ReceiptError, match="censor"):
        parse_source_periods(
            SOURCE_TEXT,
            SOURCE_TEXT.replace("Censored on", "unknown"),
            program_key="NYNS:TX1",
            published_value="2026-07-07",
        )


def test_changed_evidence_bytes_fail_before_use(tmp_path: Path) -> None:
    rel = Path("data/receipt-study/source-research/report.txt")
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    content = SOURCE_TEXT.encode()
    path.write_bytes(content)
    pin = {"path": rel.as_posix(), "bytes": len(content), "sha256": sha256(content).hexdigest()}
    assert read_source_evidence(pin, repository_root=tmp_path) == SOURCE_TEXT
    path.write_bytes(content.replace(b"2023", b"2022"))
    with pytest.raises(ReceiptError, match="fingerprint"):
        read_source_evidence(pin, repository_root=tmp_path)
    pin["path"] = "../outside.txt"
    with pytest.raises(ReceiptError, match="path"):
        read_source_evidence(pin, repository_root=tmp_path)


def test_source_prefixes_and_month_precision() -> None:
    text = "\n".join(f"L{i}@P3: {line}" for i, line in enumerate(SOURCE_TEXT.splitlines()))
    periods = parse_source_periods(text, text, program_key="NYNS:TX1", published_value="2026-07")
    assert periods.wait_end == date(2025, 6, 30)


def _config() -> dict[str, object]:
    return json.loads(Path("configs/receipt_study/sources.json").read_text(encoding="utf-8"))


def _load_config(config: dict[str, object], tmp_path: Path):  # type: ignore[no-untyped-def]
    manifest_path = tmp_path / "configs/data_sources.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(Path("configs/data_sources.yaml").read_bytes())
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return load_receipt_sources(
        path,
        manifest=load_data_source_manifest(manifest_path),
        repository_root=tmp_path,
        cache_dir=tmp_path / "cache",
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_manifest_sha256", "0" * 64, "manifest"),
        ("follow_up_convention", "source_censor_date", "follow.up"),
        ("pairs", [["1905", "2205"]], "pairs"),
        ("folds", [], "folds"),
        ("schema_version", True, "identity"),
    ],
)
def test_changed_fixed_gate_fails_before_source_io(
    field: str, value: object, message: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config()
    config[field] = value
    monkeypatch.setattr(
        "kasm.patient_journey.receipt_sources._load_release",
        lambda *args: pytest.fail("Unvalidated configuration reached source I/O"),
    )
    with pytest.raises(ReceiptError, match=message):
        _load_config(config, tmp_path)


def test_removed_release_fails_before_source_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config()
    config["releases"] = config["releases"][1:]
    monkeypatch.setattr(
        "kasm.patient_journey.receipt_sources._load_release",
        lambda *args: pytest.fail("Unvalidated release set reached source I/O"),
    )
    with pytest.raises(ReceiptError, match="release set"):
        _load_config(config, tmp_path)


@pytest.mark.parametrize("published", ["2026", "2026-0", "2026-07-0", "2026-07-32"])
def test_partial_or_invalid_publication_date_is_not_evidence(published: str) -> None:
    with pytest.raises(ReceiptError, match="publication"):
        parse_source_periods(
            SOURCE_TEXT, SOURCE_TEXT, program_key="NYNS:TX1", published_value=published
        )


def test_ambiguous_wait_period_is_rejected() -> None:
    alternative = SOURCE_TEXT + SOURCE_TEXT.replace("01/01/2020", "01/01/2019")
    with pytest.raises(ReceiptError, match="wait-time.*ambiguous"):
        parse_source_periods(
            SOURCE_TEXT, alternative, program_key="NYNS:TX1", published_value="2026-07-07"
        )


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("07/01/2023", "07/01/2025", "July-June"),
        ("01/01/2020", "07/01/2025", "reversed"),
        ("12/31/2025", "12/31/2024", "reversed"),
        ("06/30/2024", "06/31/2024", "invalid date"),
    ],
)
def test_reversed_or_invalid_source_dates_fail(old: str, new: str, message: str) -> None:
    text = SOURCE_TEXT.replace(old, new)
    with pytest.raises(ReceiptError, match=message):
        parse_source_periods(text, text, program_key="NYNS:TX1", published_value="2026-07-07")


def test_manifest_object_must_match_fingerprinted_file(tmp_path: Path) -> None:
    config = _config()
    manifest_path = tmp_path / "configs/data_sources.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_bytes(Path("configs/data_sources.yaml").read_bytes())
    manifest = load_data_source_manifest(manifest_path)
    manifest = replace(manifest, sources=manifest.sources[:-1])
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ReceiptError, match="manifest"):
        load_receipt_sources(
            path, manifest=manifest, repository_root=tmp_path, cache_dir=tmp_path / "cache"
        )


def test_complete_source_config_retains_pair_order_and_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config()
    monkeypatch.setattr(
        "kasm.patient_journey.receipt_sources._load_release",
        lambda entry, source, root, cache, manifest: SimpleNamespace(source=source),
    )
    result = _load_config(config, tmp_path)
    assert tuple(r.source.release_code for r in result.releases) == (
        "1905",
        "2105",
        "2205",
        "2305",
        "2405",
        "2505",
        "2605",
    )
    assert result.pairs[-1] == ("2305", "2605")
    assert result.folds[-1] == (("2305", "2605"), (("1905", "2205"),))
    assert result.config_sha256 == sha256((tmp_path / "sources.json").read_bytes()).hexdigest()


def _receipt_fixture():  # type: ignore[no-untyped-def]
    entry = deepcopy(_config()["releases"][-1])
    manifest = load_data_source_manifest(Path("configs/data_sources.yaml"))
    source = manifest.sources[-1]
    periods = parse_source_periods(
        SOURCE_TEXT, SOURCE_TEXT, program_key="NYNS:TX1", published_value="2026-07-07"
    )
    values: dict[str, object] = {
        field: 0.0 for field in entry["shapes"]["outcome"]["required_fields"]
    }
    values.update(
        ENTIRE_NAME="Example",
        CTR_CD="NYNS",
        CTR_TY="TX1",
        RELEASE_DATE=date(2026, 7, 7),
        ORG="KI",
        SAL_N_C=200,
        SAL_CTXFNC_C18=20,
        SAL_CTXUNK_C18=10,
        SAL_LTXFNC_C18=10,
        SAL_WLLIVE_C18=60,
        SAL_TOTTX_C18=40,
        SAL_TOTFTX_C18=30,
        SAL_TOTAL_C18=100,
    )
    fields = tuple(values)
    entry["shapes"]["outcome"].update(expected_rows=1, expected_columns=len(fields))
    descriptions = {
        "CTR_CD": "Center Code",
        "CTR_TY": "Center Type",
        "SAL_N_C": "N",
        "SAL_TOTFTX_C18": "Functioning tx (alive)",
        "SAL_TOTTX_C18": "Removed for tx",
        "SAL_TOTAL_C18": "Total",
        "SAL_LOST_C18": "Lost or Transferred",
        "SAL_REFTX_C18": "Refused transplant (status unknown)",
        "SAL_REMDET_C18": "Condition Worsened (status unknown)",
        "SAL_REMOTH_C18": "Other",
        "SAL_REMREC_C18": "Condition improved (status unknown)",
        "SAL_WLDIED_C18": "Died on waitlist",
        "SAL_WLLIVE_C18": "Alive on waitlist",
    }
    for donor in ("CTX", "LTX"):
        for suffix, label in (
            ("FNC", "Functioning (alive)"),
            ("RE", "Failed-Retransplanted (alive)"),
            ("FAIL", "Failed-alive not retransplanted"),
            ("DIED", "Died"),
            ("UNK", "Status Yet Unknown"),
        ):
            descriptions[f"SAL_{donor}{suffix}_C18"] = label
    sheet = WorkbookSheet(
        "Table B7",
        (fields, tuple(descriptions.get(f, f) for f in fields), tuple(values.values())),
        len(fields),
    )
    checks = {
        field: {"source": values[field], "workbook": values[field], "matches": True}
        for field in entry["checks"]
    }
    registry = {"NYNS:TX1": ProgramIdentity("NYNS:TX1", "NYNS", "TX1", "Example", None, None, None)}
    return source, _methodology(entry, source, periods), (sheet,), registry, checks


def test_receipt_rows_preserve_exact_composite_identity() -> None:
    args = _receipt_fixture()
    rows = _receipt_rows(*args, "NYNS:TX1")
    assert rows[0].program_key == "NYNS:TX1"
    assert rows[0].values.derived_receipt_percent == 30


@pytest.mark.parametrize("field", ["SAL_N_C", "SAL_CTXUNK_C18", "SAL_LTXRE_C18", "SAL_TOTTX_C18"])
def test_source_binding_cannot_omit_any_of_the_thirteen_checks(field: str) -> None:
    source, method, sheets, registry, checks = _receipt_fixture()
    del checks[field]
    with pytest.raises(ReceiptError, match="13"):
        _receipt_rows(source, method, sheets, registry, checks, "NYNS:TX1")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "30"])
def test_source_check_is_finite_numeric_not_boolean_or_text(value: object) -> None:
    source, method, sheets, registry, checks = _receipt_fixture()
    checks["SAL_CTXUNK_C18"]["source"] = value
    with pytest.raises(ReceiptError, match="binding"):
        _receipt_rows(source, method, sheets, registry, checks, "NYNS:TX1")


@pytest.mark.parametrize(("field", "value"), [("matches", False), ("workbook", 20.5)])
def test_source_check_cannot_claim_false_or_changed_workbook_match(
    field: str, value: object
) -> None:
    source, method, sheets, registry, checks = _receipt_fixture()
    checks["SAL_CTXUNK_C18"][field] = value
    with pytest.raises(ReceiptError, match="binding"):
        _receipt_rows(source, method, sheets, registry, checks, "NYNS:TX1")


def test_changed_component_description_is_source_drift() -> None:
    source, method, sheets, registry, checks = _receipt_fixture()
    sheet = sheets[0]
    descriptions = list(sheet.rows[1])
    descriptions[sheet.rows[0].index("SAL_CTXUNK_C18")] = "Failed"
    sheet = replace(sheet, rows=(sheet.rows[0], tuple(descriptions), sheet.rows[2]))
    with pytest.raises(ReceiptError, match="description"):
        _receipt_rows(source, method, (sheet,), registry, checks, "NYNS:TX1")


def test_report_values_use_center_eighteen_month_column_and_original_group() -> None:
    from kasm.patient_journey.receipt_sources import _report_values

    values = _report_values(REPORT_TABLE)
    assert len(values) == 13
    assert values["SAL_N_C"] == 200
    assert values["SAL_CTXFNC_C18"] == 20
    assert values["SAL_LTXFNC_C18"] == 10
    assert values["SAL_CTXUNK_C18"] == 10
    assert values["SAL_TOTTX_C18"] == 40


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("This Center", "Unknown population"),
        ("6 12 18 6 12 18", "6 18 24 6 18 24"),
        ("Transplant (deceased donor)", "Transplant (other donor)"),
        ("20.0 1.0 2.0 3.0", "-- 1.0 2.0 3.0"),
    ],
)
def test_report_binding_rejects_missing_denominator_horizon_donor_or_value(
    old: str, new: str
) -> None:
    from kasm.patient_journey.receipt_sources import _report_values

    with pytest.raises(ReceiptError, match="Source.*binding"):
        _report_values(REPORT_TABLE.replace(old, new))


def test_loading_release_passes_validated_manifest_to_acceptance_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, method, sheets, registry, checks = _receipt_fixture()
    entry = deepcopy(_config()["releases"][-1])
    entry["checks"] = checks
    entry["shapes"]["outcome"].update(expected_rows=1, expected_columns=sheets[0].column_count)
    pdf = tmp_path / "data/audit-0022/nynstx1_ki.pdf"
    pdf.parent.mkdir(parents=True)
    content = b"%PDF-1.4\nfixture"
    pdf.write_bytes(content)
    entry["pdf_bytes"] = {
        "path": "data/audit-0022/nynstx1_ki.pdf",
        "bytes": len(content),
        "sha256": sha256(content).hexdigest(),
    }
    text = SOURCE_TEXT + REPORT_TABLE
    monkeypatch.setattr(
        "kasm.patient_journey.receipt_sources.read_source_evidence", lambda *args, **kwargs: text
    )
    monkeypatch.setattr(
        "kasm.patient_journey.receipt_sources.load_workbook_payload", lambda *args: b"fixture"
    )
    monkeypatch.setattr(
        "kasm.patient_journey.receipt_sources.read_workbook_sheets", lambda *args: sheets
    )
    monkeypatch.setattr(
        "kasm.patient_journey.receipt_sources._parse_identities",
        lambda *args: tuple(registry.values()),
    )
    monkeypatch.setattr(
        "kasm.patient_journey.receipt_sources._parse_transplant_rates", lambda *args: ()
    )
    monkeypatch.setattr("kasm.patient_journey.receipt_sources._parse_wait_times", lambda *args: ())
    sentinel = object()
    manifest = load_data_source_manifest(Path("configs/data_sources.yaml"))

    def acceptance(actual_manifest, actual_source, actual_sheets):  # type: ignore[no-untyped-def]
        assert actual_manifest == manifest
        assert actual_source == source
        assert actual_sheets == sheets
        return sentinel

    monkeypatch.setattr(
        "kasm.patient_journey.receipt_sources.parse_offer_acceptance_workbook", acceptance
    )
    result = _load_release(entry, source, tmp_path, tmp_path / "cache", manifest)
    assert result.acceptance is sentinel
    assert result.outcomes[0].values.derived_receipt_percent == 30


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("organ", "Kidney-Pancreas", "organ"),
        ("horizon_months", 12, "horizon"),
        ("horizon_months", True, "horizon"),
        ("evidence_kind", "unverified_notes", "evidence kind"),
        ("source_url", "https://example.test/NYNSTX1KI202605PNEW.pdf", "URL"),
        ("source_url", "https://srtr.hrsa.gov/reportapi/documents/psr/nynstx2_ki", "URL"),
        ("workbook_sheet", "Table B6", "sheet"),
        ("report_release_date", "July 7, 2025", "publication"),
    ],
)
def test_release_metadata_cannot_disagree_with_bound_report(
    field: str, value: object, message: str, tmp_path: Path
) -> None:
    manifest = load_data_source_manifest(Path("configs/data_sources.yaml"))
    entry = deepcopy(_config()["releases"][-1])
    entry[field] = value
    with pytest.raises(ReceiptError, match=message):
        _load_release(entry, manifest.sources[-1], tmp_path, tmp_path / "cache", manifest)


@pytest.mark.parametrize(
    ("field", "value"), [("bytes", True), ("bytes", "1"), ("sha256", "f" * 63)]
)
def test_evidence_fingerprint_requires_explicit_integer_size_and_sha256(
    field: str, value: object, tmp_path: Path
) -> None:
    path = tmp_path / "data/receipt-study/source-research/source.txt"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"a")
    pin = {
        "path": "data/receipt-study/source-research/source.txt",
        "bytes": 1,
        "sha256": sha256(b"a").hexdigest(),
    }
    pin[field] = value
    with pytest.raises(ReceiptError, match="fingerprint"):
        read_source_evidence(pin, repository_root=tmp_path)


@pytest.mark.parametrize(
    "value",
    [
        "data/receipt-study/source-research/report.txt:stream",
        "data/receipt-study/source-research/subdir/report.txt",
        "D:/outside.txt",
    ],
)
def test_evidence_rejects_streams_nested_and_absolute_paths(value: str, tmp_path: Path) -> None:
    with pytest.raises(ReceiptError, match="path"):
        read_source_evidence(
            {"path": value, "bytes": 1, "sha256": "a" * 64}, repository_root=tmp_path
        )


def test_evidence_rejects_linked_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    linked = tmp_path / "data/receipt-study/source-research"
    monkeypatch.setattr(Path, "is_symlink", lambda self: self == linked)
    with pytest.raises(ReceiptError, match="links"):
        read_source_evidence(
            {
                "path": "data/receipt-study/source-research/report.txt",
                "bytes": 1,
                "sha256": "a" * 64,
            },
            repository_root=tmp_path,
        )


def test_non_utf8_and_absent_source_files_fail(tmp_path: Path) -> None:
    relative = "data/receipt-study/source-research/report.txt"
    pin = {"path": relative, "bytes": 1, "sha256": sha256(b"\xff").hexdigest()}
    with pytest.raises(ReceiptError, match="Cannot read"):
        read_source_evidence(pin, repository_root=tmp_path)
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff")
    with pytest.raises(ReceiptError, match="Cannot read"):
        read_source_evidence(pin, repository_root=tmp_path)


def test_source_json_rejects_duplicate_keys(tmp_path: Path) -> None:
    path = tmp_path / "sources.json"
    path.write_text('{"schema_version": 2, "schema_version": 1}', encoding="utf-8")
    with pytest.raises(ReceiptError, match="duplicate"):
        load_receipt_sources(
            path,
            manifest=load_data_source_manifest(Path("configs/data_sources.yaml")),
            repository_root=tmp_path,
            cache_dir=tmp_path / "cache",
        )
