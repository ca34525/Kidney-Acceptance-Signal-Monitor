import math
from dataclasses import asdict, replace

import numpy as np
import pytest

from kasm.patient_journey.receipt_config import ReceiptConfig, ReceiptError
from kasm.patient_journey.receipt_modeling import (
    ReceiptPrediction,
    evaluate_receipt,
    paired_receipt_bootstrap,
    receipt_continuation_gate,
    summarize_receipt,
)

FOLDS = (
    (("2205", "2505"), (("1905", "2205"),)),
    (("2305", "2605"), (("1905", "2205"),)),
)


def _logit(p, n):
    return math.log((n * p + 0.5) / (n * (1 - p) + 0.5))


def _row(program, pair, prior, outcome, *, n=40):
    result = {
        "program_key": program,
        "feature_release_code": pair[0],
        "target_release_code": pair[1],
        "primary_analytic_eligible": True,
        "target_n": n,
        "derived_receipt_percent": outcome * 100,
        "target_proportion": outcome,
        "target_logit": _logit(outcome, n),
        "prior_target_n": 25,
        "prior_target_proportion": prior,
        "prior_target_logit": _logit(prior, 25),
        "historical_mean_target_proportion": prior,
        "transplant_rate_ratio": 1.0 + prior,
        "transplant_rate_person_years": 100.0,
        "wait_time_months_25th_percentile": None,
        "acceptance_overall_expected_acceptances": 20.0,
        "acceptance_overall_oar": 1.0,
        "acceptance_overall_oar_lower": 0.8,
        "acceptance_overall_oar_upper": 1.2,
        "acceptance_low_oar": 1.0,
        "acceptance_medium_oar": None,
        "acceptance_high_oar": None,
        "acceptance_hard_to_place_oar": 1.0,
    }
    for name in (
        "transplant_rate_ratio",
        "transplant_rate_person_years",
        "wait_time",
        "acceptance_expected_acceptances",
        "acceptance_overall_oar",
        "acceptance_interval",
        "acceptance_low_oar",
        "acceptance_medium_oar",
        "acceptance_high_oar",
        "acceptance_hard_to_place_oar",
    ):
        result[f"missing_{name}"] = name in {
            "wait_time",
            "acceptance_medium_oar",
            "acceptance_high_oar",
        }
    return result


def _rows():
    return [
        _row(program, pair, prior, min(0.9, prior + shift), n=n)
        for pair, shift in (
            (("1905", "2205"), 0.05),
            (("2205", "2505"), 0.10),
            (("2305", "2605"), 0.12),
        )
        for program, prior, n in (
            ("AAAA:TX1", 0.2, 10),
            ("BBBB:TX1", 0.4, 20),
            ("CCCC:TX1", 0.6, 40),
        )
    ]


def _prediction(program, origin, model, error, *, n=20):
    return ReceiptPrediction(
        program_key=program,
        feature_release_code=origin,
        target_release_code=f"t{origin}",
        model=model,
        training_pairs=(),
        target_n=n,
        derived_receipt_percent=50.0,
        predicted_proportion=(50.0 + error) / 100,
        predicted_percent=50.0 + error,
        absolute_error_percentage_points=abs(error),
        signed_error_percentage_points=error,
    )


def test_receipt_metrics_balance_origins_with_unequal_program_counts():
    values = (
        _prediction("A", "one", "m", 10, n=10),
        _prediction("B", "one", "m", -20, n=30),
        _prediction("A", "two", "m", 2, n=20),
    )
    summary = summarize_receipt(values)
    assert summary.mean_absolute_error_percentage_points == 8.5
    assert summary.mean_signed_error_percentage_points == -1.5
    assert summary.volume_weighted_mae_percentage_points == 9.75
    assert summary.n == 3
    assert tuple(item.feature_release_code for item in summary.origins) == ("one", "two")


def test_receipt_fixed_folds_keep_every_model_on_identical_rows_and_bound_predictions():
    result = evaluate_receipt(_rows(), ReceiptConfig(), FOLDS)
    assert len(result.predictions) == 30
    assert len(result.contrasts) == 9
    assert {len([p for p in result.predictions if p.model == m]) for m in result.summaries} == {6}
    assert all(0 <= p.predicted_proportion <= 1 for p in result.predictions)
    assert {p.training_pairs for p in result.predictions if p.model == "history"} == {
        FOLDS[0][1],
        FOLDS[1][1],
    }
    assert all(s.n == 4 for s in result.sensitivities[20].values())
    assert all(s.n == 2 for s in result.sensitivities[30].values())
    for row in (row for row in _rows() if row["feature_release_code"] in {"2205", "2305"}):
        p = next(
            p
            for p in result.predictions
            if p.program_key == row["program_key"]
            and p.feature_release_code == row["feature_release_code"]
            and p.model == "persistence"
        )
        assert p.predicted_proportion == row["prior_target_proportion"]


