import pytest

from kasm.patient_journey.evaluation import (
    EvaluationPrediction,
    assign_within_release_volume_quartiles,
    paired_clustered_bootstrap_interval,
    summarize_predictions,
)


def _prediction(
    program: str,
    release: str,
    model: str,
    absolute_error: float,
    *,
    target_n: int,
) -> EvaluationPrediction:
    return EvaluationPrediction(
        program_key=program,
        feature_release_code="feature",
        target_release_code=release,
        model=model,
        training_pairs=(),
        target_n=target_n,
        target_published_percent=50.0,
        predicted_proportion=(50.0 + absolute_error) / 100,
        predicted_percent=50.0 + absolute_error,
        absolute_error_percentage_points=absolute_error,
        signed_error_percentage_points=absolute_error,
        volume_quartile=1,
        first_observed_program=False,
        any_model_feature_missing=False,
    )


def test_v2_volume_strata_are_deterministic_with_ties() -> None:
    rows = [
        {"program_key": key, "target_release_code": "2505", "target_n": n}
        for key, n in (("DDDD:TX1", 20), ("BBBB:TX1", 10), ("AAAA:TX1", 10), ("CCCC:TX1", 20))
    ]

    forward = assign_within_release_volume_quartiles(rows)
    reverse = assign_within_release_volume_quartiles(list(reversed(rows)))

    assert forward == reverse
    assert forward == {
        ("AAAA:TX1", "2505"): 1,
        ("BBBB:TX1", "2505"): 2,
        ("CCCC:TX1", "2505"): 3,
        ("DDDD:TX1", "2505"): 4,
    }


def test_v2_metrics_are_reported_on_published_percentage_point_scale() -> None:
    predictions = (
        _prediction("AAAA:TX1", "2205", "persistence", 10.0, target_n=10),
        _prediction("BBBB:TX1", "2205", "persistence", 20.0, target_n=30),
        _prediction("AAAA:TX1", "2505", "persistence", 2.0, target_n=20),
    )

    summary = summarize_predictions(predictions)

    assert summary.target_release_balanced_mae_percentage_points == 8.5
    assert summary.row_pooled_mae_percentage_points == 32 / 3
    assert summary.candidate_volume_weighted_mae_percentage_points == 740 / 60
    assert summary.mean_signed_error_percentage_points == 32 / 3
    assert summary.calibration_scale == "percentage_points"


def test_v2_paired_bootstrap_resamples_program_clusters_deterministically() -> None:
    comparator = tuple(
        _prediction(program, release, "history", error, target_n=20)
        for program, release, error in (
            ("AAAA:TX1", "2205", 5.0),
            ("AAAA:TX1", "2505", 4.0),
            ("BBBB:TX1", "2205", 3.0),
            ("BBBB:TX1", "2505", 2.0),
            ("CCCC:TX1", "2205", 1.0),
            ("CCCC:TX1", "2505", 3.0),
        )
    )
    challenger = tuple(
        _prediction(
            row.program_key,
            row.target_release_code,
            "full",
            row.absolute_error_percentage_points - 1.0,
            target_n=20,
        )
        for row in comparator
    )

    first = paired_clustered_bootstrap_interval(
        challenger,
        comparator,
        resamples=200,
        seed=123,
        percentiles=(2.5, 97.5),
    )
    second = paired_clustered_bootstrap_interval(
        tuple(reversed(challenger)),
        tuple(reversed(comparator)),
        resamples=200,
        seed=123,
        percentiles=(2.5, 97.5),
    )

    assert first == second
    assert first.point_estimate == -1.0
    assert first.lower == pytest.approx(-1.0)
    assert first.upper == pytest.approx(-1.0)
