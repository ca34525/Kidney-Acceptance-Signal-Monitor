# Reproducing the program prediction sprint

The [findings](program_prediction_results.md) describe the completed exploratory study.
Follow [Plan 0031](plans/0031-program-prediction-sprint.md) and its
[specification](specs/program-prediction-sprint-0031.md). Do not use the original V1 frozen-replay
command to reproduce this sprint. No source refresh, application change or deployment is needed.

## Environment and verified inputs

Use Python 3.12 and the committed `uv.lock`, from the repository root. On this Windows host,
the default user cache is inaccessible and Application Control blocks the `mypy` launcher;
the module invocation below performs the same type check. A short test temporary path matters
because older hash-addressed artifact tests can exceed Windows path limits in a nested folder.

```powershell
Set-Location 'D:\Projects\Kidney Acceptance Signal Monitor'
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
$env:MPLCONFIGDIR = Join-Path (Get-Location) '.uv-cache/matplotlib'
uv sync --frozen
uv run kasm data verify-cache
```

The complete build reuses nine immutable workbook inputs pinned in
[the source manifest](../configs/data_sources.yaml), and the seven usable B1 release bindings
in [the reviewed B1 ledger](../configs/waiting_list/sources.json). Preserve the ledger's
`evidence_path` files and any `original_pdf_path` files locally as well as the verified raw
cache. `build` verifies their recorded hashes, the workbook identities and source schema.
These ignored inputs are prerequisites on another checkout; a missing or changed file must
fail rather than acquire a new accepted hash. The recorded panel's
[source ledger](../data/research/program-prediction-0031/initial-panel/source-ledger.json)
and [QA](../data/research/program-prediction-0031/initial-panel/panel-qa.json) retain the bindings,
omitted candidate block, coverage and exclusion reasons. No network is used by the tests.

## Exact executed commands

The commands below succeeded in dependency order. Each `--run-id` is write-once. On this
workspace the IDs already exist, so a repeated publication intentionally fails on overwrite.

```powershell
uv run kasm program-prediction build --config configs/program_prediction/experiment.json --run-id initial-panel
uv run kasm program-prediction screen --config configs/program_prediction/experiment.json --panel-run initial-panel --run-id initial-discovery
uv run kasm program-prediction shortlist --config configs/program_prediction/experiment.json --discovery-run initial-discovery --selection configs/program_prediction/shortlist.json --run-id initial-shortlist
uv run kasm program-prediction assess --config configs/program_prediction/experiment.json --panel-run initial-panel --shortlist-run initial-shortlist --run-id initial-later
uv run kasm program-prediction build --config configs/program_prediction/followup_1_no_oar.json --run-id followup-1-panel
uv run kasm program-prediction screen --config configs/program_prediction/followup_1_no_oar.json --panel-run followup-1-panel --run-id followup-1-discovery
uv run kasm program-prediction assess --config configs/program_prediction/followup_1_no_oar.json --panel-run followup-1-panel --shortlist-run initial-shortlist --run-id followup-1-later
uv run kasm program-prediction report --config configs/program_prediction/experiment.json --discovery-run initial-discovery --assessment-run initial-later --shortlist-run initial-shortlist --run-id initial-report
uv run kasm program-prediction reassess --config configs/program_prediction/followup_2_review.json --run-id followup-2-review
```

To audit reproduction beside the completed runs, choose distinct IDs and use those new IDs
in each dependent command. Copy follow-up configurations to separately named local files and
set `parent_run` to the corresponding new preceding assessment. Do not edit the original
settings, shortlist or run contents. The ancestry checks accept distinct audit identities
while enforcing the same study and preserved original choice. An audit is still a reproduction
of inspected evidence, not new validation. Commit any configuration used for a recorded fit.

To regenerate the initial report alone without fitting, run the `report` command above with
a new output ID and the same saved parents. `reassess` likewise only reads saved Round 1
predictions. Settings and code identities are checked before and after execution; completed
payloads are hashed and published atomically. Loading verifies the requested stage, every
payload's SHA-256 and size, and recorded parent completion identities.

## Recorded runs and complete results

All paths below are under ignored `data/research/program-prediction-0031/`. Each completion
record contains full Git revision, clean/dirty state, source/configuration/specification/code
and lock hashes, UTC timestamps, parent fingerprints and payload identities. All nine recorded
runs have `git_worktree_dirty: false`.

