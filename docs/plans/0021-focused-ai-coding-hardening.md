# Plan 0021 — Close the AI coding safeguard gaps

**Status:** complete; all six fixes and Docker verification pass locally and in CI
**Started:** 2026-09-04 (2026-09-05 UTC)
**Starting revision:** `4155ea7`; clean worktree

## Purpose and scope

The user authorized the focused hardening recommended after the second AI coding audit.
Complete this bounded engineering pass before resuming Plan 0020's P0a documentation pass.
It closes the six recorded findings without changing either study's target, features, cohorts,
model settings, promotion rules, frozen configuration, or released results.

## Work and acceptance evidence

| Item | Behavior and expected evidence | Status |
|---|---|---|
| H1 | Agent instructions distinguish shared safeguards from V1, original V2, and separately specified follow-up contracts; approved release roots remain explicit | implemented; documentation reviewed |
| H2 | Failed outer size/hash checks stop before ZIP parsing; rejected member metadata stops before decompression; malformed compression returns an actionable issue | regression tests pass |
| H3 | Downloads stop once they exceed the pinned size, remove partial files, and still accept exact-size responses | regression tests pass |
| H4 | The actual default opener rejects non-HTTPS redirects before contacting their destination while accepting HTTPS redirects; tests stay offline | regression tests pass |
| H5 | A valid no-activation configuration produces point evaluation and persistence display without invented band/bootstrap evidence; activation-attempted behavior and trusted historical release loading stay unchanged | generation, publication, loading and offline AppTests pass |
| H6 | CI measures V2 as well as the V1 core, retains the 80% floor, and meaningful V2 boundary/publication tests bring V2 itself to at least 80% | 82.48% combined; 80.44% V2; local gates pass |

For H2–H5, add the smallest regression, run it to demonstrate the missing behavior, then
implement and rerun focused tests. Add a failing CI-policy test for H6 before changing the gate.
Additional V2 tests exercise existing validation and publication behavior; they may pass first
as characterization tests, with any discovered defect receiving its own failing regression.
H1 and explanatory documentation have a documentation-only failing-test exception.

No new dependency is planned. No canonical frozen replay command is authorized or necessary.
The no-activation path uses synthetic fixtures and temporary configurations only. Keep the
existing activation-attempted Parquet schema and values stable; missing optional evidence must
remain absent rather than become zero. Document any necessary artifact-contract representation
before implementation, without changing scientific rules.

## Verification

Run frozen sync, lock/dependency checks, Ruff formatting/lint, strict mypy, and the full suite
with combined V1/V2 statement/branch coverage at least 80%. Verify V2's own 80% floor as well.
Use the immutable source cache for verification; reproduce data/backtest/release outputs only
under an isolated ignored audit directory, compare payload identities, and never overwrite the
preserved originals. Exercise offline AppTests, application-process health, and Docker non-root
health checks. Review the final diff and record command evidence and remaining limitations here.

## Evidence log

- Mandatory reads completed. The audit commit is present and the worktree began clean.
- Initial implementation context selected by boundary symbols and their direct tests/consumers.
- All six audit findings are accepted as the scope of this pass; Plan 0020 analysis remains pending.
- H2–H4 first focused run: 17 failed, 16 passed. Failures demonstrated archive parsing after
  size/hash rejection, decompression after rejected metadata, uncaught unsupported/encrypted ZIPs,
  oversized streaming, and HTTP/FTP redirects across all five supported redirect status codes.
  After the fixes: 33 passed; focused Ruff and mypy passed. Relative/absolute HTTPS redirects
  still work through the actual opener with offline transport fixtures.

### H5 representation, fixed before implementation

The existing activation-attempted schema and JSON values stay unchanged. For a skipped activation,
the prediction band fields are null in a separate nullable Parquet schema; bootstrap and band
evaluation evidence are null, point metrics remain available, and display state is persistence
with `not_attempted`. No calibration year is claimed when calibration did not occur. The artifact
validator and view must distinguish this explicit state from malformed attempted-activation
evidence. Tests cover generation, evaluation, serialization, trusted loading, and offline display.

### Regression evidence and final review

- H5's first prediction and loading regressions failed on the required radius and required
  uncertainty objects. The offline no-activation AppTest also failed at loading before the fix.
  Release tests first rejected a valid null calibration year and accepted a skipped-activation
  marker paired with an attempted-activation frozen config. Both cases now behave correctly.
- Missing calibration and retained-but-unused calibration both produce null bands when activation
  is skipped. Spies prove no bootstrap or exact-binomial calculation occurs. Synthetic integration
  tests publish each activation state atomically and reject a second write to the same path.
  Serialization rejects band fields that disagree with activation state.
- A local synthetic comparison against `4155ea7` found exact equality for the attempted-activation
  fit, prediction values, Parquet schema, and all evaluation metrics, including sensitivities.
  This comparison did not read real replay outcomes or execute a replay CLI command.
- H6's CI-policy regression failed before adding V2. Its precision regression failed before
  adding `--precision=2`. An intermediate 79.75% V2 report rounded to 80% under the default
  display; the final gate uses two decimal places and passes at 80.44%.
- The added V2 characterization tests preserve existing behavior. They cover malformed and
  rehashed artifacts, missing/extra files, bad schemas and provenance, failed publication with
  rollback, null versus zero, publication precision, missing source fields, duplicate program
  rows, counts, dates, and source values that cannot be reconciled with the published precision.
  These tests are an explicit test-first exception because they add evidence for existing
  behavior; no V2 production code or scientific configuration changed.
