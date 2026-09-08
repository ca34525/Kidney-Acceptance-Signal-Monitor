# Plan 0022 — Audit source coverage and simplify the repository

**Status:** complete, 2026-09-08 UTC. **Scope:** audits, justified cleanup and future planning only.

The user authorized a new branch, a source/cohort feasibility audit, an outside review of
unnecessary repository material, other consequential audits, and conditional plans for
deceased-donor transplant receipt and earlier candidate characteristics. This session must
not implement those studies, fit real-data models, rerun frozen evaluations or alter results.
Work starts from a clean `main` checkout on `codex/source-and-cleanup-audit`.

## Work and acceptance

| Item | Expected evidence |
|---|---|
| A1 Source feasibility | Reconcile the newest cohort dates against release-bound evidence; inventory earlier public sources, definitions, fields and usable time splits without comparing outcomes or models. Distinguish verified facts from remaining acquisition work. |
| A2 Cleanup | Remove obsolete operational instructions, repetition and accidental files when their removal does not lose scientific contracts, completed evidence, reproducibility or useful presentation material. Review each actual deletion. |
| A3 Consequential review | Check source-date enforcement, claims, tracked-file hygiene and implementation boundaries. Fix bounded cleanup defects; record scientific or substantive implementation findings for separate work. |
| A4 Future plans | Write conditional, reviewable plans for idea 1 (deceased-donor receipt) and idea 2 (earlier candidate characteristics), with explicit populations, comparisons, temporal limits, decisions required before fitting and stopping rules. Mark both unimplemented. |
| A5 Verification | Run the required locked install, format, lint, type and test/coverage checks, cache verification and relevant offline checks. Preserve original configurations, result bundles and presentation payloads; allow dated correction notices in companion READMEs. |

Documentation-only cleanup and mechanical ignore rules use the documented failing-test
exception: link checks, diff review and preserved-file hashes are more useful than tests for
prose. Any executable behavior change requires a smallest failing regression first. Source
inspection may read verified workbook schemas and dates; it must not fit or score models.

No new dependency, application feature, analytical release or source-pin update is planned.
New source downloads, if needed, remain isolated under ignored `data/audit-0022/` with their
URL, response checks and hashes recorded. Their audit fingerprints do not authorize adding
them to the production source manifest. Existing source files remain immutable.

## Evidence and findings

Branch created from clean `main` at `f0eed3217120ab43529cf146981da0078a5c85df`.
The presentation changes from the earlier conversation are part of that starting checkout.
No commit, push, analytical implementation or model evaluation was performed in this session.

| Item | Completed finding or change |
|---|---|
| A1 | [Source audit](../audits/source-feasibility-0022.md) verified all nine pinned workbooks and four earlier archives. A release-named, hashed and rendered July 2026 PDF, matched to eight pinned workbook values, establishes July 2023–June 2024 listings. The original calendar-2023 overlap rationale is wrong. A separate study could use two retrospective evaluation periods with the pinned sources, or conditionally four with July 2017 data. These are possible designs, not additional results. |
| A2 | Condensed the roadmap, Plan 0020, implementation audit, project guide and README. Removed obsolete schedules, completed branch/permission and prose-inventory instructions, repeated slide requests and stale open-work descriptions. Preserved substantive historical failures, corrections, commands and original identities. Retained scientific safeguards and made verification proportional to the changed boundary. Removed one unused private helper and ignored Office lock files. |
| A3 | Found the source-date enforcement gap: outcome/wait-time parsers trust ledger dates, so subsequent comparison to the same ledger cannot validate source timing. A fixture with changed ledger dates and unchanged workbook cells reproduces that trust. Recorded a prerequisite correction for future studies; no original parser, ledger or result was scientifically revised. Fixed the separately reproduced Windows checkout/hash defect below. Independent review found no other consequential issue in the reviewed boundaries. |
| A4 | [Plan 0023](0023-deceased-donor-receipt-study.md) and [Plan 0024](0024-candidate-mix-study.md) define questions, populations, source gates, small fixed comparisons, decision points and stopping rules. Both remain unimplemented. |
| A5 | Full required checks passed, including offline application tests, source-cache verification, preserved-file hashes and documentation links; details below. |

