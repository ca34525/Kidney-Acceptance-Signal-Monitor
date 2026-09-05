# Plan 0020 — Explain and investigate the V2 results

**Milestone:** M14 V2 follow-up and 20-minute interview presentation

**Status:** P0a and P1/P2 complete; P3 next; presentation/rehearsal not started

**Current work order, 2026-09-04 (2026-09-05 UTC):** The user-authorized hardening in
[Plan 0021](0021-focused-ai-coding-hardening.md) is complete, including local and CI Docker
verification for commit `5f26ec9`. P0a's documentation and code-explanation pass is complete.
The current substantial batch completes P1/P2 under a separate specification and typed
configuration: exact original reconstruction, the report-count diagnosis, and all five fixed
count-removed comparisons. Changes remain uncommitted. See the
[follow-up results](../patient_journey_v2_followup_results.md) and execution evidence below.
Next is P3's source-verified outcome composition; P4 follows after that evidence is ready.

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

The initial request authorized planning and documentation, and the next implementation request
authorized P0a. The current request authorizes P1/P2, recorded below. Their new exploratory model
comparisons do not change the application or create a revised tracked release.

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

**Status:** complete, 2026-09-05 UTC. The inventory covers root guidance, every
existing document under `docs/`, and Python explanations under `src/kasm/`, `app/`, and tests.
Independent reviews cover historical records, study documents, and V2 code explanations; the
main review covers root guidance and remaining modules and integrates the accuracy checks.

Read and revise existing documentation in the order below. This table defines the scope; maintain
a per-file checklist here as the pass proceeds. Each file must end as `rewritten`, `already clear`,
or `preserved with dated explanation`, with a short reason and review evidence. A glossary alone
does not complete the pass.

| Order | Existing material to cover | Status |
|---|---|---|
| 1 | README, project guide, AGENTS, main SPEC and PLAN | complete |
| 2 | V1/V2 specifications, data/model cards, and reproduction guides | complete |
| 3 | Existing rehearsal guide, presentation explanations, audits, and accessibility checklist | complete |
| 4 | Past plans and decisions in `docs/plans/` and `docs/decisions/`, read one at a time | complete |
| 5 | Existing explanatory comments/docstrings under `src/kasm/`, `app/`, and tests, reviewed by module | complete |

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

**Status:** complete, 2026-09-05 UTC; command and review evidence below.

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

**Status:** complete, 2026-09-05 UTC; all five revisions and 12 fixed contrasts reported.

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
At that branch-setup checkpoint, the documentation rewrite and analytical passes had not started.
No commit or push was made during branch setup. The later P0a completion is recorded below.

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

### P0a execution — 2026-09-05 UTC

- Starting worktree clean on `codex/v2-follow-up`. The user requested the next substantial related
  batch, left uncommitted, and authorized subagents for independent review.
- Acceptance scope: complete P0a's file inventory, readability revisions and historical
  explanations, without changing executable statements, configurations, source inputs, released
  results, or presentation/media payloads. P1–P4 remain later work.
- Documentation-only failing-test exception: wording and docstrings do not add executable
  behavior. Verify Python syntax trees with docstrings removed against `HEAD`, resolve local
  links, compare protected-file hashes, and run the required locked install, lint, type, and
  coverage commands. Do not add tests that merely assert prose.
- Original-data builds, real-data model evaluation, app/container rebuilds, and the V1 frozen
  replay are outside this documentation-only pass; existing tests still check offline flows.
- The per-file checklist below accounts for 112 files: 43 Markdown documents, 64 Python modules,
  and five retained presentation/image files. Outcomes are 36 rewritten, 37 already clear, and
  39 preserved with dated explanation. Files without explanatory prose were explicitly reviewed;
  they did not receive artificial comments merely to create a diff.
- Independent review covered historical records, study documents, and V2 module explanations.
  A separate review of the root/V1 changes corrected an overstatement of source-loader checks
  and documented the wholly missing training-column fill. The final V1 historical notes distinguish
  the fixed replay comparison from the earlier planning inspection of 2025 outcomes.
- Dated factual clarifications preserve earlier evidence: failure of the V1 display rule does
  not establish clinical safety; candidate counts have several fixed V2 uses; installation can
  download packages even though project data commands run offline; and historical coverage
  percentages combine statement and branch counts, with their original directory scope retained.
- The first full suite found one documentation-contract failure (352 passed, one failed): the
  V1 data card no longer contained `Grain`. Restored the term beside its ordinary-language
  explanation; the focused documentation check passed, then the full suite passed. No assertion
  was weakened. Initial formatting checks identified two files; formatting was corrected before
  the successful final checks.

Required command evidence, run with `UV_CACHE_DIR` set to the repository's `.uv-cache`:

| Command | Result on 2026-09-05 UTC |
|---|---|
| `uv sync --frozen` | Passed; 68 packages checked |
| `uv run ruff format --check .` | Passed; 64 files already formatted |
| `uv run ruff check .` | Passed, including the configured security rules |
| `uv run mypy src/kasm` | Passed; 30 source files |
| `uv run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling --cov=src/kasm/reporting --cov=src/kasm/patient_journey --cov-branch --cov-fail-under=80` | Passed; 353 tests; 82.48% combined statement/branch coverage |
| `uv run coverage report --include="src/kasm/patient_journey/*" --fail-under=80 --precision=2` | Passed; 80.44% V2 statement/branch coverage |
| `uv run pytest -q tests/unit/test_repository_config.py::test_required_release_documentation_and_diagrams_are_present` | Passed after restoring the explanatory heading's original term |
| `git diff --check` | Passed |

