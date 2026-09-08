# Project walkthrough

[Open the complete PowerPoint](data-walkthrough-with-introduction.pptx): **19 main slides and six optional reference
slides**, with editable charts/tables and speaking notes. This is the current corrected package.
It preserves the author's approved sequence and visual design. Selecting and timing a shorter
20-minute interview edition, the author's spoken rehearsal and presentation-machine checks
remain separate work.

For personal study alongside slides 2–8 and 21–22, read the
[V1 data dictionary](../../v1-data-dictionary.md). Start with its actual ALUA source record
and input–outcome pair, then use the field tables as a reference. Its acceptance records
are separate from the V2 Table B7 example shown at the start of this deck.

The September 8 correction fixes July 2026 Table B7 to **July 2023–June 2024** listings, recognizes
the completed additional-period receipt study, and replaces the obsolete bias-rule appendix
with actual forecast errors. The original exact-bias rule was a design mistake. Current slides
also identify SRTR's changed included-offer definitions in July 2025 and January 2026. See the
[listing-date audit](../../audits/source-feasibility-0022.md),
[offer-definition audit](../../audits/source-definition-0029.md), and
[current interpretation](../../decisions/0016-retire-bias-gate-and-correct-readiness.md).

The earlier [walkthrough without the introduction](data-walkthrough.pptx) and its
[provenance](package-provenance.json) are historical and superseded. They retain obsolete
statements. [Other historical presentation packages](../README.md) are also outside current use.

## Principles inferred from the author's walkthrough

1. Show actual data before the machinery: one row, identifiers, dates, denominator and units.
2. Let natural questions drive the order, including why simpler approaches are insufficient.
3. Pair an overview with a concrete row, calculation, chart, result or app demonstration.
4. Keep useful math explainable in ordinary language; label hypothetical examples clearly.
5. Compare models with simple alternatives and explain the errors that matter to the task.
6. Reuse ALUA to connect the workbook, app and outcome discussion, without treating it as
   representative or as evidence of clinical quality.
7. Distinguish original findings, later investigation, uncertain conclusions and proposed work.
   Put optional detail in notes and appendices; focus the spoken story on meaning.

## Walkthrough order

| Slides | Question answered |
|---|---|
| 1 | What is the project trying to accomplish? |
| 2-3 | Where do the data come from, and what does a source record mean? |
| 4-5 | What do the checks before modeling protect against? |
| 6-7 | What does OAR mean, and how did V1 compare projections? |
| 8 | What can someone learn from the V1 app? |
| 9-12 | What does V2 ask, count and compare, and what was public when? |
| 13-15 | Why was the initial result attractive, and what changed after investigation? |
| 16-17 | What does known functioning mean for interpreting the outcome? |
| 18-19 | How is evidence delivered, and what remains before a new forecast release? |
| 20-25 | CSVs, transforms/Ridge, V1 errors, all V2 errors, corrected cohorts and unknown follow-up |

The workbook example shows four named columns from July 2025 Table B7, Excel rows 3-5 after its
two header rows. It is a schema illustration. The QA example compares source-order program keys
across two sheets; their different measurement periods prevent interpreting it as a valid
predictor/outcome join. Source definitions and selection rationale remain in the speaking notes.

## V1 app demonstration

Run `uv run streamlit run app/streamlit_app.py` from the repository root. On **Program monitor**,
select **University of Alabama Hospital (ALUA) — Birmingham, AL**.
Slide 8 provides a static history chart if the app is unavailable.

1. Show overall OAR: 0.74 in 2017, 2.00 in 2021, 0.81 in 2023 and 1.11 in 2025.
   Inspect SRTR's credible intervals. The latest 95% interval, 0.95-1.28, includes 1.
2. Show donor-stratum history and latest detail. High-KDRI OAR is 0.41 (0.15-0.81), while
   hard-to-place OAR is 0.16 (0.03-0.39). Hard-to-place overlaps KDRI groups; they cannot be summed.
3. Show **Next-calendar-year PSR projection**. Persistence carries 1.11 into calendar 2026.
   The origin is July 7, 2026, with 51.5% of the year elapsed: a delayed-report nowcast.
4. Open **Model evaluation and methodology**. Explain actual errors, the unchanged historical
   app, and source-definition limits. The later fitted adjustment remains a research candidate,
   with bands withheld. The old exact-bias rule is withdrawn.

SRTR changed which offers count in July 2025 and January 2026. The audit establishes those
definitions but does not quantify their effect on these scores. ALUA is illustrative and cannot
explain why the signal changed or diagnose care. V2 slides compare
all models on the same 218 programs. The original V2 app's baseline summaries span more periods
and should not be compared directly with its one-period Ridge results. The later follow-up does
not replace the original app's evidence.

## Sources and reproduction

[Slide text and speaking notes](slides.json) contain supporting source paths and URLs.
[The builder](build.mjs) uses the earlier [V2 deck](../v2-followup/interview.pptx) as its visual
reference. [Package provenance](package-provenance-with-introduction.json) is generated with the deck. This is a
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

The presentation finalizer checks slide count, package integrity, geometry and editable tables
and charts. Rendered inspection covers all 25 final slides. The artifact renderer emits an
inherited Helvetica Neue embedded-font decode warning, so native PowerPoint rendering and fonts
still require checking on the presentation machine. The build does not perform model fitting or
scientific validation. The [active plan](../../plans/0029-interview-readiness-corrections.md)
records this correction's verification separately from application checks.

The author's complete walkthrough and timed rehearsal remain pending.

Public aggregate research prototype. Not clinical or regulatory decision support.
