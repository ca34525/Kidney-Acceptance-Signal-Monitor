# Plan 0003 — Schema-aware workbook parser

**Milestone:** M1 source acquisition and data contracts  
**Status:** done  
**Started:** 2026-09-03

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| The complete parser contract is loaded from the source manifest | Tests reject missing release metadata, fewer than 200 rows, duplicate machine fields, and invalid publication precision | done |
| Verified ZIP and XLS sources open without publishing extracted workbooks | Tests cover both transports and prove the configured ZIP member is selected | done |
| Old and new offer-acceptance sheet names are selected by configured name and machine fields | A generated BIFF8 fixture covers the two-row header; pure fixtures cover both sheet names, reordered columns, and schema drift | done |
| Program identity is the composite `(CTR_CD, CTR_TY)` key | A duplicate center code with different center types yields distinct program keys; a repeated composite key fails | done |
| The five P0 offer groups reshape to canonical long-form rows | Tests cover exact fields, stable ordering, source provenance, and exclusion of optional recent fields | done |
| Missing and zero subgroup values retain their published meaning | Tests prove missing ratios remain null, zero offers never become ratio zero, and a published zero credible lower bound is preserved | done |
| Source row, interval, count, cohort-date, and uniqueness contracts fail closed | Focused tests exercise each hard parser invariant with actionable release/row context | done |
| The real nine-source cache satisfies the parser contract | `kasm data inspect-sources` reports pinned row and column counts for every release | done |

## Test-first log

- Initial focused collection failed because `kasm.data.parse` did not exist.
- The first real-cache parser pass failed on the documented two-row header because the human-label
  row was counted as a program; the parser now recognizes that exact row and the fixture reproduces
  the source layout.
- The next real-cache pass exposed a published 2006 hard-to-place credible lower bound of zero. A
  focused regression test failed under the overly strict positive-bound rule before the validator
  was corrected to the specification's nonnegative ordered-interval rule.
- The first full core-coverage run passed all behavior tests but failed the 80% gate at 78.17%.
  A generated legacy XLS adapter test was added; the final full suite passed 45 tests at 82.33%
  branch coverage.
- `uv sync --frozen`, Ruff format check, Ruff lint, and strict mypy all passed.
- `kasm data verify-cache` rechecked nine sources with no issues. `kasm data inspect-sources`
  parsed 2,103 program-year rows into 10,515 ordered P0 signal rows: 2017–2023 matched their pinned
  125-column schemas and 2024–2025 matched their pinned 143-column schemas.

## Scope note

This slice completes source-workbook parsing and inventory but does not write canonical Parquet,
join directory display fields, construct annual transitions, or derive forecast eligibility. Those
behaviors belong to M2 and require their own failing tests. Published OAR values remain authoritative;
formula reconstruction is not part of this parser slice.
