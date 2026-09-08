# V1 forecast improvement and future promotion

Version 2, September 8, 2026. This is the separate contract for
[Plan 0027](../plans/0027-v1-forecast-improvement.md), following the request to improve V1
forecasts generally and reconsider the exact bias comparison with persistence. The current
authorization is to complete P1–P4 following the user's request to complete the plan.
Deployment remains a separate implementation item.

## Question and preserved evidence

How large are the errors when predicting a kidney program's next published offer-acceptance
ratio, where are those errors concentrated, and can a small change improve the complete
forecasting procedure? A later product decision may select the existing Ridge method or a
revised method under the promotion policy below. Improvement is not restricted to removing
average signed error.

One record is a composite `(CTR_CD, CTR_TY)` program and a non-overlapping calendar-year
outcome cohort. The target remains the next same-cadence published offer-acceptance ratio
(OAR), modeled on its natural-log scale. OAR compares acceptances with the risk-adjusted
expectation; it is not the percentage of offers accepted or a patient outcome percentage.
The intended use remains a delayed-report nowcast for quality-improvement review.

The [original specification](../../SPEC.md), its two experiment configurations, canonical
replay and release bundle retain their original identity and result. The 2025 Ridge replay
had 10.13% lower log-scale average absolute error than persistence but failed the exact
absolute-bias comparison, 0.01145 versus 0.00885. That remains an original nonpromotion,
not a universal prohibition on selecting Ridge in a later release. Original V2 and all
completed follow-ups retain their own contracts and results.

## Data, timing and execution prerequisites

Start with the trusted saved V1 predictions and their recorded outcomes, using the release
manifest and completion/provenance records to verify payload hashes and identities. Diagnose
the saved 2021–2024 backtests and the separate 2025 replay; do not rerun the replay to obtain
these descriptions. Pin the diagnostic inputs and the model/training definitions for each year.
The source boundary remains the nine releases in [the manifest](../../configs/data_sources.yaml).
No new source acquisition, candidate-level data or target change belongs to this study.

Before diagnostic execution, implement typed settings under `configs/acceptance_forecast/`
that bind the input identities, years, populations, formulas, strata, summary methods and
output location. Before comparison execution, add a separately versioned comparison
configuration fixing the candidate procedures, temporal folds, tuning/calibration rules,
metrics and decision tolerances. Missing required choices must fail validation. These
configuration files must pass their typed validators before the corresponding execution.

The proposed output root is ignored `data/research/acceptance-forecast-0027/`; establish it
in the execution settings before writing results. Each run has a distinct immutable identity
and records specification/configuration/input hashes, source manifest and release identity,
Git commit and dirty state, dependency-lock hash, UTC build time, years, row counts,
exclusions, feature schema and fitted parameters where applicable. No original output is
overwritten and no new tracked release bundle is authorized by this execution.

Predictors, training outcomes and calibration outcomes must be public by the evaluated
prediction origin. Measurement periods obey V1's availability rules. All rows for an outcome
year stay in the same temporal fold; never use a random row split. Imputation, scaling,
fitting, tuning and correction estimation use only permitted earlier information. Center
identity, location and future report availability remain excluded as predictors.

All historical evaluation years have already been inspected. Diagnosis may inform the next
small comparison, but this makes its results exploratory development evidence even when each
fit respects time. Log those design choices and report every configured comparison. Neither
new code nor program resampling turns an inspected year into fresh validation. A later
unseen outcome can strengthen the evidence; waiting for one is not a prerequisite for an
explicitly retrospective product decision.

## Error definitions and distributions

For a published ratio `y > 0` and a prediction `p > 0`, calculate:

| Quantity | Definition and meaning |
|---|---|
| Signed ratio error | `p - y`; positive means overprediction, in ratio units |
| Absolute ratio error | `abs(p - y)` |
| Signed percentage error | `100 * (p / y - 1)`; denominator is the published ratio |
| Absolute percentage error | `100 * abs(p / y - 1)` |
| Signed log error | `log(p) - log(y)` |
| Absolute log error | `abs(log(p) - log(y))` |
| Within a relative tolerance `q` | `abs(p / y - 1) <= q`, including equality |

Hypothetical example: predicting 1.00 when the published ratio is 0.80 is 0.20 ratio units,
or 25%, too high. Reversing those numbers is 20% too low. These are relative errors in a
ratio, not percentage-point changes in an acceptance percentage. Exponentiating average
absolute log error gives a multiplicative summary, not mean absolute percentage error.

Keep mean absolute log error as the primary comparison metric, with equal weight for each
evaluation year and each eligible program within a year. Report ratio-unit MAE alongside
it. Percentage summaries explain magnitude; they do not replace the primary metric because
the published ratio can be small. Never introduce an epsilon denominator, silently trim
extremes or substitute zero for a missing value. Missing targets are explicitly counted
exclusions; a nonpositive/nonfinite ratio in an otherwise eligible record is a hard error.

