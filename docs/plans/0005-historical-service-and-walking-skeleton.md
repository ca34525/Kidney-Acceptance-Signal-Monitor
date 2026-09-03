# Plan 0005 — Historical service and offline walking skeleton

**Milestone:** Day 2 historical service; M5 walking-skeleton prerequisite  
**Status:** done  
**Started:** 2026-09-03

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| The view boundary loads only trusted precomputed Parquet artifacts and rejects missing or schema-incompatible inputs | Unit tests cover missing files and exact canonical-schema validation | done |
| Program choices and labels use display fields while retaining the composite program key as identity | Unit tests cover deterministic labels and same-code/different-type programs | done |
| Pure service functions provide chronological overall history, mechanical latest interval status, volume context, and latest subgroup display | Unit tests cover ordering, all three interval labels, source volume, and subgroup nulls rendered as `Not reported` | done |
| Forecast eligibility is read from the latest trusted panel row and is never inferred in the view | Unit and app tests prove an established-looking fixture remains unavailable when its materialized flag is false | done |
| A one-program Streamlit walking skeleton opens the precomputed fixture without network access | A Streamlit AppTest exercises selection, the historical chart, source/publication/version context, and the unavailable projection state | done |

## Test-first log

- Historical-service tests first failed at collection because `kasm.reporting` did not exist, then
  passed after the exact-schema loader and pure view functions were added.
- The first post-implementation run exposed a test-fixture helper that tried to recreate pytest's
  existing temporary directory; correcting the helper produced eight passing service tests.
- The Streamlit integration test first failed because `app/streamlit_app.py` did not exist, then
  passed after the offline walking skeleton was implemented.
- Adding Streamlit and regenerating `uv.lock` is a mechanical dependency change with no meaningful
  failing unit test; the repository-local telemetry setting is likewise mechanical. Application
  behavior remained test-first.

## Completion evidence

- `uv sync --frozen`, Ruff format, Ruff lint, and strict mypy passed.
- The required full suite passed 67 tests at 84.53% branch coverage across data and reporting;
  modeling remains absent and coverage reported the expected informational warning.
- The focused historical-service and AppTest set passed nine tests. The AppTest disables socket
  connections and verifies program selection, historical-view labeling, artifact version,
  persistent nonclinical banner, and explicit unavailable projection state.
- A real local-artifact load exposed 252 historical composite-key programs; the selected trace
  spanned all nine cohort years from 2017 through 2025.
- The real Streamlit process started against `data/processed`, and its health endpoint returned
  HTTP 200 with body `ok`.

## Scope note

This slice closes the Day-2 handoff from Plan 0004. It deliberately stops at a historical
one-program walking skeleton: model evaluation, forecasts, release-bundle publication, and final
visual/accessibility polish remain governed by later milestones.
