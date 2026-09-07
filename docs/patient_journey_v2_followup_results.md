# V2 follow-up: what changed after removing report count

**Completed:** 2026-09-05 UTC, Plan 0020 P1/P2. **Status:** exploratory development evidence;
changes and outputs remain uncommitted. No model is promoted and no future forecast is available.

The large original gain from adding acceptance information becomes much smaller once report
count is removed. History-only Ridge's average error falls from 11.49 to 7.32 percentage points;
history plus acceptance changes from 7.35 to 7.23. The incremental gain from acceptance is then
0.09 points, with a descriptive 95% interval for its error difference of [-0.491, 0.301].

This changes the interpretation of the original 4.14-point gain. Much of that comparison reflected
how the history-only model responded to the number of earlier reports. The result does not prove
acceptance has no predictive information, and it says nothing about the importance of acceptance
or access to patient care. The study uses one already-inspected evaluation period.

## Who is counted and when

One record describes a kidney transplant program and a July–June listing group, joined by
`(CTR_CD, CTR_TY)`. The target remains the published `SAL_TOTFTX_C18`: the percentage of the
original `SAL_N_C` listing group known alive with a functioning transplant 18 months after listing.
The denominator includes people who never received a transplant. Unknown status is not filled in.

The fixed comparison fits 215 programs from the July 2019–June 2020 listing group and evaluates
218 programs from July 2022–June 2023. The training outcome became public in July 2022, by the
later prediction origin; the evaluation outcome was published July 8, 2025. All five original and
five revised Ridge groups use the same training and evaluation rows. All three simple comparisons
are scored on those same 218 evaluation programs. Missing predictors retain their rows and use
only training data for replacement and scaling.

The audit saves all 966 original panel keys: 215 training, 218 evaluation, and 533 excluded from
this specific comparison. Excluded records include other periods and originally ineligible rows;
they are not 533 program closures. Per-feature missingness and exact eligibility remain in the
machine-readable evidence.

## Reproducing the original surprise

All 1,744 stored evaluation predictions (five Ridge groups and three baselines) were reproduced
with zero difference on the proportion scale, before the diagnostic interpretation or revised
fits. The specification fixed an absolute tolerance of `1e-10` and zero relative tolerance before
execution. Duplicate, missing, extra or mismatched prediction keys fail the calculation.

Report count was two for 212 of 215 training programs and five for 208 of 218 evaluation programs.
The mean rose from 1.986 to 4.927 reports, a change of 25.069 training standard deviations. This
large value partly reflects how little the count varied in training; it is not a measure of how
much a program's care changed. The input counts available reports, not program age.

In the original history-only model, report count contributed +0.532598 to the mean predicted
logit change of +0.518134. Other inputs partly offset it. A logit is the model's scale before
conversion back to a percentage; these contributions cannot be added as percentage-point or
patient effects. All five original models' input contributions, coefficients and training
preprocessing parameters are retained in the generated report and JSON.

## The one fixed revision

Remove only `historical_target_count` from every Ridge group. Keep the published target,
eligibility, publication cutoffs, other inputs, transformations, training-only preprocessing and
Ridge settings unchanged. The separate [specification](specs/patient-journey-v2-followup.md) and
[typed configuration](../configs/patient_journey_v2_followup/experiment.yaml) were written before
revised predictions were computed. No search over history windows, features or model families
was performed.

The errors below are percentage points. Average absolute error ignores direction; positive
signed error means predictions are too high. Candidate-volume weighting emphasizes larger
listing groups and remains a program-level measure, not individual patient accuracy.

| Approach | Programs | Average absolute error | Average signed error | Volume-weighted absolute error |
|---|---:|---:|---:|---:|
| Original: history | 218 | 11.488 | 9.484 | 11.455 |
| Original: history + acceptance | 218 | 7.348 | 0.654 | 6.254 |
| Original: history + access | 218 | 14.522 | 13.792 | 15.204 |
| Original: history + access + acceptance | 218 | 10.572 | 8.306 | 10.896 |
| Original: history + access + acceptance + safety | 218 | 12.523 | 11.201 | 13.387 |
| Revised: history | 218 | 7.320 | -0.933 | 6.023 |
| Revised: history + acceptance | 218 | 7.226 | -0.532 | 5.933 |
| Revised: history + access | 218 | 7.367 | 0.890 | 5.934 |
| Revised: history + access + acceptance | 218 | 7.492 | 1.107 | 6.162 |
| Revised: history + access + acceptance + safety | 218 | 7.422 | -0.265 | 6.013 |
| Historical mean | 218 | 7.609 | -0.185 | 6.034 |
| Persistence | 218 | 8.931 | 0.686 | 6.276 |
| Available-cohort reference | 218 | 9.867 | -2.008 | 8.306 |

