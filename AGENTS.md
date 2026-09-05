# Working Agreement

This file governs implementation of the Kidney Acceptance Signal Monitor. It is intentionally stricter than a generic coding guide because methodological shortcuts can change the meaning of the result.

## 1. Source of truth

Before editing, read:

1. `SPEC.md`
2. `PLAN.md`
3. `configs/data_sources.yaml`
4. the active item in `docs/plans/`, when present

Order of authority:

1. The applicable study specification below for product and scientific requirements
2. That study's configuration for its fixed experiment or frozen evaluation
3. `configs/data_sources.yaml` for source identity and provenance
4. `PLAN.md` and the active implementation plan for work order
5. existing code conventions

Choose the study contract before selecting implementation rules:

| Work | Specification and configuration |
|---|---|
| V1 acceptance monitor | `SPEC.md`; `configs/experiment.yaml` and `configs/frozen_experiment.yaml` |
| Original V2 patient-journey study | `docs/specs/patient-journey-v2.md`; `configs/patient_journey_v2/experiment.yaml` and its methodology ledger |
| Plan 0020 analytical follow-up | Its own specification and typed configuration must exist before analysis starts; original V1/V2 contracts and results remain preserved |

Read the applicable study documents in addition to the mandatory reads. Engineering, data
safety, and nonclinical/nonregulatory claim safeguards apply across studies. V1's log(OAR)
target and calendar-year cohorts do not apply to V2's published 18-month functioning-transplant
percentage and fixed July–June listing cohorts. Original V2 permits no model promotion.

If implementation requires changing scope, data meaning, target, features, splits, metrics, or promotion rules, change the specification and plan first. Record a short architectural decision in `docs/decisions/`.

After those mandatory reads, load implementation context just in time:

- use symbol and call-site search to select the production module, its direct consumers, and its tests;
- do not preload archived plans, raw artifacts, generated outputs, or unrelated modules; and
- leave decisions, unresolved risks, and command evidence in the active plan rather than relying on a chat transcript.

## 2. Plan → test → build

Every change must map to a plan item and acceptance criterion.

For each behavior:

1. State the behavior and expected evidence in the active plan.
2. Write the smallest failing test.
3. Run it and confirm that it fails for the intended reason.
4. Implement the smallest change that passes it.
5. Refactor without changing behavior.
6. Run the focused tests, then the relevant suite.
7. Update the plan with completion evidence.

New behavior and bug fixes require a failing test first. Exceptions are documentation-only changes and mechanical configuration changes that cannot be meaningfully exercised; record the reason in the plan.

Keep changes narrow. Do not combine unrelated refactors with feature work. One behavior per commit is preferred when practical.

## 3. Scientific invariants

These shared rules are non-negotiable for every study:

- Use the modeling unit, target, and pinned non-overlapping cohorts in the applicable study specification.
- Never use a random row split.
- All rows for an outcome cohort stay in the same temporal fold.
- Every predictor and training outcome must meet that study's measurement and publication cutoff rules.
- Imputation, scaling, and model fitting occur inside each training fold.
- Center code, center type, name, city, state, ZIP, OPO/DSA identity, and future report availability are never predictors.
- Published source values are authoritative. Reconstruct values only for a study's explicitly specified rounding checks or modeling transforms; never relabel reconstructed values as published.
- Statistical uncertainty for model comparisons is resampled by program, not by treating repeated program-cohort rows as independent.
- Preserve each completed study's fixed inputs and evidence; later investigations require separate identities and cannot become fresh validation.

The following additional rules govern V1. Original V2 and the follow-up use their own exact
scientific contracts, without weakening the shared safeguards above:

- The modeling unit is a kidney transplant program-year.
- The primary target is the next same-cadence calendar-year published `log(OAR)`.
- The binary credible-interval status is descriptive, not the training target.
- Modeling uses only the pinned, non-overlapping calendar-year cohorts.
- Every predictor must be available in the feature cohort or earlier.
- KDPI ≥60 is not a core model feature because it lacks adequate history.
- Baselines are implemented and evaluated before the ridge challenger.
- No second model family is added unless the specification is deliberately changed before the frozen replay.
- Do not tune, select features, alter the residual-band rule, or change claims after the frozen 2025 replay.
- The replay model is trained only through target year 2023; held-out 2024 outcomes cannot enter that fit and calibrate the band only when activation is attempted.
- Repeated programs across years are allowed because the task concerns established programs. Label first-observed programs separately and do not expose their forecast unless a tested artifact flag explicitly permits it.
- Published SRTR ratios and intervals are authoritative. Formula recreation is a nonblocking, rounding-range QA diagnostic only.
- Current SRTR credible intervals and empirical forecast bands are distinct quantities and must never share a label.
- When activation is attempted, the nominal 80% band is marginal across programs, not conditional for a center, and has a separate display gate from the point model.
- Treat 2025 replay estimates—and bootstrap intervals when activation is attempted—as descriptive product-selection evidence, never prospective or confirmatory validation.

