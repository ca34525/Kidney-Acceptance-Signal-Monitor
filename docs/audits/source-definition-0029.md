# Source definition audit 0029 — Offer acceptance across releases

**Audit date:** September 8, 2026. **Scope:** [Plan 0029](../plans/0029-interview-readiness-corrections.md), R1.
This audit reads public documentation and two existing workbook rows. It does not refit,
rescore, change source pins, or overwrite a completed study.

## Finding and project consequence

SRTR changed which declined offers enter the published offer-acceptance ratio (OAR) in
**July 2025**, then broadened the rule in **January 2026**. Allocation out of sequence
(AOOS) means allocation outside the ordered match-run sequence. The July 2025 rule used
bypass code 863 to identify its start; the January 2026 rule used OPTN's broader analytic
definition. The official [November 5–7, 2025 MPSC minutes](https://www.hrsa.gov/sites/default/files/hrsa/optn/20251105-mpsc-meeting-minutes-public.pdf),
section 2, printed page 3, explicitly distinguish these releases.

Therefore the project's `2505` source, measuring calendar 2024, already contains an AOOS
exclusion. Its `2605` source, measuring calendar 2025, follows the expanded rule. January
2026 was not the first exclusion, and January 2026's half-year cadence report is not a
pinned annual source in this project. A release date identifies when the statistic was
published; the earlier measurement year identifies when the offers occurred.

**Interpretation:** a change between published annual ratios can reflect both program
experience and the reporting rules. The project predicts the next published statistic;
it cannot separate those contributions using these aggregate releases. This is a limit
on interpretation and transport to future releases, not evidence that a particular
forecast score is wrong or that the rule caused any measured improvement. Original
results remain historical evidence under their recorded inputs. A claim about behavior
under a constant definition needs a separately specified analysis and, if definitions
cannot be reconciled, a restricted modeling era.

## Release and table evidence

| Release | Publication and offer cohort | Definition evidence and limit |
|---|---|---|
| Earlier context | September 14, 2023 explanation; discusses calendar 2022 offers | [HRSA's explanation](https://www.hrsa.gov/optn/news-events/news/new-pre-transplant-performance-metric-now-effect-offer-acceptance-rate-ratio) lists exclusions for bypasses, no-acceptance match runs, offers after the last acceptance, duplicates and most multi-organ offers. It does not list the later AOOS-start exclusion. This is a dated description, not an immutable methods snapshot for every earlier release; the page says last reviewed December 2025. |
| January 2025 | Not a pinned annual release | [SRTR's January 7, 2025 announcement](https://srtr.hrsa.gov/about-srtr/news-and-media/) identifies the new kidney donor profile index (KDPI) offer breakdown. It does not establish an AOOS change in that release. |
| `2505` | July 8, 2025; January 1–December 31, 2024 | The November minutes explicitly place the code-863 exclusion in July 2025. The [NYNS kidney report](https://www.srtr.org/PDFs/072025_release/pdfPSR/NYNSTX1KI202505PNEW.pdf), Table B11, printed page 13, identifies this release and calendar cohort. The report was available through the search provider's indexed PDF text; direct retrieval returned 404, so no local PDF hash or rendered inspection is claimed. |
| January 2026 | Announcement January 6, 2026; not a pinned annual release | The November minutes describe expansion to the OPTN analytic definition; [SRTR's January announcement](https://srtr.hrsa.gov/about-srtr/news-and-media/) confirms exclusion after AOOS begins. The announcement has a code discrepancy described below. |
| `2605` | July 7, 2026; January 1–December 31, 2025 | [SRTR's current methods](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/technical-methods-for-the-program-specific-reports/) identify the July 7 release and this Table B11 cohort. The [current NYNS kidney report](https://srtr.hrsa.gov/reportapi/documents/psr/nynstx1_ki), Table B11, printed page 13 / PDF page 17, independently confirms the dates. Its downloaded filename is `NYNSTX1KI202605PNEW.pdf`. |

The current methods exclude an offer that was not accepted and occurred after AOOS began,
identified by codes **799, 861, 862, 863 or 887**. Completed transplants remain included;
this is not exclusion of every organ allocated out of sequence. The [current professional
FAQ](https://srtr.hrsa.gov/getting-started/faqs/for-transplant-center-professionals/) agrees
with that code list. The January 2026 news item instead prints **886** as its final code.
These public documents disagree. The audit does not infer when that discrepancy arose,
which implementation used 886, or that the difference was merely a typographical error.
Use the current technical definition to describe July 2026; retain the discrepancy when
describing the precise January implementation.

The minutes also report that SRTR's presented evaluation did not show a dramatic impact
and that the model was being recalibrated. That qualitative report does not quantify the
effect on this project's programs, folds or scores. No effect size is assigned here.

## Binding the reports to the pinned workbooks

The cache loader verified the manifest's existing transport/member hashes before reading
the `Table B11 & Figures B10-B14` sheet. Selection used machine field names and the
composite identity `(CTR_CD, CTR_TY) = (NYNS, TX1)`. Six values in each published report
matched that workbook row at the report's displayed precision:

| Release | Offers | Acceptances | Expected acceptances: workbook → report | Published OAR | Published 95% credible interval |
|---|---:|---:|---:|---:|---:|
| `2505` | 28,597 | 125 | 98.63 → 98.6 | 1.26 | 1.05–1.49 |
| `2605` | 22,453 | 144 | 95.05 → 95.0 | 1.50 | 1.27–1.76 |

Fields: `OA_OVERALL_OFFERS_CENTER`, `OA_OVERALL_ACCEPTS_CENTER`,
`OA_OVERALL_EXP_ACCEPTS_CENTER`, `OA_OVERALL_HR_MN_CENTER`,
`OA_OVERALL_HR_LB_CENTER`, `OA_OVERALL_HR_UB_CENTER`. The ratio and interval were read
directly, never reconstructed from the expected count. Raw `OAR_cohort_start` and
`OAR_cohort_end` cells have the corresponding calendar dates and a non-midnight time
component; this is source formatting, not a publication timestamp.

Evidence is in ignored `data/audit-0029/oar-source-binding.json`. The July 2026 table was
rendered and visually inspected as `data/audit-0029/2605-table-b11.png`. These twelve
agreements bind a checked program's report and workbook values. They do not validate
every program or reproduce the offer-level inclusion algorithm.

## July 2026 correction notice

[SRTR's July 9, 2026 announcement](https://srtr.hrsa.gov/about-srtr/news-and-media/) says
first-year graft survival/failure dial icons displayed inaccurate tiers following the
July 7 release and were corrected. It also directs users who downloaded national
center-level summary files between **7 p.m. CDT July 7 and 7 p.m. CDT July 8** to download
corrected files.

The notice supplies no machine field list or before/after file hashes and does not say
OAR values changed. Do not relabel it as an OAR correction. The pinned manifest records
verification on September 3, 2026, after the notice's window; the current PDF agrees with
the six pinned OAR fields above. Neither observation establishes what every field or
file contained at the original publication instant. No original pins were replaced.

## What remains unresolved

- A complete archived methods snapshot for each earlier release was not recovered.
  The dated official minutes establish the July 2025/January 2026 chronology, but cannot
  establish that every other definition and model coefficient stayed constant.
- The [2026 study by Parvathinathan and colleagues](https://doi.org/10.1016/j.ekir.2026.106570)
  mentions an OAR cohort change starting in 2025 and cites a private January 27, 2025
  email. That is not enough to identify a separate change in the January 2025 release.
  The public evidence found here does not establish such a change or its exact contents.
- No public evidence found here establishes whether previously published OAR archives
  were later recalculated under a newer rule. Applying a new rule to an earlier calendar
  cohort in a new release is different from replacing an already published file.
- Exact January 2026 treatment of code 886 versus 887, the July correction's affected
  workbook fields, and the magnitude of the AOOS change remain unresolved. Confirmation
  would require release-specific documentation or clarification from SRTR; no message
  was sent and no offer-level reconstruction was attempted.

## Acquisition record and verification

`data/audit-0029` is ignored by Git. Public documentation downloads used a bounded HTTPS
allowlist, checked status/type/signature/size, computed SHA-256, and saved through a
temporary file with no overwrite. These are first-seen documentation hashes, not
retrospective authenticity proofs. Sidecar JSON records each URL, UTC retrieval time,
response headers, byte count and hash; failed attempts have separate fetch logs.

| Local document | Retrieved September 8, 2026 UTC | HTTP / type | Bytes | SHA-256 |
|---|---|---|---:|---|
| `news-and-media.html` | 19:04:26 | 200 / HTML | 222,550 | `62b383d7fba27835cbbe45c09bcab42478f7da36a28db97c5ae4453bba40d85a` |
| `technical-methods-for-the-program-specific-reports.html` | 19:04:26 | 200 / HTML | 168,387 | `6579c0c4e0260eb3b3c3bd3659b8f6554b422cff751d8060af0eaf5365c19be0` |
| `program-specific-reports-psr.html` | 19:04:26 | 200 / HTML | 87,120 | `2d4b79e7b8675cc875c5b2167cd8bb5a6a4217c272b519f4946b62d29c8b0334` |
| `nynstx1_ki.pdf` | 19:06:08 | 200 / PDF | 2,193,208 | `8d0d4a401de55e2ca7fd248168353bb27b0b9846d2f9496688122faaca5095a9` |
| `for-transplant-center-professionals.html` | 19:06:08 | 200 / HTML | 176,228 | `bbfd41c820bd5565ae6fb7810a9157f89a249197efa7a69df55cca338c08459d` |

The November minutes were read through the web provider's parsed official PDF; a direct
download returned HTTP 403. They therefore have a public URL/page citation but no local
file hash. The 2023 explanation and research paper likewise have web citations only.
The dynamic report endpoint must always be identified by its returned release, not its
unchanging URL. The downloaded July 2026 PDF also matches the PDF hash preserved in
[audit 0022](source-feasibility-0022.md).

Pinned workbook SHA-256 values remain `032584a0a1fe3df70c1f4cc9806f9a2756f8d378795534dae38a47d441422ac5`
(`2505` member) and `8f357b6ed7a060f395fd1930e34e9e4aee4fe508d67f10b4167073eded834184`
(`2605`). The former's ZIP hash remains
`359723874d5cdc2acaae98e0ebd3385f4a7d2f4dcc255e4dba90dba2a6036b8b`.

Executed the isolated `data/audit-0029/bind_oar_sources.py` against the verified cache:
six matching fields per release. Rendered the July 2026 Table B11 using
`pdftoppm -f 17 -singlefile -scale-to 1500 -png data/audit-0029/nynstx1_ki.pdf data/audit-0029/2605-table-b11`.
Documentation review covers citations, dates, limits and `git diff --check`; no model
command or Python suite is warranted for this documentation-only audit.
