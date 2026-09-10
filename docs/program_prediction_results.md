# Program prediction sprint: completed findings

The most promising lead is a registration-demand review queue using earlier activity and
history, without offer-acceptance inputs. It uses Ridge, a regression model that discourages
large weights on inputs. In the two later historical years,
reviewing 25 selected programs captured 38.7% and 30.6% of observed registration growth,
compared with 30.1% and 27.2% from reviewing the programs with the largest latest registration
counts. That could change which demand changes an analyst investigates first. The evidence
does **not establish a reliable advantage**: the comparison is uncertain, the model was chosen
after examining later errors, and it performed worse in discovery.

The original discovery shortlist also produced a useful caution. DDKT history Ridge targeted
declining activity better than repeating the last observed decline, but its advantage over
reviewing large programs was uncertain. The shortlisted registration Extra Trees model failed
the stronger size-based review comparison. Extra Trees averages randomized decision trees.
Better prediction of a reported count does not by
itself establish practical benefit.

This completes P0–P4 of [Plan 0031](plans/0031-program-prediction-sprint.md), including both
authorized follow-up rounds. No model is promoted and the application is unchanged. These
are exploratory historical delayed-report nowcasts for nonclinical, nonregulatory review.

## What was predicted and when

One record is a kidney transplant program, identified by `(CTR_CD, CTR_TY)`, at a public-report
prediction origin, for one target calendar year. The five targets are annual new registration
events, removals coded as deceased-donor transplant (DDKT), removals coded as living-donor
transplant (LDKT), registrations on the year-end waiting list, and the published overall
offer-acceptance ratio (OAR). Events at programs are not unique people nationally. Removal
declines do not establish lost transplants, inappropriate declines or clinical harm.

Discovery used target years 2021–2023; the shortlist and simple reference methods were saved
before scoring 2024–2025. At the later prediction origins, July 9, 2024 and July 8, 2025,
about 52% of the target calendar year had elapsed. The corresponding target reports were
published July 8, 2025 and July 7, 2026. These are delayed-report nowcasts, not clean
12-month-ahead planning forecasts. Earlier month-only publication dates retain month precision.
The later periods had already been inspected in related studies and are not independent validation.

All inputs and training labels had to be public at the applicable origin. Historical features
use the latest public vintage of each past year at that origin; outcomes use the earliest
verified vintage. Whole target cohorts stay together in chronological folds. Imputation,
missing indicators, scaling and fitting use training rows only. Identity and geography never
enter the model. Exact fields, periods and settings are in the
[specification](specs/program-prediction-sprint-0031.md),
[initial settings](../configs/program_prediction/experiment.json) and
[feature map](../data/research/program-prediction-0031/initial-panel/feature-map.json).

The supported broader block contains four history features, eleven earlier activity features
and fifteen published OAR features. Candidate-characteristic headers were present, but their
forecast-origin periods and denominators were not fully bound; that optional block was omitted.
The first count-target discovery fold trains on only the 2019 target cohort. OAR has earlier
training cohorts beginning in 2018. Results without 2021 are retained to expose this sparse-history
limitation. The known OAR definition changes affecting target years 2024/2025 motivate the
feature-removal follow-up; they are not interpreted as effects of a program's practices.

## Complete initial screen

The table gives average absolute error: the average size of the prediction mistake, with equal
weight for each target year and equal program weight within a year. Each cell is **discovery /
later**. Lower is better within a target. The four activity targets use counts; OAR uses natural-log
ratio units and must not be compared numerically with the count columns. Original ratio-unit
errors, signed errors, direction agreement, tails and size groups remain in the complete ledger.

| Procedure | Registrations | DDKT removals | LDKT removals | Ending list | Overall log OAR |
|---|---:|---:|---:|---:|---:|
| Latest value (persistence) | 31.56 / 36.24 | 16.81 / 14.38 | 6.01 / 6.30 | 35.20 / 40.53 | .337 / .274 |
| Mean of two recent available values | 32.63 / 40.86 | 16.94 / 14.93 | 5.73 / 6.29 | 46.12 / 50.31 | .354 / .283 |
| Half of the latest consecutive-year trend | 38.27 / 39.41 | 19.95 / 17.44 | 7.95 / 7.39 | 31.49 / 38.26 | .405 / .333 |
| Fitted adjustment of latest log ratio | — | — | — | — | .319 / .248 |
| History Ridge | 31.27 / 35.62 | 16.35 / 14.52 | 5.74 / 6.14 | 36.95 / 44.26 | .321 / .248 |
| Broader Ridge | 34.27 / 33.03 | 17.95 / 15.80 | 6.24 / 5.97 | 39.30 / 39.69 | .325 / .252 |
| Shallow histogram boosting | 34.44 / 38.04 | 18.00 / 15.22 | 6.43 / 6.08 | 50.79 / 44.66 | .332 / .246 |
| Extra Trees | 30.88 / 37.17 | 16.70 / 14.76 | 5.94 / 5.84 | 47.99 / 47.49 | .321 / .244 |

