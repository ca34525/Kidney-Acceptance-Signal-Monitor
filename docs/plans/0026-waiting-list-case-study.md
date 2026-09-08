# Plan 0026 — Turn the waiting-list finding into an analytical case study

**Status:** C0–C3 complete. **Date:** 2026-09-08.
**Purpose:** produce a useful, explainable portfolio case study; publication novelty is not a goal.
**Starting point:** completed [Plan 0025](0025-waiting-list-viability.md) and its
[recommendation](../waiting_list_viability_results.md). The subsequent request to carry out
Plan 0026 authorizes C0–C3 and the separate output root specified below.

## Question and intended use

How should a program analyst interpret a growing or shrinking kidney waiting list when
registrations, transplant removals and other removals are changing at the same time?

The case study should let a reader answer three ordinary questions:

1. How common was growth alongside increased transplant removals?
2. How large were those transplant-removal changes, including decreases and no change?
3. For one program, which recorded additions/removals account for annual growth and for
   growth accelerating or slowing compared with the preceding year?

Plan 0025 established the first result: 52.8%, 47.4% and 42.3% of eligible growing-list
programs also increased recorded transplant removals in 2023–2025. Its magnitude rules
concerned **list growth**, not a minimum increase in transplant removals. Do not turn its
successful continuation rule into a claim that the transplant increases were all substantial.
The follow-up should show their actual distribution and support a concrete review of records.

## Boundaries and work order

Reuse the completed screen's trusted annual/comparison/QA records and source ledger.
The [original specification](../specs/waiting-list-0025.md),
[settings](../../configs/waiting_list/experiment.json),
[source ledger](../../configs/waiting_list/sources.json) and completed output stay unchanged.
The selected years and distributions have already been inspected; this is further description
of known data, not fresh validation. No new continuation threshold or model contest is needed.

The planned work is one analytical pass followed by one presentation pass. End with a completed
case study or a specific unresolved issue; do not extend into open-ended source audits or searches
for a more favorable result. Preserve the original headline even if the added detail makes its
practical value look more modest, and explain that qualification plainly.

| Step | Deliverable and acceptance evidence | State |
|---|---|---|
| C0 Fix the follow-up contract | Separate specification, typed settings, decision and trusted-input/output boundaries before new calculations | Complete |
| C1 Explain frequency and size | Reproducible distributions for all three years, separate denominators and consistent units; synthetic tests | Complete |
| C2 Explain actual program records | Three examples selected by the fixed rule below, with exact annual and change-in-growth accounting | Complete |
| C3 Package the case study | Short analytical brief, up to three main figures, reusable offline program brief and a five-minute explanation outline | Complete |

### C0 — Establish a small separate contract

Before execution, write `docs/specs/waiting-list-case-study-0026.md`, typed settings under
`configs/waiting_list_case_study/`, and a short architectural decision. Fix the descriptive
population, years, summary methods, example-selection rule and claim boundaries below. Bind the
completed Plan 0025 run by its completion-marker and payload fingerprints; validate its schema
and accounting before consuming it. Missing, corrupt or mismatched inputs must produce an
actionable error. Reuse existing code after symbol/call-site search; do not rebuild completed
studies or introduce a second independent parser.

The proposed separate output root is ignored `data/research/waiting-list-case-study-0026/`.
The execution specification must establish that root and provenance before output is written.
Use a distinct write-once run identity; retain input/run/configuration/specification/implementation
hashes, Git and lock identity, UTC time, years, calculation schema and exclusions. Include a
documented way to regenerate every figure and program brief from the trusted cache. No new
dependency or tracked analytical bundle is anticipated.

### C1 — Separate “how many programs” from “how much change”

Keep 2023, 2024 and 2025 fixed and compare each with its preceding year. Inherit Plan 0025's
composite program identity, earliest verified annual vintage, complete/exact accounting,
continuous boundaries and positive current starting-list denominator. Keep deceased- plus
living-donor removals at the reporting program as the transplant grouping. Other categories,
including transplant elsewhere, stay separate.

For each year:

- Reproduce the count of growing-list programs with increased, unchanged and decreased
  transplant removals. Show the numerator and denominator beside every percentage.
- Show the full distribution of the signed transplant-removal change among **all** eligible
  growing-list programs, then describe the increased-removal subgroup separately. Report
  number of programs, minimum, lower quartile, median, upper quartile and maximum. Explain
  the quartiles as the boundaries of the middle half; fix percentile interpolation as `linear`.
- Show raw events and events per 100 current starting registrations. This denominator measures
  change relative to the list's size; it is not a patient's transplant probability, a percent
  increase from the previous transplant count, or a transplant rate per patient-year.
- Keep annual list growth and change in annual growth separately labeled. Carry the existing
  common-program, size-group and coverage findings forward without rerunning the old gate.

