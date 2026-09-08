# Kidney Acceptance Signal Monitor — Project roadmap

**Latest completed work:** [Plan 0026 — waiting-list case study](docs/plans/0026-waiting-list-case-study.md).
The original frequency finding is reproduced. Median signed transplant-removal changes among
all growing-list programs were +2, 0 and −2 events in 2023–2025; among programs with increases,
they were +15, +12 and +8. Three fixed examples reconcile annual growth and its change from the
preceding year. The [case study](docs/waiting_list_case_study.md) includes offline HTML briefs,
three figures, supporting tables and reproduction commands. C0–C3 are complete; no new execution
plan is active. Application integration would require a separate decision.

**Previously completed work:** [Plan 0025 — waiting-list viability](docs/plans/0025-waiting-list-viability.md).
The fixed descriptive screen supports continuing this direction: 52.8%, 47.4% and 42.3% of
eligible growing-list programs also recorded increased transplant removals in 2023–2025.
The count, relative-size, common-program and size-group rules passed. See the
[recommendation](docs/waiting_list_viability_results.md). Any next study needs a separate
decision; no new model or application change is authorized by this finding.

**Previously completed work:** [Plan 0023 — deceased-donor receipt study](docs/plans/0023-deceased-donor-receipt-study.md).
Adding acceptance to receipt history and access reduced average error by 0.113 percentage
points (1.27%), missing the fixed continuation rule. Development of this acceptance extension
stops; no model is promoted. The released V1 monitor, original V2 study and both completed
follow-ups remain unchanged. See the [complete results](docs/deceased_donor_receipt_results.md).

Start with [the project guide](docs/project-guide.md) for the questions and findings. Use
[AGENTS.md](AGENTS.md) for implementation and verification rules, [SPEC.md](SPEC.md) for the
V1 contract, and the applicable study specification/configuration for later work.

## Current and proposed work

