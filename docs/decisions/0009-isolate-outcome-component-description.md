# Decision 0009 — Describe outcome components in a separate run

**Date:** 2026-09-07. **Status:** accepted for Plan 0020 P3.

The next substantial follow-up batch explains the donor and unknown-status portions of the
original evaluation outcome. Restrict it to release 2505, whose programs and listing cohort can
be matched directly to the preserved predictions. Broader historical component analysis is not
needed to answer this question and would require additional release-specific reconciliation.

Use the [separate component specification](../specs/patient-journey-v2-outcome-components.md)
and typed configuration. Preserve the original V1/V2 evidence and completed report-count study.
Read stored predictions without refitting. Record all fixed associations, missingness and
unmatched programs; never interpret unknown status as an observed patient outcome or a proven
cause of prediction error. Use four separate median bars, since these components omit other
listing outcomes and medians cannot be added to make a total.

The user's request authorizes this local implementation and ignored outputs at
`data/patient_journey_v2_followup/outcome_components_v1`, with complete write-once runs and
provenance. It does not create a tracked release or change the app, target, inputs, promotion
rules or either completed model comparison. Leave all repository changes uncommitted.
