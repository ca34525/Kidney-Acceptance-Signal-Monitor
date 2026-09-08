"""Receipt runs are complete, isolated and immutable after publication."""

import json
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from kasm.patient_journey.receipt_artifacts import (
    prepare_receipt_study,
    publish_receipt_payload,
    verify_receipt_payload,
)
from kasm.patient_journey.receipt_config import ReceiptError


def payload():
    return {
        name: b"fixture"
        for name in (
            "panel.parquet",
            "predictions.parquet",
            "source_accounting.parquet",
            "evaluation.json",
            "qa.json",
            "report.md",
        )
    }


def test_incomplete_inventory_cannot_be_published(tmp_path):
    with pytest.raises(ReceiptError, match="inventory|complete"):
        publish_receipt_payload(tmp_path, "e" * 64, {"report.md": b"partial"}, {})


def test_control_symlink_is_rejected_even_when_bytes_match(tmp_path, monkeypatch):
    path = publish_receipt_payload(tmp_path, "f" * 64, payload(), {})
    original = Path.is_symlink
    monkeypatch.setattr(
        Path, "is_symlink", lambda self: self.name == "complete.json" or original(self)
    )
    with pytest.raises(ReceiptError, match="link|redirect"):
        verify_receipt_payload(tmp_path, path)


def test_control_json_rejects_duplicate_keys(tmp_path):
    path = publish_receipt_payload(tmp_path, "1" * 64, payload(), {})
    marker = json.loads((path / "complete.json").read_text())
    (path / "complete.json").write_text(
        '{"complete":false,"complete":true,"manifest_sha256":"' + marker["manifest_sha256"] + '"}'
    )
    with pytest.raises(ReceiptError, match="duplicate"):
        verify_receipt_payload(tmp_path, path)


def test_verified_reads_are_bounded(tmp_path, monkeypatch):
    import kasm.patient_journey.receipt_artifacts as artifacts

    path = publish_receipt_payload(tmp_path, "2" * 64, payload(), {})
    monkeypatch.setattr(artifacts, "_MAX_PAYLOAD_BYTES", 4, raising=False)
    with pytest.raises(ReceiptError, match="size|large|bound"):
        verify_receipt_payload(tmp_path, path)


def test_write_once_and_changed_bytes_are_rejected(tmp_path: Path) -> None:
    files = payload()
    run_id = "a" * 64
    path = publish_receipt_payload(
        tmp_path, run_id, files, {"analysis_id": "kidney_deceased_donor_receipt_0023_v1"}
    )
    assert verify_receipt_payload(tmp_path, path)["run_id"] == run_id
    with pytest.raises(ReceiptError, match="exists"):
        publish_receipt_payload(tmp_path, run_id, files, {})
    (path / "report.md").write_bytes(b"Changed result\n")
    with pytest.raises(ReceiptError, match="fingerprint"):
        verify_receipt_payload(tmp_path, path)


def test_partial_and_unknown_files_fail(tmp_path: Path) -> None:
    path = publish_receipt_payload(tmp_path, "b" * 64, payload(), {})
    (path / "unexpected.txt").write_text("extra")
    with pytest.raises(ReceiptError, match="inventory"):
        verify_receipt_payload(tmp_path, path)
    (path / "complete.json").unlink()
    with pytest.raises(ReceiptError, match="complete"):
        verify_receipt_payload(tmp_path, path)


@pytest.mark.parametrize(
    "name", ["../outside", "nested/report.md", "complete.json", "manifest.json"]
)
def test_payload_cannot_escape_or_replace_control_files(tmp_path: Path, name: str) -> None:
    with pytest.raises(ReceiptError, match="filename"):
        publish_receipt_payload(tmp_path, "c" * 64, {name: b"invalid"}, {})
    assert not (tmp_path / "outside").exists()


def test_changed_manifest_and_false_completion_fail(tmp_path: Path) -> None:
    path = publish_receipt_payload(tmp_path, "d" * 64, payload(), {})
    marker = json.loads((path / "complete.json").read_text())
    marker["complete"] = False
    (path / "complete.json").write_text(json.dumps(marker))
    with pytest.raises(ReceiptError, match="complete"):
        verify_receipt_payload(tmp_path, path)


