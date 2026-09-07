# Plan 0007 — Baseline temporal backtest

**Milestone:** M3 baselines and temporal backtest harness  
**Status:** done  
**Started:** 2026-09-03

## Reading this historical record — 2026-09-05

This completed V1 step tested three simple predictions before adding Ridge. Neutral predicts an
offer-acceptance ratio of 1; persistence carries forward the current ratio; historical mean uses
earlier log ratios for the same program. Each evaluation year stays together, and training uses
earlier years only. "MAE" is the average absolute size of prediction errors, here in log-OAR
units rather than percentage points. The primary score averages each year's MAE equally so a
larger year does not dominate. This implementation step excluded 2025 from its model comparison;
Plan 0010 records the later fixed replay. As SPEC.md explains, 2025 outcomes and model feasibility
had already been inspected during planning, so this was not an untouched validation set.

Coverage wording clarification: the historical coverage percentages include both statements and
branches; they are not branch-only measurements. The original commands and numbers are retained.

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| The model matrix accepts only the prespecified feature schema and rejects identity, location, cohort, and future fields | Unit tests exercise the exact allowlist and actionable leakage errors | done |
| Rolling-origin folds keep every evaluation target year intact and use only earlier target years for training | Unit tests assert the 2021–2024 fold boundaries, whole-year assignment, and rejection of misaligned target years | done |
| Neutral, persistence, and historical-mean baselines use only information available through the feature cohort | Unit tests assert each formula and prove future program history cannot affect the historical mean | done |
| Primary metrics weight target years equally and preserve paired per-program error comparisons | Unit tests distinguish year-balanced from row-pooled MAE and verify paired error differences | done |
| Expected-acceptance quartiles follow the deterministic within-year rank rule | Unit tests cover tie-breaking by program key and exact quartile assignment | done |
| `kasm model backtest` reads the trusted panel and writes deterministic predictions, metrics, and fold artifacts without evaluating 2025 | CLI and integration tests cover the offline command, exact schemas, and atomic output | done |
| The draft experiment configuration serializes the prespecified splits, metrics, seeds, band rule, and promotion thresholds before ridge work | Configuration tests assert the scientific constants required by `SPEC.md` | done |

## Test-first log

- The first focused run failed during collection because `kasm.modeling` did not exist.
- Feature, fold, formula, metric-aggregation, configuration, and CLI tests then passed after the
  baseline-only modeling package was implemented.
- The first formula-focused rerun exposed incomplete synthetic training-year fixtures. The tests
  now declare their intended training start explicitly while the project config continues to
  require the prespecified 2018 start.
- The end-to-end local-Parquet test verifies the already test-driven components as one offline
  artifact workflow; a forced serialization failure confirms a new output directory is never
  partially published.

## Completion evidence

- The exact 17-column model feature allowlist rejects all additional columns, including identity,
  display, cohort, and future fields.
- Real-data expanding folds contain 699/230, 929/230, 1,159/232, and 1,391/229
  training/evaluation rows for target years 2021, 2022, 2023, and 2024 respectively.
- The backtest wrote 2,763 paired predictions. On the primary 2021–2023 unweighted mean of yearly
  log-OAR MAEs, persistence scored 0.34153265, historical mean 0.40064464, and neutral 0.51989270.
- Every target year had 58 lowest-expected-acceptance-quartile rows, above the prespecified minimum
  of 30. Metrics remain descriptive baseline evidence.
- Artifacts explicitly record `frozen_replay_target_year: 2025` and
  `frozen_replay_evaluated: false`; no 2025 outcome was evaluated.
- Two consecutive real-data runs were byte-identical: predictions
  `cede39d8414cfaa916385c2c281f559bb4498873bf771d881231783d74d5e5ee`, metrics
  `9e4beea5d063b80f6c452f62fbd4c7aba528bce7e417d06ab45e447cab43e80a`, and folds
  `3e4d820b206a7423f170612d87eb9cb48ab980016f5378b3331682f47a03381c`.
- Locked sync, formatting, lint, and strict mypy passed. The required branch-coverage suite passed
  all 89 tests at 84.86% coverage across data, modeling, and reporting.
- Offline cache verification revalidated all nine sources, the canonical build reproduced 10,515
  signal rows and 2,103 panel rows, and the baseline command reproduced the recorded artifacts.

## Scope note

This slice establishes and runs the baseline gate before any challenger exists. It does not add
scikit-learn, fit ridge, inspect the 2025 replay outcome, freeze the experiment, or attempt forecast
activation.
