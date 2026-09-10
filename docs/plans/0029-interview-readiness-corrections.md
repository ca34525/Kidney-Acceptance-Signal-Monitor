# Plan 0029 — Correct sources, trusted loading and interview explanations

**Status:** complete, R0–R4. **Date:** September 8, 2026.
**Branch:** `codex/interview-readiness-fixes`.
**Authorization:** the user's outside-review follow-up requests the source-definition audit,
integrity repair, presentation correction and related substantive omissions. No new model
search, source refresh, forecast release or canonical replay is part of this work.
**Decision:** [0016](../decisions/0016-retire-bias-gate-and-correct-readiness.md).

## Purpose and boundaries

Make the existing work accurate and explainable for a 20-minute Associate Data Scientist
interview. Record the original exact-bias gate as a design mistake, remove its endorsement
from current explanations, and retain original configuration/results only as historical
evidence. Plan 0027's fixed thresholds describe its completed research comparison; they do
not establish user benefit or automatically authorize deployment. Its numerical results
remain unchanged. Plan 0028 remains unimplemented.

This is a source/documentation audit and a software boundary repair, not a new statistical
study. Read source definitions and existing predictions only as required to establish facts.
Any new model fitting or quantitative sensitivity needs a separately fixed analysis design.
No original input hashes, frozen configurations or analytical bundles may be overwritten.

## Work and acceptance

| Item | Behavior and required evidence |
|---|---|
| R0 Record the corrected policy | Decision and active specifications identify the exact-bias rule as a mistake. Current language stops celebrating it. Separate research model choice from intended-use deployment approval; explain provisional thresholds and the limits of the band gate. |
| R1 Resolve source definitions | A cited release/cohort audit identifies the AOOS exclusion, evidence for preceding methods, possible source corrections and what remains unknown. Bind local source evidence to URL, retrieval/status/type/size/SHA-256. Annotate affected current claims/views; make no unsupported statement that scores are invalid or that the change caused improvement. |
| R2 Verify before display | App accepts only the processed/modeling siblings of one complete validated release. Default paths and explicit overrides use the same trust checks. A changed same-schema signal, missing/invalid manifest or mixed release paths fails before display; a legitimate copied bundle works offline. Preserve a smallest failing regression before implementation. |
| R3 Correct presentation and current explanations | Fix July 2026 Table B7 to July 2023–June 2024 listings, the related follow-up timing and one-period explanation. Correct current slide sources, notes, decks and backups that repeat the mistake or endorse the withdrawn gate. Retain valid evidence, design and author-approved sequence; no broad redesign or new 20-minute deck. Render and inspect affected final decks. Clearly identify the current package and superseded historical packages. |
| R4 Close adjacent omissions and verify | Review touched claims, dates, transformed units, release status and missing checks. Fix substantive defects within this boundary; defer unrelated refactors and new science with reasons. Run required lint/types/full tests, trusted loading and offline startup. Record source-audit limits, actual command results and remaining author rehearsal once below. |

Documentation-only policy changes have no meaningful failing software test; review content,
links and whitespace. Presentation corrections require rendered inspection. No new Python
dependency is planned. App boundary changes follow the repository's failing-test-first rule.

The app override contract narrows to complete release bundles: `KASM_ARTIFACT_DIR` points to
`<release>/processed` and `KASM_MODELING_DIR` to that same release's `modeling`. Unpackaged
development inputs remain usable through analysis functions, not through the trusted app flow.
Explain an invalid configuration with an actionable error instead of silently bypassing checks.

## Future selection policy

Use year-balanced absolute log error as the primary research comparison, with the same
programs/years and train-only procedures. Display ratio-unit error, signed error by year,
large individual misses and important groups. Prefer a simple procedure when its observed
performance is comparable; do not claim a material advantage for the 0.66% Ridge difference.
Do not manufacture another numeric utility threshold from the already-inspected results.
Deployment requires an explicit use case and a reasoned review of consequences and acceptable
errors. The source-definition audit precedes that decision.

