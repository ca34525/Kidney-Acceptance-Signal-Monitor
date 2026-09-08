# Release-specific source evidence for Plan 0023

**Checked:** September 8, 2026 UTC. **Scope:** source definitions, periods and workbook identity
for the separately authorized [receipt study](../plans/0023-deceased-donor-receipt-study.md).
No model was fitted or scored during this audit. Original study ledgers and outputs are preserved.

Seven kidney releases have independent evidence for their listing dates. The 2018 and 2020
reports remain unavailable and must be excluded from this study's outcome history and matched
training pairs before comparison errors are examined. The verified sources permit the proposed
`2205→2505` and `2305→2605` evaluation origins, with `1905→2205` available as an earlier training
pair. Publication and predictor cutoffs still require separate panel validation.

## Evidence and its limits

Six historical reports were read through the web reader's cached extraction of release-specific
official SRTR PDF URLs. Exact returned text, including source URL, page/line locators, report
headers and complete relevant table sections, is saved under the ignored
`data/receipt-study/source-research/` directory. These are **hashes of captured extracted text**,
not hashes of the original PDF bytes. Direct historical downloads returned HTTP 404; attempts
to obtain PDF screenshots returned cache misses. Their original visual layout could not be
rechecked. This limitation is explicit rather than treating a successful text read as a successful
PDF download.

