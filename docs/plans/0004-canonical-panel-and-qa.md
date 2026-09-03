# Plan 0004 — Canonical panel and QA artifacts

**Milestone:** M2 canonical signal table and panel  
**Status:** done  
**Started:** 2026-09-03

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| The latest `Tiers` directory supplies display-only name, city, state, and ZIP by composite program key | Tests cover composite-key joining, leading-zero ZIP preservation, directory-only rows, and fallback labels | done |
| `program_signals.parquet` has the specified typed long-form schema and deterministic logical ordering | A local fixture builds twice to equal typed tables; schema and uniqueness assertions are exact | done |
| Annual source-to-target transitions use adjacent, non-overlapping calendar years | Tests reject overlapping/nonannual cohorts and preserve a missing target for program exits | done |
| `model_panel.parquet` contains only prespecified current/prior features and next-year published OAR targets | Tests cover lag/change/subgroup features, target-year alignment, and exclusion of display/future fields from the feature schema | done |
| Analytic, first-observed, and public-forecast eligibility are explicit materialized booleans | Tests prove analytic eligibility requires observed current and target OAR, while public eligibility requires current OAR plus two observations through the feature year | done |
| QA JSON explains source counts, additions, closures, unmatched transitions, subgroup missingness, and publication-rounding diagnostics | A fixture asserts each category and proves reconstruction discrepancies never replace published ratios | done |
| `kasm data build` writes the two Parquet files and QA report atomically from the verified cache | CLI and end-to-end offline XLS fixture tests cover output paths and a failed build leaving no partial artifact set | done |
| The nine-source cache produces the canonical build with all hard invariants satisfied | Real-cache command records row counts, transition counts, eligibility counts, and QA output | done |

## Test-first log

- Directory tests first failed because `kasm.data.build` did not exist, then passed after the
  display-only parser and join were implemented.
- Annual-transition and eligibility tests first failed on missing panel symbols, then passed with
  adjacent-year target construction and explicit flags.
- QA tests first failed on the missing report builder, then passed with movement, missingness, and
  rounding-range diagnostics.
- Exception: adding PyArrow is a mechanical dependency/lock change with no meaningful failing unit
  test; exact schemas, deterministic logical output, and atomic publication remain test-first.
- The first exact full-suite run exposed denied Windows user-temp and `.pytest_cache` locations;
  pytest now roots disposable temp and cache data under the already ignored `.test-tmp` workspace.
- The raw-cohort-date QA test then failed because parser output retained only normalized dates. Raw
  date/time strings now flow as internal metadata into 2,103 QA normalization records without
  expanding the canonical Parquet schema.

## Completion evidence

- `uv sync --frozen`, Ruff format, Ruff lint, and strict mypy passed.
- The required full suite passed 58 tests at 83.41% branch coverage across the core data modules.
- `kasm data verify-cache` revalidated all nine immutable sources; `kasm data build` produced
  10,515 canonical signal rows and 2,103 panel rows.
- Adjacent matched-program counts were 238, 232, 229, 230, 230, 232, 229, and 229. QA records every
  addition and closure rather than converting an exit into a target value.
- The current directory matched all 230 current signal programs and reported six directory-only
  programs. Missing subgroup OAR totals were low 2, medium 9, high 268, and hard-to-place 17.
- All 10,219 reported OAR rows with reconstruction inputs fell within their release/stratum
  rounding-implied ranges; the published OAR remains authoritative regardless of this diagnostic.
- Source-to-output trace: release `2605`, `ALUA:TX1`, cohort 2025 overall retained 13,273 offers,
  170 accepts, 152.85 expected accepts, published OAR 1.11 (0.95–1.28), current display fields, and
  the pinned source hash. Its panel row targets 2026, has no invented future truth, is analytically
  ineligible, and is explicitly public-forecast eligible from established history.
- Two consecutive full builds produced byte-identical outputs: `program_signals.parquet`
  `654936df1192c55d1659e0c464f8c6b277636698ccb58b29c4b99cfab5884522`,
  `model_panel.parquet` `00e1c6e14e0afdb9330022ac773eefaf1e3132edd24212e881967a2cc5a6c174`,
  and `qa_report.json` `bd007e5364c0df22b3a260cdc7f78fec3e004f1e60fd2781f476229bdd3f871c`.

## Scope note

This slice covers canonical Parquet generation, annual transitions, explicit eligibility, and QA
artifacts. Historical service functions and the Streamlit walking skeleton remain separate Day-2
work so this change stays narrow.
