# Waiting-list growth and reported transplant removals

Version 1, 2026-09-08 UTC. Authorized by the request to carry out
[Plan 0025](../plans/0025-waiting-list-viability.md). These comparison rules are fixed before
comparative summaries are calculated. This is one bounded descriptive screen, with no model,
application change or new release bundle.

## Question and source meaning

Among kidney programs whose waiting lists grew during a calendar year, how often did recorded
removals for transplant at that program also increase from the preceding year? Compare those
programs with growing-list programs whose transplant removals stayed the same or fell. Report
the accompanying changes in registrations and each other removal category on both sides.

One annual record represents `(CTR_CD, CTR_TY)` and a non-overlapping calendar year. Counts
describe registrations and removal events; a person may be removed and registered again.
They are not nationally unique people. Transplant removals combine deceased- and living-donor
removals **at the reporting program only**, after source definitions establish that these
categories are mutually exclusive. Transplant elsewhere, transfers, deaths, deterioration,
recovery and other removals remain separate. These are recorded waiting-list removals, not
independent verification of completed procedures or of clinical causes.

## Sources, years and annual accounting

Use only the nine immutable workbooks in [the existing manifest](../../configs/data_sources.yaml).
The candidate calendar-year range is 2016–2025, conditional on release-bound Table B1 evidence;
this is not a claim that every year is usable. A separate source ledger binds each used release
to field descriptions, annual column suffixes, exact calendar periods, category definitions,
publication precision and the evidence fingerprint. Never derive these dates from V1's
offer-cohort year or the original V2 ledger. Unverified releases do not supply analytical rows.
Do not extend the source search beyond the existing archive boundary.

Source-gate resolution before comparisons: independently verified evidence supplies 2017–2025.
Releases `1808` and `2006` are excluded because their Table B1 report periods could not be
verified within this archive search. The other seven releases cover all nine selected years.
The fixed [settings](../../configs/waiting_list/experiment.json) and
[source ledger](../../configs/waiting_list/sources.json) record that restriction.

For each year, choose the earliest pinned release with verified complete Table B1 evidence.
Keep that vintage even if a later appearance changes counts or would reconcile more rows.
Later appearances are revision checks only. Preserve source and revision values, missing
markers and provenance; do not average or fill across vintages. The selected vintage applies
to the whole year, not separately to each program. Missing programs are unknown activity, not
zero activity or proven opening/closure. Names and locations are not join keys or predictors.

All reported counts must be finite, nonnegative integers or null. Duplicate composite program
keys, unexpected field/date definitions and nonexclusive removal mappings are hard errors.
For a fully reported year, calculate the residual from:

`end = start + additions - sum(mutually exclusive removal categories)`.

Reconciliation requires exact integer equality. Keep source counts authoritative; never add a
balancing category. A missing required count or nonzero residual excludes that annual row from
clean accounting and is reported in QA. Retain deaths and deterioration even when a list shrinks.

An eligible comparison requires both selected annual rows, consecutive years, complete counts,
exact reconciliation in each year, `previous.end == current.start`, and `current.start > 0`.
Report boundary discontinuity separately from annual residuals because revisions can change
the recorded starting count. A zero current start is excluded from normalized comparisons,
not converted to zero growth. Retain annual records and all exclusion reasons in source QA.

## Calculations and denominators

Let `g_t = end_t - start_t` be growth **during the current year**. Define transplant change as
`delta_transplants = (deceased + living)_t - (deceased + living)_(t-1)`.
The primary population has `g_t > 0`; the two groups have `delta_transplants > 0` and `<= 0`.
Zero transplant change belongs to the second group. Increasing transplant removals and list
growth can occur together, without implying a contradiction or establishing what caused either.

Changes in category counts explain a different quantity: **change in growth**,
`g_t - g_(t-1) = delta_additions - sum(delta_removals)`.
A larger current list alone does not establish that growth accelerated. Report growth and
change in growth separately. For every per-100 calculation, divide the raw count or contribution
by the same `current.start` and multiply by 100. Do not subtract annual rates with different
denominators or divide contributions by net growth. For example, a hypothetical increase of
10 registrations with 200 at the year's start is 5 registrations per 100 starting registrations.

