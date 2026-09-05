# Plan 0020 — Explain and investigate the V2 results

**Milestone:** M14 V2 follow-up and 20-minute interview presentation

**Status:** planning complete; analysis and presentation work not started

**Current work order, 2026-09-04 (2026-09-05 UTC):** The user-authorized hardening in
[Plan 0021](0021-focused-ai-coding-hardening.md) is implemented and locally verified; Docker
runtime verification remains pending CI. Resume P0a after that engineering review. The hardening
does not start this plan's new analyses.

**Started:** 2026-09-04

## Purpose

Prepare a project the author can understand, explain, and discuss with senior data scientists and
a biostatistics hiring manager during a 20-minute presentation and panel interview. Clear
explanations are a top-priority acceptance requirement, including in code comments and docstrings.

The first implementation pass is P0a: bring the existing documentation into ordinary language.
This includes past documentation and existing explanatory comments/docstrings, not only material
written during the new analysis. Complete that pass before starting P1–P4.

The completed V2 study asks whether earlier public reports help predict the percentage of listed
candidates known to be alive with a functioning transplant 18 months after listing. The follow-up
asks two narrower questions:

1. Does acceptance information still help after addressing an input that mostly counts how many
   earlier reports are available?
2. How much can we learn by separating living-donor outcomes, deceased-donor outcomes, and unknown
   follow-up status within the published patient-journey outcome?

The current request authorizes this planning and documentation package. It does not start new
model runs, change application behavior, or publish a revised analytical release.

## Read this first

- [Project explanation](../project-guide.md): the ordinary-language explanation, examples, and terms.
- [Original V2 model card](../patient_journey_v2_model_card.md): the completed study's results.
- [Original V2 specification](../specs/patient-journey-v2.md): the completed study's exact design.
- [Decision 0007](../decisions/0007-preserve-v2-and-plan-explanatory-follow-up.md): why the follow-up
  has its own identity and keeps the original evidence.

Keep new decisions, unresolved questions, and command evidence here. Read production code and
tests only when needed for the next step; the explanation guide is not a replacement for the
source contracts or scientific specification.

## Preserve the completed work

V1 and the original V2 remain reproducible records. Retain the scientific content of their
specifications and model/data cards, and preserve their configuration files, source data,
predictions, evaluation results, and release bundles. P0a may improve explanatory prose and code
documentation without changing its meaning or the executable analysis. An added explanation or
dated correction must distinguish the original result from later interpretation.

The original V2 release is identified by:

| Record | Identity |
|---|---|
| Experiment SHA-256 | `ab8c01453c36039b293a8e7453b17b2b326faf734a081a4b67f8bfe132b1de79` |
| Bundle SHA-256 | `ce2844edbcec92c09d0053720d5331dd37ed43ab75de7aa4dd1de431c79a9eee` |
| Source build commit | `cdea5c40302de1797d83698566d2ebb51de16938` |
| Publication commit | `0353f9924b61441dac52e11b71326e6310603e25` |

The first three values come from the tracked release manifest. Publication history is recorded in
[Plan 0019](0019-patient-journey-v2-completion.md). The original release exposes no future forecast.

Before analytical implementation, write a separate follow-up specification and typed configuration. Give the
study a distinct analysis identifier and output locations outside both original studies' output
roots. Reject paths that could overwrite either original release or its generated inputs. Keep
the original model commands and their configuration contracts unchanged. Do not rerun the V1
frozen replay for this work.

The follow-up uses results already inspected. It is an exploratory investigation, not a new
independent test, a prospective study, or a reason to promote a model. It retains the original
publication-date rules, non-overlapping outcome cohorts, and one usable Ridge evaluation period.

## What the review found and what still needs evidence

The original model card reports these errors on the same 218-program evaluation population:

| Approach | Average absolute error in percentage points |
|---|---:|
| Simple average of each program's earlier outcomes | 7.61 |
| Ridge using history and acceptance information | 7.35 |
| Carry forward the most recent outcome | 8.93 |
| Ridge using history information | 11.49 |

Thus the 4.14-point improvement over history-only Ridge is a different comparison from the
0.26-point improvement over the simple historical average. The follow-up must explain both.

The outside review also made these read-only observations. They are preserved as investigation
leads, not new canonical release results. A checked-in calculation and command evidence are still
needed before using them as presentation findings:

- Report count was two for 212 of 215 training programs and five for 208 of 218 evaluation
  programs. Its mean changed by about 25 training standard deviations.
- Reconstructing the original fitted models reportedly matched every released prediction exactly.
  In the history-only model, report count contributed most of the upward change in the model's
  calculation before conversion to a percentage. This does not prove acceptance has no useful
  information, or that access measures are uninformative.
