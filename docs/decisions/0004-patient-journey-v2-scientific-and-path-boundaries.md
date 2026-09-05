# Decision 0004 — Separate the patient-journey v2 study from frozen v1

**Status:** accepted
**Date:** 2026-09-04

## Reading this historical record — 2026-09-05

This decision keeps two different questions and their files separate. V2's denominator is the
original group of newly listed candidates, and its outcome is the published percentage known
to be alive with a functioning transplant 18 months after listing. Unknown follow-up is not proof
that a candidate was alive or had died. Program totals lack the patient-level details needed to
adjust individual risk. Safety measures describe different groups or follow-up periods and cannot
be substituted for parts of this outcome. A secondary "ablation" means a fixed comparison with
an additional earlier input group; it does not identify the effect of an intervention.

## Context

V1 forecasts the next published offer-acceptance ratio and has completed, hash-bound retrospective
evidence. The proposed v2 question instead forecasts the observed percentage of newly listed
kidney candidates alive with a functioning transplant at 18 months. Reusing v1 output or claim
paths would risk overwriting frozen evidence or implying that the raw patient-centered target is an
officially risk-adjusted quality measure.

The public workbooks contain program aggregates, not the patient-level joint covariates, time at
risk, censoring, interactions, and national reference data required to recreate SRTR-style risk
adjustment. Published safety metrics also use cohorts and follow-up windows that differ from the
status-after-listing target.

## Decision

Treat v2 as a separate, retrospective exploratory study with `SAL_TOTFTX_C18 / 100` as its primary
observed outcome. Access and prior outcome history are the primary predictor families; acceptance
is an incremental predictor family. Aggregate candidate-mix work, if later approved, is labeled a
sensitivity analysis rather than risk adjustment.

Keep safety measures as separate outcomes first. A safety metric may enter only a prespecified
secondary lagged-feature ablation after code proves it was public by the prediction origin and its
measurement ended before the target listing cohort began.

Declare v2 output roots in a dedicated configuration and validate them before any v2 writer runs.
Reject any output root that is absolute, traverses outside the repository, or overlaps a protected
v1 root in either direction. Preserve the existing source manifest/cache as shared read-only input.

## Consequences

V1 configuration, generated data roots, frozen replay, release bundle, and default app behavior stay
unchanged. V2 results cannot be called causal, officially risk-adjusted, confirmatory, prospective,
or a fair program ranking. Separate paths add some configuration and release-management work, but
make accidental v1 overwrite a hard error rather than a review convention.
