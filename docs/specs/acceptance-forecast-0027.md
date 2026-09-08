# V1 forecast improvement and future promotion

Version 1, September 8, 2026. This is the separate contract for
[Plan 0027](../plans/0027-v1-forecast-improvement.md), following the request to improve V1
forecasts generally and reconsider the exact bias comparison with persistence. The current
authorization is to document this work; no new analysis, model fit or deployment has run.

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
configuration files and their implementation do not yet exist.

The proposed output root is ignored `data/research/acceptance-forecast-0027/`; establish it
in the execution settings before writing results. Each run has a distinct immutable identity
and records specification/configuration/input hashes, source manifest and release identity,
Git commit and dirty state, dependency-lock hash, UTC build time, years, row counts,
exclusions, feature schema and fitted parameters where applicable. No original output is
overwritten and no new tracked release bundle is authorized by this planning change.

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
