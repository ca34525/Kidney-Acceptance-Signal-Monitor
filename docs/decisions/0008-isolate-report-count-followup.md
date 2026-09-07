# Decision 0008 — Keep the report-count investigation separate

**Date:** 2026-09-05 UTC. **Status:** accepted for Plan 0020 P1/P2 implementation.

The original V2 comparison may partly reflect an input that counts earlier reports. We need to
reproduce that behavior and make the already-planned single change without rewriting the original
experiment. The current user request authorizes the next substantial follow-up batch, left
uncommitted.

Use the [separate specification](../specs/patient-journey-v2-followup.md) and typed configuration.
Read the pinned original release, reconstruct its predictions before interpretation, and remove
only report count from all five revised groups. Reuse existing numerical helpers where their
contracts permit; preserve the original configuration loader and feature allowlist. All
comparisons use the same programs and the one original eligible evaluation period.

Write complete runs once under `data/patient_journey_v2_followup/report_count_v1`, an ignored local
root with protections enforced at the writer. This approves local analytical outputs only. Each
run records its inputs and the source-file hashes needed to identify an uncommitted build. No
new tracked release, promoted model, future forecast, source refresh or original-output rebuild is
part of this decision. Already-inspected outcomes remain exploratory evidence.
