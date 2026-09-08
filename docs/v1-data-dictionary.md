# V1 data dictionary: from one source row to a prediction

**Start here:** one row in SRTR's acceptance worksheet describes **one kidney transplant
program's included offers during a specified calendar-year cohort**. Overall counts and
several offer groups occupy different columns of that same row. The row summarizes many
offers; it does not describe one patient or one organ.

SRTR is the **Scientific Registry of Transplant Recipients**. Its **Program-Specific
Reports (PSRs)** publish these program summaries.

This dictionary accompanies slides 2–8 and 21–22 of the
[current walkthrough](presentation/data-walkthrough/data-walkthrough-with-introduction.pptx).
Read sections 1–3 first. Sections 4–7 are a field reference for following the data into a model.
The deck's opening Table B7 candidate-outcome example belongs to V2 and is outside this dictionary.

**Scope:** the released V1 acceptance monitor, checked September 8, 2026, with a separately
labeled explanation of Plan 0027's fitted adjustment. Source offer cohorts cover 2017–2025;
the latest source publication is July 7, 2026. This is a companion to the
[V1 specification](../SPEC.md) and [source manifest](../configs/data_sources.yaml), not a new
study or schema. Public aggregate screening signals support quality-improvement review;
they do not establish clinical quality or provide clinical or regulatory advice.

## 1. What does one record represent?

“Record” means a row. Its meaning changes as the project organizes the source information.
A **key** is the set of values that identifies one row uniquely within its table.

| Where you are looking | One record represents | What identifies it? |
|---|---|---|
| One SRTR kidney acceptance worksheet | One program's annual offer summary, with overall and subgroup measures across columns | `CTR_CD` and `CTR_TY` within that release |
| `program_signals.parquet` | One program, one calendar year, **one offer group** | `program_key`, `cohort_year`, `offer_group` |
| `model_panel.parquet` | One program's earlier inputs paired with its **next calendar year's outcome**, when reported | `program_key`, `feature_cohort_year` |
| A saved evaluation prediction | A model's prediction for one program and target year, together with its observed error | Program, target year and model; arrangement depends on the prediction file |

For example, one ALUA source row becomes five historical signal rows: overall, low KDRI,
medium KDRI, high KDRI and hard-to-place. Those groups supply selected columns of **one**
model-panel row. Five signal rows do not mean five independent programs or five annual outcomes.
The model panel contains inputs and outcomes; predictions are produced separately.

The released files contain 10,515 signal rows and 2,103 model-panel rows. The factor of five
comes from the five offer groups. These are repeated program observations across years.

## 2. Read an actual source record

Follow **University of Alabama Hospital**, program `ALUA:TX1`, in the overall acceptance
group. These values come from the verified released historical table; the column names
below identify the corresponding fields in SRTR's worksheet.

| Question | Source field | Calendar-2024 record |
|---|---|---:|
| Which program code? | `CTR_CD` | `ALUA` |
| Which program type? | `CTR_TY` | `TX1` |
| When does the offer cohort begin? | `OAR_cohort_start` | January 1, 2024 |
| When does it end? | `OAR_cohort_end` | December 31, 2024 |
| How many included offers? | `OA_OVERALL_OFFERS_CENTER` | 24,076 |
| How many acceptances resulting in transplants? | `OA_OVERALL_ACCEPTS_CENTER` | 185 |
| How many acceptances did SRTR's model expect? | `OA_OVERALL_EXP_ACCEPTS_CENTER` | 217.53 |
| What ratio did SRTR publish? | `OA_OVERALL_HR_MN_CENTER` | 0.85 |
| What is the lower published 95% credible bound? | `OA_OVERALL_HR_LB_CENTER` | 0.73 |
| What is the upper published 95% credible bound? | `OA_OVERALL_HR_UB_CENTER` | 0.98 |

**Publication:** July 8, 2025, release `2505`, sheet `Table B11 & Figures B10-B14`.
The cohort dates above are normalized calendar dates. Publication comes from the source
manifest, not from the cohort cells or from decoding the release code.

