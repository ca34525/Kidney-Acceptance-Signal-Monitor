# Patient-journey V2 model card

This card retains the completed original V2 study and its results. A later review raised questions
about the report-count input and unknown follow-up status. Those questions and their reproduction
requirements are recorded separately in [Plan 0020](plans/0020-v2-follow-up-and-interview-story.md).
No revised model result is included here. See [the project guide](project-guide.md) for the
ordinary-language explanation and the distinction between the two history-based comparisons.

**How to read this result, 2026-09-05:** The question is whether earlier public reports help predict
the later published percentage of listed candidates known alive with a functioning transplant
18 months after listing. Each record is one program and one July–June listing group. The
denominator is everyone in that listing group, not just transplant recipients, and the outcome
is a percentage rather than a risk-adjusted ratio. Unknown follow-up status is not evidence of
death or a functioning transplant. This original model uses the published total without
separating those unknown outcomes.

## Evidence status and intended use

This is retrospective exploratory feasibility evidence. It compares prespecified baselines and
Ridge feature groups on published program-level outcomes. It is not prospective or independent
validation, an operational forecast, clinical or regulatory advice, a center ranking, or evidence
of a causal driver or intervention effect.

No V2 model is promoted. `promotion_allowed` is permanently false for this study, the release has
no future prediction row, and the separate V2 app displays historical evaluation and context only.
The V1 historical monitor and persistence projection remain unchanged.

## Frozen design

The complete analytical design was frozen in Decision 0006 and
`configs/patient_journey_v2/experiment.yaml` before real-data target-comparison results were run.
The freeze SHA-256 is
`ab8c01453c36039b293a8e7453b17b2b326faf734a081a4b67f8bfe132b1de79`.

Three baselines are evaluated across all four target releases:

- persistence: the program's prior published patient-journey outcome;
- available-cohort reference: the source-derived aggregate among contemporaneously available
  program outcomes; and
- historical mean: the program's mean earlier published outcome.

These baselines are simple comparison predictions. Persistence carries forward the latest
available outcome; historical mean averages the program's earlier available outcomes. The
available-cohort reference pools reconstructed outcomes with candidate-count weights from the
feature release, meaning the report available when the prediction is made. It is a source-derived
comparison, not a published national statistic or the later outcome release's average.

Five Ridge groups are fixed in this order: history; history plus acceptance; history plus access;
history plus access and acceptance; and the full group plus waiting-list mortality safety context.
Identity and location fields, future outcomes, future-report availability, and unlisted fields are
hard-rejected as predictors.

Ridge fits input weights while limiting their size. Its history group includes the latest outcome,
the earlier-outcome average, prior candidate count, and the number of earlier available reports
(`historical_target_count`). This fitted history group is different from the simple historical-mean
baseline. Access inputs describe transplant rate and waiting time; acceptance inputs describe
published offer-acceptance ratios and their supporting counts and intervals. Adding a group tests
a specified prediction comparison; it does not isolate a causal effect of that part of care.

Ridge uses the empirical-logit target, `alpha=1.0`, solver `lsqr`, tolerance `1e-8`, and at most
10,000 iterations. Median imputation and standard scaling are fit inside the training fold only.
Predictions are inverse-logit transformed and evaluated against the authoritative published
percentage.

The empirical logit converts the percentage to log odds with a fixed small adjustment to keep
0% and 100% finite. The inverse logit converts the fitted prediction back to a proportion between
0 and 1. Imputation replaces a missing input with the training group's median for calculation;
scaling uses that same training group's means and standard deviations. Published missing values
remain missing in the data and display.

If the whole training column is missing, `keep_empty_features=True` keeps the column and uses
zero as a numerical fallback. That value is internal to model fitting; it does not mean the
source reported zero or justify showing missing data as zero.

Strict publication vintage leaves one Ridge fold: train only on `1905→2205`, then evaluate all five
groups on the common eligible `2205→2505` population. It would be anachronistic to use outcomes
that were not public at an earlier prediction origin. The baselines and Ridge aggregates therefore
have different scopes.

In calendar terms, the fitted training outcome describes listings from 2019-07-01 through
2020-06-30 and was published in July 2022 (`2205`). Evaluation concerns listings from 2022-07-01
through 2023-06-30, published on 2025-07-08 (`2505`). "Strict publication vintage" means that
both input reports and any outcomes used to train the model must already be public at the
prediction origin. Earlier evaluation origins do not have a qualifying earlier training outcome.

