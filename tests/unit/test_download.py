from __future__ import annotations

from collections.abc import Callable
from email.message import Message
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.request import FTPHandler, HTTPHandler, HTTPSHandler, Request
from urllib.response import addinfourl

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


def test_download_stops_after_pinned_size_and_removes_partial_file(tmp_path: Path) -> None:
    expected = XLS_MAGIC + b"expected"
    response = FakeResponse(expected + b"x" * (2 * 1024 * 1024))
    sizes: list[int] = []
    original_read = response.read

    def read(size: int = -1) -> bytes:
        chunk = original_read(size)
        sizes.append(len(chunk))
        return chunk

    response.read = read
    result = sync_cache(_manifest_for(expected), tmp_path, open_url=lambda *a, **k: response)
    assert not result.ok
    assert "size" in result.issues[0].message.lower()
    assert sum(sizes) <= len(expected) + 1
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "destination", ["http://example.test/end.xls", "ftp://example.test/end.xls"]
)
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_default_opener_blocks_redirect_downgrade_before_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    destination: str,
    status: int,
) -> None:
    _check_redirect(tmp_path, monkeypatch, destination, status, expected_success=False)


@pytest.mark.parametrize("destination", ["https://example.test/end.xls", "/end.xls"])
def test_default_opener_follows_https_redirect_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    destination: str,
) -> None:
    _check_redirect(tmp_path, monkeypatch, destination, 302, expected_success=True)


def _check_redirect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    destination: str,
    status: int,
    *,
    expected_success: bool,
) -> None:
    payload = XLS_MAGIC + b"fixture"
    requested: list[str] = []

    def transport(handler: object, request: Request) -> addinfourl:
        requested.append(request.full_url)
        headers = Message()
        if len(requested) == 1:
            headers["Location"] = destination
            response = addinfourl(BytesIO(b""), headers, request.full_url, status)
            response.msg = "Redirect"
        else:
            response = addinfourl(BytesIO(payload), headers, request.full_url, 200)
            response.msg = "OK"
        return response

    # Replace transports, retaining urllib's actual redirect handling and the project opener.
    monkeypatch.setattr(HTTPSHandler, "https_open", transport)
    monkeypatch.setattr(HTTPHandler, "http_open", transport)
    monkeypatch.setattr(FTPHandler, "ftp_open", transport)
    result = sync_cache(_manifest_for(payload), tmp_path)
    assert result.ok is expected_success
    if expected_success:
        assert len(requested) == 2
        assert requested[-1] == "https://example.test/end.xls"
        assert (tmp_path / "source.xls").read_bytes() == payload
    else:
        assert requested == ["https://example.test/source.xls"]
        assert "HTTPS" in result.issues[0].message
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
