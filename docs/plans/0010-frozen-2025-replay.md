# Plan 0010 — Frozen 2025 implementation replay

**Milestone:** M4 ridge challenger and frozen retrospective replay
**Status:** done
**Started:** 2026-09-03

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| The replay requires the explicit CLI confirmation flag and the committed pre-replay configuration | CLI tests reject a missing `--confirm`, and the runner rejects a frozen config whose bytes differ from `HEAD` | done |
| The fixed-alpha ridge replay fits analytic rows from target years 2018–2023, excludes all 2024 outcomes, and evaluates only target year 2025 | A regression test records the exact training/evaluation years and changes a 2024 outcome without changing any 2025 prediction | done |
| Replay reporting applies the frozen paired bootstrap, point-promotion gate, and independent empirical-band gate without allowing a passing ridge-band gate to expose an unpromoted ridge forecast | Unit tests check the serialized bootstrap evidence, point default, coverage interval, width comparison, raw band-gate result, and effective band visibility | done |
| Replay output includes target-year, volume-quartile, first-observed/missingness, and prespecified 2020/2021 transition-exclusion diagnostics | Unit tests exercise each reporting slice and reject missing quartile-1 gate evidence | done |
| Canonical output is keyed by frozen-config and source-manifest SHA-256 values and is write-once | Integration tests prove atomic publication of predictions, metrics, and completion ledger and reject any existing canonical directory | done |
| The one canonical 2025 replay is run only after the implementation and relevant checks are green | The completion section records the command, hashes, result, and artifact paths without changing the frozen rules | done |

## Test-first log

- The first focused run failed during collection because `kasm.modeling.replay` did not exist.
- After the initial green implementation, a release-decision test failed because no resolver yet
  prevented a passing ridge-band gate from exposing output when the ridge point gate failed.
- The focused replay/CLI/integration suite now covers confirmation, fixed fitting years, 2024
  exclusion, diagnostics, sensitivities, committed-config enforcement, atomic publication,
  write-once refusal, and effective point/band display state.

## Completion evidence

- All nine source-cache entries verified, the data build reproduced 10,515 signal rows and 2,103
  panel rows, and the pre-replay backtest reproduced all three hashes frozen in the committed
  config before replay.
- The canonical replay directory is
  `data/modeling/frozen-replay/7b25737b054973386379088ccf27b66bfc9d5fd325dc4969d8449c80867f1ff1_5b30cd508a10e9cc24a6097f0eea868447c168b2744b50977aa56db43a6b86e5`.
  It contains 229 prediction rows, metrics, and a completion ledger.
- Ridge replay log-OAR MAE was `0.23990059773153982` versus persistence
  `0.2669515989967713`, for 10.13% skill. The paired-bootstrap interval for the mean absolute-error
  difference was `[-0.040869910508441396, -0.013321974380916158]`.
- The point gate failed only `bias_not_exceed_persistence`: ridge absolute mean signed log error
  was `0.011451575243091318` versus `0.008854836374016146` for persistence. Activation is
  `attempted_not_promoted`, so persistence remains the displayed projection.
- The separate ridge band gate passed with 81.66% coverage, exact 95% interval 76.03%–86.45%,
  and mean-width ratio 0.9005. Effective ridge-band display remains suppressed because the point
  model was not promoted.
- The model card records target-year, quartile, missingness/entry, 2020/2021 transition-exclusion,
  methodology, provenance, and limitation evidence without changing the frozen configuration.
- Locked sync, formatting, lint, strict mypy, all 117 tests, and 85.22% branch coverage across the
  core data, modeling, and reporting modules passed after the release-decision safeguard landed.

## Scope boundary

This slice evaluates the already frozen 2025 replay exactly once. It must not select a new alpha,
change features or thresholds, add 2024 outcomes to the fit, overwrite a canonical result, describe
the replay as prospective validation, or use replay evidence to revise the scientific contract.
