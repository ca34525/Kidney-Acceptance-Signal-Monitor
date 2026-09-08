"""Build one isolated receipt study and verify complete research output before use."""

from __future__ import annotations

import json
import math
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import asdict, fields
from datetime import UTC, date, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from kasm.config import load_data_source_manifest
from kasm.patient_journey.artifacts import current_patient_journey_build_context
from kasm.patient_journey.receipt_accounting import (
    DERIVED_LABEL,
    RECEIPT_FIELDS,
    parse_receipt_values,
)
from kasm.patient_journey.receipt_config import (
    ANALYSIS_ID,
    DEFAULT_CONFIG,
    OUTPUT_ROOT,
    SOURCE_CONFIG,
    ReceiptConfig,
    ReceiptError,
    load_receipt_config,
    validate_receipt_destination,
)
from kasm.patient_journey.receipt_modeling import (
    ReceiptEvaluation,
    ReceiptPrediction,
    evaluate_receipt,
    receipt_continuation_gate,
    summarize_receipt,
)
from kasm.patient_journey.receipt_panel import ReceiptPanel, build_receipt_panel
from kasm.patient_journey.receipt_sources import (
    FIXED_FOLDS,
    FIXED_PAIRS,
    FIXED_RELEASES,
    ReceiptSources,
    load_receipt_sources,
)

_SPEC = Path("docs/specs/deceased-donor-receipt-0023.md")
_PAYLOAD_NAMES = frozenset(
    {
        "panel.parquet",
        "predictions.parquet",
        "source_accounting.parquet",
        "evaluation.json",
        "qa.json",
        "report.md",
    }
)
_MODEL_LABELS = {
    "persistence": "Latest earlier receipt percentage",
    "historical_mean": "Mean earlier receipt percentage",
    "history": "Ridge: receipt history",
    "history_access": "Ridge: history and access",
    "history_access_acceptance": "Ridge: history, access and acceptance",
}
_MAX_PAYLOAD_BYTES = 32 * 1024 * 1024
_MAX_CONTROL_BYTES = 2 * 1024 * 1024
_MAX_TABLE_ROWS = 100_000
_HASH = re.compile(r"[0-9a-f]{64}")
_PROGRAM = re.compile(r"[A-Z0-9]{4}:[A-Za-z0-9]+")


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptError("Receipt control document contains duplicate keys.")
        result[key] = value
    return result


def _read_json(content: bytes) -> dict[str, object]:
    try:
        value: object = json.loads(content, object_pairs_hook=_object)
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            raise ReceiptError("Receipt control document must be an object.")
        return cast(dict[str, object], value)
    except ReceiptError:
        raise
    except (UnicodeError, ValueError) as exc:
        raise ReceiptError("Cannot read complete receipt JSON evidence.") from exc


