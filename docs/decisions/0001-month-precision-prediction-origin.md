# Decision 0001 — Month-precision prediction origin

**Status:** accepted  
**Date:** 2026-09-03

## Reading this historical record — 2026-09-05

This V1 decision answers how much of the target calendar year had already passed when its
prediction could be made. The "prediction origin" is the public release time of the input report.
If only July is known, six complete months have passed, so the recorded fraction is `0.5`;
this does not assert a July 1 publication date. The value explains reporting delay to the reader.
It is not an input used to fit the model. The exact day- and month-precision rules below remain
the accepted calculation.

## Context

The canonical model panel must record both the prediction origin and the fraction of the target
calendar year elapsed at that origin. Historical source publication values are sometimes known only
to the month, and the specification prohibits inventing a publication day.

## Decision

The panel stores the exact manifest publication string alongside its `month` or `day` precision.
For a day-precision value, elapsed fraction is the inclusive ordinal day divided by the number of
days in that target year. For a month-precision value, elapsed fraction is the number of complete
months before the named publication month divided by twelve. Thus July at month precision is `0.5`
and does not imply a July 1 or month-end publication date.

Elapsed fraction is provenance/context metadata and is not included in `MODEL_FEATURE_COLUMNS`.

## Consequences

Month-precision elapsed fractions are deliberately conservative and coarser than day-precision
fractions. Consumers can render the exact publication precision without reverse-engineering or
inventing a date, and the calculation remains deterministic across platforms.