def test_receipt_evaluation_targets_cannot_change_fitted_predictions():
    rows = _rows()
    first = evaluate_receipt(rows, ReceiptConfig(), FOLDS)
    changed = [dict(row) for row in rows]
    for row in (row for row in changed if row["feature_release_code"] in {"2205", "2305"}):
        row["target_proportion"] = 0.8
        row["derived_receipt_percent"] = 80.0
        row["target_logit"] = _logit(0.8, row["target_n"])
    second = evaluate_receipt(changed, ReceiptConfig(), FOLDS)
    assert [p.predicted_percent for p in first.predictions] == [
        p.predicted_percent for p in second.predictions
    ]
    reverse = evaluate_receipt(list(reversed(rows)), ReceiptConfig(), FOLDS)
    assert asdict(first) == asdict(reverse)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_n", 9),
        ("target_n", True),
        ("target_proportion", float("nan")),
        ("derived_receipt_percent", 101),
        ("target_logit", 0.0),
        ("prior_target_logit", 0.0),
        ("prior_target_n", 0),
        ("primary_analytic_eligible", 1),
    ],
)
def test_receipt_rejects_invalid_eligible_targets_and_prior_history(field, value):
    rows = _rows()
    rows[0][field] = value
    with pytest.raises(ReceiptError):
        evaluate_receipt(rows, ReceiptConfig(), FOLDS)


def test_receipt_rejects_duplicate_or_unpublished_training_pairs():
    rows = _rows()
    with pytest.raises(ReceiptError, match="duplicate"):
        evaluate_receipt([*rows, rows[0]], ReceiptConfig(), FOLDS)
    with pytest.raises(ReceiptError, match="training"):
        evaluate_receipt(rows, ReceiptConfig(), ((FOLDS[0][0], (("2006", "2305"),)),))
    with pytest.raises(ReceiptError, match="training"):
        evaluate_receipt(rows[6:], ReceiptConfig(), FOLDS)


def test_receipt_missing_targets_are_unscored_and_missing_features_keep_their_rows():
    rows = _rows()
    rows[-1].update(
        primary_analytic_eligible=False,
        derived_receipt_percent=None,
        target_proportion=None,
        target_logit=None,
        target_n=None,
    )
    result = evaluate_receipt(rows, ReceiptConfig(), FOLDS)
    assert all(s.n == 5 for s in result.summaries.values())
    assert all(
        p.program_key != "CCCC:TX1" or p.feature_release_code != "2305" for p in result.predictions
    )


def test_receipt_bootstrap_keeps_clusters_and_redraws_missing_origins():
    comparator = (_prediction("A", "one", "b", 3), _prediction("B", "two", "b", 3))
    challenger = tuple(
        replace(
            p,
            model="c",
            predicted_proportion=0.52,
            predicted_percent=52,
            absolute_error_percentage_points=2,
            signed_error_percentage_points=2,
        )
        for p in comparator
    )
    result = paired_receipt_bootstrap(challenger, comparator, resamples=100, seed=123)
    assert result.point_estimate == -1
    assert result.lower == result.upper == -1
    assert result.rejected_draws > 0
    assert result.attempted_draws == 100 + result.rejected_draws
    assert result == paired_receipt_bootstrap(
        tuple(reversed(challenger)), tuple(reversed(comparator)), resamples=100, seed=123
    )
    with pytest.raises(ReceiptError, match="identical"):
        paired_receipt_bootstrap(challenger[:1], comparator, resamples=100, seed=123)


def test_receipt_bootstrap_fails_when_redraw_budget_is_exhausted(monkeypatch):
    class AlwaysFirst:
        def integers(self, low, high, size):
            return np.zeros(size, dtype=int)

    monkeypatch.setattr(np.random, "default_rng", lambda seed: AlwaysFirst())
    rows = (_prediction("A", "one", "b", 3), _prediction("B", "two", "b", 3))
    with pytest.raises(ReceiptError, match="attempt"):
        paired_receipt_bootstrap(rows, rows, resamples=2, seed=123, max_attempt_factor=2)


def _gate_predictions(full_errors=(0.5, -0.5), baseline_errors=(1.0, -1.0)):
    return tuple(
        _prediction(program, origin, model, error)
        for model in (
            "persistence",
            "historical_mean",
            "history",
            "history_access",
            "history_access_acceptance",
        )
        for origin in ("one", "two")
        for program, error in zip(
            ("A", "B"),
            full_errors if model == "history_access_acceptance" else baseline_errors,
            strict=True,
        )
    )


