# Earlier acceptance and reported deceased-donor transplant receipt

Version 1, 2026-09-08 UTC. Authorized by the request to carry out Plan 0023.
Source feasibility must pass and the final source/configuration identities must be recorded
before any prediction errors are calculated. This is a separate exploratory historical study.

## Question, records and source meaning

Does earlier public offer-acceptance information improve prediction of the percentage of a
kidney program's newly listed candidates recorded as removed for deceased-donor transplant
within 18 months? One record represents `(CTR_CD, CTR_TY)` and one July–June listing cohort.
The denominator is `SAL_N_C`, everyone in that original listing group, including candidates
who did not receive a transplant. Programs receive equal weight in the primary analysis.

The primary target is **derived from published components**, not a published deceased-donor
total. Add `SAL_CTXFNC_C18`, `SAL_CTXRE_C18`, `SAL_CTXFAIL_C18`, `SAL_CTXDIED_C18` and
`SAL_CTXUNK_C18`. They respectively describe functioning/alive, failed/retransplanted/alive,
failed/alive without retransplant, died, and post-transplant status yet unknown. All must
share the original listing denominator and 18-month time point. A missing component makes
the target missing. Unknown post-transplant health status contributes to recorded transplant
receipt but establishes neither graft function nor survival. Removal codes do not independently
verify a completed transplant record. No patient outcome or count is imputed from unknown status.

Verify the analogous five living-donor percentages, `SAL_TOTTX_C18`, and the other waiting-list
statuses against source definitions. Reconcile the two donor sums against the published
all-donor total and all mutually exclusive statuses against 100 using the source's display
rounding intervals. Missing accounting inputs make that check unavailable, not a zero or a
replacement endpoint. Preserve full workbook precision; the PDF's 0.1-point rounding allowance
is a QA rule. Any numerical normalization may address only floating-point noise (1e-10 points).
Reject nonfinite or out-of-range components and derived targets beyond that floating-point
tolerance. Compatible accounting intervals cannot authorize an out-of-range modeling target.

The model proportion is `p = derived_percent / 100`. For fitting only, use
`log((N*p + 0.5)/(N*(1-p) + 0.5))`. This smooths boundaries without rounding to fabricated
integer successes; it does not replace the derived percentage. Predictions use the logistic
inverse and errors use the unmodified derived percentage in percentage points.

## Source and time gates

Reuse the nine immutable pinned workbooks in `configs/data_sources.yaml`. Do not expand to
pre-2018 archives in this study. An independently fingerprinted, release-bound kidney report
or equivalent authoritative evidence must bind each used listing period and wait-time period.
The new methodology must reject missing evidence, altered fingerprints, wrong release/organ,
and dates disagreeing with that evidence. The old V2 ledger is a preserved historical record,
not independent proof. Acceptance dates and transplant-rate dates are checked against workbook
fields. Record every family’s measurement and follow-up bounds and publication precision.

The [source review](../audits/source-binding-0023.md) binds six historical reports through
fingerprinted cached PDF text and the newest through text extracted from its verified PDF.
These are text fingerprints, not claims about unavailable historical PDF bytes. The reports
state 18 months after listing without an exact day-conversion rule. Use December 31 of the
year after listing ends as a conservative upper bound; do not call it a source-reported B7
censor date. Wait-time censor dates are stated in the report and retain their exact dates.

Intended pairs are `1905→2205`, `2006→2305`, `2105→2405`, `2205→2505`, and `2305→2605`.
The first three were source candidates; the last two are the evaluation origins.
The July 2026 outcome is July 2023–June 2024 listings. All target listing cohorts must be
non-overlapping full July–June years. Every predictor's measurement and follow-up end must
precede target listing start, and it must be public by the feature release's publication origin.
Origins in July, or the delayed August 2020 origin one month after July start, are allowed.
This is prediction of a later report with a disclosed origin, not a before-listing guarantee.

The completed source gate excludes `1808` and `2006`: independent release-specific listing
and wait-time evidence could not be recovered. The fixed history releases are `1905`, `2105`,
`2205`, `2305`, `2405`, `2505`, `2605`; history at each origin uses only the earlier available
members. The remaining panel pairs are `1905→2205`, `2105→2405`, `2205→2505`, `2305→2605`.
Both evaluation origins fit only `1905→2205`; `2105→2405` is not public by either origin.
This source restriction was made without inspecting errors. A training label public in the same release as
the origin is available; a later label is forbidden even if follow-up has ended. Restrict
unverifiable releases only for recorded source reasons before scoring; freeze the exact
remaining pairs and history releases in configuration. Stop without fitting if no valid
training pair survives. Fewer than two usable origins cannot establish consistency over time.

