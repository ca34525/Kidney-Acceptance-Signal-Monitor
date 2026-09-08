# V1 forecast improvement — completed retrospective comparison

September 8, 2026. [Plan 0027](plans/0027-v1-forecast-improvement.md),
[study contract](specs/acceptance-forecast-0027.md),
[fixed design](decisions/0014-fix-forecast-comparison-0027.md).

**Recommendation:** select the fitted adjustment of the latest published ratio for a future
point projection, and withhold its forecast band. It reduced average absolute log error by
6.90% versus persistence and passed every fixed point criterion. Its advantage over full Ridge
was only 0.66%; this comparison does not establish a meaningful superiority over Ridge.
The current application still displays persistence. The separate
[deployment handoff](plans/0028-v1-point-projection-release.md) is defined but not implemented.

This is a public aggregate screening signal for quality-improvement review, not clinical or
regulatory decision support. Every evaluated historical year had already been inspected.
The findings are exploratory development evidence, not prospective or independent validation.

## What was counted

One record is a kidney transplant program, identified by center code **and** center type,
and its next non-overlapping calendar-year published offer-acceptance ratio (OAR). OAR compares
accepted offers with SRTR's risk-adjusted expectation; it is not an acceptance percentage.
There are 1,150 observed program-years from 236 programs across 2021–2025. All five methods use
the same rows. Eleven missing later reports are exclusions, never zero or negative outcomes.

| Target calendar year | Earlier-report program rows | Observed targets | Missing targets | Observed targets eligible for public display |
|---|---:|---:|---:|---:|
| 2021 | 233 | 230 | 3 | 227 |
| 2022 | 232 | 230 | 2 | 229 |
| 2023 | 234 | 232 | 2 | 229 |
| 2024 | 232 | 229 | 3 | 229 |
| 2025 | 230 | 229 | 1 | 228 |

The eight analytic first-observed program-years remain in the analysis and have their public
forecast withheld. Their small numbers cannot support a new display rule. The saved artifact's
eligibility flag is retained; no view decides eligibility from its own calculations.

Feature reports were published in July 2021–July 2025; outcomes in July 2022–July 2026.
Month-only dates retain month precision. For example, the 2025 projection originates at the
July 8, 2025 release describing calendar 2024, after about half of target 2025 had elapsed;
its truth is published July 7, 2026. This is a delayed-report nowcast.

## What the original saved errors showed

No original model was refitted for this diagnosis. Its 2021–2023 predictions participated in
alpha selection; 2024 was validation and band calibration; the original 2025 frozen fit used
training outcomes only through 2023. Combined descriptive means mix those stated roles.

For the saved Ridge forecasts, a typical miss was about 19%–32% of the published target ratio.
The largest tenth were much larger, especially in 2022. These are relative errors, not percentage
points. Hypothetically, predicting 1.00 for a reported ratio of 0.80 is 0.20 ratio units or 25%
too high; predicting 0.80 for 1.00 is 20% too low.

| Year | Median absolute ratio-unit error | Median absolute percentage error | 90th-percentile absolute percentage error | Predictions within ±25% of published ratio |
|---|---:|---:|---:|---:|
| 2021 | 0.216 | 22.8% | 70.8% | 53.9% |
| 2022 | 0.310 | 32.3% | 117.3% | 40.9% |
| 2023 | 0.189 | 22.0% | 57.0% | 57.3% |
| 2024 | 0.182 | 20.4% | 50.3% | 60.7% |
| 2025 original replay | 0.172 | 18.9% | 53.0% | 64.2% |

Saved Ridge improved absolute log error on a year-balanced 60.7% of program-years and worsened
it on 39.3%, with no exact ties. In the original 2025 replay the counts were 150 improvements
and 79 worsenings. The year-balanced mean absolute log error was 0.352 in the lowest earlier
expected-acceptance quartile and 0.231 in the highest. For earlier ratios below 0.5 it was 0.358,
versus 0.273 for ratios from 1 to below 2. These are associations with earlier characteristics,
not explanations of causes. A small published target can also make a percentage miss large.

