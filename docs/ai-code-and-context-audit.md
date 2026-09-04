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