Preservation checks compared all 64 Python syntax trees with `HEAD`, ignoring only comments and
docstrings; executable statements, strings, types, and test assertions match. All compile in
memory, and existing lint/type/coverage directives are unchanged. The 27 delegated historical
records retain their complete original text after removing just the newly added dated notes.
Protected configuration, release, dependency, and media paths have no diff. All 176 local Markdown
file links and nine local heading anchors resolve. Final independent review found no missing or
duplicate checklist entries and no conflicting current work status. No source refresh, real-data
model run, output rebuild, app/container rebuild, or canonical
replay ran. The tests exercised their existing local fixtures and offline flows.

To repeat the key executable-preservation check while this batch is uncommitted, run from the
repository root in PowerShell. The temporary review helpers under `.uv-cache` are not required:

```powershell
@'
import ast
from pathlib import Path
import subprocess

def code_tree(text):
    tree = ast.parse(text, type_comments=True)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if ast.get_docstring(node) is not None:
                node.body = node.body[1:]
        if isinstance(node, ast.TypeIgnore):
            node.lineno = 0
    return ast.dump(tree, include_attributes=False)

paths = subprocess.check_output(['git', 'ls-files', '-z']).decode().strip('\0').split('\0')
checked = 0
for name in paths:
    if not name.endswith('.py') or not name.startswith(('src/', 'app/', 'tests/')):
        continue
    before = subprocess.check_output(['git', 'show', f'HEAD:{name}']).decode('utf-8')
    after = Path(name).read_text(encoding='utf-8')
    assert code_tree(before) == code_tree(after), name
    compile(after, name, 'exec')
    checked += 1
print(f'{checked} Python files: executable syntax unchanged; compilation passed')
'@ | uv run python -
git diff --exit-code HEAD -- configs artifacts uv.lock pyproject.toml Dockerfile .github docs/demo docs/presentation/*.pptx
git diff --check
```

P0a is complete. P1/P2 next requires the separate follow-up specification, typed configuration,
analysis identity, protected output paths, and failing behavior tests before any diagnostic or
revised model runs. Report-count observations are still investigation leads. The donor/unknown
components, new deck, author walkthrough, and timed rehearsal remain P3/P4 work. No commit or push
was made for this batch.

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

### P0a per-file checklist — 2026-09-05 UTC

All 112 files in the existing scope are accounted for below. Historical plans were
read individually. Python reviews cover explanatory comments and actual docstrings, not
string literals used as fixtures or user-interface content. Such executable strings and
all assertions remain unchanged. The retained media are explained by the rehearsal notes;
this pass neither alters their bytes nor claims a new visual audit or author rehearsal.

#### 1. Root guidance and project explanation

| File | Outcome | Reason | Review evidence |
|---|---|---|---|
| [AGENTS.md](../../AGENTS.md) | rewritten | Explains why study contracts protect the meaning of results; all rules retained. | Reviewed against source contracts and original facts; diff and local-link checks. |
| [PLAN.md](../../PLAN.md) | rewritten | Dates the safer-wording correction and records P0a completion without rewriting historical evidence. | Reviewed against source contracts and original facts; diff and local-link checks. |
| [README.md](../../README.md) | rewritten | Explains the product, error result, study boundaries, timing and next work. | Reviewed against source contracts and original facts; diff and local-link checks. |
| [SPEC.md](../../SPEC.md) | rewritten | Explains ratio units, input/target rows, Ridge and error metrics beside unchanged requirements. | Reviewed against source contracts and original facts; diff and local-link checks. |
| [docs/project-guide.md](../project-guide.md) | rewritten | Original examples and terms already clear; updates P0a completion and remaining work. | Reviewed against source contracts and original facts; diff and local-link checks. |

#### 2. Study contracts, cards and reproduction

