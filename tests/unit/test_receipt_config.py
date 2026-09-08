"""The receipt study cannot quietly change its question, inputs or output location."""

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest
import yaml

from kasm.patient_journey.receipt_config import (
    ReceiptConfig,
    ReceiptError,
    load_receipt_config,
    validate_receipt_config,
    validate_receipt_destination,
)


def test_fixed_config_rejects_report_count_and_changed_target() -> None:
    config = ReceiptConfig()
    validate_receipt_config(config)
    with pytest.raises(ReceiptError, match="fixed"):
        validate_receipt_config(replace(config, target_scale="published_functioning"))
    groups = (("history", ("historical_target_count",)),)
    with pytest.raises(ReceiptError, match="fixed"):
        validate_receipt_config(replace(config, feature_groups=groups))


def test_yaml_requires_exact_types_and_fields(tmp_path: Path) -> None:
    path = tmp_path / "experiment.yaml"
    values = json.loads(json.dumps(asdict(ReceiptConfig())))
    path.write_text(yaml.safe_dump(values), encoding="utf-8")
    assert load_receipt_config(path) == ReceiptConfig()
    values["promotion_allowed"] = 0
    path.write_text(yaml.safe_dump(values), encoding="utf-8")
    with pytest.raises(ReceiptError, match="fixed"):
        load_receipt_config(path)
    path.write_text("[broken", encoding="utf-8")
    with pytest.raises(ReceiptError, match="read"):
        load_receipt_config(path)


@pytest.mark.parametrize(
    "path",
    [
        "../receipt",
        "artifacts/release/a",
        "data/receipt-study/v1/../x",
        "C:/outside",
        "data/receipt-study/v1/x",
    ],
)
def test_output_rejects_traversal_and_original_roots(tmp_path: Path, path: str) -> None:
    with pytest.raises(ReceiptError, match="Output"):
        validate_receipt_destination(Path(path), repository_root=tmp_path)


def test_output_accepts_only_run_hash(tmp_path: Path) -> None:
    path = Path("data/receipt-study/v1") / ("a" * 64)
    assert validate_receipt_destination(path, repository_root=tmp_path) == tmp_path / path


def test_missing_config_is_actionable(tmp_path: Path) -> None:
    with pytest.raises(ReceiptError, match="read"):
        load_receipt_config(tmp_path / "absent.yaml")


def test_nonfinite_settings_raise_a_domain_error() -> None:
    with pytest.raises(ReceiptError, match="fixed"):
        validate_receipt_config(replace(ReceiptConfig(), alpha=float("nan")))