The `2605` report is the existing verified PDF from Plan 0022. Its original HTTP 200 response was
`application/pdf`, 2,193,208 bytes, with Content-Disposition `NYNSTX1KI202605PNEW.pdf` and SHA-256
`8d0d4a401de55e2ca7fd248168353bb27b0b9846d2f9496688122faaca5095a9`.
The [current download endpoint](https://srtr.hrsa.gov/reportapi/documents/psr/nynstx1_ki) is rolling;
only that fingerprint identifies the audited release. PDF pages 13–16, printed pages 9–12,
were rendered and visually inspected here, including all donor headings and table footnotes.

The independent audit script `data/receipt-study/source-research/bind_evidence.py` reads dates
and values from the captured report text, opens each kidney workbook through the existing
verified source loader, and joins using its report's `(CTR_CD, CTR_TY)`. All **91 checks** passed:
seven programs, each with the original listing denominator, all ten living/deceased-donor
18-month components, and two published transplant totals. Percentages agree within the PDF's
one-decimal display rounding; denominators agree exactly. The full values, workbook hashes,
file sizes, and source-text fingerprints are in the write-once `source-bindings.json` beside
the source copies. This is a release identity check, not a measure of prediction accuracy.

## Independently verified periods

Each listing period below uses the original newly listed group as its denominator. The report
measures each candidate's status 18 months after that candidate was listed. A report's source
header may give a publication day even when the pinned manifest retains month precision; this
audit does not amend the manifest's public-availability representation.

| Release and official source | Matched program; listing N | Listing period in B6/B7 | Time-to-transplant listing period; stated censor date |
|---|---|---|---|
| [1905](https://www.srtr.org/PDFs/072019_release/pdfPSR/NYUCTX1KI201905PNEW.pdf) | `NYUC:TX1`; 145 | 2016-07-01–2017-06-30 | 2013-01-01–2018-06-30; 2018-12-31 |
| [2105](https://www.srtr.org/PDFs/062021_release/pdfPSR/TXMHTX1KI202105PNEW.pdf) | `TXMH:TX1`; 485 | 2018-07-01–2019-06-30 | 2015-01-01–2020-06-30; 2020-12-31 |
| [2205](https://srtr.org/PDFs/062022_release/pdfPSR/CACLTX1KI202205PNEW.pdf) | `CACL:TX1`; 36 | 2019-07-01–2020-06-30 | 2016-01-01–2021-06-30; 2021-12-31 |
| [2305](https://srtr.org/PDFs/062023_release/pdfPSR/MNUMTX1KI202305PNEW.pdf) | `MNUM:TX1`; 229 | 2020-07-01–2021-06-30 | 2017-01-01–2022-06-30; 2022-12-31 |
| [2405](https://www.srtr.org/PDFs/072024_release/pdfPSR/NYNSTX1KI202405PNEW.pdf) | `NYNS:TX1`; 230 | 2021-07-01–2022-06-30 | 2018-01-01–2023-06-30; 2023-12-31 |
| [2505](https://www.srtr.org/PDFs/072025_release/pdfPSR/NYNSTX1KI202505PNEW.pdf) | `NYNS:TX1`; 278 | 2022-07-01–2023-06-30 | 2019-01-01–2024-06-30; 2024-12-31 |
| [2605](https://srtr.hrsa.gov/reportapi/documents/psr/nynstx1_ki) | `NYNS:TX1`; 302 | 2023-07-01–2024-06-30 | 2020-01-01–2025-06-30; 2025-12-31 |

The outcome is printed Table B6, page 8, in `1905`, and Table B7, page 9, from `2105` onward.
The time-to-transplant percentile is B9, page 11, in `1905`, and B10, page 12, afterward.
B7/B8 in the old layout and B8/B9 in the new layout instead describe receipt within three years
for a three-year listing group: 2013–2015, 2015–2017, 2016–2018, 2017–2019, 2018–2020,
2019–2021 and 2020–2022 respectively. They are not the same cohort or denominator as B6/B7.

The source does **not** state an exact day-conversion convention for the 18-month outcome.
It establishes the horizon and listing dates. The study can use December 31 of the year after
listing ends as a conservative latest-date bound around the final candidate's nominal 18-month
time. For `2605`, that bound is December 31, 2025. It must be labeled an audit bound, not a
source-reported B7 censor date. The separate B9/B10 censor dates above are explicitly printed.

The [1808 legacy source](https://www.srtr.org/PDFs/102018_release/pdfPSR/ILLUTX1KI201808PNEW.pdf)
and [2006 legacy source](https://www.srtr.org/PDFs/082020_release/pdfPSR/OHTCTX1KI202006PNEW.pdf)
both returned HTTP 404 on direct requests and were unavailable to the web reader. Alternative
known program paths did not recover `2006`; the public preview host returned HTTP 503. The
old ledger alone is insufficient evidence for either release. These exclusions follow source
availability, not comparative errors.

## Donor accounting, precision and missing values

The five fields in each donor group share `SAL_N_C`, the original listed-candidate count.
The exact 18-month fields verified in every included workbook are:

| Published status | Deceased donor | Living donor from the waiting list |
|---|---|---|
| Functioning transplant, alive | `SAL_CTXFNC_C18` | `SAL_LTXFNC_C18` |
| Failed, retransplanted, alive | `SAL_CTXRE_C18` | `SAL_LTXRE_C18` |
| Failed, alive, not retransplanted | `SAL_CTXFAIL_C18` | `SAL_LTXFAIL_C18` |
| Died | `SAL_CTXDIED_C18` | `SAL_LTXDIED_C18` |
| Post-transplant status yet unknown | `SAL_CTXUNK_C18` | `SAL_LTXUNK_C18` |

No separately published deceased-donor total was found in the 139-field outcome sheet or its
report table. The primary receipt percentage is therefore a **derived sum of the five published
deceased-donor components**. `SAL_TOTTX_C18` is the published all-donor removal-for-transplant
total; `SAL_TOTFTX_C18` is the published all-donor functioning-transplant total. The original
V2 target remains the latter. Rounding checks must compare against these published values
without replacing them. A missing component makes its derived donor sum missing.

The current [SRTR methods](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/technical-methods-for-the-program-specific-reports/)
define candidate status using waiting-list removal codes. A transplant removal can have no
matching transplant record or sufficiently late follow-up, which explains why receipt contributes
to a donor sum while later status remains unknown. It does not independently verify completed
transplant records, graft function or survival. Living-donor candidates stay in the original
listing denominator. The same methods distinguish the longer, living-donor-excluding population
used for B8/B9 from the B7 population.

The report prints one decimal for percentages; workbooks preserve additional digits and can
store numeric percentages as either numbers or numeric strings. Preserve the workbook values
for analysis. Ten rounded displayed components and one rounded total can differ by up to
0.55 percentage points solely from one-decimal rounding. The study uses these display-rounding
intervals only for the explicitly specified accounting check; model targets preserve the full
workbook precision. The rounding allowance never replaces or rounds a modeling target.
`Not Observed` in a time-to-transplant cell means the percentile was not reached in its follow-up;
it is not zero months. Empty or suppressed source cells remain null.

## Evidence file identities

Paths below are relative to `data/receipt-study/source-research/`. The local JSON records their
sizes and corresponding wait-table source files. These SHA-256 values pin the retained outcome
text; they do not claim that the historical PDF downloads succeeded.

| Release | Text snapshot | SHA-256 |
|---|---|---|
| 1905 | `1905-web-source.txt` | `8b9ffa2715777bb29b72f08d7d950580beb7745e8f91c4d73aa0a649278cb078` |
| 2105 | `2105-outcome-source.txt` | `76df61d2b0895d08a1abb424105ddc134e891273276758bf7fc6668206956b3f` |
| 2205 | `2205-outcome-source.txt` | `52ce900518e69132eb3959a8f69b5a461bdc0ac095fff981cb8eac3305bfa82a` |
| 2305 | `2305-outcome-source.txt` | `aab4649a328d8ad3b960daa36fcb2caf8d40dcde2dc77fd4ecae5fe7f1d8c5c7` |
| 2405 | `2405-outcome-source.txt` | `ff473bb7e4fea0ad2e0ec6a848325aa0daef2a50f764f631d22c6cfe099f6b78` |
| 2505 | `2505-outcome-source.txt` | `39166d6f06de227eaf97a830e974bce5406a87e8664e55a7cd306983d8b66dc1` |
| 2605 | `2605-pdf-source.txt` | `0cb17fabae6c28a1e04450563c9a12ab85ec05202dec1951d9dee193760d5904` |

The methods HTML response was HTTP 200, `text/html`, 168,388 bytes, SHA-256
`53e44c6adc0403a150c4112af2d6b990ba26d88e83d338d1ffde63f0ed2d0bd2`.
It is a fingerprinted July 2026 methods page, not release-specific proof of historical dates.

Source-bound parser regressions, temporal panel validation, complete accounting and study
execution are recorded in Plan 0023. This audit supplies their independent evidence; it does
not replace those acceptance checks or authorize changes to any original study result.
