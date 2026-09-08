# Understanding the project

This guide explains the completed studies and the current forecast-improvement plan.
Precise equations, field names and methods remain in the linked specifications and code.

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
| V1 forecast improvement | Complete; fitted latest-ratio adjustment selected for a future point release, band withheld | [Plan 0027](plans/0027-v1-forecast-improvement.md), [results](acceptance_forecast_results.md) |
| Original V2 patient-journey study | Completed exploratory study; no model promoted and no future forecast displayed | [V2 model card](patient_journey_v2_model_card.md) |
| V2 follow-up | Report-count comparison and matched outcome-component analysis complete | [Report-count results](patient_journey_v2_followup_results.md), [component results](patient_journey_v2_component_results.md) |
| Deceased-donor receipt study | Complete; acceptance added too little improvement to continue under the fixed rule | [Receipt results](deceased_donor_receipt_results.md) |
| Waiting-list viability screen | Complete; growing lists commonly coexist with more transplant removals, passing the fixed descriptive rules | [Waiting-list recommendation](waiting_list_viability_results.md) |
| Waiting-list case study | Complete; signed change distributions, three fixed program examples and reusable offline briefs | [Case study](waiting_list_case_study.md), [reproduction](waiting_list_case_study_reproduction.md) |

The original V2 results remain available. The follow-up has its own specification, configuration,
results and provenance; it does not overwrite the earlier study.

The separate waiting-list screen found increased transplant removals in 52.8%, 47.4% and
42.3% of eligible programs with growing lists in 2023–2025. Analysts should examine registration
demand and other removal categories alongside transplant activity before interpreting growth.
The finding survives the fixed size and common-program checks; it supports a further descriptive
direction, with no model or application change. These counts describe events at programs, not
unique people nationally or clinical causes. The linked recommendation reports exclusions and limits.

The completed [case study](waiting_list_case_study.md) adds the size of those changes. Across all
growing-list programs, median transplant-removal changes were +2, 0 and −2 events; among those with
increases, medians were +15, +12 and +8. Some increases were one event. A worked example shows a
list growing by 56 registrations while transplant removals increased by 24, yet annual growth
slowed from 108 the year before. Its two annual equations and the separate change-in-growth
equation reconcile exactly. Three examples follow a fixed middle-record rule, and the same offline
HTML template can describe another eligible program. This remains descriptive work, with no model
promotion, quality ranking, causal claim or application integration.

The [source audit](audits/source-feasibility-0022.md) found that the July 2026 report uses
July 2023–June 2024 listings. The original ledger incorrectly recorded calendar 2023 and
excluded that report for overlap. The separately specified
[Plan 0023 study](deceased_donor_receipt_results.md) now uses that corrected period alongside
July 2022–June 2023 listings to study recorded deceased-donor transplant receipt within 18 months.
The original one-period results remain unchanged. [Plan 0024](plans/0024-candidate-mix-study.md)
still proposes earlier candidate characteristics; it requires its own verified dates and fixed
comparisons before fitting.

For the new receipt question, adding acceptance information to receipt history and access
information reduced the average size of errors from 8.888 to 8.774 percentage points, a
0.113-point (1.27%) gain. That missed the required 0.5 points and 5%, and error improved in
only one of the two periods. Development of this acceptance extension therefore stops under
its fixed rule. Both periods use the same earlier training cohort; two periods do not make
this fresh validation. The target adds five published deceased-donor statuses among everyone
originally listed, including recipients with unknown later health status. It measures recorded
receipt, not survival, graft function or a patient's chance of receiving a transplant.

## Improving V1 forecasts

The original Ridge model predicted the next published annual acceptance ratio with 10.13% lower
average absolute log error than persistence in the 2025 replay. It was not promoted because its
absolute average signed log error was 0.01145 versus persistence's 0.00885. That exact comparison
was the only failed point-promotion criterion. The original configuration, results and product
decision remain preserved; the current application still displays persistence.

[Plan 0027](plans/0027-v1-forecast-improvement.md) is complete. The saved Ridge forecasts typically
missed by about 19%–32% of the published ratio across years, and their largest tenth of errors
were much larger. The fixed follow-up compared persistence, historical mean, full Ridge, Ridge
with three recent training years, and a simple fitted adjustment of the latest ratio.

