# Patient-journey V2 data card

## Intended use

This V2 dataset supports a retrospective, program-level exploration of a published patient-journey
outcome and related public program context. It is suitable for research demonstration and
quality-improvement review. It is not patient-level data, clinical decision support, regulatory
evidence, a national center leaderboard, or a causal analysis.

The modeling unit is a kidney transplant program and target cohort, identified by the composite
`(CTR_CD, CTR_TY)` key. Center name and location are preserved only for display and are rejected by
the model feature allowlist.

## Sources and outcome

Nine immutable, checksum-pinned SRTR Program-Specific Report releases from `1808` through `2605`
are defined in `configs/data_sources.yaml`. The release-specific sheets, machine fields,
publication precision, measurement windows, denominators, method notes, and source citations are
defined in `configs/patient_journey_v2/methodology.yaml`.

The target is the published Table B6/B7 field `SAL_TOTFTX_C18`: the observed percentage of listed
candidates known alive with a functioning transplant at 18 months. The published percentage is
authoritative. `SAL_N_C` is used only for rounding reconciliation, eligibility, and the boundary-safe
empirical-logit transform. This target is not an officially risk-adjusted measure.

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
