# Table B1 source evidence for Plan 0025

Checked September 8, 2026 UTC, before comparative summaries. This audit concerns source
identity and counting rules for the [waiting-list screen](../specs/waiting-list-0025.md).
It does not evaluate transplant performance or amend any completed study.

Seven pinned releases have independently verified annual periods and matching report counts.
They provide calendar years 2017–2025 without a gap. The `1808` and `2006` workbooks remain
available and their headers were inspected, but their report evidence could not be recovered
at the existing archive boundary. Their annual suffixes are unresolved and those releases
supply no analytical records. This does not prevent use of the other seven releases.

## Source binding and annual periods

Every workbook was opened with `load_workbook_payload`, which verifies the pinned download
and archive-member fingerprints before returning XLS bytes. Table B1 has the same 60 machine
headers and descriptive labels in all nine workbooks. Its 22 annual count fields contained
47,168 numeric cells in total, with no blank, error or text-valued cells. This observation does
not authorize a future parser to convert missing values to zero.

The two count suffixes are `NC1` for the first printed calendar year and `NC2` for the second.
The following mapping comes from the report's Table B1 column dates, independently joined to
its workbook by `(CTR_CD, CTR_TY)`. All 22 annual counts matched exactly for each listed
program: **154 checked report-to-workbook values**. Each annual period starts January 1 and
ends December 31 of the listed year. No date was inferred from the offer cohort or V2 ledger.