For each usable comparison year report matched source-pair count, eligible count and fraction,
growing count, count in each group and prevalence of increased transplant removals among growing
programs. Every program receives equal weight within a year. For both groups report medians of
current growth, change in growth, additions and each removal-category change, in raw counts and
per 100 current starting registrations. Show current category levels so shrinking lists do not
hide deaths, deterioration or other removals. These are program summaries, not pooled patient rates.
Any pooled primary summary uses each program's mean increased-removal indicator among its
growing years, then the mean across programs. Pooled subgroup magnitude uses each program's
median among its observations in that subgroup, then the median across programs. The pooled
summary is secondary; it cannot replace a failed individual-year condition.

## Fixed sufficiency, magnitude and robustness rules

A comparison year passes coverage when it has at least 100 eligible programs, at least 80% of
the composite keys present in both selected source years, and at least 30 growing programs.
The matched denominator includes incomplete, unreconciled, discontinuous and zero-start pairs.
Select the **latest three consecutive comparison years** that pass these coverage rules before
computing group prevalence or magnitude. If none exist, the verdict is inconclusive. Display
all usable comparison years; do not substitute a more favorable three-year window after results.
Three comparison years require four annual observations; overlapping changes are not independent.

The primary pattern must meet all three conditions in **each** selected comparison year:

- At least 25% of growing programs also increased transplant removals.
- Among those programs, median current growth is at least 10 registrations.
- In that same group, median current growth per 100 starting registrations is at least 5.

These are fixed practical screening choices, not validated clinical or statistical thresholds.
A pattern affecting at least one in four growing programs changes the interpretation of list
growth often enough to merit examining registrations alongside transplant activity. Ten extra
registrations and growth of five per 100 jointly require an appreciable count and a meaningful
change relative to the list being managed. Neither threshold alone establishes capacity strain.

Use two fixed checks on the selected three years:

1. **Common programs:** retain programs eligible in every selected comparison year, regardless
   of whether their list grew each year. Require at least 80 common programs and at least 20
   growing programs in each year. Recompute the three primary conditions within this sample;
   all must pass in each year. Too few programs makes robustness inconclusive.
2. **Starting-list size:** use current starting counts `<100`, `100–499`, and `>=500`. Within
   each size group, pool growing observations across the selected years. Require at least 10
   distinct growing programs and at least one with increased transplant removals per group.
   First calculate each program's mean indicator of increased transplant removals over its
   growing observations in that group, then average those means across programs. This prevalence
   must be at least 15% in **every** size group. Among observations with increased transplant
   removals, first calculate each program's median growth per 100, then the median of those
   program medians; this must be at least 5 in every size group. Report raw growth in the same
   way, but impose no 10-registration rule within size groups because that mechanically disfavors
   small lists. A program may contribute to more than one size group in different years.

The lower 15% size-group threshold checks that the recurring pattern is not confined to one
list-size group without demanding identical prevalence across differently sized programs.
An empty increased-removal subgroup with otherwise sufficient growing programs is a failed
pattern, not missing evidence. Fewer than 10 growing programs makes that size check inconclusive.
No uncertainty interval, significance test or program-level illustration is required. No search
over alternate groupings, periods, thresholds, policy effects or endpoints is permitted.

## Verdict and reproducible evidence

**Continue** requires verified source meaning, the coverage gate, all primary conditions and
both robustness checks. The interpretation is that list growth can coexist with increased
transplant removals at a material frequency and scale; operations review should examine
registrations and other removals before interpreting growth as reduced transplant activity.
Continuation authorizes a separately proposed direction, not automatic forecasting or deployment.

**Stop** when source/accounting evidence and sensitivity sample sizes are sufficient but the
fixed materiality, recurrence or robustness conditions fail. **Inconclusive** applies when source
ambiguity, missingness, revisions, insufficient history/sample sizes or unfinished verification
prevents a defensible decision. State failed and unassessed conditions separately. No model may
be added to rescue an unhelpful result, and the recorded results are not prospective validation.

The authorized output root is ignored `data/research/waiting-list-0025/`. Keep a separate run
identity; do not overwrite completed studies. Before comparative output, freeze typed settings
and the source ledger, and record their hashes together with this specification's hash.
Each run records source hashes, implementation file hashes, Git commit and dirty status,
`uv.lock` hash, UTC build time, calendar years, fields, vintage selection and exclusions.
Model parameters and feature schema are not applicable; record the calculation schema instead.
Retain annual records, revisions, eligible comparisons, summary results and QA as reproducible
local evidence. Deliver a one-page verdict and at most three reader-facing figures/tables.
Apply [repository verification](../../AGENTS.md), including an isolated parser build. Keep the
nonclinical/nonregulatory limits and all original study inputs, outputs and claims intact.