If code makes it possible to violate one of these rules silently, add a hard validation error and a regression test.

## 4. Data rules

- Treat downloaded files as immutable inputs.
- Verify URL, status, file type, size, archive member, and SHA-256 before use.
- Download to a temporary file and move atomically only after verification.
- Never accept a changed hash or schema automatically.
- Parse by machine field name, not column position.
- Use `(CTR_CD, CTR_TY)` as program identity; never join on name.
- Preserve identifiers and ZIP codes as strings.
- Preserve missing and suppressed values as null; never convert them to zero.
- A missing future program report creates a missing target, not a negative outcome.
- Do not assume donor strata are mutually exhaustive when the source shows otherwise.
- Keep raw downloads, archives, interim data, and large generated artifacts out of Git. Track only the approved, attributed, reproducible bundles under `artifacts/release/` (V1) and `artifacts/patient_journey_v2/` (original V2), each `<5 MB`. A follow-up output root needs its own explicit specification and approval.
- Tests do not access the network.
- A manual data-refresh workflow may inspect live sources but may not update checksums without review.
- Preserve publication precision: month-only values render as month/year and never acquire an invented day.
- Maintain a per-release methodology ledger. If definitions cannot be reconciled, restrict the modeling era rather than silently pooling it.

Every release artifact must include source hashes, configuration hashes, Git commit, dependency-lock identity, build time in UTC, cohort years, feature schema, and model parameters.

## 5. Product and claim rules

For the V1 acceptance monitor, use these terms. V2 uses its specification's patient-journey
terminology; the prohibited claims and interface restrictions below apply across studies:

- "screening signal"
- "published offer-acceptance ratio"
- "next-calendar-year PSR projection"
- "delayed-report nowcast"
- "quality-improvement review"

Do not use these claims:

- poor or unsafe program
- inappropriate or avoidable decline
- organ should have been accepted
- regulatory risk, noncompliance, or MPSC flag
- real-time forecast
- clean 12-month-ahead forecast
- prospective or independent validation for the 2025 replay
- formal CUSUM or control chart
- causal driver or intervention effect
- patient-level fairness or clinical benefit
- reproduction of UNOS Predict or SRTR's offer-level model

Do not build a national center leaderboard, composite score, or patient/organ input form. Do not display MPSC thresholds.

For V1, the historical monitor is the product. Show the ridge challenger as the default only if the frozen promotion gate passes. Otherwise display persistence and document the negative result plainly. Original V2 remains a separate exploratory study with promotion prohibited.

## 6. Application boundary

- Streamlit is a view layer.
- Data, statistical, and formatting logic belongs in importable modules under `src/kasm/`.
- The web process reads trusted, precomputed Parquet and JSON artifacts.
- The app never downloads, parses workbooks, trains models, or accepts arbitrary serialized models at request time.
- Keep the critical user flow functional without network access.
- Missing values display as "Not reported" or "Insufficient history," never as zero.
- The view reads `public_forecast_eligible` from trusted artifacts and never derives eligibility ad hoc.
- Color is not the only status cue.
- Display source cohort, publication date, artifact version, and the nonclinical/nonregulatory banner on every analytical view.

## 7. Engineering rules

### Ordinary-language explanations are a top priority

- Use ordinary language first in user explanations, documentation, presentations, chart text,
  and new or touched code comments/docstrings. Explain the idea before naming the method.
- Plan 0020 also requires an ordinary-language pass over existing documentation and explanatory
  comments/docstrings before its analytical work begins. Inventory the files, including past plans
  and decisions. Retain their scientific meaning, numbers, commands, and historical evidence;
  use dated explanations when a rewrite would obscure the original record.
- State the purpose, what one record represents, the people or programs counted, the relevant
  dates, and the units. Explain denominators, unknown values, and the reason for important rules.
- Keep exact source field names, formulas, types, and statistical definitions wherever needed
  for correctness. Plain explanations accompany these details; they do not replace them.
- Define an unfamiliar term at first use. Prefer "number of earlier available reports" over
  unexplained "archive depth," and "average size of the error" before introducing "MAE."
- Use a short numerical example when it clarifies meaning. Label hypothetical examples clearly.
  Distinguish percentage points from percent, reported outcomes from actual unknown outcomes,
  original study results from later investigations, and proposals from completed work.
- Comments explain intent and reasons, not every line of implementation. Do not rename stable
  identifiers, add redundant prose, or refactor unrelated code solely to remove technical terms.
- Follow `docs/project-guide.md` for the current explanation. Interview readiness requires a
  walkthrough and rehearsal in the author's own words; documentation alone does not establish it.

