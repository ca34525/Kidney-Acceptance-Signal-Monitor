# Plan 0016 — Patient-journey methodology ledger and parser

**Milestone:** M10 patient-journey v2 methodology ledger and source parser
**Status:** done
**Started:** 2026-09-04

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| V2 metric timing and schema facts are reviewable rather than inferred from release proximity | A typed, source-cited ledger records every pinned release's publication precision, outcome/access/wait-time sheets, source fields, measurement and follow-up dates, table shape, definition notes, and context | done |
| Historical sheet-name and cadence changes cannot pass silently | Ledger validation requires all nine manifest releases and records B6→B7, B9→B10, missing `TX_RR` in `1808`, and the overlapping calendar-year outcome cohort in `2605` | done |
| The primary observed outcome retains publication meaning | Fixture-first tests prove `SAL_N_C` and `SAL_TOTFTX_C18` parse to count, percentage, proportion, reconstructed successes, and a boundary-safe empirical logit without replacing the published percentage | done |
| Combined access-table identities cannot be guessed or joined by name | A registry parsed from same-release `Tiers` rows reconciles an explicit `CCCCtype` pattern to `(CTR_CD, CTR_TY)` and rejects malformed, unknown, and duplicate identities | done |
| Suppressed wait-time values never become zero or censored numeric values | Tests preserve the raw `TTT_25_C` source value while mapping `>72`, `Not Observed`, and `-` to null | done |
| Cached sources satisfy the new contracts without writing artifacts | A read-only nine-release inventory verifies checksums, table shapes, program counts, publication values, and combined-key reconciliation | done |
| V1 frozen evidence remains outside the change | Git diff contains no v1 experiment, frozen replay, processed/modeling, release-bundle, or default-app payload changes | done |

## Test-first record

Documentation and the implementation plan preceded tests because the repository agreement requires
the scientific work and expected evidence to be named first. The initial focused run failed during
collection with two `ModuleNotFoundError` errors before the ledger and parser existed. After the
first implementation, the immutable-cache audit exposed the real `Center Name` description label in
the access table and a missing `ENTIRE_NAME` in the 2006 directory. Each case was reproduced by a
focused failing test before the parser was corrected. A final provenance test also failed before the
loader began requiring every ledger source URL and SHA-256 to match the source manifest.

## Phase boundary

This plan parses and validates source facts only. It does not build the v2 panel, declare temporal
folds, fit or compare a model, update the Streamlit application, write v2 artifacts, rerun the v1
frozen replay, or change the default product. The ledger exposes the `2505`/`2605` outcome-cohort
overlap so the next plan can make an explicit era/fold decision before any modeling writer exists.

## Completion evidence

- `configs/patient_journey_v2/methodology.yaml` covers all nine pinned releases and binds each
  release's public-availability precision, workbook URL/hash, table shapes, machine fields, cohort
  timing, follow-up/censor date, definition notes, and policy context to the source manifest.
- `src/kasm/patient_journey/ledger.py` rejects omitted/reordered releases, duplicate or missing
  metric families, publication/source provenance drift, invalid timing, unsafe URLs, and malformed
  table contracts. It exposes the sole successive outcome overlap as `2505→2605`.
- `src/kasm/patient_journey/parse.py` parses observed target values, access rates, and wait time;
  reconciles combined access identifiers against same-release composite identities; normalizes the
  source's historical date offsets and 2605 Excel serials; and preserves suppressed wait-time text.
- Focused patient-journey tests: 26 passed as part of the final suite.
- Read-only immutable-cache audit passed for all nine releases: identity rows 236–246, outcome rows
  229–239, transplant-rate rows 235–242, and wait-time rows 231–244.
- `uv --cache-dir .uv-cache sync --frozen`: passed (68 packages checked).
- `uv --cache-dir .uv-cache run ruff format --check .`: passed (49 files formatted).
- `uv --cache-dir .uv-cache run ruff check .`: passed.
- `uv --cache-dir .uv-cache run mypy src/kasm`: passed (23 source files).
- Required branch-coverage suite: 169 passed; 83.93% total coverage across the required core
  modules.
- `uv --cache-dir .uv-cache run kasm data verify-cache`: passed for all nine pinned sources with no
  issues.
- `git diff -- configs/experiment.yaml configs/frozen_experiment.yaml artifacts/release
  data/processed data/modeling app/streamlit_app.py` produced no changes. The frozen replay was not
  run and no artifacts were written.
