# Data walkthrough slides

[Open the six-slide presentation](data-walkthrough.pptx).

These slides begin the author's data walkthrough. The questions asked during that walkthrough
will determine the eventual presentation structure. The earlier complete
[V2 follow-up deck](../v2-followup/interview.pptx) supplies the visual reference.
All walkthrough changes remain uncommitted until the author finishes the complete slideshow
and walkthrough pass.

1. **SRTR and the source data** introduces the publisher, public Excel program summaries,
   selected releases, measurement periods, publication dates and program identity.
2. **A small sample of the kidney workbook** makes the row grain and the outcome denominator
   concrete. The table shows four columns from three real records in July 2025 Table B7.
3. **Data quality and reproducibility** explains file identity, structural contracts, record
   checks, study timing and the records needed to reproduce an analysis. It distinguishes these
   safeguards from evidence that the source values or scientific design are correct.
4. **The workbook tables contain different programs** shows the first three program records in
   both July 2025 source tables. Row 4 refers to ALUA:TX1 in Table B7 and VANG:TX1 in the acceptance
   table. ALUA:TX1 appears on row 74 of the acceptance table. Matching code and type avoids a
   hypothetical positional-join error.
5. **SRTR's offer-acceptance ratio** explains the formula, expected acceptances, the +2 adjustment,
   a hypothetical calculation, the credible interval and the limits of interpretation.
6. **V1 methodology** covers the prediction target, simple comparisons and Ridge, time separation,
   training-only preprocessing and the frozen decision to retain persistence.

The example uses the first three program records in source order, which are also the first three
in composite-key order. They provide readable examples with different listing counts. Selection
does not depend on outcome size or model error. This is a schema illustration, with no claim of
representativeness or ranking. The columns are `CTR_CD`, `CTR_TY`, `SAL_N_C` and
`SAL_TOTFTX_C18`. Plain-language headings accompany the machine names. Only percentage display
precision changes: values round directly to two decimal places. The full source has 234 program
rows and 139 columns, excluding the two header rows.

One row describes one kidney program's July 1, 2022–June 30, 2023 listing group. The published
outcome is the percentage known alive with a functioning transplant 18 months after listing,
including living and deceased donation. Everyone in the original listing group contributes to
the denominator, including people who never receive a transplant. The July 8, 2025 publication
date is separate from those listing dates. These are published summaries without official risk
adjustment of this percentage. Unknown outcomes remain unknown.

The fourth slide is a source-record matching example. Table B7 contains 234 programs and the
offer-acceptance table contains 230, with 229 shared identifiers, five outcome-only identifiers
and one acceptance-only identifier. A difference of four in row counts does not mean four
unmatched records. The acceptance table describes calendar 2024 offers, whereas Table B7 describes
July 2022–June 2023 listings. Those same-release acceptance values are not eligible predictors for
that earlier V2 listing group. Identity matching and date eligibility are separate requirements.

## Suggested V1 app demonstration

Select **University of Alabama Hospital (ALUA) — Birmingham, AL** on **Program monitor**.
This is an illustrative teaching case chosen for its changing history and donor-group contrast.
It connects to the program already used in the source slides.

- Show overall OAR moving from 0.74 in 2017 to 2.00 in 2021, then 0.81 in 2023 and 1.11 in 2025.
  The latest SRTR 95% credible interval is 0.95–1.28, which includes 1.
- Scroll to the donor-stratum history and latest detail. In 2025, high-KDRI OAR is 0.41
  (0.15–0.81) and hard-to-place OAR is 0.16 (0.03–0.39). The overall figure does not capture
  every donor-group pattern. Hard-to-place overlaps KDRI groups, so these groups cannot be summed.
- Show **Next-calendar-year PSR projection**. Persistence carries 1.11 into calendar 2026.
  The prediction origin is July 7, 2026, with 51.5% of that year elapsed. It is a delayed-report
  nowcast; the app does not display the Ridge forecast band.
- Open **Model evaluation and methodology** to connect the displayed persistence value to the
  fixed bias rule. The model decision uses all evaluation programs, not this selected case alone.

These values come from the trusted V1 release through the same helpers used by the app.
The example cannot establish why the signal changed or whether a program's care improved.

## Source and authoring record

