from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest
import xlwt

from kasm.config import DataSourceManifest, SourceRecord
from kasm.data.parse import (
    ParseError,
    WorkbookSheet,
    load_workbook_payload,
    parse_offer_acceptance_workbook,
    read_workbook_sheets,
)

MACHINE_COLUMNS = (
    "ENTIRE_NAME",
    "CTR_CD",
    "CTR_TY",
    "OAR_cohort_start",
    "OAR_cohort_end",
    "OA_OVERALL_OFFERS_CENTER",
    "OA_OVERALL_ACCEPTS_CENTER",
    "OA_OVERALL_EXP_ACCEPTS_CENTER",
    "OA_OVERALL_HR_MN_CENTER",
    "OA_OVERALL_HR_LB_CENTER",
    "OA_OVERALL_HR_UB_CENTER",
    "OA_LOWRISK_OFFERS_CENTER",
    "OA_LOWRISK_ACCEPTS_CENTER",
    "OA_LOWRISK_EXP_ACCEPTS_CENTER",
    "OA_LOWRISK_HR_MN_CENTER",
    "OA_LOWRISK_HR_LB_CENTER",
    "OA_LOWRISK_HR_UB_CENTER",
    "OA_MEDIUMRISK_OFFERS_CENTER",
    "OA_MEDIUMRISK_ACCEPTS_CENTER",
    "OA_MEDIUMRISK_EXP_ACCEPTS_CENTER",
    "OA_MEDIUMRISK_HR_MN_CENTER",
    "OA_MEDIUMRISK_HR_LB_CENTER",
    "OA_MEDIUMRISK_HR_UB_CENTER",
    "OA_HIGHRISK_OFFERS_CENTER",
    "OA_HIGHRISK_ACCEPTS_CENTER",
    "OA_HIGHRISK_EXP_ACCEPTS_CENTER",
    "OA_HIGHRISK_HR_MN_CENTER",
    "OA_HIGHRISK_HR_LB_CENTER",
    "OA_HIGHRISK_HR_UB_CENTER",
    "OA_HARDTOPLACE100_OFFERS_CENTER",
    "OA_HARDTOPLACE100_ACCEPTS_CENTER",
    "OA_HARDTOPLACE100_EXP_ACCEPTS_CENTER",
    "OA_HARDTOPLACE100_HR_MN_CENTER",
    "OA_HARDTOPLACE100_HR_LB_CENTER",
    "OA_HARDTOPLACE100_HR_UB_CENTER",
)


def _source(*, transport: str = "xls", rows: int = 2) -> SourceRecord:
    return SourceRecord(
        release_code="fixture",
        release_label="Fixture release",
        published_value="2026-07-07",
        published_precision="day",
        cohort_year=2025,
        expected_rows=rows,
        expected_columns=len(MACHINE_COLUMNS),
        sheet_name="Table B11 & Figures B10-B14",
        transport=transport,  # type: ignore[arg-type]
        url=f"https://example.test/source.{transport}",
        download_bytes=1,
        download_sha256="0" * 64,
        member_path="nested/source.xls" if transport == "zip" else None,
        member_bytes=1 if transport == "zip" else None,
        member_sha256="0" * 64 if transport == "zip" else None,
    )


def _manifest(source: SourceRecord | None = None) -> DataSourceManifest:
    return DataSourceManifest(
        schema_version=2,
        sources=(source or _source(),),
        required_machine_columns=MACHINE_COLUMNS,
        optional_recent_machine_columns=("OA_KDPI_GTE_60_HR_MN_CENTER",),
    )


def _program_row(
    *,
    code: str = "ABCD",
    center_type: str = "TX1",
    name: object = "Fixture Kidney Program",
) -> tuple[object, ...]:
    values: dict[str, object] = {
        "ENTIRE_NAME": name,
        "CTR_CD": code,
        "CTR_TY": center_type,
        "OAR_cohort_start": datetime(2025, 1, 1, 12, 30),
        "OAR_cohort_end": datetime(2025, 12, 30, 23, 59),
    }
    for prefix, offers in (
        ("OA_OVERALL", 100),
        ("OA_LOWRISK", 25),
        ("OA_MEDIUMRISK", 30),
        ("OA_HIGHRISK", 45),
        ("OA_HARDTOPLACE100", 10),
    ):
        values[f"{prefix}_OFFERS_CENTER"] = offers
        values[f"{prefix}_ACCEPTS_CENTER"] = offers // 10
        values[f"{prefix}_EXP_ACCEPTS_CENTER"] = offers / 8
        values[f"{prefix}_HR_MN_CENTER"] = 0.9
        values[f"{prefix}_HR_LB_CENTER"] = 0.7
        values[f"{prefix}_HR_UB_CENTER"] = 1.1
    return tuple(values[column] for column in MACHINE_COLUMNS)


