# AI-assisted implementation audit

**Reviewed:** 2026-09-04–2026-09-05 UTC. **Status:** identified fixes complete.
This historical review checked source/download boundaries, tests, CI, dependency controls,
the Streamlit boundary and agent instructions. The scientific configurations, frozen results
and display decisions were preserved. Test counts below belong to the reviewed revisions;
they are not a current verification run.

The useful evidence is whether malformed inputs were rejected and failed paths were repaired.
A negative test supplies an invalid input; static analysis checks code without running the app.
Coverage measures exercised statements and branches, not whether the scientific question or
source interpretation is correct.

## First review and fixes

The starting revision had explicit study requirements, temporal/data validation, a dependency
lock and a passing 140-test suite. Review found that security-focused lint was absent, direct
construction of a source record bypassed manifest URL validation, six production assertions
served as type narrowing, three validation functions exceeded the new complexity ceiling, and
agent instructions lacked focused retrieval/dependency-verification guidance.

Implemented changes enabled Ruff `S`, `PT` and `C90` checks, replaced those assertions with
explicit checks, enforced absolute HTTPS file URLs at acquisition, split validation functions
at existing contract boundaries, and added the focused guidance. The complexity threshold is
15; the original three functions measured 19, 20 and 28. No dependency was added.

The first focused run failed three intended cases: two non-HTTPS records reached the injected
opener and the lint policy omitted the required rules. After the fixes, locked installation,
Ruff, strict mypy and 143 tests passed with 83.93% combined statement/branch coverage, compared
with the starting 83.81%. The nine-source cache verified. An isolated data/backtest/release
reproduction matched the row counts, alpha and 12-file bundle identity
`1de89083ceebfda9afaf2d6b1c6ba3f1e6d0c1a1da16df9d09d994c4ec3581ad`.
It reused the completed replay; the write-once replay was not rerun.
[Plan 0014](plans/0014-ai-code-and-context-hardening.md) retains the command evidence.

## Research basis

The review used research as prompts for concrete repository checks, rather than evidence that
this repository was correct or defective:

