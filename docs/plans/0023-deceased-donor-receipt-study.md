# Plan 0023 — Test whether earlier acceptance predicts deceased-donor receipt

**Status:** complete, 2026-09-08 UTC; acceptance extension stops under the fixed continuation rule.
**Scope:** one separately identified exploratory study; original evidence preserved.

[Complete results](../deceased_donor_receipt_results.md): adding acceptance to history plus
access reduced average error by 0.113 percentage points (1.27%) across 218 and 217 eligible
programs. It missed both minimum improvements and did not improve the first evaluation period.
All planned comparisons are reported; no model is promoted.

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

## Implementation and acceptance

The user authorized carrying this plan through after merging Plan 0022. Work starts from
`ebd29c9` on `codex/deceased-donor-receipt-study`. The separate scientific specification,
typed configuration, decision record and isolated output identity must precede analysis.
The specified output is an ignored research run under `data/receipt-study/v1/`, with a
tracked ordinary-language results document; no new tracked analytical release is needed.
Resolve the source-date blocker before fitting. Original studies and source pins stay intact.

Use small failing tests, then the smallest implementation, in this order:

1. Source fields and date-evidence binding, including disagreement and missing evidence.
2. Complete donor accounting, null propagation and published-versus-derived labeling.
3. Composite joins, origin-defined program populations, non-overlap and publication cutoffs.
4. Simple forecasts, training-only preprocessing and the fixed matched-row comparisons.
5. Program-level uncertainty, provenance, isolated output and preservation of original evidence.

Run focused and applicable repository checks, then reproduce the new outputs from verified
immutable inputs. Record commands, all fixed comparisons, excluded records and remaining limits
in this plan. Implementation is complete only when the new contract and its evidence agree.

## Work record

| Item | Behavior and expected evidence | Status |
|---|---|---|
| S1 Contract and independent source binding | Separate specification/configuration/decision; verified release evidence rejects missing, changed or disagreeing dates and fields; source-only feasibility inventory before scores | Complete; seven releases, 91/91 value matches, 59 source tests |
| S2 Receipt accounting | Five deceased-donor components, complete living/all-status accounting, null propagation and rounding checks; first failing regression then verified-cache build | Complete; 75 tests, 100% accounting coverage |
| S3 Temporal panel | Origin-visible program universe, composite keys, non-overlapping listing cohorts, only public earlier predictors and training outcomes; additions/exits retained in QA | Complete; 25 tests, 961 retained panel rows |
| S4 Fixed comparison | Two simple forecasts before three Ridge input groups, identical rows, training-only processing, fixed error/bias thresholds, program resampling | Complete; 22 tests, all five models and nine contrasts independently checked |
| S5 Delivery and preservation | Complete six-file isolated bundle; exclusive destination reservation; bounded, link-free single-read snapshots; full provenance/schema/semantic loading; concise QA counts and complete results/limitations; independent review, full required checks and original-file preservation hashes | Complete; 33 artifact tests, trusted loading, all 48 protected files unchanged |

Documentation changes use the documented test exception and receive content/link/diff review.
New executable behaviors require the smallest failing regression first. No new dependency,
original model rerun, application change, earlier-source expansion or model promotion is planned.

### Source/design gate, before model errors

The [scientific contract](../specs/deceased-donor-receipt-0023.md),
[`experiment.yaml`](../../configs/receipt_study/experiment.yaml),
[`sources.json`](../../configs/receipt_study/sources.json) and
[Decision 0010](../decisions/0010-separate-deceased-donor-receipt-study.md) define the new study.
An independent design review resolved origin-balanced signed/volume-weighted errors,
fractional (not rounded-count) smoothing, training N rules, two-origin continuation and
bounded bootstrap redraws. All decisions precede real-data errors.

[Source review](../audits/source-binding-0023.md): seven independently bound releases and
91/91 report-to-workbook value matches. Historical source text fingerprints are explicitly
distinct from PDF-byte fingerprints. `1808` and `2006` are excluded because independent
release-bound dates could not be recovered; no scores informed this restriction. Both
evaluation origins train only on `1905→2205`. Outcome follow-up uses an explicitly labeled
conservative December 31 bound; wait-time censor dates are directly reported.

The isolated source-only CLI preflight passed: 215 eligible training rows; 218 and 217
evaluation rows. The additional `2105→2405` panel has 216 eligible rows but is unpublished
at both evaluation origins and never enters either fit. Directory populations, missing future
reports, missing outcome rows within a directory and target-only additions remain in QA.
The preflight fitted no model.

### Test-first evidence

- Fixed configuration: intended missing-module failure; NaN escaped as a plain ValueError
  before the domain-error regression was fixed. Final 10 configuration tests pass.
- Receipt accounting: intended missing-module and numeric-boundary failures, then 75 new
  passing tests; 131 including neighboring component tests. All 2,112 outcome source rows
  across nine immutable workbooks satisfy donor/status accounting; this inspected no scores.
- Source-date binding: missing-module and boundary regressions failed first; independent
  review adds exact source/pair maps, source-text value binding, changed-shape/hash rejection
  and guarded evidence paths. Seven-release verified-cache build passes.
- Temporal panel: missing-module regression, then independently reproduced mismatched
  measurement-date/identity defects; 25 tests pass with 91% module coverage at review.
- Model comparisons: missing-module regression, then 22 passing tests; the final excluded-source
  regression first demonstrated an accepted forbidden training pair. Learned coefficients,
  intercepts, imputation and scaling are saved for all six fits and invariant to held-out changes.
