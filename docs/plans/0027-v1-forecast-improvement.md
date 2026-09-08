# Plan 0027 — Understand and improve V1 forecasts

**Status:** planning and documentation complete; execution not started.
**Date:** 2026-09-08. **Branch:** `codex/v1-forecast-improvement`.
**Authorized now:** write this plan and clarify future model-promotion policy.
**Contract:** [specification](../specs/acceptance-forecast-0027.md) and
[Decision 0013](../decisions/0013-revise-future-forecast-promotion.md).

## Purpose and decisions

Improve forecasts of the next published annual offer-acceptance ratio and explain their
errors in ordinary language. Begin with the distribution of existing errors, then choose a
small set of changes. Reducing average signed error alone is not the objective. Promotion
is a later decision and may select the existing Ridge model even if its absolute mean
signed error remains greater than persistence's under the revised policy.

The current V1 release and its frozen evidence remain intact. New work has its own identity;
the original bias-rule failure remains reported. Original V2 and the completed receipt and
waiting-list studies are outside scope. This plan does not run an analysis or change the app.

Existing evidence motivating the work:

- V1 Ridge reduced 2025 log-scale average absolute error by 10.13%; its original-scale
  average error was 0.2398 ratio units versus persistence's 0.2666. The only failed original
  point criterion was the exact bias comparison, 0.01145 versus 0.00885.
- Saved errors vary by year and earlier expected-acceptance volume. Small overall signed
  error can hide opposing errors and much larger individual misses.
- The saved summaries do not yet supply the full median/tail/within-tolerance explanation
  agreed for this follow-up. These are new descriptions of already-inspected predictions,
  not new validation.

Use the [model card](../model_card.md) and retained
[yearly diagnostics](../../artifacts/release/modeling/ridge_metrics.json) as the source of
these observations. Do not refit the original study to reproduce them.

## Work order and acceptance

| Step | Deliverable and acceptance evidence | State |
|---|---|---|
| P0 Document scope and policy | Plan, specification, decision and consistent current documentation distinguish the original fail from permissible future promotion | Complete |
| P1 Explain existing errors | Typed diagnostic settings, verified saved inputs, reproducible ratio/percentage/log distributions and small regression fixtures | Not started |
| P2 Fix the comparison | Diagnostic-led rationale, enumerated candidates, exact temporal design and justified decision tolerances recorded before comparison scoring | Not started |
| P3 Compare complete procedures | Failing regressions first; matched forward-in-time predictions, every configured result and required verification | Not started |
| P4 Make the model decision | Clear accuracy/error-distribution tradeoff and versioned retain/select/insufficient-evidence recommendation; separate deployment handoff if selected | Not started |

### P1 — Make the existing errors understandable

Implement diagnostic settings under `configs/acceptance_forecast/` before calculation. Bind
the trusted V1 release and prediction payloads, their hashes, 2021–2024 backtests and separate
2025 replay, original training roles, populations, percentile interpolation and strata.
Establish the separate ignored output root `data/research/acceptance-forecast-0027/` and
reproducible run/provenance identity described in the specification. Search existing loaders,
types and call sites before adding a small importable analysis module and CLI boundary.

Deliver per-year tables and full-range plots of signed and absolute errors, with medians,
middle 80% signed intervals, 90th/95th absolute percentiles and counts within ±10%, ±25% and
±50% of the published ratio. Include original ratio-unit and log-unit measures, paired
improvement/worsening distributions and earlier-volume/ratio/missingness breakdowns. Avoid
an overwhelming collection of plots: the main brief should show typical error, large misses
and where error differs; retain complete supporting tables.

**Acceptance:** a reader can state how far a typical prediction misses, how large the worst
tenth of errors are, how often Ridge improves/worsens persistence on the named error scale,
and which earlier characteristics accompany larger errors. Percentages name the published ratio as their
denominator. Counts, exclusions, first-observed/forecast eligibility, years and model-fit
differences remain visible. No fits or altered original metrics are needed for this step.

### P2 — Select a small set of changes and fix its evaluation

Record which findings motivate each candidate and which concerns remain unresolved. Consider
simple calibration, a fitted adjustment of recent history, or altered training-history
weighting; do not assume all are needed. The current target, public sources and shared
scientific safeguards remain fixed. Preserve persistence, historical mean and existing Ridge
as references, including corrected persistence when testing a generic correction.

