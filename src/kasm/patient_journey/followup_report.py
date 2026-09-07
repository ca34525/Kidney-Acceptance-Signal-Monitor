"""Turn the separate V2 follow-up evidence into readable, reproducible documents.

Each error describes a program's published 18-month outcome for one listing
group. These functions format precomputed evidence without fitting models or
writing files. Figures compare every fixed model in study order, so their order
does not suggest that an approach has been selected for use.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from io import BytesIO
from typing import cast

from matplotlib import rc_context
from matplotlib.figure import Figure

_GROUPS = (
    "history",
    "history_acceptance",
    "history_access",
    "history_access_acceptance",
    "history_access_acceptance_safety",
)
_MODELS = tuple(
    f"{version}_{group}" for version in ("original", "revised") for group in _GROUPS
) + (
    "historical_mean",
    "persistence",
    "available_cohort_reference",
)
_BANNER = "Public aggregate research prototype — not clinical or regulatory decision support."
_SOURCE = (
    "Scientific Registry of Transplant Recipients (SRTR), public kidney Program-Specific Reports; "
    "verified original V2 bundle."
)
_MAE = "target_release_balanced_mae_percentage_points"


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"Follow-up report requires a mapping for {label}.")
    return cast(Mapping[str, object], value)


def _section(row: Mapping[str, object], key: str) -> Mapping[str, object]:
    return _mapping(row.get(key), key)


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError(f"Follow-up report requires a finite number for {label}.")
    return float(value)


def _numeric(row: Mapping[str, object], key: str) -> float:
    return _number(row.get(key), key)


def _items(value: object, label: str) -> Sequence[object]:
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise ValueError(f"Follow-up report requires a sequence for {label}.")
    return value


def _label(name: str) -> str:
    if name == "historical_mean":
        return "Historical mean"
    if name == "persistence":
        return "Persistence"
    if name == "available_cohort_reference":
        return "Available-cohort reference"
    version, group = name.split("_", 1)
    return f"{version.capitalize()}: {' + '.join(group.split('_'))}"


def _summary(models: Mapping[str, object], name: str) -> Mapping[str, object]:
    return _section(_section(models, name), "summary")


def _shift_text(count: Mapping[str, object]) -> str:
    shift = count.get("mean_shift_training_standard_deviations")
    if shift is None:
        return "Not available: the training report count has no variation"
    return f"{_number(shift, 'report-count mean shift'):.3f} training standard deviations"


def _count_table(count: Mapping[str, object]) -> list[str]:
    lines = [
        "| Population | Programs | Mean reports | Population standard deviation | "
        "Minimum | Maximum |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for period in ("training", "evaluation"):
        row = _section(count, period)
        values = [
            _numeric(row, key)
            for key in ("n", "mean", "population_standard_deviation", "minimum", "maximum")
        ]
        lines.append(
            f"| {period.capitalize()} | {values[0]:.0f} | {values[1]:.3f} | "
            f"{values[2]:.3f} | {values[3]:.0f} | {values[4]:.0f} |"
        )
    lines += [
        "",
        "The mean change from training to evaluation is " + _shift_text(count) + ".",
        "A training standard deviation describes how much report count varied among training "
        "programs; it uses the population definition (ddof=0).",
        "",
        "![Earlier available reports](report_counts.svg)",
    ]
    return lines


def _error_table(models: Mapping[str, object]) -> list[str]:
    lines = [
        "| Approach | Programs | Average absolute error | Average signed error | "
        "Volume-weighted absolute error |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in _MODELS:
        summary = _summary(models, name)
        lines.append(
            f"| {_label(name)} | {_numeric(summary, 'n'):.0f} | "
            f"{_numeric(summary, _MAE):.3f} | "
            f"{_numeric(summary, 'mean_signed_error_percentage_points'):.3f} | "
            f"{_numeric(summary, 'candidate_volume_weighted_mae_percentage_points'):.3f} |"
        )
    return lines


def _contrasts_table(contrasts: Sequence[object]) -> list[str]:
    if len(contrasts) != 12:
        raise ValueError("Follow-up report requires all 12 fixed contrasts.")
    lines = [
        "| Challenger minus comparator | Error difference | Descriptive 95% interval |",
        "|---|---:|---:|",
    ]
    for item in contrasts:
        row = _mapping(item, "contrast")
        challenger, comparator = str(row.get("challenger")), str(row.get("comparator"))
        if challenger not in _MODELS or comparator not in _MODELS:
            raise ValueError("Follow-up report contrast names must identify fixed models.")
        lines.append(
            f"| {_label(challenger)} minus {_label(comparator)} | "
            f"{_numeric(row, 'point_estimate'):.3f} | "
            f"[{_numeric(row, 'lower'):.3f}, {_numeric(row, 'upper'):.3f}] |"
        )
    return lines


def _contribution_tables(models: Mapping[str, object]) -> list[str]:
    lines = [
        "The following values show which inputs move each original model's average calculation "
        "between training and evaluation. They are on the logit scale, before conversion to a "
        "percentage: coefficient × change in the mean standardized input. The same training "
        "imputation and scaling apply to both populations; the intercept cancels.",
        "",
        "These are not patient effects and are not directly additive percentage-point changes. "
        "`historical_target_count` means the number of earlier available reports. Other exact "
        "input names are retained so these tables can be checked against the evidence JSON.",
    ]
    for group in _GROUPS:
        name = f"original_{group}"
        model = _section(models, name)
        contributions = _section(model, "contributions")
        features = _section(contributions, "by_feature")
        lines += [
            "",
            f"### {_label(name)}",
            "",
            "| Input | Contribution to mean predicted logit change |",
            "|---|---:|",
            *[f"| `{key}` | {_number(value, key):.6f} |" for key, value in features.items()],
            f"| Sum of contributions | {_numeric(contributions, 'sum'):.6f} |",
            "| Mean predicted logit change | "
            f"{_numeric(contributions, 'mean_predicted_logit_change'):.6f} |",
        ]
    return lines


def _takeaway(models: Mapping[str, object]) -> str:
    original = _numeric(_summary(models, "original_history_acceptance"), _MAE)
    revised = _numeric(_summary(models, "revised_history_acceptance"), _MAE)
    historical = _numeric(_summary(models, "historical_mean"), _MAE)
    return (
        f"For history plus acceptance, average absolute error is {original:.3f} percentage points "
        f"with report count and {revised:.3f} after removing it; the historical mean is "
        f"{historical:.3f}. The revised-minus-original change is {revised - original:+.3f} "
        f"percentage points, and revised-minus-historical-mean is {revised - historical:+.3f}. "
        "A negative change means a smaller observed error. These describe the specified "
        "comparison and do not select or promote a model."
    )


def _report(evidence: Mapping[str, object], models: Mapping[str, object]) -> bytes:
    populations = _section(evidence, "populations")
    training_n = len(_items(populations.get("training"), "training population"))
    evaluation_n = len(_items(populations.get("evaluation"), "evaluation population"))
    excluded_n = len(_items(populations.get("excluded"), "excluded population"))
    reconstruction = _section(evidence, "reconstruction")
    lines = [
        "# V2 follow-up: earlier reports and prediction errors",
        "",
        f"> {_BANNER}",
        "",
        f"Study: `{evidence.get('analysis_id')}`. "
        f"Evidence status: `{evidence.get('evidence_status')}`.",
        "",
        "This separate exploratory investigation uses outcomes already inspected in the original "
        "V2 study. Uncommitted builds are development evidence. Original V1 and V2 results remain "
        "preserved. Model promotion is prohibited and no future forecast is available.",
        "",
        "## People, programs and dates counted",
        "",
        "One record represents a kidney transplant program and July–June listing group. "
        "The outcome is SRTR's published percentage of the original listing group known alive "
        "with a functioning transplant 18 months after listing (`SAL_TOTFTX_C18`, denominator "
        "`SAL_N_C`). Unknown status remains unknown; it is not a zero outcome.",
        "",
        f"Training includes {training_n} programs in July 2019–June 2020 (1905→2205); "
        f"evaluation includes {evaluation_n} programs in July 2022–June 2023 (2205→2505). "
        "The training outcome report was public in July 2022, by the evaluation prediction "
        "origin; the evaluation outcome report was published July 8, 2025. There is only "
        "one historical evaluation period. Every approach uses the same evaluation programs "
        "and every fitted model uses the same training programs. Missing predictors do not "
        "exclude programs; imputation and scaling are learned from training only.",
        "",
        f"Excluded records: {excluded_n}. Exact included/excluded keys, eligibility reasons, "
        "missingness, coefficients, imputation values and scaling parameters are retained in "
        "the companion evidence JSON. Exclusions can include other listing periods and do not "
        "represent a national program-closure count.",
        "",
        "## Original prediction check",
        "",
        f"Reconstructed {_numeric(reconstruction, 'prediction_rows'):.0f} stored prediction rows "
        f"across all five original Ridge models and three baselines. The largest absolute "
        f"difference was {_numeric(reconstruction, 'max_absolute_difference'):.3g} on the "
        f"proportion scale; the fixed absolute tolerance is "
        f"{_numeric(reconstruction, 'absolute_tolerance'):.3g} with zero relative tolerance. "
        "This check precedes interpretation or revised fitting.",
        "",
        "## How the number of earlier reports changes",
        "",
        *_count_table(_section(evidence, "report_count")),
        "",
        "## All fixed comparisons",
        "",
        "The revision removes only the number of earlier available reports "
        "(`historical_target_count`) from each of the five original Ridge input groups. "
        "All other input rules, populations, transformations and Ridge settings remain fixed.",
        "",
        "All errors below use percentage points. Average absolute error (MAE) ignores the "
        "direction of each error. Positive signed error means predictions are too high on "
        "average. Volume weighting emphasizes programs with larger listing groups; it does "
        "not measure individual patient accuracy. With one evaluation release, release-balanced "
        "MAE is the ordinary average across the evaluation programs.",
        "",
        *_error_table(models),
        "",
        _takeaway(models),
        "",
        "![All model errors against historical mean](model_errors.svg)",
        "",
        "## Paired differences and their limits",
        "",
        "All 12 specified contrasts follow, in fixed order. Differences are challenger minus "
        "comparator MAE, in percentage points; negative values favor the challenger. The "
        "descriptive 95% intervals use 2,000 whole-program resamples, seed 20260904, and linear "
        "2.5th/97.5th percentiles. Each comparison resamples both approaches on the same programs.",
        "",
        *_contrasts_table(_items(evidence.get("contrasts"), "contrasts")),
        "",
        "These intervals describe variation among the observed programs in one period. "
        "They cannot establish performance in a new period or convert already-inspected "
        "outcomes into independent or prospective validation. Added acceptance information "
        "does not establish a causal effect or a reason to change patient care.",
        "",
        "## What moved the original fitted calculations",
        "",
        *_contribution_tables(models),
        "",
        "## Source and reproducibility",
        "",
        _SOURCE,
        "[SRTR public reports](https://srtr.hrsa.gov/transplant-professionals/"
        "program-specific-report/program-specific-reports-psr/). "
        "The completion manifest records source and original bundle hashes, configuration "
        "identities, implementation and dependency-lock hashes, Git status, build time in UTC, "
        "cohorts, model inputs and fitted parameters. This report does not replace those records.",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def _figure_files(figure: Figure, stem: str) -> dict[str, bytes]:
    outputs = {}
    for extension in ("svg", "png"):
        buffer = BytesIO()
        metadata = {"Date": None} if extension == "svg" else {}
        figure.savefig(buffer, format=extension, dpi=150, metadata=metadata)
        outputs[f"{stem}.{extension}"] = buffer.getvalue()
    return outputs


def _count_figure(count: Mapping[str, object]) -> Figure:
    figure = Figure(figsize=(10, 6.4), facecolor="white")
    axes = figure.add_axes((0.10, 0.23, 0.85, 0.54))
    training = _section(_section(count, "training"), "frequencies")
    evaluation = _section(_section(count, "evaluation"), "frequencies")
    values = sorted({int(value) for value in (*training, *evaluation)})
    for index, (frequencies, color, label) in enumerate(
        ((training, "#596B7A", "Training"), (evaluation, "#087E8B", "Evaluation"))
    ):
        positions = [value + (index - 0.5) * 0.36 for value in values]
        bars = axes.bar(
            positions,
            [_number(frequencies.get(str(value), 0), "report-count frequency") for value in values],
            width=0.34,
            color=color,
            label=label,
        )
        axes.bar_label(bars, fmt="%.0f", padding=3, fontsize=9)
    axes.set_xticks(values)
    axes.set_xlabel("Number of earlier available reports", labelpad=9)
    axes.set_ylabel("Number of programs")
    axes.margins(y=0.18)
    axes.legend(frameon=False)
    axes.spines[["top", "right"]].set_visible(False)
    figure.text(0.10, 0.93, "How many earlier reports were available?", fontsize=17, weight="bold")
    figure.text(
        0.10,
        0.86,
        "V2 follow-up • exploratory • fixed training and evaluation populations",
        fontsize=11,
    )
    figure.text(0.10, 0.81, _shift_text(count), fontsize=11)
    train_n = _numeric(_section(count, "training"), "n")
    evaluation_n = _numeric(_section(count, "evaluation"), "n")
    figure.text(
        0.10,
        0.12,
        f"Training: July 2019–June 2020, {train_n:.0f} programs\n"
        f"Evaluation: July 2022–June 2023, {evaluation_n:.0f} programs",
        fontsize=9,
    )
    figure.text(
        0.10, 0.055, "Source: SRTR public reports; verified original V2 bundle.", fontsize=8
    )
    figure.text(0.10, 0.025, _BANNER, fontsize=8)
    return figure


def _error_figure(models: Mapping[str, object]) -> Figure:
    figure = Figure(figsize=(12, 9.5), facecolor="white")
    axes = figure.add_axes((0.34, 0.25, 0.59, 0.58))
    errors = [_numeric(_summary(models, name), _MAE) for name in _MODELS]
    colors = ["#596B7A"] * 5 + ["#087E8B"] * 5 + ["#9C621A"] * 3
    bars = axes.barh([_label(name) for name in _MODELS], errors, color=colors, height=0.67)
    axes.bar_label(
        bars,
        fmt="%.3f",
        padding=4,
        fontsize=9,
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.5},
    )
    historical = _numeric(_summary(models, "historical_mean"), _MAE)
    axes.axvline(historical, color="#593B14", linestyle="--", linewidth=1.5)
    axes.invert_yaxis()
    axes.set_xlim(0, max(max(errors) * 1.18, 1.0))
    axes.set_xlabel("Average absolute error (percentage points)", labelpad=10)
    axes.spines[["top", "right"]].set_visible(False)
    figure.text(0.07, 0.94, "How large were the prediction errors?", fontsize=18, weight="bold")
    figure.text(
        0.07,
        0.90,
        "V2 follow-up • exploratory • all 13 approaches in fixed study order",
        fontsize=11,
    )
    population_n = _numeric(_summary(models, "historical_mean"), "n")
    figure.text(
        0.07,
        0.865,
        f"July 2022–June 2023 listing group • {population_n:.0f} programs • one evaluation period",
        fontsize=10,
    )
    figure.text(
        0.07,
        0.16,
        f"Dashed line: historical mean, {historical:.3f} percentage points. "
        "Smaller error means closer to the published outcome.",
        fontsize=10,
    )
    figure.text(
        0.07,
        0.12,
        "Outcome: percentage of the original listing group known alive with a functioning "
        "transplant at 18 months.\nOriginal models include report count; revised models remove "
        "only report count. No model promotion.",
        fontsize=10,
    )
    figure.text(
        0.07,
        0.065,
        "Source: SRTR public reports; verified original V2 bundle. "
        "Outcomes published July 8, 2025.",
        fontsize=9,
    )
    figure.text(0.07, 0.035, _BANNER, fontsize=9)
    return figure


def render_followup_report(evidence: Mapping[str, object]) -> dict[str, bytes]:
    """Render the fixed follow-up without altering its numerical evidence.

    The report and both figures identify dates, populations and units. A
    report-count shift with zero training variation stays unavailable rather
    than acquiring a numeric zero. The caller owns output paths and provenance.
    """
    if (
        evidence.get("promotion_allowed") is not False
        or evidence.get("future_forecast_available") is not False
    ):
        raise ValueError(
            "Follow-up reporting requires promotion and future forecasts to remain prohibited."
        )
    models = _section(evidence, "models")
    for name in _MODELS:
        _summary(models, name)
    outputs = {"report.md": _report(evidence, models)}
    with rc_context(
        {
            "svg.hashsalt": "kasm-v2-followup-report-count-v1",
            "svg.fonttype": "none",
            "font.family": "DejaVu Sans",
            "font.size": 10,
        }
    ):
        outputs.update(
            _figure_files(_count_figure(_section(evidence, "report_count")), "report_counts")
        )
        outputs.update(_figure_files(_error_figure(models), "model_errors"))
    return outputs