def _workbook(
    *rows: tuple[object, ...], sheet_name: str | None = None
) -> tuple[WorkbookSheet, ...]:
    descriptions = [f"Description {i}" for i in range(len(MACHINE_COLUMNS))]
    descriptions[MACHINE_COLUMNS.index("CTR_CD")] = "Center ID"
    descriptions[MACHINE_COLUMNS.index("CTR_TY")] = "Center Type"
    return (
        WorkbookSheet(
            name=sheet_name or _source().sheet_name,
            rows=(MACHINE_COLUMNS, tuple(descriptions)) + rows,
            column_count=len(MACHINE_COLUMNS),
        ),
    )


def test_parser_finds_old_and_new_sheet_names() -> None:
    for sheet_name in ("Table B10 & Figures B7-B11", "Table B11 & Figures B10-B14"):
        source = replace(_source(rows=1), sheet_name=sheet_name)
        release = parse_offer_acceptance_workbook(
            _manifest(source), source, _workbook(_program_row(), sheet_name=sheet_name)
        )

        assert release.source_rows == 1
        assert len(release.signals) == 5


def test_program_key_uses_code_and_type() -> None:
    release = parse_offer_acceptance_workbook(
        _manifest(),
        _source(),
        _workbook(
            _program_row(center_type="TX1"),
            _program_row(center_type="VA1", name=None),
        ),
    )

    assert {row.program_key for row in release.signals} == {"ABCD:TX1", "ABCD:VA1"}
    assert {row.center_name for row in release.signals if row.center_type == "VA1"} == {
        "Program ABCD"
    }


def test_parser_uses_machine_field_names_not_column_positions() -> None:
    descriptions = [f"Description {i}" for i in range(len(MACHINE_COLUMNS))]
    descriptions[MACHINE_COLUMNS.index("CTR_CD")] = "Center ID"
    descriptions[MACHINE_COLUMNS.index("CTR_TY")] = "Center Type"
    order = tuple(reversed(range(len(MACHINE_COLUMNS))))
    source = replace(_source(), expected_rows=1)
    program = _program_row()
    sheet = WorkbookSheet(
        name=source.sheet_name,
        rows=(
            tuple(MACHINE_COLUMNS[index] for index in order),
            tuple(descriptions[index] for index in order),
            tuple(program[index] for index in order),
        ),
        column_count=len(MACHINE_COLUMNS),
    )

    release = parse_offer_acceptance_workbook(_manifest(source), source, (sheet,))

    assert release.signals[0].program_key == "ABCD:TX1"
    assert release.signals[0].offers == 100


def test_duplicate_composite_program_key_is_rejected() -> None:
    source = _source()

    with pytest.raises(ParseError, match="duplicates program key 'ABCD:TX1'"):
        parse_offer_acceptance_workbook(
            _manifest(source),
            source,
            _workbook(_program_row(), _program_row()),
        )


def test_missing_subgroup_ratio_stays_null() -> None:
    row = list(_program_row())
    row[MACHINE_COLUMNS.index("OA_LOWRISK_HR_MN_CENTER")] = ""
    row[MACHINE_COLUMNS.index("OA_LOWRISK_HR_LB_CENTER")] = None
    row[MACHINE_COLUMNS.index("OA_LOWRISK_HR_UB_CENTER")] = ""

    release = parse_offer_acceptance_workbook(
        _manifest(replace(_source(), expected_rows=1)),
        replace(_source(), expected_rows=1),
        _workbook(tuple(row)),
    )

    low = next(signal for signal in release.signals if signal.offer_group == "low")
    assert low.oar_mean is None
    assert low.oar_lower is None
    assert low.oar_upper is None


