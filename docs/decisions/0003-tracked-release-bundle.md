# Decision 0003 — Track one hash-bound offline release bundle

**Status:** accepted  
**Date:** 2026-09-03

## Context

The application must open from a clean checkout without raw SRTR workbooks, live network access,
parsing, or fitting. Generated data and modeling directories remain ignored, while the approved
derivative bundle must be small, attributed, and demonstrably tied to the frozen evidence.

## Decision

Track exactly one bundle at `artifacts/release/`. It contains the three canonical processed files,
six pre-replay modeling files, and the three files in the single hash-addressed completed replay.
`release_manifest.json` records the exact file set, byte sizes, SHA-256 values, content identity,
source attribution, dependency/config/source/feature/methodology provenance, cohort roles, and
model parameters. Publication rejects an invalid existing destination and uses a staged directory
swap. The 5 MiB limit includes the manifest.

The application defaults to the bundle’s `processed/` and `modeling/` roots. Development can opt
into other trusted roots through the two documented environment variables. Raw workbooks remain
ignored and are never copied into the bundle.

## Consequences

A clean checkout can demonstrate the frozen product offline, while full release reproduction still
starts from the immutable verified cache. Changing any payload changes the bundle content hash and
fails validation until the bundle is deliberately rebuilt and reviewed. The code’s MIT license
does not replace source attribution; the manifest preserves SRTR attribution and its
permissions-guidance link.
