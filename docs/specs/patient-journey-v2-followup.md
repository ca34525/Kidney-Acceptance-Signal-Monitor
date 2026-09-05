# V2 follow-up — Report count and the fixed revised comparison

**Version:** 1.0, 2026-09-05 UTC. **Scope:** Plan 0020 P1/P2.

This separate exploratory investigation asks whether acceptance information still helps predict
the published 18-month functioning-transplant percentage after removing an input that counts
earlier available reports. The outcomes have already been inspected. This is not fresh validation,
patient-level accuracy, a causal analysis, or grounds for model promotion.

## Records and population

The study identifier is `kidney_patient_journey_v2_followup_report_count_v1`. Its fixed settings
are in [the follow-up configuration](../../configs/patient_journey_v2_followup/experiment.yaml).
The original [V2 specification](patient-journey-v2.md), configuration, methodology ledger, panel,
predictions, evaluation and released bundle remain unchanged. V1 is also preserved; its frozen
replay must not run. The current user request authorizes this local P1/P2 implementation and its
ignored outputs, not a new tracked release or a product change.

Read the original trusted release at `artifacts/patient_journey_v2`, pinned by its bundle hash
`ce2844edbcec92c09d0053720d5331dd37ed43ab75de7aa4dd1de431c79a9eee` and original experiment hash
`ab8c01453c36039b293a8e7453b17b2b326faf734a081a4b67f8bfe132b1de79`. Verify the bundle and its
configuration/source/ledger bindings before computing. Do not rebuild or replace original inputs.

One row represents a kidney transplant program and July–June listing group, joined by
`(CTR_CD, CTR_TY)`. The target remains the published `SAL_TOTFTX_C18`, a percentage of the
original `SAL_N_C` listing group known alive with a functioning transplant 18 months after listing.
Unknown status remains unknown. Evaluation uses published percentage points; model fitting keeps
the original empirical-logit transform and never replaces the published target.

Use exactly the original `primary_analytic_eligible` rows. Fit only `1905→2205` (the July 2019–June
2020 listing group), evaluate only `2205→2505` (July 2022–June 2023), and sort by composite program
key. The earlier training outcome was public in July 2022, by the evaluation prediction origin.
Retain the original publication precision, measurement cutoffs and four non-overlapping primary
panel cohorts. Other pairs cannot enter fitting. Save included/excluded row keys and original
eligibility, plus missingness for each input group; never remove rows for missing predictors.

## Fixed calculations, recorded before execution

1. Reconstruct all five original Ridge groups with their exact ordered features and fixed
   preprocessing/settings. Compare every original Ridge evaluation prediction and all three
   evaluation-period baselines with stored predictions by program, feature release, target release,
   and model. Duplicate/missing/extra keys, disagreeing target counts/outcomes, nonfinite values,
   or an absolute prediction difference above `1e-10` on the proportion scale fail the run;
   relative tolerance is zero. Perform this check before interpreting weights or fitting revisions.
2. Describe report count for training and evaluation: frequency, mean, population standard
   deviation (`ddof=0`), minimum and maximum. Express the mean change in training standard
   deviations; if the training standard deviation is zero, report unavailable with a reason.
3. For each original fitted group, use training imputation and scaling to calculate
   `coefficient[j] * (mean(standardized_evaluation[j]) - mean(standardized_training[j]))`.
   These contributions sum to the mean change in predicted logit; the intercept cancels.
   Check this identity with absolute tolerance `1e-10`. Report coefficients, imputation values,
   scaler means/scales, missing counts and feature schemas. Contributions describe the model's
   calculation before conversion to percentages. They are neither patient effects nor directly
   additive percentage-point changes.
4. Remove only `historical_target_count` from each of the five ordered Ridge input groups.
   Keep it in descriptive data. Keep the remaining features, empirical-logit target, training and
   evaluation programs, median imputation with empty-feature retention, training-only
   standardization, `alpha=1`, `solver=lsqr`, `tol=1e-8`, `max_iter=10000`, and inverse logistic
   link. Do not modify the original feature allowlist or select a new model/window after results.
5. Report all original and revised groups, historical mean, persistence, and available-cohort
   reference on the same evaluation population. Report average absolute error, signed error
   (`prediction - observed`), and candidate-volume-weighted absolute error in percentage points.
   Positive signed error means predictions are too high. Weighting emphasizes programs with
   larger listing groups; it does not measure individual patient accuracy.
6. Reuse the original paired program bootstrap: 2,000 resamples, seed `20260904`, linear 2.5th and
   97.5th percentiles, challenger minus comparator average absolute error. The fixed contrasts
   are original history+acceptance versus historical mean; each revised group versus its original;
   all five original incremental contrasts applied to revised groups; and revised
   history+acceptance versus historical mean. Preserve paired keys and target agreement.
   These descriptive intervals reflect variation among observed programs in one period, not
   performance uncertainty in a new period. Favorable results are not a completion requirement.

## Output and safety boundary

The sole output root is `data/patient_journey_v2_followup/report_count_v1`. Each complete run uses
a new hash-addressed directory derived from configuration, original bundle and implementation
identities. Refuse overwrite, including an existing empty destination; build in a fresh sibling
staging directory, then publish the complete result atomically. Failed runs cannot publish a
completion manifest. Validate paths again at the writer, reject traversal, absolute destinations,
symlinks/junctions and any path reaching an original study or outside this fixed output root.

Save comparison predictions, exact population/missingness evidence, diagnostic and metric JSON,
a readable report, and two figures: report-count frequencies at training/evaluation and all
model errors against the historical-mean reference. Figures identify the population, period,
units and exploratory study. This root stays ignored; no new release root is approved.

The completion manifest includes all output sizes/hashes, source hashes, original bundle/payload
hashes, both configuration hashes, methodology and dependency-lock hashes, Git commit, dirty
worktree status, implementation file hashes, UTC build time, cohort timing, feature schemas and
model parameters. Uncommitted builds explicitly remain development evidence. Deterministic
analytical payloads must reproduce; build timestamps may differ. Preserve no serialized models.

## Acceptance and later work

Use constructed cases for report-count shifts, reconstruction tampering, pair mismatches,
training-only preprocessing, count exclusion, and filesystem/input failures. Run focused tests,
required full checks and a real offline build. Record commands and results in
[Plan 0020](../plans/0020-v2-follow-up-and-interview-story.md), and explain whether the original
interpretation changes. Neither original artifact/configuration nor future-forecast availability
may change. P3 outcome-component analysis and P4 presentation/rehearsal remain separate work.
