# Plan 0031 — Find useful program predictions through a short experiment sprint

**Status:** execution authorized; P0–P4 in progress.
**Branch:** `codex/program-prediction-sprint`, based on `cta/main` at `0f1a2cc`.
**Authorization:** on September 9, 2026, the user authorized implementation and execution of
P0–P4, all initial fits, historical evaluations, local outputs and up to two documented
follow-up rounds. This supersedes the original planning-only status. Local milestone commits
are authorized; pushing, merging and rewriting history are not.
**Study specification:** [program prediction sprint](../specs/program-prediction-sprint-0031.md).
**Decision:** [0017](../decisions/0017-broaden-program-prediction-research.md).

## Purpose and intended result

Find a public program-level outcome that can be predicted usefully enough to support a
concrete review or planning decision. Start with 20 small experiments: five annual targets
crossed with four pipelines. Explore broadly, compare against strong simple rules, then
develop one or two promising questions into a decision demonstration.

The first intended user is an analyst deciding which program activity changes warrant closer
investigation. Public reports provide an externally reproducible benchmark; programs have
fresher internal data for actual staffing or practice decisions. Plausible utility means
showing how the analysis could change attention or planning, without claiming patient benefit.

No new infrastructure is needed. Reuse the existing source cache, activity/OAR parsing and
modeling utilities. One shared experiment runner and results table serve all 20 comparisons.
Time-box new source work to the fields actually needed; continue on supported features if an
optional candidate field is unresolved. Keep completed studies and the application intact.

## Initial experiments

| Target | Plain meaning | Decision to investigate |
|---|---|---|
| New registrations | Annual registration events at the program | Focus review of anticipated registration demand |
| DDKT removals | Annual removals coded as deceased-donor transplant at this program | Focus review of declining reported transplant activity |
| LDKT removals | Annual removals coded as living-donor transplant at this program | Identify changes to discuss with the living-donation team |
| Ending list | Registrations on the list at year end | Focus review of growth and list-management workload |
| Overall OAR | Published risk-adjusted offer-acceptance ratio | Focus acceptance-pattern review |

The four pipelines are history-only Ridge; Ridge adding earlier activity, candidate mix and
acceptance features; shallow histogram gradient boosting with those broader inputs; and Extra
Trees with the same broader inputs. Persistence, recent mean and damped trend accompany every
target; OAR also gets the existing fitted latest-ratio adjustment. Exact initial settings and
the available source-year pairs are specified in the study document.

## Work order and acceptance

| Step | Work | Finish line |
|---|---|---|
| P0 Record executable settings | Create typed settings under `configs/program_prediction/` from the specification. Record target fields, supported features, origins, models, metrics and seeds. | One readable configuration controls the run; no per-model planning paperwork. Settings are saved before errors are examined. |
| P1 Build the small forecasting panel | Reuse verified B1 and OAR inputs; preserve source dates and program identity. Add a narrow candidate extractor only for supported fields. | One panel with source/publication provenance, target-specific eligibility, and a table of available training/evaluation periods. A fixture demonstrates that already-public outcomes cannot become forecast targets. |
| P2 Run the 20 discovery experiments | Fit four pipelines per target on earlier available labels. Score discovery target years 2021–2023 where supported, along with all baselines. | Complete model/target/period ledger, errors in meaningful units, failures retained, and a reasoned shortlist of at most two questions. No omission of poor experiments. |
| P3 Evaluate later periods and decisions | Save the shortlist before scoring 2024–2025. Score all initial pipelines there for transparency, then evaluate review budgets of 10, 15 and 25 programs for shortlisted questions. | Every period reported; compare observed change captured and false alarms with simple review rules. Later periods are inspected historical robustness evidence, not untouched validation. |
| P4 Explain and verify | Produce a short findings report, three useful figures, reproducible commands, and small example cases. Run applicable repository checks and one complete research build. | An honest decision comparison, all-run evidence, known limits, and executable reproduction. Identify the next question if none of the models adds useful information. |

