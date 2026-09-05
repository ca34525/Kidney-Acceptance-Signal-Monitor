"""Download approved public reports and publish a file only after verification.

Downloads stay in temporary files until their size, type, and SHA-256 fingerprint
match the manifest. An atomic move makes only the completed file available to readers.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from http.client import HTTPMessage
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import IO, Protocol, cast
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from kasm.config import DataSourceManifest, SourceRecord, is_https_file_url
from kasm.data.cache import CacheIssue, verify_source_file

_CHUNK_BYTES = 1024 * 1024
_DEFAULT_TIMEOUT_SECONDS = 60.0


class DownloadResponse(Protocol):
    """Minimum response interface needed by the streaming downloader."""

    status: int

    def read(self, size: int = -1) -> bytes:
        """Read response bytes."""

    def __enter__(self) -> DownloadResponse:
        """Enter the response context."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> bool | None:
        """Exit the response context."""


OpenUrl = Callable[..., DownloadResponse]


@dataclass(frozen=True)
class CacheSync:
    """Aggregate outcome from explicit source-cache acquisition."""

    checked_sources: int
    downloaded_release_codes: tuple[str, ...]
    skipped_release_codes: tuple[str, ...]
    issues: tuple[CacheIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


class _HttpsRedirectHandler(HTTPRedirectHandler):
    """Check each destination before urllib follows a source redirect."""

    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> Request | None:
        if not is_https_file_url(newurl):
            raise URLError("Source redirect destination must be an absolute HTTPS file URL.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_open_url(request: Request, *, timeout: float) -> DownloadResponse:
    # Initial URLs and every redirect are checked; normal TLS certificate checks still apply.
    opener = build_opener(_HttpsRedirectHandler())
    return cast(DownloadResponse, opener.open(request, timeout=timeout))  # noqa: S310


def _download_to_temporary_file(
    source: SourceRecord,
    cache_dir: Path,
    open_url: OpenUrl,
    timeout_seconds: float,
) -> tuple[Path | None, CacheIssue | None]:
    request = Request(  # noqa: S310 - `_sync_source` permits absolute HTTPS URLs only
        source.url,
        headers={
            "Accept": "application/octet-stream,application/zip,*/*;q=0.1",
            "User-Agent": "kidney-acceptance-signal-monitor/0.1 source-sync",
        },
    )
    temporary_path: Path | None = None
    try:
        # The injected opener is useful for offline tests; `_sync_source` still validates HTTPS.
        with open_url(request, timeout=timeout_seconds) as response:  # noqa: S310
            if response.status != 200:
                return None, CacheIssue(
                    source.release_code,
                    f"Download returned HTTP status {response.status} for {source.url}.",
                )
            with NamedTemporaryFile(
                mode="wb",
                dir=cache_dir,
                prefix=f".{source.cache_filename}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                downloaded_bytes = 0
                # Read at most one excess byte so a changed source cannot fill the cache disk.
                while chunk := response.read(
                    min(_CHUNK_BYTES, source.download_bytes - downloaded_bytes + 1)
                ):
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > source.download_bytes:
                        raise OSError(
                            f"Download exceeds pinned size of {source.download_bytes} bytes"
                        )
                    temporary_file.write(chunk)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
    except (OSError, URLError) as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        return None, CacheIssue(
            source.release_code,
            f"Download failed for {source.url}: {error}.",
        )
    return temporary_path, None


def _publish_without_overwrite(temporary_path: Path, target_path: Path) -> CacheIssue | None:
    try:
        os.link(temporary_path, target_path)
    except FileExistsError:
        return CacheIssue(
            "",
            "Immutable cache target appeared during download and was not overwritten: "
            f"{target_path}.",
        )
    except OSError as error:
        return CacheIssue("", f"Could not atomically publish {target_path}: {error}.")
    finally:
        temporary_path.unlink(missing_ok=True)
    return None


def _sync_source(
    source: SourceRecord,
    cache_dir: Path,
    open_url: OpenUrl,
    timeout_seconds: float,
) -> tuple[str, tuple[CacheIssue, ...]]:
    if not is_https_file_url(source.url):
        return "failed", (
            CacheIssue(
                source.release_code,
                f"Source URL must be an HTTPS file URL and was not opened: {source.url}.",
            ),
        )
    target_path = cache_dir / source.cache_filename
    if target_path.exists():
        existing_issues = verify_source_file(target_path, source)
        if existing_issues:
            issues = tuple(
                CacheIssue(
                    source.release_code,
                    f"Immutable cache file was not overwritten: {issue.message}",
                )
                for issue in existing_issues
            )
            return "failed", issues
        return "skipped", ()

    temporary_path, download_issue = _download_to_temporary_file(
        source, cache_dir, open_url, timeout_seconds
    )
    if download_issue is not None:
        return "failed", (download_issue,)
    if temporary_path is None:
        raise RuntimeError("Downloader returned neither a temporary path nor an issue.")

    verification_issues = verify_source_file(temporary_path, source)
    if verification_issues:
        temporary_path.unlink(missing_ok=True)
        return "failed", verification_issues

    publish_issue = _publish_without_overwrite(temporary_path, target_path)
    if publish_issue is not None:
        return "failed", (CacheIssue(source.release_code, publish_issue.message),)
    return "downloaded", ()


def sync_cache(
    manifest: DataSourceManifest,
    cache_dir: Path,
    *,
    open_url: OpenUrl = _default_open_url,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> CacheSync:
    """Download missing sources and publish only files that pass pinned verification."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[str] = []
    skipped: list[str] = []
    issues: list[CacheIssue] = []

    for source in manifest.sources:
        status, source_issues = _sync_source(source, cache_dir, open_url, timeout_seconds)
        if status == "downloaded":
            downloaded.append(source.release_code)
        elif status == "skipped":
            skipped.append(source.release_code)
        issues.extend(source_issues)

    return CacheSync(
        checked_sources=len(manifest.sources),
        downloaded_release_codes=tuple(downloaded),
        skipped_release_codes=tuple(skipped),
        issues=tuple(issues),
    )