The discovery-selected simple references were persistence for registrations and DDKT, recent
mean for LDKT, damped trend for ending list, and the fitted latest-ratio adjustment for OAR.
They remain fixed for later error comparisons. Ending-list damped trend already supplied the
strongest discovery prediction; its growth ordering adds no information to a last-change queue.
Neither a later-winning method nor a favorable target was substituted into the original shortlist.

The [saved shortlist](../configs/program_prediction/shortlist.json) chose DDKT history Ridge
and registration Extra Trees. DDKT's discovery error fell 2.72% from persistence, with small
gains in all three years; excluding 2021 retained a 2.57% gain. Registration Extra Trees improved
2.17% overall, worsened in 2022, and improved only 0.75% when 2021 was omitted. Later, both
lost their overall error advantage: DDKT was 14.52 versus 14.38 events, and registration Extra
Trees was 37.17 versus 36.24. Their later paired error differences were +0.14 events
(descriptive interval −0.38 to +0.65) and +0.93 (−1.16 to +3.48), respectively.

All 20 initial target/pipeline combinations and every baseline were executed. The initial
ledger has 180 procedure/year records: 108 discovery and 72 later. There were no model
failures and every eligible row received a forecast. Unsuccessful comparisons are retained.
See the [complete initial HTML report](../data/research/program-prediction-0031/initial-report/report.html),
[period CSV](../data/research/program-prediction-0031/initial-report/period-metrics.csv),
[full metrics JSON](../data/research/program-prediction-0031/initial-report/complete-results.json)
and [all-run ledger](program_prediction_reproduction.md#recorded-runs-and-complete-results).

## What changes in the review decision

A growth queue orders programs by predicted increase from the latest count; a decline queue
uses the predicted decrease. We compare the same budgets with the last observed change,
largest latest target count and random review. Queues are formed before checking later
outcomes. Missing outcomes remain unscorable and never trigger replacement selections.
Persistence predicts zero change everywhere; its displayed queue is a seeded tie ordering,
not an informative change prediction.

“Captured share” is the selected programs' observed change in the requested direction divided
by that change across all origin-eligible programs with reported outcomes. For example,
capturing 1,524 of 5,485 registration-growth events means 27.8%, not 27.8% of patients helped.
A false alarm is a selected program with no observed change in the requested direction.
The budgets are illustrative and are not known staffing limits.

At **15 program reviews**, the captured shares are:

| Question and target year | Model | Last change | Largest latest count | Random expectation | Model false alarms |
|---|---:|---:|---:|---:|---:|
| DDKT decline, 2024: original history Ridge | 12.9% | 4.7% | 15.8% | 6.4% | 9/15 |
| DDKT decline, 2025: original history Ridge | 21.4% | 2.7% | 8.5% | 6.4% | 3/15 |
| Registration growth, 2024: original Extra Trees | 12.9% | 12.4% | 24.6% | 6.4% | 5/15 |
| Registration growth, 2025: original Extra Trees | 14.9% | 21.3% | 18.5% | 6.4% | 3/15 |
| Registration growth, 2024: follow-up Ridge without OAR | 27.8% | 12.4% | 24.6% | 6.4% | 4/15 |
| Registration growth, 2025: follow-up Ridge without OAR | 22.9% | 21.3% | 18.5% | 6.4% | 3/15 |

DDKT Ridge could redirect activity-decline review away from simply repeating last year's
declines. At 15 reviews, its equal-year capture advantage over last change is 13.43 percentage
points (4.57 to 22.92). Against the stronger largest-count rule it is only 4.98 points
(−4.85 to 15.22), and it loses in 2024. This supports a review demonstration, not a claim
that a model is necessary or that it improves clinical outcomes. Registration Extra Trees
loses to largest-count review at every tested budget in both years.

## The two focused follow-ups

Round 1 asked whether removing the OAR block changed the registration result. Its
[configuration](../configs/program_prediction/followup_1_no_oar.json) was recorded before
the fits; all four pipelines, baselines, folds and random seeds remained fixed. Extra Trees'
later error barely changed, from 37.17 to 37.03 events, still worse than persistence's 36.24.
Its review queue still lost to largest-count review at all budgets in both years. This failed
to rescue the original candidate.

Broader Ridge without OAR had later error **32.99 versus 36.24 events**, an 8.97% reduction
from persistence. The paired difference was −3.25 events (−5.39 to −1.15); it improved in
both later years. Its discovery error was worse: **34.55 versus 31.56**, including worse
performance without 2021. Round 2 therefore recorded a new, explicitly hindsight-selected
[review question](../configs/program_prediction/followup_2_review.json), then reused the
saved Round 1 predictions with **no additional fit or tuning**. It did not replace the
original Extra Trees shortlist.

At **25 reviews**, this adapted registration Ridge captured **38.7% / 30.6%** of observed
growth in 2024/2025, versus **30.1% / 27.2%** for largest-count review. It selected 21/25
and 20/25 programs with growth, compared with 14/25 and 15/25 for largest-count review.
The equal-year capture difference was **+6.02 percentage points**, with an interval of
**−6.24 to +17.41**. At 15 reviews, its advantage was +3.80 points (−9.51 to +16.50).
At 10 reviews it lost to both last change and largest count in 2025. It does not dominate
the simple methods across budgets.

This is the strongest plausible use found: prioritizing registration-demand investigations,
with fewer no-growth selections at budgets 15 and 25 in these inspected years. It remains
a research lead. The [follow-up report](../data/research/program-prediction-0031/followup-2-review/report.html)
and [complete follow-up results](../data/research/program-prediction-0031/followup-2-review/report.json)
retain every budget and comparison. Both authorized rounds are complete; no further search
is included in this sprint.

## Important misses, missing outcomes and uncertainty

Two anonymous examples from the original shortlist show why review usefulness and count
accuracy must be assessed separately. At the July 8, 2025 origin, a selected DDKT program's
latest count was 223 and Ridge predicted 215.23; its subsequently reported count was 160.
The queue drew attention to a decline but underestimated its size by 55.23 events. This
example is the selected program with the largest observed decline at budget 15. A registration
Extra Trees false alarm had latest count 107, previous count 428, prediction 166.88 and
outcome 107. It is the selected no-growth case with the largest overprediction at budget 15.
Ties use program key. These cases illustrate errors and do not establish their causes.

For the promising follow-up Ridge, the mean of the two yearly 90th-percentile errors improved
from 86.30 to 78.47 registration events, but an individual 2025 miss was still 357.13 events.
The smallest earlier-list quartile worsened in both years: 9.81 versus 8.78 events in 2024,
and 8.56 versus 7.87 in 2025. Larger-program gains drive the aggregate improvement.
The [size-group and tail metrics](../data/research/program-prediction-0031/followup-1-later/metrics.json)
do not support uniform accuracy or dependable program-specific planning commitments.

For each count target, discovery had 704 eligible program-year rows, of which 696 had
reported outcomes; later assessment had 471, of which 466 had outcomes. OAR had 691/685
and 461/457, respectively. These are target-specific denominators, not pooled independent
programs. Unknown targets remain null. All selected model and simple-rule queues in the
completed later demonstrations happened to have reported outcomes, so selected outcome
coverage was 100%; overall outcome coverage was lower. First-observed programs after the
archive began remain in the panel/exclusion ledger outside main scoring. Initial archive
membership is labeled as unknown earlier history, rather than mistaken for observed entry.

The intervals above use 2,000 whole-program bootstrap samples: repeatedly draw programs with
replacement, keeping each program's repeated years together, then give each year equal weight.
For queues, each sample preserves the historical selection flags: the intervals describe
cross-program variation conditional on those fixed queues. They omit refitting, reranking,
model/queue selection and new-year uncertainty. No interval corrects for choosing a promising
result after looking at many methods. Only two later periods, source-definition changes,
sparse early training, omitted candidate inputs and delayed public data limit generalization.

The next justified step is to predeclare a registration-demand review comparison using the
no-OAR Ridge and the strongest simple queues on an additional, genuinely uninspected release,
while checking with intended analysts whether these public signals add information beyond
their fresher internal data. That would be a separate study. This sprint establishes a
reproducible candidate decision demonstration, not prospective utility or operational readiness.

## Figures and verification

The three main figures show every initial method's error improvement, the original shortlist's
review budgets, and observed versus predicted changes in original units. The fourth shows the
adapted follow-up. Each was rendered and visually inspected; all plots are aggregate or anonymous.

- [Initial error improvement by target/year](../data/research/program-prediction-0031/initial-report/error-improvement.png)
- [Original shortlist review budgets](../data/research/program-prediction-0031/initial-report/review-budget.png)
- [Observed and predicted changes](../data/research/program-prediction-0031/initial-report/changes.png)
- [Adapted registration Ridge review budgets](../data/research/program-prediction-0031/followup-2-review/review-budget.png)

The [reproduction record](program_prediction_reproduction.md) lists exact commands, immutable
run identities, complete predictions, failures, exclusions, metrics and verification evidence.
All recorded analysis ran from committed code and settings with a clean working tree. Large
research outputs are intentionally local and ignored by Git; the tracked report links require
those outputs or their reproduction. Completed studies and the existing application are preserved.