- An additional paired comparison of history-plus-acceptance against historical mean gave an
  error difference of about -0.2604 percentage points, with a descriptive interval of
  [-0.7389, 0.2375], using 2,000 program resamples and seed `20260904`. The comparison was added
  after the original results were seen. Volume-weighted errors were about 6.25 versus 6.03.
- A separate July 2025 source-table check reported a median combined post-transplant unknown
  percentage of about 16.27% across 222 programs with at least ten listed candidates. The
  denominator is the original listing group, not transplant recipients. This was not a matched
  analysis of prediction errors and does not establish their cause.

## Work sequence and acceptance evidence

### P0 Document the direction and communication requirement

**Status:** complete for this documentation request.

- Preserve the original V2 record and link to it from the new material.
- Add the ordinary-language guide, this plan, and Decision 0007.
- Make ordinary-language explanations a standing requirement in `AGENTS.md` and `SPEC.md`.
- Point the README and main plan to the current work, retaining the original V1 demo.
- Correct the V2 data card's outdated description of the current build while retaining its earlier
  development-build history.

Evidence: changed-file review, local-link checks, verified manifest identities, and verification
commands recorded below. Documentation-only work is exempt from the failing-test-first step:
there is no new executable behavior to exercise. No production-code or generated-artifact change
is part of P0.

### P0a Make the existing documentation understandable

**Status:** not started; first implementation pass. **Effort:** inventory first, then estimate
from the actual reading and rewriting needed. Do not treat this as optional presentation polish.

Read and revise existing documentation in the order below. This table defines the scope; maintain
a per-file checklist here as the pass proceeds. Each file must end as `rewritten`, `already clear`,
or `preserved with dated explanation`, with a short reason and review evidence. A glossary alone
does not complete the pass.

| Order | Existing material to cover | Status |
|---|---|---|
| 1 | README, project guide, AGENTS, main SPEC and PLAN | not started |
| 2 | V1/V2 specifications, data/model cards, and reproduction guides | not started |
| 3 | Existing rehearsal guide, presentation explanations, audits, and accessibility checklist | not started |
| 4 | Past plans and decisions in `docs/plans/` and `docs/decisions/`, read one at a time | not started |
| 5 | Existing explanatory comments/docstrings under `src/kasm/`, `app/`, and tests, reviewed by module | not started |

Rewrite explanatory prose in ordinary language where its original meaning stays the same. Explain
purpose first, then population, dates, denominator, units, unknown values, and reasons for important
rules where relevant. Define technical terms where they are used; keep precise mathematical and
source details close enough to check. Existing comments should explain intent without becoming
line-by-line narration. Prioritize source definitions, model inputs, evaluation, and reporting when
reviewing code documentation; record all remaining modules in the checklist as well.

Preserve original numbers, dates, commands, citations, hashes, formulas, field names, requirements,
and decisions. For completed plans, decisions, and frozen-study accounts, add a dated plain-language
explanation where rewriting would obscure what was originally known or decided. Their recorded
evidence must remain intact. Do not exempt historical files from the reading pass merely because
they are old. Keep the original presentation file as a retained release; explain its existing
story in ordinary-language notes, with the new 20-minute deck still belonging to P4.

Keep current operating instructions current. If a factual error is discovered, record a dated
correction with evidence rather than silently treating it as a wording change. Do not change
executable logic, rename identifiers, relax a configuration contract, or rebuild generated outputs
during this pass. A proposed scientific change goes into the relevant later investigation.

Acceptance evidence:

- The per-file checklist accounts for the existing documentation and code explanations, including
  already-clear files and historical records with dated explanations.
- Each document explains its purpose and unfamiliar terms without requiring the reader to consult
  the glossary repeatedly. Analytical explanations state who is counted, when, and in what units.
- Readers can distinguish original V1 results, original V2 results, later review observations, and
  work that is only planned. Hypothetical examples and percentage-point differences are explicit.
- Review the wording changes against the original facts, formulas, source fields, and requirements.
  For code comments/docstrings, check that executable statements and analytical behavior remain
  unchanged; use a comparison that ignores comments/docstrings where appropriate.
- Check local links and run the required repository verification. Record the documentation-only
  failing-test exception; do not add tests that merely assert the new prose.
- Finish a readability review before P1 starts. The author's own walkthrough and timed rehearsal
  remain P4 requirements; this pass does not by itself establish interview readiness.

### P1 Reproduce the surprising result

**Status:** not started; follows P0a. **Suggested effort:** 1–2 focused hours.

