# Plan 0011 — Complete offline product flow

**Milestone:** M5 offline Streamlit product  
**Status:** done  
**Started:** 2026-09-03

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| The web process loads only trusted, precomputed historical and modeling artifacts and validates the frozen replay completion ledger before displaying model evidence | Unit tests reject missing, ambiguous, incomplete, hash-mismatched, and processed-panel-mismatched modeling bundles; the Streamlit test rejects any network access | done |
| An eligible established program receives the persistence next-calendar-year PSR projection from its latest trusted panel row; an ineligible program receives only an explicit unavailable state | Unit and AppTest coverage prove the view reads `public_forecast_eligible`, preserves prediction-origin precision, and never exposes an ineligible projection | done |
| The frozen non-promotion decision is visible and prevents both the ridge point and its otherwise-passing empirical band from appearing | AppTest shows persistence as the displayed model, names the failed frozen bias rule, and states that no nominal 80% empirical forecast band is displayed | done |
| The model-evaluation view compares neutral, persistence, historical mean, and ridge over the 2021–2024 rolling years and reports the 2025 replay separately as descriptive retrospective evidence | Pure reporting-service tests validate the four-model yearly table and replay summary; AppTest verifies model status, replay evidence, and the prospectively-unvalidated limitation | done |
| Users can review longitudinal overall and donor-stratum signals, latest volume context, source dates, data/model versions, and methodology without rankings or regulatory claims | AppTest covers program selection, overall and subgroup history, volume, provenance, methodology, explicit non-color status, and prohibited-language safeguards | done |

## Test-first plan

- `test_model_evaluation_loader_validates_completed_frozen_bundle`
- `test_model_evaluation_loader_rejects_ambiguous_or_tampered_bundle`
- `test_persistence_projection_reads_latest_trusted_panel_state`
- `test_ineligible_projection_is_unavailable`
- `test_complete_offline_app_flow_retains_persistence_and_suppresses_band`
- `test_app_ineligible_state_never_exposes_projection`
- `test_product_copy_excludes_prohibited_claims`

## Scope boundary

This slice completes the Day-5 offline product over existing precomputed artifacts. It does not
rerun or reinterpret the frozen replay, refit a 2026 ridge model, derive eligibility in the view,
display an empirical ridge band after point non-promotion, add rankings, or begin the Day-6 tracked
release-bundle and container work.

## Test-first log

- The first focused test run failed during collection because `kasm.reporting.product`,
  `latest_persistence_projection`, and `subgroup_history` did not exist.
- The first complete AppTest failed because the historical walking skeleton had no donor-stratum
  history or model-evaluation view.
- A second focused test-first increment failed because the model loader did not yet bind replay,
  rolling metrics, and the displayed historical panel to the same panel SHA-256.
- The final focused service and AppTest set passes with 18 tests.

## Completion evidence

- The product loader verifies the canonical replay directory name, completion status, file names,
  replay prediction/metrics checksums, provenance hashes, row count, evidence classification,
  point/band decision consistency, and equality of the processed-panel hash across historical,
  baseline, ridge, and replay artifacts.
- The real canonical artifacts resolve to `attempted_not_promoted`, persistence as the displayed
  model, no displayed band, 229 replay rows, and model version `7b25737b0549`.
- The Streamlit flow now includes longitudinal overall and donor-stratum charts, latest stratum and
  volume detail, explicit interval status, eligible persistence projection, unavailable state,
  separate band-suppression explanation, four-model 2021–2024 evaluation, 2025 replay evidence,
  methodology, limitations, and provenance.
- Offline reproduction verified all 9 cached sources, rebuilt 10,515 signal rows and 2,103 panel
  rows, and reproduced 2,763 baseline plus 921 ridge predictions with frozen alpha 10.
- The real-data Streamlit AppTest completed with no exceptions, and the running app health endpoint
  returned `ok`.
- Locked sync, formatting, lint, strict mypy, and all 126 tests pass. Core data, modeling, and
  reporting branch coverage is 84.81%.