Define each prediction universe from the feature release directory before joining outcomes.
Retain absent future reports as null targets. Record additions, exits, missing components,
missing history and all eligibility reasons. Evaluation requires target `N >= 10`, a complete
valid target and at least one complete earlier receipt percentage. Missing predictors retain
their rows. Prespecified `N >= 20` and `N >= 30` sensitivity summaries filter the same fixed
predictions rather than refitting or selecting populations from performance.
Training eligibility also requires `N >= 10`. Prior history needs positive source N; its logit
uses that prior report's own N, never the future target listing count.

## Fixed comparisons and fitting

First calculate persistence (latest complete public receipt percentage) and historical mean
(simple program mean of complete earlier percentages). History requires full follow-up before
the target listing start; historical cohorts must not overlap. A missing latest report may
use an earlier valid report, with that provenance recorded. No future report availability or
report-count feature may enter the model.

Fit one Ridge family, with three fixed input groups:

1. History: prior receipt logit, mean earlier receipt proportion, and `log1p` prior listing N.
2. History plus access: add log `TX_RR`, `log1p(TMR_TxPy_c)`, `log1p(TTT_25_C)` and their
   missingness indicators, from the eligible earlier source.
3. History plus access plus acceptance: add log overall/low/medium/high/hard-to-place OAR,
   `log1p` overall expected acceptances, overall log credible-interval width, and their
   missingness indicators. Use the original importable feature transformations and exact
   allowlisted field names; exclude report count, identity/location, safety and candidate mix.

All groups use identical eligible training and evaluation rows. Within each training fold,
fit median replacement with empty-column retention, standardization, then Ridge with
`alpha=1`, `solver=lsqr`, `tol=1e-8`, `max_iter=10000`. There is no parameter search: the small
number of genuinely available training cohorts cannot support reliable tuning. Ratios used
in logs must be positive; suppressed inputs remain null with explicit indicators. Zero is
permitted for nonnegative count/time `log1p` inputs. Never split programs randomly into rows.

## Errors, uncertainty and stopping

Report every model against both simple forecasts on identical rows; also compare access with
history, full with history, and full with history-plus-access. The last is the primary
incremental comparison. Calculate average absolute error in percentage points per origin,
then average those origin means equally. Report origin-specific and origin-balanced signed
error (`prediction - observed`) and secondary candidate-volume-weighted error within each
origin, averaged equally across origins. This weights listing counts, not unique patients.

For each fixed contrast, use 2,000 whole-program paired bootstrap draws with seed `20260908`.
A drawn program brings all its repeated cohorts into both models; each origin retains equal
weight. Use linear 2.5th/97.5th percentiles and label these descriptive intervals. Sort keys
before sampling so input order cannot change the result. Do not claim accuracy in a new period.
Redraw samples missing an evaluation origin; allow at most 100 times the requested number
of draws, fail on exhaustion, and record attempted and rejected counts.

Acceptance development stops unless the full model reduces balanced mean absolute error by
at least **both 0.5 percentage points and 5%** versus history-plus-access and each simple
forecast. Require improvement against each of those comparators in both evaluation origins,
absolute signed error no greater than 2 points in either origin, and no more than 0.5 points
worsening in absolute bias against each of those same three comparators (persistence,
historical mean, and history-plus-access), per origin and overall. The 0.5-point
minimum requires a material project-level gain beyond tiny differences in rounded aggregate
data; 5% scales it to baseline difficulty. Bias limits prevent average gains from masking
systematic over/underprediction. These are project continuation rules, not clinical thresholds.
Intervals describe uncertainty but do not create a confirmatory test or a promotion rule.
Fewer than two usable evaluation origins automatically fails the continuation rule.

Report every planned comparison regardless of direction. Do not revise endpoints, features,
model families, time horizons, sensitivity thresholds or gates after errors are viewed.

## Reproduction and claims

Study identity: `kidney_deceased_donor_receipt_0023_v1`. Configuration lives in
`configs/receipt_study/`. Research output is authorized under ignored
`data/receipt-study/v1/<run-sha256>/`, with write-once completion and validated loading.
Temporary source verification belongs under `data/receipt-study/`. Track code, tests, the
contract, source fingerprints, concise evidence and an ordinary-language results document;
do not add a tracked analytical release or alter original V1/V2/follow-up outputs.

Each run records source/configuration/specification hashes, method evidence identity, Git
commit and dirty-source identity, dependency-lock hash, UTC build time, exact cohorts,
feature lists, model parameters, exclusions, all fixed errors and program-resampling results.
Reproduction uses verified local inputs and documented commands. Reject traversal, symlink
redirection, changed input/output hashes, missing files, partial completion and overwrites.

These historical outcomes were previously parsed or inspected, and the question follows
earlier findings. Results remain exploratory. No model promotion, future forecast, clinical
or regulatory advice, causal interpretation, ranking, patient-level prediction or benefit
claim is authorized. Original V2 results and its prohibition on promotion remain intact.
