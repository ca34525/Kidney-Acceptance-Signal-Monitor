# V2 outcome-component follow-up results

**Development evidence:** 2026-09-07. **Study:** Plan 0020 P3, release `2505` only.

All 218 original evaluation programs have the four donor components needed for this description.
Their median combined post-transplant unknown percentage is **16.05% of the original listing
group**. That differs from the **16.27%** median across the broader 222-program source population
with at least ten listed candidates. Neither number is a pooled patient percentage.

This separate exploratory description preserves the [original V2 comparison](patient_journey_v2_model_card.md)
and [report-count follow-up](patient_journey_v2_followup_results.md). No model was fitted,
promoted, or given target-period components as earlier inputs. The application is unchanged.

## What is counted

Each record represents one kidney program, identified by `(CTR_CD, CTR_TY)`, and its candidates
listed July 1, 2022–June 30, 2023. Status is reported 18 months after listing. The original
methodology retains December 30, 2024 as follow-up end; publication was July 8, 2025. Every
percentage uses the original listing group, `SAL_N_C`, including candidates who never received
a transplant. Living-donor outcomes here concern candidates from the waiting list.

The [source ledger](patient_journey_v2_component_ledger.md) records each field's definition,
denominator, timing, hashes, missing markers and PDF display precision. Definitions come from
the [archived July 2025 report, Table B7, page 9](https://www.srtr.org/PDFs/072025_release/pdfPSR/NYNSTX1KI202505PNEW.pdf)
and [SRTR's Table B7 methods](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/technical-methods-for-the-program-specific-reports/).

| Population accounting | Programs |
|---|---:|
| Source Table B7 records | 234 |
| Source records with at least ten listed candidates | 222 |
| Original prediction universe for `2205→2505` | 236 |
| Original eligible evaluation programs, all matched | 218 |
| Source-only programs, outside the original prediction universe | 4 |
| Original prediction-universe programs absent from the source | 6 |
| Original exclusions: fewer than ten listed candidates | 11 |
| Original exclusions: missing target | 6 |
| Original exclusions: missing earlier target | 1 |

The last three rows account for the original 18 exclusions. The six missing targets are also
the six unmatched prediction-universe programs; do not add them again. Exact keys, original
eligibility, exclusions and missingness are saved. No donor component is missing among either
the 222 source-selected or 218 original evaluation programs.

## Separate percentages across programs

| Measure | Source N≥10, 222 programs | Original evaluation, 218 programs |
|---|---:|---:|
| Deceased donor: functioning and alive | 16.69% | 16.67% |
| Living donor: functioning and alive | 6.09% | 6.09% |
| Deceased donor: status yet unknown | 12.93% | 12.75% |
| Living donor: status yet unknown | 2.45% | 2.50% |
| Combined post-transplant unknown | 16.27% | 16.05% |
| Published functioning-transplant total | 23.78% | 23.74% |

Every cell is a program median: the middle percentage after sorting that measure, averaging
the two middle values when needed. Medians cannot be added. Combined unknown first adds the
two donor-unknown percentages within each program, then finds the median across programs.
It therefore differs from adding the two displayed medians.

These four components omit waiting, death, lost/transferred and other statuses. The published
functioning total overlaps its donor components and remains authoritative. All 234 donor sums
reconcile with it at the PDF's one-decimal display precision. The largest absolute workbook
difference is about `1.0e-9` percentage points; this is an observed QA result, not a new tolerance.

The generated figure uses four separate median bars. It identifies the original evaluation
population, listing denominator, period, source publication and zero missing-component counts.

## Unknown status and original prediction errors

Pearson correlation describes whether two quantities tend to increase together across the
same programs. Its unitless value ranges from −1 to +1. All calculations below use the same
218 complete program pairs. Signed error is predicted minus published percentage; positive
values mean predictions are too high. Absolute error measures the size of that difference.

| Original approach | Unknown vs signed error | Unknown vs absolute error |
|---|---:|---:|
| Carry forward latest outcome | 0.165 | 0.253 |
| Available-cohort reference | -0.301 | 0.056 |
| Simple historical mean | 0.084 | 0.121 |
| Ridge: history | 0.072 | 0.115 |
| Ridge: history + acceptance | 0.089 | 0.108 |
| Ridge: history + access | 0.271 | 0.293 |
| Ridge: history + access + acceptance | 0.288 | 0.275 |
| Ridge: history + access + acceptance + safety | 0.330 | 0.337 |

Combined unknown and published functioning percentage have correlation **0.301**. All eight
original approaches appear in fixed order; the count-removed models were not rerun.

These associations do not establish that reporting caused prediction error. Functioning and
unknown percentages share a denominator and mutually exclusive statuses; signed error contains
the observed outcome algebraically. Unknown status can reflect an incomplete follow-up form,
including one not yet due. It does not establish health, death or graft failure. The analysis
does not fill in those outcomes, fit a survival model or provide a new evaluation period.

## Reproduce and inspect

Use the preserved original release and immutable verified cache:

```powershell
$env:UV_CACHE_DIR = '.uv-cache'
$env:MPLCONFIGDIR = '.uv-cache/matplotlib'
uv sync --frozen
uv run kasm data verify-cache
uv run kasm patient-journey outcome-components
```

The [fixed specification](specs/patient-journey-v2-outcome-components.md) and
[configuration](../configs/patient_journey_v2_followup/outcome_components.yaml) define the
calculation. [Decision 0009](decisions/0009-isolate-outcome-component-description.md) approves
only the ignored local output root. The reviewed run is:

`data/patient_journey_v2_followup/outcome_components_v1/e95ab9db56aad000f6a296c33fb4ad981a57b39f70ba2a6a0adb4b3fe388171b`

It contains `components.json`, `analysis.json`, `report.md`, SVG/PNG figures and a completion
manifest. The five payloads total 1,055,740 bytes. Repeating the command fails instead of
overwriting the run. A changed implementation/configuration identity creates a different run;
it never changes either original study or the report-count evidence.

| Identity | Value |
|---|---|
| Original V2 bundle SHA-256 | `ce2844edbcec92c09d0053720d5331dd37ed43ab75de7aa4dd1de431c79a9eee` |
| Component configuration SHA-256 | `9193473cc12bebd115f1db5e3dc79846d54925edecbee5b5082937cc92a435e5` |
| Analysis JSON SHA-256 | `90b0e02dc3817b3333dcf22389c964a3886ab31809105c4d050041af2bf73a0a` |
| Build Git commit, dirty worktree | `1d2dabb72eec1056c1117530fe4e6c50e5c34b0a`, `true` |
| Build time UTC | `2026-09-07T14:58:09.114107Z` |

The manifest records source/archive/member hashes, both configuration identities, ledgers,
specification, dependency lock, implementation hashes and cohort timing. Feature schema and
fitted-parameter mappings are empty because no model is fitted. This uncommitted build is
development evidence, not a tracked release.

All five payloads reproduce byte-for-byte in a separate read-and-calculate run. Independent
review checked the figures, medians, all error correlations and payload hashes. The
[active plan](plans/0020-v2-follow-up-and-interview-story.md) records tests and verification,
including the local Docker startup blocker. P4's program case, presentation, author walkthrough
and rehearsal remain unfinished; this analysis does not establish interview readiness.

Public aggregate research prototype — not clinical or regulatory decision support.
