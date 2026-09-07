# Plan 0013 — Interview presentation package

**Milestone:** M7 interview presentation release  
**Status:** in_progress  
**Started:** 2026-09-03

## Reading this historical record — 2026-09-05

This record concerns the original four-minute V1 presentation, which remains a retained
deliverable. Its result story is that Ridge lowered average absolute prediction error but failed
the fixed average directional-error rule, so the application kept persistence. The alternative
positive story in the rehearsal guide is hypothetical, not the released outcome. The completed
deck and 3:55 script document package preparation; they do not establish that the author has
personally rehearsed or can explain the later V2 investigation. That walkthrough and the new
20-minute package belong to Plan 0020. The pending release tag below remains a separate action.

Coverage wording clarification: the historical coverage percentages include both statements and
branches; they are not branch-only measurements. The original commands and numbers are retained.

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| The project can be explained in approximately four minutes without weakening its scientific or product claims | An eight-slide PowerPoint follows the problem, data, validity safeguard, result, product, limitation sequence and cites the frozen repository evidence in speaker notes | done |
| The negative challenger result has a direct, honest interview narrative | The deck and rehearsal guide explain that ridge improved MAE but failed the prespecified relative-bias criterion, so persistence remains displayed | done |
| The product remains demonstrable if the live app or presentation environment fails | Backup screenshots capture the offline program monitor and model-evaluation flow from the tracked release bundle | done |
| Likely methodological questions have concise, evidence-backed answers | A rehearsal guide covers temporal separation, target meaning, repeated programs, promotion, uncertainty, drift, and nonclinical scope | done |
| The presentation package is visually and mechanically usable | Every slide is rendered and inspected; overflow checks pass; the tracked offline app is exercised without a network dependency | done |

## Test-first exception

This milestone adds presentation, screenshot, and rehearsal documentation only. It does not change
application behavior, source meaning, features, splits, metrics, promotion rules, or frozen replay
evidence, so a failing production test is not meaningful. Verification is render-based, artifact-
based, and claim-based: inspect every slide, run presentation overflow checks, compare all numeric
claims with the frozen JSON/model card, and exercise the offline app used for screenshots.

## Scope boundary

- Use only the tracked release bundle, `docs/data_card.md`, `docs/model_card.md`, and repository
  documentation as factual sources.
- Present the 2025 replay as descriptive retrospective product-selection evidence, never as
  prospective or independent validation.
- Keep historical SRTR credible intervals distinct from empirical forecast bands.
- Do not add analytical features, rerun the write-once replay, or alter the persistence decision.
- Do not create a Git commit or release tag without explicit user authorization.

## Completion evidence

- `docs/presentation/kidney-acceptance-signal-monitor-interview.pptx` contains eight slides and
  eight speaker-note source blocks. Its SHA-256 is
  `a847035db135905e630966b3afd79bee69c996cfde42c45c4b62b666dc320eec`.
- `docs/presentation/interview-rehearsal-guide.md` provides a 3:55 talk track, the actual negative
  selection narrative, the gated positive counterfactual, an offline demo path, and likely-question
  notes.
- Four backup images under `docs/demo/` cover the program monitor, persistence projection, and
  frozen model evaluation. The three wide captures are 1440 × 900 and were collected while all
  non-local browser requests were blocked.
- Every slide was rendered from the final PowerPoint and visually inspected. The presentation
  overflow test passed with no overflow detected.
- The tracked Streamlit application was exercised through the program, projection, and model-
  evaluation views; its local health endpoint returned HTTP 200 with body `ok`.
- `uv sync --frozen`, Ruff format and lint, strict mypy, and the required 140-test suite pass. Core
  data/modeling/reporting branch coverage remains 83.81%.
- The package is complete and committed at `dc34b3a`. M7 remains `in_progress` only because the
  release tag needs explicit user authorization.