The [saved-error percentage figure](../data/research/acceptance-forecast-0027/diagnostics-final/error_distributions_percentage.png)
keeps the full range. The [complete diagnostic tables](../data/research/acceptance-forecast-0027/diagnostics-final/report.json)
contain signed means/medians, middle 80% intervals, absolute means/medians, 90th/95th percentiles,
minima/maxima, ±10/25/50% counts, paired changes and earlier-volume/ratio/missingness groups.
Pooled quantiles are explicitly secondary and do not treat repeated rows as independent programs.

## The fixed five-method comparison

After diagnosis, two alternatives were fixed before scoring: fit a slope and intercept using
only the latest log ratio, or shorten full Ridge's training history to three target years.
Persistence, historical mean and full Ridge remain references. Every Ridge fit uses alpha 10,
inherited from the original inspected selection; no new tuning or search was performed.

All fitted methods learn only from outcomes published by each origin, and imputation and scaling
learn only from that training subset. Full-history methods expand from target 2018 through the
previous target year. Thus the **new** 2025 fit includes target 2024, unlike the preserved frozen
replay. Comparisons below share that new information design; extra training information is not
credited as an algorithmic improvement. Each band's radius comes from the same procedure's
preceding-year out-of-sample predictions, starting with a separate 2020 warmup.

Mean absolute error (MAE) is the average size of a miss, ignoring direction. Each year has equal
weight in the following table, and each observed program has equal weight within its year.

| Method | Mean absolute log error | Improvement over persistence | Mean absolute ratio-unit error | Mean signed log error | Fixed point criteria |
|---|---:|---:|---:|---:|---|
| Persistence: reuse latest ratio | 0.31420 | Reference | 0.34000 | +0.02366 | Reference |
| Historical mean of earlier log ratios | 0.39595 | −26.02% | 0.43596 | +0.10394 | Reference |
| Full Ridge, expanding history | 0.29447 | 6.28% | 0.31500 | +0.01597 | Pass |
| Full Ridge, most recent three years | 0.29669 | 5.57% | 0.31643 | +0.01211 | Pass |
| **Fitted adjustment of latest ratio** | **0.29252** | **6.90%** | **0.30872** | **+0.01312** | **Pass; selected by lowest primary error** |

The selected procedure's mean ratio-unit error was 9.20% lower than persistence's. Its mean
absolute percentage error was 32.3%, compared with 34.9%. The proportion within ±25% increased
from 52.3% to 55.5%; those diagnostic tolerances were not used as promotion thresholds.

The selected procedure improves absolute log error on 59.9% of program-years and worsens it
on 40.1%, with no exact ties. Its year-balanced fraction with a worsening exceeding 0.25 log
units is 0.70%, below the fixed 10% ceiling. This does not make every projection reliable.

| Year | Persistence log MAE | Selected log MAE | Selected median relative miss | Selected worst-tenth boundary | Selected within ±25% |
|---|---:|---:|---:|---:|---:|
| 2021 | 0.30632 | 0.30754 | 22.7% | 72.2% | 54.8% |
| 2022 | 0.43479 | 0.39534 | 30.7% | 116.6% | 40.9% |
| 2023 | 0.28349 | 0.26527 | 21.2% | 55.0% | 57.3% |
| 2024 | 0.27947 | 0.26223 | 22.6% | 54.5% | 59.4% |
| 2025 new fit | 0.26695 | 0.23220 | 18.1% | 48.8% | 65.1% |

The small 2021 worsening is 0.40%, below the fixed 10% allowance. Four of five years improve.
All adequately sized earlier-characteristic group cells pass the mean-error rule. The selected
method's largest yearly signed log bias is +0.13325 in 2022, under the pre-scoring 0.15 drift
ceiling but still material. Its mean of yearly 90th-percentile absolute log errors is 0.59460,
within the fixed tolerance. Small cells and public-ineligible rows remain separately reported.