def test_cli_exposes_source_only_preflight() -> None:
    from kasm.cli import build_parser

    args = build_parser().parse_args(["patient-journey", "receipt-study", "--check-sources"])
    assert args.check_sources is True


@pytest.fixture
def scientific_fixture(monkeypatch):
    from test_receipt_panel import release

    import kasm.patient_journey.receipt_artifacts as artifacts
    from kasm.patient_journey.artifacts import PatientJourneyBuildContext
    from kasm.patient_journey.receipt_accounting import parse_receipt_values
    from kasm.patient_journey.receipt_config import DEFAULT_CONFIG, SOURCE_CONFIG, ReceiptConfig
    from kasm.patient_journey.receipt_modeling import evaluate_receipt
    from kasm.patient_journey.receipt_panel import build_receipt_panel
    from kasm.patient_journey.receipt_sources import (
        FIXED_FOLDS,
        FIXED_PAIRS,
        FIXED_RELEASES,
        ReceiptSources,
    )

    releases = tuple(
        release(code, 2000 + int(code[:2]), ("AAAA:TX1", "AAAA:VA", "MISS:TX1", "NULL:TX1"))
        for code in FIXED_RELEASES
    )
    releases = tuple(
        replace(
            item,
            source=replace(
                item.source, url=f"https://srtr.hrsa.gov/{item.source.release_code}.xls"
            ),
            methodology=replace(
                item.methodology, source_url=f"https://srtr.hrsa.gov/{item.source.release_code}.xls"
            ),
            outcomes=tuple(
                replace(outcome, values=parse_receipt_values({"SAL_N_C": 100}))
                if outcome.program_key == "NULL:TX1"
                else outcome
                for outcome in item.outcomes
                if not (
                    outcome.program_key == "MISS:TX1"
                    and item.source.release_code in {"2505", "2605"}
                )
            ),
        )
        for item in releases
    )
    sources = ReceiptSources(
        releases, FIXED_PAIRS, FIXED_FOLDS, {"1808": "unavailable", "2006": "unavailable"}, "a" * 64
    )
    config = ReceiptConfig()
    panel = build_receipt_panel(sources, config)
    evaluation = evaluate_receipt(panel.rows, config, sources.folds)
    identity = {
        path: "a" * 64
        for path in (
            DEFAULT_CONFIG.as_posix(),
            SOURCE_CONFIG.as_posix(),
            "docs/specs/deceased-donor-receipt-0023.md",
            "configs/data_sources.yaml",
            "uv.lock",
            "src/kasm/__init__.py",
        )
    }
    monkeypatch.setattr(artifacts, "_input_identity", lambda root: identity)
    monkeypatch.setattr(artifacts, "prepare_receipt_study", lambda root: (config, sources, panel))
    monkeypatch.setattr(artifacts, "evaluate_receipt", lambda *args: evaluation)
    monkeypatch.setattr(
        artifacts,
        "current_patient_journey_build_context",
        lambda root: PatientJourneyBuildContext(
            datetime(2026, 9, 8, tzinfo=UTC), "a" * 40, True, "3.12.11"
        ),
    )
    return artifacts, config, sources, panel, evaluation


def test_full_synthetic_build_is_readable_and_does_not_refit(
    tmp_path, scientific_fixture, monkeypatch
):
    artifacts, _, _, _, _ = scientific_fixture
    path = artifacts.build_receipt_study(tmp_path)
    loaded = artifacts.load_receipt_study(tmp_path, path)
    assert loaded["manifest"]["provenance"]["build_timestamp_utc"] == "2026-09-08T00:00:00+00:00"
    import pyarrow.parquet as pq

    rows = pq.read_table(path / "panel.parquet").to_pylist()
    missing = next(
        row
        for row in rows
        if row["program_key"] == "MISS:TX1" and row["target_release_code"] == "2505"
    )
    assert missing["target_n"] is None
    assert missing["derived_receipt_percent"] is None
    assert "missing_future_report" in missing["eligibility_reasons"]
    unknown = next(row for row in rows if row["program_key"] == "NULL:TX1")
    assert unknown["target_n"] == 100
    assert unknown["derived_receipt_percent"] is None
    monkeypatch.setattr(
        artifacts, "evaluate_receipt", lambda *args: pytest.fail("completed study was refitted")
    )
    with pytest.raises(ReceiptError, match="exists"):
        artifacts.build_receipt_study(tmp_path)


