# A growing waiting list needs a count breakdown

The waiting-list case study shows why the size of a kidney program's list cannot, by itself,
describe its transplant activity. In 2023, 2024 and 2025, **52.8%, 47.4% and 42.3%** of eligible
growing-list programs also recorded more transplant removals than in the preceding year. The
added distributions qualify that finding: increases ranged from one event to much larger changes,
and most growing programs in 2025 recorded unchanged or decreased transplant removals.

This is a descriptive portfolio case study of previously inspected public SRTR Table B1 records.
One annual record counts registrations and removal events at a composite `(CTR_CD, CTR_TY)`
kidney program. These are not unique people nationally or independently verified procedures.
“Transplant removals” combines deceased- and living-donor removals at the reporting program.
Transplant elsewhere, transfers, deaths, deterioration, recovery and other removals stay separate.

**Public aggregate prototype — not clinical or regulatory decision support.** This case study
does not establish clinical causes, program quality, novelty or demonstrated decision benefit.

## How common, and how large?

Each year compares current transplant-removal counts with the preceding calendar year. The
denominator below is all eligible programs whose list grew during the current year. Each program
has one weight within a year; repeated years are not pooled into a larger independent sample.

| Current year | Increased | Unchanged | Decreased |
|---|---:|---:|---:|
| 2023 | 56/106 (52.8%) | 6/106 (5.7%) | 44/106 (41.5%) |
| 2024 | 54/114 (47.4%) | 5/114 (4.4%) | 55/114 (48.2%) |
| 2025 | 58/137 (42.3%) | 5/137 (3.6%) | 74/137 (54.0%) |

Among **all growing-list programs**, median signed changes were **+2, 0 and −2 removal events**.
The middle half lay between −5 and +15.75 in 2023, −11 and +11.5 in 2024, and −12 and +7 in 2025.
Full ranges were −92 to +83, −92 to +59, and −93 to +181. Quartiles mark the boundaries of the
middle half; linear interpolation can put a boundary between whole event counts.

Among **only growing programs with increased transplant removals**, medians were **+15, +12
and +8 events**. Their middle-half boundaries were +6 to +35.75, +6 to +21.5, and +3 to +18.75.
The smallest increase was one event in every year. Thus “53% of growing programs” describes
frequency; “15 additional removals” describes the median size in a selected subgroup. Neither
number describes the amount by which the list grew. Plan 0025's successful magnitude rules
concerned **list growth**, not a minimum transplant-removal increase.

Relative to the current year's starting list, median signed changes among all growing programs
were +0.75, 0 and −0.91 events per 100 starting registrations. The increased-removal subgroup's
medians were +6.97, +6.25 and +3.57 per 100. These are separately computed program summaries,
not a ratio of medians. Small starting lists can produce large values: the full observed range
reaches +200 per 100 in 2025. This normalization is change relative to list size, not a patient's
transplant probability, a percentage increase over last year's transplant count, or a rate per
patient-year. The figures retain every observation and the full range on shared scales.

## Follow one program's records

The first mechanically selected example is **ARUA:TX1**, comparing calendar years 2024 and 2025.
Its starting lists were 155 and 263 registrations. Additions were 288 in both years. Total
removals increased from 180 to 232, including transplant removals increasing from 144 to 168.
Both annual equations reconcile exactly:

- **2024:** 155 starting + 288 added − 180 removed = 263 ending; annual growth **+108**.
- **2025:** 263 starting + 288 added − 232 removed = 319 ending; annual growth **+56**.

The list grew while more transplant removals were recorded. It also grew **52 registrations
less** than in the preceding year. The change in growth is a separate equation: change in additions
minus changes in all removal categories. Contributions were 0 from additions, −18 from deceased-donor
transplant removals, −6 from living-donor transplant removals, −14 from transplant elsewhere,
0 from transfers, +3 from deaths,
−9 from deterioration, −1 from recovery and −7 from other removals, summing to **−52**. The positive
death contribution reflects fewer recorded deaths, not more. Every normalized contribution uses
the same 263 current starting registrations; the total is −19.77 per 100.

These records support a review of how additions and removal categories were recorded. For this
example, total additions were unchanged; an analyst could examine listing records within that
total and the recorded circumstances of changed transplant and other removal activity. The
arithmetic does not establish why activity changed or prescribe an intervention.

The other two selected examples prevent a one-sided story. **COSL:TX1** grew by 30 registrations
in 2025 versus 13 in 2024, even as additions fell by 6 and transplant removals fell by 8. All
categories together account for the +17 change in growth. **PAAG:TX1** shrank by 8 after growing
by 15. Its transplant removals fell by 10, while deaths rose from 5 to 11 and deterioration
removals from 7 to 16. Shrinking alone therefore cannot be labeled improvement. All three briefs
show both years' published counts, every removal category and exact equations.

The rule was fixed before examining the examples: use the same 169 programs eligible in all
three years; in each 2025 group sort by starting registrations and composite key and choose
zero-based index `floor((n−1)/2)`. ARUA:TX1 is index 21 of 43 growing/increased programs;
COSL:TX1 is index 31 of 63 growing/same-or-decreased programs; PAAG:TX1 is index 28 of 58 shrinking
programs. Five common programs had zero growth and belong to none of these example groups.
These examples illustrate accounting, not a representative sample or a quality comparison.

## Coverage, dates and practical limits

Eligible comparisons have complete counts, exact annual accounting, a preceding ending count
equal to the current starting count, and a positive current starting list. Coverage was
198/236 matched programs in 2023 (83.9%), 199/235 in 2024 (84.7%), and 206/233 in 2025 (88.4%).
Excluded records cannot be treated as zero activity. Across the original 2017–2025 record set,
241 consecutive pairs had discontinuous boundaries and 11 had zero current starts. All 2,144
annual records reconciled. Later report revisions never replace the earliest verified vintage.

The retained Plan 0025 checks found increased-removal shares of 50.0%, 46.5% and 40.6% among
growing lists in the common 169-program sample. Across starting-list groups below 100, 100–499
and at least 500, the program-weighted shares were 43.7%, 38.9% and 59.8%. All original fixed
rules passed. These are carried-forward findings, not a rerun or a new continuation test;
the size-group percentages average each program's share over its growing years and are not
simple pooled observation ratios. See [the original evidence](waiting_list_viability_evidence.md).

The retained calendar 2022, 2023, 2024 and 2025 counts were published July 6, 2023; July 9, 2024;
July 8, 2025; and July 7, 2026, respectively. Each cohort runs January 1–December 31. Source URLs,
publication precision and fingerprints are preserved in every generated brief and its provenance.
This is delayed public reporting of events, not patient-level analysis or fresh validation.

Use the [offline reproduction instructions](waiting_list_case_study_reproduction.md) to generate
the short analytical HTML brief, three figures, complete supporting tables and the three
program briefs, or a brief for another eligible program in 2023–2025. The
[five-minute outline](waiting_list_case_study_outline.md) explains the case study. The
[execution plan](plans/0026-waiting-list-case-study.md#execution-evidence) records verification.
No application integration or model promotion belongs to this completed descriptive work.
