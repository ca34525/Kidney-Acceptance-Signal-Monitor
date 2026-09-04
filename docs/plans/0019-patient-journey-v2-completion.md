# Plan 0019 — Patient-journey v2 completion

**Milestone:** M13 patient-journey v2 exploratory study and optional product
**Status:** complete
**Started:** 2026-09-04

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| Current retrospective model evidence is fixed before results are inspected | The typed v2 config fixes baseline definitions, feature groups and transforms, Ridge regularization, the one strict-vintage evaluation fold, metrics, deterministic volume strata, program-clustered paired bootstrap settings, sensitivity populations, and `promotion_allowed: false` | complete |
| Baselines and Ridge comparisons cannot use unpublished truth or prohibited features | Focused tests fail first for future-vintage labels, identity/location/future fields, non-fold-local preprocessing, post-result feature selection, and any Ridge evaluation origin without an earlier labeled training cohort | complete |
| V2 evaluation is reported on the published percentage-point scale | Deterministic artifacts contain persistence, available-cohort, and historical-mean baselines; five prespecified Ridge feature-group comparisons; balanced MAE, signed error, named-scale calibration, volume-weighted and median errors; fixed volume/missingness strata; and program-clustered paired intervals | complete |
| The one-fold evidence cannot be mistaken for promotion or stable validation | Machine-readable results and user-facing copy identify the `2205→2505` strict-vintage fold, its single `1905→2205` training pair, and the result as retrospective exploratory feasibility evidence with no promoted model or future forecast | complete |
| Required safety context is source-ledgered and remains separate from the patient-journey outcome | A typed parser and artifact capture the approved pre-transplant mortality and post-transplant graft-failure measures with their own cohorts, denominators, directions, uncertainty, and availability; only safety values proven available before an evaluation origin may enter the secondary feature group | complete |
| V2 modeling output is isolated, atomic, provenance-bound, and trusted on read | `kasm patient-journey model evaluate` reads the validated processed bundle and config-owned modeling root, writes the exact artifact set atomically, records source/config/ledger/lock/panel hashes plus Git/build context and model parameters, and rejects tampering or mixed generations | complete |
| A separately approved V2 demo bundle works offline without changing V1 | `kasm patient-journey artifacts build` publishes one attributed bundle under `artifacts/patient_journey_v2/`; a clean offline loader validates content hashes and the V1 release bundle and default app remain unchanged | complete |
| The optional V2 interface supports the required research flow without rankings or causal/clinical/regulatory claims | A separate Streamlit entry point loads only trusted precomputed V2 artifacts and lets a user review patient-centered history, exploratory forecast evaluation, access/acceptance context, and separately labeled safety context; an AppTest covers selection, missing states, timing, provenance, and the nonpromotion state | complete |
| Documentation and reproducibility evidence match the artifacts | V2 data/model cards, README commands, limitations, result tables, and a reproduction record agree with the generated bundle; focused checks and the repository-required verification suite pass | complete |
| V1 scientific and product evidence remains immutable | A protected-path diff check shows no changes to the V1 experiment/frozen configs, V1 generated data/modeling roots, `artifacts/release/`, or default `app/streamlit_app.py` behavior | complete |

## First failing tests

- `test_v2_model_config_freezes_baselines_features_metrics_bootstrap_and_nonpromotion`
- `test_v2_model_matrix_rejects_identity_location_and_future_fields`
- `test_v2_evaluation_uses_only_strict_vintage_training_pairs`
- `test_v2_preprocessing_is_fit_only_on_the_training_pair`
- `test_v2_baselines_use_only_values_available_at_prediction_origin`
- `test_v2_metrics_are_reported_on_published_percentage_point_scale`
- `test_v2_volume_strata_are_deterministic_with_ties`
- `test_v2_paired_bootstrap_resamples_programs_with_all_repeated_rows`
- `test_v2_ridge_feature_groups_are_fixed_and_inverse_logit_bounded`
- `test_v2_safety_parser_preserves_cohort_direction_interval_and_missingness`
- `test_v2_secondary_safety_features_require_proven_availability`
- `test_v2_model_writer_is_atomic_provenance_bound_and_tamper_evident`
- `test_v2_release_bundle_matches_trusted_processed_and_modeling_artifacts`
- `test_v2_app_loads_offline_and_displays_nonpromotion_and_timing`
- `test_v2_app_never_displays_rank_score_or_risk_adjusted_target_claim`

## Scientific freeze before real-data evaluation

No real-data baseline or Ridge result will be inspected until the specification, Decision 0006,
typed configuration, and focused configuration tests agree on every analytical degree of freedom.
The processed panel may be inspected for schema and source-contract work, but target-comparison
metrics are out of bounds until that freeze is recorded here with the configuration hash.

Freeze recorded before evaluation: `configs/patient_journey_v2/experiment.yaml` SHA-256
`ab8c01453c36039b293a8e7453b17b2b326faf734a081a4b67f8bfe132b1de79`. Decision 0006,
the V2 specification, the typed loader, and the focused config/model/evaluation tests agree on the
three baselines, five ordered Ridge feature groups, sole `1905→2205` training pair, sole
`2205→2505` Ridge evaluation pair, fixed Ridge parameters, percentage-point metrics, deterministic
target-N quartiles, 2,000-replicate program-clustered bootstrap with seed `20260904`, and permanent
nonpromotion. No real-data target-comparison metric had been run or inspected at this point.

The current pinned releases support only one strict-vintage Ridge evaluation fold. Completion means
shipping honest exploratory evidence and a historical/context product, not selecting or promoting a
forecasting model. A new same-cadence release requires a new locked prospective plan; it may not be
folded into this result after inspection.