- [Slide text, full-precision excerpt and speaking notes](slides.json)
- [Presentation builder](build.mjs)
- [Package provenance](package-provenance.json)
- [SRTR download page](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/program-specific-reports-psr/)
- [Original source archive](https://srtr.hrsa.gov/Archives/PSRdownloads/csrs_tables_all/csrs_final_tables_2505all.zip)
- [Source manifest](../../../configs/data_sources.yaml) and
  [release-specific methods](../../../configs/patient_journey_v2/methodology.yaml)

The source member is `csrs_final_tables_2505_KI.xls`, sheet `Table B7`, Excel rows 3–5.
Archive SHA-256 is `359723874d5cdc2acaae98e0ebd3385f4a7d2f4dcc255e4dba90dba2a6036b8b`.
Workbook SHA-256 is `032584a0a1fe3df70c1f4cc9806f9a2756f8d378795534dae38a47d441422ac5`.
The source reader verified the cached archive and member before extraction. The existing component
parser also validated all 234 records and reconciled program identity with the same-release
directory. The date and field definitions follow the original V2 methodology ledger.

This is a small attributed documentation excerpt. It creates no analytical release, model,
comparison or change to the application. The authoring code uses the supplied desktop artifact
runtime, without adding a Python dependency or modifying `uv.lock`.

## Reproduce the slides

Run from the repository root with the supplied runtime. Choose a fresh build name. The builder
refuses an existing build directory and does not overwrite the checked-in deck or its reference.

```powershell
$env:RUNTIME_NODE_MODULES = 'C:/Users/chris/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:RUNTIME_PYTHON = 'C:/Users/chris/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PRESENTATIONS_SKILL_DIR = 'C:/Users/chris/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations'
$env:DATA_SLIDES_BUILD_NAME = 'data-slides-reproduction'
& 'C:/Users/chris/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' docs/presentation/data-walkthrough/build.mjs
```

Outputs appear under ignored `data/patient_journey_v2_followup/p4_build/<build-name>/`.
The `delivery` subdirectory contains the editable PowerPoint and provenance. The build directory
also contains the six rendered slides and a private validation receipt. The builder reads only
the attributed slide copy and existing presentation reference. It does not require the raw cache
or network. PPTX metadata and generated object IDs can vary between builds.

To recheck both excerpts against the immutable local cache, use the project environment:

```powershell
@'
import json
from pathlib import Path
from kasm.config import load_data_source_manifest
from kasm.data.parse import load_workbook_payload, read_workbook_sheets

manifest = load_data_source_manifest(Path("configs/data_sources.yaml"))
source = next(s for s in manifest.sources if s.release_code == "2505")
payload = load_workbook_payload(source, Path("data/raw/srtr"))
sheets = read_workbook_sheets(payload)
sheet = next(s for s in sheets if s.name == "Table B7")
content = json.loads(Path("docs/presentation/data-walkthrough/slides.json").read_text())
example = content["slides"][1]
header = list(sheet.rows[0])
actual = [[row[header.index(field)] for field in example["fields"]]
          for row in sheet.rows[2:5]]
assert actual == example["rows"], "The editorial excerpt differs from the verified source"
print("All 12 displayed source cells match the verified workbook.")
acceptance = next(s for s in sheets if s.name == source.sheet_name)
def keys(table):
    fields = list(table.rows[0])
    return [f'{row[fields.index("CTR_CD")]}:{row[fields.index("CTR_TY")]}'
            for row in table.rows[2:]]
b7_keys, b11_keys = keys(sheet), keys(acceptance)
actual_pairs = [[n + 3, b7_keys[n], b11_keys[n]] for n in range(3)]
assert actual_pairs == content["slides"][3]["rows"]
assert (len(b7_keys), len(b11_keys)) == (234, 230)
assert (len(set(b7_keys) & set(b11_keys)),
        len(set(b7_keys) - set(b11_keys)),
        len(set(b11_keys) - set(b7_keys))) == (229, 5, 1)
assert (b7_keys.index("ALUA:TX1") + 3, b11_keys.index("ALUA:TX1") + 3) == (4, 74)
print("All displayed row identities, counts and the correct ALUA match are verified.")
'@ | uv run python -
```

All six final slides were rendered and inspected, and the editable tables, native bullets, layout,
package structure and source values passed checks. Native PowerPoint rendering has not been
inspected. The inherited Helvetica Neue font triggers the same embedded-font decode warning
as the earlier deck in the artifact renderer; its rendered text remains legible. Check fonts on
the presentation machine during rehearsal. The author's walkthrough and rehearsal remain pending.

Public aggregate research prototype. Not clinical or regulatory decision support.