def test_report_explains_cohorts_unknowns_and_population_counts(scientific_fixture):
    artifacts, _, _, panel, evaluation = scientific_fixture
    report = artifacts.render_receipt_report(evaluation, panel)
    assert "July 2023-June 2024" in report
    assert "derived" in report
    assert "unknown" in report
    assert "exploratory" in report
    assert "qa.json" in report
    assert "```json" not in report
    assert "Origin programs" in report


def reseal(path, name, content):
    (path / name).write_bytes(content)
    manifest = json.loads((path / "manifest.json").read_text())
    if name != "manifest.json":
        manifest["files"][name] = {"bytes": len(content), "sha256": sha256(content).hexdigest()}
    raw = json.dumps(manifest).encode()
    (path / "manifest.json").write_bytes(raw)
    (path / "complete.json").write_text(
        json.dumps({"complete": True, "manifest_sha256": sha256(raw).hexdigest()})
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("git_commit_sha", "unknown"),
        ("build_timestamp_utc", "2026-09-08"),
        ("dependency_lock_sha256", "b" * 64),
        ("feature_schema", {}),
        ("folds", []),
        ("sources", []),
    ],
)
def test_checksum_valid_bad_provenance_is_rejected(tmp_path, scientific_fixture, field, value):
    artifacts, *_ = scientific_fixture
    path = artifacts.build_receipt_study(tmp_path)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["provenance"][field] = value
    reseal(path, "manifest.json", json.dumps(manifest).encode())
    with pytest.raises(ReceiptError, match="provenance|source|fold|schema|lock|timestamp|Git"):
        artifacts.load_receipt_study(tmp_path, path)


@pytest.mark.parametrize(
    ("name", "field", "value"),
    [
        ("panel.parquet", "target_label", "Published deceased-donor total"),
        ("predictions.parquet", "derived_receipt_percent", 900.0),
        ("source_accounting.parquet", "derived_label", "Published total"),
    ],
)
def test_checksum_valid_wrong_scientific_meaning_is_rejected(
    tmp_path, scientific_fixture, name, field, value
):
    import pyarrow.parquet as pq

    artifacts, *_ = scientific_fixture
    path = artifacts.build_receipt_study(tmp_path)
    rows = pq.read_table(path / name).to_pylist()
    rows[0][field] = value
    reseal(path, name, artifacts._parquet(rows))
    with pytest.raises(
        ReceiptError, match="schema|derived|percentage|label|accounting|numeric bounds"
    ):
        artifacts.load_receipt_study(tmp_path, path)


def test_reported_errors_must_agree_with_stored_predictions(tmp_path, scientific_fixture):
    artifacts, *_ = scientific_fixture
    path = artifacts.build_receipt_study(tmp_path)
    evaluation = json.loads((path / "evaluation.json").read_text())
    evaluation["summaries"]["persistence"]["mean_absolute_error_percentage_points"] = 999
    reseal(path, "evaluation.json", json.dumps(evaluation).encode())
    with pytest.raises(ReceiptError, match="summar|prediction"):
        artifacts.load_receipt_study(tmp_path, path)


def test_loading_parses_the_verified_snapshot_without_reopening_paths(
    tmp_path, scientific_fixture, monkeypatch
):
    artifacts, *_ = scientific_fixture
    path = artifacts.build_receipt_study(tmp_path)
    original = artifacts._verified_snapshots

    def replace_after_snapshot(*args):
        result = original(*args)
        (path / "predictions.parquet").write_bytes(b"replaced after verified read")
        return result

    monkeypatch.setattr(artifacts, "_verified_snapshots", replace_after_snapshot)
    assert artifacts.load_receipt_study(tmp_path, path)["evaluation"]["summaries"]


def test_accounting_must_match_the_panel_target(tmp_path, scientific_fixture):
    import pyarrow.parquet as pq

    artifacts, *_ = scientific_fixture
    path = artifacts.build_receipt_study(tmp_path)
    rows = pq.read_table(path / "source_accounting.parquet").to_pylist()
    changed = next(row for row in rows if row["release_code"] == "2505")
    changed.update(SAL_CTXFNC_C18=30.0, derived_receipt_percent=40.0)
    reseal(path, "source_accounting.parquet", artifacts._parquet(rows))
    with pytest.raises(ReceiptError, match="accounting.*panel|panel.*accounting"):
        artifacts.load_receipt_study(tmp_path, path)