| Work | Status | Record |
|---|---|---|
| Waiting-list analytical case study | Complete; distributions, worked examples and reusable offline program briefs | [Plan 0026](docs/plans/0026-waiting-list-case-study.md), [case study](docs/waiting_list_case_study.md) |
| Waiting-list changes and operational interpretation | Complete; fixed descriptive continuation rule passed | [Plan 0025](docs/plans/0025-waiting-list-viability.md), [recommendation](docs/waiting_list_viability_results.md) |
| Source coverage, repository cleanup and consequential review | Complete; original source-date error documented | [Plan 0022](docs/plans/0022-source-and-cleanup-audit.md) |
| Deceased-donor transplant receipt study | Complete; fixed acceptance continuation rule failed | [Plan 0023](docs/plans/0023-deceased-donor-receipt-study.md), [results](docs/deceased_donor_receipt_results.md) |
| Earlier candidate characteristics study | Deferred; unimplemented and outside the viability screen | [Plan 0024](docs/plans/0024-candidate-mix-study.md) |
| Project presentation | Packages prepared; source-date correction and author rehearsal remain | [Current walkthrough](docs/presentation/data-walkthrough/README.md), [Plan 0020 P4](docs/plans/0020-v2-follow-up-and-interview-story.md#p4-build-the-explanation-and-interview-package) |

Each proposed analysis needs its own approved specification and fixed configuration before
fitting begins. Previously inspected outcomes cannot become fresh validation. The original
studies retain their input, output and claim boundaries; original V2 permits no model promotion.

## Completed work and evidence

These records describe the revisions checked at the time. Their test counts and build results
are historical evidence, not claims about a new verification run.

| Milestones | Delivered behavior | Evidence |
|---|---|---|
| M0–M1: scaffold and acquisition | Locked environment, quality gates and nine immutable verified sources | [Plan 0001](docs/plans/0001-repository-scaffold-and-cache-verification.md), [Plan 0002](docs/plans/0002-verified-atomic-source-sync.md) |
| M1–M2: parsing and annual panel | 2,103 program-years, 10,515 validated signal rows and deterministic Parquet/QA | [Plan 0003](docs/plans/0003-schema-aware-workbook-parser.md), [Plan 0004](docs/plans/0004-canonical-panel-and-qa.md) |
| M2–M3: historical service and baselines | Offline history and temporal evaluation; 2,763 paired baseline predictions; persistence selection MAE 0.3415 on log OAR | [Plan 0005](docs/plans/0005-historical-service-and-walking-skeleton.md), [Plan 0006](docs/plans/0006-ci-pytest-fresh-checkout.md), [Plan 0007](docs/plans/0007-baseline-temporal-backtest.md) |
| M4: Ridge and frozen replay | 229-program descriptive replay; Ridge failed the fixed bias rule and persistence remained displayed | [Plan 0008](docs/plans/0008-ridge-pre-replay-backtest.md), [Plan 0009](docs/plans/0009-pre-replay-activation-freeze.md), [Plan 0010](docs/plans/0010-frozen-2025-replay.md), [model card](docs/model_card.md) |
| M5–M6: offline release | Program flow, explicit eligibility, band suppression, 1.23 MB bundle and non-root container; clean reproduction and CI at `2c815688` | [Plan 0011](docs/plans/0011-offline-product-flow.md), [Plan 0012](docs/plans/0012-release-hardening-and-container.md) |
| M7: original V1 presentation | Eight-slide deck and backup package at `dc34b3a`; a release tag remains a separate uncompleted action | [Plan 0013](docs/plans/0013-interview-presentation-package.md) |
| M8: implementation hardening | Source-boundary regressions, security/complexity lint and focused retrieval guidance | [Plan 0014](docs/plans/0014-ai-code-and-context-hardening.md) |
| M9–M12: V2 data foundation | Separate typed contract, release-level methodology ledger, four non-overlapping pairs and a 966-row panel | [Plan 0015](docs/plans/0015-patient-journey-v2-foundation.md), [Plan 0016](docs/plans/0016-patient-journey-ledger-and-parser.md), [Plan 0017](docs/plans/0017-patient-journey-temporal-panel.md), [Plan 0018](docs/plans/0018-patient-journey-artifact-publication.md) |
| M13: original V2 study | 679 KB offline research bundle built from `cdea5c4`, published at `0353f99`; one configured Ridge evaluation period and no promotion | [Plan 0019](docs/plans/0019-patient-journey-v2-completion.md), [V2 model card](docs/patient_journey_v2_model_card.md) |
| M14: V2 follow-ups | Report-count diagnosis and outcome-component description complete; original results preserved | [Plan 0020](docs/plans/0020-v2-follow-up-and-interview-story.md), [report-count results](docs/patient_journey_v2_followup_results.md), [component results](docs/patient_journey_v2_component_results.md) |
| Cross-study hardening | Six audit findings fixed; local and CI container verification at `5f26ec9` | [Plan 0021](docs/plans/0021-focused-ai-coding-hardening.md), [audit](docs/ai-code-and-context-audit.md) |

The report-count follow-up reduced history-only Ridge's average error from 11.49 to 7.32
percentage points, leaving a 0.09-point acceptance improvement on the same 218 programs.
The matched component study found a median 16.05% of the original listing group with unknown
post-transplant status. That is a program median, not a pooled patient percentage or an
explanation of prediction error. Both follow-ups describe already-inspected outcomes.

## Maintenance boundaries

Reproduction starts from the verified immutable cache. Source refresh is a separate maintenance
action; a new hash or schema requires review. The V1 frozen replay is write-once and is not an
ordinary verification command. Follow [the reproduction log](docs/reproduction_log.md) and the
applicable study's instructions rather than rerunning it during cleanup.

A model's failure to pass a display rule is evidence about that prediction rule, not clinical
safety. The historical monitor remains the released product. Preserve the exact dates,
denominators, missing-value meanings and original evidence when explaining or extending it.

The original seven-day execution schedule has been retired from this current roadmap. Its
implementation choices and completion evidence remain in Plans 0001–0013 and Git history.