def _read_snapshot(path: Path, limit: int) -> bytes:
    """Read one bounded regular file and reject replacement while its handle is open."""
    try:
        if path.is_symlink() or path.is_junction():
            raise ReceiptError("Receipt file contains filesystem redirection.")
        before = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= limit:
            raise ReceiptError("Receipt file size or regular-file boundary is invalid.")
        descriptor = os.open(
            path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                raise ReceiptError("Receipt file changed before reading.")
            content = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
        current = path.stat(follow_symlinks=False)
        if (
            path.is_symlink()
            or path.is_junction()
            or len(content) != before.st_size
            or len(content) > limit
            or _file_identity(before) != _file_identity(after)
            or _file_identity(before) != _file_identity(current)
        ):
            raise ReceiptError("Receipt file changed during reading or exceeded its size bound.")
        return content
    except OSError as exc:
        raise ReceiptError(f"Cannot read complete receipt evidence: {path.name}.") from exc


def _file_identity(value: os.stat_result) -> tuple[int, ...]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def publish_receipt_payload(
    repository_root: Path, run_id: str, files: Mapping[str, bytes], provenance: Mapping[str, object]
) -> Path:
    """Publish verified bytes once, with completion appearing only after all payload files."""
    destination = validate_receipt_destination(
        OUTPUT_ROOT / run_id, repository_root=repository_root
    )
    if not set(files).issubset(_PAYLOAD_NAMES):
        raise ReceiptError("Receipt payload filename is outside the fixed allowlist.")
    if set(files) != _PAYLOAD_NAMES:
        raise ReceiptError("Receipt payload requires the complete six-file inventory.")
    if any(
        not isinstance(value, bytes) or not 0 < len(value) <= _MAX_PAYLOAD_BYTES
        for value in files.values()
    ):
        raise ReceiptError("Receipt payload bytes exceed the fixed size boundary.")
    if destination.exists():
        raise ReceiptError("Receipt run already exists; completed evidence cannot be overwritten.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "analysis_id": ANALYSIS_ID,
        "run_id": run_id,
        "provenance": dict(provenance),
        "files": {
            name: {"sha256": sha256(content).hexdigest(), "bytes": len(content)}
            for name, content in files.items()
        },
    }
    manifest_bytes = _json_bytes(manifest)
    if len(manifest_bytes) > _MAX_CONTROL_BYTES:
        raise ReceiptError("Receipt manifest exceeds its size bound.")
    try:
        # Exclusive creation reserves this run, including against another writer.
        destination.mkdir()
    except FileExistsError as exc:
        raise ReceiptError(
            "Receipt run already exists; concurrent writers cannot overwrite it."
        ) from exc
    try:
        for name, content in files.items():
            validate_receipt_destination(OUTPUT_ROOT / run_id, repository_root=repository_root)
            with (destination / name).open("xb") as stream:
                stream.write(content)
        with (destination / "manifest.json").open("xb") as stream:
            stream.write(manifest_bytes)
        validate_receipt_destination(OUTPUT_ROOT / run_id, repository_root=repository_root)
        with (destination / "complete.json").open("xb") as stream:
            stream.write(
                _json_bytes(
                    {"complete": True, "manifest_sha256": sha256(manifest_bytes).hexdigest()}
                )
            )
    except OSError as exc:
        raise ReceiptError(f"Cannot publish complete receipt run: {exc}") from exc
    verify_receipt_payload(repository_root, destination)
    return destination


def _verified_snapshots(
    repository_root: Path, path: Path
) -> tuple[dict[str, object], dict[str, bytes]]:
    root = repository_root.resolve()
    candidate = path if path.is_absolute() else root / path
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ReceiptError("Receipt output is outside the repository.") from exc
    directory = validate_receipt_destination(relative, repository_root=root)
    marker = _read_json(_read_snapshot(directory / "complete.json", _MAX_CONTROL_BYTES))
    if set(marker) != {"complete", "manifest_sha256"} or marker.get("complete") is not True:
        raise ReceiptError("Receipt run is not complete.")
    manifest_bytes = _read_snapshot(directory / "manifest.json", _MAX_CONTROL_BYTES)
    if sha256(manifest_bytes).hexdigest() != marker.get("manifest_sha256"):
        raise ReceiptError("Receipt manifest fingerprint changed.")
    manifest = _read_json(manifest_bytes)
    if manifest.get("analysis_id") != ANALYSIS_ID or manifest.get("run_id") != directory.name:
        raise ReceiptError("Receipt manifest identifies another study or run.")
    inventory = manifest.get("files")
    if not isinstance(inventory, dict) or set(inventory) != _PAYLOAD_NAMES:
        raise ReceiptError("Receipt payload inventory is invalid.")
    if {file.name for file in directory.iterdir()} != {
        *inventory,
        "manifest.json",
        "complete.json",
    }:
        raise ReceiptError("Receipt payload inventory has missing or unexpected files.")
    snapshots: dict[str, bytes] = {}
    for name, expected in inventory.items():
        if (
            not isinstance(expected, dict)
            or set(expected) != {"bytes", "sha256"}
            or type(expected.get("bytes")) is not int
            or not isinstance(expected.get("sha256"), str)
            or _HASH.fullmatch(expected["sha256"]) is None
        ):
            raise ReceiptError("Receipt payload fingerprint is malformed.")
        content = _read_snapshot(directory / name, _MAX_PAYLOAD_BYTES)
        if len(content) != expected.get("bytes") or sha256(content).hexdigest() != expected.get(
            "sha256"
        ):
            raise ReceiptError(f"Receipt payload fingerprint changed: {name}.")
        snapshots[name] = content
    validate_receipt_destination(relative, repository_root=root)
    return manifest, snapshots


def verify_receipt_payload(repository_root: Path, path: Path) -> dict[str, object]:
    """Reject partial, redirected or changed research output before parsing payloads."""
    return _verified_snapshots(repository_root, path)[0]


def _input_identity(root: Path) -> dict[str, str]:
    inputs = [
        DEFAULT_CONFIG,
        SOURCE_CONFIG,
        _SPEC,
        Path("configs/data_sources.yaml"),
        Path("uv.lock"),
    ]
    inputs.extend(path.relative_to(root) for path in sorted((root / "src/kasm").rglob("*.py")))
    try:
        for path in inputs:
            current = root / path
            if any(
                parent.is_symlink() or parent.is_junction()
                for parent in (current, *current.parents)
                if parent.is_relative_to(root) and parent != root
            ):
                raise ReceiptError("Receipt input cannot traverse a filesystem link.")
        return {
            path.as_posix(): sha256(_read_snapshot(root / path, _MAX_PAYLOAD_BYTES)).hexdigest()
            for path in inputs
        }
    except OSError as exc:
        raise ReceiptError("Cannot fingerprint receipt-study build inputs.") from exc


def _parquet(rows: list[dict[str, object]]) -> bytes:
    stream = BytesIO()
    pq.write_table(pa.Table.from_pylist(rows), stream, compression="zstd")
    return stream.getvalue()


def _accounting_rows(sources: ReceiptSources) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for release in sources.releases:
        for outcome in release.outcomes:
            values = outcome.values
            row: dict[str, object] = {
                "release_code": release.source.release_code,
                "program_key": outcome.program_key,
                "target_n": values.target_n,
                "derived_receipt_percent": values.derived_receipt_percent,
                "derived_label": values.derived_label,
            }
            for component in (
                *values.deceased_components,
                *values.living_components,
                *values.other_components,
            ):
                row[component.field] = component.percent
            row["published_all_donor_percent"] = values.published_all_donor_percent
            row["published_status_total"] = values.published_status_total
            for name, check in values.reconciliation.items():
                row[f"{name}_status"] = check["status"]
            rows.append(row)
    return rows


def render_receipt_report(evaluation: ReceiptEvaluation, panel: ReceiptPanel) -> str:
    """Explain the fixed comparison in ordinary language and percentage-point units."""
    decision = "met" if evaluation.continuation.passed else "did not meet"
    lines = [
        "# Earlier acceptance and reported deceased-donor transplant receipt",
        "",
        f"Adding earlier acceptance information **{decision} the prespecified continuation rule**.",
        "",
        "This exploratory study predicts the percentage of a kidney program's original "
        "listing group recorded as removed for deceased-donor transplant within 18 months. "
        "The target is derived from five published statuses, including unknown "
        "post-transplant health status. It is not survival among recipients or a "
        "patient-level probability.",
        "",
        "Each row represents one program and a July-June listing group. All models use "
        "identical evaluation rows. The two evaluation groups are July 2022-June 2023 and "
        "July 2023-June 2024; predictions originate at the July 2022 and July 2023 report "
        "releases. Both fits use the July 2019-June 2020 listing group, whose outcome was "
        "public in July 2022. Earlier reports supply only information actually public by "
        "each origin.",
        "",
        "Average errors below give each evaluation period equal weight. A prediction of 40% "
        "against a derived 30% outcome has a 10-percentage-point absolute error. Signed "
        "error is prediction minus observed; positive means too high on average.",
        "",
        "| Forecast | Average absolute error (points) | Signed error (points) | "
        "Volume-weighted error (points) |",
        "|---|---:|---:|---:|",
    ]
    for name, summary in evaluation.summaries.items():
        lines.append(
            f"| {_MODEL_LABELS[name]} | "
            f"{summary.mean_absolute_error_percentage_points:.3f} | "
            f"{summary.mean_signed_error_percentage_points:.3f} | "
            f"{summary.volume_weighted_mae_percentage_points:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Each evaluation period",
            "",
            "| Model | Origin / outcome report | Programs | Absolute error (points) | Signed "
            "error (points) |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for name, summary in evaluation.summaries.items():
        for origin in summary.origins:
            lines.append(
                f"| {_MODEL_LABELS[name]} | "
                f"{origin.feature_release_code} / {origin.target_release_code} | "
                f"{origin.n} | "
                f"{origin.mean_absolute_error_percentage_points:.3f} | "
                f"{origin.mean_signed_error_percentage_points:.3f} |"
            )
    lines.extend(
        [
            "",
            "## Fixed paired comparisons",
            "",
            "The difference is added-input model minus comparator average error, in "
            "percentage points. Negative favors the added-input model. These descriptive 95% "
            "intervals resample whole programs, keeping repeated cohorts together; they do "
            "not measure accuracy in a new period.",
            "",
            "| Added-input model | Comparator | Difference | Descriptive interval |",
            "|---|---|---:|---:|",
        ]
    )
    for contrast in evaluation.contrasts:
        interval = contrast.interval
        lines.append(
            f"| {_MODEL_LABELS[contrast.challenger]} | "
            f"{_MODEL_LABELS[contrast.comparator]} | "
            f"{interval.point_estimate:.3f} | "
            f"[{interval.lower:.3f}, {interval.upper:.3f}] |"
        )
    lines.extend(
        [
            "",
            "## Prespecified population sensitivities",
            "",
            "These rescore the same fixed predictions among larger listing groups, without "
            "refitting.",
            "",
            "| Minimum listed candidates | Forecast | Program-cohort rows | Absolute error "
            "(points) |",
            "|---|---|---:|---:|",
        ]
    )
    for minimum, summaries in evaluation.sensitivities.items():
        for name, summary in summaries.items():
            lines.append(
                f"| {minimum} | "
                f"{_MODEL_LABELS[name]} | "
                f"{summary.n} | "
                f"{summary.mean_absolute_error_percentage_points:.3f} |"
            )
    lines.extend(
        [
            "",
            "## Decision and limits",
            "",
            "Continuation requires at least 0.5 points and 5% improvement versus both simple "
            "forecasts and history-plus-access, improvement in both periods, and the fixed "
            "absolute-bias limits. These are project-use rules, not clinical-benefit "
            "thresholds.",
            "",
        ]
    )
    if evaluation.continuation.reasons:
        lines.extend(f"- {reason}" for reason in evaluation.continuation.reasons)
    lines.extend(
        [
            "",
            "Seven releases have independent report evidence. The 2018 and 2020 releases are "
            "excluded because their source-bound date evidence could not be recovered. Six "
            "historical reports are bound through saved cached PDF text; the newest has a "
            "verified PDF. Historical PDF-byte fingerprints are not claimed. This "
            "restriction leaves both evaluation origins using the same earlier training "
            "cohort.",
            "",
            "The 18-month outcome uses a conservative December 31 follow-up bound for "
            "temporal checks, not an invented source censor date. Month-only publication "
            "values retain their precision. Missing future reports and components are "
            "unknown outcomes, not zero receipt. Larger listing groups receive more weight "
            "only in the secondary summary; candidates may be listed at more than one "
            "program.",
            "",
            "Original V1/V2 and both completed follow-ups remain unchanged. These "
            "already-inspected historical sources provide exploratory evidence, not fresh or "
            "prospective validation. No model is promoted. No causal, patient-level, "
            "clinical or regulatory conclusion follows from the comparison.",
            "",
            "## Population accounting",
            "",
            "Counts describe programs at each origin before checking their later outcomes. A "
            "program can have more than one exclusion reason. Full identifiers and exact "
            "lists remain in `qa.json`.",
            "",
            "| Earlier / later release | Origin programs | Eligible rows | Missing future "
            "report | New later programs | Exclusion reasons (counts) |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    pairs = cast(dict[str, dict[str, object]], panel.qa["pairs"])
    for pair, population in pairs.items():
        reasons = cast(dict[str, int], population["exclusion_reasons"])
        description = (
            "; ".join(
                f"{name.replace('_', ' ')}: {count}" for name, count in sorted(reasons.items())
            )
            or "None"
        )
        lines.append(
            f"| {pair} | {population['origin_programs']} | {population['eligible_rows']} | "
            f"{len(cast(list[str], population['missing_future_programs']))} | "
            f"{len(cast(list[str], population['target_only_programs']))} | {description} |"
        )
    lines.append("")
    return "\n".join(lines)


def prepare_receipt_study(
    repository_root: Path,
) -> tuple[ReceiptConfig, ReceiptSources, ReceiptPanel]:
    """Verify sources and construct the isolated panel without fitting or scoring."""
    root = repository_root.resolve()
    config = load_receipt_config(root / DEFAULT_CONFIG)
    manifest = load_data_source_manifest(root / "configs/data_sources.yaml")
    sources = load_receipt_sources(
        root / SOURCE_CONFIG,
        manifest=manifest,
        repository_root=root,
        cache_dir=root / "data/raw/srtr",
    )
    return config, sources, build_receipt_panel(sources, config)


def build_receipt_study(repository_root: Path) -> Path:
    """Complete the fixed comparisons once after every source and time gate passes."""
    root = repository_root.resolve()
    identity = _input_identity(root)
    run_id = sha256(_json_bytes(identity)).hexdigest()
    destination = validate_receipt_destination(OUTPUT_ROOT / run_id, repository_root=root)
    if destination.exists():
        raise ReceiptError(
            "Receipt run already exists; use its verified result instead of refitting."
        )
    config, sources, panel = prepare_receipt_study(root)
    evaluation = evaluate_receipt(panel.rows, config, sources.folds)
    context = current_patient_journey_build_context(root)
    provenance: dict[str, object] = {
        **asdict(context),
        "build_timestamp_utc": context.build_timestamp_utc.isoformat(),
        "analysis_id": ANALYSIS_ID,
        "input_sha256": identity,
        "config": asdict(config),
        "folds": sources.folds,
        "sources": [
            {
                "release_code": release.source.release_code,
                "source_url": release.source.url,
                "source_sha256": release.source.download_sha256,
                "workbook_sha256": release.source.member_sha256 or release.source.download_sha256,
                "published_value": release.source.published_value,
                "published_precision": release.source.published_precision,
                "listing_start": str(release.periods.listing_start),
                "listing_end": str(release.periods.listing_end),
                "outcome_follow_up_bound": str(release.periods.outcome_follow_up_bound),
            }
            for release in sources.releases
        ],
        "source_evidence_sha256": sources.config_sha256,
        "canonical_committed_build": False,
        "feature_schema": dict(config.feature_groups),
        "model_parameters": {
            "alpha": config.alpha,
            "solver": config.solver,
            "tolerance": config.tolerance,
            "max_iterations": config.max_iterations,
        },
        "dependency_lock_sha256": identity["uv.lock"],
    }
    result = asdict(evaluation)
    predictions = result.pop("predictions")
    files = {
        "panel.parquet": _parquet(list(panel.rows)),
        "predictions.parquet": _parquet(predictions),
        "source_accounting.parquet": _parquet(_accounting_rows(sources)),
        "evaluation.json": _json_bytes(result),
        "qa.json": _json_bytes(panel.qa),
        "report.md": render_receipt_report(evaluation, panel).encode("utf-8"),
    }
    if identity != _input_identity(root):
        raise ReceiptError("Study inputs changed during the build; no result was published.")
    path = publish_receipt_payload(root, run_id, files, provenance)
    load_receipt_study(root, path)
    return path


def load_receipt_study(repository_root: Path, path: Path) -> dict[str, object]:
    """Read only a complete checked bundle with the fixed study and model identities."""
    manifest, snapshots = _verified_snapshots(repository_root, path)
    try:
        provenance = _validate_provenance(manifest)
        evaluation = _read_json(snapshots["evaluation.json"])
        tables = {
            name: _table_rows(snapshots[name])
            for name in ("panel.parquet", "predictions.parquet", "source_accounting.parquet")
        }
        _validate_tables(tables, provenance)
        _validate_evaluation(evaluation, tables["predictions.parquet"], tables["panel.parquet"])
        qa = _read_json(snapshots["qa.json"])
        if qa.get("source_config_sha256") != provenance["source_evidence_sha256"] or set(
            _mapping(qa.get("pairs"))
        ) != {f"{a}->{b}" for a, b in FIXED_PAIRS}:
            raise ReceiptError("Receipt QA source identity or pair inventory disagrees.")
    except ReceiptError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError, pa.ArrowException) as exc:
        raise ReceiptError("Receipt study schema or scientific metadata is malformed.") from exc
    return {"manifest": manifest, "evaluation": evaluation}


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ReceiptError("Receipt provenance or schema requires named fields.")
    return value


def _same(actual: object, expected: object, context: str) -> None:
    if _json_bytes(actual) != _json_bytes(expected):
        raise ReceiptError(f"Receipt {context} disagrees with the fixed evidence.")


def _validate_provenance(manifest: dict[str, object]) -> dict[str, Any]:
    provenance = _mapping(manifest.get("provenance"))
    config = ReceiptConfig()
    _same(provenance.get("analysis_id"), ANALYSIS_ID, "provenance study")
    _same(provenance.get("config"), asdict(config), "provenance settings")
    _same(provenance.get("feature_schema"), dict(config.feature_groups), "feature schema")
    _same(provenance.get("folds"), FIXED_FOLDS, "fold provenance")
    _same(
        provenance.get("model_parameters"),
        {
            "alpha": config.alpha,
            "solver": config.solver,
            "tolerance": config.tolerance,
            "max_iterations": config.max_iterations,
        },
        "model provenance",
    )
    identity = _mapping(provenance.get("input_sha256"))
    required = {
        DEFAULT_CONFIG.as_posix(),
        SOURCE_CONFIG.as_posix(),
        _SPEC.as_posix(),
        "configs/data_sources.yaml",
        "uv.lock",
    }
    if not required.issubset(identity) or not any(key.startswith("src/kasm/") for key in identity):
        raise ReceiptError("Receipt provenance lacks configuration, lock or code identity.")
    for key, value in identity.items():
        path = Path(key)
        if (
            path.is_absolute()
            or path.drive
            or ".." in path.parts
            or not isinstance(value, str)
            or _HASH.fullmatch(value) is None
        ):
            raise ReceiptError("Receipt input provenance identity is invalid.")
    _same(manifest.get("run_id"), sha256(_json_bytes(identity)).hexdigest(), "run provenance")
    _same(provenance.get("dependency_lock_sha256"), identity["uv.lock"], "dependency lock")
    _same(
        provenance.get("source_evidence_sha256"),
        identity[SOURCE_CONFIG.as_posix()],
        "source provenance",
    )
    timestamp = datetime.fromisoformat(provenance["build_timestamp_utc"])
    if timestamp.tzinfo is None or timestamp.utcoffset() != UTC.utcoffset(timestamp):
        raise ReceiptError("Receipt build timestamp must be timezone-aware UTC.")
    if (
        not isinstance(provenance.get("git_commit_sha"), str)
        or re.fullmatch(r"[0-9a-f]{40,64}", provenance["git_commit_sha"]) is None
    ):
        raise ReceiptError("Receipt Git provenance is invalid.")
    if (
        type(provenance.get("git_worktree_dirty")) is not bool
        or provenance.get("canonical_committed_build") is not False
        or not isinstance(provenance.get("python_version"), str)
        or not provenance["python_version"].startswith("3.12.")
    ):
        raise ReceiptError("Receipt build provenance is invalid.")
    sources = provenance.get("sources")
    if not isinstance(sources, list) or [item.get("release_code") for item in sources] != list(
        FIXED_RELEASES
    ):
        raise ReceiptError("Receipt source provenance lacks the fixed release inventory.")
    for item in sources:
        _validate_source_metadata(_mapping(item))
    return provenance


def _validate_source_metadata(source: dict[str, Any]) -> None:
    year = 2000 + int(source["release_code"][:2])
    for name, expected in (
        ("listing_start", date(year - 3, 7, 1)),
        ("listing_end", date(year - 2, 6, 30)),
        ("outcome_follow_up_bound", date(year - 1, 12, 31)),
    ):
        _same(source.get(name), expected.isoformat(), "source cohort")
    for name in ("source_sha256", "workbook_sha256"):
        if not isinstance(source.get(name), str) or _HASH.fullmatch(source[name]) is None:
            raise ReceiptError("Receipt source fingerprint is invalid.")
    url = urlparse(source["source_url"])
    if url.scheme != "https" or url.hostname != "srtr.hrsa.gov" or url.username or url.password:
        raise ReceiptError("Receipt source URL provenance is invalid.")
    value, precision = source["published_value"], source["published_precision"]
    if precision == "month":
        if value != f"{year}-07":
            raise ReceiptError("Receipt source publication month disagrees.")
    elif (
        precision != "day"
        or date.fromisoformat(value).year != year
        or not value.startswith(f"{year}-07-")
    ):
        raise ReceiptError("Receipt source publication precision disagrees.")


def _table_rows(content: bytes) -> list[dict[str, Any]]:
    parquet = pq.ParquetFile(
        BytesIO(content),
        thrift_string_size_limit=_MAX_CONTROL_BYTES,
        thrift_container_size_limit=_MAX_CONTROL_BYTES,
    )
    if not 0 < parquet.metadata.num_rows <= _MAX_TABLE_ROWS:
        raise ReceiptError("Receipt table row-count schema is invalid.")
    if (
        sum(
            parquet.metadata.row_group(i).total_byte_size
            for i in range(parquet.metadata.num_row_groups)
        )
        > _MAX_PAYLOAD_BYTES
    ):
        raise ReceiptError("Receipt table exceeds the expanded size bound.")
    table = parquet.read()
    if (
        len(table.column_names) != len(set(table.column_names))
        or "program_key" not in table.column_names
    ):
        raise ReceiptError("Receipt table lacks a unique program schema.")
    rows: list[dict[str, Any]] = table.to_pylist()
    if any(
        not isinstance(row["program_key"], str) or _PROGRAM.fullmatch(row["program_key"]) is None
        for row in rows
    ):
        raise ReceiptError("Receipt table program identity schema is invalid.")
    return rows


def _validate_tables(tables: dict[str, list[dict[str, Any]]], provenance: dict[str, Any]) -> None:
    sources = {source["release_code"]: source for source in provenance["sources"]}
    seen: set[tuple[str, str, str]] = set()
    for row in tables["panel.parquet"]:
        feature, target = row["feature_release_code"], row["target_release_code"]
        key = (row["program_key"], feature, target)
        if key in seen or (feature, target) not in FIXED_PAIRS:
            raise ReceiptError("Receipt panel has duplicate or unknown pair schema.")
        seen.add(key)
        _same(row["target_label"], DERIVED_LABEL, "derived target label")
        _same(row["target_listing_start"], sources[target]["listing_start"], "panel source cohort")
        _same(row["target_listing_end"], sources[target]["listing_end"], "panel source cohort")
        _same(
            row["target_follow_up_bound"],
            sources[target]["outcome_follow_up_bound"],
            "panel follow-up",
        )
        _same(row["feature_source_sha256"], sources[feature]["source_sha256"], "panel source hash")
        _same(row["target_source_sha256"], sources[target]["source_sha256"], "panel source hash")
        if type(row["primary_analytic_eligible"]) is not bool or not isinstance(
            row["eligibility_reasons"], list
        ):
            raise ReceiptError("Receipt panel eligibility schema is invalid.")
        if row["primary_analytic_eligible"] != (not row["eligibility_reasons"]):
            raise ReceiptError("Receipt panel eligibility reasons disagree.")
    accounting: set[tuple[str, str]] = set()
    reported: dict[tuple[str, str], tuple[object, object, object, object]] = {}
    for row in tables["source_accounting.parquet"]:
        if not (set(RECEIPT_FIELDS) - {"SAL_N_C", "SAL_TOTTX_C18", "SAL_TOTAL_C18"}).issubset(row):
            raise ReceiptError("Receipt source accounting component schema is incomplete.")
        key2 = (row["program_key"], row["release_code"])
        if key2 in accounting or row["release_code"] not in sources:
            raise ReceiptError("Receipt accounting has duplicate or unknown source rows.")
        accounting.add(key2)
        _same(row["derived_label"], DERIVED_LABEL, "derived accounting label")
        values = {field: row.get(field) for field in RECEIPT_FIELDS}
        values.update(
            SAL_N_C=row["target_n"],
            SAL_TOTTX_C18=row["published_all_donor_percent"],
            SAL_TOTAL_C18=row["published_status_total"],
        )
        parsed = parse_receipt_values(values)
        reported[key2] = (
            parsed.target_n,
            parsed.derived_receipt_percent,
            parsed.target_proportion,
            parsed.target_logit,
        )
        _same(
            row["derived_receipt_percent"],
            parsed.derived_receipt_percent,
            "derived accounting percentage",
        )
    for row in tables["panel.parquet"]:
        target_value = reported.get(
            (row["program_key"], row["target_release_code"]), (None, None, None, None)
        )
        _same(
            (
                row["target_n"],
                row["derived_receipt_percent"],
                row["target_proportion"],
                row["target_logit"],
            ),
            target_value,
            "panel and source accounting",
        )


def _validate_evaluation(
    evaluation: dict[str, object], rows: list[dict[str, Any]], panel: list[dict[str, Any]]
) -> None:
    predictions: list[ReceiptPrediction] = []
    expected_fields = {field.name for field in fields(ReceiptPrediction)}
    for row in rows:
        if set(row) != expected_fields:
            raise ReceiptError("Receipt prediction schema disagrees.")
        row["training_pairs"] = tuple(tuple(pair) for pair in row["training_pairs"])
        predictions.append(ReceiptPrediction(**row))
    config = ReceiptConfig()
    groups = {name: [p for p in predictions if p.model == name] for name in _MODEL_LABELS}
    summaries = {name: asdict(summarize_receipt(items)) for name, items in groups.items()}
    if {prediction.model for prediction in predictions} != set(_MODEL_LABELS):
        raise ReceiptError("Receipt prediction model inventory disagrees.")
    _same(evaluation.get("summaries"), summaries, "prediction summaries")
    _same(
        evaluation.get("continuation"),
        asdict(receipt_continuation_gate(predictions, config)),
        "continuation decision",
    )
    evaluation_pairs = {pair for pair, _ in FIXED_FOLDS}
    targets = {
        (row["program_key"], row["feature_release_code"], row["target_release_code"]): row
        for row in panel
        if row["primary_analytic_eligible"]
        and (row["feature_release_code"], row["target_release_code"]) in evaluation_pairs
    }
    for name, items in groups.items():
        if {(p.program_key, p.feature_release_code, p.target_release_code) for p in items} != set(
            targets
        ):
            raise ReceiptError("Receipt predictions must match eligible program/cohort rows.")
        for prediction in items:
            target = targets[
                (
                    prediction.program_key,
                    prediction.feature_release_code,
                    prediction.target_release_code,
                )
            ]
            _same(
                (prediction.target_n, prediction.derived_receipt_percent),
                (target["target_n"], target["derived_receipt_percent"]),
                "prediction target",
            )
            training = (
                dict(FIXED_FOLDS)[(prediction.feature_release_code, prediction.target_release_code)]
                if name not in config.baselines
                else ()
            )
            _same(prediction.training_pairs, training, "prediction training provenance")
    _same(
        evaluation.get("sensitivities"),
        {
            str(n): {
                name: asdict(summarize_receipt([p for p in items if p.target_n >= n]))
                for name, items in groups.items()
            }
            for n in config.sensitivity_min_target_n
        },
        "sensitivity summaries",
    )
    _validate_fit_parameters(evaluation.get("fit_parameters"), config)
    _validate_contrasts(evaluation.get("contrasts"), summaries, config)


def _validate_contrasts(value: object, summaries: dict[str, Any], config: ReceiptConfig) -> None:
    if not isinstance(value, list) or len(value) != len(config.contrasts):
        raise ReceiptError("Receipt fixed comparison inventory is incomplete.")
    _same(
        [(item["challenger"], item["comparator"]) for item in value],
        config.contrasts,
        "contrast inventory",
    )
    for item in value:
        interval = _mapping(item["interval"])
        point = (
            summaries[item["challenger"]]["mean_absolute_error_percentage_points"]
            - summaries[item["comparator"]]["mean_absolute_error_percentage_points"]
        )
        if not math.isclose(interval["point_estimate"], point, rel_tol=0, abs_tol=1e-10):
            raise ReceiptError("Receipt contrast point disagrees with prediction summaries.")
        if (
            any(
                type(interval.get(name)) not in (int, float) or not math.isfinite(interval[name])
                for name in ("point_estimate", "lower", "upper")
            )
            or interval["lower"] > interval["upper"]
        ):
            raise ReceiptError("Receipt contrast interval bounds are invalid.")
        _same(interval.get("resamples"), config.bootstrap_resamples, "contrast resamples")
        _same(interval.get("seed"), config.bootstrap_seed, "contrast seed")
        attempted, rejected = interval.get("attempted_draws"), interval.get("rejected_draws")
        if (
            type(attempted) is not int
            or type(rejected) is not int
            or rejected < 0
            or attempted - rejected != config.bootstrap_resamples
            or attempted > config.bootstrap_max_attempt_factor * config.bootstrap_resamples
        ):
            raise ReceiptError("Receipt contrast draw accounting is invalid.")


def _validate_fit_parameters(value: object, config: ReceiptConfig) -> None:
    parameters = _mapping(value)
    expected = {
        f"{a}->{b}/{model}" for (a, b), _ in FIXED_FOLDS for model, _ in config.feature_groups
    }
    if set(parameters) != expected:
        raise ReceiptError("Receipt fitted model parameter inventory disagrees.")
    for identity, fit in parameters.items():
        fit = _mapping(fit)
        _same(
            identity,
            f"{fit['feature_release_code']}->{fit['target_release_code']}/{fit['model']}",
            "fitted model identity",
        )
        names = dict(config.feature_groups)[fit["model"]]
        _same(fit["feature_names"], names, "fitted feature schema")
        _same(
            fit["training_pairs"],
            dict(FIXED_FOLDS)[(fit["feature_release_code"], fit["target_release_code"])],
            "fitted training provenance",
        )
        vectors = [
            fit[name]
            for name in ("coefficients", "imputer_statistics", "scaler_mean", "scaler_scale")
        ]
        if (
            any(not isinstance(vector, list) or len(vector) != len(names) for vector in vectors)
            or any(
                type(number) not in (int, float) or not math.isfinite(number)
                for number in [
                    fit["intercept"],
                    *(number for vector in vectors for number in vector),
                ]
            )
            or any(number <= 0 for number in fit["scaler_scale"])
        ):
            raise ReceiptError("Receipt learned model parameters are invalid.")
