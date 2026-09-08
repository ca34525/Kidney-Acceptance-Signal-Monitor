# Plan 0020 — V2 follow-ups and presentation evidence

**Status:** P0a and P1–P3 complete. Presentation packages are prepared and verified;
the author's timed rehearsal and native presentation-machine checks are not recorded.
**Work dates:** 2026-09-04–2026-09-07.

This completed implementation record covers two exploratory investigations of the original V2
study and their presentation. Current work is listed in [PLAN.md](../../PLAN.md). The earlier
branch, permission and incremental slide-request instructions have been retired; the study
contracts, results and substantive verification/correction evidence are retained below.

## Purpose and study boundaries

The original V2 study predicts the later published percentage of newly listed candidates known
alive with a functioning transplant at 18 months. Its denominator is the original listing group,
including candidates who never received a transplant. The follow-up asks:

1. Does acceptance still add useful predictive information after removing an input that counts
   the program's earlier available reports?
2. What do living-donor, deceased-donor and unknown-status components tell us about the published
   outcome and its limits?

Both investigations use already-inspected outcomes. They are exploratory and cannot create a
new independent evaluation, change the original outcome or promote a model. Target-period
components describe the observed outcome; they are never earlier model inputs. V1, original V2,
report-count analysis and component analysis keep separate identities and output roots.

The original V2 release identities are retained:

| Record | Identity |
|---|---|
| Experiment SHA-256 | `ab8c01453c36039b293a8e7453b17b2b326faf734a081a4b67f8bfe132b1de79` |
| Bundle SHA-256 | `ce2844edbcec92c09d0053720d5331dd37ed43ab75de7aa4dd1de431c79a9eee` |
| Source build commit | `cdea5c40302de1797d83698566d2ebb51de16938` |
| Publication commit | `0353f9924b61441dac52e11b71326e6310603e25` |

See the [original specification](../specs/patient-journey-v2.md),
[model card](../patient_journey_v2_model_card.md) and
[Decision 0007](../decisions/0007-preserve-v2-and-plan-explanatory-follow-up.md).
The follow-ups preserve the original publication cutoffs, non-overlapping listing groups and
single usable Ridge evaluation period.

## Work and acceptance evidence

| Item | Behavior and expected evidence | Outcome |
|---|---|---|
| P0/P0a: explanation | Review existing documentation and code explanations; preserve scientific meaning, exact source details and executable behavior | Completed 2026-09-05; scope and corrections below |
| P1: diagnose report count | Reconstruct all five fitted models, verify stored predictions and paired populations, then inspect report-count contributions before conversion to percentages | Original predictions matched exactly; [results and command](../patient_journey_v2_followup_results.md) |
| P2: fixed comparison | Remove only `historical_target_count` from all five Ridge groups; keep rows, transformations and other settings fixed; report all 12 contrasts, including unfavorable results | Completed under a separate specification and typed configuration; no promotion |
| P3: outcome components | Verify source definitions/rounding, original listing denominator and 18-month timing; match the original evaluation programs; preserve missingness and explain associations without causal claims | All 218 evaluation programs matched; [results and command](../patient_journey_v2_component_results.md) |
| P4: presentation | Editable evidence, sourced illustrative case, independent offline backup, source/visual review and author rehearsal | Packages verified; author rehearsal not recorded |

P1/P2 fixed the original reconstruction tolerance at absolute `1e-10` proportion and zero
relative tolerance before revisions ran. Contributions add on the logit scale, not in percentage
points and not as effects of changing care. P2 did not search history windows or model families.
P3 fixed release 2505, four donor components, PDF-precision rounding checks, program medians and
all eight original-model error associations before calculation. Published totals remain
authoritative; missing components are never zeros. Numerical scenarios for unknown outcomes
were outside this scope.

Documentation-only changes used source, syntax, link, provenance and render checks instead of
tests asserting prose or chart pixels. New behavior required failing constructed tests; the
substantive failures and corrections are recorded below.

## Original review observations and later findings

The original 218-program errors were 11.49 percentage points for history-only Ridge, 7.35 for
history-plus-acceptance Ridge, 7.61 for the simple historical average and 8.93 for persistence.
The apparent 4.14-point acceptance gain against history-only Ridge was therefore a different
comparison from the 0.26-point gain against the historical average.

