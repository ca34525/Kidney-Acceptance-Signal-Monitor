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

Raw SRTR inputs are immutable local files and are ignored by Git. Once acquired, place each
download under `data/raw/srtr/` using the filename from its manifest URL, then verify it:

```powershell
uv run kasm data verify-cache
```

The verification command is offline: it checks the pinned file size, SHA-256, file type, and,
for ZIP sources, the expected archive member and its pinned size and SHA-256.

