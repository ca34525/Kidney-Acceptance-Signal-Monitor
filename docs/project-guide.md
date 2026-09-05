# Understanding the project and the next investigation

This guide explains what the project does, what the original V2 results and report-count follow-up
say, and what remains to investigate. It is written for the author preparing a 20-minute interview presentation and
for readers who want the meaning before the statistical details.

Ordinary language is a project requirement. Precise equations, field names, and methods remain in
the linked specifications and code. Explain the idea first, then give the technical term when it
helps someone check or implement the work.

## What V1 and V2 do

V1 helps a kidney transplant program review its published offer-acceptance history. The published
offer-acceptance ratio compares acceptances with what SRTR expected for the offers received. It is
different from simply dividing accepted offers by all offers. V1 also tests whether a model can
predict the next published annual ratio better than carrying the latest value forward.

V2 asks a broader question: do earlier public reports help predict what percentage of listed
candidates will be known to be alive with a functioning transplant 18 months after listing? It
compares earlier outcomes with additional information about access to transplant, offer acceptance,
and a separately defined safety measure.

The records describe programs and groups of listed candidates. They do not describe individual
offers or patients. The project supports research and quality-improvement review; it cannot tell
a patient which program to choose, establish a program's clinical quality, or prescribe an organ
acceptance decision.

| Work | Current state | Detailed record |
|---|---|---|
| V1 acceptance monitor | Released; carries the latest ratio forward because Ridge missed a frozen promotion rule | [V1 model card](model_card.md) |
| Original V2 patient-journey study | Completed exploratory study; no model promoted and no future forecast displayed | [V2 model card](patient_journey_v2_model_card.md) |
| V2 follow-up | Report-count diagnosis and fixed revised comparison complete; unknown follow-up investigation remains planned | [Follow-up results](patient_journey_v2_followup_results.md) |

The first pass is complete as of 2026-09-05 UTC. It reviewed existing documentation, including
older records and code comments/docstrings, and clarified their meaning while retaining the
original facts and decisions. Plan 0020 contains the per-file record and verification evidence.
The report-count investigation below is now complete. Outcome components and the author's
walkthrough and rehearsal remain separate work.

The original V2 results remain available. The follow-up has its own specification, configuration,
results and provenance; it does not overwrite the earlier study.

## First investigation: is the comparison model being misled by report count?

V2 uses the same regression method, Ridge, with five different sets of information. Ridge limits
how strongly it can weight its inputs. It can still learn a relationship that does not work when
the inputs change substantially.

One original input counts how many earlier reports about the program are available in the
selected dataset. More reports become available as time passes. The count can therefore increase
even when nothing about the program's care changes. It is not the age of the program.

The outside review found that most training programs had two earlier reports, while most later
evaluation programs had five. The model learned from counts of one or two and then extended that
relationship to five. Because it gave report count a positive weight, the larger count pushed its
later predictions upward. The separate follow-up now reproduces this diagnostic and all original
evaluation predictions exactly; its saved command and evidence are in the
[follow-up results](patient_journey_v2_followup_results.md).

The original results make this worth investigating:

| Approach on the same 218 programs | Average size of the error |
|---|---:|
| Ridge using history information | 11.49 percentage points |
| Ridge using history and acceptance information | 7.35 percentage points |
| Simple average of the program's earlier outcomes | 7.61 percentage points |

These are reported in the [original V2 model card](patient_journey_v2_model_card.md). A prediction
of 40% when the reported outcome is 30% has an error of ten percentage points.

Adding acceptance appears to improve on history-only Ridge by 4.14 percentage points, but it
improves on the simple historical average by only 0.26 points. The trained history-only formula
and the simple historical average are different approaches. They should never share an ambiguous
label such as just "history baseline."

The review suggested that adding acceptance also changed the weight on report count and reduced
its upward push. That does not prove acceptance lacks useful information. It gives us a concrete
reason to question how much of the apparent gain comes from the original comparison model's
weakness.

The follow-up removed report count from all five model versions and kept the other choices fixed.
History-only Ridge's average error fell to 7.32 percentage points; history plus acceptance reached
7.23. Acceptance's added improvement was therefore 0.09 points, with a descriptive interval for
its error difference of [-0.491, 0.301]. Much of the original 4.14-point gain reflected the
comparison model's response to report count. This does not prove acceptance lacks information;
the small observed gain and interval crossing zero leave its value uncertain in this single,
already-inspected period. All favorable and unfavorable comparisons remain in the results.

## Second investigation: what is included in the reported patient outcome?

