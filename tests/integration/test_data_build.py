from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path

import pyarrow.parquet as pq
import xlwt

from kasm.config import DataSourceManifest, SourceRecord
from kasm.data.build import build_cached_data
from kasm.data.parse import _PARSER_REQUIRED_COLUMNS


def _program_row(program_key: str, year: int, overall_oar: float) -> tuple[object, ...]:
    center_code, center_type = program_key.split(":")
    values: dict[str, object] = {
        "ENTIRE_NAME": f"Program {center_code}",
        "CTR_CD": center_code,
        "CTR_TY": center_type,
        "OAR_cohort_start": datetime(year, 1, 1),
        "OAR_cohort_end": datetime(year, 12, 31),
    }
    for group, offers, ratio in (
        ("OA_OVERALL", 100, overall_oar),
        ("OA_LOWRISK", 25, overall_oar + 0.1),
        ("OA_MEDIUMRISK", 30, overall_oar + 0.2),
        ("OA_HIGHRISK", 45, overall_oar + 0.3),
        ("OA_HARDTOPLACE100", 10, overall_oar + 0.4),
    ):
        values[f"{group}_OFFERS_CENTER"] = offers
        values[f"{group}_ACCEPTS_CENTER"] = offers // 10
        values[f"{group}_EXP_ACCEPTS_CENTER"] = offers / 8
        values[f"{group}_HR_MN_CENTER"] = ratio
        values[f"{group}_HR_LB_CENTER"] = ratio * 0.8
        values[f"{group}_HR_UB_CENTER"] = ratio * 1.2
    return tuple(values[column] for column in _PARSER_REQUIRED_COLUMNS)


def _write_workbook(
    cache_dir: Path,
    *,
    year: int,
    release_code: str,
    program_ratios: tuple[tuple[str, float], ...],
    include_directory: bool,
) -> SourceRecord:
    workbook = xlwt.Workbook()
    sheet_name = "Table B11 & Figures B10-B14"
    signals = workbook.add_sheet(sheet_name)
    descriptions = [f"Description {index}" for index in range(len(_PARSER_REQUIRED_COLUMNS))]
    descriptions[_PARSER_REQUIRED_COLUMNS.index("CTR_CD")] = "Center ID"
    descriptions[_PARSER_REQUIRED_COLUMNS.index("CTR_TY")] = "Center Type"
    date_style = xlwt.easyxf(num_format_str="YYYY-MM-DD")
    for column_index, value in enumerate(_PARSER_REQUIRED_COLUMNS):
        signals.write(0, column_index, value)
    for column_index, value in enumerate(descriptions):
        signals.write(1, column_index, value)
    for row_index, (program_key, ratio) in enumerate(program_ratios, start=2):
        for column_index, value in enumerate(_program_row(program_key, year, ratio)):
            signals.write(
                row_index,
                column_index,
                value,
                date_style if isinstance(value, datetime) else xlwt.Style.default_style,
            )

    if include_directory:
        tiers = workbook.add_sheet("Tiers")
        headers = (
            "ENTIRE_NAME",
            "PRIMARY_CITY",
            "PRIMARY_STATE",
            "PRIMARY_ZIP",
            "CTR_CD",
            "CTR_TY",
            "ORGAN",
        )
        descriptions = (
            "Center Name",
            "Primary City",
            "Primary State",
            "Primary Zip",
            "Center Code",
            "Center Type",
            "Organ",
        )
        for column_index, value in enumerate(headers):
            tiers.write(0, column_index, value)
        for column_index, value in enumerate(descriptions):
            tiers.write(1, column_index, value)
        directory_rows = tuple(program_ratios) + (("ONLY:TX1", 0.0),)
        for row_index, (program_key, _) in enumerate(directory_rows, start=2):
            center_code, center_type = program_key.split(":")
            row = (
                f"Current {center_code}",
                "Boston",
                "MA",
                "01234",
                center_code,
                center_type,
                "Kidney",
            )
            for column_index, value in enumerate(row):
                tiers.write(row_index, column_index, value)

    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{release_code}.xls"
    workbook.save(str(path))
    payload = path.read_bytes()
    return SourceRecord(
        release_code=release_code,
        release_label=f"Fixture {year}",
        published_value=f"{year + 1}-07-07",
        published_precision="day",
        cohort_year=year,
        expected_rows=len(program_ratios),
        expected_columns=len(_PARSER_REQUIRED_COLUMNS),
        sheet_name=sheet_name,
        transport="xls",
        url=f"https://example.test/{release_code}.xls",
        download_bytes=len(payload),
        download_sha256=sha256(payload).hexdigest(),
    )


def test_verified_workbooks_build_parquet_panel_and_qa_offline(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    first = _write_workbook(
        cache_dir,
        year=2023,
        release_code="first",
        program_ratios=(("ABCD:TX1", 0.8), ("EXIT:TX1", 0.7)),
        include_directory=False,
    )
    second = _write_workbook(
        cache_dir,
        year=2024,
        release_code="second",
        program_ratios=(("ABCD:TX1", 0.9), ("NEW1:TX1", 1.1)),
        include_directory=True,
    )
    manifest = DataSourceManifest(
        schema_version=2,
        sources=(first, second),
        required_machine_columns=_PARSER_REQUIRED_COLUMNS,
    )

    result = build_cached_data(manifest, cache_dir, tmp_path / "processed")

    signals = pq.read_table(result.program_signals_path)
    panel = pq.read_table(result.model_panel_path).to_pylist()
    qa = json.loads(result.qa_report_path.read_text(encoding="utf-8"))
    assert signals.num_rows == 20
    assert len(panel) == 4
    exited = next(row for row in panel if row["program_key"] == "EXIT:TX1")
    assert exited["target_cohort_year"] == 2024
    assert exited["target_oar"] is None
    assert qa["annual_transitions"][0]["added_program_keys"] == ["NEW1:TX1"]
    assert qa["annual_transitions"][0]["closed_program_keys"] == ["EXIT:TX1"]
    assert qa["directory"]["directory_only_program_keys"] == ["ONLY:TX1"]