The fitted adjustment had 6.90% lower average absolute log error than persistence and met the
[revised policy](specs/acceptance-forecast-0027.md). It is recommended for a future point release,
with its band withheld because coverage varied across years and groups. Its advantage over full
Ridge was small (0.66%), and it worsened individual errors about 40% of the time. The
[complete results](acceptance_forecast_results.md) explain the units, comparisons and limits.

This remains exploratory retrospective evidence. The current app retains persistence until
the separate [Plan 0028 handoff](plans/0028-v1-point-projection-release.md) is implemented. The
original V1 decision and original V2 prohibition on promotion remain intact.

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

The original results motivated the investigation:

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

The [completed numerical description](patient_journey_v2_component_results.md) matches all 218
original evaluation programs in the July 2025 report. Their median combined post-transplant
unknown percentage is 16.05% of the original listing group. The earlier 16.27% review figure
describes a broader set of 222 source programs with at least ten listed candidates. These are
program medians, not pooled patient percentages. The four donor components are shown separately
because they omit other statuses and their medians cannot be added.

All original models' signed and absolute errors are compared with unknown status on those same
218 programs. The published target remains unchanged. These associations cannot show that
reporting caused an error: functioning and unknown percentages share a denominator and mutually
exclusive statuses, and signed error contains the observed outcome in its calculation. Unknown
patient outcomes remain unknown.

### Is unknown follow-up the same as censoring?

"Unknown" reports that a person's status is unavailable at a specified time. A survival
calculation uses when events happened and how long people remained under observation. The key
question is whether a summary preserves that information: aggregate data can support survival
analysis when the necessary timing and counts remain available.

Consider a hypothetical mortality study of ten patients enrolled together. The table lists
every death and end of observation at its exact time, not counts across intervals. A person
whose observation ends alive is censored then: we know they survived through that time, but
their later survival is unknown.

| Month after enrollment | Alive and observed just before | Deaths then | Observation ends alive then |
|---|---:|---:|---:|
| 3 | 10 | 2 | 0 |
| 6 | 8 | 0 | 3 |
| 12 | 5 | 1 | 0 |
| 18 | 4 | 0 | 4 (study ends) |

The Kaplan–Meier estimate of survival to 18 months is `(8/10) × (4/5) = 64%`: at month 3,
eight of ten remain alive after two deaths; at month 12, four of five remain alive after one death.
The three censored at month 6 leave subsequent observation counts without being counted as
deaths. These aggregate counts give the same unadjusted survival estimate as the individual
records. See [NIST's explanation of the calculation](https://www.itl.nist.gov/div898/handbook/apr/section2/apr215.htm).

If we kept only the final totals—four known alive, three known dead, three unknown—we would
lose the timing needed to reproduce that calculation. Similarly,
[SRTR's Table B7](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/technical-methods-for-the-program-specific-reports/)
reports candidate status at 6, 12, and 18 months after listing. It does not provide individual
event or last-observed dates, or equivalent event and observation counts over time. These
snapshots do not supply the information needed to apply standard censoring-adjusted survival
methods directly.

Interpreting the survival estimate also requires appropriate censoring assumptions. Standard
methods generally assume that, among otherwise comparable people still event-free at a given
time, those censored then have the same subsequent event risk as those still observed. This is
called independent censoring; it does not require knowing each person's reason for censoring.
An "unknown" category alone does not establish whether that assumption is reasonable. See
[Jackson et al. on independent censoring and sensitivity analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC4282781/).

Our study predicts the program's published percentage known alive with a functioning transplant
at 18 months among everyone originally listed. That outcome includes receiving a transplant,
being alive with it functioning, and having that status documented. It is not simply survival
among transplant recipients, and this analysis does not estimate unreported outcomes.

### Whose percentage is the unknown percentage?

For one program, add the percentages with unknown status after living- and deceased-donor
transplants. Both use the original listing group as the denominator. An unknown percentage of 15%
means 15 of every 100 originally listed people, not 15% of transplant recipients.

To find a median across programs, order their percentages from smallest to largest and take the
middle value. Each program contributes one value regardless of size. That is different from
pooling people across programs; people may also be listed at more than one program.

The initial review used 222 source programs without matching prediction errors. The completed
218-program analysis above makes that match; neither summary establishes why errors occurred.

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

Distinguish original results, later diagnoses and proposed studies. The
[roadmap](../PLAN.md) links their separate records and the current presentation package.