Say it aloud: “This row summarizes ALUA's included kidney offers in the 2024 cohort.
SRTR published it in July 2025. There were 185 acceptances compared with an expected
217.53, and the published offer-acceptance ratio was 0.85.”

OAR means **offer-acceptance ratio**. It compares completed-transplant acceptances with a
risk-adjusted expected count. Expected acceptances can be fractional because SRTR sums
offer-level predicted probabilities. This project's models read that published expectation;
they do not reproduce SRTR's underlying offer-level model.

SRTR's formula explanation is `(acceptances + 2) / (expected acceptances + 2)`. For this
record, `(185 + 2) / (217.53 + 2)` is about 0.852. We retain SRTR's published **0.85**.
The calculation is a rounding check, not a replacement source value. Offers are not the
denominator of OAR, so **0.85 does not mean 85% of offers were accepted**.
[Source: SRTR offer-acceptance FAQ](https://srtr.hrsa.gov/getting-started/faqs/for-transplant-center-professionals/).

“Included offers” means the offers that meet SRTR's reporting rules. It is not every offer
message, every donated kidney, or every transplant performed at the program. SRTR assigns
the offer cohort using donor recovery dates. See the
[technical methods](https://srtr.hrsa.gov/transplant-professionals/program-specific-report/technical-methods-for-the-program-specific-reports/)
for inclusions and exclusions.

The next record for the same program has a different measurement period:

| Offer cohort | Publication | Offers | Acceptances | Expected acceptances | Published OAR | Published 95% credible interval |
|---|---|---:|---:|---:|---:|---|
| January–December 2024 | July 8, 2025 | 24,076 | 185 | 217.53 | 0.85 | 0.73–0.98 |
| January–December 2025 | July 7, 2026 | 13,273 | 170 | 152.85 | 1.11 | 0.95–1.28 |

These are published records, not evidence that a particular operational change caused the
difference. SRTR changed included-offer rules in July 2025 and January 2026; these boundaries
affect the two releases above. Their effect on the project’s values has not been quantified.
The [source-definition audit](audits/source-definition-0029.md) records what is established
and what remains uncertain.

## 3. The same program becomes an input–outcome pair

The **feature year** supplies inputs. The **target year** is the next year whose published
overall OAR we want to predict. “Current” in an input name means current at that record's
prediction date, not the year in which you happen to read this document.

| Model-panel field | ALUA's observed pair | ALUA's latest pair in this release |
|---|---|---|
| `program_key` | `ALUA:TX1` | `ALUA:TX1` |
| `feature_cohort_year` | 2024 | 2025 |
| `target_cohort_year` | 2025 | 2026 |
| `prediction_as_of` | July 8, 2025 | July 7, 2026 |
| Input overall OAR, before taking its log | 0.85 | 1.11 |
| `current_log_overall_oar` | −0.162519 | 0.104360 |
| `target_oar` | 1.11 | Not reported |
| `truth_published_value` | July 7, 2026 | Not reported |
| `analytic_eligible` | true | false |
| `public_forecast_eligible` | true | true |

Natural logarithms, written `ln` here and `log` in field names, change the modeling scale.
For example, `ln(0.85) = −0.162519`. A log value of zero represents OAR 1, and a negative log
value represents an OAR below 1. These transformed values are calculated inputs, not new
SRTR measurements. Displayed calculations here are rounded; models use unrounded values.

On July 8, 2025, persistence would carry the published **0.85** forward as the projection for
calendar 2025. The later published **1.11** lets us assess that prediction. Its signed error
is `0.85 − 1.11 = −0.26` ratio units; its absolute error is **0.26**. The absolute log error
is `abs(ln(0.85) − ln(1.11))`, about **0.266879**. These are two scales for the same miss.
This is an illustration using already-inspected outcomes, not a new evaluation.

For the latest pair, the app's persistence point is **1.11** for calendar 2026. Its outcome
is absent from this release, so an observed error cannot yet be calculated. The stored flags
can therefore legitimately say “eligible to display a projection” and “not eligible to score.”
About half the target year had already elapsed at publication, which is why this is a
**delayed-report nowcast**, also labeled a **next-calendar-year PSR projection**.

## 4. Historical signal dictionary

This section covers all 22 columns in
[`program_signals.parquet`](../artifacts/release/processed/program_signals.parquet).
**Text** preserves codes and leading zeros; **integer** means a whole number;
**number** allows decimals; **date** is a calendar date; **category** is one of a fixed set
of labels. **Null** means unavailable, represented in the interface as “Not reported” or
“Insufficient history,” according to context.

### Program identity and display labels

| Field | Type | Meaning and source | Model role |
|---|---|---|---|
| `program_key` | Text | Project's combined `CTR_CD:CTR_TY`, such as `ALUA:TX1` | Joins records; never a predictor |
| `center_code` | Text | SRTR `CTR_CD`, such as `ALUA` | Identity only |
| `center_type` | Text | SRTR `CTR_TY`, such as `TX1`; distinguishes program types that can share a center code, including Veterans Administration programs | Identity only |
| `center_name` | Text | Readable program name, from `ENTIRE_NAME` | Display only |
| `city` | Text or null | Directory `PRIMARY_CITY` | Display only |
| `state` | Text or null | Directory `PRIMARY_STATE` | Display only |
| `zip` | Text or null | Directory `PRIMARY_ZIP`; leading zeros matter | Display only |

Name and location use the **latest pinned workbook's `Tiers` directory**, matched by code
and type. Thus an old signal row may carry a current display label; it is not a historical
address record. Without a directory match, the source name is retained, or a `Program {code}`
fallback is used; unavailable locations stay null. Join on identity, not names or row positions.

### Dates and source identity

| Field | Type | Meaning and source |
|---|---|---|
| `release_code` | Text | Manifest's source identifier, such as `2505`; use its recorded publication date rather than interpreting the digits |
| `published_value` | Text | Recorded source publication value: `YYYY-MM-DD` or `YYYY-MM` |
| `published_precision` | Category | `day` or `month`; says how precisely publication is known |
| `cohort_year` | Integer | Calendar year covered by the offer cohort |
| `cohort_start` | Date | Validated `OAR_cohort_start`, normalized to January 1 of that year |
| `cohort_end` | Date | Validated `OAR_cohort_end`, normalized to December 31 of that year |
| `source_url` | Text | Manifest URL of the downloaded workbook or archive |
| `source_sha256` | Text | File fingerprint of that **download**; for an archived release, this is the ZIP hash |

The manifest separately records an archived XLS member's hash. Do not confuse it with
`source_sha256`. Raw cohort-cell representations are retained in QA, rather than added to
these 22 columns. Month-only publication values remain month/year; they do not become an
invented first-of-month date. Earlier releases use sheet `Table B10 & Figures B7-B11`;
newer releases use `Table B11 & Figures B10-B14`. Machine field names identify the measures.

### Offer groups and published measures

`offer_group` is a category derived from the source column prefix. KDRI means **Kidney
Donor Risk Index**, SRTR's donor grouping measure here. Group membership follows the source
report; the project does not reconstruct it from individual donor characteristics.

| `offer_group` | Source prefix | Read it as |
|---|---|---|
| `overall` | `OA_OVERALL` | All included offers |
| `low` | `OA_LOWRISK` | Included offers in the source's low-KDRI group |
| `medium` | `OA_MEDIUMRISK` | Included offers in the source's medium-KDRI group |
| `high` | `OA_HIGHRISK` | Included offers in the source's high-KDRI group |
| `hard-to-place` | `OA_HARDTOPLACE100` | Kidney offers with more than 100 previous offers, under SRTR's definition |

Append the suffix below to the appropriate prefix. For example,
`OA_HIGHRISK_HR_MN_CENTER` becomes `oar_mean` in the `high` signal row.

| Processed field | Source suffix | Type / units | Meaning |
|---|---|---|---|
| `offers` | `_OFFERS_CENTER` | Integer count or null | Number of included offers for this program, cohort and group |
| `acceptances` | `_ACCEPTS_CENTER` | Integer count or null | Number counted as accepted because they resulted in completed transplants |
| `expected_acceptances` | `_EXP_ACCEPTS_CENTER` | Number, expected-count units, or null | Published sum of SRTR's predicted acceptance probabilities |
| `oar_mean` | `_HR_MN_CENTER` | Number, unitless ratio, or null | SRTR's published OAR point estimate; not an average across years |
| `oar_lower` | `_HR_LB_CENTER` | Number, ratio units, or null | Published lower 95% credible bound |
| `oar_upper` | `_HR_UB_CENTER` | Number, ratio units, or null | Published upper 95% credible bound |

The source retains `HR` in these machine names; the measure described here is OAR.
The published 95% credible interval describes uncertainty about the source ratio. It is
different from an empirical band around a prediction of a later report.

Hard-to-place overlaps KDRI groups. Do not add all five groups together, or assume that
low, medium and high counts always sum exactly to overall counts. Recent source workbooks
also contain `OA_KDPI_GTE_60_*` fields; KDPI means Kidney Donor Profile Index. The released V1 parser and signal table contain
**only the five groups above**; KDPI ≥60 is not one of the original model inputs.

### What a missing or zero value means

All six overall measures must be present for the source row to pass the parser. The table
allows null measurements for subgroup records; missing ratio and interval values remain
unknown. A group's ratio and its two bounds must be either all reported or all missing.
Recognized source blanks and missing markers, including `-`, `--`, `.`, `NA`,
`N/A` and `NULL`, become null rather than zero.

Zero subgroup offers is a distinct case: acceptances and expected acceptances must also
be zero, and the ratio and its interval remain null. We do not invent an OAR of 1 from the
formula when no subgroup offers were observed. A missing later program report similarly
produces a missing target, never a zero acceptance outcome.

## 5. Model-panel dictionary: dates, outcomes and flags

[`model_panel.parquet`](../artifacts/release/processed/model_panel.parquet) has **31 columns**:
the 14 context/outcome fields below and the 17 inputs in section 6. A Boolean is `true` or
`false`. None of the fields in this section is supplied as a predictor to Ridge.

| Field | Type | Meaning |
|---|---|---|
| `program_key` | Text | Same composite identity as the signal table |
| `feature_cohort_year` | Integer | Offer cohort of the input report, denoted `t` below |
| `target_cohort_year` | Integer | Outcome offer cohort, exactly `t + 1` |
| `prediction_as_of` | Text | Publication value of the feature report; the origin for this projection |
| `prediction_as_of_precision` | Category | `day` or `month` for that origin |
| `target_cohort_end` | Date | December 31 of the target year |
| `truth_published_value` | Text or null | Target release's publication date, if available; this can exist even when the particular program has no later row |
| `truth_published_precision` | Category or null | `day` or `month` for that target release |
| `elapsed_target_cohort_fraction_at_prediction` | Number, fraction 0–1 | How much of the target year had elapsed by publication; 0.5 means half a year |
| `target_oar` | Number, ratio units, or null | This program's later published overall OAR; absent if its outcome is unavailable |
| `target_log_oar` | Number, log units, or null | `ln(target_oar)`; the outcome used for model fitting and primary error calculation |
| `analytic_eligible` | Boolean | Whether this row has an observed target that permits scoring; the builder has already validated current overall inputs |
| `public_forecast_eligible` | Boolean | Stored program-level display eligibility: current ratio available and at least two annual observations through the feature year |
| `first_observed_program` | Boolean | This is the program's first annual appearance in this dataset; it does not establish its opening date |

For a day-precision origin, elapsed fraction counts days through and including the origin
date, divided by days in the year. For month precision, the builder uses completed months
before the reported month divided by 12, without assigning a day.

Public eligibility counts available annual observations, which need not be consecutive.
A row can therefore have a missing previous-year input but sufficient earlier history for
display. The app reads the stored eligibility flag. Model selection and forecast-band
display are separate release decisions; this flag alone does not promote a model.

Targets are attached for fitting or later evaluation. Their presence in a retrospective
table does not make them available at the prediction origin. Training outcomes must already
be public then, and all programs with the same target year stay together in an evaluation fold.
A **fold** is one such separation of earlier training records from later evaluation records.

## 6. The original 17 model inputs

Let `t` be the feature year, `r` its published overall ratio, and `L` and `U` its published
lower and upper credible bounds. All numeric fields below are decimal numbers; the last
six are Booleans. The model uses these derived fields instead of receiving every source column.

| Input field | Calculation and ordinary-language meaning | Null handling before fitting |
|---|---|---|
| `current_log_overall_oar` | `ln(r_t)`: latest overall ratio on the log scale | Required; overall OAR must be positive |
| `previous_annual_log_overall_oar` | `ln(r_(t−1))`: ratio from exactly the previous calendar year | Null if that year's report is absent |
| `one_year_change_log_overall_oar` | `ln(r_t) − ln(r_(t−1))`: change between adjacent annual ratios on the log scale | Null if the previous annual value is absent |
| `log1p_overall_expected_acceptances` | `ln(1 + expected_acceptances)`: transformed expected volume | Required; adding 1 permits an expected count of zero |
| `log_credible_interval_width` | `ln(U) − ln(L)`, or `ln(U/L)`: width of the published interval **on the log scale** | Both bounds must be positive; this is not `ln(U−L)` |
| `current_log_low_oar` | Natural log of the current low-KDRI ratio | Null if subgroup ratio is unavailable or nonpositive |
| `current_log_medium_oar` | Natural log of the current medium-KDRI ratio | Same rule |
| `current_log_high_oar` | Natural log of the current high-KDRI ratio | Same rule |
| `current_log_hard_to_place_oar` | Natural log of the current hard-to-place ratio | Same rule |
| `high_offers_share` | High-group offers divided by overall offers | Null if subgroup offers are unavailable; overall offers must be positive |
| `hard_to_place_offers_share` | Hard-to-place offers divided by overall offers | Same rule |
| `missing_previous_annual_log_overall_oar` | `true` when the previous annual log ratio is null | Always reported |
| `missing_one_year_change_log_overall_oar` | `true` when the annual log change is null | Always reported |
| `missing_current_log_low_oar` | `true` when the low-group log ratio is null | Always reported |
| `missing_current_log_medium_oar` | `true` when the medium-group log ratio is null | Always reported |
| `missing_current_log_high_oar` | `true` when the high-group log ratio is null | Always reported |
| `missing_current_log_hard_to_place_oar` | `true` when the hard-to-place log ratio is null | Always reported |

The offer shares are fractions: **0.20 means 20% of the included overall offers**. They
describe the composition of offers, not an acceptance percentage. The two shares can overlap.
An older report cannot substitute for a missing `t−1` report in the previous-year/change fields.

There are **11 numeric inputs and six missing-value indicators**. During fitting, Ridge
fills missing numeric inputs with that training fold's median, then scales inputs using
training means and standard deviations. An entirely empty training column is retained with
a numerical zero fallback inside the calculation. Boolean inputs become 0/1 and are also
scaled. None of this converts a missing published measurement into an observed zero.

The project excludes program identity, name, location, calendar-year labels, future report
availability and target values from the predictor list. In particular, `target_log_oar`
teaches the model only for permitted **training** records; it is not an input for the row
being predicted. The exact list is fixed in [the experiment](../configs/experiment.yaml)
and enforced by [the feature contract](../src/kasm/modeling/features.py).

## 7. Predictions are calculated outputs

| Method | What it does with the earlier records |
|---|---|
| Neutral | Predicts log OAR 0, which becomes ratio 1 |
| Persistence | Reuses the current published ratio |
| Historical mean | Averages the program's available annual **log OARs**, including the feature year, then exponentiates; this gives their geometric mean on the ratio scale |
| Original full Ridge | Fits weights and an intercept using the 17 inputs above, with a penalty limiting coefficient size |
| Plan 0027 fitted adjustment (`adjusted_persistence`) | Separately fits a slope and intercept using **only `current_log_overall_oar`**, with training-only scaling and Ridge alpha 10 |

Plan 0027 selected the fitted adjustment as a provisional research candidate for a future
point projection; deployment remains separate. The current app retains persistence and
withholds forecast bands. The original exact-bias selection rule was a design mistake
and is retired; its saved result remains historical evidence. The original frozen 2025 fit
ends with training target year 2023. Plan 0027's distinct 2025 fit used target 2024, which
was then public. See the [current results](acceptance_forecast_results.md) for that distinction.

The fields below are a selected guide to saved predictions, not additional model inputs:

| Output field | Meaning / units |
|---|---|
| `model` | Method label, such as `persistence` or `ridge`, in files storing one method per row |
| `fold_id` | Evaluation-period label, such as `target_2024` |
| `predicted_log_oar` | Model's point prediction on the natural-log scale |
| `predicted_oar` | `exp(predicted_log_oar)`, returning a positive ratio-scale point |
| `signed_error_log_oar` | Predicted log OAR minus later published log OAR; positive means too high |
| `absolute_error_log_oar` | Absolute size of that log-scale difference |
| `absolute_error_oar` | Absolute size of predicted OAR minus published OAR, in ratio units |
| `absolute_error_difference_vs_persistence` | Candidate absolute log error minus persistence absolute log error; negative favors the candidate |
| `expected_acceptance_quartile` | Earlier expected-volume group within the evaluation year, numbered 1–4; a diagnostic grouping, not another predictor |

The baseline file stores a separate row for each method. The original Ridge file stores
Ridge rows. The frozen replay stores Ridge and persistence side by side, with prefixes
such as `ridge_predicted_oar` and `persistence_predicted_oar`. Its `*_band_lower_oar` and
`*_band_upper_oar` columns describe empirical prediction bands; `*_band_covered` records
whether the later ratio fell within them. These are distinct from the source's
`oar_lower` and `oar_upper` credible bounds.

`exp(x)` means raising the number `e` to the power `x`; it reverses the natural logarithm.
Exponentiating a log prediction returns a point on the ratio scale; it does not generally
give the arithmetic expected OAR. **Mean absolute error (MAE)** averages individual absolute
errors. V1's primary summary first averages within each target year and then averages the
yearly values equally. One program's error, such as ALUA's example, is not that overall score.

## 8. How to check this dictionary

The source-to-field mappings follow [the parser](../src/kasm/data/parse.py) and
[the table builder and schemas](../src/kasm/data/build.py). Baseline calculations follow
[the temporal backtest](../src/kasm/modeling/backtest.py); the current app point follows
[the historical service](../src/kasm/reporting/history.py). Plan 0027 follows its
[separate specification](specs/acceptance-forecast-0027.md) and
[comparison settings](../configs/acceptance_forecast/comparison.json).

Example values were read after validating the existing
[release manifest](../artifacts/release/release_manifest.json) and all 12 payloads. The bundle
content identity is `1de89083ceebfda9afaf2d6b1c6ba3f1e6d0c1a1da16df9d09d994c4ec3581ad`.
The manifest contains the source/configuration hashes, code and dependency identities,
build time and cohort context. This dictionary does not rebuild or replace that evidence.
The checks and a read-only example command are recorded in
[Plan 0030](plans/0030-v1-data-dictionary.md).

For a first personal walkthrough, point to the ALUA row and explain its identity, the
offers counted, its cohort and publication dates, the expected-count denominator, and why
the next year's ratio belongs in a separate outcome column. Then follow the persistence
calculation in section 3 using those values.
