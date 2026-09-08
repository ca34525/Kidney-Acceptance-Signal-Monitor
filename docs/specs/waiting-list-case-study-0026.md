# Waiting-list case study: frequency, size and program accounting

Version 1, September 8, 2026. The request to carry out [Plan 0026](../plans/0026-waiting-list-case-study.md)
authorizes this separate descriptive study and its ignored output root. The contract is fixed
before new calculations. The completed Plan 0025 study, inputs, settings and results are preserved.

## Population and question

How often did a growing kidney waiting list accompany more recorded transplant removals, how
large were those changes, and how do one program's annual records reconcile? One record is a
composite `(CTR_CD, CTR_TY)` program and calendar year. Registrations and removal events are
counted, not unique people nationally or independently verified procedures.

Use only the completed Plan 0025 run
`ad9a92cc0d20d407ab118f6b171e24bd9182a35557f149285a36035c45106cc4`.
Its completion marker SHA-256 is
`2b24e865f2247fe11d190f7f89b8f49aa1da530ad2756f485ff7831b00bf243e`.
The marker binds all six payloads, including annual counts, comparisons, QA, summary, revisions
and provenance. Verify each fingerprint before use; validate schemas and recompute accounting
to check saved values, without rebuilding sources or rerunning the continuation rule. Bind the
original specification, configuration and source ledger to the recorded provenance hashes.
Require bounded regular files, confined paths and no filesystem redirects. Missing, malformed,
duplicate, nonfinite, mismatched or tampered inputs produce actionable errors.

Comparisons stay fixed at 2023, 2024 and 2025 against their preceding calendar years. Inherit
earliest verified annual vintages, complete integer counts, exact annual reconciliation,
continuous year boundaries and positive current starting registrations. All eight removal
categories remain distinct. Transplant removals here combine deceased- and living-donor removals
at the reporting program; transplant elsewhere is separate. Retain exclusions and unknown values.

## Summaries fixed before calculation

Within each year, among all eligible programs with current growth greater than zero, report
increased, unchanged and decreased transplant removals with numerator, growing-program denominator
and percentage. Every program has one weight within a year; do not pool repeated program-years.

For all growing programs and separately for those with increased transplant removals, report
program count, minimum, 25th percentile, median, 75th percentile and maximum of signed transplant
change. Percentiles use `linear` interpolation. The two quartiles bound the middle half of
observations. Retain zeros, decreases and extremes; no distribution fit, trimming, significance
test, new threshold or uncertainty interval is authorized.

Report both raw removal events and `100 * change / current.start`, using the current year's
starting registrations for each program. The latter is change relative to list size, not a
patient probability, percent increase from the previous transplant count, or patient-year rate.
Use shared scales across years within each unit and retain exact values in supporting tables.
Carry forward Plan 0025's coverage, common-program and size-group results with attribution.
Its successful magnitude rules describe list growth, not a minimum transplant-removal increase.

## Examples and reusable program brief

Use 2025 records from the same 169 programs eligible in all three comparison years. The three
mutually exclusive groups are growing with increased transplant removals, growing with unchanged
or decreased transplant removals, and shrinking regardless of transplant change. Within each
group sort by `(2025 starting registrations, program_key)` and take index `floor((n - 1) / 2)`.
Publish keys, group sizes and indices. Empty groups are unavailable; never replace an example.
Examples illustrate arithmetic and are not a representative sample or quality comparison.

The reusable offline HTML brief accepts a composite program key and comparison year in 2023–2025.
It shows both years' published start, end, additions and all eight removals, and calculated growth:
`end = start + additions - sum(removals)`; `growth = end - start`.
Show a separate breakdown for `change in growth = change in additions - sum(changes in removals)`.
All normalized contributions use the same current starting count. Do not divide contributions
by net growth, sum cross-program medians or invent a balancing category. Unsupported or excluded
comparisons return explicit unavailable explanations; missing source values remain unknown.

Show exact cohorts, publication values with original precision, source references, program key,
artifact identity and the banner “Public aggregate prototype — not clinical or regulatory
decision support.” Review questions may concern registration/listing records, transplant activity
and circumstances, or recorded reasons for other removals. They cannot establish causes or
prescribe interventions. Deaths and deterioration remain visible for shrinking lists.

## Outputs and reproducibility

Authorized ignored root: `data/research/waiting-list-case-study-0026/`. Each new run is write-once,
identified by input, configuration, specification and implementation hashes. Save SHA-256 for
every output and a final completion marker; never overwrite a run or follow symlinks/junctions.
Provenance records original input run and payload hashes, original source hashes, new input-file
and implementation hashes, Git commit and dirty status, dependency lock identity, Python version,
UTC time, years, exclusion information and calculation schema. Model parameters and feature
schema are explicitly not applicable. Figures and HTML are generated from trusted precomputed
records, without workbook parsing, download, fitting or network access.

Deliver a concise analytical brief (about two narrative pages), up to three main figures,
full supporting tables, the three program briefs using one reusable template, reproduction
commands and a five-minute explanation outline. HTML is the offline export format; figures
are also exported for sharing. Render and inspect figures and briefs. Tracked documentation
summarizes results and links reproduction instructions; no new tracked analytical bundle.

This is further description of already-inspected data, not fresh or prospective validation.
No novelty or demonstrated decision benefit is claimed. No forecasting, acceptance join, patient
input, rankings, application integration, deployment, literature search or new data year belongs
to this study. Follow the shared safeguards in [AGENTS.md](../../AGENTS.md). A consequential new
source defect requires a separate documented decision; completion does not require a favorable result.
