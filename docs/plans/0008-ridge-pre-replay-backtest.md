# Plan 0008 — Ridge pre-replay backtest

**Milestone:** M4 ridge challenger and frozen retrospective replay  
**Status:** done  
**Started:** 2026-09-03

## Reading this historical record — 2026-09-05

This completed V1 step tested whether a regression using earlier public measurements improved
on carrying the current ratio forward. Ridge limits the size of fitted weights; its `alpha`
setting controls that limit, with larger values applying stronger shrinkage. The fixed tie rule
preferred stronger shrinkage when errors were within 1%. Filling missing values and scaling inputs
used each training period alone, so later evaluation values could not influence preparation.
The error values below are in log-OAR units. Passing this candidate gate allowed consideration
of the next step; it did not authorize displaying Ridge or establish future performance.

Coverage wording clarification: the historical coverage percentages include both statements and
branches; they are not branch-only measurements. The original commands and numbers are retained.

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| Ridge preprocessing is fit inside each temporal training fold and preserves the prespecified missingness inputs | A unit test inspects training-fold imputation statistics and proves held-out values cannot affect them | done |
| The ridge pipeline and rolling predictions are deterministic | Repeated fits and artifact runs produce identical predictions and selected alpha | done |
| Alpha is selected only from the fixed grid using year-balanced 2021–2023 log-OAR MAE and the larger-alpha 1% tie rule | Unit tests exercise the metric aggregation, candidate boundary, and tie break | done |
| The selected alpha is evaluated in intact rolling folds through held-out target year 2024 without accessing target year 2025 | Unit and integration tests assert training/evaluation years, push the 2024 cutoff into the Parquet read, and verify artifact schemas | done |
| The prespecified pre-replay candidate gate is derived from 2021–2024 overall and lowest-volume-quartile evidence | Unit tests exercise each gate condition and the emitted decision evidence | done |
| `kasm model backtest` writes deterministic ridge selection, prediction, and metric artifacts alongside the baseline outputs | An offline integration test covers the command-level artifact workflow and staged ridge publication | done |

## Test-first log

- The first focused run failed during collection because `kasm.modeling.challenger` did not exist.
- After the first implementation, the focused test exposed an overflowing synthetic fixture; the
  fixture now isolates the held-out imputation value without constructing a meaningless OAR.
- The training-only imputation statistic, repeated selection/prediction equality, alpha tie rule,
  gate failures, filtered Parquet read, exact artifact schema, and offline CLI path are covered.

## Completion evidence

- The verified cache remained green for all nine pinned sources, and a fresh canonical build
  reproduced 10,515 signal rows and 2,103 panel rows.
- Alpha 10 was selected: its 2021–2023 unweighted mean yearly log-OAR MAE was 0.32616573. The
  nominal minimum was alpha 0.01 at 0.32474404; alpha 10 remained within 1%, while alpha 100 did
  not, so the prespecified larger-alpha tie rule selected 10.
- On target years 2021–2024, ridge MAEs were 0.30173671, 0.40520410, 0.27155636, and 0.25421673,
  versus persistence MAEs of 0.30631777, 0.43478694, 0.28349324, and 0.27947253.
- Ridge improved in all four years, achieved 5.4718% year-balanced skill, was never worse in a
  single year, improved lowest-quartile MAE by 8.9356%, and had 58 rows in the smallest yearly
  lowest-volume quartile. The pre-replay candidate gate passed.
- Two consecutive real-data runs were byte-identical: ridge predictions
  `6e451509cb4c681c2bd91c1a5617eb2facf178f8df8b6656f77d6db5eda5c7e8`, metrics
  `2cc3efd9b7413fdab7a27b6125c9c471f2be6db35f2e2e4e62e77422bdbd3c18`, and selection
  `b10d42d5ca5e38b492def2cf45a7b3e37bac6be4887ddce8357d317ae487c7cc`.
- Locked sync, formatting, lint, and strict mypy passed. The required branch-coverage suite passed
  all 97 tests at 85.27% coverage across data, modeling, and reporting.

## Scope boundary

This slice does not evaluate the 2025 target, decide whether forecast activation is attempted,
create `configs/frozen_experiment.yaml`, calibrate or gate an empirical band, bootstrap replay
performance, or run the frozen replay. The pre-replay Parquet reads are filtered through target
year 2024.
