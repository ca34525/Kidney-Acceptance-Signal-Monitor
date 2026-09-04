from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.request import Request

import pytest

from kasm.config import DataSourceManifest, SourceRecord
from kasm.data.download import sync_cache

XLS_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")


class FakeResponse(BytesIO):
    def __init__(self, payload: bytes, *, status: int = 200) -> None:
        super().__init__(payload)
        self.status = status


def _manifest_for(
    payload: bytes,
    *,
    digest: str | None = None,
    url: str = "https://example.test/source.xls",
) -> DataSourceManifest:
    return DataSourceManifest(
        schema_version=2,
        sources=(
            SourceRecord(
                release_code="test",
                cohort_year=2025,
                transport="xls",
                url=url,
                download_bytes=len(payload),
                download_sha256=digest or sha256(payload).hexdigest(),
            ),
        ),
    )


def _opener_for(
    payload: bytes, *, status: int = 200
) -> tuple[Callable[..., FakeResponse], list[Request]]:
    requests: list[Request] = []

    def open_url(request: Request, *, timeout: float) -> FakeResponse:
        del timeout
        requests.append(request)
        return FakeResponse(payload, status=status)

    return open_url, requests


def test_download_rejects_wrong_sha256_without_publishing_partial_file(tmp_path: Path) -> None:
    payload = XLS_MAGIC + b"fixture"
    open_url, _ = _opener_for(payload)

    result = sync_cache(_manifest_for(payload, digest="0" * 64), tmp_path, open_url=open_url)

    assert not result.ok
    assert "sha-256" in result.issues[0].message.lower()
    assert not (tmp_path / "source.xls").exists()
    assert list(tmp_path.iterdir()) == []


def test_download_publishes_verified_file_and_records_request(tmp_path: Path) -> None:
    payload = XLS_MAGIC + b"fixture"
    open_url, requests = _opener_for(payload)

    result = sync_cache(_manifest_for(payload), tmp_path, open_url=open_url)

    assert result.ok
    assert result.downloaded_release_codes == ("test",)
    assert result.skipped_release_codes == ()
    assert (tmp_path / "source.xls").read_bytes() == payload
    assert requests[0].full_url == "https://example.test/source.xls"


def test_sync_skips_verified_existing_file_without_network(tmp_path: Path) -> None:
    payload = XLS_MAGIC + b"fixture"
    (tmp_path / "source.xls").write_bytes(payload)

    def unexpected_network(request: Request, *, timeout: float) -> FakeResponse:
        raise AssertionError(f"Unexpected network call for {request.full_url} after {timeout}")

    result = sync_cache(_manifest_for(payload), tmp_path, open_url=unexpected_network)

    assert result.ok
    assert result.downloaded_release_codes == ()
    assert result.skipped_release_codes == ("test",)


def test_sync_never_overwrites_invalid_existing_file(tmp_path: Path) -> None:
    payload = XLS_MAGIC + b"expected"
    invalid_payload = XLS_MAGIC + b"invalid"
    target = tmp_path / "source.xls"
    target.write_bytes(invalid_payload)

    def unexpected_network(request: Request, *, timeout: float) -> FakeResponse:
        raise AssertionError(f"Unexpected network call for {request.full_url} after {timeout}")

    result = sync_cache(_manifest_for(payload), tmp_path, open_url=unexpected_network)

    assert not result.ok
    assert "immutable" in result.issues[0].message.lower()
    assert target.read_bytes() == invalid_payload


def test_download_rejects_http_failure_without_partial_file(tmp_path: Path) -> None:
    payload = XLS_MAGIC + b"fixture"
    open_url, _ = _opener_for(payload, status=503)

    result = sync_cache(_manifest_for(payload), tmp_path, open_url=open_url)

    assert not result.ok
    assert "http status 503" in result.issues[0].message.lower()
    assert not (tmp_path / "source.xls").exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "url",
    [pytest.param("http://example.test/source.xls"), pytest.param("file:///tmp/source.xls")],
)
def test_sync_rejects_non_https_source_before_opening_url(tmp_path: Path, url: str) -> None:
    payload = XLS_MAGIC + b"fixture"

    def unexpected_network(request: Request, *, timeout: float) -> FakeResponse:
        raise AssertionError(f"Unsafe URL was opened: {request.full_url} after {timeout}")

    result = sync_cache(
        _manifest_for(payload, url=url),
        tmp_path,
        open_url=unexpected_network,
    )

    assert not result.ok
    assert "https" in result.issues[0].message.casefold()
    assert list(tmp_path.iterdir()) == []