| Run | Committed revision | Complete evidence |
|---|---|---|
| `initial-panel` | `a4a394f` | [Completion](../data/research/program-prediction-0031/initial-panel/completion.json), [panel](../data/research/program-prediction-0031/initial-panel/panel.json), [feature map](../data/research/program-prediction-0031/initial-panel/feature-map.json) |
| `initial-discovery` | `a4a394f` | [Completion](../data/research/program-prediction-0031/initial-discovery/completion.json), [predictions](../data/research/program-prediction-0031/initial-discovery/predictions.json), [metrics](../data/research/program-prediction-0031/initial-discovery/metrics.json), [folds](../data/research/program-prediction-0031/initial-discovery/folds.json), [failures](../data/research/program-prediction-0031/initial-discovery/failures.json), [exclusions](../data/research/program-prediction-0031/initial-discovery/exclusions.json) |
| `initial-shortlist` | `b1c1971` | [Completion](../data/research/program-prediction-0031/initial-shortlist/completion.json), [saved questions](../data/research/program-prediction-0031/initial-shortlist/shortlist.json), [fixed references](../data/research/program-prediction-0031/initial-shortlist/comparators.json) |
| `initial-later` | `b1c1971` | [Completion](../data/research/program-prediction-0031/initial-later/completion.json), [predictions](../data/research/program-prediction-0031/initial-later/predictions.json), [metrics](../data/research/program-prediction-0031/initial-later/metrics.json), [folds](../data/research/program-prediction-0031/initial-later/folds.json), [failures](../data/research/program-prediction-0031/initial-later/failures.json), [exclusions](../data/research/program-prediction-0031/initial-later/exclusions.json), [reviews](../data/research/program-prediction-0031/initial-later/reviews.json), [selection flags within reviews](../data/research/program-prediction-0031/initial-later/reviews.json) |
| `followup-1-panel` | `0508c4a` | [Completion](../data/research/program-prediction-0031/followup-1-panel/completion.json), [panel](../data/research/program-prediction-0031/followup-1-panel/panel.json), [feature map](../data/research/program-prediction-0031/followup-1-panel/feature-map.json) |
| `followup-1-discovery` | `0508c4a` | [Completion](../data/research/program-prediction-0031/followup-1-discovery/completion.json), [predictions](../data/research/program-prediction-0031/followup-1-discovery/predictions.json), [metrics](../data/research/program-prediction-0031/followup-1-discovery/metrics.json), [folds](../data/research/program-prediction-0031/followup-1-discovery/folds.json), [failures](../data/research/program-prediction-0031/followup-1-discovery/failures.json), [exclusions](../data/research/program-prediction-0031/followup-1-discovery/exclusions.json) |
| `followup-1-later` | `0508c4a` | [Completion](../data/research/program-prediction-0031/followup-1-later/completion.json), [predictions](../data/research/program-prediction-0031/followup-1-later/predictions.json), [metrics](../data/research/program-prediction-0031/followup-1-later/metrics.json), [folds](../data/research/program-prediction-0031/followup-1-later/folds.json), [failures](../data/research/program-prediction-0031/followup-1-later/failures.json), [exclusions](../data/research/program-prediction-0031/followup-1-later/exclusions.json), [reviews](../data/research/program-prediction-0031/followup-1-later/reviews.json), [selection flags within reviews](../data/research/program-prediction-0031/followup-1-later/reviews.json) |
| `initial-report` | `0508c4a` | [Completion](../data/research/program-prediction-0031/initial-report/completion.json), [HTML](../data/research/program-prediction-0031/initial-report/report.html), [all initial metrics](../data/research/program-prediction-0031/initial-report/complete-results.json), [period CSV](../data/research/program-prediction-0031/initial-report/period-metrics.csv), [summary CSV](../data/research/program-prediction-0031/initial-report/summary-metrics.csv), [review CSV](../data/research/program-prediction-0031/initial-report/review-metrics.csv), [paired errors](../data/research/program-prediction-0031/initial-report/error-differences.json), [paired decisions](../data/research/program-prediction-0031/initial-report/decision-differences.json) |
| `followup-2-review` | `b301cb4` | [Completion](../data/research/program-prediction-0031/followup-2-review/completion.json), [HTML](../data/research/program-prediction-0031/followup-2-review/report.html), [full decision result](../data/research/program-prediction-0031/followup-2-review/report.json), [inherited errors](../data/research/program-prediction-0031/followup-2-review/inherited-metrics.json), [review CSV](../data/research/program-prediction-0031/followup-2-review/review-metrics.csv), [selection flags](../data/research/program-prediction-0031/followup-2-review/review-selections.json), [paired errors](../data/research/program-prediction-0031/followup-2-review/error-differences.json), [paired decisions](../data/research/program-prediction-0031/followup-2-review/decision-differences.json) |

The initial discovery/later ledgers have 25,240/16,876 prediction records, including repeated
program-year rows across procedures. Round 1 has 4,928/3,297. Missing target outcomes remain
in these ledgers; all four fit-stage failure lists are empty. There are 180 initial and 35
Round 1 procedure/year records: 100 initial pipeline fits, five fitted OAR baseline fits,
20 follow-up pipeline fits and 90 nonfitted baseline evaluations. Round 2 performs no fits.
The original panel's 7,585 rows also include training origins and ineligible programs.
Do not interpret procedure repetitions or different targets as independent people or programs.

## Verification

The final executable checks use the standard short `.test-tmp` path from `pyproject.toml`:

```powershell
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run python -m mypy src/kasm
uv run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling --cov=src/kasm/reporting --cov=src/kasm/patient_journey --cov=src/kasm/program_prediction --cov-branch --cov-fail-under=80
uv run python -m coverage report --include="src/kasm/patient_journey/*" --fail-under=80 --precision=2
uv run python -m coverage report --include="src/kasm/program_prediction/*" --fail-under=80 --precision=2
git diff --check
```

Test-first fixtures cover cutoff/vintage drift, missing-versus-zero values, entry/gaps,
train-only preprocessing, all specified procedures, failure retention, error arithmetic,
queue selection before outcome availability, whole-program resampling, write-once output,
unsafe paths, tampered payloads, lineage and adapted follow-up preservation. Independent
reviews checked the scientific implementation as well as software behavior. The initial
research build verified nine sources without issues and all recorded stages completed.
All four figures were visually inspected. No dependency, container, released artifact or
application boundary changed; no Docker build or old-study refit was required.

At code revision `b301cb4`, all checks above passed: 74 packages checked, 145 Python files
formatted, 75 typed modules, and 1,069 tests passed with two existing host-restricted symlink
tests skipped. Branch-enabled coverage was 86.02% overall, 85.29% for patient journey and
90.37% for program prediction. The final documentation review checked 199 local links without
missing targets and passed `git diff --check`. The
[active plan](plans/0031-program-prediction-sprint.md#execution-record) records the initial
Windows long-path test failure, its shorter-path resolution, and independent scientific checks.
