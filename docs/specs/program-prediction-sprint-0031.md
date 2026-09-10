# Exploratory program prediction sprint

Planning specification for [Plan 0031](../plans/0031-program-prediction-sprint.md).
This is a new exploratory study, separate from the completed V1/V2, receipt, activity and
acceptance-forecast experiments. The first run has five targets and four pipelines; it can
lead to documented follow-up rounds. Numerical settings below are initial research choices,
not thresholds of practical usefulness or permission to deploy a model.

## Question and population

Which public annual program outcomes can be predicted better than simple historical rules,
and could those predictions improve the allocation of limited analyst review time?

One record identifies `(CTR_CD, CTR_TY)`, a prediction origin, a target calendar year and a
target variable. Program identity is used for joining and paired evaluation, never as a
predictor. Include programs observable at each origin; a later absent report means an unknown
target. Evaluate established programs with a reported latest target-history value; retain and
report first-observed/insufficient-history cases separately. Do not require a program to exist
in every future year to enter an earlier fold.

| Target ID | Source field | Units and interpretation | Primary loss |
|---|---|---|---|
| `registrations` | B1 `WLA_ADDCEN_NC1` / `_NC2` | Registration events during the year | Mean absolute error in events |
| `ddkt_removals` | B1 `WLA_REMTXC_NC1` / `_NC2` | Removal events coded DDKT at this program | Mean absolute error in events |
| `ldkt_removals` | B1 `WLA_REMTXL_NC1` / `_NC2` | Removal events coded LDKT at this program | Mean absolute error in events |
| `ending_list` | B1 `WLA_END_NC1` / `_NC2` | Registrations at year end | Mean absolute error in registrations |
| `overall_oar` | `OA_OVERALL_HR_MN_CENTER` | Published risk-adjusted acceptance ratio | Mean absolute error in log OAR |

B1 events are not distinct people, procedure counts or staffing hours. Transplants elsewhere
are a separate removal category. List growth is not by itself a poor outcome, and low OAR is
not an inappropriate-decline label. These are public-data nowcasts and review signals.

## Available information and historical pairs

Use the nine pinned workbooks in [data sources](../../configs/data_sources.yaml), with B1
periods bound through [the existing B1 ledger](../../configs/waiting_list/sources.json).
Start with its seven verified B1 releases. Do not reopen an archive search for `1808` or
`2006` before the first screen; unresolved optional information is omitted and recorded.

Retain release-specific source records. For features at an origin, use only records already
public then; select the latest available valid vintage for each past year, consistently across
programs. For a target outcome, use the earliest verified reporting vintage for that target
year across all programs. Later revisions are not replacements chosen by model performance.
Keep the vintage used for every training example's historical features fixed to its own origin.
Original archived-as-downloaded values cannot establish that no retrospective revisions occurred.

The retrospective `annual.json` is not a historical feature matrix. In particular, selected
2017/2018 B1 values both first appear in the verified July 2019 source, and 2019/2020 values
in July 2021. That does not create forecasts for an outcome already known at those origins.

| B1 origin release | Latest feature year | Target year | Outcome release/column | Role |
|---|---:|---:|---|---|
| `1905`, July 2019 | 2018 | 2019 | `2105`, NC1 | Historical training example; no earlier eligible fit promised |
| `2105`, July 2021 | 2020 | 2021 | `2205`, NC2 | Discovery; only target 2019 available for training |
| `2205`, July 2022 | 2021 | 2022 | `2305`, NC2 | Discovery; training targets 2019 and 2021 |
| `2305`, July 2023 | 2022 | 2023 | `2405`, NC2 | Discovery; add training target 2022 |
| `2405`, July 2024 | 2023 | 2024 | `2505`, NC2 | Later robustness; add training target 2023 |
| `2505`, July 2025 | 2024 | 2025 | `2605`, NC2 | Later robustness; add training target 2024 |

This table establishes timing candidates, not complete-case counts or a guarantee every
pipeline will fit. Report training programs and distinct target years in every fold. The
single-cohort 2021 B1 fit is especially limited; also summarize discovery results without it.