Every program has one weight within a year. Avoid pooling repeated program-years for the main
distribution. Display observed distributions without a fitted bell curve, significance test,
trimmed extremes or an invented “meaningful increase” cutoff. Use shared units/scales across
the three years and retain the full range. Source tables remain available for exact values.

**Acceptance:** a reader can distinguish “53% of growing programs” from “15 additional recorded
transplant removals at the median increased-removal program in 2023,” and from growth of the
waiting list itself. Tests must include ties, zeros, decreases, a large extreme and small
starting lists so filtering, percentiles and denominators cannot silently change that meaning.

### C2 — Make the accounting understandable for actual programs

Use 2025 as the example year, with 2024 beside it. Select from the same 169 programs eligible
in all three Plan 0025 comparison years, using three mutually exclusive example groups:

1. Growing list and increased transplant removals.
2. Growing list and unchanged or decreased transplant removals.
3. Shrinking list, regardless of transplant-removal direction.

Within each group, sort by `(2025 starting registrations, program_key)` and select the lower
middle record: zero-based index `floor((n - 1) / 2)`. Fix this selection before viewing individual
examples; publish the rule and keys. An empty group is explicitly unavailable. Do not replace an
unremarkable example with a more dramatic program. These are illustrations, not a representative
sample or a comparison of program quality.

Each program brief must show both years' published starting/end counts, additions, all eight
removal categories, and calculated annual growth. A separate count breakdown shows the change
in growth: change in additions minus changes in each removal category. Use the same current
starting-list denominator for all normalized contributions. Never add cross-program medians
into an example, divide contributions by net growth, or invent a balancing category.

Add a short explanation of what the arithmetic supports and which internal records an analyst
could review. For example, more registrations suggests examining referral/listing activity;
fewer transplant removals suggests examining transplant activity and its circumstances. These
are review questions, not demonstrated causes or prescribed interventions. Show deaths,
deterioration and other removals even in a shrinking-list example.

**Acceptance:** every displayed count traces to the trusted annual row; both annual equations
and the equation for change in growth reconcile exactly. Selection is deterministic under row
reordering. Fixtures distinguish growth from acceleration and keep missing/zero values separate.
Program identity uses the composite key; any display-name lookup is display-only and must not
change the join or require a new source.

### C3 — Deliver the usable case study

Produce a concise analytical brief (target two pages of narrative) and up to three main figures:
the frequency by year, the distribution of signed changes, and a worked count breakdown.
Put full tables and the three selected program briefs in supporting material. Use ordinary
language, visible counts/denominators, source/cohort/publication dates, program coverage and
the nonclinical/nonregulatory statement. Render and inspect exported figures and briefs.

Provide one reusable offline HTML program-brief template, backed by the trusted precomputed
records, and a documented command to generate it for an eligible program in 2023–2025. Calculation and
formatting logic belongs in importable modules under `src/kasm/`; rendering must not download,
parse workbooks, fit anything or access the network. Unsupported or excluded comparisons get
an explicit unavailable explanation. The three selected examples exercise this same template.

Update the project guide and add a five-minute explanation outline: question, data, finding,
worked example, practical interpretation and limits. Explain the earlier forecasting work as
project history; no old deck rebuild or mandatory author rehearsal belongs to this plan.
Describe this as a descriptive case study; do not claim novelty or demonstrated decision benefit.

**Acceptance:** the case study stands on its own, reproduces the fixed headline and explains the
sizes honestly; a reader can follow the record counts through both equations and identify the
next records to review. The reusable brief works offline, preserves missingness/exclusions, and
has meaningful tests and inspected output. Completion does not depend on another positive result.

## Verification and stopping point

The original planning change was documentation-only. During execution, use the plan → failing test → implementation
workflow for new calculations, trusted-input/output boundaries, selection and brief behavior.
Run the required full code checks in [AGENTS.md](../../AGENTS.md), plus an isolated offline case-study
build, output fingerprint checks and rendered inspection. Test malformed/missing/tampered inputs,
unsafe paths and overwrite attempts at the new boundaries. Do not refit a completed study.

After C3, this plan is done. A program-selector view in the application is a possible separate
next plan if the brief is useful enough to warrant it; app integration and deployment are not
part of C0–C3. Also outside scope: forecasting, acceptance-feature joins, patient-level analysis,
causal attribution, program rankings, new data years, a literature-review project or attempts to
establish publication novelty. A consequential new data defect gets its own documented decision;
routine reuse does not restart the prior audits.

## Planning evidence

