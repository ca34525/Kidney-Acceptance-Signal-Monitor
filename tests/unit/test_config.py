from pathlib import Path

import pytest
import yaml

from kasm.config import ManifestError, load_data_source_manifest


def test_manifest_rejects_duplicate_cohort_year(tmp_path: Path) -> None:
    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(
        """
schema_version: 2
required_machine_columns: [CTR_CD]
optional_recent_machine_columns: []
sources:
  - release_code: first
    release_label: First
    release_date_value: "2025-07-01"
    release_date_precision: day
    cohort_year: 2024
    expected_rows: 200
    expected_columns: 1
    sheet_name: Sheet
    transport: xls
    url: https://example.test/first.xls
    download_bytes: 8
    download_sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  - release_code: second
    release_label: Second
    release_date_value: "2025-07-01"
    release_date_precision: day
    cohort_year: 2024
    expected_rows: 200
    expected_columns: 1
    sheet_name: Sheet
    transport: xls
    url: https://example.test/second.xls
    download_bytes: 8
    download_sha256: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="Duplicate cohort_year 2024"):
        load_data_source_manifest(manifest_path)


def test_project_manifest_loads_all_nine_pinned_sources() -> None:
    manifest = load_data_source_manifest(Path("configs/data_sources.yaml"))

    assert manifest.schema_version == 2
    assert tuple(source.cohort_year for source in manifest.sources) == tuple(range(2017, 2026))
    assert "CTR_CD" in manifest.required_machine_columns
    assert "OA_OVERALL_HR_MN_CENTER" in manifest.required_machine_columns
    assert "OA_KDPI_GTE_60_HR_MN_CENTER" in manifest.optional_recent_machine_columns
    assert manifest.sources[0].sheet_name == "Table B10 & Figures B7-B11"
    assert manifest.sources[-1].sheet_name == "Table B11 & Figures B10-B14"
    assert manifest.sources[0].published_value == "2018-10"
    assert manifest.sources[0].published_precision == "month"
    assert manifest.sources[-1].published_precision == "day"
    assert manifest.sources[-1].expected_rows == 230
    assert manifest.sources[-1].expected_columns == 143


def test_zip_source_requires_member_contract(tmp_path: Path) -> None:
    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(
        """
schema_version: 2
required_machine_columns: [CTR_CD]
optional_recent_machine_columns: []
sources:
  - release_code: archive
    release_label: Archive
    release_date_value: "2025-07-01"
    release_date_precision: day
    cohort_year: 2024
    expected_rows: 200
    expected_columns: 1
    sheet_name: Sheet
    transport: zip
    url: https://example.test/archive.zip
    download_bytes: 100
    download_sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="member_path"):
        load_data_source_manifest(manifest_path)


def test_manifest_rejects_invalid_publication_precision(tmp_path: Path) -> None:
    raw = yaml.safe_load(Path("configs/data_sources.yaml").read_text(encoding="utf-8"))
    raw["sources"][0]["release_date_precision"] = "week"
    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ManifestError, match="release_date_precision"):
        load_data_source_manifest(manifest_path)


def test_manifest_rejects_duplicate_machine_field(tmp_path: Path) -> None:
    raw = yaml.safe_load(Path("configs/data_sources.yaml").read_text(encoding="utf-8"))
    raw["required_machine_columns"].append(raw["required_machine_columns"][0])
    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ManifestError, match="Duplicate required_machine_columns"):
        load_data_source_manifest(manifest_path)


def test_manifest_requires_release_parser_metadata(tmp_path: Path) -> None:
    raw = yaml.safe_load(Path("configs/data_sources.yaml").read_text(encoding="utf-8"))
    del raw["sources"][0]["sheet_name"]
    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ManifestError, match="sheet_name"):
        load_data_source_manifest(manifest_path)


def test_manifest_stops_when_a_release_has_fewer_than_200_program_rows(tmp_path: Path) -> None:
    raw = yaml.safe_load(Path("configs/data_sources.yaml").read_text(encoding="utf-8"))
    raw["sources"][0]["expected_rows"] = 199
    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ManifestError, match="at least 200"):
        load_data_source_manifest(manifest_path)
