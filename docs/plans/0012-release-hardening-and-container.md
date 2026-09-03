# Plan 0012 — Release hardening and container verification

**Milestone:** M6 reproducibility, documentation, and container  
**Status:** done
**Started:** 2026-09-03

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| Exactly one attributed, reproducible release bundle under 5 MB is tracked and bound by content hashes to the canonical processed, backtest, and frozen-replay artifacts | Release-manifest and bundle-integrity tests validate required provenance, checksums, allowed files, size, and equality with canonical artifact content | done |
| A clean checkout opens the tracked bundle without raw inputs or network access, while the immutable-cache command sequence reproduces it deterministically | Clean-checkout fixture/app smoke and a recorded local full-data reproduction log pass without live-source access | done |
| CI enforces the locked environment, formatting, lint, strict typing, branch coverage, dependency consistency, fixture/AppTest/process smoke, bundle policy, and Docker smoke | GitHub Actions reported 2/2 checks green for commit `2c815688c9ecb66d2519ee1c00638a803f17704d` | done |
| The container runs Streamlit as an unprivileged user, reads only the tracked bundle by default, and exposes a working health check | Docker Desktop 4.89.0 built the image; configured user `kasm`, runtime UID/GID 10001, HTTP 200 `ok`, and Docker `healthy` status were verified | done |
| README, data card, model card, decision record, diagrams, licensing boundary, accessibility checklist, and four-minute demo path match the frozen artifacts | Documentation review and repository-contract tests show every required deliverable and attribution | done |

## Test-first plan

- `test_release_manifest_contains_required_provenance`
- `test_app_bundle_matches_canonical_artifacts`
- `test_no_disallowed_large_files_tracked`
- `test_container_process_is_nonroot`
- release builder unit tests for deterministic hashes and atomic publication
- clean-checkout offline bundle/AppTest smoke

## Scope boundary

This milestone packages and verifies the already frozen M1–M5 outputs. It does not change source
meaning, features, temporal splits, promotion rules, frozen replay evidence, or the persistence
display decision. It does not rerun the canonical write-once replay in place.

## Test-first log

- The first focused run failed at collection because `kasm.reporting.artifacts` did not exist.
- Once the release builder existed, the repository-contract run failed because no tracked bundle,
  Dockerfile, hardened documentation, or CI gates existed.
- Documentation and CI contract tests failed independently before their required files and commands
  were added.
- The focused release, repository, and default-path AppTest set now passes with 14 tests.

## Completion evidence

- `artifacts build` published 12 approved payloads plus its manifest at 1,229,848 bytes. Bundle
  content identity is `1de89083ceebfda9afaf2d6b1c6ba3f1e6d0c1a1da16df9d09d994c4ec3581ad`.
- A deliverable-only clean-checkout simulation opened the default tracked bundle with network
  creation rejected. The running Streamlit process returned HTTP 200 and `ok` from its health URL.
- A fresh immutable-cache audit reproduced all 9 processed/pre-replay files byte-for-byte and
  reproduced replay metrics and prediction values; its run-specific provenance remained distinct.
- Locked sync, lock consistency, dependency consistency, format, lint, strict mypy, all 140 tests,
  and 83.81% combined core branch coverage pass.
- The current SRTR source, methods, and citations/permissions pages confirm the documented
  attribution boundary.
- Docker Desktop 4.89.0 with Linux engine 29.7.2 built
  `kidney-acceptance-signal-monitor:m6`. Image configuration named user `kasm`; the live
  container reported user `kasm`, UID/GID 10001, HTTP 200 with body `ok`, and Docker health
  `healthy`. The isolated verification container was removed after the check.
- The pinned CI workflow contains the same image/user/health assertions. GitHub Actions reported
  2/2 checks green for commit `2c815688c9ecb66d2519ee1c00638a803f17704d`.
- These closing edits only record completed status and external CI evidence; no executable behavior
  changed, so an additional fail-first test does not meaningfully apply.