@pytest.mark.parametrize("field", ["target_proportion", "target_logit"])
def test_stored_target_transforms_must_match_source_components(tmp_path, scientific_fixture, field):
    import pyarrow.parquet as pq

    artifacts, *_ = scientific_fixture
    path = artifacts.build_receipt_study(tmp_path)
    rows = pq.read_table(path / "panel.parquet").to_pylist()
    rows[0][field] = 0.123
    reseal(path, "panel.parquet", artifacts._parquet(rows))
    with pytest.raises(ReceiptError, match="panel.*accounting"):
        artifacts.load_receipt_study(tmp_path, path)


def test_fitted_model_parameters_must_match_their_inventory_key(tmp_path, scientific_fixture):
    artifacts, *_ = scientific_fixture
    path = artifacts.build_receipt_study(tmp_path)
    evaluation = json.loads((path / "evaluation.json").read_text())
    fits = evaluation["fit_parameters"]
    fits["2305->2605/history_access_acceptance"] = fits["2305->2605/history"]
    reseal(path, "evaluation.json", json.dumps(evaluation).encode())
    with pytest.raises(ReceiptError, match="fitted.*identity"):
        artifacts.load_receipt_study(tmp_path, path)


def test_input_identity_rejects_redirected_code(tmp_path, monkeypatch):
    import kasm.patient_journey.receipt_artifacts as artifacts

    names = (
        "configs/receipt_study/experiment.yaml",
        "configs/receipt_study/sources.json",
        "docs/specs/deceased-donor-receipt-0023.md",
        "configs/data_sources.yaml",
        "uv.lock",
        "src/kasm/__init__.py",
    )
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    original = Path.is_symlink
    monkeypatch.setattr(
        Path, "is_symlink", lambda self: self.name == "__init__.py" or original(self)
    )
    with pytest.raises(ReceiptError, match="link|redirect"):
        artifacts._input_identity(tmp_path)


def test_missing_fixed_comparison_is_rejected(tmp_path, scientific_fixture):
    artifacts, *_ = scientific_fixture
    path = artifacts.build_receipt_study(tmp_path)
    evaluation = json.loads((path / "evaluation.json").read_text())
    evaluation["contrasts"].pop()
    reseal(path, "evaluation.json", json.dumps(evaluation).encode())
    with pytest.raises(ReceiptError, match="comparison|contrast"):
        artifacts.load_receipt_study(tmp_path, path)


def test_concurrent_writer_cannot_replace_a_reserved_run(tmp_path, monkeypatch):
    original = Path.mkdir
    run = "3" * 64

    def race(self, *args, **kwargs):
        if self.name == run:
            original(self, *args, **kwargs)
            (self / "sentinel").write_text("other writer")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", race)
    with pytest.raises(ReceiptError, match="exists"):
        publish_receipt_payload(tmp_path, run, payload(), {})
    assert (tmp_path / "data/receipt-study/v1" / run / "sentinel").read_text() == "other writer"


def test_prepare_is_source_only_and_build_refuses_changed_inputs(
    tmp_path, scientific_fixture, monkeypatch
):
    artifacts, config, sources, panel, _ = scientific_fixture
    monkeypatch.setattr(artifacts, "load_receipt_config", lambda path: config)
    monkeypatch.setattr(artifacts, "load_data_source_manifest", lambda path: object())
    monkeypatch.setattr(artifacts, "load_receipt_sources", lambda *args, **kwargs: sources)
    monkeypatch.setattr(
        artifacts,
        "evaluate_receipt",
        lambda *args: pytest.fail("source preparation must not score"),
    )
    assert prepare_receipt_study(tmp_path)[2] == panel
    monkeypatch.setattr(artifacts, "evaluate_receipt", lambda *args: scientific_fixture[-1])
    old = artifacts._input_identity(tmp_path)
    revisions = iter((old, {**old, "src/kasm/__init__.py": "b" * 64}))
    monkeypatch.setattr(artifacts, "_input_identity", lambda root: next(revisions))
    with pytest.raises(ReceiptError, match="inputs changed"):
        artifacts.build_receipt_study(tmp_path)
    assert not (tmp_path / "data/receipt-study/v1").exists()