OAR uses verified 2017→2018 through 2024→2025 annual pairs. Discovery targets are 2021–2023,
training on available targets from 2018 through the preceding year; later targets are
2024–2025 with expanding available training. Match richer-feature OAR comparisons to the
same target-eligible rows; unavailable B1 inputs are missing predictors, not invented records.

Every feature measurement must end before the target year starts, and every predictor must
be public by the origin. Every training label must also be public at the evaluated origin.
A label released in that exact origin report is available for training; a label available at
its own original forecast origin is not a valid forecast example. Keep month-only publication
precision and apply the existing conservative availability logic.

Calendar-year `t` data published during `t+1` predict the still-unpublished full-year `t+1`
report. Display both dates and elapsed target-year fraction. This is delayed-report nowcasting,
not a complete future-year planning forecast. Do not mix horizons in the initial comparison.

## Features and initial model settings

History block: latest target value, previous calendar-year value if public, the mean of up to
three available years, and the last consecutive-year change. Preserve gaps. Do not use the
number of earlier reports, identity, geography, future availability or target-period components.

Broader block: history plus earlier B1 starting/ending list, additions and separate removals;
earlier overall/subgroup OAR, offers and expected acceptances; and a small candidate-mix block
when supported. Use appropriate log/log1p transforms for nonnegative scales; preserve missing
values for training-fold handling. Keep a feature map with units and population.

Candidate extraction starts with new-registration blood-type proportions, previous-transplant
categories, and diabetes/hypertension diagnosis proportions from `_NEWC2` fields. Confirm each
release's period and denominator with a targeted source check. Do not attach `_NEWC2` or
`_ALLC2` characteristics to an older B1 NC1 year simply because they share a workbook. Omit age
and PRA categories initially because comparable categories/definitions are less well established.
If candidate binding is incomplete, run broader models using supported activity/OAR inputs and
record the omitted block. A later candidate addition is a documented follow-up round.

| Pipeline | Inputs | Initial settings |
|---|---|---|
| `ridge_history` | Own history | Ridge alpha 10; training-fold median imputation and standardization |
| `ridge_broader` | Broader block | Same Ridge settings |
| `boosting_broader` | Broader block | Histogram gradient boosting; 150 iterations, learning rate 0.05, max 7 leaves, minimum 20 samples per leaf, L2 1, early stopping disabled |
| `extra_trees_broader` | Broader block | Extra Trees; 300 trees, max depth 6, minimum 8 samples per leaf, all features considered |

Seed `20260909` for randomized fitting and comparisons; derive per-run seeds deterministically.
Use training-fold imputation with missingness indicators consistently across pipelines and
record fields entirely absent in a training fold. Fit counts on `log1p(y)` and OAR on `log(y)`.
Back-transform count predictions, clip negative count predictions at zero, and score original
units; do not round predictions to integers. Back-transformed log predictions are point
forecasts, not automatically arithmetic expected counts/ratios. Missing or nonpositive OAR
cannot enter log fitting; reported zero count targets remain valid.

These are deliberately small fixed first-pass settings. There is no hyperparameter sweep.
If subsequent tuning is useful, it must use inner earlier-period folds and be recorded as a
new round. Disable any random validation split or early stopping that mixes calendar periods.

Baselines: carry forward the latest value; mean of up to two latest available annual values;
and latest plus half the last consecutive-year change, falling back to persistence without a
valid consecutive pair. Use these in count units for counts and log units for OAR, with
nonnegative count outputs. Add a fitted intercept/slope on latest log OAR as the strong OAR
reference, refit using the same available training labels as the other models.

## Comparisons and exploratory selection

Run all 20 pipeline/target combinations on discovery years first. Within each target, compare
models and baselines on the same eligible rows and origins. Missing optional features do not
create favorable model-specific populations. Record failed fits/predictions and report paired
valid rows plus coverage; do not rank a partial-success model as though it had full coverage.

