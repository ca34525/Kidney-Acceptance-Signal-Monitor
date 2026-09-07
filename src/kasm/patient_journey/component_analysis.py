"""Describe reported donor outcomes on exactly matched original evaluation programs.

Program medians do not pool patients. Correlations describe one already-seen
period and cannot diagnose why outcomes are unknown or why predictions differ.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from statistics import median

import numpy as np

from kasm.patient_journey.component_config import (
    COMPONENT_FIELDS,
    ERROR_MODELS,
    ComponentConfig,
    ComponentError,
    validate_component_config,
)
from kasm.patient_journey.components import ComponentRecord, reconcile_functioning, sum_components

Row = Mapping[str, object]


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ComponentError("Matched outcomes and predictions must contain finite numbers.")
    return float(value)


def _key(row: Row) -> str:
    key = row.get("program_key")
    if not isinstance(key, str) or not key:
        raise ComponentError("A matched record requires a program key.")
    return key


def _evaluation_rows(rows: Sequence[Row], config: ComponentConfig) -> list[Row]:
    selected = []
    for row in rows:
        if row.get("target_release_code") != config.release_code:
            continue
        if row.get("feature_release_code") != config.feature_release_code:
            raise ComponentError("Evaluation records disagree with the fixed feature/target pair.")
        selected.append(row)
    return sorted(selected, key=lambda row: (_key(row), str(row.get("model", ""))))


def _source_index(
    records: Sequence[ComponentRecord], config: ComponentConfig
) -> dict[str, ComponentRecord]:
    index = {}
    for record in records:
        if record.program_key in index:
            raise ComponentError("Duplicate source program/cohort key.")
        if (
            record.release_code != config.release_code
            or str(record.listing_cohort_start) != config.listing_cohort_start
            or str(record.listing_cohort_end) != config.listing_cohort_end
            or str(record.follow_up_end) != config.follow_up_end
            or tuple(c.field for c in record.components) != COMPONENT_FIELDS
        ):
            raise ComponentError(
                "Source record has a mismatched release, cohort or component schema."
            )
        if record.combined_unknown != sum_components(record.components[2:]):
            raise ComponentError("Source unknown sum disagrees with its reported components.")
        reconcile_functioning(record.components[:2], record.published_total)
        index[record.program_key] = record
    if not index:
        raise ComponentError("Component analysis requires source records.")
    return index


def _validate_join(row: Row, record: ComponentRecord, config: ComponentConfig) -> None:
    dates = {
        "target_listing_cohort_start": config.listing_cohort_start,
        "target_listing_cohort_end": config.listing_cohort_end,
        "target_follow_up_end": config.follow_up_end,
    }
    if any(str(row.get(field)) != expected for field, expected in dates.items()):
        raise ComponentError("Matched program records disagree on listing cohort or follow-up.")
    for field, value in (
        ("target_n", record.target_n),
        ("target_published_percent", record.published_total),
    ):
        observed = row.get(field)
        if observed is not None and value is not None and _number(observed) != value:
            raise ComponentError(f"Matched program records disagree on {field}.")
        if row["primary_analytic_eligible"] and (observed is None or value is None):
            raise ComponentError("Eligible original programs require a reported count and outcome.")


def _match_panel(
    panel: Sequence[Row], source: dict[str, ComponentRecord], config: ComponentConfig
) -> tuple[list[ComponentRecord], dict[str, object], dict[str, Row]]:
    rows = _evaluation_rows(panel, config)
    index: dict[str, Row] = {}
    matched, excluded, audit_rows = [], [], []
    for row in rows:
        key = _key(row)
        if key in index:
            raise ComponentError("Duplicate panel program/cohort key.")
        index[key] = row
        eligible = row.get("primary_analytic_eligible")
        if not isinstance(eligible, bool):
            raise ComponentError("Original eligibility must be an explicit boolean.")
        record = source.get(key)
        if record is not None:
            _validate_join(row, record, config)
        if eligible:
            if record is None:
                raise ComponentError(
                    "An eligible original program is missing from the component source."
                )
            matched.append(record)
        else:
            excluded.append(
                {"program_key": key, "eligibility_status": row.get("eligibility_status")}
            )
        audit_rows.append(
            {
                "program_key": key,
                "primary_analytic_eligible": eligible,
                "eligibility_status": row.get("eligibility_status"),
                "source_matched": record is not None,
            }
        )
    if not matched:
        raise ComponentError("No original evaluation programs were eligible for matching.")
    audit: dict[str, object] = {
        "source_count": len(source),
        "panel_count": len(index),
        "matched_eligible_count": len(matched),
        "matched_eligible_keys": [r.program_key for r in matched],
        "source_only_keys": sorted(set(source) - set(index)),
        "panel_only_keys": sorted(set(index) - set(source)),
        "excluded_panel_rows": excluded,
        "panel_rows": audit_rows,
        "missing_unknown_eligible_keys": [
            r.program_key for r in matched if r.combined_unknown is None
        ],
        "missing_component_eligible_keys": {
            field: [r.program_key for r in matched if r.components[i].percent is None]
            for i, field in enumerate(COMPONENT_FIELDS)
        },
    }
    return matched, audit, index


def _prediction_index(
    predictions: Sequence[Row], eligible: Sequence[ComponentRecord], config: ComponentConfig
) -> dict[tuple[str, str], Row]:
    records = {r.program_key: r for r in eligible}
    index = {}
    for row in _evaluation_rows(predictions, config):
        key, model = _key(row), row.get("model")
        if not isinstance(model, str) or model not in ERROR_MODELS or key not in records:
            raise ComponentError("Prediction has an unexpected model or evaluation program.")
        if (key, model) in index:
            raise ComponentError("Duplicate prediction program/model key.")
        record = records[key]
        if (
            _number(row.get("target_n")) != record.target_n
            or _number(row.get("target_published_percent")) != record.published_total
        ):
            raise ComponentError(
                "Prediction count or published target disagrees with the matched source."
            )
        proportion, percent = (
            _number(row.get("predicted_proportion")),
            _number(row.get("predicted_percent")),
        )
        signed = _number(row.get("signed_error_percentage_points"))
        absolute = _number(row.get("absolute_error_percentage_points"))
        target = _number(record.published_total)
        if (
            not 0 <= proportion <= 1
            or not 0 <= percent <= 100
            or abs(percent - proportion * 100) > config.arithmetic_tolerance
            or abs(signed - (percent - target)) > config.arithmetic_tolerance
            or abs(absolute - abs(signed)) > config.arithmetic_tolerance
        ):
            raise ComponentError("Prediction values or stored error arithmetic disagree.")
        index[key, model] = row
    if set(index) != {(key, model) for key in records for model in ERROR_MODELS}:
        raise ComponentError(
            "Predictions do not cover every original evaluation program and model."
        )
    return index


def describe_association(pairs: Sequence[tuple[float | None, float | None]]) -> dict[str, object]:
    """Describe co-variation using complete programs; no significance or causal claim."""
    complete = [(_number(a), _number(b)) for a, b in pairs if a is not None and b is not None]
    reason = None
    correlation = None
    if len(complete) < 3:
        reason = "fewer_than_three_pairs"
    elif len({a for a, _ in complete}) == 1 or len({b for _, b in complete}) == 1:
        reason = "constant_variable"
    else:
        correlation = float(np.corrcoef(np.asarray(complete, dtype=float).T)[0, 1])
    return {
        "pearson_r": correlation,
        "pairs": len(complete),
        "missing_pairs": len(pairs) - len(complete),
        "reason": reason,
    }


def _median(values: Sequence[float | None]) -> dict[str, object]:
    observed = [value for value in values if value is not None]
    return {
        "programs": len(observed),
        "missing_programs": len(values) - len(observed),
        "median_percent": median(observed) if observed else None,
    }


def _population(records: Sequence[ComponentRecord]) -> dict[str, object]:
    return {
        "program_count": len(records),
        "program_keys": [r.program_key for r in records],
        "components": {
            field: _median([r.components[i].percent for r in records])
            for i, field in enumerate(COMPONENT_FIELDS)
        },
        "combined_unknown": _median([r.combined_unknown for r in records]),
        "published_total": _median([r.published_total for r in records]),
    }


def analyze_components(
    records: Sequence[ComponentRecord],
    panel: Sequence[Row],
    predictions: Sequence[Row],
    config: ComponentConfig,
) -> dict[str, object]:
    """Match original eligibility and report every fixed component/error association."""
    validate_component_config(config)
    source = _source_index(records, config)
    matched, audit, _ = _match_panel(panel, source, config)
    prediction_index = _prediction_index(predictions, matched, config)
    source_eligible = [
        record
        for record in sorted(source.values(), key=lambda r: r.program_key)
        if record.target_n is not None and record.target_n >= config.source_min_n
    ]
    audit["source_below_minimum_or_missing_n_keys"] = sorted(
        set(source) - {r.program_key for r in source_eligible}
    )
    audit["reconciliation"] = {key: source[key].reconciliation for key in sorted(source)}
    associations = {
        model: {
            label: describe_association(
                [
                    (r.combined_unknown, _number(prediction_index[r.program_key, model][field]))
                    for r in matched
                ]
            )
            for label, field in (
                ("signed", "signed_error_percentage_points"),
                ("absolute", "absolute_error_percentage_points"),
            )
        }
        for model in ERROR_MODELS
    }
    return {
        "analysis_id": config.analysis_id,
        "promotion_allowed": False,
        "future_forecast_available": False,
        "release_code": config.release_code,
        "listing_cohort_start": config.listing_cohort_start,
        "listing_cohort_end": config.listing_cohort_end,
        "follow_up_end": config.follow_up_end,
        "published_value": config.published_value,
        "published_precision": config.published_precision,
        "denominator": config.denominator,
        "months_after_listing": config.months_after_listing,
        "audit": audit,
        "populations": {
            "source_n_at_least_10": _population(source_eligible),
            "original_evaluation": _population(matched),
        },
        "associations": {
            "published_outcome": describe_association(
                [(r.combined_unknown, r.published_total) for r in matched]
            ),
            "errors": associations,
        },
        "matched_errors": [
            {
                "program_key": r.program_key,
                "model": model,
                "combined_unknown_percent": r.combined_unknown,
                "published_total_percent": r.published_total,
                "signed_error_percentage_points": prediction_index[r.program_key, model][
                    "signed_error_percentage_points"
                ],
                "absolute_error_percentage_points": prediction_index[r.program_key, model][
                    "absolute_error_percentage_points"
                ],
            }
            for r in matched
            for model in ERROR_MODELS
        ],
    }
