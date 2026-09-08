# Reproduce the waiting-list case study offline

[Plan 0026](plans/0026-waiting-list-case-study.md) uses only the completed Plan 0025 records.
The [separate specification](specs/waiting-list-case-study-0026.md) fixes the descriptive
population, equations, years and example rule. No original study is refitted or overwritten.

## Required local inputs

Restore the exact completed Plan 0025 directory under
`data/research/waiting-list-0025/ad9a92cc0d20d407ab118f6b171e24bd9182a35557f149285a36035c45106cc4/`.
It contains `annual.json`, `comparisons.json`, `summary.json`, `qa.json`, `revisions.json`,
`provenance.json` and `complete.json`. These ignored files are not included in a fresh checkout.
The completion-marker fingerprint and fixed settings are in
[the configuration](../configs/waiting_list_case_study/experiment.json).

The loader checks the marker and all six payload hashes, exact count and publication schemas,
the original source/configuration/specification bindings, and annual and comparison accounting.
It retains unknown values and exclusions. A missing or mismatched file produces an error;
the command does not fetch sources or substitute another run. The workbook parser and the old
continuation gate are not called. Restore the trusted run; do not regenerate it merely to render
this case study.

## Generate the case study or a program brief

From the project root with the locked Python 3.12 environment installed:

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD '.uv-cache'
$env:MPLCONFIGDIR = Join-Path $PWD '.test-tmp/matplotlib'
uv sync --frozen --offline
uv run --offline python -m kasm.waiting_list_case_study.build
```

The command prints a new run directory beneath `data/research/waiting-list-case-study-0026/`.
Open `case_study.html` for the analytical brief, `supporting_tables.html` for complete tables,
and `program_1.html` through `program_3.html` for the mechanically selected examples. The three
main figures are also exported as SVG and PNG. All HTML uses local or embedded content and works
without a network connection. JSON files retain exact numerical results and selection details.

To use the same template for a composite program key in any comparison year 2023–2025:

```powershell
uv run --offline python -m kasm.waiting_list_case_study.build --program-key NYNS:TX1 --year 2025
```

This creates a separate write-once directory with `program_brief.html` and its calculated JSON.
Unsupported years, absent records, missing counts, unreconciled counts, discontinuous boundaries
or zero current starting registrations receive an explicit unavailable explanation. Zero remains
a reported count; missing counts display as “Not reported.” No program names or new source lookups
are needed to join the composite identity.

## Verify and regenerate

Delivered run: `ecf56720c3f3f0b26f68fad70f6fbe0e0c29635ecd7731499a7e9d847ecdce3e`,
built September 8, 2026 at 13:51:57 UTC. Its completion marker binds 18 payloads, including the
three figures in two formats and three selected program briefs. The directory contains about
1.10 MB. The [analytical explanation](waiting_list_case_study.md) retains the main findings in Git.

Every output, including provenance, has a SHA-256 fingerprint in the final completion marker.
Substitute the printed 64-character directory name:

```powershell
uv run --offline python -m kasm.waiting_list_case_study.build --verify-run RUN_ID
```

The run identity binds the original input fingerprints, new specification/settings, implementation
and request. An unchanged command refuses to overwrite an existing run. To reproduce from exactly
the same files, restore those files and the trusted input run in a separate checkout where the
output directory does not yet exist. Build time, Git context and HTML provenance will reflect that
build; calculation payloads and fixed selections reproduce. Never delete or overwrite completed
evidence to make room for a rerun. A changed implementation produces its own run identity.

This is a descriptive review of already-inspected public aggregate records. It is not clinical
or regulatory decision support. Program examples are illustrations, not a representative sample
or a ranking of quality. [Execution evidence](plans/0026-waiting-list-case-study.md#execution-evidence)
records verification and rendered inspection for the delivered revision.
