# Plan 0006 — Pytest fresh-checkout portability

**Milestone:** M0 repository scaffold and quality gates  
**Status:** done  
**Started:** 2026-09-03

## Reading this historical record — 2026-09-05

This completed fix made test setup work on a fresh checkout, where ignored temporary folders
do not yet exist. Pytest now creates the top-level disposable folder itself. The failure counts
and passing rerun below record that specific problem and its correction.

Coverage wording clarification: the historical coverage percentages include both statements and
branches; they are not branch-only measurements. The original commands and numbers are retained.

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| Pytest creates its repository-local base temp directory on a fresh checkout without relying on an ignored parent directory | A repository-config regression test rejects nested base-temp paths, and the full CI test command passes after the base temp is made top-level | done |

## Test-first log

- The GitHub Actions run passed 33 tests and raised 34 setup errors because
  `--basetemp=.test-tmp/pytest` asked pytest to create a child directory while the ignored
  `.test-tmp` parent did not exist in the fresh checkout.
- The repository-config regression test then failed for the intended reason: the configured base
  temp's parent was `.test-tmp` rather than the repository root.

## Completion evidence

- `--basetemp` now targets the top-level ignored `.test-tmp` directory, which pytest can create
  itself on a fresh checkout.
- After removing the existing disposable `.test-tmp` directory, the CI-equivalent suite passed
  all 68 tests and recreated the directory without setup errors.
- Locked environment sync, Ruff format, Ruff lint, and strict mypy passed.
- The required branch-coverage suite passed all 68 tests at 84.53% coverage. The expected warning
  remains that `kasm.modeling` does not exist yet because M3 has not started.

## Scope note

This plan changes only disposable pytest path configuration and its regression coverage. It does
not change application behavior, data meaning, model behavior, or scientific claims.