Write typed comparison settings and extend the specification before scoring. Fix the exact
candidate list/limit, inputs, losses, tuning grids, temporal and publication cutoffs,
calibration and band roles, same-row comparisons, exclusions, aggregation, uncertainty
method and stopping rule. Separately identify an original frozen fit and any refit using
newer training outcomes. Keep selection/tuning inside earlier data for each evaluated origin.

Define useful primary accuracy improvement and acceptable absolute bias or bias deterioration
with a practical rationale. Also fix worst-year, tail/subgroup and uncertainty treatment;
do not silently substitute a favorable metric when another worsens. The ±10/25/50% diagnostic
fractions are not automatically promotion thresholds. No exact bias tolerance or new model
is selected in this planning pass; choosing them follows the error description.

**Acceptance:** another analyst can execute the configured comparison without deciding which
model, years, correction window, error metric or tolerance would make the result favorable.
Document that choices were informed by inspected historical data; do not claim an untouched
test or a newly prespecified original replay. Once this comparison is fixed, report every
candidate and end it before any further design revision.

### P3 — Evaluate the forecasting procedure

Implement the smallest configured changes, preserving a failing regression before each new
behavior. Reuse verified source/panel inputs; no live refresh, canonical replay invocation
or original-release overwrite. Fit preprocessing, model and any correction using only
information permitted at each origin. A chronological split alone does not repair an
adjustment estimated using the evaluated outcomes.

Report every year, the year-balanced primary metric, ratio/percentage distributions, paired
win/tie/loss and large worsening, calibration and selected subgroup results. Use whole-program
paired resampling across repeated years. Evaluate bands for the final procedure separately.
Preserve unfavorable candidates and explain tradeoffs rather than searching until one wins.

**Acceptance:** the complete configured procedure is reproducible from trusted inputs; all
models share the declared evaluation population; no later information enters a fit or
correction; tests, lint, types and the relevant authorized backtest pass. Historical results
remain exploratory even when gains are consistent across years.

### P4 — Decide what merits display

Apply the revised configured policy and explain whether to retain persistence, select the
existing Ridge method, select a revised method, or defer selection. A model can be selected
despite failing the original exact bias comparison. Show original and revised decisions
together, describe the numerical tradeoff and limits, and state what later evidence could
change the recommendation. Unseen prospective data are desirable evidence, not a mandatory
waiting period for an honestly retrospective product decision.

**Acceptance:** the recommendation follows the recorded policy and is intelligible in ratio
and percentage-error terms. If display is recommended, define a separate implementation
item for a new trusted release identity, artifact provenance, explicit eligibility,
point/band handling, offline app behavior and a reversal path. This plan's documentation
completion is not deployment or a claim that predictive improvement has been achieved.

## Verification and current evidence

P0 is documentation-only. A failing software test would not meaningfully exercise this
policy clarification; the test-first exception is content review, checked links and
`git diff --check`. No executable configuration, source manifest, code, model or artifact is
changed, so model reproduction and the Python suite are not appropriate for P0.

For P1–P3, use synthetic fixtures for ratio-versus-percentage units; signed/absolute means;
asymmetric over/underprediction; boundary-inclusive tolerances; ties, extremes and small
positive denominators; null/nonfinite/nonpositive values; equal-year versus row-pooled
summaries; paired populations; input corruption/path escape; fold publication availability;
training-only calibration/tuning; and preserved original output paths. Include band
reassessment and future-promotion policy regressions when those behaviors are implemented.
Preserve the original fixed-gate regression and add a separate case where a candidate with
higher absolute bias than persistence passes a justified new tolerance, plus cases where
the new accuracy, bias or display requirements fail.

Run the full checks in [AGENTS.md](../../AGENTS.md#8-required-verification) for executable
changes, plus the authorized isolated backtest for modeling changes and trusted packaging/
offline startup for any later deployment. Record actual commands and outcomes here as each
step completes; do not run the frozen-replay command as a routine check.

P0 completed on 2026-09-08:

- Content review covered policy consistency, metric units, error distributions, timing,
  original-result preservation and the boundary between planning and execution. An
  independent review prompted explicit log-scale win/tie/loss definitions.
- A local Markdown checker validated 110 relative links, including heading anchors,
  across all nine changed/new documents; new-document whitespace checks passed.
- `git diff --check` passed. `git diff --exit-code -- configs artifacts src app tests uv.lock`
  confirmed no changes to executable settings, original evidence, implementation or lockfile.
- The Python suite, model fitting, frozen replay and application startup were not run:
  this change is documentation-only. No P1–P4 work has run.
