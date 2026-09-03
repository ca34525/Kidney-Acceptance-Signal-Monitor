# Model card — Kidney Acceptance Signal Monitor

**Model-card version:** 1.0
**Frozen replay date:** 2026-09-03
**Activation status:** `attempted_not_promoted`
**Displayed projection:** persistence

## Intended use

This model is a public-data screening signal for transplant-program quality-improvement review.
It projects the next same-cadence calendar-year published offer-acceptance ratio from earlier public
program aggregates. It does not evaluate offers, patients, clinical decisions, regulatory status,
or causal effects.

The modeling unit is one kidney transplant program-year. The target is the next-calendar-year
published `log(OAR)`. The 2025 result below is a frozen retrospective implementation replay and
descriptive product-selection evidence, not prospective or independent validation.

## Data and feature contract

The panel contains non-overlapping calendar-year cohorts from the nine checksum-pinned SRTR
releases covering 2017–2025. Program identity is `(CTR_CD, CTR_TY)`. The model never receives
program code, type, name, location, OPO/DSA identity, cohort year, future report availability, or
target-period values.

The 17 prespecified inputs are current and previous annual overall log OAR, their one-year change,
log expected acceptances, log credible-interval width, four current donor-stratum log OARs, two
offer-share measures, and six corresponding lag/subgroup missingness indicators. KDPI ≥60 is not a
model feature. Median imputation and standardization are fit inside each training fold.

## Temporal evaluation and model selection

Neutral, persistence, and historical-mean baselines were implemented before ridge. Ridge alpha
was selected from `[0.01, 0.1, 1, 10, 100]` using the unweighted mean of per-target-year log-OAR
MAEs for rolling target years 2021–2023, with the larger alpha chosen when scores were within 1%.
Alpha 10 was frozen.

Across pre-replay target years 2021–2024, ridge improved on persistence in all four years and had
5.47% year-balanced log-OAR MAE skill. It passed the pre-replay candidate gate. The nominal 80%
marginal band radii were then frozen from the 229 held-out 2024 residuals: 0.3842946 log-OAR units
for ridge and 0.4054651 for persistence.

The 2025 replay ridge fit used analytic target years 2018–2023 only. Target-year 2024 outcomes did
not enter model fitting; they were used only for the already frozen band calibration.

## Frozen 2025 replay result

The replay included 229 analytic programs.

| Measure | Ridge | Persistence |
|---|---:|---:|
| MAE, log OAR | 0.2399 | 0.2670 |
| MAE, OAR scale | 0.2398 | 0.2666 |
| Mean signed log error | -0.01145 | -0.00885 |
| Calibration slope | 0.795 | 0.673 |
| Nominal-band coverage | 81.66% | 79.04% |
| Mean band width, OAR scale | 0.7870 | 0.8740 |

Ridge's log-OAR MAE was 10.13% lower than persistence. The frozen 10,000-resample paired
program-key bootstrap interval for `ridge absolute error − persistence absolute error` was
`[-0.04087, -0.01332]`, with an observed mean difference of -0.02705.

### Point-promotion decision

| Frozen criterion | Evidence | Result |
|---|---|---|
| At least 5% MAE skill over persistence | 10.13% | pass |
| Paired-bootstrap interval lies below zero | upper bound -0.01332 | pass |
| Absolute mean signed log error ≤0.05 | 0.01145 | pass |
| Absolute bias no greater than persistence | 0.01145 vs 0.00885 | **fail** |
| Lowest-quartile MAE ≤1.10 × persistence with at least 30 rows | 0.3140 vs 0.3463; n=58 | pass |

Because every criterion was required, ridge was not promoted. Persistence remains the displayed
projection. The result is recorded as `attempted_not_promoted`; the favorable error difference is
reported without overriding the prespecified bias safeguard.

### Separate empirical-band decision

Ridge's frozen band covered 187 of 229 replay outcomes (81.66%). Its two-sided 95% exact binomial
interval was 76.03%–86.45%, which includes the nominal 80% rate. Its mean OAR-scale width was
90.05% of the persistence-band width, so the statistical band gate passed.