- Artifacts/CLI: missing-module regression, then boundary and semantic regressions demonstrated
  accepted unsafe or inconsistent bundles before fixes. Independent review found fit keys
  unbound to their enclosed model/origin and stored target transforms unbound to source
  accounting; all three failing regressions now pass. Final 33 artifact and three CLI tests pass.

`uv sync --frozen` passed (74 packages). Focused work uses separate test temporary directories.
These counts are intermediate evidence, not substitutes for final repository verification.

### Comparison freeze — 2026-09-08 04:07:51 UTC

At this freeze, no real-data models had been fitted or scored. Source, accounting, temporal, model and CLI
pre-fit checks: **194 passed**. Independent reviews found no remaining scientific mismatch.
The following identities fix the comparisons and source-based exclusions before scoring:

| Contract file | SHA-256 |
|---|---|
| `configs/receipt_study/experiment.yaml` | `adc6b4196670c0ac91b78021acbe3c982b4df933e9e860376fc667916713a9ec` |
| `configs/receipt_study/sources.json` | `4813ae2a67ae8b4d128bb8e33681f9a6a3f81eb09ebe37e40739c19980c7ab79` |
| `docs/specs/deceased-donor-receipt-0023.md` | `e473208f4154086455b7d0d4b64e49b113bb5b11ff2f653633a3e7a8ee7251b7` |

After output verification passes, `uv run kasm patient-journey receipt-study` is authorized
to complete this fixed retrospective comparison. Do not change the contract based on its errors.
The builder records the exact implementation/lock hashes and current Git identity separately;
the user has not requested a commit. Original study commands are not part of this evaluation.

The temporary Git object/filter regression reproduced changed hashes under Windows automatic
line-ending conversion. Explicit LF attributes fixed it; all 12 repository-configuration tests
pass, and these three frozen file hashes remained unchanged through completion.

### Final verification and execution

All checks below passed before the first real-data fit:

| Command | Evidence |
|---|---|
| `uv sync --frozen` | 74 packages, no dependency or lock changes |
| `uv run ruff format --check .` | 93 files already formatted |
| `uv run ruff check .` | All checks passed, including configured security rules |
| `uv run mypy src/kasm` | No issues in 45 source files |
| Required full `uv run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling --cov=src/kasm/reporting --cov=src/kasm/patient_journey --cov-branch --cov-fail-under=80` | 722 passed; 85.08% coverage |
| `uv run coverage report --include="src/kasm/patient_journey/*" --fail-under=80 --precision=2` | 85.29%, gate passed |
| `uv run kasm data verify-cache` | Nine immutable sources, zero issues |

The initial full test run had 15 Windows path-length failures in existing V1 fixture paths
(707 passed). Repeating with a fresh short `$env:TEMP/k23-*` `--basetemp` resolved all failures;
no production or test changes were needed. `MPLCONFIGDIR` was set to the writable local cache
for tests. The study command's omitted setting produced only a Matplotlib cache fallback notice;
it completed successfully and the reproduction instructions set the variable explicitly.

`uv run kasm patient-journey receipt-study` completed the fixed study once at
`2026-09-08T04:23:14.846199+00:00`, including isolated build and trusted loading. Output:
`data/receipt-study/v1/3bca655e1de9580167edd017af62c63bcc1fa9c20fdd4dbfeed0a41d9ad2832e/`.
Six payloads plus manifest/completion total 377,445 bytes: 961 panel rows, 1,638 source-accounting
rows and 2,175 predictions. Manifest SHA-256:
`a9fac0c6342d560a8d63fd2ea92e8f507305150534e7c4f24ec101fe81396b49`.
Base Git identity is `ebd29c9fdd46017a40966c2b75ef38b5e1fbc4d7`; the uncommitted build is explicitly
noncanonical, with exact production-file hashes. No commit was requested or created.

The saved result passed trusted reloading without fitting. A separate agent independently
recomputed all primary, signed, origin-specific and volume-weighted summaries, both N20/N30
sensitivities, and all nine 2,000-draw bootstrap intervals from the saved predictions. Every
value matched within 1e-10; no resampling draw was rejected. The three continuation failures
exactly match the fixed rule: below 0.5 points, below 5%, and no first-origin improvement over
history plus access. No contract, feature, model or population choice changed after scoring.

Original configuration, application, released artifacts, patient-journey implementation and
dependency lock were checked against the 48-file preservation snapshot: zero differences.
The new result remains under the approved ignored root. No original study was refitted, no
application changed, and no presentation or container change required additional rendering or
build checks. Final prose changes use content/link review and `git diff --check` rather than
repeating the Python suite.

Final documentation review checked 86 local links with none broken, and `git diff --check`
passed. The independent results review verified all stated numbers and fingerprints and caught
one omitted reproduction prerequisite; the instructions now explicitly require the pinned
July 2026 PDF as well as cached workbooks and saved source text. No study input drift was found
when comparing every recorded production/configuration/lock identity after documentation edits.

Remaining evidence limits are scientific, not unfinished implementation: two evaluation periods
share one earlier training cohort; historical report dates rely on preserved cached text;
`1808` and `2006` remain excluded; missing future outcomes remain unknown; and the previously
inspected historical sources cannot provide fresh validation. The
[results record](../deceased_donor_receipt_results.md) contains every comparison, the complete
decision, population accounting, exact provenance and offline reproduction/loading commands.
