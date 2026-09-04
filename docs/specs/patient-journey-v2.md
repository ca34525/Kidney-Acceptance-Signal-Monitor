# Kidney Patient-Journey Forecast — v2 Scientific Specification

**Specification version:** 0.2
**Status:** Approved for phased implementation
**Specification date:** 2026-09-04
**Primary audience:** Transplant-program quality and performance staff

## 1. Version boundary

This specification defines a separate v2 patient-journey study. It does not replace the v1
Kidney Acceptance Signal Monitor specification.

The following v1 assets are immutable inputs to this work and may not be overwritten, rerun, or
silently reinterpreted by a v2 workflow:

- `configs/experiment.yaml`;
- `configs/frozen_experiment.yaml`;
- `data/processed/` and `data/modeling/`;
- `artifacts/release/`; and
- the default v1 Streamlit behavior.

V2 may reuse the pinned source manifest and verified source cache. Its configuration, processed
data, modeling output, and any future release bundle use distinct paths. V2 must remain optional
until an explicit product decision changes the default application.

## 2. Research question and intended use

The primary question is:

> Can previously published program-level signals forecast the percentage of newly listed kidney
> candidates who are alive with a functioning transplant 18 months later, and how much predictive
> information comes from access measures versus offer acceptance?

The intended use is exploratory quality-improvement review of a multidimensional patient journey.
The study forecasts a later published program-level outcome; it does not estimate a program's
causal effect, intrinsic quality, patient-level benefit, safety, or regulatory standing.

The central comparisons are:

1. persistence and prior-outcome history versus more complete public-data forecasts;
2. history plus access versus history alone;
3. access plus acceptance versus access without acceptance; and
4. access plus acceptance versus a secondary model that also includes eligible lagged safety
   measures.

A negative incremental result is scientifically valid and must be reported plainly.

## 3. Primary target and claim boundary

The primary target is the SRTR status-after-listing program percentage
`SAL_TOTFTX_C18`, "Functioning transplant (alive)" at 18 months. The canonical proportion is
`SAL_TOTFTX_C18 / 100` after source parsing and validation.

This is a patient-centered observed outcome, not a published risk-adjusted program measure. Product
and model documentation may call it a published 18-month functioning-transplant percentage or an
observed patient-journey outcome. It may not be labeled a risk-adjusted outcome, fair center
comparison, SRTR-equivalent adjustment, causal effect, or composite quality score.

The published percentage is authoritative. Candidate counts reconstructed from `SAL_N_C` may be
used only for rounding reconciliation and a boundary-safe empirical-logit transform:

```text
successes = round(target_n * published_percent / 100)
smoothed_p = (successes + 0.5) / (target_n + 1)
target_logit = log(smoothed_p / (1 - smoothed_p))
```

Evaluation is reported on the published percentage-point scale. The transform must not replace the
published value.

## 4. Source scope and program identity

Use the nine pinned kidney PSR releases in `configs/data_sources.yaml`: `1808`, `1905`, `2006`,
`2105`, `2205`, `2305`, `2405`, `2505`, and `2605`. Ordinary tests and application startup do not
access the network. Downloaded workbooks remain immutable and checksum-verified.

Program identity remains `(CTR_CD, CTR_TY)`, serialized as `center_code:center_type`. Names and
locations are display fields only and may not be join keys or model features. A combined program
identifier from a source sheet must be parsed with an explicit validated pattern and reconciled
against a same-release sheet containing separate code and type fields.

The required v2 metric families are:

| Family | Core measure | Role |
|---|---|---|
| Patient-centered history | `SAL_TOTFTX_C18`, `SAL_N_C` | Target and persistence history |
| Access | `TX_RR`, `TMR_TxPy_c`, `TTT_25_C` | Primary predictors and context |
| Acceptance | Overall OAR, expected acceptances, interval, donor strata | Predictor ablation and context |
| Safety | Published mortality and graft-failure ratios with intervals | Separate outcomes; eligible lags only in a secondary ablation |
| Candidate mix | Stable prior-release Tables B2–B3 summaries | Optional P1 aggregate sensitivity only |

The 25th-percentile time-to-transplant field is the primary wait-time feature. Suppressed strings,
including `Not Observed` and values such as `>72`, remain missing until an explicitly specified
normalization step; they never become zero.

## 5. Cohort timing and leakage controls

V2 uses one row per `program_key × target_listing_cohort`. All rows for one target release remain in
the same temporal fold. Random row splitting is prohibited, and statistical uncertainty is
resampled by program.

Every feature must satisfy both conditions before it may enter the primary matrix:

```text
feature.available_at <= prediction_origin
feature.measurement_end < target_listing_cohort_start
```

