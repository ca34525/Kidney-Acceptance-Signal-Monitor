# Plan 0015 — Patient-journey v2 foundation

**Milestone:** M9 patient-journey v2 foundation
**Status:** done
**Started:** 2026-09-04

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| V2 has an authoritative scientific boundary without changing v1 meaning | `docs/specs/patient-journey-v2.md` defines the observed target, claim limits, timing rules, models, and product boundary; `SPEC.md` links the version boundary | done |
| The target, risk-adjustment boundary, safety timing, and v1 isolation are explicit decisions | Decision 0004 records the rationale and consequences | done |
| V2 configuration and generated outputs have distinct roots | `configs/patient_journey_v2/experiment.yaml` declares only v2-owned roots | done |
| A malformed v2 configuration cannot direct a writer into v1 frozen paths | A focused regression test failed before implementation, then the typed loader rejected equality, descendants, ancestors, absolute paths, parent traversal, and overlapping v2 roots | done |
| V1 frozen evidence remains byte-for-byte outside the change | Git diff contains no v1 config, replay, or release-bundle payload changes | done |

## Test-first record

The first production behavior was the v2 path boundary. The initial focused run failed during test
collection with `ModuleNotFoundError: No module named 'kasm.patient_journey'`, before the loader
existed. After the smallest implementation, the release-root regression passed. Boundary coverage
was then extended to ancestors, descendants, absolute paths, parent traversal, overlapping v2
roots, and the prohibited risk-adjusted target claim.

Documentation changes precede the test because the repository agreement requires specification,
plan, and decision updates before changing target or scope.

## Phase boundary

This plan covers handoff Phase 0 only. It does not parse new workbook tables, construct a v2 panel,
fit a model, update the application, rerun v1, or create a release. Phase 1 begins only after a new
plan records metric-ledger and parser contracts with fixture-based failing tests.

## Completion evidence

- `configs/patient_journey_v2/experiment.yaml` declares separate processed, modeling, and future
  release roots. The code-owned protected-root contract covers `data/processed`, `data/modeling`,
  and `artifacts/release` and cannot be weakened by editing the YAML list.
- `tests/unit/test_patient_journey_config.py`: 8 passed.
- `uv --cache-dir .uv-cache sync --frozen`: passed (68 packages checked).
- `uv --cache-dir .uv-cache run ruff format --check .`: passed (45 files formatted).
- `uv --cache-dir .uv-cache run ruff check .`: passed.
- `uv --cache-dir .uv-cache run mypy src/kasm`: passed (21 source files).
- Required branch-coverage suite: 151 passed; 83.93% total branch coverage across the required core
  modules.
- `uv --cache-dir .uv-cache run kasm data verify-cache`: passed for all nine pinned sources with no
  issues.
- `git diff -- configs/experiment.yaml configs/frozen_experiment.yaml artifacts/release
  data/processed data/modeling` produced no changes. The frozen replay was not run.