Report every target year and give years equal weight in the primary summary, with equal
program weight within each year. For counts include signed error, 90th-percentile absolute
error, errors by earlier list-size group, direction agreement and predicted-versus-observed
change plots. Change-error MAE is identical to level-error MAE when both subtract the same
latest value, so do not count it as extra evidence. For OAR add ratio-unit error. Select and
save each target's strongest simple comparator on discovery years for later headline skill,
while continuing to show every baseline. Do not choose a new headline comparator using later
errors, compare raw MAEs across unlike target units, or choose a target by its pooled R².

Write a shortlist of at most two questions after discovery: gains versus baselines, consistency,
large misses, and the decision the forecast could affect. No arbitrary 5% improvement or exact
zero-bias gate decides usefulness. Simple methods can be selected. If none improves forecasting,
state that result and use errors to propose a focused next experiment.

Then score all initial procedures on 2024–2025 for transparent later-period comparison; assess
the previously saved shortlist first. These years were already inspected in related studies.
The entire project is exploratory, and later performance is not an independent holdout or a
selection-adjusted estimate. Any changes prompted by later errors are labeled another round.
Do not silently switch the shortlisted story to whichever later result looks best.

Use paired whole-program resampling for descriptive error/decision differences, keeping each
program's years together; 2,000 resamples suffice initially. Preserve equal-year weighting.
These intervals reflect cross-program sampling variation, not uncertainty from new years,
national shocks or selecting a winner among 20 experiments. Label OAR definition changes in
target years 2024/2025; for a shortlisted count model, compare a follow-up without OAR features
to see whether reliance on those inputs changes the result. Do not infer causal effects.

Do not import Plan 0025's boundary-continuity or positive-start restrictions wholesale: they
served its accounting comparisons. Report discontinuities, preserve source counts, and apply
target-specific validity. Never require future-period predictors for inclusion. New missing or
inconsistent fields are handled explicitly, without fabricated balancing events.

## Decision demonstration and deliverables

For a DDKT-removal decline question, rank `max(latest count - predicted count, 0)`.
For growth questions, reverse the difference. For OAR use the analogous log-ratio decline.
At review budgets 10, 15 and 25, compare the model with ranking by last observed consecutive
change and by largest latest target count for count targets. For OAR use lowest latest log OAR
as the level-based review comparator. Include the random-review expectation. Resolve ties by
a stable seeded ordering. Rank ties including all-zero scores explicitly; do not imply
persistence identifies different changes when all its predicted changes are zero.

Create review lists from the origin-eligible forecast universe before checking later outcome
availability. Retain selected programs with unknown later outcomes as unscorable; do not
refill or rerank the queue after removing missing targets. Report forecast coverage, selected
outcome coverage and observed-outcome metric denominators. Compare methods on the same
origin-eligible prediction universe; a model failure is not permission to silently shrink it.

Report the observed directional change captured by selected programs divided by that among
all origin-eligible programs with observed outcomes; the fraction of scorable selected programs
with a true directional change; missed observed changes; and
illustrative false alarms. If total directional change is zero, captured-share is unavailable,
not 100%. For random review, expected captured share is K/N when N is the origin-eligible
universe and K is the effective budget; label outcomes as observable only for reported programs.
Report the effective budget if fewer programs are eligible. No unvalidated materiality
threshold is required; the budgets are illustrative, not known UNOS staffing constraints.

Research selection flags stay in local predictions. Present aggregate review-budget curves and
anonymized worked examples, not a public national quality leaderboard or regulatory flag list.
Observed removal declines are not proven lost transplants or avoidable harm. Improved targeting
would support review usefulness in historical replay; intervention benefit remains untested.

The specified research output root is ignored `data/research/program-prediction-0031/<run-id>/`.
Each run retains settings, source/feature identities, code and lock hashes, Git revision/dirty
state, time, seed, predictions, exclusions/failures and all metrics. Use a new run directory on
revision. No completed study bundle or original frozen result may be overwritten.

Deliver a complete comparison table plus three main figures: error improvement by target/year,
review-budget performance for the shortlist, and representative errors/changes in original
units. The result report states what decision could change, what was learned, and what is
still uncertain. App integration, predictive intervals, deployment and simulation are outside
this research plan. The plan ends with a supported next choice, not a guaranteed winning model.