The initial read-only review found report count equal to two for 212 of 215 training programs
and five for 208 of 218 evaluation programs: a shift of about 25 training standard deviations.
P1 reproduced that diagnostic and all original predictions. P2 reduced history-only error to
7.32 percentage points; acceptance then improved it by about 0.09 points, with a descriptive
error-difference interval crossing zero. This weakens the large-gain interpretation without
proving that acceptance is uninformative.

The review's additional history-plus-acceptance versus historical-mean comparison gave an
error difference of about -0.2604 percentage points and interval [-0.7389, 0.2375], using 2,000
program resamples and seed `20260904`; volume-weighted errors were about 6.25 versus 6.03.
It was added after outcomes were inspected and was reproduced in P1.

The preliminary 16.27% unknown-status median described 222 source programs with at least ten
listed candidates. P3's 16.05% median describes the matched 218-program evaluation population.
Both percentages use the original listing denominator and weight each program equally. Neither
is a pooled patient percentage or evidence that unknown reporting caused prediction error.

## Documentation and implementation audit — 2026-09-05 UTC

P0a reviewed 112 files: 43 Markdown documents, 64 Python modules and five retained presentation
or image files. The review recorded 36 rewritten, 37 already clear and 39 preserved with dated
explanations. All 64 Python syntax trees matched the starting revision after excluding comments
and docstrings; all compiled in memory. The 27 reviewed historical records retained their
original text after removing the added dated notes. Protected configurations, release bundles,
dependencies and media had no diff; 176 local file links and nine heading anchors resolved.
The obsolete per-file work checklist remains in Git history.

Substantive clarifications retained V1's prior inspection of 2025 outcomes, distinguished a
failed display rule from clinical safety, stated V2's fixed uses of candidate counts, clarified
that package installation can need the network, and identified coverage as combined statement
and branch counts. Review also corrected an overstatement of source-loader checks and explained
the wholly missing training-column fill. One documentation-contract test failed because the V1
data card lost the term `Grain` (352 passed, one failed). Restoring the term beside its plain
explanation fixed the focused check and full suite without weakening an assertion.

Commands ran with `UV_CACHE_DIR=.uv-cache`:

| Command | Result on 2026-09-05 UTC |
|---|---|
| `uv sync --frozen` | Passed; 68 packages checked |
| `uv run ruff format --check .` | Passed; 64 files already formatted |
| `uv run ruff check .` | Passed, including the configured security rules |
| `uv run mypy src/kasm` | Passed; 30 source files |
| `uv run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling --cov=src/kasm/reporting --cov=src/kasm/patient_journey --cov-branch --cov-fail-under=80` | Passed; 353 tests; 82.48% combined statement/branch coverage |
| `uv run coverage report --include="src/kasm/patient_journey/*" --fail-under=80 --precision=2` | Passed; 80.44% V2 statement/branch coverage |
| `uv run pytest -q tests/unit/test_repository_config.py::test_required_release_documentation_and_diagrams_are_present` | Passed after restoring the explanatory heading's original term |
| `git diff --check` | Passed |

### AI coding practices recheck — 2026-09-04

