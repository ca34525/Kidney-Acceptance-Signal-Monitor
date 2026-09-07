"""Check saved source files against approved sizes and SHA-256 fingerprints offline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import IO
from zipfile import BadZipFile, ZipFile, is_zipfile
from zlib import error as ZlibError

from kasm.config import DataSourceManifest, SourceRecord

_XLS_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
_WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:")


@dataclass(frozen=True)
class CacheIssue:
    """One actionable cache verification failure."""

    release_code: str
    message: str


@dataclass(frozen=True)
class CacheVerification:
    """Aggregate result from checking an immutable cache."""

    checked_sources: int
    issues: tuple[CacheIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


def _digest_and_prefix(stream: IO[bytes], prefix_bytes: int = 8) -> tuple[str, bytes]:
    digest = sha256()
    prefix = b""
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
        if len(prefix) < prefix_bytes:
            prefix += chunk[: prefix_bytes - len(prefix)]
    return digest.hexdigest(), prefix


def _issue(source: SourceRecord, message: str) -> CacheIssue:
    return CacheIssue(release_code=source.release_code, message=message)


def _unsafe_member_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return (
        not normalized
        or normalized.startswith("/")
        or _WINDOWS_DRIVE_PATTERN.match(normalized) is not None
        or ".." in path.parts
    )


def _verify_zip(path: Path, source: SourceRecord) -> list[CacheIssue]:
    issues: list[CacheIssue] = []
    if not is_zipfile(path):
        return [_issue(source, f"File type mismatch for {path.name}: expected ZIP archive.")]
    if source.member_path is None or source.member_bytes is None or source.member_sha256 is None:
        return [_issue(source, "ZIP member contract is incomplete after manifest validation.")]

    try:
        with ZipFile(path) as archive:
            unsafe_names = [
                info.filename for info in archive.infolist() if _unsafe_member_name(info.filename)
            ]
            if unsafe_names:
                issues.append(
                    _issue(source, f"Archive contains unsafe member path {unsafe_names[0]!r}.")
                )
                return issues

            try:
                member = archive.getinfo(source.member_path)
            except KeyError:
                issues.append(
                    _issue(source, f"Expected archive member {source.member_path!r} is missing.")
                )
                return issues

            if member.is_dir():
                issues.append(
                    _issue(
                        source, f"Expected archive member {source.member_path!r} is a directory."
                    )
                )
                return issues
            if member.file_size != source.member_bytes:
                issues.append(
                    _issue(
                        source,
                        "Archive member size mismatch: "
                        f"expected {source.member_bytes}, found {member.file_size} bytes.",
                    )
                )
                return issues
            with archive.open(member) as stream:
                member_digest, member_prefix = _digest_and_prefix(stream)
            if member_digest != source.member_sha256:
                issues.append(
                    _issue(
                        source,
                        "Archive member SHA-256 mismatch: "
                        f"expected {source.member_sha256}, found {member_digest}.",
                    )
                )
            if member_prefix != _XLS_MAGIC:
                issues.append(
                    _issue(source, "Archive member file type mismatch: expected an XLS workbook.")
                )
    except BadZipFile:
        issues.append(_issue(source, f"File type mismatch for {path.name}: invalid ZIP archive."))
    except (NotImplementedError, RuntimeError, OSError, EOFError, ZlibError) as error:
        issues.append(_issue(source, f"Cannot read ZIP archive {path.name}: {error}."))
    return issues


def verify_source_file(path: Path, source: SourceRecord) -> tuple[CacheIssue, ...]:
    """Check one saved report without changing it or accepting a new fingerprint.

    Stop after a size or hash mismatch, before opening an untrusted archive. A ZIP's
    named workbook must also match its approved size, fingerprint, and file type.
    """
    if not path.exists():
        return (_issue(source, f"Cached source is missing: {path}."),)
    if not path.is_file():
        return (_issue(source, f"Cached source is not a regular file: {path}."),)

    issues: list[CacheIssue] = []
    actual_bytes = path.stat().st_size
    if actual_bytes != source.download_bytes:
        issues.append(
            _issue(
                source,
                "Download size mismatch: "
                f"expected {source.download_bytes}, found {actual_bytes} bytes.",
            )
        )
        return tuple(issues)
    with path.open("rb") as stream:
        actual_digest, prefix = _digest_and_prefix(stream)
    if actual_digest != source.download_sha256:
        issues.append(
            _issue(
                source,
                "Download SHA-256 mismatch: "
                f"expected {source.download_sha256}, found {actual_digest}.",
            )
        )
        return tuple(issues)

    if source.transport == "zip":
        issues.extend(_verify_zip(path, source))
    elif prefix != _XLS_MAGIC:
        issues.append(_issue(source, f"File type mismatch for {path.name}: expected XLS workbook."))
    return tuple(issues)


def _verify_source(cache_dir: Path, source: SourceRecord) -> tuple[CacheIssue, ...]:
    return verify_source_file(cache_dir / source.cache_filename, source)


def verify_cache(manifest: DataSourceManifest, cache_dir: Path) -> CacheVerification:
    """Verify all pinned sources without downloading or modifying the cache."""
    issues = tuple(
        issue for source in manifest.sources for issue in _verify_source(cache_dir, source)
    )
    return CacheVerification(checked_sources=len(manifest.sources), issues=issues)
