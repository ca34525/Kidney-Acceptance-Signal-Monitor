# Patient-journey V2 data card

## Intended use

This V2 dataset supports a retrospective, program-level exploration of a published patient-journey
outcome and related public program context. It is suitable for research demonstration and
quality-improvement review. It is not patient-level data, clinical decision support, regulatory
evidence, a national center leaderboard, or a causal analysis.

The modeling unit is a kidney transplant program and target cohort, identified by the composite
`(CTR_CD, CTR_TY)` key. Center name and location are preserved only for display and are rejected by
the model feature allowlist.

**Reading note, 2026-09-05:** One record represents one program and one group of candidates listed
during the stated dates. A program can appear for more than one listing group. These are summaries
of those groups, not individual candidate records. This card retains the original V2 release;
the separately planned follow-up has no revised result here.

## Sources and outcome

Nine immutable, checksum-pinned SRTR Program-Specific Report releases from `1808` through `2605`
are defined in `configs/data_sources.yaml`. The release-specific sheets, machine fields,
publication precision, measurement windows, denominators, method notes, and source citations are
defined in `configs/patient_journey_v2/methodology.yaml`.

The target is the published Table B6/B7 field `SAL_TOTFTX_C18`: the observed percentage of listed
candidates known alive with a functioning transplant at 18 months. The published percentage is
authoritative. `SAL_N_C` is used only for rounding reconciliation, eligibility, and the boundary-safe
empirical-logit transform. This target is not an officially risk-adjusted measure.

The denominator is the original listing group (`SAL_N_C`), not only people who received a
transplant. The numerator concerns those known alive with a functioning transplant 18 months after
listing. For example, a hypothetical reported value of 40% means 40 of each 100 listed candidates
are recorded in that status. It does not establish what happened to candidates whose status is
unknown. The original panel retains the published total and does not yet separate its donor-type
or unknown-status components.

**Use-of-count correction, 2026-09-05:** The word "only" in the preceding original description of
`SAL_N_C` is too narrow. Counts also support volume summaries and the available-cohort reference;
the prior report's count enters Ridge as `log1p_prior_target_n`. Target counts determine eligibility,
volume groups, and volume-weighted evaluation, but are not future predictor inputs. These roles
are fixed in the [original specification](specs/patient-journey-v2.md#7-models-and-evaluation) and
[experiment configuration](../configs/patient_journey_v2/experiment.yaml). The available-cohort
reference pools reconstructed success counts as expressly specified for that baseline. Those
counts and the resulting reference are calculations, not published national statistics, and do
not replace the authoritative published target percentage.

The empirical-logit transform is a calculation used for fitting a percentage outcome. It applies
the fixed small adjustment in the specification so reported 0% and 100% values stay finite on a
log-odds scale. Evaluation returns to the original published percentage scale.

Four nonoverlapping primary feature-to-target pairs are pinned:

| Feature release | Target release | Target listing cohort |
|---|---|---|
| `1905` | `2205` | 2019-07-01 to 2020-06-30 |
| `2006` | `2305` | 2020-07-01 to 2021-06-30 |
| `2105` | `2405` | 2021-07-01 to 2022-06-30 |
| `2205` | `2505` | 2022-07-01 to 2023-06-30 |

The `1808→2105` candidate is excluded because the prediction origin is more than one month after
target-cohort start. The `2305→2605` candidate is excluded because the target cohort overlaps the
preceding primary cohort.

## Contents

Primary rows are the rows eligible for the main evaluation. Sensitivity rows repeat the evaluation
with the two fixed larger candidate-count cutoffs; they are subsets, not extra observations.

The current processed bundle contains 966 program-pair rows:

- 865 primary rows with a published target, prior target, and target candidate count at least 10;
- 815 sensitivity rows at target `N ≥ 20`;
- 758 sensitivity rows at target `N ≥ 30`;
- 47 rows with no published target, retained as missing rather than recoded as a negative outcome;
- 48 rows below the primary target-volume threshold; and
- 6 rows without a prior target.

The separate safety table contains 5,678 published program-measure rows:

| Family | Rows | First pinned availability | Interpretation |
|---|---:|---|---|
| Waiting-list mortality | 1,902 | `1905` | Lower ratio means a lower published event rate relative to expected |
| Mortality after listing | 1,432 | `2105` | Lower ratio means a lower published event rate relative to expected |
| 90-day graft failure | 1,172 | `2205` | Lower ratio means a lower published event rate relative to expected |
| One-year graft failure conditional on day 90 | 1,172 | `2205` | Lower ratio means a lower published event rate relative to expected |

Each safety family retains its own population, event definition, denominator, measurement and
follow-up dates, source release, published ratio, and 95% Bayesian credible interval. Safety context
is not interchangeable with the patient-journey outcome and is never combined into a score. Only
waiting-list mortality is available at both vintages required by the prespecified secondary Ridge
feature group.

Waiting-list mortality and mortality after listing use candidate person-years, meaning the total
time the relevant candidates contribute to each source's follow-up. The graft-failure measures
count adult single-organ kidney recipients: the 90-day measure starts at transplant, whereas the
conditional one-year measure concerns recipients whose graft is functioning at day 90. A lower
ratio means fewer reported events relative to that measure's expectation. None uses the Table B7
listing denominator as an interchangeable total.

## Missingness and validation

Missing and suppressed source values remain null. They are never converted to zero. Text such as
“Not Observed,” `>72`, hyphens, and blanks remains missing. Future report absence creates a missing
target. Program entry and exit are preserved.

Parsing uses machine field names, exact sheet contracts, composite identity, source file hashes,
safe archive handling, count and interval invariants, and release-specific date handling. The
`2105` source replay established two important real-source behaviors: mortality-after-listing dates
use `MM/DD/YYYY`, and a valid safety program may be absent from the same-release Tiers sheet.

## Provenance and limitations

### Current published bundle

The tracked release contains 966 panel rows and 5,678 safety rows. Its four payload files total
679,407 bytes with bundle content SHA-256
`ce2844edbcec92c09d0053720d5331dd37ed43ab75de7aa4dd1de431c79a9eee`.
The [release manifest](../artifacts/patient_journey_v2/release_manifest.json) records source commit
`cdea5c40302de1797d83698566d2ebb51de16938`, `canonical_build: true`,
`git_worktree_dirty: false`, and build time `2026-09-04T22:40:05.364170Z`.
[Plan 0019](plans/0019-patient-journey-v2-completion.md) records publication at `0353f99`.

### Earlier development bundle retained as history

The earlier workspace development release contained 966 panel rows and 5,678 safety rows. Its
payload was 679,407 bytes with bundle content SHA-256
`6542fc61968b4cda95a33dcb5057b41b37d6fc3ba5ad40397ee8e7a1ed2cc205`.

That development artifact was generated at Git commit
`9357a33f96a19b4024d222a526e696b297740738` while the worktree contained the uncommitted V2
implementation. Its manifest recorded `canonical_build: false` and
`git_worktree_dirty: true`. It is retained here as the earlier build record, not the current
published bundle.

### Interpretation and planned follow-up

[Plan 0020](plans/0020-v2-follow-up-and-interview-story.md) proposes a separate investigation of
the report-count input and the living/deceased-donor and unknown-status parts of the outcome.
Those additional components are not yet included in this original V2 panel. The existing published
target and results remain unchanged.

Aggregate program measures cannot support patient-level inference or fairness claims. Measurement
definitions and policy context vary by release, including COVID-era exclusions and allocation
changes recorded in the methodology ledger. Published credible intervals describe their own SRTR
measures; they are not forecast intervals.