| File | Outcome | Reason | Review evidence |
|---|---|---|---|
| [docs/data_card.md](../data_card.md) | preserved with dated explanation | Explains program-year/group rows, offer-ratio units, overlapping donor groups, missingness, and public versus analytic eligibility. | Contract/fact comparison; preserved fields, commands, result tables; link check. |
| [docs/model_card.md](../model_card.md) | preserved with dated explanation | Retains V1 numeric results and defines log-OAR error, temporal folds, preprocessing, bootstrap, quartiles, display decision, and replay restrictions. | Contract/fact comparison; preserved fields, commands, result tables; link check. |
| [docs/patient_journey_v2_data_card.md](../patient_journey_v2_data_card.md) | preserved with dated explanation | Explains original listing denominator, unknown outcomes, nested eligibility sets, and separate safety populations; dates correction of too-narrow SAL_N_C use claim. | Contract/fact comparison; preserved fields, commands, result tables; link check. |
| [docs/patient_journey_v2_model_card.md](../patient_journey_v2_model_card.md) | preserved with dated explanation | Defines baseline versus fitted history, input groups, outcome/logit scale, publication timing, error units, weighting, and the 4.14 versus 0.26 point comparisons. | Contract/fact comparison; preserved fields, commands, result tables; link check. |
| [docs/patient_journey_v2_reproduction_log.md](../patient_journey_v2_reproduction_log.md) | preserved with dated explanation | Retains canonical build identities and commands; explains row units, provenance, trusted offline bundle, and separates environment downloads from offline project commands. | Contract/fact comparison; preserved fields, commands, result tables; link check. |
| [docs/reproduction_log.md](../reproduction_log.md) | preserved with dated explanation | Retains dated V1 commands and evidence; explains different row units, canonical versus audit, exact-byte identities, and write-once replay boundary. | Contract/fact comparison; preserved fields, commands, result tables; link check. |
| [docs/specs/patient-journey-v2.md](../specs/patient-journey-v2.md) | preserved with dated explanation | Preserves scientific requirements and equations; adds local denominator, timing, eligibility, model/error definitions and dated count-use clarification supported by fixed contract and code. | Contract/fact comparison; preserved fields, commands, result tables; link check. |

#### 3. Presentation, audits, accessibility and retained media

| File | Outcome | Reason | Review evidence |
|---|---|---|---|
| [docs/accessibility_checklist.md](../accessibility_checklist.md) | preserved with dated explanation | Keeps the original V1 evidence and scope while explaining keyboard focus, contrast, WCAG, AppTest, and gap meaning; no new accessibility claim. | Contract/fact comparison; preserved fields, commands, result tables; link check. |
| [docs/ai-code-and-context-audit.md](../ai-code-and-context-audit.md) | preserved with dated explanation | Keeps historical findings, citations, command evidence and fixes; explains audit terms and directs readers from historical open status to completed hardening. | Contract/fact comparison; preserved fields, commands, result tables; link check. |
| [docs/demo/model-evaluation.png](../demo/model-evaluation.png) | preserved with dated explanation | Retained V1 media; its story is explained in the dated rehearsal notes. | Unchanged tracked bytes; no new visual audit or author rehearsal claimed. |
| [docs/demo/persistence-projection.png](../demo/persistence-projection.png) | preserved with dated explanation | Retained V1 media; its story is explained in the dated rehearsal notes. | Unchanged tracked bytes; no new visual audit or author rehearsal claimed. |
| [docs/demo/program-monitor-top.png](../demo/program-monitor-top.png) | preserved with dated explanation | Retained V1 media; its story is explained in the dated rehearsal notes. | Unchanged tracked bytes; no new visual audit or author rehearsal claimed. |
| [docs/demo/program-monitor.png](../demo/program-monitor.png) | preserved with dated explanation | Retained V1 media; its story is explained in the dated rehearsal notes. | Unchanged tracked bytes; no new visual audit or author rehearsal claimed. |
| [docs/presentation/interview-rehearsal-guide.md](../presentation/interview-rehearsal-guide.md) | rewritten | Rewrites spoken explanations while retaining slide names/results and the old deck; dates timing and nonpromotion clarifications and keeps V2 P4 rehearsal separate. | Contract/fact comparison; preserved fields, commands, result tables; link check. |
| [docs/presentation/kidney-acceptance-signal-monitor-interview.pptx](../presentation/kidney-acceptance-signal-monitor-interview.pptx) | preserved with dated explanation | Retained V1 media; its story is explained in the dated rehearsal notes. | Unchanged tracked bytes; no new visual audit or author rehearsal claimed. |

#### 4. Plans and decisions

