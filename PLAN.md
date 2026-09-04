# Kidney Acceptance Signal Monitor — One-Week Build Plan

**Plan version:** 1.1  
**Status:** Ready to execute  
**Time box:** Seven full-time days  

The hard budget is 56 focused hours: eight hours per day. Day 7 is release/rehearsal buffer, not a feature day. Conditional forecast activation is the first automatic cut and cannot consume that buffer.

## 1. Operating model

This project uses a plan → test → build loop.

For every behavior:

1. Tie the work to a plan item and an acceptance criterion in `SPEC.md`.
2. Write the smallest test that fails for the intended reason.
3. Implement the smallest change that makes it pass.
4. Refactor while the focused tests remain green.
5. Run the relevant suite, then update this plan with evidence.

If the scope or statistical method changes, update `SPEC.md` and this plan before changing production code. Record material choices in `docs/decisions/`.

The historical monitor is the guaranteed product. The ridge challenger is allowed to lose. A tested conclusion that persistence is safer is a valid, presentation-worthy result.

## 2. Start condition for the seven-day clock

Before Day 1 begins, all nine source files must be present in an immutable local cache and must match `configs/data_sources.yaml`. This acquisition was verified on 2026-09-03; repeat the checksum check on the development machine. If the cache is incomplete, do not start the clock. Live URL availability is not a release dependency after this point.

## 3. Definition of the MVP

The MVP contains:

- a pinned and checksum-verified SRTR downloader;
- a schema-aware parser for nine annual kidney PSR workbooks;
- a validated annual program-signal table;
- overall and donor-stratum historical views;
- neutral, persistence, and historical-mean baselines;
- one ridge challenger evaluated with rolling time splits;
- an offline model-evaluation view and persistence reference; and, only if its full release path is green, an activated ridge point nowcast and empirical band;
- a single offline-capable Streamlit app;
- unit, contract, integration, UI, and Docker smoke tests;
- CI, a lockfile, data/model cards, and a four-minute demo path.

The MVP does not require a public cloud deployment or a separate API.

## 4. Milestone board

Use these exact statuses: `not_started`, `in_progress`, `blocked`, `done`, `cut`.

| ID | Milestone | Status | Completion evidence |
|---|---|---|---|
| M0 | Repository scaffold and quality gates | done | Locked sync, dependency checks, format, lint, strict mypy, 140-test/83.81% branch-coverage suite, nine-source cache verification, and 2/2 remote CI checks pass at `2c815688` |
| M1 | Source acquisition and data contracts | done | Nine sources verified; 2,103 program-years parsed to 10,515 validated P0 signal rows |
| M2 | Canonical signal table and panel | done | 10,515 signal rows, 2,103 panel rows, deterministic Parquet, and reconciled QA JSON |
| M3 | Baselines and temporal backtest harness | done | Plan 0007: 2,763 paired predictions; persistence selection MAE 0.3415; 2025 untouched |
| M4 | Ridge challenger and frozen retrospective replay | done | Plan 0010: 229-row write-once replay; ridge not promoted on frozen bias rule; persistence retained; model card complete |
| M5 | Offline Streamlit product | done | Plan 0011: complete offline program flow, persistence projection, model evaluation, explicit non-promotion/band suppression, provenance, AppTest, and process health smoke |
| M6 | Reproducibility, documentation, and container | done | Plan 0012: 1.23 MB tracked bundle, clean-checkout/full reproduction, docs, local Docker non-root/health smoke, and 2/2 remote CI checks pass at `2c815688` |
| M7 | Interview presentation release | in_progress | Plan 0013: verified eight-slide deck, offline backup demo, and 3:55 rehearsal package committed at `dc34b3a`; release tag awaits explicit user authorization |
| M8 | AI-generated code and context hardening | done | Plan 0014: research-backed audit, HTTPS boundary regression, Ruff security/complexity/pytest gates, focused context guidance, 143 tests at 83.93% branch coverage, and reproducible 12-file release bundle |

## 5. Day-by-day execution

### Day 1 — Scaffold and source contracts

#### Plan