For every year and model, show sample size, signed means and medians, absolute means and
medians, the middle 80% of signed errors (`p10`–`p90`), the 90th and 95th percentiles of
absolute errors, and the full range. Use linear percentile interpolation. Report counts and
fractions within ±10%, ±25% and ±50%; these are descriptive tolerances, not promotion or
clinical thresholds. Provide full-range signed-error and cumulative absolute-error plots
with shared units and scales. Do not impose a normal distribution.

Report each year before combined summaries. An overall mean or tolerance fraction is the
unweighted average of yearly values. Any combined distribution/quantiles are explicitly
secondary, row-pooled summaries, with counts and repeated-program dependence disclosed;
do not call an average of yearly medians a pooled median. Program-clustered paired
resampling keeps all selected years for a sampled program together and recomputes the
year-balanced statistic; pin count, seed and interval method before use.
Those intervals describe variation across the observed programs, not uncertainty from a new
year or from choosing methods after inspecting historical outcomes.

Use identical eligible program-year rows for paired comparisons. Define the population
independently of which method performs well or returns a prediction; missing candidate
predictions on required rows are errors, not silent removals. Retain original analytic and
public-forecast-eligibility flags and report the deployment-eligible population separately.
Include win/tie/loss counts and the distribution of candidate-minus-comparator absolute
errors, so a mean gain cannot hide frequent or large worsening. The primary paired
difference uses absolute log error: negative is a win, exact equality a tie, and positive
a loss, using unrounded values before display formatting. Label any ratio-unit or
percentage-error comparison separately; changing the error scale can change which model
wins for a program.

Describe errors by earlier expected-acceptance quartile, earlier OAR and predictor
missingness; reuse existing volume assignments for saved forecasts. Fix any new cut points
before calculation. Show cell sizes and unknown groups. Investigations selected after seeing
errors are labeled exploratory and cannot become subgroup display rules without a separate
test. Explain the largest errors by available record characteristics without creating a
national named-program ranking or claiming causes. Report existing band coverage by group
as evidence about error spread, distinct from published SRTR credible intervals.

## Small comparison after diagnosis

Retain persistence, historical mean and the existing Ridge procedure as references. Select
a small, enumerated set of alternatives after recording the diagnostic findings. Candidate
ideas are a constant correction, a simple fitted adjustment of the latest ratio toward
typical values, and different weighting of earlier training observations. These are options,
not three already-approved fits or evidence that they will improve forecasts. Fix exact
inputs, loss, parameter grid, training windows, fallback rules and candidate limit before
scoring. Broad automated feature or model-family search is outside this plan.

When testing a correction, estimate it from earlier predictions of the same forecasting
procedure made without their outcomes in the corresponding fit, whose outcomes are also
public by the later origin. Fix minimum calibration history and fallback behavior. Any choice
between mean/median correction, correction window or strength is tuning and belongs inside
the earlier training/development periods. A mean correction targets directional error; it
need not improve absolute error. Give persistence the same calibration opportunity and
retain both uncorrected methods. Inspect the existing fitted intercept before proposing
an extra adjustment; the current Ridge already has one.

Use matched training and information cutoffs when attributing gains to a method. In
particular, the original 2025 replay fit ends at target 2023 because 2024 calibrated its
band. A new procedure that trains through 2024 has a different training design and must be
identified separately. Compare methods under the same new design and retain the original
replay as a historical reference; do not attribute extra training information to an
algorithmic improvement. Likewise, alpha 10 was selected using 2021–2023 outcomes; saved
results for those years are selection evidence. Carrying alpha 10 into a new reference is
permitted when identified as a retrospective choice, not as tuning-independent evaluation.
Any newly tuned procedure must choose parameters from earlier permitted data within each fold.
Reassess forecast bands for the complete corrected/refitted procedure rather than attaching
old residual radii without evaluation.

## Fixed comparison v1

The September 8 saved-error diagnosis precedes these settings and their scoring. This is one
retrospective comparison, fixed in `configs/acceptance_forecast/comparison.json` and explained
in [Decision 0014](../decisions/0014-fix-forecast-comparison-0027.md). Report every configured
procedure and stop; any further design revision needs a new identity and contract.

| Procedure | Exact fit and inputs |
|---|---|
| Persistence | Latest available published log OAR |
| Historical mean | Mean of the program's available annual published log OAR through the feature year; exponentiate for the ratio |
| Ridge | Original fixed 17 inputs, training target years 2018 through origin target year minus one |
| Ridge recent three years | Same inputs and fit, restricted to `max(2018, target_year-3)` through `target_year-1` |
| Adjusted persistence | Ridge using only current log OAR, with a fitted intercept, on expanding 2018-through-prior-year training outcomes |

For all fitted procedures use median imputation retaining empty columns, standard scaling,
an intercept, Ridge alpha 10, `lsqr`, seed 20260903 and equal training-row weights. The shorter
window changes history inclusion, not the input schema. The fitted adjustment estimates a
slope and intercept from earlier outcomes; it is not a correction estimated from evaluation
errors. There is no tuning grid or added correction. Alpha 10 remains an acknowledged
retrospective choice from original 2021–2023 selection. Record coefficients, intercept,
imputation/scaling parameters and the exact training years for every new fit.