The five deceased-donor components exist across the pinned history, but their sum is derived,
not a published deceased-donor total. Candidate tables also exist throughout; changed age bins
and unresolved historical PRA definitions require explicit source reconciliation. Earlier
archive fingerprints are audit evidence only; no source pin was accepted into production.

Dated notices in the original V2 specification, data/model cards and Decision 0005 distinguish
the incorrect exclusion rationale from the unchanged completed study. The current guide and
roadmap point to the corrected evidence. Both presentation READMEs identify the affected cohort
claim. Slide sources, decks, HTML and build metadata remain unchanged; correction and rendered
rebuilding belong to the later presentation revision. Historical results and original input
identities must remain distinguishable from any future source contract.

### Checkout stability and proportional checks

The original release manifests bind five YAML inputs to exact bytes. Git previously
protected release payloads from line-ending conversion but not those inputs; Plan 0020
already records Windows checkout hash failures. The new regression reproduced the problem with
Git's checkout filters under `core.autocrlf=true`: the first manifest-bound input's SHA-256
failed as intended. Pinning LF for those five inputs makes every filtered hash agree with its
release manifest. Present input bytes and all results remain unchanged. Follow-up development files have separate byte identities
and are not normalized in this cleanup. The current dependency lock is a later version than the
lock recorded by the original releases; it is preserved, not mistaken for that historical input.

Removed the completed Plan 0020 prose-inventory mandate from current agent guidance.
Documentation uses content/link checks; executable, test, dependency, build, scientific/executable
configuration and source-manifest changes require the full checks. Additional source/build/container
checks follow the affected boundary. Scientific constraints, CI gates and the frozen-replay
restriction remain. Independent review prompted explicit inclusion of configuration changes.

An independent call-site and AST/token review found `_unique_by_program` in
`src/kasm/patient_journey/panel.py` had no callers or decorators. Removed only that private helper.
The remaining module AST matches the original exactly; all 44 panel tests pass. This is a
behavior-preserving dead-code removal, so there is no new behavior for a failing test to exercise.

## Verification and handoff

Commands used the existing locked environment, with local `UV_CACHE_DIR` and `MPLCONFIGDIR`.

| Command or check | Result |
|---|---|
| `uv sync --frozen` | Passed; 74 packages |
| `uv lock --check`; `uv pip check` | Passed; 74 packages resolved/compatible; no lock change |
| `uv run ruff format --check .` | Passed; 80 files |
| `uv run ruff check .` | Passed |
| `uv run mypy src/kasm` | Passed; 39 source files |
| Focused repository configuration tests | 11 passed after the intended checkout-hash failure |
| Focused patient-journey panel tests | 44 passed; remaining module AST unchanged |
| `uv run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling --cov=src/kasm/reporting --cov=src/kasm/patient_journey --cov-branch --cov-fail-under=80` | 494 passed in 38.22 seconds; 84.17% combined coverage; includes offline app flows |
| `uv run coverage report --include="src/kasm/patient_journey/*" --fail-under=80 --precision=2` | Passed; 83.77% |
| `uv run kasm data verify-cache` | Nine sources verified; zero issues |
| Office ignore check | Both lock-name formats ignored; ordinary `.pptx` remains trackable |
| Protected-file SHA-256 comparison | 83 of 86 unchanged; only intended helper removal and two companion README notices differ. All original configs, releases, app files, lock, decks and slide sources remain byte-identical. |
| Documentation and final diff | Local path/heading references and whitespace checks passed |

The full suite ran after the final executable changes. Subsequent edits were documentary and
received content/link/diff checks. No data build, model backtest, artifact writer or frozen replay
ran. A new live app/container build was unnecessary because those boundaries were unchanged
and offline app tests passed. Temporary audit inputs and reproduction notes stay under ignored
`data/audit-0022/`; only the concise findings and proposals enter the tracked documentation.

The next analytical session must resolve source-bound dates and any earlier-release mapping,
write its separate specification and fixed configuration, and freeze comparisons before fitting.
Additional historical periods remain retrospective and exposed. Presentation refinement must
correct the marked cohort claim and then rebuild/review the delivery package. Neither task was
implemented here.