- Create Python 3.12 project with `uv`, `src` layout, Ruff, mypy, pytest, coverage, and pre-commit hooks.
- Add the source manifest from `data_sources.yaml` under `configs/`.
- Define downloader, archive, parser, and canonical-schema interfaces.
- Add a tiny workbook fixture with:
  - two-row headers;
  - both sheet-name variants;
  - a missing program name;
  - a zero-offer subgroup;
  - a missing subgroup ratio;
  - a duplicate center code with a different center type;
  - a program that disappears in the next year; and
  - an intentionally invalid interval;
  - both month- and day-precision publication values.
- Implement verified, atomic source download and safe archive extraction.
- Implement initial source and manifest contract checks.
- Start the release-methodology ledger, including the 2020 COVID context, 2021-03-15 circle allocation, 2023-07-27 OAR monitoring change, table names, and field availability.
- Add README, data-card, model-card, and presentation-outline skeletons so evidence is filled in as work lands.

#### First failing tests

- `test_manifest_rejects_duplicate_cohort_year`
- `test_download_rejects_wrong_sha256`
- `test_archive_rejects_unexpected_member`
- `test_parser_finds_old_and_new_sheet_names`
- `test_program_key_uses_code_and_type`
- `test_source_contract_rejects_bad_interval`
- `test_month_precision_never_invents_publication_day`

#### Gate

Proceed only if all nine cached inputs match their pinned hashes, expose the required machine columns, and contain at least 200 eligible center rows. If source compatibility fails and cannot be explained in two hours, disable challenger promotion and preserve the historical monitor plus baselines.

#### End-of-day evidence

- Green focused tests
- Source inventory with sizes, hashes, row counts, and columns
- CI running offline against fixtures

### Day 2 — Canonical data and historical service

#### Plan

- Parse the published machine fields without selecting by position.
- Normalize dates and reshape center measures to the P0 long form; leave OPO/region/nation comparators for the separate P1 table.
- Join the current directory table for display fields only.
- Enforce count, interval, missingness, and uniqueness invariants.
- Build `program_signals.parquet` deterministically.
- Build annual source→target transitions using the composite program key.
- Create a QA report for additions, closures, unmatched transitions, missing subgroup values, and rounding-range formula diagnostics.
- Materialize and test analytic eligibility, first-observed status, and public-forecast eligibility.
- Implement pure service functions for program history, latest status, volume context, and subgroup display.
- Build a walking skeleton from cached fixture to Parquet to one-program history chart and an offline Streamlit process smoke test.

#### First failing tests

- `test_missing_subgroup_ratio_stays_null`
- `test_zero_subgroup_offers_do_not_become_ratio_zero`
- `test_published_ratio_is_authoritative`
- `test_annual_transitions_do_not_overlap`
- `test_program_exit_has_missing_target_not_negative_label`
- `test_forecast_eligibility_is_explicit`
- `test_output_is_logically_deterministic`
- `test_walking_skeleton_loads_one_program_offline`

#### Gate

A selected program must be traceable from its source row to its canonical row and chart-ready service response. All hard invariants must pass. Every discrepancy must be explained in the QA report rather than silently repaired.

#### End-of-day evidence

- Canonical Parquet schema and row counts
- One source-to-output trace
- QA report committed
- Historical service unit tests green

### Day 3 — Baselines and frozen experiment design

#### Plan

- Implement the exact feature contract from `SPEC.md`.
- Add automatic leakage rejection for identity, location, and target-period fields.
- Build rolling-origin folds by target year.
- Implement neutral, persistence, and historical-mean baselines.
- Implement primary metrics and paired comparison structures.
- Create `configs/experiment.yaml` with feature names, target, folds, alpha grid, metrics, seeds, per-year aggregation, finite-sample residual order statistic, 10,000-resample percentile bootstrap, Clopper–Pearson coverage interval, deterministic yearly volume-quartile assignment, and every numeric point/band promotion threshold from `SPEC.md`.
- Run and save baseline backtests before writing the ridge model.
- Add a minimal Dockerfile, then run clean-install, non-root container, and process smoke tests.
- Fill the presentation outline with the problem, data, design, and validity safeguards; results remain blank.

#### First failing tests

- `test_random_row_split_is_not_available`
- `test_all_rows_for_target_year_share_fold`
- `test_future_fields_are_rejected`
- `test_preprocessing_receives_training_rows_only`
- `test_persistence_equals_current_log_oar`
- `test_historical_mean_uses_prior_years_only`
- `test_primary_selection_metric_weights_target_years_equally`

#### Gate

Do not start the challenger until one command reproduces the baseline metrics and the tests prove the cohort and feature-availability rules.

