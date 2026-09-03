# Plan 0009 — Pre-replay activation freeze

**Milestone:** M4 ridge challenger and frozen retrospective replay  
**Status:** in_progress  
**Started:** 2026-09-03

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| The empirical log-scale residual radius uses the prespecified finite-sample order statistic and only held-out target-year 2024 ridge residuals | A unit test rejects any calibration input containing another target year and checks the exact selected order statistic | done |
| The descriptive paired bootstrap resamples 2025 program keys with replacement using the frozen seed, count, percentiles, and percentile method | Unit tests prove deterministic output, program-key pairing, and rejection of duplicate keys | done |
| Ridge point promotion applies every replay criterion, including low-volume eligibility, independently of the empirical-band display gate | Unit tests make each criterion fail in isolation and prove a failed point gate retains persistence | done |
| The band display gate uses a two-sided 95% Clopper–Pearson interval and compares mean width with a persistence band calibrated by the same rule | Unit tests check exact-binomial endpoints, nominal-coverage inclusion, and width rejection | done |
| `configs/frozen_experiment.yaml` serializes the activation decision, selected alpha, and every prespecified replay rule without exposing target year 2025 | A strict frozen-config loader rejects null decisions or altered methods and the checked-in config contains only pre-replay evidence | in_progress |

## Test-first log

- The first focused run failed during collection because `kasm.modeling.activation` did not exist.
- After the initial implementation, a second focused test failed because the frozen config did not
  yet expose the real-data 2024 calibration sample size, order-statistic rank, and model-specific
  radii.
- The calibration-year guard, finite-sample rank, deterministic program-key bootstrap, every point
  criterion, independent band gate, and strict frozen-config contract are now covered.

## Completion evidence

- The pre-replay command again selected alpha 10, passed the candidate gate, emitted 921 ridge
  predictions, and did not read target year 2025.
- The real-data 2024 calibration contains 229 programs. The prespecified 80% finite-sample rule
  selected rank 184, giving an absolute log-residual radius of `0.3842946113686516` for ridge and
  `0.4054651081081644` for persistence.
- The ridge prediction, metrics, and selection hashes reproduced Plan 0008 exactly and are recorded
  in the frozen config.
- Forecast activation is recorded as attempted, with alpha, calibration evidence, bootstrap
  contract, point gate, and band gate serialized before replay.
- Locked sync, formatting, lint, strict mypy, all 110 tests, 85.11% branch coverage across core
  modules, and verification of all nine cached sources passed.
- The frozen config remains uncommitted because repository commits require explicit user
  authorization. The 2025 replay has not been run.

## Scope boundary

This slice must not read target-year 2025 rows, execute the frozen replay, use replay evidence to
change a threshold, or publish a replay result. The canonical replay remains blocked until the
frozen config is committed in a separate, explicitly authorized Git action.