def test_zero_subgroup_offers_do_not_become_ratio_zero() -> None:
    row = list(_program_row())
    for suffix, value in (
        ("OFFERS_CENTER", 0),
        ("ACCEPTS_CENTER", 0),
        ("EXP_ACCEPTS_CENTER", 0),
        ("HR_MN_CENTER", ""),
        ("HR_LB_CENTER", ""),
        ("HR_UB_CENTER", ""),
    ):
        row[MACHINE_COLUMNS.index(f"OA_HARDTOPLACE100_{suffix}")] = value

    source = replace(_source(), expected_rows=1)
    release = parse_offer_acceptance_workbook(_manifest(source), source, _workbook(tuple(row)))

    hard_to_place = next(
        signal for signal in release.signals if signal.offer_group == "hard-to-place"
    )
    assert hard_to_place.offers == 0
    assert hard_to_place.acceptances == 0
    assert hard_to_place.expected_acceptances == 0
    assert hard_to_place.oar_mean is None


def test_zero_credible_lower_bound_is_preserved() -> None:
    row = list(_program_row())
    row[MACHINE_COLUMNS.index("OA_HARDTOPLACE100_HR_LB_CENTER")] = 0
    source = replace(_source(), expected_rows=1)

    release = parse_offer_acceptance_workbook(_manifest(source), source, _workbook(tuple(row)))

    hard_to_place = next(
        signal for signal in release.signals if signal.offer_group == "hard-to-place"
    )
    assert hard_to_place.oar_lower == 0


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("CTR_CD", "ABC", "center code"),
        ("OA_OVERALL_OFFERS_CENTER", 1.5, "whole number"),
        ("OA_OVERALL_ACCEPTS_CENTER", 101, "cannot exceed offers"),
        ("OA_OVERALL_EXP_ACCEPTS_CENTER", 101, "cannot exceed offers"),
        ("OA_OVERALL_HR_LB_CENTER", 1.0, "credible interval"),
        ("OA_HIGHRISK_OFFERS_CENTER", 0, "zero offers"),
    ],
)
def test_source_contract_rejects_invalid_rows(column: str, value: object, message: str) -> None:
    row = list(_program_row())
    row[MACHINE_COLUMNS.index(column)] = value
    source = replace(_source(), expected_rows=1)

    with pytest.raises(ParseError, match=message):
        parse_offer_acceptance_workbook(_manifest(source), source, _workbook(tuple(row)))


def test_parser_rejects_schema_and_row_count_drift() -> None:
    source = replace(_source(), expected_rows=1)
    missing_column_sheet = WorkbookSheet(
        name=source.sheet_name,
        rows=(MACHINE_COLUMNS[:-1], _program_row()[:-1]),
        column_count=len(MACHINE_COLUMNS) - 1,
    )

    with pytest.raises(ParseError, match="column count"):
        parse_offer_acceptance_workbook(_manifest(source), source, (missing_column_sheet,))

    with pytest.raises(ParseError, match="row count"):
        parse_offer_acceptance_workbook(
            _manifest(replace(source, expected_rows=2)),
            replace(source, expected_rows=2),
            _workbook(_program_row()),
        )


def test_parser_rejects_missing_required_machine_field_without_position_fallback() -> None:
    source = replace(_source(), expected_rows=1)
    headers = list(MACHINE_COLUMNS)
    headers[headers.index("OA_OVERALL_HR_MN_CENTER")] = "UNEXPECTED_FIELD"
    sheet = WorkbookSheet(
        name=source.sheet_name,
        rows=(tuple(headers), _program_row()),
        column_count=len(MACHINE_COLUMNS),
    )

    with pytest.raises(ParseError, match="machine-header row"):
        parse_offer_acceptance_workbook(_manifest(source), source, (sheet,))


def test_parser_rejects_incomplete_manifest_machine_contract() -> None:
    source = replace(_source(), expected_rows=1)
    manifest = replace(_manifest(source), required_machine_columns=MACHINE_COLUMNS[:-1])

    with pytest.raises(ParseError, match="manifest machine-column contract"):
        parse_offer_acceptance_workbook(manifest, source, _workbook(_program_row()))


