# Plan 0028 — Release the selected point projection

**Status:** defined deployment handoff; not started. Execution is a separate request.
**Basis:** [Plan 0027 results](../acceptance_forecast_results.md) and
[Decision 0015](../decisions/0015-select-adjusted-persistence-point.md).

## Purpose and fixed boundary

Implement the selected fitted adjustment of the latest published log ratio as an experimental
next-calendar-year PSR point projection. Preserve the original release and its failed Ridge
gate. This handoff does not authorize a new model search, forecast band, source refresh or
relabeling of already-inspected outcomes as new validation.

Before implementation, extend the separate release specification and typed configuration to
pin the exact prediction origin, training targets, feature/source/configuration hashes, alpha 10,
point-only decision identity and a new artifact location. The proposed tracked bundle root is
`artifacts/acceptance_forecast_0028/`, under 5 MB; approve that explicit root in the release
contract before writing a tracked bundle. Keep both existing study bundles intact.

## Acceptance and work order

| Step | Required evidence |
|---|---|
| R0 Fix the release | Typed release settings and methodology ledger bind Decision 0015, the Plan 0027 comparison hash, public source versions, training years and prediction origin. No evaluation year becomes fresh validation. |
| R1 Build the point artifact | Offline builder fits only the single configured input on outcomes public by the release origin. Record intercept, coefficient, scaling/imputation parameters, exact feature schema, UTC time, Git/lock/config/source hashes and complete row/exclusion counts. Write trusted JSON/Parquet, never an arbitrary serialized model. |
| R2 Preserve eligibility and suppress bands | Materialize and validate `public_forecast_eligible`; retain first-observed suppression and null meanings. Store explicit point permission and `band_display_permitted: false`. Loader rejects absent or conflicting decision/eligibility/provenance fields. Regression first for each boundary. |
| R3 Update the offline view | App reads only the new trusted precomputed bundle, exposes the selected point with persistence context, source/target dates and version, and labels the delayed-report nowcast and retrospective evidence. No runtime download, parsing, fitting, new input form, ranking or clinical/regulatory claim. SRTR current credible intervals stay separately labeled; no nominal forecast band appears. |
| R4 Verify and reverse | Full repository checks, trusted packaging/load and offline critical-flow/startup checks pass; Docker check if its paths/configuration change. Preserve an explicit release selector that restores `artifacts/release/` and persistence without rebuilding or altering either bundle. Test that reversal and the missing/corrupt-new-bundle failure state. |

If the latest available source remains July 7, 2026 for calendar 2025, a separately authorized
release could fit through observed target 2025 and project calendar 2026. Fix that origin in R0,
verify publication availability and disclose that much of target 2026 had already elapsed. This
is a new release-time fit, not another evaluation of target 2025. Do not borrow the failed band
or promise coverage for the new point procedure.

Define future monitoring/reversal criteria before observing the next annual truth; no scheduled
monitor is created by this handoff. A change in sources, eligibility, scope, claims or band
handling requires its own specification and decision. Point release completion must not imply
that a new model comparison or prospective validation has occurred.
