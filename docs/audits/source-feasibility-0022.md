# Source coverage and future-study feasibility audit

**Audit date:** 2026-09-08 UTC. **Scope:** [Plan 0022](../plans/0022-source-and-cleanup-audit.md).
No model was fitted or scored. This audit inspects source definitions, dates, field names and
one report-to-workbook match. It does not change either original study or authorize a new analysis.

The main finding is a source-date error in the retained V2 methodology: the July 2026 kidney
report covers listings **July 2023–June 2024**, not calendar 2023. Consequently, its listing
cohort does not overlap the July 2022–June 2023 cohort. A separately specified investigation can
consider another retrospective evaluation period. The original one-period comparison remains
the comparison actually performed; its configuration and result must remain preserved.

## 1. The newest cohort is resolved against a specific report

The PDF obtained from the [official kidney report download](https://srtr.hrsa.gov/reportapi/documents/psr/nynstx1_ki)
identifies North Shore University Hospital/Northwell Health, `NYNS:TX1`, kidney, release
July 7, 2026 and data available April 30, 2026. Printed page 9, Table B7, explicitly gives
`07/01/2023` through `06/30/2024`. Its 6-, 12- and 18-month columns use the same listing group.
The complete page was rendered and visually checked, including the donor headings and footnote.

The response was HTTP 200, `application/pdf`, 2,193,208 bytes. Its Content-Disposition names
`NYNSTX1KI202605PNEW.pdf`; SHA-256 is
`8d0d4a401de55e2ca7fd248168353bb27b0b9846d2f9496688122faaca5095a9`.
The download endpoint is current rather than immutable: require this fingerprint for this audit
copy and never assume the endpoint will continue returning the same release.

The immutable `2605` XLS passed the existing manifest's size/hash verification. Its matching
`NYNS:TX1` row has `SAL_N_C=302`, matching the PDF. All five deceased-donor 18-month component
fields and the two published functioning/receipt totals match the PDF at its one-decimal
precision. Eight checks, including the denominator, passed. This is a source-identity check,
not a model or outcome-association calculation. The XLS fingerprint remains
`8f357b6ed7a060f395fd1930e34e9e4aee4fe508d67f10b4167073eded834184`.

Table B7's workbook has `RELEASE_DATE` but **no listing-period date fields** in its machine
header or description row. The corresponding B2–B3 sheet also lacks its measurement dates.
Therefore, copying a date from the ledger into a parsed record and comparing it back to the
ledger cannot independently validate that date. A future source contract needs a fingerprinted,
release-bound PDF or equivalent authoritative definition alongside the workbook. A rolling
timeline is insufficient provenance for a historical cohort.

The retained V2 ledger's `2023-01-01`/`2023-12-31` and overlap explanation are wrong for this
source. Its `2025-06-30` follow-up end is also inconsistent with the newly verified listing
group: the final listing's nominal 18-month point is in December 2025. The future contract must
verify and record the precise follow-up convention instead of silently modifying the original.

## 2. All nine pinned workbooks

Every workbook was opened only after the existing loader verified the source/archive/member
fingerprints in [the source manifest](../../configs/data_sources.yaml). Each outcome sheet has
139 columns, with identical ordered machine names and descriptions across these nine releases.
Each `Tables B2-B3 Center` sheet has 191 columns, but age categories change as described below.
Row counts exclude the two header rows and are source records, not eligible model populations.

| Release | Public availability retained from manifest | Listing cohort | Outcome / B2–B3 rows | Date evidence in this audit |
|---|---|---|---:|---|
| `1808` | October 2018 | July 2015–June 2016 | 236 / 239 | Retained ledger; old direct PDF link unavailable |
| `1905` | July 2019 | July 2016–June 2017 | 239 / 241 | Independently located kidney PDF, printed page 8 |
| `2006` | August 2020 | July 2017–June 2018 | 238 / 238 | Retained ledger; old direct PDF link unavailable |
| `2105` | July 2021 | July 2018–June 2019 | 235 / 237 | Kidney PDF, printed page 9 |
| `2205` | July 2022 | July 2019–June 2020 | 232 / 234 | Independently located kidney PDF, printed page 9 |
| `2305` | July 6, 2023 | July 2020–June 2021 | 233 / 236 | Kidney PDF, printed page 9 |
| `2405` | July 9, 2024 | July 2021–June 2022 | 236 / 234 | Retained ledger; its cited PDF is kidney-pancreas |
| `2505` | July 8, 2025 | July 2022–June 2023 | 234 / 234 | Kidney PDF, printed page 9 |
| `2605` | July 7, 2026 | **July 2023–June 2024** | 229 / 234 | Downloaded, hashed, rendered and matched to pinned XLS |

Historical sanity checks used the release-bound [1905 kidney report](https://www.srtr.org/PDFs/072019_release/pdfPSR/NYUCTX1KI201905PNEW.pdf),
[2105 kidney report](https://www.srtr.org/PDFs/062021_release/pdfPSR/TXMHTX1KI202105PNEW.pdf),
[2205 kidney report](https://srtr.org/PDFs/062022_release/pdfPSR/CACLTX1KI202205PNEW.pdf),
[2305 kidney report](https://srtr.org/PDFs/062023_release/pdfPSR/MNUMTX1KI202305PNEW.pdf)
and [2505 kidney report](https://www.srtr.org/PDFs/072025_release/pdfPSR/NYNSTX1KI202505PNEW.pdf).
These corroborate the original fitting/evaluation dates. Historical PDF text was available to
the web reader, while several direct legacy downloads returned 404; no newly verified local
hash is claimed for those historical PDFs. Before a new analytical release, obtain and bind
the remaining historical PDF copies. The unavailable `1808`/`2006` dates are not newly proved
by successful workbook parsing. The `1905` ledger originally cited a kidney-pancreas PDF;
this audit adds kidney-specific corroboration without editing that frozen ledger.

## 3. Deceased-donor receipt is available as a defined component sum

All nine sources contain these center fields for each `h` in `6`, `12`, `18`:

| Field | Published category within deceased-donor transplants |
|---|---|
| `SAL_CTXFNC_C{h}` | Functioning transplant, alive |
| `SAL_CTXRE_C{h}` | Failed, retransplanted, alive |
| `SAL_CTXFAIL_C{h}` | Failed, alive, not retransplanted |
| `SAL_CTXDIED_C{h}` | Died |
| `SAL_CTXUNK_C{h}` | Post-transplant status yet unknown |

The five mutually exclusive percentages share `SAL_N_C`, the **original listing group**, as
denominator. Their sum represents reported removal for deceased-donor transplant by the
specified time, regardless of subsequent graft status. It must be labeled a derived sum of
published components, not a separately published deceased-donor total. Receipt remains known
when the subsequent graft status is unknown; no health outcome is imputed. All five categories
are needed. The two categories examined in P3 alone do not establish receipt.

The workbook also publishes `SAL_TOTTX_C{h}` for receipt from either donor type. The analogous
five `SAL_LTX...` living-donor fields permit a future rounding-aware reconciliation of both
donor sums against this published total. Do not replace the original functioning-transplant
target, turn unknown/suppressed components into zero, or remove living-donor candidates from
the listing denominator. No donor sums across programs or predictive comparisons were run here.

The [SRTR Table B7 methods](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/technical-methods-for-the-program-specific-reports/)
define transplant receipt using waitlist removal codes and distinguish it from post-transplant
status. Table B8–B9 is not an interchangeable target: it uses a longer listing cohort and
excludes removals for living-donor transplant, changing both timing and population.
Choosing 6 or 12 months changes the question; those columns arrive in the same release as
18 months and do not independently provide earlier publication or more evaluation periods.

## 4. Earlier candidate characteristics have useful, limited continuity

The center sheet has separate `_NEWC2` fields for new registrations and `_ALLC2` for everyone
listed at the period end. These populations must stay distinct. The July 2026 PDF's printed
page 3 confirms that new registrations concern January–December 2025, while all registrations
are measured on December 31, 2025. Earlier-report characteristics may be predictors when their
measurement and publication both precede the relevant cutoff; target-cohort characteristics
from a later report must not be treated as information known when forecasting began.

Examples of fields present across all nine pinned sources are:

- `WLC_N_NEWC2`: number of new registrations, the candidate-mix denominator;
- `WLC_BO_NEWC2`, `WLC_BA_NEWC2`, `WLC_BB_NEWC2`, `WLC_BAB_NEWC2`: blood-type percentages;
- `WLC_PRA9_NEWC2`, `WLC_PRA79_NEWC2`, `WLC_PRA80_NEWC2`, `WLC_PRAU_NEWC2`:
  source-labeled PRA groups 0–9, 10–79, 80+, and unknown;
- `WLC_PTXY_NEWC2`, `WLC_PTXN_NEWC2`, `WLC_PTXU_NEWC2`: prior transplant yes/no/unknown;
- `WLC_KIDIA_NEWC2`, `WLC_KIHYP_NEWC2`: diabetes and hypertensive nephrosclerosis categories.

Presence is not a complete clinical-definition audit. In particular, verify the release-specific
meaning of the source's PRA labels before relabeling them as calculated PRA or combining eras.
The shared sheet also contains liver, heart and other-organ fields; an all-column import is
inappropriate. Earlier aggregate characteristics do not produce patient-level risk adjustment.

There is actual schema drift despite the unchanged 191-column count: `1808`/`1905` contain
`WLC_A65P_NEWC2` (65+) and `WLC_AU_NEWC2` (age other). From `2006`, these become
`WLC_A69_NEWC2` (65–69) and `WLC_A70P_NEWC2` (70+), with parallel all-registration changes.
Use a small explicitly justified stable subset or a separately documented harmonization;
do not silently equate these fields. This audit verifies schema availability, not per-feature
completeness, range validation or usable program counts for a future analysis.

## 5. Earlier archives and the number of possible time splits

The [official archive menu](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/program-specific-reports-psr/)
lists national workbooks back to July 2012. Four earlier all-organ archives were fetched into
the isolated audit directory and checked for HTTP status, declared size, content type, archive
paths, unique kidney member, XLS signature and first-observed archive/member SHA-256. They are
audit inputs, not approved production pins. The kidney files use names such as
`csrs_final_tables_1707KI.xls`, without the later underscore before `KI`.

| Archive / public label | Bytes | SHA-256 | Verified scope |
|---|---:|---|---|
| `1506` / June 2015 | 9,084,610 | `d382e5d733bfa4762b52bfdf96d2ffa7e98dc3ab920544c988d1bf9e360857c9` | B6 outcome and B2–B3 fields; no OAR sheet |
| `1606` / June 2016 | 8,985,399 | `c52d08deee84b50b71eac82d54aa317eed4df83bc9a5253b81088c62a1dbd026` | B6 outcome and B2–B3 fields; no OAR sheet |
| `1701` / January 2017 | 7,401,284 | `1709a018db9ea1a90c7ed411d1c237f0734604d6bdec11ade0c16e8bd47e9aca` | B6 outcome and B2–B3 fields; no OAR sheet |
| `1707` / July 2017 | 7,094,082 | `d4f3f586f07dc0586c08f0d83c7aa23571d44f541bd1c7d3c7a9dac1543f0419` | Same outcome/mix fields, plus first OAR cohort January–December 2016 |

The 2015/2016 headers contain leading whitespace and a blank center-name header; composite
`CTR_CD`/`CTR_TY` identity remains present. The 2017 B6 schema equals the pinned outcome schema.
All five deceased-donor categories and all three follow-up times are present. July 2017 OAR
uses `OA_HARDTOPLACE_*`, described as more than 100 offers; later workbooks use
`OA_HARDTOPLACE100_*`. Any reuse needs an explicit reviewed mapping and source-drift tests.

| Separate future design | Temporally possible evaluations | Remaining gate |
|---|---|---|
| Nine pinned sources, corrected `2605` dates | `2205→2505`, then `2305→2605`: **two**, instead of the original one | New contract and source-bound date ledger; preserve original result |
| Add July 2017 as `1707→2006` training data | Also `2006→2305` and `2105→2405`: **four in total** | Bind 2017 predictor definitions and `2006` target PDF; validate population, transformations and all inputs before fitting |
| Longer history/mix investigation using pre-2017 archives | Potentially earlier training/evaluation periods | No additional count asserted: earlier listing dates, full availability and comparability are not yet verified |

For the first row, July 2022 can train on `1905→2205`; July 2023 can additionally train on
`2006→2305`, whose outcome is then public. For the second row, the outcome of July 2017–June
2018 listings in `2006` would be public by the August 2020 prediction origin and by July 2021.
This adds two evaluation origins without pretending that an unpublished training label was
available earlier. The four-count statement is a metadata-based feasibility result conditional
on the stated source and eligibility checks, not four completed evaluations. It uses the
original allowance for an August 2020 origin one month after July-start listings; a stricter
before-listing design requires its own date matrix and may have fewer usable periods.

Earlier history/mix data cannot automatically enter an acceptance comparison: OAR is absent
from the inspected pre-July-2017 sources. Do not pool January and July outcome cohorts as
independent years. Further archive breadth should follow a defined question rather than become
an unrestricted search for a favorable result.

## 6. Exposure status and reproduction

All nine pinned sources were parsed in the original project. Their functioning-transplant
outcomes are already exposed, including `2605`, even though it was excluded from modeling.
This audit additionally viewed a small number of source values to bind the July 2026 PDF and
XLS. The new receipt/mix study is motivated by earlier inspected results; it is exploratory
even if some component values have not previously been analyzed. Earlier archives were inspected
for headers and metadata here, without outcome summaries or scores. Their complete prior human
exposure is unknown; no archive is designated an untouched holdout by this audit.

Local evidence is under ignored `data/audit-0022/`: `pinned-metadata.json`,
`earlier-metadata.json`, `2605-pdf-workbook-binding.json`, the PDF and its rendering, per-download
HTTP/hash manifests, and the inspection/downloader scripts. The scripts do not import modeling
code. Pinned inspection runs with the existing project environment:

```powershell
.venv/Scripts/python.exe data/audit-0022/inspect_sources.py
.venv/Scripts/python.exe data/audit-0022/inspect_earlier.py
pdftoppm -f 13 -singlefile -scale-to 1500 -png data/audit-0022/nynstx1_ki.pdf data/audit-0022/2605-table-b7
```

For a fresh checkout, the inspection is reproducible from `load_data_source_manifest` and
`load_workbook_payload` in the existing package: load each manifest entry, open verified bytes
with `xlrd.open_workbook(..., on_demand=True)`, and record sheet rows 0/1 plus `RELEASE_DATE`.
Do not read or summarize measurement columns for a metadata audit. Compare the named PDF's
Table B7 identity, listing dates and `SAL_N_C`; the eight explicit binding fields are listed
above. Earlier archive URLs follow the observed menu's
`https://srtr.hrsa.gov/Archives/PSRdownloads/csrs_tables_all/csrs_final_tables_{code}all.zip`.
Require the audit fingerprints above before reusing those copies. The ignored scripts are
working evidence rather than a supported production workflow.

The complete execution and repository checks belong to Plan 0022. No original source hash,
configuration, model output, analytical bundle, application or presentation was rewritten by
this source audit.
