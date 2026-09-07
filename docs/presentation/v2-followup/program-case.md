# One illustrative program: University of Alabama Hospital

This case explains why acceptance context and the later recorded patient-journey outcome
need their own measures, populations and dates. It is a teaching example from already-inspected
evidence, not a representative program or evidence of an intervention's effect.

**Program:** `ALUA:TX1`, University of Alabama Hospital (ALUA), Birmingham, Alabama.
Names and location are labels only. The extraction joins on the composite program key and
target release, then checks listing dates, candidate count and published outcome agreement.

## Why this case

Start with the original 218 eligible `2205→2505` evaluation programs. Require a reported
earlier outcome, an earlier overall offer-acceptance ratio above 1, a lower later published
functioning-transplant percentage and all four later donor components. Sort by composite
program key and choose the first match. **61 programs qualify; `ALUA:TX1` comes first.**

This disclosed editorial rule chooses a difference between measures for explanation. It does
not select the largest decline, highest error or a program-quality rank. The case is not a
new statistical analysis or a new evaluation population. The full studies keep their original
eligibility and every favorable and unfavorable comparison.

## What was public at the prediction origin

The prediction origin is **July 2022**, the source's month-only publication date. No day is
imputed. That report includes these differently timed quantities:

| Quantity | Published value | People or offers counted and dates |
|---|---:|---|
| Overall offer-acceptance ratio | 2.00 | Calendar-2021 offers; published 95% credible interval 1.76–2.25 |
| Expected acceptances | 125.6 | Same calendar-2021 offer cohort; expected count, not the candidate denominator |
| Earlier published functioning-transplant percentage | 28.07424594% | 431 candidates listed July 1, 2019–June 30, 2020, status 18 months after listing |

The earlier outcome ledger records follow-up end **December 30, 2021**. The offer-acceptance
ratio compares observed acceptances with the risk-adjusted expectation for the offers received.
It is not the percentage of offers accepted, and a value of 2 does not imply twice the patient
benefit. Its credible interval describes that published ratio, not a range around a prediction.

## What the later outcome report records

The later listing group contains **548 candidates listed July 1, 2022–June 30, 2023**. The
report describes their status **18 months after listing**. The original ledger retains
**December 30, 2024** as follow-up end and **July 8, 2025** as publication date.

Every percentage below uses that original 548-candidate listing group, including candidates
who did not receive a transplant. Living-donor outcomes concern people originally on the list.

| Field or fixed donor sum | Exact saved percentage | Slide display |
|---|---:|---:|
| Published functioning total, `SAL_TOTFTX_C18` | 17.518248175 | 17.52% |
| Deceased-donor functioning, `SAL_CTXFNC_C18` | 14.416058394 | 14.42% |
| Living-donor functioning, `SAL_LTXFNC_C18` | 3.102189781 | 3.10% |
| Deceased-donor post-transplant unknown, `SAL_CTXUNK_C18` | 18.97810219 | 18.98% |
| Living-donor post-transplant unknown, `SAL_LTXUNK_C18` | 4.0145985401 | 4.01% |
| Combined post-transplant unknown, sum within this program | 22.9927007301 | 22.99% |

The functioning donor sum reconciles with the authoritative published total under the fixed
P3 rounding check. The total overlaps its components and must not be added to them. The four
donor categories omit other statuses and do not form a complete 100% partition. Unknown
status establishes neither a functioning transplant nor death or graft failure. No unknown
outcome is imputed and no patient count is reconstructed for this case.

The earlier 28.07% and later 17.52% describe different listing groups. The 22.99% is this
program's combined unknown percentage. It is distinct from the 16.05% median across all 218
evaluation programs and the 16.27% median across the broader 222-program source group.

## Historical predictions for the later group

These predictions were evaluated against the already-published **17.518248175%** outcome.
They do not project a future cohort. The compact selection below supports the explanation;
all 13 approaches remain in the [follow-up results](../../patient_journey_v2_followup_results.md).

| Approach | Saved prediction, rounded to percentage |
|---|---:|
| Simple historical mean | 24.55% |
| Persistence | 28.07% |
| Original history-only Ridge | 36.08% |
| Original history plus acceptance | 30.07% |
| Count-removed history-only Ridge | 24.81% |
| Count-removed history plus acceptance | 28.65% |

All six listed predictions exceed the observed percentage in this one case. The case cannot
establish which model works best across programs. The original app shows original predictions;
the count-removed predictions belong only to the separately identified follow-up.

## A question for quality-improvement review

What differences in the listing groups, donor pathways and follow-up reporting records would
help account for the recorded change? Internal review would need evidence beyond these public
aggregates to distinguish those possibilities. The case does not identify the cause, judge
individual acceptance decisions or establish clinical or regulatory standing.

Separately timed safety measures are outside this displayed arithmetic. The app's Safety
context tab shows each measure's own dates and denominator. For example, its waiting-list
mortality ratio concerns candidate person-time, not the 548-candidate Table B7 denominator;
it must never be added to these percentages.

## Source and reproduction trail

The original trusted reader validated the release, schemas and configuration/source/ledger
bindings. The extraction also verified every payload size and SHA-256 in the completed P1/P2
and P3 run manifests. No model fitting, workbook parsing or analytical writer was needed.

| Evidence | Identity |
|---|---|
| Original V2 bundle | `ce2844edbcec92c09d0053720d5331dd37ed43ab75de7aa4dd1de431c79a9eee` |
| Original experiment | `ab8c01453c36039b293a8e7453b17b2b326faf734a081a4b67f8bfe132b1de79` |
| Original methodology ledger | `a1129b00614bcf51f64b9a2b8f93cb13c6c141e767240de5e715023f8334da2e` |
| July 2022 source archive | `6e87092dc56207937ff032783cd49e1b1fbb3e522f0ae1ccab5192431f7530c8` |
| July 2025 source archive | `359723874d5cdc2acaae98e0ebd3385f4a7d2f4dcc255e4dba90dba2a6036b8b` |
| July 2025 workbook member | `032584a0a1fe3df70c1f4cc9806f9a2756f8d378795534dae38a47d441422ac5` |
| P1/P2 reviewed run | `c6cc2cea133e7e61e9e42ac284f170baef43d9989d3ab04eea543ffb47af1cfa` |
| P1/P2 prediction Parquet | `62b89ce483fc77209c4ddde31c514d5a4e1d3333be7e0cf152ad5352d910f2fe` |
| P3 reviewed run | `e95ab9db56aad000f6a296c33fb4ad981a57b39f70ba2a6a0adb4b3fe388171b` |
| P3 analysis JSON | `90b0e02dc3817b3333dcf22389c964a3886ab31809105c4d050041af2bf73a0a` |

For the original values, load the trusted [original panel](../../../artifacts/patient_journey_v2/patient_journey_panel.parquet)
and select `program_key == "ALUA:TX1"`, `feature_release_code == "2205"`,
`target_release_code == "2505"`. Use those same identities in the preserved predictions and
P3 `components.json`. Apply the selection rule above to all original eligible rows to verify
the editorial choice. The [P1/P2](../../patient_journey_v2_followup_results.md) and
[P3](../../patient_journey_v2_component_results.md) results record the full reproduction commands
and manifests; do not overwrite a completed run for this presentation.

Source: Scientific Registry of Transplant Recipients, public kidney Program-Specific Reports,
reused under the [pinned source manifest](../../../configs/data_sources.yaml) and
[component ledger](../../patient_journey_v2_component_ledger.md).

Public aggregate research prototype — not clinical or regulatory decision support.
