# Outcome-component source ledger — V2 follow-up P3

**Verified:** 2026-09-07. **Intended release:** `2505` only. No claim of historical
component comparability is made. This extends the follow-up's evidence without editing the
original V2 methodology ledger.

Each record describes one kidney program's original July 1, 2022–June 30, 2023 listing group.
Status is measured 18 months after listing; the original ledger retains December 30, 2024 as
follow-up end. Publication was July 8, 2025. Every percentage below has the original listing
group `SAL_N_C` as denominator, including candidates who never received a transplant.

| Field | Exact workbook description | Meaning at 18 months | Unit |
|---|---|---|---|
| `SAL_N_C` | N | Number in the original listing group | Candidates |
| `SAL_CTXFNC_C18` | Functioning (alive) | Deceased-donor transplant, known alive with a functioning transplant | Percent of original listing group |
| `SAL_LTXFNC_C18` | Functioning (alive) | Living-donor transplant from the waiting list, known alive with a functioning transplant | Percent of original listing group |
| `SAL_CTXUNK_C18` | Status Yet Unknown | Deceased-donor transplant, post-transplant status yet unknown | Percent of original listing group |
| `SAL_LTXUNK_C18` | Status Yet Unknown | Living-donor transplant from the waiting list, post-transplant status yet unknown | Percent of original listing group |
| `SAL_TOTFTX_C18` | Functioning tx (alive) | Published total functioning-transplant percentage; authoritative | Percent of original listing group |

The archived [July 2025 kidney report, Table B7, printed page 9](https://www.srtr.org/PDFs/072025_release/pdfPSR/NYNSTX1KI202505PNEW.pdf)
verifies the dates, donor headings, denominator and timing for every field in this table.
The [SRTR Table B7 methods](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/technical-methods-for-the-program-specific-reports/)
explain that unknown post-transplant status can reflect an incomplete follow-up form, including
one not yet due. Unknown does not establish health, death or graft failure. Lost/transferred
and other removal categories are distinct and outside the four components described here.

## Verified workbook and precision

- [Pinned source archive](https://srtr.hrsa.gov/Archives/PSRdownloads/csrs_tables_all/csrs_final_tables_2505all.zip):
  SHA-256 `359723874d5cdc2acaae98e0ebd3385f4a7d2f4dcc255e4dba90dba2a6036b8b`.
- Member `csrs_final_tables_2505_KI.xls`:
  SHA-256 `032584a0a1fe3df70c1f4cc9806f9a2756f8d378795534dae38a47d441422ac5`.
- `Table B7`: 234 program records and 139 columns. First row contains machine names;
  second row contains descriptions. Identity is checked against same-release `Tiers`.
- The workbook uses `General` cell formatting and retains varying decimal digits, through ten
  decimal places. Living-donor values are numeric strings. Preserve these published digits;
  neither trailing zeros nor `General` establishes a universal decimal rounding rule.
- The archived PDF displays percentages to one decimal place. The specified reconciliation
  therefore uses a 0.1-percentage-point display quantum, with ±0.05 per value clipped to [0,100].
  It tests compatibility at PDF display precision and reports the raw workbook difference
  separately. It never replaces the published total with the donor sum.
- No missing/suppressed cells were observed in these six fields in the verified 2505 workbook.
  The new parser defensively preserves null/blank, dash, double dash, `Not Reported` and
  `Not Observed` as null and records the raw marker. These are declared input-handling rules,
  not a claim that those markers occurred in this report. Other text fails review.

The four donor components are mutually exclusive, but omit other listing outcomes. The
published total overlaps the two functioning components and cannot be added to them. Component
medians describe the middle program's percentage separately for each component; they cannot
be stacked or interpreted as a pooled candidate percentage.

The functioning and unknown percentages share a denominator and describe mutually exclusive
statuses. Signed prediction error also contains the observed outcome in its calculation.
Correlations among these quantities therefore cannot show that reporting caused prediction error.
This analysis has no event-time histories and fits no survival model or unknown-outcome scenario.
