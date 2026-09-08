# Project walkthrough

[Open the complete PowerPoint](data-walkthrough.pptx): **18 main slides and six optional reference
slides**, with editable charts/tables and speaking notes. This pass has no time limit. The first
six slides preserve the author's approved data, QA and V1 sequence.

## Principles inferred from the author's walkthrough

1. Show actual data before the machinery: one row, identifiers, dates, denominator and units.
2. Let natural questions drive the order, including why simpler approaches are insufficient.
3. Pair an overview with a concrete row, calculation, chart, result or app demonstration.
4. Keep useful math explainable in ordinary language; label hypothetical examples clearly.
5. Judge models against simple alternatives and the rules fixed for their study.
6. Reuse ALUA to connect the workbook, app and outcome discussion, without treating it as
   representative or as evidence of clinical quality.
7. Distinguish original findings, later investigation, uncertain conclusions and proposed work.
   Put optional detail in notes and appendices; focus the spoken story on meaning.

## Walkthrough order

| Slides | Question answered |
|---|---|
| 1-2 | Where do the data come from, and what does a source record mean? |
| 3-4 | What do the checks before modeling protect against? |
| 5-6 | What does OAR mean, and how did V1 compare projections? |
| 7 | What can someone learn from the V1 app? |
| 8-11 | What does V2 ask, count and compare, and what was public when? |
| 12-14 | Why was the initial result attractive, and what changed after investigation? |
| 15-16 | What does known functioning mean for interpreting the outcome? |
| 17-18 | How is evidence delivered, what was established, and what comes next? |
| 19-24 | CSVs, transforms/Ridge, V1 rules, all V2 errors, cohorts and unknown follow-up |

The workbook example shows four named columns from July 2025 Table B7, Excel rows 3-5 after its
two header rows. It is a schema illustration. The QA example compares source-order program keys
across two sheets; their different measurement periods prevent interpreting it as a valid
predictor/outcome join. Source definitions and selection rationale remain in the speaking notes.

## V1 app demonstration

Run `uv run streamlit run app/streamlit_app.py` from the repository root. On **Program monitor**,
select **University of Alabama Hospital (ALUA) — Birmingham, AL**.
Slide 7 provides a static history chart if the app is unavailable.

1. Show overall OAR: 0.74 in 2017, 2.00 in 2021, 0.81 in 2023 and 1.11 in 2025.
   Inspect SRTR's credible intervals. The latest 95% interval, 0.95-1.28, includes 1.
2. Show donor-stratum history and latest detail. High-KDRI OAR is 0.41 (0.15-0.81), while
   hard-to-place OAR is 0.16 (0.03-0.39). Hard-to-place overlaps KDRI groups; they cannot be summed.
3. Show **Next-calendar-year PSR projection**. Persistence carries 1.11 into calendar 2026.
   The origin is July 7, 2026, with 51.5% of the year elapsed: a delayed-report nowcast.
4. Open **Model evaluation and methodology**. The fixed bias rule explains why the app retains
   persistence and suppresses the Ridge band. The decision uses the full evaluation population.

ALUA is illustrative; it cannot explain why the signal changed or diagnose care. V2 slides compare
all models on the same 218 programs. The original V2 app's baseline summaries span more periods
and should not be compared directly with its one-period Ridge results. The later follow-up does
not replace the original app's evidence.

## Sources and reproduction

[Slide text and speaking notes](slides.json) contain supporting source paths and URLs.
[The builder](build.mjs) uses the earlier [V2 deck](../v2-followup/interview.pptx) as its visual
reference. [Package provenance](package-provenance.json) is generated with the deck. This is a
documentation build; it fits no models and changes no analytical release bundles.

Run with the supplied desktop runtime and a fresh build directory name:

```powershell
$env:RUNTIME_NODE_MODULES = 'C:/Users/chris/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:RUNTIME_PYTHON = 'C:/Users/chris/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PRESENTATIONS_SKILL_DIR = 'C:/Users/chris/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations'
$env:DATA_SLIDES_BUILD_NAME = 'complete-walkthrough-reproduction'
& 'C:/Users/chris/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' docs/presentation/data-walkthrough/build.mjs
```

Outputs appear in ignored `data/patient_journey_v2_followup/p4_build/<build-name>/`: `delivery`
contains the PowerPoint and provenance, with slide PNGs and validation outside it. The builder
refuses an existing directory and does not overwrite the checked-in deck. PPTX metadata and
object IDs may vary between builds; displayed content is reproducible.

All 24 final slides are rendered and inspected. Content, editable evidence, package structure,
layout and the six required repository checks pass. The artifact renderer emits the inherited
Helvetica Neue embedded-font decode warning; rendered text remains legible. Native PowerPoint
rendering and fonts still need checking on the presentation machine during the author's rehearsal.

The author's complete walkthrough remains pending. These completion changes stay uncommitted;
the author will decide when to make the single eventual presentation commit.

Public aggregate research prototype. Not clinical or regulatory decision support.