The revised history-plus-acceptance model is 0.383 percentage points below the historical mean
in average absolute error, with interval [-0.852, 0.103]. Its volume-weighted error is 5.933,
compared with 6.034 for the historical mean. The original comparison was -0.2604 points with
interval [-0.7389, 0.2375], reproducing the outside review's calculation.

Both favorable and unfavorable incremental results remain visible. After count removal, adding
access to history raises average absolute error by 0.046 points; adding acceptance to history
plus access raises it by 0.125. These comparisons do not establish that access measures are
uninformative or should be removed from program review.

## All planned paired comparisons

Differences are challenger minus comparator average absolute error in percentage points;
negative values favor the challenger. These are descriptive 95% intervals from 2,000 whole-program
resamples, seed `20260904`, using the linear 2.5th and 97.5th percentiles. Paired programs, listing
cohorts and target evidence must agree. Resampling these programs does not create a new time
period or establish future performance.

| Challenger minus comparator | Error difference | Descriptive 95% interval |
|---|---:|---:|
| Original: history + acceptance minus Historical mean | -0.260 | [-0.739, 0.238] |
| Revised: history minus Original: history | -4.167 | [-5.295, -3.071] |
| Revised: history + acceptance minus Original: history + acceptance | -0.123 | [-0.288, 0.031] |
| Revised: history + access minus Original: history + access | -7.156 | [-8.387, -5.955] |
| Revised: history + access + acceptance minus Original: history + access + acceptance | -3.080 | [-3.874, -2.241] |
| Revised: history + access + acceptance + safety minus Original: history + access + acceptance + safety | -5.101 | [-6.228, -3.929] |
| Revised: history + access minus Revised: history | 0.046 | [-0.578, 0.647] |
| Revised: history + acceptance minus Revised: history | -0.095 | [-0.491, 0.301] |
| Revised: history + access + acceptance minus Revised: history + access | 0.125 | [-0.271, 0.507] |
| Revised: history + access + acceptance minus Revised: history + acceptance | 0.266 | [-0.324, 0.849] |
| Revised: history + access + acceptance + safety minus Revised: history + access + acceptance | -0.069 | [-0.411, 0.307] |
| Revised: history + acceptance minus Historical mean | -0.383 | [-0.852, 0.103] |

## Reproduce and inspect the local evidence

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
$env:MPLCONFIGDIR = "$PWD/.test-tmp/matplotlib"
uv sync --frozen
uv run kasm patient-journey follow-up
```

The command reads the pinned original V2 bundle and requires no source network access or original
artifact rebuild. It creates a complete run once under `data/patient_journey_v2_followup/report_count_v1`.
An identical run refuses overwrite, including an existing empty directory. A new implementation
has a distinct directory identity; it cannot overwrite prior results. Generated files stay ignored.

Reviewed run: `c6cc2cea133e7e61e9e42ac284f170baef43d9989d3ab04eea543ffb47af1cfa`.
The run includes `report.md`, report-count and error figures as SVG/PNG, `evaluation.json`,
`predictions.parquet`, and `manifest.json`. The report includes every original input contribution.
The manifest records all file sizes/hashes, sources, both experiment identities, original/current
locks, exact implementation hashes, model parameters, cohort timing and UTC build context.

| Identity | Value |
|---|---|
| Original V2 bundle SHA-256 | `ce2844edbcec92c09d0053720d5331dd37ed43ab75de7aa4dd1de431c79a9eee` |
| Follow-up configuration SHA-256 | `da88d4180ff712680634755ee6b756d95a49ca27ab827b39bdc5bca656ba92b4` |
| Follow-up evaluation JSON SHA-256 | `a9c873ddf303569bf628911baa60d147ebab72399083fbb574be1eba6473a774` |
| Original dependency lock SHA-256 | `9783d6fc61d5c69012494519e674b5c17c0f346ba1923a4758c38fcdc573a687` |
| Current dependency lock SHA-256 | `10f23b33f1b26e644c60c5a56126c7b73d884e874fa57319dd0a6928decbb02b` |
| Build Git commit, dirty worktree | `9eaa30a72d9cb5d8254e2b829d835bf048324a0a`, `true` |
| Build time UTC | `2026-09-05T03:28:57.884319Z` |

Matplotlib supplies the two standalone figures. Adding it changed no pre-existing package
version. The original lock is retained in Git at the original release's recorded source commit;
the original bundle's provenance is unchanged. Exact reconstruction checks compatibility of
this environment with the preserved predictions. This uncommitted build is development evidence,
not a new canonical release.

The [active plan](plans/0020-v2-follow-up-and-interview-story.md) records failing-test evidence,
full verification, independent review, and preservation checks. P3's donor/unknown-status
investigation and P4's presentation, author walkthrough and rehearsal remain next. This result
does not correct unknown follow-up or establish interview readiness.

Source: Scientific Registry of Transplant Recipients public kidney Program-Specific Reports,
reused through the verified original V2 bundle and [source manifest](../configs/data_sources.yaml).
Public aggregate research prototype — not clinical or regulatory decision support.
