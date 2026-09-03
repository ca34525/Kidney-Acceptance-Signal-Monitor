# Kidney Acceptance Signal Monitor

An offline-capable, public-data quality-improvement prototype for reviewing longitudinal
kidney transplant program offer-acceptance signals. The scientific and product requirements
are defined in `SPEC.md`; implementation order is defined in `PLAN.md`.

## Development

Python 3.12 and `uv` are required.

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run mypy src/kasm
uv run pytest -q
```

Raw SRTR inputs are immutable local files and are ignored by Git. Acquire any missing pinned
sources explicitly, then verify the cache offline:

```powershell
uv run kasm data sync
uv run kasm data verify-cache
uv run kasm data inspect-sources
uv run kasm data build
```

`data sync` is the networked preflight/maintenance path. It skips valid existing files, refuses to
overwrite an invalid cache entry, downloads through a temporary file, and publishes a source only
after its complete pinned contract passes. `data verify-cache` is offline and is the starting point
for release reproduction; it checks file size, SHA-256, file type, and, for ZIP sources, the
configured archive member with its pinned size and SHA-256.

`data inspect-sources` stays offline, re-verifies every input, opens only the configured XLS or ZIP
member, locates the versioned offer-acceptance sheet by name and machine fields, and validates the
pinned source row/column counts plus the center-level scientific invariants. Its JSON inventory is
the M1 evidence that all nine source eras reshape into the five P0 offer groups without silently
accepting schema drift.

`data build` also stays offline. It reparses the verified cache and atomically publishes
`data/processed/program_signals.parquet`, `data/processed/model_panel.parquet`, and
`data/processed/qa_report.json`. The long signal table uses the current `Tiers` directory only for
display fields. The model panel aligns each feature cohort to the next calendar year, retains
program exits as missing targets, and materializes analytic, first-observed, and public-forecast
eligibility. The QA report records source counts, raw-to-normalized cohort dates, annual additions
and closures, missing subgroup OARs, and nonblocking publication-rounding diagnostics. These
canonical build products remain ignored until the approved release-bundle step.

The temporal backtest likewise runs entirely from the trusted model panel:

```powershell
uv run kasm model backtest
```

This command enforces the exact predictor allowlist, constructs expanding target-year folds, and
writes paired neutral, persistence, and historical-mean predictions under `data/modeling/`. It
also fits median imputation, standardization, and ridge inside each training fold; selects alpha
from the fixed grid using year-balanced 2021–2023 log-OAR MAE and the prespecified 1% larger-alpha
tie rule; then evaluates the selected alpha through held-out target year 2024. Ridge selection,
predictions, metrics, and the pre-replay candidate-gate decision are separate deterministic
artifacts. The panel read is filtered through 2024, and every artifact records that the 2025 frozen
replay remains unevaluated.

On the verified nine-release panel, alpha 10 was selected. Ridge improved over persistence in all
four pre-replay years and produced 5.47% year-balanced log-OAR MAE skill, so it passed the
prespecified pre-replay candidate gate. This is model-development evidence only: activation is
still undecided, `forecast_activation_attempted` remains unset, and no 2025 result has been used.

## Historical walking skeleton

The current Streamlit slice reads only the trusted precomputed Parquet files. It provides
composite-key program selection, published overall OAR history with SRTR credible intervals,
latest source-volume context, donor-stratum values, explicit missing states, and the materialized
public-forecast eligibility state. Model evaluation and any eligible projection remain later
milestones.

Build the local artifacts first, then start the offline view:

```powershell
$env:KASM_ARTIFACT_DIR = "$PWD/data/processed"
uv run streamlit run app/streamlit_app.py
```

Once the artifacts exist, the critical view does not require network access.
