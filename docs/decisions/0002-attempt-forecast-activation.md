# Decision 0002 — Attempt forecast activation before frozen replay

**Status:** accepted pending frozen-config commit  
**Date:** 2026-09-03

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