#### End-of-day evidence

- Frozen experiment config draft
- Baseline metrics by year and expected-acceptance quartile
- Leakage tests green

### Day 4 — Ridge challenger and frozen retrospective replay

#### Plan

##### Guaranteed pre-replay path

- Implement the sklearn preprocessing and ridge pipeline.
- Select alpha only from backtest years 2021–2023 using the fixed tie rule.
- Generate rolling predictions through held-out target year 2024.

##### Pre-replay activation decision

At the mid-Day-4 checkpoint, attempt activation only if the guaranteed pre-replay path is green and at least four focused hours remain. Before viewing the 2025 replay:

- implement and test the exact bootstrap, point-promotion, residual-band, and band-gate rules;
- construct the band from held-out 2024 residuals only;
- set `forecast_activation_attempted: true`; and
- commit `configs/frozen_experiment.yaml`.

Otherwise set `forecast_activation_attempted: false` and commit the frozen base experiment config. Do not add forecast activation after seeing 2025. The historical monitor, all three baselines, ridge evaluation, persistence reference, and model card still ship.

##### Shared frozen replay

Only after one of the two configuration branches above is committed:

- run the 2025 frozen implementation replay once with explicit confirmation, using the model trained only through target year 2023;
- evaluate the 2020/2021 exclusion sensitivities, the 2023 mixed-policy context, target years, expected-acceptance quartiles, and missingness/first-observed diagnostics;
- write predictions, metrics, and activation status atomically to a canonical directory keyed by the frozen-config and source-manifest hashes, refuse overwrite, and write a completion ledger; and
- draft the factual results section of the model card.

#### First failing tests

- `test_ridge_pipeline_is_deterministic`
- `test_alpha_tie_selects_more_regularized_model`
- `test_replay_model_excludes_2024_outcomes_from_fit`
- `test_frozen_replay_requires_config_and_confirmation`
- `test_frozen_replay_cannot_tune_or_overwrite`

Conditional activation tests:

- `test_band_uses_only_2024_validation_residuals`
- `test_band_gate_uses_exact_binomial_interval_and_width`
- `test_low_volume_gate_applies_in_replay`
- `test_promotion_gate_selects_persistence_when_challenger_fails`

#### Gate

By the checkpoint, either the entire activation path is green and frozen or activation is disabled. The latter is not a blocker. If attempted, the selected point default and band visibility are determined separately by code from prespecified numeric rules. Never adjust predictors, alpha, thresholds, residual-band width, or claims after seeing 2025. Label the replay descriptive and ridge prospectively unvalidated.

#### End-of-day evidence

- Frozen experiment config
- Hash-addressed write-once replay bundle and completion marker
- Challenger/persistence evaluation and explicit activation status
- Model-card results table

### Day 5 — Product and core feature freeze

#### Plan

- Build the Streamlit app over precomputed artifacts only.
- Implement program search and the required flow from `SPEC.md`.
- Render historical SRTR intervals and, when activated, empirical forecast bands distinctly; suppress a band when its gate fails or was not attempted.
- Add subgroup, volume, provenance, model-status, and limitation panels.
- Read explicit forecast eligibility from the artifact and add missing/insufficient-history states.
- Add the persistent nonclinical/nonregulatory banner.
- Add UI tests with Streamlit AppTest or the smallest reliable equivalent.
- Rehearse a four-minute user journey offline.

#### First failing tests

- `test_app_loads_without_network`
- `test_program_search_uses_display_fields_only`
- `test_missing_subgroup_displays_not_reported`
- `test_view_never_infers_forecast_eligibility`
- `test_no_leaderboard_or_mpsc_language`
- `test_data_and_model_versions_are_visible`

Conditional activation tests:

- `test_interval_types_have_distinct_labels`
- `test_failed_band_gate_suppresses_interval_claim`

#### Gate

Core feature development ends when the user journey works from a clean environment without network access. After this gate, only correctness, accessibility, documentation, and presentation blockers may enter P0.

#### End-of-day evidence

- App smoke test
- Screenshots of the critical path
- Timed offline demo under four minutes

### Day 6 — Reproducibility and hardening

#### Plan

