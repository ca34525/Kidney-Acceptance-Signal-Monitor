# Plan 0025 — Determine whether waiting-list changes support a useful insight

**Status:** complete, 2026-09-08; **continue** under the fixed descriptive rule.
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
| V1 Source gate | Release-specific field/period map, vintage rule, program coverage and verified category definitions | Complete; seven verified releases cover 2017–2025 |
| V2 Accounting | Tested annual reconciliation and comparable consecutive program-year records, with exclusions and revisions reported | Complete; 2,144 exact annual reconciliations, 1,637 eligible comparisons |
| V3 Substantive screen | One fixed descriptive comparison, sizes in ordinary units, recurrence across years and program-size sensitivity | Complete; all fixed 2023–2025 conditions and both sensitivity checks pass |
| V4 Verdict | One-page recommendation, up to three useful figures/tables, reproducible evidence and principal limitations | Complete; recommendation and three evidence tables linked below |

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

### Execution record — 2026-09-08

Started from clean commit `1090a9ac11c85852fb4fe5f682ac65126c5db8bb` on the planned
branch. The execution request authorizes completing the separate specification, fixed
settings and isolated ignored research output described below. No comparative summaries
have been viewed before fixing the contract. Source evidence and implementation proceed
independently; unresolved report dates exclude a release rather than inherit V1/V2 dates.

Expected evidence: synthetic tests first for source drift, vintage selection, null counts,
exact accounting, boundary continuity, growth versus acceleration, and comparison/verdict
rules; then an isolated verified-cache build and the required full checks. Documentation
and the decision record use the documentation-only test exception. No dependency is added.
The local commands set `UV_CACHE_DIR` to the repository's ignored `.uv-cache` because the
system cache is outside the writable workspace.

The [separate specification](../specs/waiting-list-0025.md),
[fixed typed settings](../../configs/waiting_list/experiment.json),
[source ledger](../../configs/waiting_list/sources.json) and
[Decision 0011](../decisions/0011-isolate-waiting-list-screen.md) were written before the first
comparative build. The authorized ignored output root is `data/research/waiting-list-0025/`.
There is no new dependency, model, application feature, release bundle or original-study rerun.

Source evidence: all nine verified workbooks have the same Table B1 fields. Seven independently
matched reports establish calendar years 2017–2025; `1808` and `2006` remain excluded because
their historical periods could not be verified. The 154 report/workbook binding counts agree.
Six retained historical evidence files are cached text, not original PDF bytes; that distinction
and their hashes are explicit. See the [source audit](../audits/waiting-list-source-0025.md).

Failure-first evidence: parser, comparison/settings and output-boundary tests initially failed
on absent imports, then passed with implementation. Independent synthetic verdict tests found
that an unknown matched-program denominator could pass coverage; that regression failed before
the denominator check was corrected. Added tests also require fixed source-ledger/evidence
fingerprints and retained death counts for shrinking lists. Final focused result: **61 passed,
1 skipped**. The skip is creation of an actual directory symlink, unavailable on this Windows
host; the normal path/escape, overwrite and missing/changed evidence checks passed.

The isolated command `uv run python -m kasm.waiting_list.build` completed offline at
`2026-09-08T13:04:19.247066+00:00`. Run identity:
`ad9a92cc0d20d407ab118f6b171e24bd9182a35557f149285a36035c45106cc4`.
Its completion marker fingerprints annual records, revisions, comparisons, summaries, QA and
provenance. The latter records implementation/configuration/specification/source hashes,
Git commit and dirty status, lock identity, years and calculation schema. Inputs and this run
are preserved; unchanged reruns refuse overwrite. Restoring the exact ignored input cache in a
fresh checkout is required for reproduction, as documented in the evidence instructions.

All 2,144 annual records reconcile exactly, with no missing counts. Of 1,889 consecutive matched
pairs, 241 fail boundary continuity and 11 have zero current starting counts, leaving 1,637.
Among 1,195 later-vintage comparisons, 268 have count disagreements and 22 have program-presence
disagreements. These values and source identities remain visible; no balancing category or
later-vintage backfill was introduced. The first-appearance and apparent-exit lists are QA,
not claims that programs opened or closed.

The latest sufficiently covered comparison years are 2023–2025. Among growing lists, increased
transplant removals occur in 56/106, 54/114 and 58/137 programs (52.8%, 47.4%, 42.3%). Median
growth in that group is 26.5, 22.5 and 35 registrations, or 9.3, 9.9 and 11.5 per 100 current
starting registrations. Every fixed rule passes, including the same 169 programs and all three
size groups. Independent recomputation checked 23,584 source count cells, all annual identities,
vintages, comparison arithmetic, group summaries, common/size checks and revision records with
no discrepancy. The verdict is **continue the descriptive direction**; any further study needs
its own decision and specification.

Required command evidence (workspace `UV_CACHE_DIR` throughout):

- `uv sync --frozen`: passed, 74 packages checked.
- `uv run ruff format --check .`: passed, 102 files.
- `uv run ruff check .`: passed, including enabled security rules.
- `uv run python -m mypy src/kasm`: passed, 50 source files. The module invocation uses the
  same checker; the standalone launcher was blocked by Windows execution policy.
- Full prescribed pytest/branch-coverage command: **783 passed, 1 skipped**, 104.79 seconds;
  required data/modeling/reporting/patient-journey coverage **85.20%**.
- `uv run coverage report --include="src/kasm/patient_journey/*" --fail-under=80 --precision=2`:
  passed, **85.29%**.
- `uv run kasm data verify-cache`: passed, all nine sources, no issues.
- Isolated parser/research build: passed; no frozen replay, fit, packaging or app/container
  command is warranted by these changes.
- Documentation content, local links, output fingerprints and `git diff --check`: passed.

Handoff check: `.gitattributes` pins the new source ledger to LF, preserving its approved byte
fingerprint on Windows checkouts with automatic line-ending conversion. `git check-attr text eol`
confirmed this rule. This mechanical checkout setting changes no calculation and uses direct
attribute/byte verification instead of another Python-suite run; all recorded run inputs still
match their build fingerprints.

Deliverables: [one-page recommendation](../waiting_list_viability_results.md) and
[three evidence tables, limits and reproduction instructions](../waiting_list_viability_evidence.md).
No implementation work remains in this plan. Limitations are retained: incomplete historical
report retrieval, boundary revisions, selected program coverage, event rather than unique-person
counts, and descriptive rather than causal/prospective interpretation.