Working allocation: roughly half a day for P0/P1 source binding, the remainder of days 1–2
for the first complete discovery screen, days 3–4 for later-period/decision evaluation, and
days 5–7 for focused follow-up, verification, explanation and personal rehearsal. This is a
planning estimate, not a deadline or an obligation to spend a week if useful results arrive sooner.

After the initial screen, small follow-up experiments may change a feature block, model or
target within the broad research question. Save the reason and revised configuration as a new
round before running it. Keep earlier results; do not present an adapted round as independent
confirmation. Do not require another architectural decision for each routine experiment.

## Code and source reuse

| Need | Existing location | Planned use |
|---|---|---|
| Verified workbook loading | `src/kasm/data/parse.py` | Reuse `load_workbook_payload` and `read_workbook_sheets` |
| Annual activity parsing | `src/kasm/waiting_list/parse.py` | Reuse `parse_release`, `AnnualRecord` and removal-field definitions; keep both annual vintages |
| B1 period evidence | `configs/waiting_list/sources.json` | Reuse seven reviewed release bindings; do not infer dates from OAR cohorts |
| Offer-acceptance parsing | `src/kasm/data/parse.py` | Reuse published OAR fields and source metadata |
| Publication cutoff handling | `src/kasm/patient_journey/receipt_panel.py` | Reuse `publication_available` if its interface fits; retain month precision |
| Regression preprocessing | `src/kasm/modeling/challenger.py` | Reuse `fit_ridge_pipeline` where compatible with the new features and targets |
| Broader candidate inputs | `docs/audits/source-feasibility-0022.md` | Add a small extractor; no existing production candidate-mix parser was found |
| Known OAR definition changes | `docs/audits/source-definition-0029.md` | Label affected periods and include a feature-block sensitivity; do not repeat the audit |

Keep new analysis in `src/kasm/program_prediction/` with only the modules needed for settings,
panel construction, fitting/evaluation and reporting. Add a CLI group in `src/kasm/cli.py`.
Use installed scikit-learn models; no new package is planned. Do not route this study through
the old frozen-replay command or call the fixed descriptive build as if it created forecast pairs.

Proposed commands below are **not implemented yet**; document final working commands in P4:

```text
uv run kasm program-prediction build --config configs/program_prediction/experiment.json
uv run kasm program-prediction screen --config configs/program_prediction/experiment.json
uv run kasm program-prediction assess --config configs/program_prediction/experiment.json
uv run kasm program-prediction report --run-dir data/research/program-prediction-0031/<run-id>
```

## Outputs and verification

Use ignored `data/research/program-prediction-0031/<run-id>/`. Deliver the source/feature map,
panel, complete experiment ledger, row-level predictions, period metrics, shortlist rationale,
review-budget comparisons, and report. Keep a compact narrative at
`docs/program_prediction_results.md` when there are actual results. No named national quality
ranking, new application, forecast-band study, service, source refresh or tracked analytical
bundle is part of this sprint.

For implementation, write focused failing fixtures for the meaningful new behavior: publication
cutoffs including same-release outcomes, historical vintages, fold-local transformations,
missing-versus-zero targets, matched comparison rows, finite model predictions, and hand-worked
error/review-budget calculations. Reuse existing source checks. Complete the executable-change
checks in [AGENTS.md](../../AGENTS.md), including coverage for the new package, after code changes.
No live network tests or frozen replay are needed.

The original planning delivery was documentation only. Implementation now follows the
failing-test-first and executable verification requirements above.

## Execution record

- Planning changes were already committed as `5ab8697` when execution began; the requested
  branch was checked out and the working tree was clean. Reviewed that planning commit rather
  than duplicating it. This authorization update is documentation only and needs no new test.
- P0/P1 expected evidence: strict settings, release-specific rows, cutoff and vintage fixtures,
  preserved missing targets, and source/feature/fold ledgers from the verified cache.
- Clarified earliest-release membership as unknown prior history, not observed program entry;
  retain latest-valid initial programs to preserve the specified earliest training pairs.
  Later first-observed identities are retained separately. Specification and Decision 0017
  record this interpretation before fitting.
