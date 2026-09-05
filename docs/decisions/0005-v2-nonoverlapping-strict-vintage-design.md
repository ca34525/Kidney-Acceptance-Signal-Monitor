# Decision 0005 — Use non-overlapping cohorts and strict publication vintages for v2

**Status:** accepted
**Date:** 2026-09-04

## Reading this historical record — 2026-09-05

This decision prevents two different timing errors. Non-overlapping listing cohorts avoid
counting the same listing period in successive outcome groups. Publication-vintage checks then
ask whether an earlier outcome report actually existed when a later prediction would have been
made. Ordering cohorts alone does not answer that second question. The release codes below
identify source files, and each arrow links an input release to its later outcome release. Four
pairs can describe the data, but only one has a usable earlier training pair. That is why the
original Ridge results describe feasibility in one period and cannot support model promotion.

## Context

The v2 source ledger proves that target releases `2505` and `2605` overlap for six months because
the former uses a July–June listing cohort and the latter changes to calendar year 2023. Treating both
as consecutive evaluation folds would count some candidates twice and overstate temporal evidence.

The candidate feature→target pairs also create a separate training-label timing problem. An ordinary
expanding-window backtest would train early evaluation origins on outcomes not published until later
releases. That would be cohort-ordered but not a historically reproducible forecast simulation.

## Decision

Use `1905→2205`, `2006→2305`, `2105→2405`, and `2205→2505` as the primary panel design. Their
target listing cohorts are contiguous, non-overlapping July–June periods. A prediction origin may be
in the target cohort's starting month or at most one calendar month later. The latter allowance keeps
the COVID-delayed August 2020 `2006` release as an explicitly delayed nowcast for the target beginning
July 2020. Calculate the offset from year/month only, retain publication precision, and do not invent
a day. Retain `2305→2605` only as a source-valid exclusion with reason
`overlapping_target_cohort`, and retain `1808→2105` as an exclusion with reason
`prediction_origin_more_than_one_month_after_target_start`; its October release has a three-month
offset from the July target start.

Define the prediction universe from programs present in the feature release. A program missing from
the later target table keeps a null target and is analytically ineligible; a target-only addition is
reported in QA and is not backfilled into the earlier universe.

Use strict publication-vintage model folds. A training pair is available at an evaluation origin only
when its target release is at or before the evaluation pair's feature release in the pinned release
sequence. Under the current sources, only `2205→2505` has an earlier labeled pair available at its
origin: `1905→2205`, whose target is published in release `2205`. No anachronistic expanding folds are
permitted.

## Consequences

The canonical panel can contain four target cohorts, label the zero- or one-month prediction-origin
offset, and preserve target-missing programs without future selection. Current data support only one strict-vintage Ridge evaluation origin with one
training cohort. Any Ridge feature-group comparison is therefore feasibility evidence, not stable
temporal validation, and cannot promote a model into the v2 product. The calendar-year `2605` outcome
remains available for descriptive history or a separately specified future cadence analysis.