def test_receipt_continuation_requires_size_consistency_and_bias_bounds():
    config = ReceiptConfig()
    assert receipt_continuation_gate(_gate_predictions(), config).passed
    small = receipt_continuation_gate(_gate_predictions((0.51, -0.51)), config)
    assert not small.passed
    biased = receipt_continuation_gate(_gate_predictions((2.1, 2.1), (4.0, -4.0)), config)
    assert not biased.passed
    one_origin = tuple(p for p in _gate_predictions() if p.feature_release_code == "one")
    assert not receipt_continuation_gate(one_origin, config).passed
    one_bad_origin = tuple(
        replace(
            p,
            predicted_proportion=0.52,
            predicted_percent=52,
            absolute_error_percentage_points=2,
            signed_error_percentage_points=2,
        )
        if p.feature_release_code == "two" and p.model == "history_access_acceptance"
        else p
        for p in _gate_predictions()
    )
    assert not receipt_continuation_gate(one_bad_origin, config).passed


def test_receipt_preprocessing_uses_training_values_only():
    rows = _rows()
    first = evaluate_receipt(rows, ReceiptConfig(), FOLDS)
    next(row for row in rows if row["feature_release_code"] == "2205")["transplant_rate_ratio"] = (
        1e100
    )
    second = evaluate_receipt(rows, ReceiptConfig(), FOLDS)

    def unaffected(p):
        return not (p.program_key == "AAAA:TX1" and p.feature_release_code == "2205")

    assert [p.predicted_percent for p in first.predictions if unaffected(p)] == [
        p.predicted_percent for p in second.predictions if unaffected(p)
    ]


def test_receipt_bootstrap_never_splits_a_programs_repeated_origins():
    comparator = tuple(
        _prediction(program, origin, "b", 5) for program in ("A", "B") for origin in ("one", "two")
    )
    challenger = tuple(
        _prediction(p.program_key, p.feature_release_code, "c", error)
        for p, error in zip(comparator, (8, 2, 2, 8), strict=True)
    )
    interval = paired_receipt_bootstrap(challenger, comparator, resamples=100, seed=42)
    assert interval.lower == interval.upper == interval.point_estimate == 0
    assert interval.attempted_draws == 100


def test_receipt_continuation_also_requires_relative_improvement_and_bias_change():
    relative = receipt_continuation_gate(
        _gate_predictions((11.5, -11.5), (12, -12)), ReceiptConfig()
    )
    assert not relative.passed
    assert any("5%" in reason for reason in relative.reasons)
    bias = receipt_continuation_gate(_gate_predictions((1, 1), (2, -2)), ReceiptConfig())
    assert not bias.passed
    assert any("bias worsens" in reason for reason in bias.reasons)


def test_receipt_source_restriction_can_use_one_training_pair_at_both_origins():
    folds = tuple((evaluation, (("1905", "2205"),)) for evaluation, _ in FOLDS)
    rows = [row for row in _rows() if row["feature_release_code"] != "2006"]
    result = evaluate_receipt(rows, ReceiptConfig(), folds)
    assert all(
        p.training_pairs == (("1905", "2205"),)
        for p in result.predictions
        if p.model not in ("persistence", "historical_mean")
    )


def test_receipt_runner_rejects_training_from_the_final_excluded_source():
    forbidden = (
        FOLDS[0],
        (("2305", "2605"), (("1905", "2205"), ("2006", "2305"))),
    )
    with pytest.raises(ReceiptError, match="training"):
        evaluate_receipt(
            [*_rows(), _row("AAAA:TX1", ("2006", "2305"), 0.3, 0.4)],
            ReceiptConfig(),
            forbidden,
        )


def test_receipt_fit_evidence_contains_only_deterministic_training_parameters():
    first = evaluate_receipt(_rows(), ReceiptConfig(), FOLDS)
    assert len(first.fit_parameters) == 6
    for name, fit in first.fit_parameters.items():
        assert name == f"{fit.feature_release_code}->{fit.target_release_code}/{fit.model}"
        assert fit.training_pairs == (("1905", "2205"),)
        assert len(fit.feature_names) == len(fit.coefficients) == len(fit.imputer_statistics)
        assert len(fit.feature_names) == len(fit.scaler_mean) == len(fit.scaler_scale)
        assert all(
            math.isfinite(value)
            for value in (
                fit.intercept,
                *fit.coefficients,
                *fit.imputer_statistics,
                *fit.scaler_mean,
                *fit.scaler_scale,
            )
        )
        assert all(value > 0 for value in fit.scaler_scale)
        if "log1p_wait_time_months_25th_percentile" in fit.feature_names:
            index = fit.feature_names.index("log1p_wait_time_months_25th_percentile")
            assert fit.imputer_statistics[index] == 0
    rows = _rows()
    for row in rows:
        if row["feature_release_code"] in {"2205", "2305"}:
            row.update(
                target_proportion=0.8,
                derived_receipt_percent=80.0,
                target_logit=_logit(0.8, row["target_n"]),
                transplant_rate_ratio=1e50,
            )
    changed = evaluate_receipt(list(reversed(rows)), ReceiptConfig(), FOLDS)
    assert first.fit_parameters == changed.fit_parameters
