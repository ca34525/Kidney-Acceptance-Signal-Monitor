"""Typed loading and validation for project configuration manifests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlparse

import yaml

Transport = Literal["zip", "xls"]

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    """Raised when a source manifest violates its contract."""


@dataclass(frozen=True)
class SourceRecord:
    """One immutable source release from the manifest."""

    release_code: str
    cohort_year: int
    transport: Transport
    url: str
    download_bytes: int
    download_sha256: str
    member_path: str | None = None
    member_bytes: int | None = None
    member_sha256: str | None = None

    @property
    def cache_filename(self) -> str:
        """Return the required local filename derived from the pinned URL."""
        return Path(urlparse(self.url).path).name


@dataclass(frozen=True)
class DataSourceManifest:
    """Validated collection of immutable source releases."""

    schema_version: int
    sources: tuple[SourceRecord, ...]


def _mapping(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ManifestError(f"{context} must be a mapping with string keys.")
    return cast(dict[str, object], value)


def _required_string(values: dict[str, object], key: str, context: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{context}.{key} must be a non-empty string.")
    return value


def _optional_string(values: dict[str, object], key: str, context: str) -> str | None:
    value = values.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{context}.{key} must be null or a non-empty string.")
    return value


def _required_integer(values: dict[str, object], key: str, context: str) -> int:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestError(f"{context}.{key} must be an integer.")
    return value


def _optional_integer(values: dict[str, object], key: str, context: str) -> int | None:
    value = values.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestError(f"{context}.{key} must be null or an integer.")
    return value


def _validate_sha256(value: str, context: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ManifestError(f"{context} must be a lowercase 64-character SHA-256 digest.")


def _parse_source(value: object, index: int) -> SourceRecord:
    context = f"sources[{index}]"
    values = _mapping(value, context)
    release_code = _required_string(values, "release_code", context)
    cohort_year = _required_integer(values, "cohort_year", context)
    raw_transport = _required_string(values, "transport", context)
    if raw_transport not in {"zip", "xls"}:
        raise ManifestError(f"{context}.transport must be 'zip' or 'xls'.")
    transport = cast(Transport, raw_transport)
    url = _required_string(values, "url", context)
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or not parsed_url.netloc or not Path(parsed_url.path).name:
        raise ManifestError(f"{context}.url must be an HTTPS file URL.")
    download_bytes = _required_integer(values, "download_bytes", context)
    if download_bytes <= 0:
        raise ManifestError(f"{context}.download_bytes must be positive.")
    download_sha256 = _required_string(values, "download_sha256", context)
    _validate_sha256(download_sha256, f"{context}.download_sha256")
    member_path = _optional_string(values, "member_path", context)
    member_bytes = _optional_integer(values, "member_bytes", context)
    member_sha256 = _optional_string(values, "member_sha256", context)

    if transport == "zip":
        if member_path is None:
            raise ManifestError(f"{context}.member_path is required for a ZIP source.")
        if member_bytes is None or member_bytes <= 0:
            raise ManifestError(f"{context}.member_bytes must be positive for a ZIP source.")
        if member_sha256 is None:
            raise ManifestError(f"{context}.member_sha256 is required for a ZIP source.")
        _validate_sha256(member_sha256, f"{context}.member_sha256")
    elif any(value is not None for value in (member_path, member_bytes, member_sha256)):
        raise ManifestError(f"{context} must not define archive-member fields for an XLS source.")

    expected_suffix = f".{transport}"
    if not Path(parsed_url.path).name.lower().endswith(expected_suffix):
        raise ManifestError(f"{context}.url must end in {expected_suffix}.")

    return SourceRecord(
        release_code=release_code,
        cohort_year=cohort_year,
        transport=transport,
        url=url,
        download_bytes=download_bytes,
        download_sha256=download_sha256,
        member_path=member_path,
        member_bytes=member_bytes,
        member_sha256=member_sha256,
    )


def _reject_duplicate_sources(sources: tuple[SourceRecord, ...]) -> None:
    cohort_years: set[int] = set()
    release_codes: set[str] = set()
    urls: set[str] = set()
    for source in sources:
        if source.cohort_year in cohort_years:
            raise ManifestError(f"Duplicate cohort_year {source.cohort_year}.")
        if source.release_code in release_codes:
            raise ManifestError(f"Duplicate release_code {source.release_code!r}.")
        if source.url in urls:
            raise ManifestError(f"Duplicate source URL {source.url!r}.")
        cohort_years.add(source.cohort_year)
        release_codes.add(source.release_code)
        urls.add(source.url)


def load_data_source_manifest(path: Path) -> DataSourceManifest:
    """Load and validate the immutable-source portion of a YAML manifest."""
    raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    values = _mapping(raw, "Manifest root")
    schema_version = _required_integer(values, "schema_version", "Manifest root")
    if schema_version != 2:
        raise ManifestError(f"Unsupported manifest schema_version {schema_version}; expected 2.")
    raw_sources = values.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ManifestError("Manifest root.sources must be a non-empty list.")

    sources = tuple(_parse_source(value, index) for index, value in enumerate(raw_sources))
    _reject_duplicate_sources(sources)
    return DataSourceManifest(schema_version=schema_version, sources=sources)
