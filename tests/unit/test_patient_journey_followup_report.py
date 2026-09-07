from collections.abc import Iterator
from copy import deepcopy
from xml.etree import ElementTree

import pytest

from kasm.patient_journey.followup_report import render_followup_report

GROUPS = (
    "history",
    "history_acceptance",
    "history_access",
    "history_access_acceptance",
    "history_access_acceptance_safety",
)


def _model_names() -> Iterator[str]:
    yield from (f"{version}_{group}" for version in ("original", "revised") for group in GROUPS)
    yield from ("historical_mean", "persistence", "available_cohort_reference")


def _evidence() -> dict[str, object]:
    models = {}
    for index, name in enumerate(_model_names()):
        models[name] = {
            "features": ["historical_target_count"] if name.startswith("original") else [],
            "summary": {
                "n": 4,
                "target_release_balanced_mae_percentage_points": 2.25 + index,
                "mean_signed_error_percentage_points": -0.5 + index,
                "candidate_volume_weighted_mae_percentage_points": 3.75 + index,
            },
            "contributions": {
                "by_feature": {"historical_target_count": 0.375},
                "sum": 0.375,
                "mean_predicted_logit_change": 0.375,
            },
        }
    contrasts = [
        ("original_history_acceptance", "historical_mean"),
        *((f"revised_{group}", f"original_{group}") for group in GROUPS),
        ("revised_history_access", "revised_history"),
        ("revised_history_acceptance", "revised_history"),
        ("revised_history_access_acceptance", "revised_history_access"),
        ("revised_history_access_acceptance", "revised_history_acceptance"),
        ("revised_history_access_acceptance_safety", "revised_history_access_acceptance"),
        ("revised_history_acceptance", "historical_mean"),
    ]
    return {
        "analysis_id": "kidney_patient_journey_v2_followup_report_count_v1",
        "evidence_status": "development_uncommitted",
        "promotion_allowed": False,
        "future_forecast_available": False,
        "reconstruction": {
            "prediction_rows": 32,
            "max_absolute_difference": 4e-14,
            "absolute_tolerance": 1e-10,
        },
        "populations": {
            "training": ["A", "B", "C", "D"],
            "evaluation": ["A", "B", "C", "D"],
            "excluded": ["E"],
        },
        "report_count": {
            "training": {
                "n": 4,
                "frequencies": {"1": 2, "2": 2},
                "mean": 1.5,
                "population_standard_deviation": 0.5,
                "minimum": 1,
                "maximum": 2,
            },
            "evaluation": {
                "n": 4,
                "frequencies": {"4": 2, "5": 2},
                "mean": 4.5,
                "population_standard_deviation": 0.5,
                "minimum": 4,
                "maximum": 5,
            },
            "mean_shift_training_standard_deviations": 6.0,
            "unavailable_reason": None,
        },
        "models": models,
        "contrasts": [
            {
                "challenger": challenger,
                "comparator": comparator,
                "units": "percentage_points",
                "point_estimate": -1.125,
                "lower": -2.5,
                "upper": 0.25,
                "resamples": 2000,
                "seed": 20260904,
            }
            for challenger, comparator in contrasts
        ],
    }


def _svg_text(payload: bytes) -> str:
    # Only parse bytes freshly created from our constructed fixture, never external XML.
    root = ElementTree.fromstring(payload)  # noqa: S314
    return " ".join(element.text or "" for element in root.iter() if element.tag.endswith("}text"))


def test_followup_report_preserves_units_and_all_fixed_comparisons() -> None:
    outputs = render_followup_report(_evidence())
    report = outputs["report.md"].decode()

    assert "July 2019–June 2020" in report
    assert "July 2022–June 2023" in report
    assert "original listing group" in report
    assert "18 months" in report
    assert "one historical evaluation period" in report
    assert "6.000 training standard deviations" in report
    assert "| Original: history | 4 | 2.250 | -0.500 | 3.750 |" in report
    assert report.count("| -1.125 | [-2.500, 0.250] |") == 12
    assert "0.375000" in report
    assert "logit" in report
    assert "not directly additive percentage-point changes" in report
    assert "Positive signed error means predictions are too high" in report
    assert "does not measure individual patient accuracy" in report
    assert "development_uncommitted" in report
    assert "Public aggregate research prototype" in report
    assert "Scientific Registry of Transplant Recipients" in report


def test_followup_figures_are_deterministic_labeled_and_never_rank_models() -> None:
    evidence = _evidence()
    before = deepcopy(evidence)

    first = render_followup_report(evidence)
    second = render_followup_report(evidence)

    assert first == second
    assert evidence == before
    count_text = _svg_text(first["report_counts.svg"])
    errors_text = _svg_text(first["model_errors.svg"])
    assert "Number of earlier available reports" in count_text
    assert "Number of programs" in count_text
    assert "Training" in count_text
    assert "Evaluation" in count_text
    assert "percentage points" in errors_text
    assert errors_text.index("Original: history") < errors_text.index("Revised: history")
    assert "Historical mean" in errors_text
    assert first["report_counts.png"].startswith(b"\x89PNG\r\n\x1a\n")
    assert first["model_errors.png"].startswith(b"\x89PNG\r\n\x1a\n")


def test_followup_report_keeps_unavailable_shift_separate_from_zero() -> None:
    evidence = _evidence()
    count = evidence["report_count"]
    assert isinstance(count, dict)
    count["mean_shift_training_standard_deviations"] = None
    count["unavailable_reason"] = "training_standard_deviation_is_zero"

    report = render_followup_report(evidence)["report.md"].decode()

    assert "Not available: the training report count has no variation" in report
    assert "0.000 training standard deviations" not in report


@pytest.mark.parametrize("flag", ["promotion_allowed", "future_forecast_available"])
def test_followup_report_rejects_forecast_or_promotion_permission(flag: str) -> None:
    evidence = _evidence()
    evidence[flag] = True

    with pytest.raises(ValueError, match="promotion and future forecasts"):
        render_followup_report(evidence)


def test_followup_report_rejects_missing_models_and_nonfinite_metric() -> None:
    evidence = _evidence()
    models = evidence["models"]
    assert isinstance(models, dict)
    del models["revised_history"]
    with pytest.raises(ValueError, match="revised_history"):
        render_followup_report(evidence)

    evidence = _evidence()
    models = evidence["models"]
    assert isinstance(models, dict)
    models["historical_mean"]["summary"]["target_release_balanced_mae_percentage_points"] = float(
        "nan"
    )
    with pytest.raises(ValueError, match="finite"):
        render_followup_report(evidence)