def test_parser_rejects_non_calendar_year_cohort_dates() -> None:
    row = list(_program_row())
    row[MACHINE_COLUMNS.index("OAR_cohort_start")] = datetime(2024, 12, 25)
    source = replace(_source(), expected_rows=1)

    with pytest.raises(ParseError, match="full calendar year 2025"):
        parse_offer_acceptance_workbook(_manifest(source), source, _workbook(tuple(row)))


def test_output_is_logically_deterministic_and_preserves_provenance() -> None:
    source = replace(_source(), expected_rows=1)
    first = parse_offer_acceptance_workbook(_manifest(source), source, _workbook(_program_row()))
    second = parse_offer_acceptance_workbook(_manifest(source), source, _workbook(_program_row()))

    assert first == second
    assert [row.offer_group for row in first.signals] == [
        "overall",
        "low",
        "medium",
        "high",
        "hard-to-place",
    ]
    assert all(row.cohort_start.isoformat() == "2025-01-01" for row in first.signals)
    assert all(row.cohort_end.isoformat() == "2025-12-31" for row in first.signals)
    assert all(row.published_value == "2026-07-07" for row in first.signals)
    assert all(row.published_precision == "day" for row in first.signals)
    assert all(row.source_url == source.url for row in first.signals)
    assert all(row.source_sha256 == source.download_sha256 for row in first.signals)


def test_loader_selects_configured_zip_member_without_extracting(tmp_path: Path) -> None:
    member_payload = bytes.fromhex("D0CF11E0A1B11AE1") + b"selected"
    archive_path = tmp_path / "source.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("other.xls", bytes.fromhex("D0CF11E0A1B11AE1") + b"other")
        archive.writestr("nested/source.xls", member_payload)
    archive_payload = archive_path.read_bytes()
    source = replace(
        _source(transport="zip"),
        download_bytes=len(archive_payload),
        download_sha256=sha256(archive_payload).hexdigest(),
        member_bytes=len(member_payload),
        member_sha256=sha256(member_payload).hexdigest(),
    )

    assert load_workbook_payload(source, tmp_path) == member_payload
    assert tuple(tmp_path.iterdir()) == (archive_path,)


def test_loader_returns_verified_direct_xls_bytes(tmp_path: Path) -> None:
    payload = bytes.fromhex("D0CF11E0A1B11AE1") + b"direct"
    path = tmp_path / "source.xls"
    path.write_bytes(payload)
    source = replace(
        _source(),
        download_bytes=len(payload),
        download_sha256=sha256(payload).hexdigest(),
    )

    assert load_workbook_payload(source, tmp_path) == payload


def test_xls_adapter_reads_two_row_header_and_date_cells(tmp_path: Path) -> None:
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet(_source().sheet_name)
    descriptions = [f"Description {i}" for i in range(len(MACHINE_COLUMNS))]
    descriptions[MACHINE_COLUMNS.index("CTR_CD")] = "Center ID"
    descriptions[MACHINE_COLUMNS.index("CTR_TY")] = "Center Type"
    date_style = xlwt.easyxf(num_format_str="YYYY-MM-DD")
    for column_index, value in enumerate(MACHINE_COLUMNS):
        sheet.write(0, column_index, value)
    for column_index, value in enumerate(descriptions):
        sheet.write(1, column_index, value)
    for column_index, value in enumerate(_program_row()):
        if isinstance(value, datetime):
            sheet.write(2, column_index, value, date_style)
        else:
            sheet.write(2, column_index, value)
    workbook_path = tmp_path / "fixture.xls"
    workbook.save(str(workbook_path))

    source = replace(_source(), expected_rows=1)
    sheets = read_workbook_sheets(workbook_path.read_bytes())
    release = parse_offer_acceptance_workbook(_manifest(source), source, sheets)

    assert release.source_rows == 1
    assert release.signals[0].cohort_start.isoformat() == "2025-01-01"
    assert release.signals[0].cohort_end.isoformat() == "2025-12-31"


def test_xls_adapter_rejects_invalid_payload() -> None:
    with pytest.raises(ParseError, match="Could not open XLS workbook"):
        read_workbook_sheets(b"not a workbook")