| File | Outcome | Reason | Review evidence |
|---|---|---|---|
| [docs/decisions/0001-month-precision-prediction-origin.md](../decisions/0001-month-precision-prediction-origin.md) | preserved with dated explanation | Explain prediction origin and elapsed-year metadata without inventing a publication day. | Full file read; original text preserved; dated-note review. |
| [docs/decisions/0002-attempt-forecast-activation.md](../decisions/0002-attempt-forecast-activation.md) | preserved with dated explanation | Distinguish the original decision to attempt activation from the completed nonpromotion outcome. | Full file read; original text preserved; dated-note review. |
| [docs/decisions/0003-tracked-release-bundle.md](../decisions/0003-tracked-release-bundle.md) | preserved with dated explanation | Explain bundle fingerprints, precomputed offline behavior, and the decision's V1-only one-bundle scope. | Full file read; original text preserved; dated-note review. |
| [docs/decisions/0004-patient-journey-v2-scientific-and-path-boundaries.md](../decisions/0004-patient-journey-v2-scientific-and-path-boundaries.md) | preserved with dated explanation | Explain the listing denominator, published-versus-unknown outcome, missing patient detail, and separate safety comparisons. | Full file read; original text preserved; dated-note review. |
| [docs/decisions/0005-v2-nonoverlapping-strict-vintage-design.md](../decisions/0005-v2-nonoverlapping-strict-vintage-design.md) | preserved with dated explanation | Explain the distinct cohort-overlap and publication-timing protections and limited evaluation evidence. | Full file read; original text preserved; dated-note review. |
| [docs/decisions/0006-v2-modeling-and-nonpromotion-freeze.md](../decisions/0006-v2-modeling-and-nonpromotion-freeze.md) | preserved with dated explanation | Explain common-row comparisons, model transform versus reported units, resampling, and nonpromotion. | Full file read; original text preserved; dated-note review. |
| [docs/decisions/0007-preserve-v2-and-plan-explanatory-follow-up.md](../decisions/0007-preserve-v2-and-plan-explanatory-follow-up.md) | already clear | Explains preservation, the two follow-up questions, P0a-first work order, and why inspected data cannot become fresh validation in ordinary language. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0001-repository-scaffold-and-cache-verification.md](0001-repository-scaffold-and-cache-verification.md) | preserved with dated explanation | Explain the locked tool environment and local source verification; distinguish the original missing-cache result from later completion. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0002-verified-atomic-source-sync.md](0002-verified-atomic-source-sync.md) | preserved with dated explanation | Explain temporary-file verification, immutable cache, and why repeat downloads are skipped. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0003-schema-aware-workbook-parser.md](0003-schema-aware-workbook-parser.md) | preserved with dated explanation | Explain workbook parsing, composite identity, the row unit, and the release-code meaning of 2006. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0004-canonical-panel-and-qa.md](0004-canonical-panel-and-qa.md) | preserved with dated explanation | Explain the two row units, evaluation versus display eligibility, and rounding checks. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0005-historical-service-and-walking-skeleton.md](0005-historical-service-and-walking-skeleton.md) | preserved with dated explanation | Explain the first complete offline user flow and why the display reads stored eligibility. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0006-ci-pytest-fresh-checkout.md](0006-ci-pytest-fresh-checkout.md) | preserved with dated explanation | Retain the clear temporary-directory fix and clarify the historical coverage denominator. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0007-baseline-temporal-backtest.md](0007-baseline-temporal-backtest.md) | preserved with dated explanation | Explain simple comparisons, forward-year evaluation, the error scale, and equal year weighting. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0008-ridge-pre-replay-backtest.md](0008-ridge-pre-replay-backtest.md) | preserved with dated explanation | Explain Ridge shrinkage, the alpha tie rule, training-only preprocessing, and the limited candidate gate. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0009-pre-replay-activation-freeze.md](0009-pre-replay-activation-freeze.md) | preserved with dated explanation | Explain prediction-error band calibration, resampling whole programs, separate display gates, and historical authorization state. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0010-frozen-2025-replay.md](0010-frozen-2025-replay.md) | preserved with dated explanation | Explain why lower average error did not meet all promotion requirements and clarify the band result. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0011-offline-product-flow.md](0011-offline-product-flow.md) | preserved with dated explanation | Explain the completed screen flow, matching evidence to displayed data, and preserved nonpromotion behavior. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0012-release-hardening-and-container.md](0012-release-hardening-and-container.md) | preserved with dated explanation | Explain the offline release bundle, separate reproduction evidence, and container permissions. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0013-interview-presentation-package.md](0013-interview-presentation-package.md) | preserved with dated explanation | Distinguish the retained four-minute V1 package from the planned V2 presentation and actual rehearsal readiness. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0014-ai-code-and-context-hardening.md](0014-ai-code-and-context-hardening.md) | preserved with dated explanation | Explain executable security checks, complexity limits, negative tests, and bounded historical audit claims. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0015-patient-journey-v2-foundation.md](0015-patient-journey-v2-foundation.md) | preserved with dated explanation | Explain V2's distinct observed outcome and how separate output locations protect V1. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0016-patient-journey-ledger-and-parser.md](0016-patient-journey-ledger-and-parser.md) | preserved with dated explanation | Explain release-specific definitions, target denominator, model-only transforms, missing wait-time values, and overlap. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0017-patient-journey-temporal-panel.md](0017-patient-journey-temporal-panel.md) | preserved with dated explanation | Explain feature-to-outcome pairs, publication-aware training, missing later reports, and listing-count thresholds. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0018-patient-journey-artifact-publication.md](0018-patient-journey-artifact-publication.md) | preserved with dated explanation | Explain source-bound saved data, semantic checks beyond hashes, and development versus canonical provenance. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0019-patient-journey-v2-completion.md](0019-patient-journey-v2-completion.md) | preserved with dated explanation | Explain one-period evidence, percentage-point errors, differing comparison populations, and clean-source versus development release identities. | Full file read; original text preserved; dated-note review. |
| [docs/plans/0020-v2-follow-up-and-interview-story.md](0020-v2-follow-up-and-interview-story.md) | rewritten | Records batch scope, file reviews, evidence and the next analytical prerequisites. | Reviewed against source contracts and original facts; diff and local-link checks. |
| [docs/plans/0021-focused-ai-coding-hardening.md](0021-focused-ai-coding-hardening.md) | already clear | Recent bounded engineering record already explains every fix, coverage denominator, null-evidence representation, and corrected Docker conclusion. | Full file read; original text preserved; dated-note review. |

#### 5. Module and test explanations

