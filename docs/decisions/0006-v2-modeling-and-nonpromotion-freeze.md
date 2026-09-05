# Decision 0006 — Freeze one-fold V2 modeling without promotion

**Status:** accepted
**Date:** 2026-09-04

## Context

The patient-journey panel contains four contiguous, non-overlapping July–June target cohorts, but
strict publication-vintage evaluation leaves only one Ridge origin with an earlier published
training outcome. At the `2205` origin, the `1905→2205` outcome is public and can train a model for
the `2205→2505` evaluation cohort. Earlier origins have no published primary-pair truth. Treating
cohort order as availability would create an anachronistic backtest.

Several remaining modeling choices were also underspecified: the cohort baseline name, exact
feature transforms, Ridge regularization, comparison population, calibration orientation, volume
strata, and clustered-bootstrap implementation. Those choices must be fixed before real target-
comparison results are inspected.

## Decision

Use the exact current retrospective evaluation contract in Section 7 of
`docs/specs/patient-journey-v2.md` and serialize it in
`configs/patient_journey_v2/experiment.yaml`.

Evaluate the three baselines on all four primary-pair eligible populations. Call the feature-
release aggregate the **available-cohort reference** because it is reconstructed from published
program counts and percentages; it is not an official published national statistic. Evaluate the
five fixed Ridge feature groups only on `2205→2505`, trained only on `1905→2205`, with identical
rows across groups and fold-local preprocessing.

Fit Ridge to the empirical-logit target with fixed `alpha=1.0`, `lsqr`, `tol=1e-8`, and
`max_iter=10000`. Report authoritative published percentages on the percentage-point scale. Use
the specified target-release-balanced metrics, calibration orientation, deterministic within-
release N quartiles, N-threshold sensitivities, and 2,000-resample program-clustered paired
bootstrap.

Only waiting-list mortality is eligible for the current secondary safety feature group because it
is present at both the training and evaluation feature vintages. Mortality-after-listing and graft-
failure measures are retained as separately timed descriptive context and cannot be substituted
for the Table B7 outcome or combined into a score.

Set `promotion_allowed: false`. The current Ridge comparison is retrospective one-fold feasibility
evidence, not stable temporal validation, an operational forecast, or a basis for changing the V1
default.

## Consequences

The completed V2 can answer whether access and acceptance add signal in the sole historically
reproducible fold, with appropriately limited uncertainty, but it cannot establish temporal
stability or promote a model. A future same-cadence release requires a new prospectively locked
plan and configuration before its outcomes are inspected.

The feature allowlists and contrasts are fixed rather than selected from results. Missing source
values remain in the common comparison population and are handled inside the training-fold
pipeline. All generated modeling and release artifacts stay under V2-owned roots and carry the
configuration hash that identifies this freeze.
