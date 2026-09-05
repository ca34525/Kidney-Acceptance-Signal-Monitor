"""Check that missing values and malformed timing cannot become plausible display values."""

from datetime import date
from pathlib import Path

import pytest

from kasm.patient_journey.product import (
    PatientJourneyProductError,
    load_patient_journey_product,
    measurement_segments_text,
    program_panel,
    publication_value_text,
    published_date_text,
    reported_value,
)


def test_missing_values_and_reported_zero_remain_distinct() -> None:
    assert reported_value(None) == "Not reported"
    assert reported_value(0) == "0.0"
    assert reported_value("Suppressed") == "Suppressed"
    assert published_date_text(None) == "Not reported"
    assert published_date_text(date(2025, 7, 8)) == "2025-07-08"
    assert publication_value_text(None, "month") == "Not reported"
    assert publication_value_text("2019-07", "month") == "07/2019"
    assert publication_value_text("2025-07-08", "day") == "2025-07-08"


@pytest.mark.parametrize(
    ("value", "precision"),
    [
        (2025, "month"),
        ("2025-07", "year"),
        ("2025-00", "month"),
        ("2025-13", "month"),
        ("2025-07-08", "month"),
        ("2025-02-30", "day"),
    ],
)
def test_publication_display_rejects_inconsistent_precision(value: object, precision: str) -> None:
    with pytest.raises(PatientJourneyProductError, match="Publication value"):
        publication_value_text(value, precision)


def test_date_display_rejects_unparsed_source_text() -> None:
    with pytest.raises(PatientJourneyProductError, match="must be a date"):
        published_date_text("July 2025")


@pytest.mark.parametrize(
    "value",
    [
        None,
        "{",
        "{}",
        "[]",
        "[1]",
        '[{"start": 2020, "end": "2021-01-01"}]',
        '[{"start": "2020-02-30", "end": "2021-01-01"}]',
    ],
)
def test_measurement_display_rejects_malformed_segments(value: object) -> None:
    with pytest.raises(PatientJourneyProductError, match="[Mm]easurement"):
        measurement_segments_text(value)


def test_program_selection_rejects_missing_or_unknown_program() -> None:
    product = load_patient_journey_product(
        Path(__file__).parents[2] / "artifacts/patient_journey_v2",
    )
    with pytest.raises(PatientJourneyProductError, match="cannot be empty"):
        program_panel(product, "")
    with pytest.raises(PatientJourneyProductError, match="absent"):
        program_panel(product, "not-a-program")


def test_product_loader_reports_missing_release(tmp_path: Path) -> None:
    with pytest.raises(PatientJourneyProductError, match="release is invalid"):
        load_patient_journey_product(tmp_path / "missing")
