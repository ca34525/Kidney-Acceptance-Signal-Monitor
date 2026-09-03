# M6 reproduction and verification log

**Date:** 2026-09-03  
**Platform:** Windows development host; Linux container target  
**Purpose:** verify the tracked offline bundle, immutable-cache reproduction, quality gates, and
non-root container contract without changing the frozen experiment

## Release identity

- Payload files: 12
- Total bundle size: 1,229,848 bytes
- Bundle content SHA-256:
  `1de89083ceebfda9afaf2d6b1c6ba3f1e6d0c1a1da16df9d09d994c4ec3581ad`
- Model panel SHA-256:
  `00e1c6e14e0afdb9330022ac773eefaf1e3132edd24212e881967a2cc5a6c174`
- Frozen config SHA-256:
  `7b25737b054973386379088ccf27b66bfc9d5fd325dc4969d8449c80867f1ff1`
- Source manifest SHA-256:
  `5b30cd508a10e9cc24a6097f0eea868447c168b2744b50977aa56db43a6b86e5`
- Dependency lock SHA-256:
  `9783d6fc61d5c69012494519e674b5c17c0f346ba1923a4758c38fcdc573a687`

## Commands and evidence

| Command or check | Result |
|---|---|
| `uv sync --frozen` | passed; 68 locked packages checked |
| `uv lock --check` and `uv pip check` | passed; lock resolves and installed packages are compatible |
| `uv run kasm data verify-cache` | passed; all 9 immutable sources verified with no issues |
| `uv run kasm data sync` maintenance check | passed without network transfer; all 9 valid files skipped |
| Fresh `data build` → `model backtest` → confirmed replay audit → `artifacts build` | passed in `data/m6-reproduction`; 10,515 signal rows, 2,103 panel rows, 2,763 baseline predictions, 921 ridge predictions, and 229 replay predictions |
| Canonical-versus-audit comparison | all 9 processed/pre-replay files matched byte-for-byte; replay metrics excluding run provenance and all replay prediction row values matched |
| `uv run ruff format --check .` | passed; 42 files formatted |
| `uv run ruff check .` | passed |
| `uv run mypy src/kasm` | passed for 19 source files under strict mode |
| Required branch-coverage test command | passed; 140 tests, 83.81% combined branch coverage for core data/modeling/reporting code |
| Tracked-bundle offline AppTest | passed; app loaded default release roots without network access |
| Clean-checkout simulation | passed from a fresh deliverable-only directory using the locked preinstalled environment; no ignored data or repository metadata was present |
| Streamlit process `/_stcore/health` smoke | passed; HTTP 200 with body `ok` |
| Dockerfile contract | passed static regression test: final user `kasm`, UID 10001 creation, offline bundle roots, and health check precede the runtime command |
| `docker build` plus configured/runtime non-root and health smoke | passed on Docker Desktop 4.89.0 / Linux engine 29.7.2; image configured user `kasm`, live process user `kasm`, UID/GID 10001, HTTP 200 body `ok`, and Docker health `healthy`; verification container removed afterward |
| GitHub Actions clean-checkout CI | passed; 2/2 checks green for commit `2c815688c9ecb66d2519ee1c00638a803f17704d` |
| Source attribution and permissions check | confirmed against the current SRTR PSR, technical-methods, and citations/permissions pages on 2026-09-03 |

`uv run kasm data sync` remains the separately networked, nonblocking source-maintenance path. It
is intentionally not part of release reproduction or automated tests. Local Docker acceptance and
the pinned remote CI workflow are green; M6 is complete.
