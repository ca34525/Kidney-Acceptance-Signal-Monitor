# Plan 0001 — Repository scaffold and cache verification

**Milestones:** M0 repository scaffold; initial M1 source contract  
**Status:** done (source-cache gate handed to Plan 0002)
**Started:** 2026-09-03

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| Python 3.12 project has locked, offline-testable quality tooling | `uv sync --frozen`, Ruff, mypy, and pytest pass | done |
| Source manifest lives at its specified path and cannot silently reuse a cohort year | `test_manifest_rejects_duplicate_cohort_year` fails first, then passes | done |
| Offline cache verification checks presence, pinned size, SHA-256, file type, and configured ZIP member | Focused unit tests and `kasm data verify-cache` | done |
| Raw and generated data cannot be committed accidentally | `.gitignore` excludes `data/` and non-release artifacts | done |
| Fixture-only checks run in CI with pinned actions | `.github/workflows/ci.yml` matches local quality commands | configured; remote run pending |
| Nine-source start condition is evaluated | Real manifest command reports either nine verified inputs or actionable missing-file failures | done: initially absent; all nine verified by Plan 0002 |

## Test-first log

- Initial focused command: `uv run pytest -q tests/unit/test_config.py tests/unit/test_cache.py`;
  four tests failed because duplicate cohorts were accepted and cache verification was a no-op.
- Expanded failing contract: `uv run pytest -q tests/unit`; ten intended failures and one
  passing real-manifest load test.
- Passing focused command: `uv run pytest -q tests/unit`; 11 passed.
- Full local gates: Ruff format check passed, Ruff lint passed, strict mypy passed on five
  source files, and pytest passed all 11 tests.
- Lock evidence: `uv sync --frozen` checked 26 packages successfully.
- Nine-source cache result: `uv run kasm data verify-cache` checked nine configured releases,
  reported all nine expected files missing, and returned exit code 1. The Day 1 start condition
  remains unsatisfied.

## Scope note

This slice does not download source files, parse workbooks, or begin modeling. A missing local cache
is reported as an explicit start-condition failure rather than repaired or fetched implicitly.

The 2026-09-03 addition of a commit-message handoff rule to `AGENTS.md` is documentation-only and
cannot be meaningfully exercised by an automated repository test; review of the rendered rule is
the acceptance evidence.

Plan 0001 is complete as an offline verification slice. The missing-cache start condition was not
waived; Plan 0002 added explicit acquisition and subsequently satisfied it.