This gate is kept separate from the point gate. A passing ridge-band gate does not expose a ridge
band when the ridge point model was not promoted; the effective release decision suppresses that
ridge output. The historical SRTR 95% credible intervals remain distinct from any empirical
forecast band.

## Expected-acceptance quartiles

Quartiles were assigned within target year 2025 by deterministic rank of feature-period expected
acceptances, with program key as the tie-breaker.

| Quartile | n | Ridge log MAE | Persistence log MAE | Ridge skill | Ridge band coverage |
|---:|---:|---:|---:|---:|---:|
| 1 (lowest) | 58 | 0.3140 | 0.3463 | 9.32% | 68.97% |
| 2 | 57 | 0.2514 | 0.2813 | 10.60% | 80.70% |
| 3 | 57 | 0.2076 | 0.2270 | 8.53% | 87.72% |
| 4 (highest) | 57 | 0.1852 | 0.2118 | 12.57% | 89.47% |

The lowest-quartile coverage estimate is imprecise: its exact 95% interval is 55.46%–80.46%.
The nominal band is marginal across programs, not a conditional guarantee for a center or volume
quartile.

## Prespecified diagnostics and sensitivities

Thirty replay rows had at least one prespecified missing predictor; ridge skill was 7.26% in that
group. The other 199 rows had 10.65% skill. Only one replay row was a first-observed program, so
its result is not interpreted; first-observed programs remain ineligible for a public forecast.

Both drift sensitivities retained lower ridge MAE than persistence:

| Sensitivity fit | Ridge log MAE | Skill over persistence |
|---|---:|---:|
| Exclude transitions touching cohort 2020 | 0.2345 | 12.16% |
| Exclude transitions touching cohort 2021 | 0.2462 | 7.76% |

These exclusions are drift checks, not causal analyses. Calendar year 2023 is a mixed
offer-acceptance monitoring context because the metric took effect on 2023-07-27; 2024 and 2025
are full post-policy cohorts, but there are too few to fit or validate a separate era model.

## Limitations

- The target is a delayed published program aggregate, not a latent quality measure or real-time
  outcome.
- Published SRTR OARs and credible intervals are authoritative; formula recreation is only a
  rounding-range QA diagnostic.
- Repeated programs across years are intentional, but the replay remains one retrospective year.
- The bootstrap interval is descriptive and resamples programs; it is not a confirmatory p-value.
- Empirical-band coverage is marginal and may change under drift.
- There is no patient-level fairness, clinical-benefit, causal, or regulatory claim.
- A genuinely prospective assessment requires the later calendar-year 2026 PSR signal.

## Reproduction and provenance

The canonical command is:

```powershell
uv run kasm data verify-cache
uv run kasm data build
uv run kasm model backtest
uv run kasm model evaluate-frozen-replay --confirm
```

The write-once output directory is keyed by the full hashes below and contains replay predictions,
metrics, and a completion ledger:

- Frozen config SHA-256: `7b25737b054973386379088ccf27b66bfc9d5fd325dc4969d8449c80867f1ff1`
- Source manifest SHA-256: `5b30cd508a10e9cc24a6097f0eea868447c168b2744b50977aa56db43a6b86e5`
- Input panel SHA-256: `00e1c6e14e0afdb9330022ac773eefaf1e3132edd24212e881967a2cc5a6c174`
- Frozen configuration commit: `2a5b52402875ab9d5542b38d6c2155027c09ba97`

The local completion ledger also records that the worktree contained the replay implementation
changes at execution time. The artifact includes the dependency-lock hash, feature-schema hash,
all source hashes, UTC build time, cohort roles, fixed model parameters, and a per-release
methodology ledger.

The tracked offline bundle is generated from those canonical artifacts with:

```powershell
uv run kasm artifacts build
```

Its manifest binds all 12 approved payloads to their canonical byte size and SHA-256, preserves
the complete replay provenance envelope and SRTR attribution, and enforces a total size below
5 MiB. Bundle content SHA-256 is
`1de89083ceebfda9afaf2d6b1c6ba3f1e6d0c1a1da16df9d09d994c4ec3581ad`. Packaging does not refit,
retune, reinterpret, or overwrite the frozen replay.
