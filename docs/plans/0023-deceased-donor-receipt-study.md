# Plan 0023 — Test whether earlier acceptance predicts deceased-donor receipt

**Status:** unimplemented proposal; future implementation requires authorization.
**Scope:** one separately identified exploratory study, conditional on source feasibility.

## Question and purpose

Does earlier public offer-acceptance information improve predictions of the percentage of a
program's newly listed kidney candidates removed from the waiting list for a deceased-donor
transplant within 18 months?

This asks about access to a transplant. Original V2 predicts the percentage known alive with a
functioning transplant, which also depends on later graft status and reporting. The new question
has a substantive reason; its target must be chosen before comparing prediction errors. It does
not replace original V2 or establish that the original outcome is unimportant.

Read [Plan 0022](0022-source-and-cleanup-audit.md), the
[source feasibility audit](../audits/source-feasibility-0022.md), and the
[original V2 specification](../specs/patient-journey-v2.md) before resolving this proposal.
The audit verified the five deceased-donor components across all nine pinned releases and
corrected the newest cohort's dates. It found a possible second evaluation period within those
sources and conditional earlier periods using July 2017 archives. These are feasibility findings,
not extra completed evaluations. Source availability alone does not establish usable training data.

## One record, denominator and target

One record represents one kidney program, identified by `(CTR_CD, CTR_TY)`, and one fixed,
non-overlapping listing cohort. The denominator is that original cohort's `SAL_N_C`, including
candidates who do not receive a transplant. The target is a percentage of listed candidates,
not survival among recipients or the probability for an individual candidate.

Prefer a published deceased-donor total if the source audit verifies its definition and history.
Otherwise explicitly define a derived sum of all five mutually exclusive deceased-donor statuses
at 18 months: functioning and alive; failed and retransplanted alive; failed and alive without
retransplant; died; and status yet unknown. Verify the exact machine fields, donor headings,
denominator and time point in each eligible source before fixing their mapping.

Label a sum as derived from published components. Unknown post-transplant status contributes
because the source records removal for transplant; it does not establish graft function or
survival. Do not assume that a removal code independently verifies a completed transplant record.
A missing component makes a derived target missing. Never fill it with zero or another status.

`SAL_TOTTX_C18` is the all-donor removal-for-transplant total. It may support a separately labeled
source reconciliation or descriptive comparison after verification. It is not automatically
the primary target, and it must not become a replacement endpoint because its scores look better.

## Feasibility and source-date gate

Before fitting, complete these checks without comparing model errors:

1. Verify source identities, release-bound definitions, all five components, published totals,
   missing markers, display precision and consistent candidate accounting across candidate releases.
2. Bind listing and follow-up dates to release-specific evidence. Plan 0022 found that outcome
   and wait-time parsers copy dates from the ledger and then validate against that same ledger.
   A separately tested correction path must reject disagreement with source-period evidence
   before this study can use those dates. Preserve the original ledger and results as records.
3. List the exact publication origins and non-overlapping target cohorts. Every predictor must
   have been public by its origin, with measurement and follow-up ending before target listing
   begins. Every training outcome must have been public by the evaluated prediction origin.
4. Record the programs visible at each origin before looking for their later outcome. Retain
   missing future reports as unknown targets and report additions, exits and missing components.
   Fix the minimum listing-group size and any sensitivity population before scoring.

Do not infer that a shorter follow-up endpoint becomes public sooner within the same report.
Do not pool overlapping annual or semiannual reports as independent outcome cohorts. At least
two eligible evaluation origins are required before discussing consistency across time. If only
one is usable, a bounded exploratory comparison remains possible, with that limitation explicit.

## Bounded comparisons

Use the same eligible evaluation rows for every comparison. Missing predictors retain their rows;
replacement values and scaling are learned within each training fold. No report-count input,
identity/location predictor, future report availability or target-period component may enter.

Compare two simple forecasts first: carry forward the latest public receipt percentage, and
average the program's earlier public receipt percentages. Then fit one regularized regression
family with three fixed input groups: receipt history; receipt history plus eligible earlier
access measures; and those same inputs plus earlier offer-acceptance measures.

The primary incremental comparison adds acceptance to history plus access. Also report both
history-based comparisons and every model against the simple forecasts on identical rows. A
gain over a weak fitted comparison is insufficient if the simple forecasts remain more accurate.
Freeze field lists, target transformation, regularization choices and training-only selection
rules after the feasibility gate and before errors are examined. Do not add model families,
donor endpoints, follow-up horizons or feature searches after seeing the comparison.

Report average absolute error in percentage points, averaged equally across eligible evaluation
origins, with signed error and origin-specific results. Include a prespecified volume-weighted
summary and whole-program paired resampling that retains each program's repeated cohorts.
Specify the minimum useful error improvement and tolerated bias change before scoring, with
a project-use rationale; neither is a clinical-benefit threshold.

## Stopping rules and evidence limits

Stop before fitting if source definitions cannot be reconciled, source dates remain unbound,
no prior published training outcome exists, or the design requires nonpublic data or overlap.
Restrict the era only for a documented source reason established before comparing errors.

Complete the fixed comparisons once. Stop development of the acceptance extension if it does
not meet the prespecified improvement requirement against the strongest simple comparison and
the model without acceptance, or if gains rely on one period or unacceptable bias. Report all
planned outcomes; do not revise the target or comparison to produce a favorable conclusion.

Historical outcomes already parsed or inspected are not untouched validation. Additional
historical periods can strengthen an exploratory investigation, but program resampling does
not establish accuracy in a new time period. Keep original V1/V2 and both completed follow-ups
unchanged. No model promotion, clinical or regulatory advice, causal interpretation, program
ranking or patient-level prediction is authorized by this plan.

## Future implementation and acceptance

After authorization, write the separate scientific specification, typed configuration, decision
record and isolated output identity before analytical implementation. No output root or new
tracked analytical release is approved here. Resolve the source-date blocker first.

Use small failing tests, then the smallest implementation, in this order:

1. Source fields and date-evidence binding, including disagreement and missing evidence.
2. Complete donor accounting, null propagation and published-versus-derived labeling.
3. Composite joins, origin-defined program populations, non-overlap and publication cutoffs.
4. Simple forecasts, training-only preprocessing and the fixed matched-row comparisons.
5. Program-level uncertainty, provenance, isolated output and preservation of original evidence.

Run focused and applicable repository checks, then reproduce the new outputs from verified
immutable inputs. Record commands, all fixed comparisons, excluded records and remaining limits
in this plan. Implementation is complete only when the new contract and its evidence agree.
