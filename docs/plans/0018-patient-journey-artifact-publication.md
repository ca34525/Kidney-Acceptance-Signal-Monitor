# Plan 0018 — Patient-journey canonical artifact publication

**Milestone:** M12 patient-journey v2 canonical artifact publication
**Status:** done
**Started:** 2026-09-04

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| The in-memory v2 panel is published only to its config-owned processed root | A dedicated `kasm patient-journey data build` command loads the typed config, methodology ledger, pinned manifest, dependency lock, and verified cache without accepting an arbitrary output override | done |
| Readers can distinguish a processed-data build from model evidence | Every artifact carries provenance that records the target and cohort timing, exact source/config/ledger/lock identities, schema, Git state, UTC build time, and `model_fitted: false` with no model parameters | done |
| QA preserves the temporal and eligibility evidence used to build the panel | The QA artifact records pair summaries, strict-vintage training pairs, named exclusions, eligibility-status counts, sensitivity thresholds, missing future reports, source-derived histories and earliest identities, complete target rosters, and feature-cohort aggregate counts | done |
| Publication cannot expose a partial or mixed-generation bundle | Files are staged together and the directory is replaced atomically with rollback or recovery of a prior valid bundle if final publication is interrupted | done |
| Later analysis cannot silently consume tampered or schema-drifted panel bytes | A trusted validator checks the exact file set, manifest hashes and sizes, Parquet schema and metadata, fixed scientific claims, row-level scientific invariants, source-derived QA evidence, configuration identities, and per-release source hashes | done |
| Canonical payloads are reproducible while run provenance remains honest | Fixed build context produces identical logical panel and JSON payloads; real builds record the actual UTC time, Git HEAD, and dirty-worktree state, with dirty builds marked noncanonical | done |
| V1 frozen evidence remains outside the change | No v1 experiment, frozen replay, processed/modeling roots, release bundle, or default Streamlit behavior changes | done |

## First failing tests

- `test_patient_journey_writer_publishes_exact_manifest_bound_artifacts`
- `test_patient_journey_writer_failure_leaves_prior_bundle_unchanged`
- `test_patient_journey_build_manifest_contains_required_provenance_and_no_model_claim`
- `test_patient_journey_qa_preserves_pairs_exclusions_vintage_folds_and_eligibility`
- `test_patient_journey_artifact_payload_is_deterministic_with_fixed_build_context`
- `test_patient_journey_artifact_validator_rejects_tampered_hash_or_schema`
- `test_patient_journey_build_command_uses_configured_v2_root_and_reports_counts`

## Phase boundary

This milestone creates and validates processed v2 artifacts only. It does not fit or compare a
baseline or Ridge model, parse safety outcomes, update the Streamlit application, publish a tracked
v2 release bundle, rerun v1 frozen evaluation, or change the default product. Baseline definitions,
comparison populations, metric aggregation, calibration scale, and clustered-bootstrap settings
must be frozen in a later plan before model evaluation begins.

The cohort-level value already carried in the panel is derived from reconstructed counts. This
milestone does not rename it as a published national comparator or use it as evaluation evidence.

## Test-first record

Documentation precedes implementation because the repository agreement requires the artifact and
reproducibility boundary to be planned before a writer is introduced. Record each intended failing
test and its failure reason here before implementing production behavior.

- The first focused run failed during collection with `ModuleNotFoundError` for
  `kasm.patient_journey.artifacts`, before the writer, provenance contract, and validator existed.
- After the artifact module passed its focused contract tests, the CLI regression failed because
  `kasm.cli` did not expose a patient-journey build function or command namespace.
- A QA completeness regression then failed because eligibility counts encoded the thresholds only
  in their labels; the artifact now records the exact configured `N>=10`, `N>=20`, and `N>=30`
  values separately from the resulting counts.
- Independent review produced two same-schema regressions that failed because the first writer
  could publish an unconfigured release pair or an eligibility flag inconsistent with its target
  and history values. The artifact boundary must now recompute scientific row invariants rather
  than relying on Arrow types and checksums alone.
- A second review pass produced failing regressions for mutable fixed scientific claims, missing
  reconstructed successes, negative model inputs, inconsistent history and first-observed fields,
  self-asserted target-only counts, and an input snapshot changing during construction. The writer
  and trusted reader now reject those cases and bind one typed input snapshot through publication.
- The final review pass identified evidence that could not be reconstructed from panel rows alone.
  Pair QA now retains the source-derived contributing history releases and proportions, earliest
  identity release, complete target-outcome roster, and feature-cohort target numerator and
  denominator. Publication and trusted reads recompute the corresponding row fields. Independent
  re-review reported no remaining concrete defect within the M12 scope.

## Completion evidence

- `uv --cache-dir .uv-cache sync --frozen` — passed; 68 packages checked. The repo-local cache was
  used because the sandbox denied access to uv's default user cache.
- `uv --cache-dir .uv-cache run ruff format --check .` — passed; 52 files already formatted.
- `uv --cache-dir .uv-cache run ruff check .` — passed.
- `uv --cache-dir .uv-cache run mypy src/kasm` — passed; 25 source files checked.
- `uv --cache-dir .uv-cache run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling
  --cov=src/kasm/reporting --cov-branch --cov-fail-under=80` — passed; 214 tests and 83.93%
  measured coverage.
- `uv --cache-dir .uv-cache run kasm data verify-cache` — passed; all 9 pinned sources verified.
- `uv --cache-dir .uv-cache run kasm patient-journey data build` — passed from the immutable cache;
  966 rows published with pair sizes `246, 243, 241, 236`, strict-vintage training-pair counts
  `0, 0, 0, 1`, and artifact-set SHA-256
  `fc14f2348a7b7698bdc44e1573c0f929d11b24aa01740d5118c8d247feaf231e`.
- The real dirty-worktree build is correctly marked noncanonical and contains no fitted model or
  model parameters. Generated output remains under the ignored v2 data root.
- `git diff --check` and the protected-v1 diff check — passed after this plan update; no
  whitespace errors and no v1 config, frozen evidence, processed/modeling roots, release bundle,
  or Streamlit entry-point changes were present.
