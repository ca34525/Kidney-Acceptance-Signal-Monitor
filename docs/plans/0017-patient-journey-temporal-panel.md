# Plan 0017 — Patient-journey temporal design and canonical panel

**Milestone:** M11 patient-journey v2 temporal design and canonical panel
**Status:** done
**Started:** 2026-09-04

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| Overlapping or excessively delayed outcome cohorts cannot enter the primary panel | The v2 specification, Decision 0005, and typed experiment config fix four July–June pairs, allow a precision-safe maximum one-month prediction-origin offset, and retain the two named exclusions | done |
| Model evaluation cannot use labels unavailable at its historical origin | A strict-vintage fold helper derives training pairs by release availability and exposes only `1905→2205` as training evidence for the `2205→2505` evaluation origin | done |
| Future report availability cannot define the prediction universe | Panel rows originate from feature-release composite identities; missing later reports remain null/ineligible and target-only additions are not backfilled | done |
| Target meaning and eligibility remain explicit | Rows retain published percent, proportion, reconstructed count, empirical logit, cohort/follow-up timing, prior published target, and fixed `N>=10`, `N>=20`, and `N>=30` eligibility flags | done |
| Access and acceptance features are joined without identity or timing shortcuts | Same-release access, wait-time, and OAR rows join only on `(CTR_CD, CTR_TY)`; every family ends before the target cohort and missing values receive explicit indicators | done |
| Panel bytes are deterministic and schema-bound before any writer exists | An exact PyArrow schema and stable ordering reject duplicate pair/program keys and preserve month publication precision as a string plus precision | done |
| Immutable cached sources satisfy the panel contract without writing artifacts | A read-only in-memory build reports pair-level universe, matched-target, threshold, exclusion, and addition counts for all primary pairs | done |
| V1 frozen evidence remains outside the change | No v1 experiment, frozen replay, processed/modeling, release-bundle, or default-app payload changes | done |

## First failing tests

- `test_project_config_fixes_nonoverlapping_primary_pairs_and_exclusions`
- `test_primary_target_cohorts_are_pairwise_nonoverlapping`
- `test_prediction_origin_offset_rejects_1808_to_2105_without_inventing_a_day`
- `test_strict_vintage_folds_never_use_unpublished_training_truth`
- `test_panel_uses_feature_release_universe_and_keeps_missing_target_null`
- `test_target_only_program_is_not_backfilled_into_prediction_universe`
- `test_primary_and_sensitivity_threshold_boundaries_are_fixed`
- `test_history_uses_only_outcomes_public_by_prediction_origin`
- `test_suppressed_wait_time_stays_null_with_missing_indicator`
- `test_acceptance_join_uses_composite_identity_and_feature_release_only`
- `test_panel_schema_and_order_are_deterministic`

## Phase boundary

This plan freezes the temporal design and builds a typed, in-memory canonical panel with QA. It does
not write v2 artifacts, fit or compare models, parse safety outcomes, update the Streamlit
application, rerun the v1 frozen replay, or change the default product. A later plan must add a v2
writer/provenance contract before any generated panel is published.

## Test-first record

Documentation preceded production behavior because the repository agreement requires changes to
splits and scientific scope to be specified and decided first. The configuration tests then failed
because schema version 2 and the temporal-design structures did not exist. The panel tests initially
failed during collection because `PatientJourneyPanel` and its helpers did not exist. Subsequent
review-driven regressions failed for their intended reasons before implementation: nested rows could
carry a different release, the panel lacked a methodology-ledger identity, target-only additions
were counted from the directory instead of the outcome table, and `1808→2105` did not enforce the
maximum prediction-origin month offset.

## Completion evidence

- `uv --cache-dir .uv-cache sync --frozen` checked all 68 locked packages.
- `uv --cache-dir .uv-cache run ruff format --check .` passed for 51 files.
- `uv --cache-dir .uv-cache run ruff check .` passed.
- `uv --cache-dir .uv-cache run mypy src/kasm` passed for 24 source files.
- `uv --cache-dir .uv-cache run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling
  --cov=src/kasm/reporting --cov-branch --cov-fail-under=80` passed 181 tests at 83.93% branch
  coverage.
- `uv --cache-dir .uv-cache run kasm data verify-cache` verified all nine pinned sources with no
  issues.
- The read-only real-cache build produced 966 rows and 72 schema-bound columns. Pair counts were
  `246/243/241/236` feature-release programs, `229/229/231/230` matched targets, and
  `17/14/10/6` missing targets. Strict-vintage training-pair counts were `0/0/0/1`, and observed
  prediction-origin offsets were exactly zero or one month.
- `git diff --check` passed, and a targeted diff of the protected v1 experiment, frozen replay,
  processed/modeling roots, release bundle, and default Streamlit entry point was empty.
- Independent review found no remaining actionable issues after the nested-row, ledger-identity,
  target-addition, and prediction-origin regressions were added.