Write the smallest reproducible diagnostic using the original trusted panel and predictions. Save
its command, input hashes, row-selection rules, and output in the separate follow-up location.

Acceptance evidence:

- Reproduce the report-count distribution for the exact training and evaluation rows.
- Reconstruct all five original fitted models and compare with their stored predictions before
  interpreting their weights. Specify numerical tolerance before running the comparison.
- Show which inputs move the model's average calculation up or down. Record that these additive
  contributions are on the logit scale, before conversion to percentages; they are not patient
  effects or directly additive percentage-point changes.
- Reproduce the same-program baseline comparisons and the review-only bootstrap comparison.
- Produce one readable figure showing report counts at training and evaluation, and one showing
  prediction errors against the simple historical average.

First failing tests: a small constructed model identifies a report-count-driven shift; a changed
stored prediction is detected; mismatched programs cannot enter a paired comparison. Fixtures test
the calculation rather than hard-coding the real-data scores.

### P2 Make one defined model change

**Status:** not started. **Suggested effort:** 2–3 focused hours after P1.

The planned first change is to remove `historical_target_count` from every Ridge input group in
the separate follow-up. Keep report count in the descriptive data so its meaning stays visible.
Keep the other inputs, transformations, training/evaluation programs, target, Ridge settings, and
missing-value treatment the same. Do not try several history windows and choose the best one from
these already-inspected outcomes.

The follow-up specification and typed configuration must record that choice before revised
predictions are computed. Reuse existing pure functions where their contracts permit it; do not
weaken the original V2 feature allowlist to make the new experiment fit.

Acceptance evidence:

- Report all five revised versions, the original versions, historical mean, and persistence on
  exactly the same evaluation programs. Present average absolute error, average signed error,
  and candidate-volume-weighted error in percentage points. Explain that positive signed error
  means predictions are too high on average, and weighting is not patient-level accuracy.
- Save the exact comparison populations, missingness, and both favorable and unfavorable results.
- Use the existing program-resampling method with recorded settings for planned comparisons;
  describe its limits in ordinary language. It cannot establish performance in a new time period.
- State whether the original interpretation changes. Improvement is not a completion requirement.
- Verify that no original configuration, result, or release payload changed and no future forecast
  became available.

First failing tests: revised models cannot receive report count; original models keep their exact
input contract; shared row selection and training-only preprocessing hold; follow-up writes cannot
reach original output roots. Keep safety and source-boundary tests required by the working agreement.

### P3 Explain the outcome and its unknown part

**Status:** not started. **Suggested effort:** 2–3 focused hours; source reconciliation may vary.

First verify the machine fields and definitions for each intended source release. Candidate fields
identified during review are `SAL_CTXFNC_C18`, `SAL_LTXFNC_C18`, `SAL_CTXUNK_C18`, and
`SAL_LTXUNK_C18`; waiting, death, lost/transferred, and transplant-total fields may provide further
context. Their presence in some cached reports is not a substitute for a release-by-release ledger.

Acceptance evidence:

- Record source field, human explanation, original listing denominator, 18-month timing, missing
  markers, and source citation for every displayed component.
- Check functioning living-plus-deceased donor percentages against `SAL_TOTFTX_C18` within the
  publication's rounding precision. Keep the published total authoritative.
- Use mutually exclusive categories for any chart that adds to a total. Do not add overlapping
  summary rows, or combine separate mortality/graft-failure ratios into this arithmetic.
- Preserve unknown and suppressed values. Missing a component prevents a complete total; it does
  not mean that component is zero. Do not assume unknown patients are healthy or have died.
- Explain per-program medians separately from pooled counts. State whose percentage each number is.
- Match the same program and listing cohort before comparing unknown status with recorded outcomes
  or prediction errors. Show matched, unmatched, and missing counts, including exclusions.
- Keep target-period components as explanations of the observed outcome, never as earlier model
  inputs. An association with unknown status is not proof that reporting caused an error.
- Produce one outcome-composition figure and a short explanation of what remains unknown. Do not
  silently replace the target or claim a survival analysis has corrected the missing follow-up.

First failing tests: donor components use the same denominator/time; overlapping categories cannot
be added; missing components stay missing; rounding reconciliation behaves at boundaries; duplicate
or mismatched program/cohort joins fail; target-period components are rejected as predictors.

Any numerical scenarios for unknown outcomes require their own explicit assumptions and reporting
rule in the follow-up specification before calculation. They are not part of the initial comparison.

### P4 Build the explanation and interview package

**Status:** not started. **Suggested effort:** 2–3 focused hours after evidence is ready.

