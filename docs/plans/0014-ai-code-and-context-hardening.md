# Plan 0014 — AI-generated code and context hardening

**Milestone:** M8 AI-generated code and context hardening  
**Status:** done  
**Started:** 2026-09-04

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| AI-assisted changes remain subject to executable security checks instead of prose-only review | Ruff security rules run in the existing lint gate; production assertions and unvalidated URL-opening paths are removed or explicitly justified | done |
| Source acquisition rejects unsafe URL schemes even when a caller constructs a `SourceRecord` without the manifest loader | A focused negative test fails before the fix and proves that the opener is never called for a non-HTTPS source | done |
| Complex configuration validation stays locally understandable to human and AI reviewers | Experiment and release validation are split along existing contract sections and a checked cyclomatic-complexity ceiling prevents another monolithic parser | done |
| Generated tests follow pytest conventions and target observable behavior | Pytest-style lint joins CI; the new security regression exercises the boundary rather than asserting implementation text | done |
| Future agents receive high-signal, non-conflicting context without preloading unrelated history | `AGENTS.md` defines progressive, just-in-time context routing, dependency verification, reuse-before-abstraction, and evidence handoff rules | done |
| The audit distinguishes remediated findings, existing strengths, and residual risks | A repository-specific audit cites primary research and records the command evidence from this change | done |

## Test-first record

Before production edits:

1. Add a download regression proving non-HTTPS sources are rejected before the injected opener runs.
2. Extend the repository-policy test to require security, complexity, and pytest-style Ruff gates.
3. Run both focused tests and record that they fail for the intended missing controls.
4. Refactor and harden only enough to make the focused tests and lint gates pass.

The experiment-loader split and documentation edits preserve behavior. They use the existing
configuration contract tests as characterization coverage; no new scientific behavior, source
meaning, feature, split, metric, promotion rule, or frozen replay artifact is introduced.

## Audit boundaries

- Do not alter `configs/experiment.yaml`, `configs/frozen_experiment.yaml`, source hashes, model
  outputs, release artifacts, or the persistence promotion decision.
- Do not add a dependency merely to perform the audit.
- Do not pursue cosmetic rewrites, blanket "DRY" refactors, or arbitrary file-size limits.
- Treat justified cleanup handlers and fixed offline Streamlit rendering as intentional unless an
  executable failure demonstrates otherwise.
- Do not create a commit or release tag without explicit user authorization.

## Completion evidence

- The first focused test run failed three cases for the intended reasons: `http:` and `file:`
  source records reached the injected opener, and the Ruff configuration omitted `S`, `C90`, and
  `PT`.
- The downloader now applies the same absolute-HTTPS-file predicate at manifest parsing and at the
  network boundary. Both negative cases pass without invoking the opener.
- Ruff security, McCabe complexity (maximum 15), and pytest-style rules run through the existing
  `ruff check .` CI command. Test assertions have the narrow `S101` exemption; reviewed fixed Git
  subprocess calls and verified HTTPS openers have line-level or file-level explanations.
- Six production type-narrowing assertions were removed. Experiment target/feature and temporal
  parsing, replay identity checks, and release-bundle validation are split by contract boundary.
- `uv sync --frozen`, Ruff format and lint, strict mypy, and all 143 tests pass. Core
  data/modeling/reporting branch coverage is 83.93%.
- All nine immutable cached sources verify. A disposable clean data build reproduced 10,515
  signal rows and 2,103 panel rows; the backtest reproduced 2,763 baseline predictions, 921 ridge
  predictions, and selected alpha 10.0.
- A disposable release build reproduced 12 files, 1,229,848 total bytes, and content identity
  `1de89083ceebfda9afaf2d6b1c6ba3f1e6d0c1a1da16df9d09d994c4ec3581ad`. Temporary outputs were
  removed after verification. The write-once frozen replay was not rerun.