- Review of the shared instruction wording retained V2's explicitly specified count reconstruction
  for its modeling transform, while keeping published percentages authoritative. V1's separate
  formula-recreation rule remains unchanged.

### Commands and results — 2026-09-04 (2026-09-05 UTC)

| Command | Result |
|---|---|
| `uv sync --frozen` | passed; 68 packages checked |
| `uv lock --check` | passed; 68 packages resolved |
| `uv pip check` | passed; installed packages compatible |
| `uv run ruff format --check .` | passed; 64 files formatted correctly |
| `uv run ruff check .` | passed, including security and complexity rules |
| `uv run mypy src/kasm` | passed; 30 source files |
| `uv run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling --cov=src/kasm/reporting --cov=src/kasm/patient_journey --cov-branch --cov-fail-under=80 --cov-report=json:data/hardening-0021/coverage.json --cov-report=term:skip-covered --tb=short` | 353 passed; 82.48% combined statement/branch coverage |
| `uv run coverage report --include="src/kasm/patient_journey/*" --fail-under=80 --precision=2` | passed; 80.44% V2 statement/branch coverage |
| `uv run pytest -q tests/unit/test_repository_config.py --tb=short` | 10 passed after wrapping the CI assertion string; no behavior changed |
| `uv run kasm data verify-cache` | all 9 sources verified; no issues |
| `uv run kasm data build --output-dir data/hardening-0021/processed` | 10,515 signal rows; 2,103 model-panel rows |
| `uv run kasm model backtest --panel-path data/hardening-0021/processed/model_panel.parquet --output-dir data/hardening-0021/modeling` | 2,763 baseline and 921 ridge predictions; alpha 10 |
| `uv run kasm artifacts build --processed-dir data/hardening-0021/processed --modeling-dir data/hardening-0021/modeling --output-dir data/hardening-0021/release` | 12 payload files; 1,229,848 bytes; original content identity reproduced |
| `uv run python data/hardening-0021/check_compatibility.py` | synthetic attempted-activation fit/schema/predictions/metrics exactly match `4155ea7` |
| `uv run python data/hardening-0021/check_app_health.py` | local Streamlit child process returned HTTP 200 / `ok`; child stopped afterward |
| `docker build -t kidney-acceptance-signal-monitor:hardening .` | initial attempt could not resolve Docker from the session PATH; the standard machine-wide path was absent. This did not establish that Docker was uninstalled; see the completed verification below |
| `git diff --check` | passed |

The isolated reproduction first compared all three processed and six backtest payload SHA-256
hashes with the preserved originals; all matched. It then copied the existing completed frozen
replay bundle into the isolated directory for release packaging, without recalculating it.
Release content identity remained
`1de89083ceebfda9afaf2d6b1c6ba3f1e6d0c1a1da16df9d09d994c4ec3581ad`.
Scripts, coverage details, app log, and reproduction outputs stay under ignored
`data/hardening-0021/`. Frozen configurations, source pins, dependency lock, and tracked V1/V2
release artifacts are unchanged. No dependency was added and no commit was created.

### Docker verification completed — 2026-09-04 (2026-09-05 UTC)

The user committed and pushed the hardening as
`5f26ec93262a53069dcd5b2c7fb1c8cfb783bf7e`, then requested local Docker verification.
Docker was installed under `%LOCALAPPDATA%/Programs/DockerDesktop/resources/bin/docker.exe`
and its Linux engine was running. The earlier check missed this per-user installation because
the executable was absent from the session PATH; accessing this location and the engine also
required execution outside the restricted sandbox. The earlier conclusion that Docker was
unavailable on the host was too broad.

Using that executable directly, Docker Desktop 4.89.0 / Engine 29.7.2 in the `desktop-linux`
context passed the following checks against the committed project:

| Check | Evidence |
|---|---|
| `docker build -t kidney-acceptance-signal-monitor:hardening-5f26ec9 .` | image built successfully with the frozen production dependencies |
| `docker image inspect ... --format '{{.Config.User}}'` | configured user `kasm` |
| `docker run --detach --rm --name <unique-verification-name> --network none ...` | isolated container started with external networking disabled |
| `docker exec <container-id> id -u` | UID `10001`, not root |
| `docker inspect <container-id> --format '{{.State.Health.Status}}'` | `healthy`, after waiting for the configured Docker health check |
| HTTP request inside the container to `http://127.0.0.1:8501/_stcore/health` | HTTP `200`, body `ok` |
| Cleanup | only the temporary verification container was removed; the built image remains available |

Independently confirmed [CI run 33938291395](https://github.com/ca34525/Kidney-Acceptance-Signal-Monitor/actions/runs/33938291395)
for the exact pushed commit. Both `quality` (job `101230449776`) and `container`
(job `101230609252`) completed successfully. This includes both coverage gates, offline app
startup, image build, and configured/runtime non-root checks.

This follow-through changes documentation only and records the existing test-first exception
for documentation. `git diff --check` passes; production code, dependencies, scientific settings,
and released results are unchanged from the verified commit. No further verification remains
open for Plan 0021. Resume Plan 0020 at P0a; its documentation pass, follow-up analysis, and
presentation work remain separate work.