Choose one program case for a stated reason, such as a disagreement between acceptance context
and the later recorded outcome. Label it illustrative, not representative or evidence of impact.
Show the dates, candidate count, relevant patterns, and the specific question a quality-improvement
reviewer would investigate next. Keep separately timed safety measures clearly identified.

Suggested spoken allocation: problem 2 minutes; outcome and reporting 3; timing 3; results and
investigation 5; program case 3; engineering and next evidence 2; buffer 2. Keep the old four-minute
V1 package as a separate retained deliverable.

Acceptance evidence:

- The author can explain both investigations, the denominator, the simple comparison, and the
  main limitation in their own words. A readable document alone does not establish this; record
  a walkthrough and rehearsal before declaring interview readiness.
- Figures state the question and takeaway in ordinary language and identify the study version.
- New or touched analysis functions explain purpose, units, timing, missing values, and the reason
  for important restrictions. Preserve exact names, equations, types, and concise technical detail.
- Prepare answers about report-count behavior, unknown follow-up versus censoring, why only one
  evaluation period was usable, what acceptance adds, the next useful data request, and how
  AI-assisted work was checked.
- Explain V1's actual MAE improvement and the rule that blocked promotion. Do not claim that
  nonpromotion by itself establishes that persistence is clinically safer.
- The 18-minute story, short demo, and static backup work independently. Update presentation links
  only when the new package exists, keeping the original V2 results accessible.

## One branch for the follow-up