## Metrics and uncertainty

The primary metric is the average size of the prediction error, or mean absolute error (MAE),
first calculated within each target release and then averaged with equal weight per release.
Errors are in percentage points: a hypothetical prediction of 45% versus an observed 40% has
an absolute error of 5 percentage points. Secondary metrics are candidate-volume-weighted MAE,
median absolute error, and mean signed error defined as
prediction minus observed. Calibration follows `observed = intercept + slope × predicted`.

Volume weighting gives larger listing groups more influence on the program-level error summary;
it does not measure individual patient accuracy. Positive mean signed error means predictions
are too high on average. Calibration describes the fitted straight-line relation between observed
and predicted percentages, with both quantities on the percentage-point scale.

Prespecified sensitivity summaries use target `N ≥ 20` and `N ≥ 30`, deterministic within-release
target-volume quartiles, and missingness strata. Paired contrasts resample whole programs, retaining
all repeated program rows, with 2,000 bootstrap replicates, seed `20260904`, and linear 2.5th and
97.5th percentiles.

Here `N` is the number of candidates in the target listing group. Quartiles divide programs into
four roughly equal-sized groups ordered by N. A paired bootstrap repeatedly draws whole programs
and compares both models on the same draw, keeping repeated records together. The resulting
interval describes variability across the observed programs; it cannot establish performance in
a new time period.

## Results

Across four target releases, all three baselines have 865 eligible rows:

| Model | Balanced MAE | Volume-weighted MAE | Median absolute error | Mean signed error |
|---|---:|---:|---:|---:|
| Persistence | 8.14 | 6.05 | 5.76 | -0.26 |
| Available-cohort reference | 9.87 | 8.03 | 7.40 | -2.82 |
| Historical mean | 7.45 | 5.73 | 5.16 | 0.81 |

On the sole Ridge fold, all models have the same 218-row evaluation population:

| Fixed Ridge feature group | MAE | Volume-weighted MAE | Median absolute error | Mean signed error |
|---|---:|---:|---:|---:|
| History | 11.49 | 11.46 | 10.71 | 9.48 |
| History + acceptance | 7.35 | 6.25 | 5.69 | 0.65 |
| History + access | 14.52 | 15.20 | 14.35 | 13.79 |
| History + access + acceptance | 10.57 | 10.90 | 8.91 | 8.31 |
| Full + safety | 12.52 | 13.39 | 10.51 | 11.20 |

For scope-matched context on `2205→2505`, historical-mean MAE is 7.61, persistence MAE is 8.93,
and available-cohort-reference MAE is 9.87. History plus acceptance is numerically lowest among the
five fixed Ridge groups at 7.35, but one retrospective fold cannot establish temporal stability or
justify promotion.

**Comparison explanation, 2026-09-05:** On these same 218 programs, the 4.14-point reduction is
from history-only Ridge (11.49) to history plus acceptance (7.35). The reduction relative to the
simple historical mean (7.61) is 0.26 points. Those are different questions and comparators.
The later report-count investigation in Plan 0020 is still separate from these frozen results.

Prespecified paired MAE contrasts are challenger minus comparator; negative values favor the
challenger within this fold:

| Contrast | Difference | Program-clustered 95% interval |
|---|---:|---:|
| History + access minus history | 3.03 | 2.27 to 3.80 |
| History + acceptance minus history | -4.14 | -5.12 to -3.22 |
| History + access + acceptance minus history + access | -3.95 | -4.54 to -3.34 |
| History + access + acceptance minus history + acceptance | 3.22 | 2.28 to 4.17 |
| Full + safety minus history + access + acceptance | 1.95 | 1.51 to 2.37 |

The current data show incremental acceptance context improving the history-only group, while access
and waiting-list-mortality additions worsen MAE in their prespecified paired comparisons. These are
descriptive comparisons from a single historical fold, not feature-selection instructions or causal
claims.

## Limitations

- Only one strict-vintage Ridge fold is available.
- The target is published and patient-centered but not officially risk adjusted.
- Program-level aggregates do not support patient-level clinical or fairness conclusions.
- Pandemic and allocation-policy periods may limit transportability.
- Safety measures have separate populations, denominators, timing, and meanings.
- Bootstrap intervals quantify program-resampled variability within this design; they do not create
  independent validation.
- No result may be used to tune this frozen study, promote a model, or create a future forecast.