The word **known** matters. The target is the percentage of listed candidates documented as alive
with a functioning transplant at 18 months. It includes living- and deceased-donor transplants.
SRTR also reports unknown post-transplant status when relevant records are unavailable; sometimes
a follow-up form is not yet due. See [SRTR's Table B7 methods](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/technical-methods-for-the-program-specific-reports/).

Consider this hypothetical group of 100 people originally listed at a program:

| Status at 18 months | People |
|---|---:|
| Known alive with a functioning deceased-donor transplant | 25 |
| Known alive with a functioning living-donor transplant | 15 |
| Received a transplant but subsequent status is unknown | 15 |
| Other statuses, such as still waiting, death, or graft failure | 45 |

The reported known-functioning percentage is 40%: 25 plus 15, divided by the original 100 people.
The 15 with unknown status are not counted as known successes. That does not establish that they
died or their grafts failed. We also cannot assume they are doing well.

An outcome recorded this way can differ because patients' actual outcomes differ, because their
follow-up reporting differs, or both. Separating living and deceased donation is also useful:
the kidney-offer acceptance measures concern deceased-donor offers, while the target includes both.

The planned work will separate compatible published outcome categories, show unknown status
explicitly, and compare reporting completeness with prediction errors for the same program and
listing group. It will preserve the published target. It will not fill in unknown outcomes as
successes or failures, or treat a relationship with missing information as proof of its cause.

### Is unknown follow-up the same as censoring?

"Unknown" is a reporting category. Censoring describes incomplete information about an event's
timing. For a hypothetical mortality study, someone confirmed alive at 12 months with no later
observation could be censored at 12 months: their record establishes survival through that point,
while survival to 18 months remains unknown.

Standard methods for right-censored survival data do not require knowing each person's reason
for censoring. They generally assume that, among otherwise comparable people still event-free
at a given time, those censored then have the same subsequent event risk as those still observed.
This is called independent censoring. An "unknown" category alone does not establish whether
that assumption is reasonable. See [Jackson et al. on independent censoring and sensitivity analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC4282781/).

For this study, [SRTR's Table B7](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/technical-methods-for-the-program-specific-reports/)
provides aggregate candidate status at 6, 12, and 18 months after listing. It does not provide
individual event or last-observed dates, or event and censoring counts over time sufficient to
reconstruct a survival analysis. These snapshots therefore do not supply the observation
histories needed to apply standard censoring-adjusted survival methods directly. This is a
limitation of the published data; it does not demonstrate that independent censoring is false.
The study predicts the published percentage known alive with a functioning transplant at
18 months, without estimating unreported outcomes.

### Whose percentage is the unknown percentage?

For one program, add the percentages with unknown status after living- and deceased-donor
transplants. Both use the original listing group as the denominator. An unknown percentage of 15%
means 15 of every 100 originally listed people, not 15% of transplant recipients.

To find a median across programs, order their percentages from smallest to largest and take the
middle value. Each program contributes one value regardless of size. That is different from
pooling people across programs; people may also be listed at more than one program.

The review's initial check of unknown status did not match those figures to each program's model
errors. It showed that unknown status warrants investigation, not that it explained the errors.
Its preliminary numerical results and reproduction requirements are retained in Plan 0020.

## Terms used in the technical record

| Technical wording | Ordinary-language explanation |
|---|---|
| Feature or predictor | An input supplied to the prediction model |
| Target or outcome | The quantity the model is trying to predict; name the exact published measure |
| Cohort | The group of candidates defined by a particular listing period |
| Ridge feature group | One version of Ridge given a particular set of inputs |
| Pinned archive | The exact saved report versions selected for the project |
| Archive depth or accumulated archive history | How many earlier reports are available in that selected collection |
| Persistence | Use the program's most recent published value again |
| Historical mean | Average the program's earlier published values |
| Ablation comparison | Compare model versions that include or omit a particular set of inputs |
| MAE | Average size of the prediction errors, ignoring whether each is high or low |
| Mean signed error | Average prediction minus observed value; positive means too high on average |
| Decompose a fixed model | Inspect how each input contributes to the already-trained calculation |
| Publication vintage | What information had actually been made public by the prediction date |
| Temporal fold | One evaluation period, using only earlier information allowed for training |
| Program-clustered paired bootstrap | Repeatedly resample programs and compare their two sets of errors together |
| Unpaired descriptive audit | An initial summary that has not yet matched the same programs and periods for the intended comparison |
| Promotion | Allow a model's predictions to be displayed in the product after its defined requirements pass |

For model decomposition, contributions add before the final conversion to a percentage. They do
not directly add in percentage points, and they are not effects of changing care. For bootstrap
intervals, explain that resampling programs does not create evidence about a new time period.

## How to document and explain future work

Use this order for an explanation, analytical function, chart, or important error message:

1. State the real-world question or purpose.
2. Say what one record represents, who is counted, and which dates apply.
3. Explain the calculation and units, with a small example when it clarifies the meaning.
4. State how unknown values are handled and why any important restriction exists.
5. Give the precise field name, equation, or statistical term needed to verify the work.

For example, describe `historical_target_count` as "the number of earlier published outcomes
available in our selected reports; this can grow without a change in the program." Describe a
future-information rejection as "this outcome was not public on the prediction date, so the
model could not have learned from it then."

Keep mathematical definitions, types, exact identifiers, and source references. Do not rename
established code or source fields just to avoid a technical word. Explain their meaning nearby.
Comments should explain intent and reasons rather than repeat every line of code.

For the interview, distinguish original results, later diagnoses, planned changes, and unresolved
questions. The author should be able to explain the question, comparison, result, and limitation
without relying on this glossary. That understanding must be checked in a walkthrough and timed
rehearsal; creating this guide alone does not establish interview readiness.
