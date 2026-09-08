# V2 follow-up interview rehearsal guide

**Historical and superseded.** Use the [current corrected walkthrough](../data-walkthrough/README.md).
The retained PowerPoint and HTML contain a known July 2026 listing-date error and an obsolete
V1 selection narrative. These notes preserve the earlier package, with current clarifications.

The historical [editable deck](interview.pptx) planned an **18-minute story with a two-minute buffer**.
The [offline HTML backup](interview-backup.html) carries the story independently; the
[program-case note](program-case.md) supplies the selected program's exact evidence and dates.
The two-minute app demonstration below can also stand alone. Its compressed 90-second version
fits slide 13. The two appendix slides keep all 13 approaches and source/unit details available
for questions; they are outside the planned 18 minutes.

This package presents the completed original V2 study and two later exploratory investigations.
The live app still shows the original study. The follow-up comparisons and donor components are
static presentation evidence; they have not become app features or future forecasts. Keep the
[original V1 rehearsal package](../interview-rehearsal-guide.md) as its separate retained record.

**Readiness status:** speaking times below are allocations, not measured performance. The
author's own-words walkthrough, timed rehearsal, and presentation-machine checks remain pending.
Complete the log at the end before claiming interview readiness.

## The explanation to own

Practice this idea without memorizing its wording:

> I asked whether earlier public kidney-program reports help predict the percentage of newly
> listed candidates known to be alive with a functioning transplant 18 months later. A large
> apparent gain from acceptance information became small after a separate investigation removed
> an input counting earlier reports. I also checked the unknown part of the published outcome.
> These results help explain the study's limits; one already-inspected evaluation period does
> not establish future performance or support a clinical decision.

Define terms when they first matter. SRTR is the Scientific Registry of Transplant Recipients;
a PSR is a Program-Specific Report. A cohort is the group defined by its listing dates. Ridge
fits a prediction formula while limiting the size of its input weights. A baseline is a simple
comparison prediction. Mean absolute error, or MAE, is the average size of an error regardless
of direction. In V2 it is measured in **percentage points**: predicting 40% when the published
outcome is 30% gives a ten-point error.

## Planned 18-minute delivery

Use the running clock to decide how much detail to give. The table names each slide's role;
the slide title may express the takeaway more briefly.

| Slide | Planned time | Running clock | Explain in your own words |
|---|---:|---:|---|
| 1. Question and problem | 1:00 | 0:00–1:00 | A program wants useful context from earlier public reports. One record describes a kidney program and a listing group. This is aggregate research for quality-improvement review. |
| 2. What V1 taught us | 1:00 | 1:00–2:00 | Ridge lowered average absolute log-OAR error by 10.13% in the fixed 2025 replay. The exact-bias rule that rejected the gain was a design mistake, now withdrawn. The unchanged historical app retains persistence. |
| 3. Define the V2 target | 1:30 | 2:00–3:30 | The published percentage counts those known alive with a functioning transplant at 18 months among everyone originally listed, including people never transplanted. It combines living and deceased donation and is not officially risk adjusted. |
| 4. Explain unknown outcomes | 1:30 | 3:30–5:00 | Unknown post-transplant status establishes neither success nor failure. The matched 218 programs have a median combined unknown percentage of 16.05% of their listing groups. This is a median across programs; the four component medians cannot be added. |
| 5. Show both timing rules | 1:30 | 5:00–6:30 | Inputs must have been public by the prediction origin, and their measurement periods must end before the target listing group starts. Month-only publication dates keep their month precision. |
| 6. Explain the original configured split | 1:30 | 6:30–8:00 | Fit 215 programs from the July 2019–June 2020 listing group and evaluate 218 from July 2022–June 2023. The earlier outcome became public in July 2022. This describes the original configuration. The corrected July 2026 report covers July 2023–June 2024 listings, which the later receipt study used separately. |
| 7. Show the original comparison | 1:00 | 8:00–9:00 | On those same 218 programs, average errors were 11.49 points for history-only Ridge, 7.35 for history plus acceptance, and 7.61 for the simple historical average. The 4.14-point and 0.26-point gains answer different comparisons. |
| 8. Diagnose report count | 1:00 | 9:00–10:00 | Count was two for 212 of 215 training programs and five for 208 of 218 evaluation programs. It counts available reports, not program age. The original model extended a relationship learned over very little training variation. |
| 9. Show the fixed removal comparison | 1:00 | 10:00–11:00 | Removing only report count reduced history-only Ridge's error to 7.32 points; history plus acceptance reached 7.23. The observed added gain from acceptance was about 0.09 points. |
| 10. Keep uncertainty and all comparisons visible | 0:45 | 11:00–11:45 | The revised acceptance-minus-history error difference has descriptive interval [−0.491, 0.301] points. Report the unfavorable additions too. Resampling whole programs does not create another time period. |
| 11. Explain component associations carefully | 1:15 | 11:45–13:00 | All 218 evaluation programs match the component source. Unknown status was compared with every original model's errors. Shared denominators and error arithmetic limit interpretation; association cannot establish that reporting caused an error. |
| 12. Walk through the ALUA case | 1:30 | 13:00–14:30 | University of Alabama Hospital, ALUA:TX1, had calendar-2021 acceptance ratio 2.00 in the July 2022 report. Published functioning outcomes were 28.07% for the July 2019–June 2020 listing group and 17.52% for July 2022–June 2023. Name each denominator and the disclosed illustrative selection rule. |
| 13. Demonstrate the original offline app | 1:30 | 14:30–16:00 | Select ALUA:TX1, identify the 2205→2505 history row and original historical predictions, then show provenance and the no-promotion boundary. Return to the static package for the later follow-up. |
| 14. Explain the engineering evidence | 1:00 | 16:00–17:00 | Verified source files, publication cutoffs, typed contracts, training-only preprocessing, regression tests, preserved artifacts, and an offline view make the calculation inspectable. Explain one concrete check you understand. |
| 15. Ask for the next useful evidence | 1:00 | 17:00–18:00 | A new non-overlapping, definition-compatible outcome period with choices locked beforehand would test performance across time. Understanding unknown follow-up additionally needs records that preserve observation and event timing. |
| Questions or delay | 2:00 | 18:00–20:00 | Use the prepared answers below. This buffer is separate from the planned story. |

