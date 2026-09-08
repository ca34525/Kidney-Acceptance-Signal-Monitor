# Decision 0014 — Fix the small retrospective forecast comparison

Accepted September 8, 2026 after the saved-prediction diagnosis and before scoring alternatives.
This implements P2 of [Plan 0027](../plans/0027-v1-forecast-improvement.md).

Saved Ridge predictions improve absolute log error on about 61% of program-years, with larger
errors at low earlier ratios and lower earlier expected-acceptance volume. Median relative
errors range from 18.9% to 32.3% across years; their 90th percentiles range from 50.3% to 117.3%.
The 2022 signed error is unusually positive, while other years' means are near zero or negative.
This motivates testing response to changing history, rather than minimizing one small pooled
signed mean. These findings describe already-inspected predictions.

Retain persistence, historical mean and the existing Ridge procedure. Add only two alternatives:
a single-input fitted adjustment of the latest log ratio, and the existing Ridge input set trained
on the most recent three target years. The first tests whether simple shrinkage captures the gain;
the second tests whether old relationships make the full-history fit less useful. Neither is
guaranteed to improve. Do not add a constant correction: the original Ridge implementation already
fits an intercept, and signed errors change direction across years. Its saved bundle does not store
the fitted intercept value; all new fits will record it. No original fit is rerun for inspection.

The [extended specification](../specs/acceptance-forecast-0027.md#fixed-comparison-v1)
and [typed settings](../../configs/acceptance_forecast/comparison.json) fix the complete procedures,
uncertainty and decision criteria. Alpha 10 is inherited from an inspected historical selection,
not newly tuned or claimed independent. There is no grid search. Evaluate all five procedures,
report every result and stop this design after one comparison, even if none pass.

The tolerances describe an aggregate quality-improvement prototype, not clinical utility.
A 5% improvement in average absolute log error must also beat historical mean and avoid worse
ratio-unit average error. Absolute year-balanced signed log error may be at most 0.05 (about a 5%
multiplicative shift), independently of persistence's exact bias. A 0.15 maximum yearly bias
(about 16%) is a disclosed drift ceiling, not a claim that such misses are small. Require gains in
four of five years, no year or sufficiently populated earlier-characteristic cell more than 10%
worse, and no more than 10% deterioration in the year-balanced 90th-percentile log error.
At most 10% of programs per year on average may have absolute log error worsen by more than 0.25
(a substantial multiplicative discrepancy, approximately 28%). These constraints keep mean gains
from excusing common large losses. A paired whole-program interval must support lower mean error.

The bias ceiling is revised with full knowledge of the original result. The criteria were selected
after diagnosis, so even a passing result remains retrospective and exploratory. Small groups are
reported without claiming adequate evidence; first-observed programs remain ineligible for display.
Forecast bands must pass a separate coverage/width assessment. Actual deployment needs its own
trusted artifact and tested application handoff; no completed study's evidence is replaced.
