# Decision 0007 — Preserve V2 and plan an explanatory follow-up

**Status:** accepted for planning and documentation; implementation not started

**Date:** 2026-09-04

## Context

The original V2 study is complete. An outside review raised two questions: whether the count of
available earlier reports distorts a model comparison, and how living donation and unknown
follow-up status affect interpretation of the published outcome. The author has made ordinary-
language understanding and a strong 20-minute hiring-panel presentation top priorities.

The original V2 design forbids changing its inputs after viewing results. Preserving that record
is compatible with a separately identified investigation of a discovered problem.

## Decision

Retain the original V1 and V2 scientific designs, model configurations, predictions, evaluations,
and releases. Add Plan 0020 and a project explanation guide. Make clear explanations a standing
requirement for prose, presentations, charts, comments, and docstrings while retaining exact
formulas, identifiers, types, and source contracts.

The first implementation pass also covers existing documentation and explanatory comments/docstrings.
P0a in Plan 0020 defines the file inventory and review. Retain original facts and dated evidence,
using a dated explanation where rewriting historical prose would obscure what was originally
known. Complete this pass before the new analytical work; its changes are explanatory only.

Plan a separate exploratory follow-up. Its first revised model comparison will remove
`historical_target_count` from all five Ridge versions while keeping other settings and comparison
populations fixed. The field remains useful descriptive metadata. The second investigation will
verify and describe compatible living-donor, deceased-donor, and unknown-status components of the
published outcome, matching program and listing period before examining prediction errors.

Before implementation, record the separate scientific specification, typed configuration,
analysis identity, protected output boundaries, and test-first acceptance evidence. Do not relax
the original V2 configuration contract. Do not use its outcome-period components as predictors or
change the authoritative target. The follow-up uses already-inspected data, retains the one-period
evaluation limitation, and cannot promote a model or claim independent/prospective validation.

Review-only calculations are investigation leads until a saved command and input identities make
them reproducible. Retain them with that status; do not silently insert them into the frozen result.

## Consequences

The author can explain both the original work and why a follow-up is useful. Honest disappointing
results remain acceptable. Completion requires understanding and a rehearsed evidence-based story,
in addition to correct code and data.

The original seven-day build schedule remains historical context. The follow-up has its own work
order in [Plan 0020](../plans/0020-v2-follow-up-and-interview-story.md); it does not alter V1's replay
or reopen the original V2 freeze. This decision records a plan, not a completed correction or a
newly validated model.
