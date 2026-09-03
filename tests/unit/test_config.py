from pathlib import Path

import pytest

from kasm.config import ManifestError, load_data_source_manifest


def test_manifest_rejects_duplicate_cohort_year(tmp_path: Path) -> None:
    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(
        """
schema_version: 2
sources:
  - release_code: first
    cohort_year: 2024
    transport: xls
    url: https://example.test/first.xls
    download_bytes: 8
    download_sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  - release_code: second
    cohort_year: 2024
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


def test_zip_source_requires_member_contract(tmp_path: Path) -> None:
    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(
        """
schema_version: 2
sources:
  - release_code: archive
    cohort_year: 2024
    transport: zip
    url: https://example.test/archive.zip
    download_bytes: 100
    download_sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="member_path"):
        load_data_source_manifest(manifest_path)