Prepared from clean commit `d9abc5d56819e5c5ae72ebce29a7071cf3172ebc` on
`codex/waiting-list-viability`. Only this plan and the roadmap are changed. No analysis, source
retrieval, code/configuration change, generated output or study rerun occurred in this turn.
Verification: independent review approved the scope and counting/selection rules. Local links,
content and whitespace checks passed for both changed documents, including direct checks of this
new untracked plan; `git diff --check` passed. No Python suite was rerun for these prose changes.

## Execution evidence

- Started from clean commit `538a914a297e1410773af1c5bb88b91a4f78c6a5`.
- Before new calculations, fixed the [separate contract](../specs/waiting-list-case-study-0026.md),
  [settings](../../configs/waiting_list_case_study/experiment.json) and
  [Decision 0012](../decisions/0012-isolate-waiting-list-case-study.md). No new source or dependency.
- Regression expectations established before implementation: synthetic signed changes (ties,
  zero, negative, extreme, small denominator), deterministic selection under reordering and
  exact program equations; malformed, missing, mismatched, unsafe and overwritten input/output
  cases; escaped offline rendering and unavailable comparisons.
- RED → GREEN: each new module initially failed its focused test collection because its API was
  absent. Additional failing regressions reproduced duplicate completion keys, root-directory
  redirects, replacement during file reading, provenance identity and nested revision corruption,
  an unreconciled row incorrectly displayed as a valid equation, and omitted narrow chart labels.
  Each was corrected and passed. Final new focused cases: 19 calculation, 36 input, 7 rendering,
  and 22 build tests; one additional link-creation test skips on this host. Tests use synthetic
  fixtures and isolated temporary directories; the integrated build test prohibits network/source
  parsing and compares selected and requested briefs from the same records.
- C0 verified the pinned completion marker and six payloads, 2,144 annual records, 1,637 comparisons,
  169 common programs and 1,195 retained revision records. The loader validates accounting and
  source identity without calling the workbook parser or rerunning the old continuation rule.
- C1 reproduced 56/106, 54/114 and 58/137 growing-program increases. Full signed and increased-only
  distributions are in the [case study](../waiting_list_case_study.md). The original headline
  remains; the added detail shows some increases were just one event.
- C2 fixed selections: ARUA:TX1 (43 candidates, index 21), COSL:TX1 (63, index 31), PAAG:TX1
  (58, index 28). All six annual equations and three change-in-growth equations reconcile.
  ARUA's list grew 56 while growth slowed 52; PAAG's list shrank despite fewer transplant removals.
  Independent factual review checked every narrative number against the trusted records.
- C3 delivered the analytical HTML brief, full tables/observations CSV, three SVG/PNG figures,
  three HTML program briefs, [reproduction commands](../waiting_list_case_study_reproduction.md),
  [five-minute outline](../waiting_list_case_study_outline.md) and updated project guide.
  Browser screenshots inspected the complete analytical brief and both sections of every selected
  program brief. All three PNGs were inspected, including final narrow unchanged-count labels;
  full extremes, counts, units and source dates remain readable. HTML is the export format;
  no printed PDF page-count claim or application change is made.
- Final write-once run:
  `ecf56720c3f3f0b26f68fad70f6fbe0e0c29635ecd7731499a7e9d847ecdce3e`, built
  `2026-09-08T13:51:57.863940+00:00`, 1,098,786 bytes including its marker (18 fingerprinted
  payloads). The first presentation-inspection run `d98fdb9bc6c0e1c4d01b4a50db28188338fe43f4d7ed904399dc7f40c95f0ea9`
  is preserved. Distributions, selections, program JSON and observation CSV match byte-for-byte
  between runs; only presentation/provenance changed. Final implementation hashes match the
  working files. Original input fingerprints remain intact.
- Full required checks passed: `uv sync --frozen`; `uv run ruff format --check .` (112 files);
  `uv run ruff check .`; `uv run mypy src/kasm` (56 files); and the exact required pytest command
  with four coverage roots, branch coverage and the 80% floor: **867 passed, 2 platform-dependent
  skips**, **85.20%** coverage. The separate patient-journey coverage command passed at **85.29%**.
- Isolated generation and verification passed with `uv run --offline python -m
  kasm.waiting_list_case_study.build` and `--verify-run` for the final identity. Actual requested
  ARUA:TX1 briefs succeeded for 2023, 2024 and 2025; 2022 produced an explicit unavailable brief.
  Workspace `UV_CACHE_DIR` and `MPLCONFIGDIR` avoid host-cache write restrictions. No dependencies,
  parser, application, container or original-study artifacts changed, so their extra rebuild/refit
  commands were not applicable. No frozen replay, source refresh or model fit was run.
- Content/local-link review (90 links) and `git diff --check` passed. Generated research output is
  ignored; the proposed Git diff contains only documentation, configuration, implementation and
  tests. No unresolved issue remains in C0–C3.
  Application integration and any further analysis require a separate plan.
