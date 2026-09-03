# Decision 0001 — Month-precision prediction origin

**Status:** accepted  
**Date:** 2026-09-03

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