If a metric's follow-up makes the second condition impossible, exclude it from the primary feature
matrix and retain it only as a separate outcome. Same-cohort Table B7 status components, target-
period values, future report availability, identity fields, and location fields are prohibited
predictors.

A metric-level methodology ledger must record release code, publication value and precision,
source sheet, measurement start/end, follow-up end, earliest public availability, definition or
method changes, and relevant COVID-era or policy context. Release-index proximity alone does not
establish temporal validity.

The initial candidate feature-to-target release pairs to verify are `1905→2205`, `2006→2305`,
`2105→2405`, `2205→2505`, and `2305→2605`. The `1808→2105` pair remains excluded unless the ledger
proves that the feature release preceded the target listing-cohort start.

The release-level methodology audit found a target-cadence discontinuity that must remain explicit:
`2505` covers candidates listed from 2022-07-01 through 2023-06-30, while `2605` covers calendar year
2023. Those target cohorts overlap from 2023-01-01 through 2023-06-30. The parser may retain both
published cohorts, but a modeling workflow may not treat them as independent consecutive temporal
folds. The primary panel is therefore restricted to the four contiguous, non-overlapping July–June
target cohorts represented by `1905→2205`, `2006→2305`, `2105→2405`, and `2205→2505`. The
`2305→2605` pair remains source-valid but excluded from the primary panel because its target overlaps
the preceding fold. Prediction origins may be in the target cohort's starting month or, for the
COVID-delayed `2006` release, at most one calendar month later. This month-offset rule uses the exact
published year/month and never invents a day for month-precision releases. Each panel row records the
offset. The `1808→2105` pair remains excluded because its October feature release is three calendar
months after the July target-cohort start. Both exclusions remain machine-readable in the v2
experiment configuration and QA evidence.

Evaluation also follows a strict publication-vintage rule: a training outcome may enter a fold only
when its target release was already public at that fold's prediction origin. With the currently pinned
sources, only the `2205→2505` evaluation origin has an earlier configured target (`2205`, from the
`1905→2205` pair) available for model fitting. Earlier pairs remain useful for panel construction,
baseline history, and descriptive audits, but they cannot become anachronistic model-training folds.
This one-fold limitation must be reported as feasibility evidence and cannot support promotion or a
claim of stable temporal validation.

## 6. Canonical panel and eligibility

The separate v2 model panel includes at least:

- program and feature/target release identity;
- exact publication values and precision;
- target listing-cohort start/end and follow-up end;
- `target_n`, published percentage, canonical proportion, and empirical-logit target;
- explicit analytic eligibility and missingness indicators; and
- source URL/hash and method-ledger identities for joined metric families.

The prediction universe is defined from programs present in each feature release, before future
target availability is known. Programs absent from the later outcome table retain a null target and
are ineligible; they are never dropped before QA or converted to a negative outcome. Target-release-
only programs are reported as additions but are not backfilled into an earlier prediction universe.

Primary analytic eligibility requires a valid composite program identity, proven temporal
availability, a target in `[0, 1]`, `target_n >= 10`, and an available prior target for persistence.
Sensitivity analyses use fixed `target_n >= 20` and `target_n >= 30` thresholds. Thresholds may not
be selected after inspecting model comparisons.

## 7. Models and evaluation

Required baselines are:

1. persistence using the latest published 18-month functioning-transplant percentage available at
   the prediction origin;
2. the candidate-volume-weighted aggregate of reconstructed outcomes in the feature release,
   available at the prediction origin and labeled the **available-cohort reference**, never a
   published national statistic or the future target-release value; and
3. the program's historical mean using only outcomes public by the prediction origin.

The only P0 challenger family is Ridge with fold-local median imputation, explicit missingness
indicators, fold-local standardization, fixed regularization, and inverse-logit predictions bounded
to `[0, 1]`. Required feature-group comparisons are history only; history plus acceptance; history
plus access; history plus access plus acceptance; and a secondary full model adding eligible lagged
safety measures. No model zoo or post-result feature selection is allowed. A Ridge comparison may run
only for a strict-vintage fold with at least one earlier labeled training cohort; the current one-fold
design is exploratory feasibility evidence and cannot promote a model into the product.

Primary reporting includes target-release-balanced MAE in percentage points, mean signed error in
percentage points, and named-scale calibration intercept/slope. Secondary reporting includes
patient-volume-weighted MAE, median absolute error, target-release and fixed within-release volume
strata, missingness/first-observed strata, and program-clustered paired bootstrap intervals.

The latest target releases and feature combinations were inspected during feasibility work.
Therefore every current v2 result is retrospective and exploratory, never an independent holdout,
prospective validation, or confirmatory result. Future prospective evaluation requires a locked
configuration before a new same-cadence release becomes available.

### Current retrospective evaluation freeze

The current study fixes the following analytical contract before target-comparison results are
computed:

- Baselines are evaluated on every primary pair's `primary_analytic_eligible` rows. Ridge is
  evaluated only for `2205→2505`, using only `1905→2205` eligible rows for fitting. A Ridge runner
  must fail for an evaluation pair without a strict-vintage training pair.
- All Ridge feature groups use identical training and evaluation populations. Missing predictors
  are retained and handled inside the training-fold pipeline; complete-case filtering is
  prohibited.
- The history group contains prior empirical logit, the historical-mean proportion on its native
  bounded scale, `log1p` prior target N, and historical target count.
- The access group contains log transplant-rate ratio, `log1p` transplant-rate person-years,
  `log1p` 25th-percentile wait time, and their source missingness indicators.
- The acceptance group contains `log1p` expected acceptances; log overall, low-, medium-, high-,
  and hard-to-place OAR; log credible-interval width; and their source missingness indicators.
- The safety group contains only lagged safety fields whose source ledger proves availability at
  both the training and evaluation prediction origins and whose measurement/follow-up period ends
  before the associated target listing cohort. With the current sources, the model-eligible safety
  family is limited to the published waiting-list mortality ratio and its log interval width;
  later safety families remain separate descriptive context.
- Every logarithmic transform requires a finite positive input except `log1p`, which requires a
  finite nonnegative input. A reported zero or nonpositive ratio is a hard source/model-input error;
  suppression remains null and receives an explicit indicator.
- The only challenger is Ridge on the empirical-logit target with median imputation and empty-
  feature retention, standardization, and `alpha=1.0`, `solver=lsqr`, `tol=1e-8`, and
  `max_iter=10000`. Predictions are inverse-logit transformed and therefore bounded to `[0, 1]`.
- Errors are in published percentage points with signed error defined as `prediction - observed`.
  The primary summary is the unweighted mean of target-release MAEs. Named-scale calibration fits
  `observed percentage points = intercept + slope × predicted percentage points`; combined-release
  fits give every release equal total weight, and a zero-variance prediction reports calibration as
  unavailable with a reason.
- Secondary summaries include candidate-volume-weighted MAE, median absolute error, results by
  target release, deterministic within-release target-N quartiles, N≥20 and N≥30 sensitivities,
  first-observed/established status, and prespecified missingness strata. Quartiles are assigned by
  sorting on target N and then program key and dividing rows into four groups whose sizes differ by
  at most one.
- Paired uncertainty uses 2,000 program-clustered bootstrap resamples with seed `20260904` and the
  linear 2.5th/97.5th percentiles. Every sampled program contributes all of its repeated rows and
  the estimand is challenger minus comparator target-release-balanced MAE. Input row order may not
  change the result.
- Fixed incremental contrasts are history+access versus history, history+acceptance versus history,
  full versus history+access, full versus history+acceptance, and full+safety versus full.
- `promotion_allowed` is false. No current Ridge result may activate a program-level forecast or
  replace the V1 product.

## 8. Risk adjustment and safety outcomes

Public aggregate candidate summaries cannot reproduce SRTR's patient-level risk adjustment.
Optional aggregate case-mix models are sensitivity analyses only. Acceptance and historical safety
measures are predictive/context variables, not baseline risk adjusters for the same outcome.

Published pre-transplant mortality, mortality-after-listing, 90-day graft-failure, and one-year
conditional graft-failure measures are presented separately with their own cohorts, denominators,
directions, and uncertainty. They are not arithmetically compatible components of the Table B7
target and may not be averaged into a score.

## 9. Product rules

The future v2 interface presents separate patient-centered history, forecast evaluation, access
context, and safety context views. It may show a selected program against descriptive national or
regional context, but it may not create a leaderboard, ordinal rank, red/green quality label,
regulatory prediction, MPSC-threshold display, patient/organ input form, or causal explanation.

Every analytical view must identify its cohort and publication timing and display a persistent
banner stating that the product is a public aggregate research prototype, not patient-level,
clinical, regulatory, or causal decision support. Missing values display as `Not reported` or
`Insufficient history`, never as zero.

The v1 application remains the default until a separate explicit product decision approves v2.

## 10. Reproducibility and completion

V2 output roots are declared in `configs/patient_journey_v2/experiment.yaml` and validated before
any writer runs. A v2 output path must be repository-relative, must not traverse outside the
repository, and must not equal, contain, or be contained by a protected v1 root.

Every v2 artifact records source and configuration hashes, Git commit, dependency-lock identity,
UTC build time, cohort timing, feature schema, and model parameters. Only an explicitly approved,
attributed, reproducible bundle may be tracked; raw and generated data remain ignored.

V2 is complete only when the active plan's acceptance criteria, test-first evidence, focused and
full verification, documentation, provenance, offline loading, and claim checks all pass without
changing v1 frozen evidence.
