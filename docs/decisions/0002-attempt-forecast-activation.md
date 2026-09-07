# Decision 0002 — Attempt forecast activation before frozen replay

**Status:** accepted pending frozen-config commit  
**Date:** 2026-09-03

## Reading this historical record — 2026-09-05

This records the V1 decision to test whether Ridge could be displayed, before the fixed 2025
replay comparison ran. The outcomes had already been inspected during planning, as SPEC.md
explains. "Activation attempted" means the full point and band evaluation rules were
prepared; it does not mean Ridge was approved for display. The pending-commit status is historical:
Plan 0009 records the frozen configuration commit `2a5b524`. Plan 0010 then records that Ridge
failed the point rule for average directional error, so persistence remained displayed and the
Ridge band stayed hidden. The decision and its original evidence below are preserved.

## Context

The guaranteed ridge path is green. Its prespecified 2021–2024 candidate gate passed with 5.4718%
year-balanced skill over persistence, improvement in all four years, no worse single year, and an
8.9356% improvement in the lowest expected-acceptance quartile. The complete activation rules and
their tests were finished before any target-year 2025 replay rows were read.

## Decision

Set `forecast_activation_attempted: true` in `configs/frozen_experiment.yaml`. Freeze alpha 10; the
2024-only ridge and persistence empirical-band calibration; the paired program-key bootstrap; the
point-promotion thresholds; and the independent band display gate before running the one allowed
canonical replay.

The replay model remains trained only through target year 2023. Target year 2024 is calibration
only. The replay result will be descriptive product-selection evidence and will not be used to
change any frozen method or claim.

## Consequences

The ridge point projection can become the experimental default only if every frozen point criterion
passes on the 2025 replay. The empirical band can be displayed only if its separate exact-coverage
and relative-width gate passes. Persistence remains the displayed projection after any point-gate
failure, and band failure suppresses the band without blocking the historical monitor.