The review of `9df76eb` found six gaps: omitted V2 coverage, archive processing after failed
verification, an unbounded download read, unchecked redirect schemes, a broken skipped-activation
replay path and V1-specific instructions stated as shared rules. The shipped replay's attempted
activation was unaffected. The [audit](../ai-code-and-context-audit.md#second-review--2026-09-04)
retains the synthetic failures and coverage measurements; [Plan 0021](0021-focused-ai-coding-hardening.md)
records all six fixes and local/CI verification. No canonical replay or real-data model run
was used to diagnose these software defects.

### Censoring and aggregate-data explanation — 2026-09-05 UTC

The guide was corrected to distinguish the information missing from Table B7 snapshots from
the assumptions of survival methods. Independent censoring does not require knowing each
person's reason for leaving observation; unknown status alone does not show the assumption
false. Aggregate data can support survival analysis when they retain exact event/observation
counts over time. Table B7's 6-, 12- and 18-month status snapshots do not retain that information.

The hypothetical ten-person example in [the guide](../project-guide.md) accounts for every person
and reproduces Kaplan–Meier survival `(8/10) × (4/5) = 64%` from exact event-time counts.
It is a teaching example, not an estimate of this study's unknown patient outcomes.
Source review used [SRTR Table B7 methods](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/technical-methods-for-the-program-specific-reports/),
[Jackson et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC4282781/) and
[NIST's calculation](https://www.itl.nist.gov/div898/handbook/apr/section2/apr215.htm).
The published target and original listing denominator remained unchanged.

Both wording passes checked all 125 local links and the example's exact-fraction arithmetic.
Each ran the six required commands with `UV_CACHE_DIR=.uv-cache` and
`MPLCONFIGDIR=.uv-cache/matplotlib`: sync passed (74 packages), Ruff format/check passed
(72 files), mypy passed (34 source files), and 437 tests passed with 83.42% combined coverage
and 82.43% V2 coverage. No real-data calculation, output rebuild or frozen replay ran.

### P1/P2 execution — 2026-09-05 UTC

- Separate contract and Decision 0008 preceded analytical implementation. The typed loader pins
  all five revised groups, 12 contrasts, reconstruction/contribution tolerances, bootstrap settings
  and nonpromotion. Original configuration and original feature allowlist are unchanged.
- Independent review of the contract and numerical code confirmed temporal selection, paired
  comparisons, training-only preprocessing and logit contribution arithmetic. A final independent
  review compared every narrative number and identity against the saved evidence and found no
  actionable issue.
- Failing-test evidence: the new config, numerical, artifact/CLI and report test files first
  failed collection because their intended production modules did not exist. Small regressions
  subsequently failed for the intended behavior: missing original eligibility in included audit
  rows (`KeyError`), missing lock file (`FileNotFoundError`), uncaught reconstruction failure, and
  unwrapped report rendering failure. Each now passes without weakening the assertions.
- Focused results: 31 config tests; 29 numerical tests; 18 artifact/CLI tests; six report tests.
  Negative cases cover changed/malformed configurations, prediction keys/values and paired targets,
  count/prohibited-feature injection, missing inputs, protected destinations, symlinked ancestors,
  unexpected filenames, existing empty/full destinations and simulated publication failures.
- The real run matched all 1,744 original evaluation predictions exactly before the revisions.
  Training uses 215 programs; all 13 approaches evaluate the same 218 programs, yielding 2,834
  comparison predictions. Audit data retain every original panel key and eligibility.
- Report-count frequencies and the original review bootstrap reproduce. Removing count lowers
  history-only MAE from 11.488 to 7.320 percentage points. The revised acceptance addition is
  -0.095 points (challenger minus comparator), descriptive interval [-0.491, 0.301]. Every fixed
  comparison, including unfavorable ones, is saved. This weakens the original interpretation of
  a large acceptance gain; it neither disproves acceptance information nor provides a new period
  of validation. No model is promoted.
- Both real figures were visually inspected. A formatting-only refinement gives numeric bar
  labels white backgrounds where the historical-mean line crossed them. This changes no numerical
  behavior, so visual QA and the existing deterministic-render checks cover it; no pixel test was
  added. The original run and the separately addressed final run have byte-identical evaluation
  JSON. No result-guided analytical setting changed.
- The original dependency lock identity remains in the preserved release and is available at
  source commit `cdea5c40302de1797d83698566d2ebb51de16938`. The current lock adds Matplotlib 3.10.9
  and five transitive packages; comparing parsed lock package/version maps showed no changed or
  removed pre-existing version. Official verification: [PyPI](https://pypi.org/project/matplotlib/)
  and [Matplotlib savefig](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html).

- SHA-256 checks before/after cover 42 existing files across both original configurations,
  manifests, generated inputs/results, and release roots: all remain byte-identical. Cache
  verification separately passed all nine source inputs. App/CI/container configuration and
  original modeling modules were not edited. No source download or frozen replay ran.

Required verification, with `UV_CACHE_DIR=.uv-cache` (and a writable `MPLCONFIGDIR` for figures):

| Command | Result on 2026-09-05 UTC |
|---|---|
| `uv sync --frozen` | Passed; 74 packages checked |
| `uv run ruff format --check .` | Passed; 72 Python files |
| `uv run ruff check .` | Passed, including configured security rules |
| `uv run mypy src/kasm` | Passed; 34 source files |
| `uv run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling --cov=src/kasm/reporting --cov=src/kasm/patient_journey --cov-branch --cov-fail-under=80` | Passed; 437 tests, 83.42% combined statement/branch coverage |
| `uv run coverage report --include="src/kasm/patient_journey/*" --fail-under=80 --precision=2` | Passed; 82.43% V2 statement/branch coverage |
| `uv run kasm data verify-cache` | Passed; nine sources, no issues |
| `uv run kasm patient-journey follow-up` | Passed offline; final run below |
| Same follow-up command again | Expected exit 1: run already exists; no overwrite |
| `uv run streamlit run app/streamlit_app.py --server.headless true --server.port 8504 --browser.gatherUsageStats false` | Started; `/_stcore/health` returned `ok`; temporary process stopped |
| `docker build -t kidney-acceptance-signal-monitor:v2-followup .` | Passed with locked production dependencies |
| `docker run --detach --network none --name kasm-v2-followup-smoke-52795f kidney-acceptance-signal-monitor:v2-followup` | Non-root UID 10001; internal health `ok`; Docker health `healthy`, network `none`; temporary container removed |

Docker is outside this session's PATH and its executable requires sandbox escalation. Used the
existing `%LOCALAPPDATA%/Programs/DockerDesktop/resources/bin/docker.exe` with approved escalation;
no Docker installation or configuration change was needed. Container verification covers the
added dependency and unchanged offline product; the subsequent chart-label-only refinement is
covered by the full Python suite and real rendering verification.

Final ignored run:
`data/patient_journey_v2_followup/report_count_v1/c6cc2cea133e7e61e9e42ac284f170baef43d9989d3ab04eea543ffb47af1cfa`.
Its seven payloads total 704,350 bytes, plus the completion manifest. A separate in-memory
recalculation matched the complete evaluation JSON and all 2,834 prediction values; regenerating
all five report/figure files matched their bytes. Every payload size/hash in the manifest passed.
The generated run records the dirty worktree and exact implementation hashes; it is development
analysis evidence, not a canonical release. The earlier figure-layout run remains separately
identified at `52795fe6303fed873ed9cce19ba3db0e09ba78020e1b4b03629081360a70543f`.

The numerical audit used the same importable calculation as the CLI without invoking any writer:

```python
inputs = _load_original_inputs(Path.cwd(), FollowupConfig())
result = evaluate_followup(inputs.rows, inputs.stored_predictions, inputs.config, FollowupConfig())
# Compare JSON-normalized result.evidence with evaluation.json;
# compare patient_journey_prediction_table(result.predictions).to_pylist() with saved Parquet rows;
# compare each render_followup_report(result.evidence) byte payload and each manifest size/hash.
```

Original data-build/model/artifact writers and the V1 frozen replay were not rerun. The
follow-up reads their preserved release; fixture tests cover both original offline app flows.
This investigation produced no model promotion, future forecast or tracked analytical bundle.

### P3 implementation and verification — 2026-09-07

Source and scientific evidence:

- Independent research inspected the verified 2505 archive/member in memory and official SRTR
  Table B7 definitions. The separate component ledger records all six fields, their exact
  descriptions, original listing denominator, 18-month timing, numeric-string handling and
  one-decimal PDF precision. It distinguishes observed absence of missing markers from the
  parser's explicitly declared defensive null/suppression rules. Only release 2505 is included.
- The fixed scope, source ledger, configuration and specification preceded analytical output.
  Reused original input validation, workbook verification, identity/field/date parsing and
  deterministic figure export. Original contracts and feature allowlists remain unchanged.
- All 234 source records parse; 222 have at least ten listed candidates. All 218 original
  evaluation programs match with no missing donor components. The original 236-row prediction
  universe retains 18 exclusions: 11 below the candidate minimum, six missing targets and one
  missing earlier target. Four source-only and six panel-only programs are recorded separately.
- All 234 functioning-donor sums reconcile at the specified PDF precision. The largest absolute
  raw workbook difference is about `1.0e-9` percentage points. No published total was replaced.
- Median combined post-transplant unknown is 16.05% for the 218 matched programs, versus 16.27%
  for the broader 222-program source group. These are per-program medians. All eight original
  models' signed/absolute error associations, and the observed-outcome association, are saved
  in fixed order. The report explains shared denominators and the algebraic use of the outcome
  in signed error; it makes no reporting-cause claim or inference about unknown patient outcomes.

Test-first and independent-review evidence:

- The source/config, analysis, and artifact/report/CLI test modules first failed collection
  because the intended production modules did not exist. Implementation then passed their
  constructed arithmetic, matching, null, source-drift and isolated-publication expectations.
- Independent source/numerical review found a missing-component bypass: 60% and 40% functioning
  plus 5% deceased-donor unknown and a missing living-donor unknown were accepted. The smallest
  regression first failed with `DID NOT RAISE`; checking the lower rounding bounds of all
  reported components now rejects it while incomplete donor-pair sums stay null.
- An all-missing-component figure first failed with a `TypeError` from the empty numeric range.
  Its regression now passes and the figure displays `Not reported`, without drawing a zero value.
- The 56 added tests also cover numeric strings, malformed/boolean/nonfinite percentages,
  exact PDF rounding endpoints, duplicate/overlapping/mixed-denominator or mixed-time sums,
  wrong source labels/dimensions, duplicate/mismatched keys/cohorts/counts/targets, explicit
  original eligibility, stored-prediction tampering, unavailable correlations, missing/unmatched
  audit, deterministic order/rendering, component exclusion in both model contracts, bad cached
  source bytes, missing contracts, protected/traversing/link destinations, unsafe file sets,
  existing empty/full destinations and failed/changed-during-build publication. Additional
  boundary coverage reused existing validation without introducing a new behavior or workaround.
- Independent final review checked source/input/provenance and writer boundaries, inspected the
  figure, and verified every payload hash/size, median and fixed error correlation. A separate
  pass checked the tracked results and all status updates against the saved evidence. No
  actionable issue remained after the missing-component regression was fixed.

Final verification used `UV_CACHE_DIR=.uv-cache` and `MPLCONFIGDIR=.uv-cache/matplotlib`:

| Command or check | Result |
|---|---|
| `uv sync --frozen` | Passed; 74 packages checked; no dependency or lock change |
| `uv run ruff format --check .` | Passed; 80 Python files |
| `uv run ruff check .` | Passed, including configured security checks |
| `uv run mypy src/kasm` | Passed; 39 source files |
| `uv run pytest -q --cov=src/kasm/data --cov=src/kasm/modeling --cov=src/kasm/reporting --cov=src/kasm/patient_journey --cov-branch --cov-fail-under=80` | Passed; 493 tests, 84.08% combined statement/branch coverage |
| `uv run coverage report --include="src/kasm/patient_journey/*" --fail-under=80 --precision=2` | Passed; 83.62% V2 statement/branch coverage |
| `uv run kasm data verify-cache` | Passed; all nine pinned sources, no issues |
| `uv run kasm patient-journey outcome-components` | Passed offline; complete ignored run below |
| Repeat component command | Expected exit 1: existing run cannot be overwritten |
| Separate read/calculate/render audit | All five payloads reproduced byte-for-byte; all manifest sizes/hashes agree |
| `uv run streamlit run app/streamlit_app.py --server.headless true --server.port 8504 --browser.gatherUsageStats false` (via the same Python module entry point) | `/_stcore/health` returned `ok`; temporary hidden process stopped |
| Docker build with installed `%LOCALAPPDATA%/Programs/DockerDesktop/resources/bin/docker.exe` | Initially blocked: Linux engine pipe absent; resolved in the repair record below |
| Local links and `git diff --check` | Passed; 162 local links across the eight touched/new documents |
| Protected input/result SHA-256 comparison | All 43 recorded files unchanged |

The reviewed ignored run is
`data/patient_journey_v2_followup/outcome_components_v1/e95ab9db56aad000f6a296c33fb4ad981a57b39f70ba2a6a0adb4b3fe388171b`.
Its five payloads total 1,055,740 bytes, plus the completion manifest. The manifest records the
dirty worktree, exact implementation/input/configuration/ledger/specification/lock hashes, UTC
build time, timing and no-fitted-model state. See the [results](../patient_journey_v2_component_results.md)
for identities and the reproduction command. These are development outputs, not a new release.

The separate reproduction audit used the same importable calculation without invoking a writer:

```python
original, records, metadata = read_component_inputs(root, root / DEFAULT_CONFIG)
evidence = analyze_components(
    records, original.rows, original.stored_predictions,
    load_component_config(root / DEFAULT_CONFIG),
)
files = render_component_report(evidence) | {
    "analysis.json": _json_bytes(evidence),
    "components.json": component_payloads(records),
}
# Compare every payload byte, size and SHA-256 with the completed run;
# rehash each entry in p3_preservation_before.json and require no change.
```

### Docker startup repair and P3 verification closure — 2026-09-07 UTC

P3's first Docker build could not reach `dockerDesktopLinuxEngine`. The backend logs showed
inaccessible `sailor-ingest.sock` and then `docker-secrets-engine/engine.sock` runtime endpoints.
The initial nonrecursive removal attempt failed: neither endpoint was removed, despite a
misleading success message from the shell script. No image or health success was claimed then.

After verifying that the stopped engines' runtime directories contained only zero-byte sockets,
the directories were preserved and replaced with empty runtime directories. Backups remain at
`%LOCALAPPDATA%/Docker/run.before-repair-20260907-101556`,
`%LOCALAPPDATA%/Docker/run.before-repair-20260907-101923` and
`%LOCALAPPDATA%/docker-secrets-engine.before-repair-20260907-101923`.
No settings, credentials, WSL disk, existing images or containers were removed. Docker Desktop
`4.89.0 (238018)` then started Linux Engine `29.7.2`. This resolved the occurrence without
establishing why the sockets became inaccessible.

The following commands used the installed executable at
`%LOCALAPPDATA%/Programs/DockerDesktop/resources/bin/docker.exe`:

| Command or check | Result |
|---|---|
| `docker version --format '{{json .Server}}'` | Passed; Linux Engine `29.7.2` responds |
| `docker build -t kidney-acceptance-signal-monitor:v2-components .` | Passed; locked production dependencies installed and image exported |
| `docker run --detach --network none --name kasm-docker-repair-20260907-1523 kidney-acceptance-signal-monitor:v2-components` | Passed; temporary container became `healthy` |
| `docker inspect` user, network, health and image | `kasm`, `none`, `healthy`; image `sha256:51405749377b46f6598e04b2aec1dd8de468edb85da0139f5f9e71523fb76a3b` |
| `docker exec kasm-docker-repair-20260907-1523 id -u` | `10001` (non-root) |
| Python `urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=5)` inside the container | Returned `ok` with networking disabled |
| `docker rm -f kasm-docker-repair-20260907-1523` | Removed only the temporary smoke container; Docker remains running |

The image contains the retained V1 app bundle; this verifies the existing container, not a
new V2 container release. The six required repository commands were rerun: sync passed
(74 packages), Ruff format/check passed (80 files), mypy passed (39 source files), 493 tests
passed in 38.27 seconds with 84.08% combined coverage, and V2 coverage passed at 83.62%.
All 43 protected input/result hashes remained unchanged. No analytical writer or replay ran.
This closed P3's remaining verification gap.

### P4 Build the explanation and interview package

The [V2 follow-up package](../presentation/v2-followup/README.md) contains a 17-slide editable
deck (15 main slides for an 18-minute story and two appendices), self-contained HTML backup,
source-bound ALUA:TX1 case, short demo/rehearsal guide and reproducible authoring/provenance.
Four charts have embedded workbooks and two model tables remain editable. Its eight files
total 490,114 bytes. The original V1 presentation remains preserved.

The illustrative-case rule sorted original eligible `2205→2505` programs by composite key,
required complete prior/outcome/component evidence, earlier overall OAR above 1 and a lower
later published functioning percentage, and chose the first match. Independent extraction
confirmed 61 qualifying programs and the selected case's joins, dates, count and values. This
is an editorial example, not a ranking, representative sample or estimate of clinical impact.

The author's own-words walkthrough, timed rehearsal and native presentation-machine font
check remain unrecorded. Key discussion requirements are the comparison model's report-count
behavior, the listing denominator, unknown status versus censoring, the single usable evaluation
period, V1's actual bias-rule failure and what additional evidence would be useful.

### P4 package preparation and verification — 2026-09-07 UTC

- Independent review checked all 13 model approaches and six displayed contrasts against the
  completed JSON. Review corrected an overly categorical unknown-status heading, percentage-label
  precision and a chart/footer overlap. The final claim leaves causes unresolved.
- All 17 slides were rendered and inspected. Package, layout, font-policy, import and native
  chart-workbook checks passed. A second build reproduced all rendered PNGs and the HTML bytes;
  package IDs/timestamps may differ. The HTML has no scripts, external assets or server dependency.
- `uv sync --frozen`, Ruff format/check and mypy passed (74 packages, 80 Python files, 39 source
  files). The required suite passed 493 tests in 37.22 seconds: 84.08% combined coverage and
  83.62% V2 coverage. All 72 protected hashes and 188 local links passed verification.
- With `socket.socket.connect` blocked, AppTest verified ALUA selection, candidate count 548,
  displayed outcome 17.5%, month-precision origin and original nonpromotion. The live app's
  loopback health and program/method routes also passed. An initial scratch assertion expected
  slash-separated dates; correcting it to the app's valid `2025-07-08` fixed the test expectation.
- Build used runtime `26.905.11957`, Node `24.19.0` and artifact-tool `2.8.59`.
  `node --check docs/presentation/v2-followup/build.mjs` and `git diff --check` passed.
  The unsupported embedded-font decode warning remained; native PowerPoint/Google Slides font
  appearance was not checked. The independent HTML backup uses a system font.

Final ignored build: `data/patient_journey_v2_followup/p4_build/final03`; reproduction is its
sibling `reproduction` directory. PPTX SHA-256:
`0dbefa72281f36c0460c50bcef25e8f17a7facfffaa4feb24caff44f95c51c4e`.
The preservation snapshot is `p4_build/preservation-before.json`. Original source/configuration,
release and P1–P3 hashes matched. No analytical writer, model fit, source/cache rebuild,
Docker rebuild or frozen replay was run for this presentation-only batch.

### User-led data walkthrough — 2026-09-07

The later [project walkthrough](../presentation/data-walkthrough/README.md) follows source data,
QA, V1 and an app bridge, original V2, the two follow-ups, delivery and conclusions. Its final
25 slides contain 19 main slides and six optional references. This is a documentation artifact
built from completed evidence; it adds no comparison or analytical release.

The source-QA example independently verified July 2025 Table B7 rows 3–5 as ALCH:TX1, ALUA:TX1
and ALVA:TX1, while the acceptance sheet's same rows are PAUP:TX1, VANG:TX1 and MDUM:TX1.
ALUA's correct acceptance match is row 74. The tables have 234 and 230 programs: 229 shared,
five B7-only and one acceptance-only. Same-release identity matching does not make their different
measurement periods eligible for a predictor/outcome join.

The first two source slides matched all 12 extracted workbook cells. Subsequent QA/V1 additions
preserved the earlier approved slide content; source checks verified the OAR formula, interpretation,
uncertainty, ALUA example and original modeling evidence. The complete 24-slide build reproduced
all rendered PNGs, including five editable charts and six tables. Independent review corrected
month-only date precision and record/feature descriptions before final verification.

`DATA_SLIDES_BUILD_NAME=opening-slide-03` produced the final 25-slide introduction version.
It preserved the preceding 24 slides' content and appearance apart from numbering. All final
renders, package, layout, editable-evidence and font-policy checks passed without layout warnings.
The original PPTX was open and locked, so the reviewed introduction version and its provenance
were saved as `data-walkthrough-with-introduction.pptx` and a separate companion file. Both are
retained. Native font appearance and the author's timed rehearsal were not established by renders.

Each delivery ran the six required repository checks. The final run passed frozen sync,
Ruff format/lint and mypy; 493 tests passed with 84.08% combined and 83.62% V2 coverage.
An earlier run found two provenance failures from CRLF checkout bytes in original V2
`experiment.yaml` and `methodology.yaml`. Their committed bytes matched the original manifest;
restoring those exact bytes fixed both focused tests (two passed in 1.60 seconds) and the full
suite without a content diff or altered source/configuration identity. The remaining 24 files
in the 26-file preservation snapshot stayed byte-identical. No source, fitted model, original
release, app, lock or analytical behavior changed in these slide deliveries.
