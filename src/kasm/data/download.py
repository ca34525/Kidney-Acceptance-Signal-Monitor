"""Verified, atomic acquisition for immutable public source files."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol, cast
from urllib.error import URLError
from urllib.request import Request, urlopen

from kasm.config import DataSourceManifest, SourceRecord
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


def _default_open_url(request: Request, *, timeout: float) -> DownloadResponse:
    return cast(DownloadResponse, urlopen(request, timeout=timeout))


def _download_to_temporary_file(
    source: SourceRecord,
    cache_dir: Path,
    open_url: OpenUrl,
    timeout_seconds: float,
) -> tuple[Path | None, CacheIssue | None]:
    request = Request(
        source.url,
        headers={
            "Accept": "application/octet-stream,application/zip,*/*;q=0.1",
            "User-Agent": "kidney-acceptance-signal-monitor/0.1 source-sync",
        },
    )
    temporary_path: Path | None = None
    try:
        with open_url(request, timeout=timeout_seconds) as response:
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
                while chunk := response.read(_CHUNK_BYTES):
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