| Release; report link | Table B1 rows | NC1 / NC2 years | Matched program; PDF page |
|---|---:|---|---|
| [1808](https://www.srtr.org/PDFs/102018_release/pdfPSR/ILLUTX1KI201808PNEW.pdf) | 242 | Unresolved; excluded | Report unavailable |
| [1905](https://www.srtr.org/PDFs/072019_release/pdfPSR/NYUCTX1KI201905PNEW.pdf) | 242 | 2017 / 2018 | `NYUC:TX1`; 6 |
| [2006](https://www.srtr.org/PDFs/082020_release/pdfPSR/OHTCTX1KI202006PNEW.pdf) | 239 | Unresolved; excluded | Report unavailable |
| [2105](https://www.srtr.org/PDFs/062021_release/pdfPSR/TXMHTX1KI202105PNEW.pdf) | 239 | 2019 / 2020 | `TXMH:TX1`; 8 |
| [2205](https://srtr.org/PDFs/062022_release/pdfPSR/CACLTX1KI202205PNEW.pdf) | 236 | 2020 / 2021 | `CACL:TX1`; 8 |
| [2305](https://srtr.org/PDFs/062023_release/pdfPSR/MNUMTX1KI202305PNEW.pdf) | 238 | 2021 / 2022 | `MNUM:TX1`; 8 |
| [2405](https://www.srtr.org/PDFs/072024_release/pdfPSR/NYNSTX1KI202405PNEW.pdf) | 236 | 2022 / 2023 | `NYNS:TX1`; 8 |
| [2505](https://www.srtr.org/PDFs/072025_release/pdfPSR/NYNSTX1KI202505PNEW.pdf) | 237 | 2023 / 2024 | `NYNS:TX1`; 8 |
| [2605](https://srtr.hrsa.gov/reportapi/documents/psr/nynstx1_ki) | 235 | 2024 / 2025 | `NYNS:TX1`; 6 |

PDF page numbers are one-based; each table is printed page 2. Row counts exclude the two
header rows and differ from the offer-table row counts in the original manifest. The Table B1
dates cover the full calendar years in the COVID-era reports; exclusions printed in other
tables must not be imported into this table.

The earliest verified release is `1905` for 2017–2018, `2105` for 2019–2020, then `2205`,
`2305`, `2405`, `2505` and `2605` respectively for 2021–2025. Later appearances of a year
are revision evidence only. Calendar year 2016 has no independently verified pinned source.

## Fields, units and category boundaries

The identity fields are `CTR_CD` and `CTR_TY`; `ENTIRE_NAME`, `RELEASE_DATE` and `ORG` are
metadata. Append `_NC1` or `_NC2` to each prefix below to obtain an annual program count.
The additional `_PCZ`, `_PRZ` and `_PUZ` fields are program, region and national comparisons
for the second year, expressed per 100 registrations present at that year's start. They are
not extra count categories and do not enter annual reconciliation.

| Prefix | What the count represents |
|---|---|
| `WLA_ST` | Registrations present at the year's start |
| `WLA_ADDCEN` | New registration events at the reporting program |
| `WLA_END` | Registrations present at the year's end |
| `WLA_REMTFER` | Removal to transfer to another program |
| `WLA_REMTXL` | Removal coded as living-donor transplant at this program |
| `WLA_REMTXC` | Removal coded as deceased-donor transplant at this program |
| `WLA_REMDIED` | Removal coded as death |
| `WLA_REMTXOC` | Removal because transplant occurred at another program |
| `WLA_REMDET` | Removal coded as deterioration |
| `WLA_REMREC` | Removal coded as recovery |
| `WLA_REMOTH` | Other recorded removal reasons |

The eight removal rows are parallel removal-reason categories in every verified Table B1.
There is no count-valued removal-total row to add to those components. The source's reason-code
description and table structure support treating them as mutually exclusive **removal events**;
the screen must additionally check the exact count identity for every included program-year.
They do not establish mutually exclusive people: registrations and removals can recur for the
same person. The source does not provide a separate medically-unsuitable field here, so no
finer category should be reconstructed from `WLA_REMOTH`.

For this screen, transplant removals at the reporting program are `WLA_REMTXL + WLA_REMTXC`.
`WLA_REMTXOC` remains separate. A transfer records departure from the reporting program;
the workbook gives no linked destination registration. A transplant elsewhere similarly
removes a registration from this list while the procedure belongs elsewhere. Neither category
can be assumed to cancel across a selected set of programs. The footnote in every verified
report distinguishes transplant removal coding from procedure counts.

[SRTR's current Table B1 methods](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/technical-methods-for-the-program-specific-reports/)
define the beginning count, repeated registration/removal events, and the end-count identity.
They include listed candidates regardless of whether they arrived during the year; a living-donor
recipient who was never listed is outside these counts. Those methods explain the present
concept, while the historical reports above establish the release-specific periods and rows.

Publication values and month/day precision remain exactly as pinned in
[`configs/data_sources.yaml`](../../configs/data_sources.yaml). A day printed inside a report
does not replace a month-only manifest value. All eight historical workbook release rows carry
one Excel date value per release; this metadata does not itself establish annual column dates.

## Evidence retention and limits

[`configs/waiting_list/sources.json`](../../configs/waiting_list/sources.json) records the nine
inventories, exact periods, all 154 independently transcribed binding values, source-manifest
and workbook hashes, matched keys, URLs, exclusions and evidence fingerprints.
The six historical B1 captures are ignored files named
`data/research/waiting-list-0025/source-evidence/{release}-table-b1-web.txt`. Each includes
the official URL, report header, page/line locators, annual columns, all count rows and footnote.
They are cached web-reader text, **not original PDF bytes**; `report_sha256` is therefore null
and `evidence_sha256` fingerprints the captured UTF-8 text. Historical PDF screenshots were
unavailable, so their original visual layout was not rechecked.

The original `2605` PDF was reused from `data/audit-0022/nynstx1_ki.pdf` without modification.
Its 2,193,208 bytes match SHA-256
`8d0d4a401de55e2ca7fd248168353bb27b0b9846d2f9496688122faaca5095a9`.
Its Table B1 page was extracted to `2605-table-b1-pdf.txt`, rendered with Poppler and visually
inspected, including column headings and the transplant-removal footnote. The URL is a rolling
download endpoint; the byte fingerprint, report date and matched counts identify this release.
The older receipt-study captures remain untouched and are not substitutes for these B1 pages.

Offline reproduction reads the ledger, checks each evidence file against `evidence_sha256`,
opens each pinned workbook through `load_workbook_payload`, and checks the 60 headers, Table B1
row counts and each `report_counts` value at `matched_program_key`. The source gate never uses
unverified year suffixes. Full program coverage, revisions, consecutive-year boundaries and
annual accounting are separate parser/calculation checks; this source audit makes no claim
that those later checks have passed.
