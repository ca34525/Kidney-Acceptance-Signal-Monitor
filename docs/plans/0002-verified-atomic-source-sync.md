# Plan 0002 — Verified atomic source sync

**Milestone:** M1 source acquisition and data contracts
**Status:** done
**Started:** 2026-09-03

## Reading this historical record — 2026-09-05

This completed V1 step added an explicit download command for the nine agreed source releases.
"Atomic publication" means a temporary download becomes the usable cache file only after its
size, fingerprint, file type, and required archive member pass verification. Existing files are
kept unchanged; a bad existing file is reported for review. The second download command below
therefore fetched nothing. These checks established the original acquisition behavior; later
network and archive protections are recorded in Plan 0021.

Coverage wording clarification: the historical coverage percentages include both statements and
branches; they are not branch-only measurements. The original commands and numbers are retained.

## Scope and acceptance evidence

| Behavior | Expected evidence | Status |
|---|---|---|
| Missing pinned sources can be acquired explicitly | `kasm data sync` downloads only missing manifest URLs | done |
| A download is never published before full verification | A hash-mismatch test fails first, then proves the target and temporary file are absent | done |
| HTTP failures are actionable and do not leave partial inputs | Focused test asserts release-specific failure and clean cache | done |
| Existing cache files remain immutable | Valid files are skipped; invalid files are reported and never overwritten | done |
| ZIP and XLS contracts are reused during acquisition | Downloaded size, SHA-256, file type, and configured member checks pass before atomic publication | done |
| The nine-source start condition is retried | `kasm data sync` followed by `kasm data verify-cache` reports the real cache state | done |

## Test-first log

- Initial focused command: `uv run pytest -q tests/unit/test_download.py tests/unit/test_cli.py`;
  collection failed because `kasm.data.download` did not exist.
- Passing focused command with workspace-local pytest paths: 14 cache, download, and CLI tests
  passed.
- Real sync downloaded all nine release codes (`1808` through `2605`) with no issues; the files
  total 98,653,729 bytes.
- Offline `uv run kasm data verify-cache` checked all nine sources with no issues.
- A second `data sync` skipped all nine verified existing files and downloaded none.
- `uv sync --frozen` passed; the full suite passed 17 tests.
- Ruff format, Ruff lint, and strict mypy passed. The required core branch-coverage command passed
  at 84.55%; modeling and reporting packages do not exist yet and produced informational warnings.

## Scope note

This slice adds only the manual/preflight network boundary required by `SPEC.md`. It does not parse
workbooks, update manifest checksums, extract archives, or make release reproduction depend on live
URLs. Tests use local fakes and never access the network.

The root data-cache ignore rule is anchored as a mechanical configuration correction. The previous
unanchored rule also ignored the importable `src/kasm/data/` package, which made acquisition code
impossible to track; `git check-ignore` is the acceptance evidence for this non-runtime change.
