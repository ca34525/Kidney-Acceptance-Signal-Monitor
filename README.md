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
```

`data sync` is the networked preflight/maintenance path. It skips valid existing files, refuses to
overwrite an invalid cache entry, downloads through a temporary file, and publishes a source only
after its complete pinned contract passes. `data verify-cache` is offline and is the starting point
for release reproduction; it checks file size, SHA-256, file type, and, for ZIP sources, the
configured archive member with its pinned size and SHA-256.
