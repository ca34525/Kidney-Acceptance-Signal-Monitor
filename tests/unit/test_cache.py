from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from kasm.config import DataSourceManifest, SourceRecord
from kasm.data.cache import verify_cache

XLS_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")


def _manifest_for(payload: bytes, *, digest: str | None = None) -> DataSourceManifest:
    return DataSourceManifest(
        schema_version=2,
        sources=(
            SourceRecord(
                release_code="test",
                cohort_year=2025,
                transport="xls",
                url="https://example.test/source.xls",
                download_bytes=len(payload),
                download_sha256=digest or sha256(payload).hexdigest(),
            ),
        ),
    )


def test_verify_cache_reports_missing_file(tmp_path: Path) -> None:
    result = verify_cache(_manifest_for(XLS_MAGIC), tmp_path)

    assert not result.ok
    assert result.checked_sources == 1
    assert "missing" in result.issues[0].message.lower()


def test_verify_cache_accepts_exact_direct_file(tmp_path: Path) -> None:
    payload = XLS_MAGIC + b"fixture"
    (tmp_path / "source.xls").write_bytes(payload)

    result = verify_cache(_manifest_for(payload), tmp_path)

    assert result.ok
    assert result.checked_sources == 1


def test_verify_cache_rejects_wrong_sha256(tmp_path: Path) -> None:
    payload = XLS_MAGIC + b"fixture"
    (tmp_path / "source.xls").write_bytes(payload)

    result = verify_cache(_manifest_for(payload, digest="0" * 64), tmp_path)

    assert not result.ok
    assert "sha-256" in result.issues[0].message.lower()


def test_verify_cache_rejects_wrong_size(tmp_path: Path) -> None:
    payload = XLS_MAGIC + b"fixture"
    (tmp_path / "source.xls").write_bytes(payload)
    source = _manifest_for(payload).sources[0]
    manifest = DataSourceManifest(
        schema_version=2,
        sources=(
            SourceRecord(
                release_code=source.release_code,
                cohort_year=source.cohort_year,
                transport=source.transport,
                url=source.url,
                download_bytes=source.download_bytes + 1,
                download_sha256=source.download_sha256,
            ),
        ),
    )

    result = verify_cache(manifest, tmp_path)

    assert not result.ok
    assert "size" in result.issues[0].message.lower()


def test_verify_cache_rejects_wrong_file_type(tmp_path: Path) -> None:
    payload = b"not an xls workbook"
    (tmp_path / "source.xls").write_bytes(payload)

    result = verify_cache(_manifest_for(payload), tmp_path)

    assert not result.ok
    assert "file type" in result.issues[0].message.lower()


def test_verify_cache_checks_expected_zip_member(tmp_path: Path) -> None:
    member_payload = XLS_MAGIC + b"workbook"
    archive_path = tmp_path / "source.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("nested/source.xls", member_payload)
    archive_payload = archive_path.read_bytes()
    manifest = DataSourceManifest(
        schema_version=2,
        sources=(
            SourceRecord(
                release_code="test",
                cohort_year=2025,
                transport="zip",
                url="https://example.test/source.zip",
                download_bytes=len(archive_payload),
                download_sha256=sha256(archive_payload).hexdigest(),
                member_path="nested/source.xls",
                member_bytes=len(member_payload),
                member_sha256=sha256(member_payload).hexdigest(),
            ),
        ),
    )

    result = verify_cache(manifest, tmp_path)

    assert result.ok
    assert result.checked_sources == 1


def test_verify_cache_rejects_unsafe_archive_member(tmp_path: Path) -> None:
    member_payload = XLS_MAGIC + b"workbook"
    archive_path = tmp_path / "source.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("nested/source.xls", member_payload)
        archive.writestr("../escape.txt", b"unsafe")
    archive_payload = archive_path.read_bytes()
    manifest = DataSourceManifest(
        schema_version=2,
        sources=(
            SourceRecord(
                release_code="test",
                cohort_year=2025,
                transport="zip",
                url="https://example.test/source.zip",
                download_bytes=len(archive_payload),
                download_sha256=sha256(archive_payload).hexdigest(),
                member_path="nested/source.xls",
                member_bytes=len(member_payload),
                member_sha256=sha256(member_payload).hexdigest(),
            ),
        ),
    )

    result = verify_cache(manifest, tmp_path)

    assert not result.ok
    assert "unsafe" in result.issues[0].message.lower()
