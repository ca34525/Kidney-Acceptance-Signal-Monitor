from __future__ import annotations

import json
import shlex
import subprocess
import tomllib
from pathlib import Path

from kasm.patient_journey.release import validate_patient_journey_release_directory
from kasm.reporting.artifacts import validate_release_bundle

PROJECT_ROOT = Path(__file__).parents[2]


def test_pytest_basetemp_is_creatable_in_a_fresh_checkout() -> None:
    config = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    addopts = shlex.split(config["tool"]["pytest"]["ini_options"]["addopts"])
    basetemp_option = next(option for option in addopts if option.startswith("--basetemp="))
    basetemp = Path(basetemp_option.partition("=")[2])

    assert not basetemp.is_absolute()
    assert basetemp.parent == Path("."), (
        "pytest creates --basetemp without parent directories, so a nested path fails when its "
        "ignored parent is absent from a fresh checkout"
    )


def test_no_disallowed_large_files_tracked() -> None:
    tracked = (
        subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
        )
        .stdout.decode()
        .split("\0")
    )
    tracked_paths = [Path(value) for value in tracked if value]

    assert Path("artifacts/release/release_manifest.json") in tracked_paths
    assert Path("artifacts/patient_journey_v2/release_manifest.json") in tracked_paths
    assert not any(path.parts[0] == "data" for path in tracked_paths)
    assert not any(
        path.suffix.casefold() in {".xls", ".xlsx", ".zip", ".pkl", ".joblib"}
        for path in tracked_paths
    )
    assert not any(
        (PROJECT_ROOT / path).stat().st_size >= 5 * 1024 * 1024 for path in tracked_paths
    )
    release_roots = {
        path.parts[:2] for path in tracked_paths if path.parts and path.parts[0] == "artifacts"
    }
    assert release_roots == {("artifacts", "release"), ("artifacts", "patient_journey_v2")}


def test_tracked_release_bundle_is_valid_and_under_five_megabytes() -> None:
    summary = validate_release_bundle(PROJECT_ROOT / "artifacts" / "release")
    assert summary.total_bytes < 5 * 1024 * 1024


def test_tracked_v2_release_is_canonical_and_under_five_megabytes() -> None:
    release_dir = PROJECT_ROOT / "artifacts" / "patient_journey_v2"
    summary = validate_patient_journey_release_directory(release_dir)
    manifest = json.loads(summary.manifest_path.read_text(encoding="utf-8"))

    assert summary.total_bytes < 5 * 1024 * 1024
    assert manifest["provenance"]["canonical_build"] is True
    assert manifest["provenance"]["git_worktree_dirty"] is False


def test_container_process_is_nonroot() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    effective = [
        line.strip()
        for line in dockerfile.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    user_index = effective.index("USER kasm")
    command_index = next(
        index for index, line in enumerate(effective) if line.startswith(("CMD ", "ENTRYPOINT "))
    )

    assert user_index < command_index
    assert any(line.startswith("HEALTHCHECK ") for line in effective)
    assert "KASM_ARTIFACT_DIR=/app/artifacts/release/processed" in dockerfile
    assert "KASM_MODELING_DIR=/app/artifacts/release/modeling" in dockerfile


def test_release_manifest_documents_expected_offline_application_roots() -> None:
    manifest = json.loads(
        (PROJECT_ROOT / "artifacts" / "release" / "release_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["application_roots"] == {
        "modeling": "artifacts/release/modeling",
        "processed": "artifacts/release/processed",
    }
    app_source = (PROJECT_ROOT / "app" / "streamlit_app.py").read_text(encoding="utf-8")
    assert '"artifacts" / "release" / "processed"' in app_source
    assert '"artifacts" / "release" / "modeling"' in app_source


def test_required_release_documentation_and_diagrams_are_present() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    data_card = (PROJECT_ROOT / "docs" / "data_card.md").read_text(encoding="utf-8")
    model_card = (PROJECT_ROOT / "docs" / "model_card.md").read_text(encoding="utf-8")
    accessibility = (PROJECT_ROOT / "docs" / "accessibility_checklist.md").read_text(
        encoding="utf-8"
    )
    reproduction = (PROJECT_ROOT / "docs" / "reproduction_log.md").read_text(encoding="utf-8")

    assert "Four-minute offline demo" in readme
    assert readme.count("```mermaid") >= 2
    for phrase in ("Grain", "2017–2025", "Missingness", "Exclusions", "Provenance"):
        assert phrase in data_card
    assert "attempted_not_promoted" in model_card
    assert "Keyboard" in accessibility
    assert "WCAG AA" in accessibility
    assert "uv sync --frozen" in reproduction
    assert "docker" in reproduction.casefold()
    assert (PROJECT_ROOT / "LICENSE").is_file()


def test_ci_enforces_release_and_container_gates() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for required in (
        "uv lock --check",
        "uv pip check",
        "--cov=src/kasm/data",
        "--cov=src/kasm/modeling",
        "--cov=src/kasm/reporting",
        "--cov-branch",
        "--cov-fail-under=80",
        "docker build",
        "docker exec",
        "id -u",
        "_stcore/health",
    ):
        assert required in workflow


def test_static_analysis_includes_ai_assisted_change_guardrails() -> None:
    config = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    selected_rules = set(config["tool"]["ruff"]["lint"]["select"])

    assert {"C90", "PT", "S"} <= selected_rules
    assert config["tool"]["ruff"]["lint"]["mccabe"]["max-complexity"] <= 15


def test_release_artifact_bytes_are_checkout_stable() -> None:
    attributes = (PROJECT_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "artifacts/release/** binary" in attributes
    assert "artifacts/patient_journey_v2/** binary" in attributes
