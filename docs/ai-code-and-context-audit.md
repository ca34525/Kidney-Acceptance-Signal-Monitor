# AI-generated code and context audit

**Audit date:** 2026-09-04  
**Scope:** tracked Python, tests, CI, dependency controls, Streamlit boundary, and agent context  
**Scientific scope:** unchanged; frozen experiment inputs, outputs, and promotion decisions were
not modified

## Executive finding

The repository did not exhibit the usual high-risk form of "vibe-coded" software: its behavior is
specified, temporal and data invariants fail closed, dependencies are locked, and 140 tests passed
before this audit. The material gaps were narrower:

- security-focused static analysis was absent from the default lint gate;
- direct construction of a source record could bypass manifest URL validation;
- six production `assert` statements were being used for type narrowing;
- three validation functions exceeded the new complexity ceiling; and
- agent guidance required broad mandatory context but did not explain how to keep subsequent
  retrieval focused or how to verify AI-suggested dependencies.

The implementation closes those gaps without changing source data, modeling, the frozen replay,
the release bundle, or application claims.

## Research synthesis and project response

| Common failure | Evidence | Repository finding | Control in this project |
|---|---|---|---|
| Plausible code is mistaken for correct repository behavior | [SWE-bench](https://arxiv.org/abs/2310.06770) shows that real issues require coordinated repository context, execution, and cross-file reasoning; early frontier models solved only the simplest cases | Strong existing control: `SPEC.md`, an active plan, named invariants, failing-test-first work, strict typing, and end-to-end fixture tests | Preserve the plan → failing test → implementation → full verification loop; record command evidence in the active plan |
| Long or noisy context dilutes critical instructions | [Lost in the Middle](https://arxiv.org/abs/2307.03172) found substantial position-dependent degradation in long contexts. [Anthropic's context-engineering guidance](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) recommends the smallest high-signal context plus just-in-time retrieval | `AGENTS.md`, `SPEC.md`, and `PLAN.md` are necessarily detailed, but there was no routing rule after the mandatory read | `AGENTS.md` now front-loads just-in-time symbol/call-site retrieval, excludes archived/generated context by default, and requires durable handoff evidence in the active plan |
| Generated code reproduces insecure patterns | In a security-focused benchmark, [Pearce et al.](https://arxiv.org/abs/2108.09293) found vulnerabilities in about 40% of 1,689 Copilot-generated programs. [NIST SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) recommends repeatable code analysis, review, negative testing, and recorded remediation | Ruff's default gate did not include security rules. Six production assertions and URL-opening calls were invisible to the configured lint set | Ruff `S` rules now run in the normal gate; production assertions were removed; URL acquisition revalidates absolute HTTPS file URLs at the I/O boundary; fixed, shell-free Git calls carry narrow reviewed suppressions |
| Generated tests can compile and cover code while remaining hard to understand or weak | A large study of [test smells in LLM-generated suites](https://arxiv.org/abs/2410.10628) found recurring Assertion Roulette and Magic Number Test patterns and sensitivity to prompt/context choices | Existing tests are unusually strong: named domain risks, malformed inputs, deterministic fixtures, temporal leakage guards, and branch coverage. Pytest-specific lint was not enforced | Ruff `PT` rules now join CI; new regression tests exercise unsafe input at the acquisition boundary and first demonstrated the unfixed failure. Coverage remains a floor, not the acceptance argument |
| Models invent plausible package names and create supply-chain risk | The USENIX Security 2025 study on [package hallucinations](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen) found the problem across commercial and open models | Strong existing control: every dependency is declared, `uv.lock` is committed, and CI runs `uv lock --check`, `uv sync --frozen`, and `uv pip check` | `AGENTS.md` now requires an explicit need, verification against an official registry/upstream source, and lockfile diff review before adding a dependency. This audit added none |
| Locally plausible branches accrete into code that is difficult to review | This is amplified by the repository-level and long-context limitations above; a passing happy path does not make a monolithic validator easy to audit | Complexity diagnostics found functions at 19, 20, and 28, above the adopted ceiling of 15 | Ruff `C90` now enforces a maximum cyclomatic complexity of 15. Configuration and release validation were split by existing contract boundaries without changing outcomes |

## Streamlit boundary review

The Streamlit entry point remains a view layer over trusted local artifacts. It does not download
sources, parse workbooks, train models, or derive forecast eligibility. Expensive data loading is
cached, domain formatting and validation live under `src/kasm/reporting/`, and AppTest covers the
offline critical flow. The fixed `unsafe_allow_html=True` block contains repository-owned CSS for
visible focus and accessibility; it interpolates no source or user content. Hidden tab/expander
work is limited to already-loaded, small release artifacts, so fragment or dynamic-state machinery
would add complexity without a measured performance benefit.

## Findings deliberately not converted into rules

- File length was measured but not capped. The largest modules encode many explicit domain
  contracts; an arbitrary line limit would reward fragmentation rather than clarity.
- Similar row-reading helpers remain local to baseline, challenger, and replay modules because
  they raise different domain errors. A generic abstraction would save few lines while coupling
  distinct scientific stages.
- Mutation testing was not added as a dependency. It remains a useful future audit technique, but
  the current improvement is higher-signal negative tests plus existing invariant/property tests.
- Cleanup handlers that catch `Exception`, remove an unpublished staging directory, and re-raise
  were retained. They do not hide failures or publish partial artifacts.

## Residual risks

- Static analysis and high coverage cannot prove the scientific implementation correct; expert
  review of source meaning, temporal separation, and frozen claims remains required.
- The context map reduces noise but cannot eliminate model attention failures. The active plan and
  executable checks remain the durable state.
- Dependency locking verifies identity and reproducibility, not that every transitive version is
  vulnerability-free. Vulnerability intelligence changes over time and should be handled by a
  separately reviewed maintenance workflow rather than a network-dependent release build.

## Verification record

Before implementation, the required baseline passed with 140 tests and 83.81% measured branch
coverage across data, modeling, and reporting. The first focused run then failed three cases for
the intended reasons: both non-HTTPS records reached the injected opener, and the Ruff policy did
not include `S`, `C90`, or `PT`.

After implementation, `uv sync --frozen`, Ruff format and lint, strict mypy, and all 143 tests
passed; measured branch coverage is 83.93%. The nine-source immutable cache verified, a disposable
data build and backtest reproduced the canonical row counts and alpha, and a disposable 12-file
release build reproduced content identity
`1de89083ceebfda9afaf2d6b1c6ba3f1e6d0c1a1da16df9d09d994c4ec3581ad`. The write-once frozen
replay was not rerun. Detailed command evidence is in
`docs/plans/0014-ai-code-and-context-hardening.md`.

## Second review — 2026-09-04

**Reviewed revision:** `9df76eb`, after the original V2 study was added.
**Status:** review complete; the findings below remain open.

The project follows many sound AI coding practices: explicit acceptance criteria, tests before
implementation, dependency locks, strict type checking, security lint, and checks that prevent
future information from entering training. These match the emphasis on clear context, durable
instructions, and verification in [OpenAI's current coding-agent guidance](https://learn.chatgpt.com/guides/best-practices).
A green test run still leaves gaps. This second review found six issues requiring focused fixes.
It supplements the earlier audit; the earlier completion record describes the earlier revision.

### 1. Include V2 in the coverage gate (P2)

The test command in [.github/workflows/ci.yml](../.github/workflows/ci.yml) measures only
`src/kasm/data`, `src/kasm/modeling`, and `src/kasm/reporting` (lines 37–39). The newer
`src/kasm/patient_journey` package is outside the measurement. Thus CI can remain green while
new V2 paths receive no tests. The repository-policy test also checks only the three old paths.

Fresh verification passed all 236 tests and measured 83.93% combined statement/branch coverage
for the V1 directories. Running the same suite with V2 coverage enabled measured **76.05%** and
failed an 80% threshold. Combining covered and total counts from the two reports gives **79.84%**
for all four directories. The combined figure is a calculation from those reports, not a third
test run. The percentages are not branch-only coverage.

Include V2 in CI and the documented commands, then add tests for meaningful missing boundary
cases rather than lowering the floor. The V2 model-artifact and release modules measured about
66% and 69%, respectively; start by checking their untested rejection and publication paths.

### 2. Stop processing an archive after failed verification (P2)

[cache.py](../src/kasm/data/cache.py) calls `_verify_zip` at lines 150–151 even after recording
an outer-file size or SHA-256 mismatch. Inside `_verify_zip`, it also decompresses the requested
member after detecting a member-size mismatch (lines 94–103). Processing already-rejected
content exposes the verifier to unnecessary resource use and malformed compression data.

An offline synthetic archive with a wrong pinned hash still reached `ZipExtFile`. A small
wrong-hash archive with unsupported compression raised `NotImplementedError` instead of
returning a structured `CacheIssue`. Stop before opening rejected archives and before expanding
members that fail their size contract; preserve these cases in regression tests. This finding
does not mean a changed archive was accepted into the trusted cache.

### 3. Enforce the download size while reading (P2)

[download.py](../src/kasm/data/download.py), lines 93–94, reads until the server ends the
response. It checks the pinned size only after the entire response is written. A changed or
malfunctioning endpoint can therefore consume disk space far beyond the declared file size.
The socket timeout does not bound a response that keeps supplying bytes.

An offline response pinned at 16 bytes was allowed to supply 2,097,160 bytes before rejection.
Limit cumulative bytes during the read, remove the temporary file on overflow, and test that
reading stops early. The final hash check is still necessary but does not replace this limit.

### 4. Apply the HTTPS rule to redirects (P2)

[download.py](../src/kasm/data/download.py), line 60, uses the default `urlopen` redirect
behavior. The initial URL is checked, but later redirect destinations are not checked by the
project. An offline call to the installed Python `HTTPRedirectHandler.redirect_request`
confirmed that both HTTP and FTP destinations are allowed after an initial HTTPS request.
This is broader than the HTTPS-only boundary claimed by the nearby security-lint suppression.

Reject a non-HTTPS redirect before contacting its destination and add an offline redirect test.
Pinned hashes still protect accepted file contents; they do not enforce transport security.
No live source redirect was observed or requested during this review.

### 5. Exercise the forecast-disabled replay path (P2)

[experiment.py](../src/kasm/modeling/experiment.py), lines 489–498, allows missing band
calibration when `forecast_activation_attempted=false`. However,
[replay.py](../src/kasm/modeling/replay.py), lines 313–320, unconditionally requires both
calibrated residual radii before generating its prediction rows.

A temporary copy of the configuration with activation disabled, no calibration evidence, and
`candidate_gate_passed=false` loaded successfully. Calling the prediction function with the
existing four-program synthetic fixture then raised
`Frozen config must contain a valid ridge absolute-log-residual radius.`
This breaks the specified replay path when activation was skipped. The shipped configuration
attempted activation and is unaffected. Cover the skipped branch with a failing test, then omit
band calculations and evidence when absent; do not invent a zero-width band. The reproduction
did not execute the canonical replay command or write any analytical result.

### 6. Route agent instructions to the correct study (P2)

[AGENTS.md](../AGENTS.md), lines 50–55, presents the V1 log(OAR) target and calendar-year cohorts
as repository-wide, non-negotiable rules. Line 87 permits only the V1 release directory.
The approved [V2 specification](specs/patient-journey-v2.md) instead uses `SAL_TOTFTX_C18`,
July–June listing cohorts, and a separate release directory. `SPEC.md` correctly identifies
the version boundary, but the agent instructions and their authority list lack that qualifier.

Explicitly distinguish shared safeguards from V1-specific requirements, and route original V2
and follow-up work to their respective specifications and configurations. This is an instruction
clarification, not a change to either study. It belongs in the planned P0a documentation review.

### Verified strengths and limits of this review

- Required checks passed: frozen sync, lock consistency, installed dependency compatibility,
  Ruff formatting/lint, strict mypy, and the 236-test suite with its current V1 coverage gate.
- Existing negative tests cover immutable cache publication, changed hashes, program identity,
  missing values, feature allowlists, temporal separation, and explicit public eligibility.
- A regression checks that changing 2024 outcomes cannot change the V1 replay prediction fit.
  V2 validates predictions against trusted processed inputs and prohibits model promotion.
- CI uses actions pinned to commit SHAs and read-only repository permissions. It defines
  application and non-root container smoke checks. Those process/container checks were inspected,
  not executed again in this audit; existing offline AppTests ran with the suite.
- Independent reviews examined source boundaries, scientific safeguards, and instruction routing.
  Boundary reproductions used local synthetic inputs. No source refresh, real-data model run,
  canonical replay, or release rebuild occurred.

Dependency compatibility is not a vulnerability scan. This review did not query live dependency
advisories or remote branch-protection/secret-scanning settings, and makes no claim about them.
The previously disclosed V2 report-count shift and limited evaluation history remain analytical
limitations assigned to Plan 0020, not new code defects discovered here.

Command evidence and the documentation-only test exception are recorded in
[Plan 0020](plans/0020-v2-follow-up-and-interview-story.md#ai-coding-practices-recheck--2026-09-04).
This change adds the audit record only; all six remediations remain open.

## Focused hardening follow-through — 2026-09-04 (2026-09-05 UTC)

The user committed the second review as `4155ea7` and authorized its focused hardening.
All six findings now have implemented fixes and local evidence in
[Plan 0021](plans/0021-focused-ai-coding-hardening.md). The open-finding text above is retained
as the record of the reviewed revision.

Agent instructions now route work to the correct study. Archive verification stops at failed
outer or member checks, oversized downloads stop early, and the actual HTTP opener rejects
non-HTTPS redirects before following them. A skipped forecast activation keeps point results
and persistence display, with band and bootstrap evidence absent. Synthetic tests cover that
path through artifact publication and offline display; the attempted-activation calculations
match the starting revision exactly.

CI now includes V2 and separately requires its coverage to reach 80%, checked to two decimal
places. New tests exercise malformed artifacts, rehashed inconsistencies, rollback after failed
publication, source drift, and missing-value/date handling. All **353 tests pass**, with
**82.48% combined** and **80.44% V2** statement/branch coverage. Frozen sync, lock checks,
dependency compatibility, Ruff, mypy, nine-source cache verification, and local Streamlit
process health also pass. An isolated data/backtest/release reproduction matches the original
payload hashes and release content identity; it reuses the existing completed replay bundle.

Docker is unavailable on this host, so image build and runtime non-root/health verification
remain for CI. Frozen settings, source pins, the dependency lock, and both tracked release bundles
are unchanged. Plan 0020's scientific follow-up has not begun.
