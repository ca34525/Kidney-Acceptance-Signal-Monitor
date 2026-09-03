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