Whole-program paired resampling gives a descriptive 95% interval of **[−0.02571, −0.01761] log
units** for selected-method minus persistence mean absolute error. All 10,000 draws retained
the required years; the 236 programs were sampled with all their observed years together.
The interval describes variation across these programs, not performance in a new year or the
uncertainty from choosing the methods after inspecting history. No new comparison interval
against Ridge was specified; the 0.00196 log-unit advantage over it should not be overstated.

The [full comparison figure](../data/research/acceptance-forecast-0027/comparison-v1/error_distributions_log.png)
shows the full log-error distributions. [All comparison tables and fitted parameters](../data/research/acceptance-forecast-0027/comparison-v1/report.json)
retain every method, every year, ratio/percentage distributions, calibration, paired losses,
group checks and unsuccessful band criteria.

## Why the band remains withheld

Point accuracy does not establish a useful forecast range. The selected method's empirical
band covers 77.4%, 75.2%, 92.7%, 79.5% and 85.6% of outcomes in 2021–2025. Its 2023 and 2025
overall exact intervals exclude the nominal 80% on the high side, while some 2022 groups have
too little coverage. For example, the second earlier-volume quartile covers 61.4% of 57 programs,
with a 95% interval of 47.6%–74.0%. A range can be too broad in one period and too narrow in
another group. Mean width passes its separate limit, but coverage fails. All three fitted
candidates fail their band criteria. No displayed nominal 80% band is recommended.

These empirical ranges predict a later published ratio. They are distinct from SRTR's
published credible intervals for the current ratio and may never share a label.

## Original decision and new recommendation

| Evidence identity | Decision |
|---|---|
| Original frozen 2025 replay; fit through target 2023 | Retain persistence. Ridge failed the exact absolute-bias comparison: 0.01145 versus 0.00885. |
| Plan 0027 comparison v1; expanding fits through each previous year | Full Ridge and both alternatives pass revised point criteria. Select the fitted adjustment by the fixed lowest-error rule; withhold its band. |
| Current released application | Continue persistence until the separate trusted release and offline application work is completed. |

No original result was changed into a pass. The revised bias policy knowingly permits a useful
model with greater absolute bias than persistence; its test suite includes that case. This
particular selected procedure also has lower five-year absolute signed bias than persistence.

Stop this comparison here. A later unseen annual report, sustained error changes across years,
or reproducible degradation in important program groups could change the recommendation under
a separately fixed monitoring decision. A new band study would need a new contract. None of
these results establish clinical benefit, regulatory suitability, causal effects, or patient-level
fairness. The separate original V2 and completed follow-up studies remain intact.

## Reproduce and verify

Run from the repository root with the locked Python 3.12 environment; no network, raw data
download, original replay invocation or application startup is needed.

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
$env:MPLCONFIGDIR = "$PWD/.test-tmp/matplotlib"
uv sync --frozen
uv run kasm acceptance-forecast diagnose --run-id diagnostics-final
uv run kasm acceptance-forecast compare --run-id comparison-v1
```

Runs are immutable: those IDs fail before analysis if already present. Reproduction then uses a
distinct ID such as `diagnostics-audit-1` or `comparison-audit-1`, preserving the same settings.
The ignored output root is `data/research/acceptance-forecast-0027/`. Each run contains JSON
tables/predictions, three full-range PNGs, and `completion.json` recording every payload's hash,
specification/configuration/code hashes, original source/release identity, dependency-lock hash,
Git commit and dirty state, UTC time and original provenance. New fit/calibration parameters
and row counts are in `report.json`; no arbitrary serialized model is written.

The fixed comparison configuration SHA-256 is
`2ef29c45e529e64aa1c53c56c1f502eb113507545510213145daaf1c58a7751d`.
Comparison-v1 `report.json` SHA-256 is
`408bca282e8f49b62a3b7da509205bcceeb47be6d8a5a32c887e5981a12a9ee6`.
The original release content identity remains
`1de89083ceebfda9afaf2d6b1c6ba3f1e6d0c1a1da16df9d09d994c4ec3581ad`.
These runs record an uncommitted implementation state with exact code hashes; they do not claim
to be clean release builds. Verification commands and outcomes are in the active plan.