If running late, shorten the narration of all-model tables and leave their full values available
for questions. Retain the denominator, publication rule, simple historical-average comparison,
single-period limitation, and original-versus-follow-up distinction. If the app stalls, move to
the static case immediately and keep speaking; troubleshooting belongs outside the presentation.

## Standalone two-minute offline demonstration

Install the locked environment before the offline session, from the repository root:

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
uv sync --frozen
```

Then disconnect networking and start the existing optional V2 view:

```powershell
uv run streamlit run app/patient_journey_v2.py
```

Open the local address printed by Streamlit. This command serves the trusted original release;
it does not run the follow-up analyses. Keep the local HTML backup open in a second window.
Before presenting, test selecting the case again after a fresh app launch with networking
disabled. Record that presentation-machine check below; successful automated checks elsewhere
are separate evidence.

| Planned time | Action | What to say or verify |
|---|---|---|
| 0:00–0:20 | In **Kidney transplant program**, select **University of Alabama Hospital** and confirm **Program key ALUA:TX1** beneath the heading. | “This is one program's public history. The banner identifies aggregate, nonclinical and nonregulatory research; zero models are promoted.” |
| 0:20–0:50 | On **Program history**, locate feature release **2205**, target release **2505** in **Published patient-journey history**. | Identify the July 2022 prediction origin, July 2022–June 2023 listing group, July 8, 2025 publication, 548 candidates and about 17.52% known functioning. The app rounds displayed percentages; the [case note](program-case.md) retains the exact values. |
| 0:50–1:15 | Scroll to **Feature-release access and acceptance context**, then **Historical evaluation for this program**. | Point to the earlier offer-acceptance ratio, 2.00, and later functioning percentage. Their definitions and dates differ. The saved predictions concern an already-published cohort; this screen offers no future forecast. |
| 1:15–1:35 | Open **Model evidence** and read the scope message before its table. | “The app preserves the original study. Its baseline summaries span four target releases, while Ridge has one usable split. The static follow-up compares all approaches on the same 218 programs.” Do not compare the app's mixed-scope headline errors as though they use the same rows. |
| 1:35–2:00 | Open **Methods and provenance**, show the bundle identity and limitations, then return to the static case. | “This view reads a saved, verified bundle. Removing report count and describing donor/unknown components are separate later investigations shown in the presentation. Neither investigation promotes a model.” |

For slide 13's 90-second version, preselect ALUA, use 20 seconds on the banner and history row,
30 seconds on earlier acceptance and saved predictions, 20 seconds on provenance, and 20 seconds
to return to the static case and identify the later follow-up. Explain the mixed-scope app table
only if opening **Model evidence**; the full two-minute version includes it explicitly.

The **Safety context** tab is available for a question, but it is outside this short route.
Its mortality and graft-failure ratios have their own measurement periods and denominators;
they cannot be added to the patient-journey percentages or turned into a composite score.

## Independent static route

Open [interview-backup.html](interview-backup.html) locally and follow the same slide order.
For a standalone two-minute case, use the selected-program evidence, original results, fixed
report-count comparison, and limitations. The backup is a static presentation, so describe its
tables as saved evidence rather than live app controls. The [case note](program-case.md) is also
readable without running Python. No live source page is needed during either route.

The source documents remain available for detailed questions:

- [Original V2 model card](../../patient_journey_v2_model_card.md) and
  [scientific specification](../../specs/patient-journey-v2.md).
- [Report-count follow-up: all five revisions and 12 comparisons](../../patient_journey_v2_followup_results.md).
- [Matched donor and unknown-status results](../../patient_journey_v2_component_results.md) and
  [source definitions](../../patient_journey_v2_component_ledger.md).
- [V1 frozen result and promotion rules](../../model_card.md).
- [Project explanation, including censoring](../../project-guide.md) and
  [Plan 0020 verification evidence](../../plans/0020-v2-follow-up-and-interview-story.md).

## Likely panel questions

**Why was report count a problem if it was available at prediction time?**

Availability prevents future information from entering the model; it does not guarantee a
useful relationship. Count mostly measured the growth of this selected report collection.
Training counts were usually two and evaluation counts usually five. The mean shift was 25.069
training standard deviations, partly because the training variation was so small. In original
history-only Ridge, count contributed +0.532598 to a total mean prediction shift of +0.518134 on
the model's logit scale. Other inputs partly offset it. Those are contributions to a fixed
calculation before conversion to percentages, not patient effects or percentage-point changes.
The follow-up first reproduced all 1,744 original evaluation predictions exactly, then removed
only that input under its separate fixed contract.

**What does acceptance add after the follow-up?**

On the same 218 programs, revised history-only Ridge has 7.320-point average error and history
plus acceptance has 7.226. The added reduction is about 0.09 points, with descriptive
error-difference interval [−0.491, 0.301]. Compared with the simple historical
average, the revised acceptance model is 0.383 points lower, with interval [−0.852, 0.103]. The
observed improvement is small and its future value remains uncertain. Adding acceptance to the
revised history-plus-access model instead raises average error by 0.125 points. Keep that result
visible too. These findings concern these prediction formulas; they do not measure the clinical
importance of acceptance or access.

**Why does the original configuration have one fitted evaluation period?**

The training outcome must already have been published at the later prediction origin. In July
2022, the outcome for candidates listed July 2019–June 2020 was available, allowing that group
to train predictions for July 2022–June 2023. The earlier configured prediction dates had no
earlier configured outcome available for fitting Ridge. The original ledger mistakenly excluded
the July 2026 report for overlap. It actually covers July 2023–June 2024 listings, following the
previous group without overlap. The separate receipt study subsequently evaluated that period
under its own target and configuration. Four original baseline periods do not establish four
original fitted-model evaluations, and the corrected date creates no new independent validation.

**What does the bootstrap interval tell you?**

It repeatedly samples whole programs and compares both approaches on each same draw. The V2
follow-up uses 2,000 resamples, seed `20260904`, and the 2.5th and 97.5th percentiles. It describes
variation across the programs observed in this fixed period. It does not create a new year,
remove the consequences of having inspected these outcomes, or account for every source of
uncertainty. We report descriptive intervals and preserve all fixed comparisons; we do not
choose a new production winner from them.

**Is unknown follow-up just censoring? Could you use survival analysis?**

Unknown here means a candidate's status is unavailable at a specified time; it can include a
follow-up form not yet due. It does not itself supply the time of an event or the last time
someone was known to be event-free. Survival methods need that timing, or equivalent event and
observation counts over time, with suitable assumptions about people whose observation ends.
Aggregate data can support such methods when those details are preserved. These Table B7
snapshots do not preserve them, so this analysis does not apply a censoring correction or
estimate the unknown outcomes. The target also includes receiving a transplant and documented
functioning status among everyone listed; it is not simply survival among recipients.

**Does the 16.05% unknown figure mean that share of all patients is missing?**

It is the median of 218 program percentages. Each program first adds its living- and
deceased-donor post-transplant unknown percentages, both divided by its original listing group.
We then take the middle program percentage. We do not pool patients, and people can be listed
at more than one program. The earlier 16.27% figure uses a broader set of 222 source programs.
All 218 evaluation programs have complete donor-component fields, so missing component cells
do not account for this matched result.

**Did unknown reporting explain the prediction errors?**

The matched description does not establish that. It reports associations for all eight original
approaches. For example, unknown status and signed error have correlation 0.089 for original
history-plus-acceptance Ridge, while unknown status and the published functioning percentage
have correlation 0.301. Correlation is a unitless measure of whether values tend to move together
across programs. Functioning and unknown percentages share a denominator and mutually exclusive
statuses, and signed error directly subtracts the observed percentage. Reporting, actual outcomes,
and other differences could contribute. The analysis leaves unknown outcomes unresolved.

**Why choose this program, and what does its example show?**

The disclosed editorial rule sorts eligible evaluation programs by composite program key,
requires complete prior/outcome/component evidence, an earlier overall offer-acceptance ratio
above 1 and a lower later published functioning percentage, then takes the first match among
61 qualifying programs. That is ALUA:TX1. It illustrates why two differently defined measures from different periods need
separate explanations. It is not representative sampling, a ranking, evidence that acceptance
caused the outcome, or a judgment about the program's care. The case note preserves the rule and
the exact numbers so the selection is reviewable. Its later combined post-transplant unknown
percentage is 22.99% of the 548 originally listed candidates. That value does not fill in their
outcomes or establish the reason for the lower published functioning percentage.

**What evidence would you request next?**

The completed receipt follow-up found a small acceptance increment across two historical periods.
Any future comparison needs compatible definitions, verified publication timing and a design fixed
before scoring. An unseen period would add evidence about performance over time. For the unknown-status
question, request a documented account of reporting completeness and data that preserve event
and last-observed timing, or equivalent aggregate event and observation counts. Such a request
would need its own study scope and governance. The current public-data project does not acquire
nonpublic records or fill in unknown patient outcomes.

**Why retain persistence in V1 when Ridge improved?**

Ridge's average absolute log-OAR error was 0.2399 versus 0.2670, a 10.13% reduction. It passed
the improvement criterion but failed the fixed requirement that its absolute mean signed log
error be no greater than persistence: 0.01145 versus 0.00885. Every point-promotion criterion
had to pass. Retaining persistence follows the specified product rule; it does not prove that
persistence is clinically safer or that Ridge failed on every measure. Those V1 units and rules
are separate from V2's percentage-point errors and prohibition on model promotion.

**How did you verify AI-assisted work?**

Explain checks you can trace yourself: specifications and typed configurations fixed the study;
hashes identified immutable sources; machine field names and methodology ledgers fixed their
meaning; small regression cases tested timing, missingness, joins and write protection; and
training-only preprocessing prevented evaluation rows from setting model inputs. The separate
follow-up reconstructed saved predictions, preserved original hashes and reproduced its outputs.
Independent review checked scientific meaning and numerical evidence. Use the active plan for
the exact commands and their recorded outcomes. Tests are necessary evidence, but passing tests
cannot establish that a scientific question or claim is valid. Do not imply the author has
personally reviewed every check before completing the walkthrough below.

## Own-words walkthrough and honest rehearsal record

Have the author explain each item without reading the prepared answer. A reviewer should ask
one follow-up and record where the explanation became unclear. Correct the explanation and
repeat that item; a checked box records demonstrated understanding, not document completion.

- [ ] State the question, what one row represents, the listing denominator and 18-month outcome.
- [ ] Explain one hypothetical percentage-point error and distinguish it from percent change.
- [ ] Explain the original configured split and corrected additional July–June listing period.
- [ ] Distinguish history-only Ridge from the simple historical average using the original errors.
- [ ] Explain how available report count shifted and what the fixed removal comparison changes.
- [ ] Describe what the paired program interval can and cannot establish.
- [ ] Explain unknown status, why medians cannot be added, and what timing survival methods need.
- [ ] Walk the ALUA case, its selection rule and dates without making a causal or quality claim.
- [ ] Trace one source value and one meaningful regression test through the repository.
- [ ] Explain V1's 10.13% log-OAR MAE gain, the withdrawn bias rule and separate V2 contract.
- [ ] State the next useful evidence request and why no future V2 forecast is exposed.

All entries begin **pending**. Add actual dates, observed times and corrections after each session.

| Check | Date and reviewer/machine | Measured time | Observed issue or correction | Status |
|---|---|---:|---|---|
| Author's own-words walkthrough | Pending | Not measured | Record answers and follow-up questions above | Pending |
| Full story, including compressed demo | Pending | Not measured | Target 18:00; record slide transition times | Pending |
| Standalone offline app demonstration | Pending | Not measured | Target 2:00; verify ALUA selection with networking disabled | Pending |
| Independent static-backup route | Pending | Not measured | Open the local HTML without the app or network | Pending |
| Panel-question rehearsal | Pending | Not measured | Record questions that require a clearer answer | Pending |
| Final presentation-machine run | Pending | Not measured | Confirm readable text, switching windows and two-minute buffer | Pending |

After rehearsing, record the evidence in [Plan 0020](../../plans/0020-v2-follow-up-and-interview-story.md).
Keep a failed or over-time run in the record and add the subsequent correction. Creating the
deck, demonstrating automated app health, or reading this guide alone does not complete the
author walkthrough or establish interview readiness.

Public aggregate research prototype — not clinical or regulatory decision support.
