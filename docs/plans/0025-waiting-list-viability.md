# Plan 0025 — Determine whether waiting-list changes support a useful insight

**Status:** plan prepared; investigation not started.
**Branch:** `codex/waiting-list-viability`. **Date:** 2026-09-08.
**Scope:** one bounded descriptive feasibility investigation using the nine existing workbooks.

## Question and decision

When a kidney program's waiting list grows, what do the reported additions and removals show:
more registrations, fewer removals for transplant, or changes in other removals?

The intended reader is a program analyst or operations lead deciding which internal records
and process to investigate. Increased registrations can prompt a capacity review; fewer
transplant removals can prompt review of transplant activity and its circumstances. Death,
deterioration and other removals must remain visible when a list shrinks. None of these
descriptions establishes that an organ should have been accepted or that care was inadequate.

The objective is a substantive, repeatable finding with a clear consequence for interpretation.
Correct accounting alone is insufficient. A new predictive model is not a deliverable of this
screen; any later forecasting work requires a separate decision.

## Starting evidence and boundaries

Header inspection found matching Table B1 fields in the verified `1808` and `2605` workbooks:
beginning/end counts, additions, deceased/living-donor transplant removals, transplant elsewhere,
transfers, deaths, deterioration, recovery and other removal categories. The complete field
mapping, historical periods and accounting have **not** been validated for this investigation.
[SRTR's Table B1 methods](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/technical-methods-for-the-program-specific-reports/)
explain the annual counts and distinguish removal records from separately reported transplants.
Current methods explain the concept; historical periods need release-bound evidence.

Reuse [the pinned source manifest](../../configs/data_sources.yaml) and verified cached
workbooks. No additional years, external datasets, new dependencies, model fits, app features,
presentation rebuilds or original-study reruns belong to this screen. Preserve the completed
V1, V2, follow-up and receipt studies, their configurations and evidence. Plan 0024 remains
unimplemented and is not part of this work.

Budget the initial investigation to one focused work session. Record a continue, stop or
inconclusive verdict at its end, including any unmet source or verification requirement.
Do not extend the search automatically when the evidence is weak.

## Work order and acceptance

| Step | Required evidence | State |
|---|---|---|
| V0 Planning | This bounded plan, roadmap pointer and separate branch; documentation checks | Complete |
| V1 Source gate | Release-specific field/period map, vintage rule, program coverage and verified category definitions | Not started |
| V2 Accounting | Tested annual reconciliation and comparable consecutive program-year records, with exclusions and revisions reported | Not started |
| V3 Substantive screen | One fixed descriptive comparison, sizes in ordinary units, recurrence across years and program-size sensitivity | Not started |
| V4 Verdict | One-page recommendation, up to three useful figures/tables, reproducible evidence and principal limitations | Not started |

### V1 — Establish what can be counted

Use the existing verified-workbook loader. Inspect Table B1 in all nine releases and record
the machine fields, definitions, units, missing markers, publication precision and exact annual
periods. Establish what the first/second-year column suffixes mean; do not infer dates from V1's
offer-cohort year or the old V2 ledger. Verify the mapping against release-bound report evidence.

One analytical record represents `(CTR_CD, CTR_TY)` and one non-overlapping calendar year.
Additions/removals are events: a person can be removed and listed again. Program totals must
not be described as unique patients nationally. Keep the origin and destination of transfers
and transplant-elsewhere categories explicit; they may not cancel in a selected program sample.

Choose the earliest pinned release with verified complete Table B1 evidence for each year.
Later appearances of that year are revision checks, not additional observations. Retain
disagreements and their provenance; do not average versions or choose the one that fits best.
Verify category exclusivity before summing; do not add both a removal total and its components.

Report absent years/programs, missing cells, newly observed programs, apparent exits and zero
starting counts. They are not zero activity or proof of opening/closure. Require at least three
consecutive usable years for a claim of recurrence; describe the matched program coverage.
Stop the source search at the existing archive boundary if definitions remain unresolved.

### V2 — Reconcile annual change and change in growth

For each fully reported program-year, test the source-defined identity:

`ending count = starting count + additions - sum of mutually exclusive removals`.

Keep published counts authoritative. Derived differences are explicitly labeled calculations.
Retain unexplained residuals and exclude those records from a clean decomposition; never invent
a balancing category or overwrite the source. Integer accounting must agree exactly unless a
specific source definition establishes a different rule. Report how exclusions affect coverage.
Keep deaths, deterioration and other categories separate from transplant removals.

Define `g_t = end_t - start_t` as **growth during a year**. For comparable consecutive years,
`g_t - g_previous = change in additions - sum of changes in removal categories` explains
**why reported growth accelerated or slowed**. Current-year component levels cannot establish
that growth accelerated because registrations increased. Check boundary continuity separately:
a revised count between report versions must not be mistaken for a real change in the list.

Show raw registration/event counts alongside values per 100 registrations at the year's start.
Do not divide by zero. For a decomposition of the change in growth, divide every contribution
by the same stated starting-count denominator; subtracting differently normalized annual rates
does not give that count decomposition. Avoid contribution percentages divided by small net
growth, which can be unstable or exceed 100% when components offset one another.

### V3 — Run one prespecified substantive comparison

Primary comparison: **among programs with a growing list, how often did transplant removals
also increase, and what changes in registrations and other removals accompanied that pattern?**
Compare with growing-list programs whose transplant removals did not increase. Use consecutive
years from the same program, retaining the distinction between growth and acceleration above.
This does not treat increased transplant removals and list growth as contradictory by definition.
The measured events are recorded waiting-list removals for transplant; this screen does not
independently verify completed transplant procedures.

Before calculating comparative summaries, record a compact separate specification, typed fixed
settings and a short decision record. Fix the exact donor/category grouping, source years,
eligible population, minimum coverage, practical magnitude and recurrence criteria there.
Explain magnitude in counts and per-100-starting-list units, with an operations-review rationale.
If a defensible materiality rule cannot be stated before viewing results, the screen is
inconclusive; do not select a threshold from the most attractive result.

Report both sides of the fixed comparison and results for each usable year. Give programs equal
weight in the primary prevalence summary; also show how the conclusion changes with program
size and a fixed common-program sample. Any repeated-program uncertainty must preserve whole
program histories. Do not treat overlapping year-to-year changes as independent evidence.
No search over acceptance subgroups, survival endpoints, model families or policy effects follows
an unhelpful result. Individual illustrative programs must follow a declared selection rule.

### V4 — Decide whether to pursue the direction

**Continue** only if source/accounting coverage is adequate and a practically meaningful pattern
recurs across the specified years, survives the planned size/coverage checks, and changes a
specific interpretation or internal investigation. State the magnitude and affected population.

**Stop** if sound accounting produces only the identity, program-size differences or isolated
examples. **Inconclusive** applies if source ambiguity, revisions, missingness, inadequate history
or unfinished verification prevents a defensible answer. Neither finding calls for a new model
to rescue the story. Statistical significance alone is not an acceptance criterion.

Deliver a one-page verdict, at most three figures/tables and the source/accounting evidence.
Explain the arithmetic contribution to recorded change, without claiming its clinical cause,
better care, an intervention effect or a unique-patient national total. No center leaderboard,
composite quality score or patient/organ input form is permitted.

## Implementation, verification and handoff

No analysis runs in the plan-writing session. Future execution should reuse the acquisition
and validation infrastructure, adding only the smallest importable parser/calculations needed.
Use small failing tests for field/date drift, duplicate year vintages, revisions, composite keys,
null/zero distinctions, nonexclusive categories, reconciliation and the two growth definitions.
A fixture should distinguish a growing list with increasing transplant removals from one with
falling transplant removals. Keep tests about meanings, not exact live-data findings.

The future specification must define a separate ignored output root and provenance before any
analysis output is written; no new analytical release or output root is approved here. Record
source/configuration/specification and implementation hashes, Git/lock identity, UTC build time,
periods, fields and exclusions; model parameters are not applicable. Use the applicable checks
in [AGENTS.md](../../AGENTS.md), including full code checks and an isolated parser build if code
is added. The verdict may be inconclusive within the session budget; incomplete checks cannot
be labeled passed. Never overwrite or refit a completed study for this screen.

This planning change is documentation-only: content/link review and `git diff --check` replace
a failing test and Python-suite rerun. The starting checkout was clean at `d2f9c56`.
`codex/combined-model-investigation` contained no unique commits and was deleted after creating
this branch at the same commit. No commit or analytical execution was performed.

Verification: content and independent scope review passed; local file links resolve in this
plan and `PLAN.md`. Whitespace checks passed for the tracked diff and this new plan.