### Implementation requirements

- Python 3.12 and `uv` with a committed `uv.lock` are the supported environment.
- Prefer small, typed, pure functions and explicit schemas.
- Treat AI-generated code, tests, dependency names, and factual claims as untrusted until verified.
- Search for existing definitions and call sites before adding a helper. Prefer direct reuse, and do not add speculative abstractions, compatibility layers, placeholders, or unrelated cleanup.
- A new dependency needs a concrete requirement in the active plan, verification against its official package registry or upstream source, and an updated `uv.lock` reviewed in the diff.
- Keep side effects at CLI and I/O boundaries.
- Give external-input, filesystem, archive, network, and subprocess boundaries negative tests and security-focused static analysis. Keep any suppression narrow and explain why the boundary is safe.
- Use structured logging; do not log entire source rows unnecessarily.
- Raise actionable domain errors rather than returning partially valid data.
- Fix random seeds and record them, but do not confuse deterministic code with statistical certainty.
- Do not add a database, API service, orchestration platform, model registry service, cloud dependency, or notebook-only production logic.
- Docker must run as a non-root user and expose a health check.
- Pin CI actions to commit SHAs.
- Do not commit secrets, raw source files, large model files, local caches, or unrelated generated output.

## 8. Required verification

Run the smallest relevant command while developing, then the full required set before marking a plan item complete:

```bash
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run mypy src/kasm
uv run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling --cov=src/kasm/reporting --cov=src/kasm/patient_journey --cov-branch --cov-fail-under=80
uv run coverage report --include="src/kasm/patient_journey/*" --fail-under=80 --precision=2
```

When the relevant components exist, also run:

```bash
uv run kasm data verify-cache
uv run kasm data build
uv run kasm model backtest
uv run kasm artifacts build
uv run streamlit run app/streamlit_app.py
docker build -t kidney-acceptance-signal-monitor .
```

`uv run kasm data sync` is the networked preflight/maintenance path. Release reproduction starts from the immutable verified cache and does not depend on live URLs.

The frozen-replay command is exceptional:

```bash
uv run kasm model evaluate-frozen-replay --confirm
```

Run it only after `configs/frozen_experiment.yaml` is committed and the plan explicitly authorizes the evaluation. Write the canonical result once to the config-hash + source-manifest-hash path with a completion marker; fail on overwrite. A rerun must use a distinct audit path. Never automate the replay in ordinary pull-request CI.

## 9. Test expectations

The suite must cover:

- source and schema drift;
- unsafe archive extraction and bad hashes;
- old and new workbook sheet names;
- two-row headers;
- composite program identity;
- date normalization;
- publication-date precision;
- null-versus-zero behavior;
- count and interval invariants;
- program entry and exit;
- annual non-overlap;
- feature availability;
- train-only preprocessing;
- baseline formulas;
- deterministic folds and ridge results;
- explicit forecast eligibility;
- exclusion of 2024 outcomes from replay fitting;
- write-once frozen-replay output;
- artifact provenance;
- offline app loading and critical user flow; and
- non-root container startup.

When `forecast_activation_attempted: true`, the suite must additionally cover promotion-gate behavior, point-versus-band promotion, 2024-only band calibration, exact-binomial coverage, bootstrap reproducibility, and band suppression.

Do not write brittle tests for exact live-data model scores or chart pixels. Use small fixtures and property/invariant tests. A coverage threshold is a floor, not a substitute for testing the named risks.

Prefer assertions on observable domain behavior over assertions that repeat the implementation. For a defect or safety boundary, preserve the smallest case that failed before the fix and include malformed, missing, or boundary inputs when they can change the meaning of the result.

## 10. Definition of done

A task is done only when:

- its acceptance criterion is satisfied;
- the new test failed first and now passes, or the recorded exception is justified;
- focused and relevant full tests pass;
- lint and type checks pass;
- documentation and provenance are updated;
- the active plan records evidence;
- no scientific or claim rule has been weakened; and
- generated output is reproducible from the documented command.

## 11. Commit-message handoff

After completing any repository change, include one ready-to-use commit message in the final
response. Base it on the actual completed diff and use Conventional Commits format:
`<type>(optional-scope): <imperative summary>`.

- Keep the subject specific, lowercase after the colon, and at most 72 characters.
- Use an imperative verb and describe the outcome rather than the work process.
- Add a body or footer only when needed to explain rationale, migration impact, issue references,
  or a breaking change.
- Never claim checks passed unless they were actually run successfully.
- Provide the message even when the changes remain uncommitted; do not create a commit unless the
  user explicitly asks for one.

Stop rather than improvise if a change would require nonpublic data, weaken temporal separation, use the frozen replay for iteration, or turn the product into clinical/regulatory advice.
