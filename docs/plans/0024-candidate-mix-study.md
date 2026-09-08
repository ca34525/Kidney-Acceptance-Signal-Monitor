# Plan 0024 — Test whether earlier candidate characteristics improve prediction

**Status:** unimplemented proposal; future implementation requires authorization.
**Scope:** one small, predefined candidate-characteristic input block in a separate study.

## Question and purpose

Do earlier public summaries of the candidates a kidney program lists improve predictions
beyond that program's earlier outcomes, and does acceptance add information after those
candidate characteristics are included?

The proposed primary target remains original V2's published 18-month functioning-transplant
percentage. This is an unadjusted reported outcome, so earlier candidate characteristics may
contain information not captured by outcome history alone. That is a hypothesis to test,
not a claim that adding these inputs creates official risk adjustment or fair center comparisons.

Read [Plan 0022](0022-source-and-cleanup-audit.md), the
[source feasibility audit](../audits/source-feasibility-0022.md), the
[original V2 specification](../specs/patient-journey-v2.md), and the
[report-count follow-up](../patient_journey_v2_followup_results.md) before fixing this study.
The audit verified candidate-table availability in all nine pinned releases, but also found
changed age categories despite the same column count. It corrected the newest outcome cohort's
dates and identified conditional additional historical periods. This proposal does not freeze
source coverage or model choices.

## Target and population decision

One record represents a kidney program identified by `(CTR_CD, CTR_TY)` and a fixed,
non-overlapping listing cohort. The primary target is published `SAL_TOTFTX_C18`: candidates
known alive with a functioning transplant at 18 months as a percentage of the original
listing group, `SAL_N_C`. Candidates who never received a transplant remain in the denominator.
Unknown status is neither success nor failure and is not filled in.

Applying the candidate block to the deceased-donor receipt target in
[Plan 0023](0023-deceased-donor-receipt-study.md) is a separate possible application. Decide
whether to authorize it, and whether it is secondary or a distinct study, before either
endpoint's new comparison errors are inspected. Keep functioning-transplant percentage primary
for this proposal. Do not select the reported endpoint by whichever produces the larger gain.

Define the program population from reports available at each prediction origin. A later absent
report creates a missing target, not a negative outcome. Retain missing predictors for training-
fold treatment, report unmatched programs, and fix any minimum listing-group size or sensitivity
population before scoring. These are program-level predictions, not individual patient estimates.

## Source and timing gate

Use prior-release Tables B2–B3 only after verifying which column describes newly listed
candidates and which describes everyone on the waiting list. They are different populations;
do not mix their denominators or substitute one silently when a field is missing.

Propose one compact block covering age distribution, blood type O, previous transplant,
and high cPRA. cPRA, calculated panel-reactive antibody, describes sensitization relevant to
donor compatibility. Exact age and cPRA categories, column names and permitted combinations
must be resolved from source definitions, then fixed before errors are examined. Use the
smallest stable set of proportions, rather than every available demographic category.

The audit found that `1808`/`1905` have age 65+ and age-other columns, while `2006` onward
split the older group into 65–69 and 70+. Do not treat those schemas as identical. Use verified
stable age bins, or document a justified combination before freezing the block. Blood type,
prior-transplant and PRA field names were stable across the nine releases, but matching names
alone do not verify historical cPRA definitions, candidate denominators or measurement dates.

For each proposed field, record the source release, population counted, denominator, units,
missing/unknown categories, measurement dates and publication precision. Check category changes
and rounding before combining bins. Preserve reported unknown categories explicitly; do not
renormalize them away or treat them as zero. Do not claim a historical category is equivalent
to a later one without evidence. Fix field inclusion using source comparability and the question,
never target correlations or observed model gains.

Plan 0022 found that outcome and wait-time dates are copied from the ledger without an
independent source-period check. A separately tested correction path must bind those dates to
release-specific evidence and reject disagreement before this study proceeds. Candidate-period
dates need that same source binding. Preserve the original configurations and results as records.

Every input must have been public by its prediction origin, with measurement and follow-up
ending before the target listing cohort begins. Each training outcome must have been public
by the evaluated origin. Document exact eligible origins and non-overlapping cohorts after
the source audit. Earlier candidate summaries describe earlier candidates; never substitute
the target cohort's characteristics because they would be more predictive.

At least two eligible evaluation origins are necessary before discussing consistency across
time. If only one exists, a fixed exploratory comparison can proceed after authorization,
but cannot show stable temporal performance. More fields cannot solve that limitation.

## Fixed small comparison

Carry forward the latest earlier outcome and calculate the program's historical mean first.
Use one regularized regression family with three fixed input groups: outcome history;
the same history plus the candidate block; and those same inputs plus earlier acceptance.
The primary comparison is history plus candidate characteristics versus history alone.
The acceptance comparison adds acceptance to history plus candidate characteristics.

Score all approaches on identical eligible rows and report the simple forecasts alongside
the fitted comparisons. Do not regard improvement over a weak history model as sufficient
if the simple historical forecast remains stronger. Exclude report count, program identity,
location, future report availability and target-period values from every predictor list.

Freeze the exact history, candidate and acceptance fields, transformations and regularization
after source coverage is resolved and before fitting. Fit missing-value replacement, scaling
and any permitted parameter selection using training data only. Do not search interactions,
nonlinear models, candidate subgroups or alternate demographic blocks in this first study.
If a later nonlinear hypothesis is justified, give it a separate plan before evaluating it.

Report average absolute error in percentage points, giving eligible evaluation origins equal
weight, plus signed error and results for every origin. Include a prespecified volume-weighted
summary and paired resampling of whole programs, retaining their repeated cohorts. Define the
minimum useful improvement and tolerated bias change before scoring, with a project-use
rationale rather than an invented clinical threshold.

## Stopping rules and interpretation

Stop before fitting if stable field definitions or denominators cannot be verified, source
dates remain unbound, no published prior training outcome is available, or the design needs
nonpublic data or overlapping outcome cohorts. A source-driven era restriction must precede
comparison results and remain visible in the study's population accounting.

Run the fixed comparisons once and report each. Stop expanding the candidate block if it
does not meet the prespecified improvement requirement against both the model without it
and the strongest simple forecast, or if apparent gains rely on one period or unacceptable
bias. Do not prune or replace fields based on evaluation errors to rescue the result.

Previously inspected historical outcomes remain exploratory evidence, even if they were
excluded from an earlier model fit. Program-level resampling does not create a new time period.
Report associations and prediction error only: no causal effects, program rankings, patient-level
fairness, clinical benefit, regulatory conclusions or equivalence to SRTR risk adjustment.
The study cannot promote a model or alter original V1/V2 and completed follow-up results.

## Future implementation and acceptance

After authorization and source reconciliation, write a separate scientific specification,
typed configuration, decision record and isolated output identity before analytical work.
No new output root or tracked analytical release is approved by this proposal.

Use small failing tests, then the smallest implementation, for source-period disagreement;
new-versus-all-waitlist denominator confusion; category drift and unknown values; composite
joins and publication cutoffs; exclusion of report count and future data; training-only
preprocessing; identical comparison rows; and artifact isolation/provenance.

Run focused and applicable repository checks, reproduce outputs from immutable verified
inputs, and record all fixed comparisons and limitations here. Preserve original evidence
identities. The acceptance criterion is a reproducible answer to the fixed question, including
an unfavorable answer, rather than a favorable score or increased model complexity.