Evaluate complete intact target years 2021–2025. Generate a 2020 warmup prediction using
training targets 2018–2019 solely for the first later band. Training targets, feature source
and any calibration target must have been public at the origin: the origin is the manifest
release for the feature year. A value from the identical release is available even when
publication has month precision. For different releases, require the latest possible source
publication date no later than the earliest possible origin date. Reject disagreeing panel
publication metadata. Later evaluation outcomes may be read for scoring only.

The new 2025 full-history fit includes target 2024, which was public in the feature release.
This differs from the original frozen fit through 2023, retained only as a saved historical
reference. Compare procedures on this same information design; do not attribute additional
training information to the algorithm. Keep all original analytic rows and explicitly report
missing targets, first-observed programs, public eligibility and the eligible-for-display
subset. Every method must return a finite positive prediction on every required row.

For each method and origin, take absolute log residuals from its immediately preceding
year's out-of-sample complete procedure. Require at least 30, and use order statistic
`min(n, ceil((n+1)*0.8))`. Apply that radius around the new fit's log prediction, then exponentiate.
Record the calibration year, count and radius. The changing fitted model and possible time drift
mean these are empirical bands; no exchangeability guarantee or new prospective coverage is claimed.
Report every year's coverage, exact binomial 95% interval and ratio-unit width, plus groups.

Primary comparison is mean of the five yearly mean absolute log errors. Retain all diagnostic
ratio/percentage/log tables, paired changes and groups. Paired resampling draws whole programs
with replacement, keeping all their observed years together, and recomputes the equal-year
statistic on each draw. Use exactly 10,000 attempts, seed 20260908, linear 2.5th/97.5th percentiles;
skip and count attempts missing any evaluation year. It describes variation across observed
programs, not a new year or uncertainty from choosing the design after inspecting outcomes.

Point recommendation requires all of these fixed rules:

- At least 5% lower primary error than persistence, error no greater than historical mean,
  and ratio-unit year-balanced mean absolute error no greater than persistence.
- The paired whole-program 95% interval's upper bound is below zero.
- Improvement in at least four of five years; no year's mean absolute log error more than
  10% above persistence; absolute year-balanced signed log bias at most 0.05 and absolute
  yearly signed log bias at most 0.15.
- Mean of yearly 90th-percentile absolute log errors no more than 1.10 times persistence's
  equivalent summary. This is a tail summary, not a pooled 90th percentile.
- Every earlier-volume, earlier-ratio, missingness and public-eligible group-year cell with
  at least 30 programs has mean absolute log error at most 1.10 times persistence's. Report
  smaller and unknown cells without using them to invent new eligibility rules.
- The year-balanced fraction with candidate absolute log error more than 0.25 worse than
  persistence is at most 10%. Exact unrounded differences govern this comparison.

Select the passing candidate with smallest primary error; exact ties use Ridge, adjusted
persistence, then recent-three-year Ridge. If none pass, retain persistence and state why.
For each method separately, band recommendation requires every yearly and every named
group-year coverage interval with at least 30 programs to include 0.80, and year-balanced
mean ratio width no larger than persistence's. Missing required band evidence fails its gate.
Point selection never grants band selection. Public-ineligible rows remain in the analytic
overall summaries and are reported separately; they cannot enter a future display population.

## Future promotion policy

The exact rule `abs(mean signed error) <= abs(persistence mean signed error)` is **not
required for Plan 0027 or a release based on it**. The existing Ridge model or a revised
model may be selected even when it fails that comparison. This is an explicit policy
revision informed by the known original result, not a claim that the new policy was fixed
before that result was seen. See [Decision 0013](../decisions/0013-revise-future-forecast-promotion.md).

A new decision must weigh useful accuracy improvement against strong simple forecasts,
typical and large errors, year-to-year consistency, calibration, uncertainty and important
program groups. Define a practical absolute-bias tolerance or a justified allowable
difference from a comparator, with units and an intended-use rationale. Specify the primary
accuracy requirement, worst-year/subgroup tolerances, uncertainty treatment, minimum group
sizes and separate point-versus-band display requirements in the comparison configuration
before scoring alternatives. Do not choose a tolerance solely to clear 0.01145 or repeatedly
revise it until a candidate passes. None of these are validated clinical thresholds.

The final decision may retain persistence, select the existing Ridge method, select a
revised method, or conclude that evidence is insufficient. A new method need not be invented
to justify selecting an existing one. Report the original failed criterion and the revised
decision side by side. Selection does not establish clinical benefit, causality, prospective
validation or regulatory suitability.

Actual display requires a versioned decision, trusted new artifact identity, tested explicit
eligibility and an offline application change under its own implementation item. The
historical release continues to show persistence until that work is completed. Point-model
selection does not automatically permit a forecast band. No model is promoted by this
documentation change.