- P2 expected evidence: train-only preprocessing and baseline fixtures, finite predictions or
  explicit failures, every discovery combination, matched-row metrics and a saved shortlist.
- P3/P4 expected evidence: later scoring requires that saved shortlist; hand-worked equal-year
  error and review-queue fixtures preserve unknown outcomes and whole-program resampling;
  complete runs, figures, report, reproduction and full verification follow.
- Environment preflight: `uv sync --frozen` checked 74 packages; `uv run kasm data
  verify-cache` verified all nine sources with no issues. Set `UV_CACHE_DIR=.uv-cache`
  and `MPLCONFIGDIR=.test-tmp/matplotlib` within this workspace. Windows Application
  Control blocks the `mypy` launcher; use equivalent `uv run python -m mypy`.
- Run storage and command regressions failed first with missing-module errors, then all
  16 focused checks passed. They exercise write-once stages, content-hash verification,
  unsafe paths/redirects, missing records, discovery coverage and the required shortlist
  argument before later scoring. Focused Ruff checks passed.
- P0/P1 implemented: strict initial settings and documented follow-up settings; diagnostic
  panel has 7,585 rows, 30 explicit features, 3,326 B1 source records and 10,515 OAR stratum
  records. All seven supported B1 releases retain both vintages. Candidate headers are
  present, but origin-period/denominator binding is incomplete; omit that optional block.
  Initial-release history is labeled unknown; later entries stay outside main evaluation.
  No clean-accounting or positive-start restriction is imported from Plan 0025.
- P0/P1 tests: 24 passed after initial missing-module failures and specific duplicate-key and
  follow-up-subset failures. Config/panel branch coverage is 98%; focused Ruff and mypy
  pass. Negative fixtures cover manifest/ledger drift, duplicates, invalid publication,
  already-public targets, global vintage choice, gaps, entry, null versus zero and OAR omission.
- P2/P3 implementation: all specified procedures and fold-local preprocessing are implemented;
  15 model tests pass (86.17% branch coverage), and 16 error/decision tests pass (89%).
  Each suite failed first before its implementation. Focused Ruff and mypy pass. Independent
  reviews checked panel/model timing and error/queue arithmetic without finding a blocking
  scientific defect. The spec now states the exact transformed-history mean/change convention,
  ordinary least-squares OAR adjustment and shared random seeds across feature-removal rounds.
  Ineligible records live in the panel/exclusion ledger, outside prediction-only denominators.
- First full verification: 1,048 tests passed, two environment-dependent smoke tests skipped;
  combined branch coverage 86.06%. Ruff lint and all 74 typed modules passed. Applied the
  required CLI formatting correction and rechecked formatting. A later independent report
  review found partial-coverage plotting and run-lineage gaps before any recorded fit.
  Regressions reproduced both defects, plus unchecked parent fingerprints; fixes suppress
  incomplete plot points, validate actual discovery/panel/follow-up ancestry and fingerprints,
  and compare settings/code/revision before and after execution. All 21 root integration,
  publication and report checks now pass. Full checks will run again on the final code.

## Planning evidence

- Starting local `main` was clean at `d2f9c56`, 11 commits behind its upstream. Fetched `cta`
  and created this branch directly from the latest merged `cta/main`, `0f1a2cc`; local `main`
  was not reset or advanced.
- Read the current repository rules, V1 specification, source manifest, roadmap and relevant
  existing source/model documents. Two independent read-only reviews checked the modeling
  design and source/code reuse.
- Confirmed that B1's descriptive 2017–2025 coverage does not imply nine valid forecast
  origins. The specification records actual release pairs and the sparse first training fold.
- Confirmed the four B1 target field names and the absence of a production candidate parser.
  Candidate categories and periods need a small implementation-time check; this does not
  block the activity/history experiments.
- Reviewed the written design independently. Fixed the main baseline on discovery results,
  distinguished change plots from redundant change-error MAE, and specified review selection
  before checking later outcome availability.
- Planning content reviewed; 71 local Markdown links checked with no missing targets;
  new-file whitespace inspection and `git diff --check` passed. No software suite, fitting,
  source refresh, application change or commit was performed.
