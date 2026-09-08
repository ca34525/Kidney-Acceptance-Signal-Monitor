# Plan 0030 — Explain V1 records and fields

**Status:** complete, D0–D3. **Date:** September 8, 2026.
**Authorization:** the user requests a data dictionary limited to V1 to prepare a personal
walkthrough, following the explanatory style of the current data-walkthrough deck.

## Purpose and acceptance

Create a readable reference that starts with what one record represents, then connects
SRTR's source fields to the historical signal table and the annual prediction inputs.
Use ordinary language, exact field names, units, dates, missing-value meanings and a
verified ALUA example. Cover the original 17 model inputs and identify the later fitted
adjustment separately. Distinguish published values, derived inputs and predictions.

| Item | Acceptance evidence |
|---|---|
| D0 Record the scope | This plan precedes authoring. Existing V1 specifications and configurations remain authoritative; no schema, scientific rule or result changes. |
| D1 Write the dictionary | Source-to-output mappings agree with the parser, feature builder and saved release schemas. Explain row identity at each stage, all original model inputs, units, null handling, publication precision and model eligibility. A real example names its source period and release. |
| D2 Make it usable | Link the dictionary from the project guide and current walkthrough README. Put the first reading route and concrete source example ahead of the detailed field reference. |
| D3 Verify and close | Validate the existing release before reading its example values; review field coverage, formulas, links and `git diff --check`. Record the commands and results here. |

Documentation-only exception: no software behavior changes, so a failing software test,
Python suite, model fit, replay, source refresh or artifact rebuild would not exercise this
change. Validate existing artifacts read-only and review content instead. No dependency,
presentation binary, source pin or release artifact change is planned. An architectural
decision is unnecessary because this documents existing meaning and behavior.

## Evidence and handoff

- D0: recorded the requested scope and acceptance before writing the dictionary.
- D1: [the dictionary](../v1-data-dictionary.md) starts with the source row and actual ALUA
  calendar-2024/2025 values, then follows its input–outcome pairs and persistence error.
  All 22 signal fields, all 31 model-panel fields and the exact ordered 17 model inputs
  were checked against the implementation and released schemas. Two independent content
  reviews checked the source mapping/provenance and the model/timing meanings.
- D2: linked from the project guide and current walkthrough README. The first reading
  route is sections 1–3; detailed field tables follow. No presentation binary changed.
- D3: `validate_release_bundle(Path('artifacts/release'))` passed for all 12 payloads,
  1,229,848 bytes, content SHA-256
  `1de89083ceebfda9afaf2d6b1c6ba3f1e6d0c1a1da16df9d09d994c4ec3581ad`.
  Read-only Python checks matched the ALUA counts, ratios, publication dates and eligibility
  flags, verified the displayed log/error calculations, and confirmed dictionary coverage
  against `PROGRAM_SIGNALS_SCHEMA`, `MODEL_PANEL_SCHEMA` and `MODEL_FEATURE_COLUMNS`.
  Local link targets, new-file whitespace and `git diff --check` passed. SRTR's linked
  professional FAQ and technical methods opened successfully for definition review.
- No Python suite, fit, replay, source refresh, artifact rebuild or new analysis was run.
  The dictionary's worked arithmetic illustrates saved published records; it does not
  establish fresh validation or complete the author's personal walkthrough/rehearsal.

### Reproduce the source example without rebuilding

Run from the repository root using the existing supported environment. This validates the
saved release and reads only ALUA's overall 2024/2025 rows and corresponding panel records:

```powershell
@'
from pathlib import Path
from math import log
import pyarrow.parquet as pq
from kasm.reporting.artifacts import validate_release_bundle

bundle = Path('artifacts/release')
print(validate_release_bundle(bundle))
for filename, year_field in [
    ('program_signals.parquet', 'cohort_year'),
    ('model_panel.parquet', 'feature_cohort_year'),
]:
    rows = pq.read_table(bundle / 'processed' / filename).to_pylist()
    for row in rows:
        if row['program_key'] != 'ALUA:TX1' or row[year_field] not in (2024, 2025):
            continue
        if 'offer_group' in row and row['offer_group'] != 'overall':
            continue
        print(filename, row)
print('Ratio reconstruction check:', (185 + 2) / (217.53 + 2))
print('Persistence absolute ratio error:', abs(0.85 - 1.11))
print('Persistence absolute log error:', abs(log(0.85) - log(1.11)))
'@ | uv run --no-sync python -
```
