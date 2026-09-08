# Decision 0015 — Select the fitted ratio adjustment for a future point release

Accepted September 8, 2026 for the completed [Plan 0027](../plans/0027-v1-forecast-improvement.md)
recommendation; deployment is a separate implementation item.

Apply [Decision 0014's fixed comparison](0014-fix-forecast-comparison-0027.md) once. Full Ridge,
recent-three-year Ridge and the fitted adjustment of the latest log ratio all pass its point
criteria. Select `adjusted_persistence`, the method with the lowest year-balanced absolute log
error: 0.29252 versus persistence's 0.31420, a 6.90% improvement. Mean ratio-unit error is 0.30872
versus 0.34000, a 9.20% reduction. The selected model uses one input and a fitted slope/intercept.

The advantage over full Ridge is only 0.00196 log units (0.66%). There was no configured interval
for that difference, so selection does not establish substantive superiority over Ridge. The
procedure worsens individual absolute log errors in about 40.1% of program-years and is slightly
worse in 2021; those costs and the large 2022 misses remain in the
[results](../acceptance_forecast_results.md). All fixed point criteria, including group and tail
checks, pass. The program-resampled interval against persistence is [−0.02571, −0.01761].

Withhold the forecast band: coverage varies across years and earlier-characteristic groups and
fails the separate exact-interval rule. Passing a point criterion does not authorize its range.

This knowingly retrospective decision was informed by inspected outcomes. It does not establish
fresh validation, clinical benefit or regulatory suitability. The original Ridge replay's exact
bias failure, training-through-2023 identity, release bundle and current app remain unchanged.
The comparison's 2025 fits through 2024 are separately identified. Original V2 and other studies
remain outside scope.

The [Plan 0028 handoff](../plans/0028-v1-point-projection-release.md) defines a new trusted bundle,
explicit eligibility, suppressed bands, offline product behavior and a reversal path. No product
output changes until that separate item is authorized and completed. Stop the five-method
comparison; future redesign or monitoring decisions need their own fixed identity.