## Test-first record

Documentation and the analytical freeze precede production modeling behavior because the working
agreement requires all target, feature, split, metric, and claim decisions to be fixed before model
results are viewed.

- The model-configuration contract first failed because the typed loader exposed no `model_design`;
  it now rejects any change to the fixed baselines, feature order, transforms, fold, metrics,
  bootstrap, or nonpromotion state.
- Modeling and evaluation tests first failed at import because their production modules did not
  exist. They now cover the feature allowlist, bounded inverse link, train-fold-only preprocessing,
  strict-vintage rows, percentage-point metrics, volume strata, sensitivities, and whole-program
  paired resampling.
- Safety tests first failed because the ledger/parser exposed no typed safety contract. Real-source
  replay then failed on `2105` `MM/DD/YYYY` dates and a valid safety program absent from Tiers;
  both cases are preserved as regressions without weakening composite-key validation.
- Panel publication first failed because no separate safety artifact or waiting-list-mortality
  feature fields existed. The processed writer now publishes and revalidates the exact panel,
  safety, QA, and manifest generation atomically.
- Model-artifact and release tests first failed because their modules did not exist. They now reject
  partial files, unexpected files, checksum changes, schema drift, provenance disagreement, mixed
  generations, recomputation disagreement, and loss of the permanent nonpromotion state.
- The AppTest first failed because the separate V2 entry point did not exist, then exposed a
  dictionary-sort bug before passing. It now exercises offline loading, program selection,
  missing-value text, timing, safety separation, provenance, and no-promotion/no-future-forecast
  copy against the tracked bundle.

## Completion evidence

- Source-contract replay: initial safety parsing failed on the real 2105 tables because SFL uses
  `MM/DD/YYYY` dates and its safety roster includes a program absent from the same-release Tiers
  directory. Regression tests now preserve those valid source behaviors while retaining composite
  `(CTR_CD, CTR_TY)` identity and forbidding name joins.
- Processed build after safety integration: `uv --cache-dir .uv-cache run kasm patient-journey data build`
  succeeded with 966 panel rows and artifact-set SHA-256
  `dc5f96040d5a3f3dd0ec644c72f9d011c12aeb162e03f43ae878e9715eb98ba8`; the separate safety
  table contains 5,678 rows across four source-ledgered families.
- Model evaluation: `uv --cache-dir .uv-cache run kasm patient-journey model evaluate` succeeded
  with 3,685 historical prediction rows and artifact-set SHA-256
  `ac579a8891d01d71b6a52a83c90c19874da9a6594fab33940b2e646983dbdf68`.
- Release publication: `uv --cache-dir .uv-cache run kasm patient-journey artifacts build`
  succeeded with four payload files, 679,407 bytes, and bundle content SHA-256
  `6542fc61968b4cda95a33dcb5057b41b37d6fc3ba5ad40397ee8e7a1ed2cc205`. The manifest records the
  uncommitted worktree as dirty and the build as noncanonical.
- Prespecified results: the three all-release baseline MAEs are 8.14 for persistence, 9.87 for the
  available-cohort reference, and 7.45 for the historical mean (865 rows each). On the sole
  218-row Ridge fold, fixed-group MAEs are 11.49 for history, 7.35 for history plus acceptance,
  14.52 for history plus access, 10.57 for history plus access and acceptance, and 12.52 for full
  plus safety. These remain one-fold descriptive evidence; no model is promoted.
- Focused V2 verification: 99 tests passed. The final bundle-specific AppTest/artifact subset passed
  5 tests after the final rebuild.
- Independent final review: the first pass found that a self-rehashed mixed release could evade the
  top-level manifest, publication/COVID-segment timing was not fully visible, and the AppTest
  overstated its coverage. New failing tests reproduced those gaps. The release now recomputes the
  modeling identity, binds processed payload hashes to prediction provenance, cross-checks embedded
  panel/safety/model generations, and validates evaluation nonpromotion. The app and AppTest now
  cover public-aggregate/non-patient/noncausal boundaries, month/day publication precision,
  effective COVID-separated segments, a real missing-value program, and provenance fields.
- Repository gates: `uv sync --frozen`, `ruff format --check .`, `ruff check .`, and
  `mypy src/kasm` passed; the final required coverage suite passed 235 tests at 83.93% branch
  coverage.
- V2 process smoke: `streamlit run app/patient_journey_v2.py --server.headless true
  --server.port 8513` started successfully and `/_stcore/health` returned HTTP 200 with `ok`.
- Container verification: `docker build -t kidney-acceptance-signal-monitor .` succeeded with
  Docker client/server 29.7.2. A temporary container started successfully, reported configured user
  `kasm`, reached Docker health status `healthy`, and returned HTTP 200 with `ok` from
  `/_stcore/health`; it was then stopped and removed.
- Offline command smoke: nine sources verified; isolated V1 data build produced 10,515 signal and
  2,103 panel rows; isolated V1 backtest produced 2,763 baseline and 921 Ridge predictions; a
  short-path isolated V1 release reproduced its 12-file, 1,229,848-byte bundle with content identity
  `1de89083ceebfda9afaf2d6b1c6ba3f1e6d0c1a1da16df9d09d994c4ec3581ad`.
- Protected-path evidence: `git diff -- configs/experiment.yaml configs/frozen_experiment.yaml
  app/streamlit_app.py artifacts/release` is empty, and no protected V1 data/modeling/release path
  appears in `git status --short`.
