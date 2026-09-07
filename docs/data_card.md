# Data card — Kidney Acceptance Signal Monitor

**Data-card version:** 1.0  
**Release date:** 2026-09-03  
**Scope:** public, aggregate kidney transplant program data

## Intended use

This dataset supports an offline screening signal for transplant-program quality-improvement
review. It is not patient- or offer-level data and must not be used to determine whether an organ
should have been accepted, infer a clinical or regulatory outcome, rank programs, or reproduce
SRTR’s offer-level model.

**Reading note, 2026-09-05:** This card describes the original V1 release. It counts published
program-level offer measures for calendar years 2017–2025. The separate V2 study follows groups
of listed candidates and uses a different outcome and calendar. The figures and release identity
below retain their original meaning.

## Source and attribution

The source is the Scientific Registry of Transplant Recipients (SRTR) national center-level
Program-Specific Report workbooks for kidney programs. `configs/data_sources.yaml` pins the nine
source URLs, download sizes, SHA-256 values, workbook members where applicable, sheet names,
publication values and their precision, and expected schemas. The source landing page, technical
methods, reporting timeline, and permissions guidance are linked there.

Raw workbooks total about 94 MiB and remain in the ignored immutable local cache. They are not
redistributed in Git. The tracked release contains only the attributed, derived program-level
tables and factual build/model evidence needed for the offline demonstration.

## Grain — what one row represents and which years are covered

`program_signals.parquet` has one row per
`program_key × cohort_year × offer_group`. `program_key` is the composite `(CTR_CD, CTR_TY)`;
program name is display-only and is never a join key. The five P0 offer groups are overall, low
KDRI, medium KDRI, high KDRI, and hard-to-place.

One program-year contributes five rows, one for each offer group; those rows are not five
independent programs. KDRI means Kidney Donor Risk Index and names the source's donor-risk
groups. Hard-to-place means an offer sequence greater than 100. It can overlap those groups, so
adding the rows does not give a valid overall offer count.

The table contains 10,515 rows representing 2,103 program-years across nine non-overlapping
calendar-year cohorts from 2017–2025:

| Cohort | Release | Programs | Signal rows | Source columns |
|---:|---:|---:|---:|---:|
| 2017 | 1808 | 238 | 1,190 | 125 |
| 2018 | 1905 | 240 | 1,200 | 125 |
| 2019 | 2006 | 234 | 1,170 | 125 |
| 2020 | 2105 | 233 | 1,165 | 125 |
| 2021 | 2205 | 232 | 1,160 | 125 |
| 2022 | 2305 | 234 | 1,170 | 125 |
| 2023 | 2405 | 232 | 1,160 | 125 |
| 2024 | 2505 | 230 | 1,150 | 143 |
| 2025 | 2605 | 230 | 1,150 | 143 |

`model_panel.parquet` has one row per `program_key × feature_cohort_year` and contains 2,103 rows.
It materializes the adjacent target year, feature availability, analytic eligibility,
first-observed status, and `public_forecast_eligible`; the view never derives eligibility.

## Fields and source meaning

The offer-acceptance ratio (OAR) compares completed-transplant acceptances with SRTR's expectation
for similar offers. An OAR of 1 means in line with expectation; it is a ratio, not a percentage
of offers accepted. Expected acceptances come from SRTR's offer-level calculations, not from a
model fitted by this project. A 95% credible interval expresses SRTR's uncertainty about its
published ratio; it is distinct from uncertainty about a future projection.

Published OAR means and 95% credible bounds are authoritative. Observed and expected acceptances,
offers, source URL/hash, exact publication value/precision, cohort dates, and display-only program
location accompany each signal. Formula recreation using `(acceptances + 2) / (expected + 2)` is
only a quality-assurance (QA) check that allows for source rounding.

Identifiers and ZIP codes remain strings. Published month-only dates remain month precision and do
not acquire an invented day. Hard-to-place offers can overlap KDRI strata and are not summed with
them. KDPI ≥60 fields appear only in recent sources and are excluded from the P0 model.

## Missingness

Missing and suppressed values remain null and never become zero. Across 2,103 program-years,
missing published subgroup OAR counts are: low KDRI 2, medium KDRI 9, high KDRI 268, and
hard-to-place 17. A program absent from the next release receives a missing target, not a negative
label. Zero subgroup offers require zero observed/expected accepts and null ratio/bounds.

First-observed programs are labeled. They may appear in prespecified diagnostics, but their public
projection is withheld. The latest feature cohort contains 229 explicitly public-eligible programs
and one first-observed program; its target is not yet published and therefore analytic-eligible
count is zero for that projection row set.

Here, public eligibility means the stored data permit displaying a projection; analytic eligibility
means a later published outcome is available for measuring its error. These are different tests.
The latest cohort is calendar year 2025, published on 2026-07-07; its next-calendar-year target is
2026. A missing published outcome gives no information about whether the underlying outcome was
good, bad, or zero.

## Exclusions and transformations

- Only the pinned annual calendar-year cadence is modeled; overlapping semiannual cohorts are
  excluded.
- Center code/type/name, city/state/ZIP, OPO/DSA identity, cohort year, target-period values, and
  future report availability never enter the feature matrix.
- KDPI ≥60 is display-only because it lacks sufficient history.
- Rows without an observed adjacent-year target do not enter analytic evaluation.
- The prespecified drift checks exclude transitions touching cohort 2020 and cohort 2021; these are
  sensitivity analyses, not causal estimates.

## Known shifts and limitations

- The 2020 cohort reflects COVID-19 disruption.
- Circle-based kidney allocation began 2021-03-15, within the 2021 cohort.
- The OAR monitoring metric took effect 2023-07-27, so 2023 is mixed context; 2024–2025 are full
  post-policy cohorts but are insufficient for a separate era model.
- SRTR risk models and national practice can change. Cross-year OAR change need not reflect program
  behavior alone.
- Program entry, closure, and type change occur. Adjacent matched transitions range from 229 to
  238 and are reconciled in `qa_report.json`.

## Validation and QA

The build rejects source size/hash/type/member/schema drift, unsafe archives, duplicate composite
keys, invalid counts or intervals, non-calendar or overlapping cohorts, and forbidden feature
fields. The release QA report records source inventories, date normalizations, entry/exit,
eligibility, missing subgroup values, and rounding diagnostics. All checked published ratios were
inside their release-specific rounding ranges; the published values remain authoritative
regardless.

## Provenance and reproducibility

The tracked bundle’s `release_manifest.json` contains every payload size and SHA-256 plus the Git
commit recorded by the frozen replay, Python and lock identity, source/config hashes, all source
hashes, feature schema, model parameters, cohort roles, build time, and methodology-ledger hash.
Bundle content SHA-256 is
`1de89083ceebfda9afaf2d6b1c6ba3f1e6d0c1a1da16df9d09d994c4ec3581ad`; total size is about
1.23 MB. Reproduction starts with `uv run kasm data verify-cache` and does not depend on live URLs.
