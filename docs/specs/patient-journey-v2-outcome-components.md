# V2 follow-up — Explain the published outcome components

**Version:** 1.0, 2026-09-07. **Scope:** Plan 0020 P3.

This exploratory description asks how living-donor and deceased-donor functioning transplants
and post-transplant unknown status appear in the original V2 evaluation outcome. It uses already
inspected outcomes. It cannot establish why a prediction was wrong or correct missing follow-up.

## Fixed population and source

The analysis identifier is `kidney_patient_journey_v2_followup_outcome_components_v1`.
[The typed configuration](../../configs/patient_journey_v2_followup/outcome_components.yaml)
fixes release `2505` only: candidates listed July 1, 2022–June 30, 2023, status 18 months after
listing, follow-up end December 30, 2024, published July 8, 2025. The original V2 methodology
ledger supplies these dates and the Table B7/Tiers sheet contracts. No cross-release pooling
or new model fitting is permitted. Other releases need their own source reconciliation first.

Read only the checksum-verified cached workbook pinned in `configs/data_sources.yaml` and the
preserved original V2 release. Verify the original bundle, configuration, source-manifest and
methodology bindings with the existing trusted reader. Preserve V1, original V2, and the P1/P2
report-count specification, configuration and outputs. The bundle identity remains
`ce2844edbcec92c09d0053720d5331dd37ed43ab75de7aa4dd1de431c79a9eee`.

One source record represents a program identified by `(CTR_CD, CTR_TY)` and this listing cohort.
Reconcile its key against the same-release Tiers directory; names never join records. Parse by
machine field, validate sheet dimensions and description labels, and retain numeric strings as
numbers. The separate [component ledger](../patient_journey_v2_component_ledger.md) records each
displayed component's definition, denominator, timing, precision, missing markers and citations.

All five percentage fields use the original listing-group count `SAL_N_C`, including candidates
who did not receive a transplant. They are not percentages among transplant recipients:

- `SAL_CTXFNC_C18`: deceased-donor transplant, functioning and alive.
- `SAL_LTXFNC_C18`: living-donor transplant, functioning and alive.
- `SAL_CTXUNK_C18`: deceased-donor transplant, status yet unknown.
- `SAL_LTXUNK_C18`: living-donor transplant, status yet unknown.
- `SAL_TOTFTX_C18`: published total functioning-transplant percentage, always authoritative.

Unknown status in these two donor fields is only the post-transplant unknown portion. Other
removal/lost-status categories are outside this bounded description. A blank, dash, double dash,
`Not Reported` or `Not Observed` remains null; preserve the raw marker for audit. Unexpected text,
nonfinite, boolean or out-of-range values fail. Missing candidate counts remain null; percentages
require a positive original listing count. Do not reconstruct or pool patient counts.

## Calculations fixed before execution

1. Retain all source rows and every original panel row for `2205→2505` in the audit. Describe
   source programs with `SAL_N_C >= 10` separately from the original evaluation population.
   Evaluation associations use exactly the original `primary_analytic_eligible` programs, with
   complete donor-unknown components for the particular association. Never redefine eligibility.
2. Join by program and target release, then require identical listing start/end, follow-up end,
   candidate count and published total wherever both sides report them. Duplicate keys, wrong
   releases/cohorts, or disagreements fail. Report exact matched keys, source-only keys,
   panel-only keys, original exclusions and missing-component keys/counts. A missing source
   match for an eligible original program fails instead of silently shrinking the comparison.
3. Sum only the two functioning donor components, or only the two unknown donor components.
   Reject duplicate, overlapping summary, mixed-denominator or mixed-time components. A missing
   operand makes the sum missing. The published total never enters a component sum.
4. Reconcile donor functioning sum against the published total using the verified PDF's one
   decimal display precision: each of three operands has a clipped interval of ±0.05 percentage
   points. Require intersection of the sum interval and total interval (inclusive endpoints,
   floating-point arithmetic allowance `1e-12`). Save the exact workbook difference too; do not
   round or replace workbook values. Unreconciled reported values fail; missing operands yield
   an unavailable check. Check that the four disjoint selected components cannot exceed 100
   within the same rounding intervals. These four components do not form a complete 100% total.
5. Report component-specific program counts and medians for both populations, including the
   combined unknown percentage and authoritative published total. Each program has equal weight.
   Medians are not additive and are not pooled candidate percentages. No reconstructed counts,
   inferred unknown outcomes, numerical best/worst-case scenarios or survival estimates.
6. On exact matched original evaluation programs, report Pearson correlation of combined
   post-transplant unknown percentage with the published total, and separately with signed and
   absolute errors for all eight stored original approaches. Use stored predictions only;
   validate all model/program keys, targets, counts and error arithmetic before use. Positive
   signed error means predicted too high. Use complete pairs per association, record missing
   counts, and report unavailable for fewer than three pairs or a constant variable. No
   p-values, confidence intervals, fitted explanation model or selection by result. Association
   describes co-variation among programs in one period; it does not establish reporting as a
   cause, patient outcomes among unknowns, or performance in a new period.

## Report, output and acceptance

Produce a readable report and one standalone SVG/PNG figure with four separate median bars for
the matched original evaluation programs. Label donor type, listing denominator, dates, units,
population size and missing counts. Never stack medians or imply the four bars total 100%.
The report includes the authoritative total separately, source/population audit and all fixed
associations. Explain what remains unknown in ordinary language. Target-period components stay
outside both original and count-removed feature contracts; regression tests enforce this.

The authorized ignored local root is `data/patient_journey_v2_followup/outcome_components_v1`.
Publish each complete run once to a direct child named by the input/implementation hash. Reject
overwrite, traversal, absolute destinations, symlinks/junctions, unsafe filenames and writes
outside that root. Stage complete payloads and atomically rename them; failure leaves no
completion manifest. Outputs include parsed components, exact matching evidence, summaries,
report and figure. No new tracked release, application change or forecast is authorized.

Record source/archive/member hashes, original release/payload identities, both study configuration
hashes, original and component ledgers, specification, dependency lock, implementation hashes,
Git commit/dirty status and UTC build time. Record cohort timing, empty feature schema and model
parameters (no model fitted). Recheck bound identities before publication. Uncommitted builds
remain development evidence. Deterministic payloads must reproduce independently of timestamps.

Acceptance requires constructed failing tests first for arithmetic/missingness, changed source
labels/schema, mismatched joins, predictor exclusion and input/filesystem failures; focused/full
verification; a real offline build; visual review; and preserved original hashes. Record commands
in [Plan 0020](../plans/0020-v2-follow-up-and-interview-story.md). P4's case, presentation,
author walkthrough and rehearsal remain subsequent work.