The original V2 PR (#1) has been merged into `main` at `ebe935f`. At the user's request, use one
branch, `codex/v2-follow-up`, for the entire follow-up. It starts from that merged main commit and
retains the uncommitted planning package. This replaces the earlier recommendation to split the
passes across multiple branches and PRs.

Keep the work order within this branch:

1. Complete P0a, the existing-documentation rewrite and its accuracy/readability checks.
2. Complete P1/P2, the reproducible report-count diagnosis and the defined revised comparison.
3. Complete P3, the source-verified outcome components and unknown-status investigation.
4. Complete P4, the interview story, demo, static backup, and rehearsal.

Use focused commits when authorized so each pass remains understandable in review. A draft PR
can be opened after the first push; request final review of the combined follow-up when its
acceptance criteria and required checks pass. Separate analytical study identities and output
locations are still required even though the work shares a Git branch. Keep the original V1 and
V2 evidence intact.

Branch setup evidence: fetched `cta/main`, verified its merge commit and unchanged tree relative
to the completed V2 branch, then created `codex/v2-follow-up` from it. All ten uncommitted
documentation files were preserved byte-for-byte during the switch before updating this section.
The documentation rewrite and analytical passes have not started. No commit or push was made.

## Priorities and open questions

This is a focused follow-up after the original seven-day build, not a reopening of its deadline.
P0a now comes first and adds a substantial existing-documentation review to the scope. Its estimate
depends on the file inventory. The later analysis estimates suggest roughly one substantial workday
plus presentation and verification time; they are not a reason to stop useful work or weaken checks.
After P0a, prioritize P1/P2, then the source-verified P3 explanation and P4. P3 field verification can
run alongside P1/P2 after the documentation pass is complete.

Additional model families, older archives, and deployment infrastructure are not in this first
follow-up. Reconsider them only for a concrete unanswered question after these results.

Open questions to resolve through the work:

- How much of the original error pattern remains after report count is removed?
- Are the donor and unknown-status fields comparable in every intended release?
- How many original evaluation programs remain in a complete matched component analysis?
- Which program case explains the findings without overstating them?

## Verification and evidence log

For implementation, run focused failing tests first, then the full required commands in
`AGENTS.md`. Run cache/source checks and relevant build/app/container checks when those boundaries
change. Do not overwrite preserved original outputs to perform a follow-up check.

For this documentation request:

- Starting worktree: clean.
- Mandatory specification, plan, manifest, and active-plan reads completed.
- Original release identity and clean-build provenance checked against the tracked V2 manifest.
- Independent planning review checked original-study preservation, fixed first model change,
  unknown-status denominators, prediction timing, and ordinary-language requirements.
- Independent final review clarified that V2 predicts a percentage rather than a candidate count;
  the guide now states that explicitly. No other material issue remained.
- Documentation checks passed: ten Markdown-only changed/new files; all 29 local links in them
  resolve; all four V2 payload sizes/hashes match the manifest; the current data-card provenance
  matches the manifest. The check reads UTF-8 explicitly on Windows.
- `git diff --check` passed after replacing new Markdown trailing-space line breaks with blank
  lines. Protected-path comparison confirms no changes to code, tests, apps, configurations,
  artifacts, dependencies, container/CI files, the original presentation, or Plan 0019.
- Required commands below ran with `UV_CACHE_DIR` set to the repository's `.uv-cache`.
- No new real-data model fitting, source refresh, artifact rebuild, or canonical frozen replay
  was run. Tests exercised their existing fixture-based behavior; the released evidence stayed
  unchanged. App/container rebuilds were not relevant to this Markdown-only change.

| Command | Result |
|---|---|
| `uv sync --frozen` | Passed; 68 packages checked |
| `uv run ruff format --check .` | Passed; 63 files already formatted |
| `uv run ruff check .` | Passed |
| `uv run mypy src/kasm` | Passed; 30 source files |
| `uv run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling --cov=src/kasm/reporting --cov-branch --cov-fail-under=80` | Passed; 236 tests, 83.93% coverage with branches included |

### Scope update: existing documentation comes first

- User requested that past documentation be rewritten in ordinary language as the first pass.
- Added P0a with a per-file checklist, existing comments/docstrings, preservation rules, and an
  explicit dependency before P1–P4. This update defines that work; it does not claim the rewrite is
  complete.
- Independent scope review checked that historical files receive attention while dated facts,
  exact requirements, and executable behavior are retained.
- Live GitHub comparison and PR search informed the PR checkpoints above; no GitHub write occurred.
- Verification of the planning amendment passed: `git diff --check`; all 29 local links in the
  ten changed/new Markdown files resolve; P0a precedes P1 and explicitly gates P1–P4; all four V2
  payload sizes/hashes still match the manifest; protected code/configuration/output paths remain
  unchanged. The full 236-test and quality-check results above are from the preceding planning
  update, not a new run for this prose-only amendment. No new behavioral tests were warranted.

Future P0a–P4 command evidence belongs below, with input identities and limitations. The earlier
conversation is not a substitute for a reproducible calculation.

### AI coding practices recheck — 2026-09-04

The user requested a second check of the project's AI coding practices. This bounded review
checks whether the written rules are enforced by code, tests, and CI. It does not complete P0a
or begin P1–P4. Starting revision: `9df76eb`; starting worktree: clean.

Acceptance evidence for this review: inspect the current guidance and relevant boundaries,
compare the workflow with current official guidance, run the required quality checks, reproduce
suspected failures with local fixtures, and record actionable findings with their limits in
the [existing audit](../ai-code-and-context-audit.md#second-review--2026-09-04).
This change records findings only. The documentation-only failing-test exception applies;
future behavior fixes require their own failing regression tests before implementation.

Independent reviews covered source/download boundaries, scientific safeguards, and instruction
consistency. Six open findings remain: missing V2 coverage enforcement; archive processing after
failed verification; unbounded download size; non-HTTPS redirects; a failing no-activation replay
path; and V1-specific agent instructions presented as repository-wide rules. The shipped replay
configuration is unaffected by the no-activation finding. Fixes are not claimed by this review.

Fresh command evidence, with `UV_CACHE_DIR` set to the repository's `.uv-cache`:

| Command | Result |
|---|---|
| `uv sync --frozen` | Passed; 68 packages checked |
| `uv lock --check` and `uv pip check` | Passed; lock agrees and installed dependencies are compatible |
| `uv run ruff format --check .` and `uv run ruff check .` | Passed; 63 files already formatted |
| `uv run mypy src/kasm` | Passed; 30 source files |
| `uv run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling --cov=src/kasm/reporting --cov-branch --cov-fail-under=80` | Passed; 236 tests; 83.93% combined statement/branch coverage for the three V1 directories |
| `uv run pytest -q --cov=src/kasm/patient_journey --cov-branch --cov-fail-under=80` | All 236 tests passed, but the command failed its coverage threshold: V2 measured 76.05% |

The second coverage run used `COVERAGE_FILE=.test-tmp/ai-audit-coverage` to retain the first
measurement. Combining the two reports' covered and total statement/branch counts gives 79.84%
for the four core directories; this is calculated from the two runs, not a separate combined run.
These percentages include branches; they are not branch-only percentages.

No real-data fitting, source refresh, canonical replay, or artifact rebuild ran. Existing tests
checked both tracked releases and offline application flows. Docker/process builds and live
dependency-vulnerability or GitHub policy checks were not rerun for this documentation-only audit.
Original scientific configuration, code, tests, and release outputs remain unchanged.

Final documentation verification: `git diff --check` passed; all 15 local links in the two
review documents resolve; exactly those two Markdown files changed. Independent review found
no necessary corrections and confirmed that completed checks, inspected controls, open fixes,
and the limits of the synthetic reproductions are distinguished. No commit was created.