- [SWE-bench](https://arxiv.org/abs/2310.06770) motivated checking changes across their actual
  callers and tests.
- [Lost in the Middle](https://arxiv.org/abs/2307.03172) and
  [Anthropic's context guidance](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  informed focused retrieval after the mandatory study reads.
- [Pearce et al.](https://arxiv.org/abs/2108.09293) and
  [NIST SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) informed security analysis,
  malformed-input tests and recorded remediation.
- [Research on generated test smells](https://arxiv.org/abs/2410.10628) supported reviewing
  assertions for observable behavior instead of treating a coverage percentage as sufficient.
- [Package-hallucination research](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen)
  informed verification of suggested dependencies against official sources and review of lock changes.

## Second review — 2026-09-04

**Reviewed revision:** `9df76eb`, after original V2 was added. The six findings below were open
at that revision and subsequently fixed under [Plan 0021](plans/0021-focused-ai-coding-hardening.md).
Reproductions used offline synthetic inputs, not new source downloads or real-data model runs.

### 1. V2 omitted from the coverage gate

CI measured only the three V1 directories, allowing V2 paths outside the gate. All 236 tests
passed with 83.93% V1 coverage. A separate run including only V2 measured **76.05%** and failed
80%; combining covered/total counts from the two reports gave **79.84%** for all four roots.
That combined value was calculated, not measured by a third run. V2's model-artifact and
release modules measured about 66% and 69%, pointing to untested rejection/publication paths.

The fix added V2 to CI and an independent V2 coverage gate, with meaningful artifact/source
boundary tests. Coverage uses two decimal places because an intermediate 79.75% report rounded
to 80% under the default display. The final hardening run passed at 80.44% V2 coverage.

### 2. Archive processing continued after failed verification

The [cache verifier](../src/kasm/data/cache.py) opened ZIPs after outer size/hash rejection and
decompressed a member after its size mismatch. A wrong-hash synthetic archive still reached
`ZipExtFile`; unsupported compression raised `NotImplementedError` instead of `CacheIssue`.
The fix stops before rejected content is opened or expanded and preserves structured errors.
This defect exposed unnecessary parsing; it did not mean a changed archive entered the trusted cache.

### 3. Download size was checked only after reading

The [downloader](../src/kasm/data/download.py) read until response completion before checking
size. An offline response pinned at 16 bytes supplied 2,097,160 bytes before rejection. The fix
bounds cumulative reads, stops at at most one excess byte and removes the temporary file.
The hash check remains necessary; a socket timeout alone does not limit a continuously supplied response.

### 4. Redirects bypassed the HTTPS rule

The original opener checked the initial URL but allowed Python's default HTTP/FTP redirect
behavior. Offline reproduction confirmed both downgrade destinations were permitted. The actual
opener now rejects a non-HTTPS redirect before contacting it, with offline redirect regressions.
No live source redirect was observed or requested. Content hashes and transport checks serve
different purposes.

### 5. Skipped activation still required forecast-band calibration

The configuration allowed `forecast_activation_attempted=false` without calibration, but replay
prediction unconditionally required calibrated radii. The four-program synthetic fixture raised
`Frozen config must contain a valid ridge absolute-log-residual radius.` The shipped experiment
attempted activation and was unaffected.

The fix preserves point results and persistence display when activation is skipped, with band
and bootstrap evidence absent rather than invented zero-width bands. Regressions cover prediction,
serialization, publication and offline display. A synthetic comparison with `4155ea7` established
exactly unchanged attempted-activation predictions, schema and metrics. No canonical replay ran.

### 6. Shared agent instructions incorrectly imposed V1's study contract

[AGENTS.md](../AGENTS.md) presented V1's log(OAR), calendar-year cohorts and release root as
repository-wide requirements, conflicting with V2's published percentage, July–June listing
groups and separate output root. The fix routes each study to its own specification and
configuration while retaining shared engineering/data/claim safeguards. Neither study changed.

## Application boundary and scope decisions

The Streamlit entry point reads trusted local artifacts; it does not download, parse workbooks,
train models or derive forecast eligibility. Domain validation/formatting stays in importable
reporting modules. AppTest exercises the offline flow. The repository-owned CSS block interpolates
no source or user content; no additional dynamic-state machinery was justified by measured need.

The review retained local row readers with different domain errors, cleanup handlers that remove
unpublished staging and re-raise, and explicit validators without an arbitrary file-length cap.
It did not add a generic helper layer or mutation-testing dependency solely for this audit.

## Focused hardening follow-through — 2026-09-04 (2026-09-05 UTC)

All six second-review findings were fixed after review commit `4155ea7`.
[Plan 0021](plans/0021-focused-ai-coding-hardening.md) contains the failing/passing regressions
and full commands. Frozen sync, lock consistency, package compatibility, Ruff, mypy and the
nine-source cache passed. All **353 tests passed**, with **82.48% combined** and **80.44% V2**
statement/branch coverage. Additional cases covered rehashed inconsistent artifacts, rollback,
missing/extra files, source drift, null versus zero, publication precision and provenance.
An isolated reproduction matched original payload hashes and reused the completed replay bundle.

The initial Docker inspection missed the installed per-user executable. A later check using
that installation verified image build, UID `10001`, Docker health and HTTP `200 / ok` with
external networking disabled. Both jobs passed in
[CI run 33938291395](https://github.com/ca34525/Kidney-Acceptance-Signal-Monitor/actions/runs/33938291395)
for commit `5f26ec9`. Frozen settings, source pins, lock and both tracked release bundles were unchanged.

## Limits

These checks do not prove scientific validity, correct source meaning, statistical generalization
or absence of every defect. Dependency compatibility/locking is not a vulnerability scan. The
review did not query live vulnerability advisories or remote branch-protection/secret-scanning
settings. The V2 report-count shift and single usable evaluation period remained analytical
limitations; the separate follow-up is documented in [Plan 0020](plans/0020-v2-follow-up-and-interview-story.md).