| File | Outcome | Reason | Review evidence |
|---|---|---|---|
| [app/patient_journey_v2.py](../../app/patient_journey_v2.py) | rewritten | Adds the original V2 offline-view purpose and separation from fitting/source logic. | Reviewed 1 docstrings and 0 comments; AST/compile checks. |
| [app/streamlit_app.py](../../app/streamlit_app.py) | already clear | Existing docstring clearly identifies the trusted offline V1 view; no other prose comments. | Reviewed 1 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/__init__.py](../../src/kasm/__init__.py) | already clear | Package name already clear; no analytical explanation to rewrite. | Reviewed 1 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/cli.py](../../src/kasm/cli.py) | already clear | Existing short docstrings explain command parsing, exit status and entry points. | Reviewed 4 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/config.py](../../src/kasm/config.py) | rewritten | Explains source metadata and file fingerprints without overstating loader enforcement. | Reviewed 7 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/data/__init__.py](../../src/kasm/data/__init__.py) | rewritten | States download and validation purpose. | Reviewed 1 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/data/build.py](../../src/kasm/data/build.py) | rewritten | Explains row units, missing future targets, stored eligibility and rounding QA. | Reviewed 14 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/data/cache.py](../../src/kasm/data/cache.py) | rewritten | Explains unchanged source identity and rejection before archive opening. | Reviewed 5 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/data/download.py](../../src/kasm/data/download.py) | rewritten | Explains temporary downloads, verification and completed-file publication. | Reviewed 8 docstrings and 6 comments; AST/compile checks. |
| [src/kasm/data/parse.py](../../src/kasm/data/parse.py) | rewritten | Explains named-field parsing, program/year/group rows and null source values. | Reviewed 12 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/modeling/__init__.py](../../src/kasm/modeling/__init__.py) | rewritten | States earlier-information and year-order purpose. | Reviewed 1 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/modeling/activation.py](../../src/kasm/modeling/activation.py) | rewritten | Explains log-scale band width, coverage denominator and paired program resampling. | Reviewed 11 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/modeling/backtest.py](../../src/kasm/modeling/backtest.py) | rewritten | Explains intact evaluation years, volume groups and error averaging units. | Reviewed 11 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/modeling/challenger.py](../../src/kasm/modeling/challenger.py) | rewritten | Explains fixed penalty selection and training-only median/empty-column treatment. | Reviewed 15 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/modeling/experiment.py](../../src/kasm/modeling/experiment.py) | rewritten | Explains fixed configuration and disruption-year exclusions. | Reviewed 7 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/modeling/features.py](../../src/kasm/modeling/features.py) | rewritten | Explains the matrix and exact allowed input list. | Reviewed 4 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/modeling/replay.py](../../src/kasm/modeling/replay.py) | rewritten | Explains fixed fitting years, separate band role and already-inspected replay limits. | Reviewed 13 docstrings and 3 comments; AST/compile checks. |
| [src/kasm/patient_journey/__init__.py](../../src/kasm/patient_journey/__init__.py) | rewritten | Explain the V2 study purpose and separate nonpromotion boundary. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [src/kasm/patient_journey/artifacts.py](../../src/kasm/patient_journey/artifacts.py) | rewritten | Explain complete-bundle staging, file hashes, build identity, and protected V1 output. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [src/kasm/patient_journey/config.py](../../src/kasm/patient_journey/config.py) | rewritten | Explain fixed input-report/outcome-report relationships, count thresholds, error units, and program resampling. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [src/kasm/patient_journey/evaluation.py](../../src/kasm/patient_journey/evaluation.py) | rewritten | Explain percentage-point errors, equal-release averaging, candidate weighting, paired program resampling, and descriptive limits. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [src/kasm/patient_journey/ledger.py](../../src/kasm/patient_journey/ledger.py) | rewritten | Explain source definitions, measurement/follow-up/publication dates, workbook contracts, and cohort overlap. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [src/kasm/patient_journey/model_artifacts.py](../../src/kasm/patient_journey/model_artifacts.py) | rewritten | Explain original fixed comparisons, the single usable Ridge period, expected-calculation checks, and nonpromotion. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [src/kasm/patient_journey/modeling.py](../../src/kasm/patient_journey/modeling.py) | rewritten | Explain Ridge purpose, retained missing predictors, exact log transforms, training-only preprocessing, and simple baselines. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [src/kasm/patient_journey/panel.py](../../src/kasm/patient_journey/panel.py) | rewritten | Explain program/listing-cohort rows, publication cutoffs, report count, calculated available-cohort reference, and missing later reports. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [src/kasm/patient_journey/parse.py](../../src/kasm/patient_journey/parse.py) | rewritten | Explain listed-candidate denominator, published versus reconstructed outcomes, suppression, composite identity, and exact empirical-logit transform. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [src/kasm/patient_journey/product.py](../../src/kasm/patient_journey/product.py) | rewritten | Explain offline saved results, explicit unreported values, and included measurement spans. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [src/kasm/patient_journey/release.py](../../src/kasm/patient_journey/release.py) | rewritten | Explain the four-file offline bundle, shared build identity, staged validation, and absence of future forecasts. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [src/kasm/reporting/__init__.py](../../src/kasm/reporting/__init__.py) | rewritten | States saved-result display purpose. | Reviewed 1 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/reporting/artifacts.py](../../src/kasm/reporting/artifacts.py) | rewritten | Explains the tracked bundle, fingerprints and recorded origins. | Reviewed 5 docstrings and 1 comments; AST/compile checks. |
| [src/kasm/reporting/history.py](../../src/kasm/reporting/history.py) | rewritten | Explains published history, missingness, stored eligibility and interval labels. | Reviewed 22 docstrings and 0 comments; AST/compile checks. |
| [src/kasm/reporting/product.py](../../src/kasm/reporting/product.py) | rewritten | Explains saved error comparisons and unchanged display rules. | Reviewed 6 docstrings and 0 comments; AST/compile checks. |
| [tests/integration/test_baseline_backtest.py](../../tests/integration/test_baseline_backtest.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/integration/test_data_build.py](../../tests/integration/test_data_build.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/integration/test_frozen_replay.py](../../tests/integration/test_frozen_replay.py) | already clear | Existing comment explains the offline test boundary; assertions unchanged. | Reviewed 0 docstrings and 1 comments; AST/compile checks. |
| [tests/integration/test_historical_app.py](../../tests/integration/test_historical_app.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/integration/test_release_bundle.py](../../tests/integration/test_release_bundle.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/integration/test_ridge_backtest.py](../../tests/integration/test_ridge_backtest.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_activation.py](../../tests/unit/test_activation.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_baselines.py](../../tests/unit/test_baselines.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_build.py](../../tests/unit/test_build.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_cache.py](../../tests/unit/test_cache.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_cli.py](../../tests/unit/test_cli.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_config.py](../../tests/unit/test_config.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_download.py](../../tests/unit/test_download.py) | already clear | Existing comment explains the offline test boundary; assertions unchanged. | Reviewed 0 docstrings and 1 comments; AST/compile checks. |
| [tests/unit/test_experiment.py](../../tests/unit/test_experiment.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_history.py](../../tests/unit/test_history.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_modeling_features.py](../../tests/unit/test_modeling_features.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_parse.py](../../tests/unit/test_parse.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_patient_journey_config.py](../../tests/unit/test_patient_journey_config.py) | already clear | No explanatory comments/docstrings to rewrite; descriptive test names and executable fixture/assertion text remain unchanged. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [tests/unit/test_patient_journey_evaluation.py](../../tests/unit/test_patient_journey_evaluation.py) | already clear | No explanatory comments/docstrings to rewrite; descriptive test names and executable fixture/assertion text remain unchanged. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [tests/unit/test_patient_journey_ledger.py](../../tests/unit/test_patient_journey_ledger.py) | already clear | No explanatory comments/docstrings to rewrite; descriptive test names and executable fixture/assertion text remain unchanged. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [tests/unit/test_patient_journey_model_artifacts.py](../../tests/unit/test_patient_journey_model_artifacts.py) | already clear | No explanatory comments/docstrings to rewrite; descriptive test names and executable fixture/assertion text remain unchanged. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [tests/unit/test_patient_journey_modeling.py](../../tests/unit/test_patient_journey_modeling.py) | already clear | No explanatory comments/docstrings to rewrite; descriptive test names and executable fixture/assertion text remain unchanged. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [tests/unit/test_patient_journey_panel.py](../../tests/unit/test_patient_journey_panel.py) | already clear | No explanatory comments/docstrings to rewrite; descriptive test names and executable fixture/assertion text remain unchanged. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [tests/unit/test_patient_journey_parse.py](../../tests/unit/test_patient_journey_parse.py) | already clear | No explanatory comments/docstrings to rewrite; descriptive test names and executable fixture/assertion text remain unchanged. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [tests/unit/test_patient_journey_product.py](../../tests/unit/test_patient_journey_product.py) | already clear | Existing explanation already states the missing-value and malformed-timing regression purpose in ordinary language. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [tests/unit/test_patient_journey_release.py](../../tests/unit/test_patient_journey_release.py) | already clear | No explanatory comments/docstrings to rewrite; descriptive test names and executable fixture/assertion text remain unchanged. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [tests/unit/test_patient_journey_v2_app.py](../../tests/unit/test_patient_journey_v2_app.py) | already clear | No explanatory comments/docstrings to rewrite; descriptive test names and executable fixture/assertion text remain unchanged. | All prose reviewed; AST unchanged; compile and Ruff checks. |
| [tests/unit/test_product.py](../../tests/unit/test_product.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_release_artifacts.py](../../tests/unit/test_release_artifacts.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_replay.py](../../tests/unit/test_replay.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_repository_config.py](../../tests/unit/test_repository_config.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |
| [tests/unit/test_ridge.py](../../tests/unit/test_ridge.py) | already clear | No explanatory prose to rewrite; descriptive test names and assertions retained. | Reviewed 0 docstrings and 0 comments; AST/compile checks. |

### P1/P2 execution — 2026-09-05 UTC

- Starting worktree clean; the current request authorizes the next substantial related batch,
  using independent review where useful and leaving changes uncommitted.
- Scope: complete P1/P2 under the new follow-up specification and typed configuration.
  Decision 0008 authorizes only the ignored local output root. P3/P4 remain later work.
- Before analytical implementation, recorded the exact five count-removed input groups,
  original reconstruction tolerance (absolute 1e-10 proportion, zero relative tolerance),
  contribution definition, paired population, 12 fixed bootstrap contrasts, and write-once
  output/provenance rules in the separate contract. No revised prediction has run yet.
- Expected evidence: constructed failing tests for reconstruction tampering, contribution sums,
  count removal and training-only fitting; malformed input/path and overwrite tests; original
  release reconstruction followed by one fixed revised comparison, readable report and figures.
- Original config/release/input hashes are read-only. No V1 frozen replay or original-output
  rebuild is authorized by this batch.
- P1's two standalone, offline figures require a plotting library. Add Matplotlib as a direct
  dependency, verified against its official PyPI project and savefig documentation on 2026-09-05.
  Review the lock diff for unchanged existing numerical-package versions. Retain the original
  release's recorded lock identity and identify the new build lock separately; do not rebuild
  either original bundle merely to update its provenance. The original lock remains available
  at its recorded source commit. Prediction reconstruction gates numerical compatibility.
- Report acceptance: one-period population, dates, original listing denominator and units;
  fixed-order tables of all models/contrasts; unavailable wording when training SD is zero;
  deterministic standalone SVG/PNG figures. Focused tests check numerical text, missing states,
  nonpromotion and output determinism without asserting chart pixels.


P1/P2 completion evidence:

- Separate contract and Decision 0008 preceded analytical implementation. The typed loader pins
  all five revised groups, 12 contrasts, reconstruction/contribution tolerances, bootstrap settings
  and nonpromotion. Original configuration and original feature allowlist are unchanged.
- Independent review of the contract and numerical code confirmed temporal selection, paired
  comparisons, training-only preprocessing and logit contribution arithmetic. A final independent
  review compared every narrative number and identity against the saved evidence and found no
  actionable issue.
- Failing-test evidence: the new config, numerical, artifact/CLI and report test files first
  failed collection because their intended production modules did not exist. Small regressions
  subsequently failed for the intended behavior: missing original eligibility in included audit
  rows (`KeyError`), missing lock file (`FileNotFoundError`), uncaught reconstruction failure, and
  unwrapped report rendering failure. Each now passes without weakening the assertions.
- Focused results: 31 config tests; 29 numerical tests; 18 artifact/CLI tests; six report tests.
  Negative cases cover changed/malformed configurations, prediction keys/values and paired targets,
  count/prohibited-feature injection, missing inputs, protected destinations, symlinked ancestors,
  unexpected filenames, existing empty/full destinations and simulated publication failures.
- The real run matched all 1,744 original evaluation predictions exactly before the revisions.
  Training uses 215 programs; all 13 approaches evaluate the same 218 programs, yielding 2,834
  comparison predictions. Audit data retain every original panel key and eligibility.
- Report-count frequencies and the original review bootstrap reproduce. Removing count lowers
  history-only MAE from 11.488 to 7.320 percentage points. The revised acceptance addition is
  -0.095 points (challenger minus comparator), descriptive interval [-0.491, 0.301]. Every fixed
  comparison, including unfavorable ones, is saved. This weakens the original interpretation of
  a large acceptance gain; it neither disproves acceptance information nor provides a new period
  of validation. No model is promoted.
- Both real figures were visually inspected. A formatting-only refinement gives numeric bar
  labels white backgrounds where the historical-mean line crossed them. This changes no numerical
  behavior, so visual QA and the existing deterministic-render checks cover it; no pixel test was
  added. The original run and the separately addressed final run have byte-identical evaluation
  JSON. No result-guided analytical setting changed.
- The original dependency lock identity remains in the preserved release and is available at
  source commit `cdea5c40302de1797d83698566d2ebb51de16938`. The current lock adds Matplotlib 3.10.9
  and five transitive packages; comparing parsed lock package/version maps showed no changed or
  removed pre-existing version. Official verification: [PyPI](https://pypi.org/project/matplotlib/)
  and [Matplotlib savefig](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html).
  Initial sandbox network access failed; the approved dependency download then succeeded.
- SHA-256 checks before/after cover 42 existing files across both original configurations,
  manifests, generated inputs/results, and release roots: all remain byte-identical. Cache
  verification separately passed all nine source inputs. App/CI/container configuration and
  original modeling modules were not edited. No source download or frozen replay ran.

Required verification, with `UV_CACHE_DIR=.uv-cache` (and a writable `MPLCONFIGDIR` for figures):

| Command | Result on 2026-09-05 UTC |
|---|---|
| `uv sync --frozen` | Passed; 74 packages checked |
| `uv run ruff format --check .` | Passed; 72 Python files |
| `uv run ruff check .` | Passed, including configured security rules |
| `uv run mypy src/kasm` | Passed; 34 source files |
| `uv run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling --cov=src/kasm/reporting --cov=src/kasm/patient_journey --cov-branch --cov-fail-under=80` | Passed; 437 tests, 83.42% combined statement/branch coverage |
| `uv run coverage report --include="src/kasm/patient_journey/*" --fail-under=80 --precision=2` | Passed; 82.43% V2 statement/branch coverage |
| `uv run kasm data verify-cache` | Passed; nine sources, no issues |
| `uv run kasm patient-journey follow-up` | Passed offline; final run below |
| Same follow-up command again | Expected exit 1: run already exists; no overwrite |
| `uv run streamlit run app/streamlit_app.py --server.headless true --server.port 8504 --browser.gatherUsageStats false` | Started; `/_stcore/health` returned `ok`; temporary process stopped |
| `docker build -t kidney-acceptance-signal-monitor:v2-followup .` | Passed with locked production dependencies |
| `docker run --detach --network none --name kasm-v2-followup-smoke-52795f kidney-acceptance-signal-monitor:v2-followup` | Non-root UID 10001; internal health `ok`; Docker health `healthy`, network `none`; temporary container removed |

Docker is outside this session's PATH and its executable requires sandbox escalation. Used the
existing `%LOCALAPPDATA%/Programs/DockerDesktop/resources/bin/docker.exe` with approved escalation;
no Docker installation or configuration change was needed. Container verification covers the
added dependency and unchanged offline product; the subsequent chart-label-only refinement is
covered by the full Python suite and real rendering verification.

Final ignored run:
`data/patient_journey_v2_followup/report_count_v1/c6cc2cea133e7e61e9e42ac284f170baef43d9989d3ab04eea543ffb47af1cfa`.
Its seven payloads total 704,350 bytes, plus the completion manifest. A separate in-memory
recalculation matched the complete evaluation JSON and all 2,834 prediction values; regenerating
all five report/figure files matched their bytes. Every payload size/hash in the manifest passed.
The generated run records the dirty worktree and exact implementation hashes; it is development
analysis evidence, not a canonical release. The earlier figure-layout run remains separately
identified at `52795fe6303fed873ed9cce19ba3db0e09ba78020e1b4b03629081360a70543f`.

The numerical audit used the same importable calculation as the CLI without invoking any writer:

```python
inputs = _load_original_inputs(Path.cwd(), FollowupConfig())
result = evaluate_followup(inputs.rows, inputs.stored_predictions, inputs.config, FollowupConfig())
# Compare JSON-normalized result.evidence with evaluation.json;
# compare patient_journey_prediction_table(result.predictions).to_pylist() with saved Parquet rows;
# compare each render_followup_report(result.evidence) byte payload and each manifest size/hash.
```

Original data-build/model/artifact writers were deliberately not rerun because this follow-up
reads their preserved release. The full suite covers their fixture pipelines and both offline
application flows. No V1 frozen replay, model promotion, future forecast, tracked analytical
bundle, commit, push or PR was created. P3 and P4 remain unfinished; interview readiness is not
claimed by P1/P2 completion.

Final handoff checks: all 153 local links in the seven touched/new documents resolve;
`git diff --check`, Ruff format/check and strict mypy pass on the final worktree. Temporary
agent files, application process and smoke container are cleaned up. Both final figures were
visually verified, and the independent results/narrative review found no actionable issue.
All intended source/documentation/configuration changes remain unstaged and uncommitted.

### Censoring explanation clarification — 2026-09-05 UTC

- User-authorized scope: clarify the project guide's censoring explanation under P0a's
  ordinary-language requirements and P3's outcome-definition safeguards. This is a wording
  clarification, not completion of P3's planned analysis.
- Acceptance: distinguish Table B7's aggregate status snapshots from observation histories;
  explain that standard censoring methods need not know each person's reason for censoring;
  separate the missing data needed to fit those methods from the independent-censoring
  assumption. Preserve the published target, denominator, original results, and unknown outcomes.
- Evidence sources: [SRTR's Table B7 methods](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/technical-methods-for-the-program-specific-reports/)
  describe status at 6, 12, and 18 months and the unknown categories;
  [Jackson et al.'s methodological study](https://pmc.ncbi.nlm.nih.gov/articles/PMC4282781/)
  describes independent censoring and sensitivity to departures from it. Both were inspected
  during the discussion preceding this edit.
- Documentation-only failing-test exception: no executable behavior changes, so no new test
  asserting prose is warranted. Expected evidence is source/wording review, local-link and
  diff checks, and the required locked-environment, lint, type, and coverage commands.
- Completed wording/source review: the guide now states the data limitation explicitly,
  defines independent censoring, and does not claim that unknown status proves the assumption
  false. The mortality example is labeled hypothetical and separate from the study target.
- Verification: all 125 local file links in the two edited documents resolve; `git diff --check`
  passes. Only the guide and this plan changed. Real-data builds and app/container rebuilds
  were not run for this documentation change; original study outputs remain preserved.

Fresh command evidence, with `UV_CACHE_DIR=.uv-cache` and `MPLCONFIGDIR=.uv-cache/matplotlib`:

| Command | Result |
|---|---|
| `uv sync --frozen` | Passed; 74 packages checked |
| `uv run ruff format --check .` | Passed; 72 files already formatted |
| `uv run ruff check .` | Passed |
| `uv run mypy src/kasm` | Passed; 34 source files |
| `uv run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling --cov=src/kasm/reporting --cov=src/kasm/patient_journey --cov-branch --cov-fail-under=80` | Passed; 437 tests, 83.42% combined statement/branch coverage |
| `uv run coverage report --include="src/kasm/patient_journey/*" --fail-under=80 --precision=2` | Passed; 82.43% V2 statement/branch coverage |