- Finish the Day-1 README, data-card, model-card, and decision-log skeletons; keep the short methodology summary inside the README rather than creating another document.
- Harden the existing Dockerfile only as needed; non-root execution and a health check are required, multi-stage optimization is optional.
- Build and track exactly one attributed, reproducible `<5 MB` release bundle; ignore all other generated artifacts and raw data.
- Verify that a clean checkout opens that bundle offline. Verify full release reproduction from the immutable cache with `data verify-cache`, `data build`, `model backtest`, `model evaluate-frozen-replay --confirm` into a fresh canonical path, and `artifacts build`; test `data sync` separately as a nonblocking maintenance path.
- Verify locked install, lint, mypy on owned `src/kasm` code, ≥80% branch coverage on core data/model/reporting modules, one critical Streamlit AppTest, fixture pipeline, app process smoke, and Docker smoke in CI.
- Add dependency and accidental-large-file checks.
- Confirm source attribution and code/data licensing boundaries.
- Complete the bounded accessibility checklist: keyboard critical flow, visible focus, non-color status labels, and WCAG AA text/control contrast.

#### First failing tests

- `test_release_manifest_contains_required_provenance`
- `test_app_bundle_matches_canonical_artifacts`
- `test_no_disallowed_large_files_tracked`
- `test_container_process_is_nonroot`

#### Gate

A clean checkout must reproduce the fixture pipeline and open the tracked demo bundle without network access. The documented full command sequence—cache verification, data build, backtest, fresh frozen replay, and artifact build—must reproduce the committed metrics without live-source access.

#### End-of-day evidence

- Green CI and Docker smoke
- Complete data/model cards
- Reproduction log

### Day 7 — Release and presentation buffer

#### Plan

- Tag a release and freeze the demo bundle.
- Complete the approximately eight-slide presentation outline using only frozen results.
- Prepare both result narratives:
  - ridge promoted because it adds stable lift; or
  - persistence retained because complexity did not generalize.
- Capture backup screenshots; record a short local demo only if time remains.
- Test the demo on the presentation machine with networking disabled.
- Rehearse the full story and likely statistical questions.
- Fix release-blocking defects only; add no analytical features.

#### Gate

The project is interview-ready when the release, offline demo, backup, and spoken explanation all work independently.

#### End-of-day evidence

- Tagged release
- Backup demo assets
- Completed rehearsal checklist

## 6. Scope-control rules

If work falls behind, cut in this order:

1. Forecast activation, automatically, if its mid-Day-4 gate is missed
2. Local demo recording, presentation animation, and visual flourish
3. GitHub Actions commit-SHA pinning and container-size optimization
4. OPO/DSA, region, and national comparison display
5. KDPI ≥60 recent-history display
6. Single-program report export
7. Coefficient display

Never cut:

- source hashes and contracts;
- composite program identity;
- non-overlapping annual modeling cohorts;
- feature-availability tests;
- baseline comparison;
- ridge temporal evaluation and factual model-card result;
- the frozen-replay and write-once-output rules;
- honest limitations;
- the offline demo; or
- the data and model cards.

## 7. Stop conditions

Stop and update the plan before proceeding if:

- a pinned source hash changes;
- a required machine field changes meaning;
- the annual cohorts cannot be shown to be non-overlapping;
- fewer than 200 programs remain in a key annual release;
- a proposed feature cannot be shown to exist by the prediction cutoff;
- implementation requires patient-level or nonpublic data;
- the app begins to imply clinical, causal, or regulatory use; or
- a task would displace a P0 item beyond day five.

If reconciling source definitions requires an era restriction that leaves fewer than three model-selection target years, one validation year, and one replay year, disable challenger promotion and ship the historical monitor, baseline evaluation, and persistence reference.

## 8. Release checklist

- [x] All P0 acceptance criteria in `SPEC.md` are satisfied.
- [x] Current milestone statuses and evidence are updated above.
- [x] Full CI is green from a clean checkout.
- [x] The tracked `<5 MB` bundle opens offline; full-data artifacts reproduce from the immutable, checksum-verified cache.
- [x] Frozen-replay output is hash-addressed, write-once, and was not used for retuning.
- [x] Forecast activation status and any promotion decision match the frozen configuration and rules.
- [x] Data card and model card match the artifacts.
- [x] App works offline and has no ranking or regulatory language.
- [x] Docker runs as non-root and passes its health check.
- [x] No raw source, credential, or large generated artifact is tracked; only the approved release bundle is committed.
- [x] Four-minute demo, backup screenshots, and likely-question notes are ready.