Keep forecast bands withheld. A future specified band study should evaluate coverage and
width together with a proper interval score and prespecified diagnostic groups; inclusion of
80% in every binomial confidence interval is neither a calibration guarantee nor a universal
deployment rule. This plan does not change or rerun the fixed historical band comparison.

## Verification and evidence

- Starting worktree was clean at `f1149c3`; the requested branch was created successfully.
- R0: current specifications, model/results cards, project guide and README explicitly retire
  the original bias rule and distinguish the provisional research choice from deployment.
  The app explains the mistake; original configuration, scores and artifact flags remain intact.
- R1: [the source audit](../audits/source-definition-0029.md) establishes the July 2025 code-863
  exclusion and January 2026 expansion from dated official minutes and current methods.
  Six published values in each of two NYNS reports match verified pinned workbook rows at
  publication precision. The app, cards and current deck flag both reporting boundaries.
- R2: a regression first showed that changing ALUA's 2025 signal from 1.11 to 1.20, without
  changing its schema, still allowed display. The app now validates the complete manifest and
  every release payload before loading either analytical view. The 36 focused integration
  tests pass, covering corruption, absent/invalid manifests, mixed roots and a valid offline copy.
- R3: corrected current deck, notes and reference guides; historical packages are explicitly
  superseded. July 2026 Table B7 uses July 2023–June 2024 listings with follow-up through
  December 2025. The archive-limit claim is corrected, the bias-gate appendix is replaced by
  observed errors, and back-transformed log predictions are distinguished from arithmetic
  expected OAR. The original 25-slide sequence and chart data are retained.
- R4: CI omitted `src/kasm/acceptance_forecast` from coverage. The existing required-CI
  regression failed on the missing argument, then passed after adding package measurement and
  its independent 80% coverage gate. No new dependencies or unrelated refactors were needed.

Executed checks on September 8, 2026:

| Check | Result |
|---|---|
| `uv sync --frozen` | Passed; 74 packages checked |
| `uv run ruff format --check .` | Passed; 128 files formatted |
| `uv run ruff check .` | Passed, including configured security rules |
| `uv run mypy src/kasm` | Passed; 66 source files |
| Full pytest with branch coverage for data, modeling, reporting, patient journey and acceptance forecast | 975 passed, 2 existing host-dependent symlink skips; 85.69% coverage |
| Independent patient-journey coverage report, 80% minimum | 85.29%, passed |
| Independent acceptance-forecast coverage report, 80% minimum | 89.88%, passed |
| Offline application | Integration critical flow passed; loopback Streamlit process returned HTTP 200 and `ok` from its health endpoint, then shut down |
| Current presentation | Fresh build `interview-corrections-0029-02`; 25 rendered slides inspected, six native tables and five native charts; no package/layout findings; notes, local source references and provenance hashes checked |
| Documentation | Content reviewed, 206 local Markdown link targets verified and `git diff --check` passed |
| Original evidence | No changes to source pins, original experiment configurations, analytical bundles, modeling/forecast implementation or dependency lock; no fit, replay or data refresh executed |

The full test command extends the required command with
`--cov=src/kasm/acceptance_forecast`; both independent coverage reports use `--fail-under=80
--precision=2`. Initial format checking identified one touched test file; it was formatted and
the check passed. Docker was not rebuilt: its packaged-input contract and configuration are
unchanged, and the repaired flow is exercised by offline integration and process checks.

## Remaining limits and handoff

The source-definition chronology is resolved. Exact January treatment of codes 886/887,
possible retrospective archive revisions, the July 2026 correction's complete field list and
the quantitative effect of changed offer definitions remain unestablished by public evidence.
These are recorded uncertainties, not permission to infer unchanged methods or invalidate scores.
Any new sensitivity analysis or release needs its own fixed design and intended-use decision.

The current PowerPoint has been rendered with the artifact renderer. It reports an inherited
Helvetica Neue font decode warning; native PowerPoint/font behavior needs checking on the
presentation machine. The author's 20-minute selection, ownership walkthrough and rehearsal
remain separate work. No patient-selection tool, new model study or Plan 0028 deployment was
started by this correction.
