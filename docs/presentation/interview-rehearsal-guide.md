# Interview rehearsal guide

Use the companion eight-slide deck for a 3:55–4:00 presentation. The live application is the
preferred product demonstration; the screenshots under `docs/demo/` are the independent backup.
Keep the language descriptive, program-level, nonclinical, and nonregulatory throughout.

**Retained V1 presentation, explained 2026-09-05:** The eight-slide deck and its screenshots remain
the original four-minute release package. These notes explain that existing story; they are not
the new 20-minute V2 follow-up presentation. The latter belongs to
[Plan 0020 P4](../plans/0020-v2-follow-up-and-interview-story.md#p4-build-the-explanation-and-interview-package)
after the separate investigations. Reading these notes does not establish that the author has
completed a spoken walkthrough or timed rehearsal.

The V1 story is: show a program its earlier published acceptance signal, test whether a fitted
model predicts the next published signal better, and follow the prewritten display rules when
the answer differs across error measures. One observation is a kidney program and calendar year.
The offer-acceptance ratio (OAR) compares completed-transplant acceptances with SRTR's expected
number for similar offers; 1 is in line with expectation. It is a ratio, not a percentage of
patients transplanted. PSR means Program-Specific Report, and SRTR is the Scientific Registry of
Transplant Recipients. Missing source values remain unknown.

For the method slides: a baseline is a simple comparison prediction; persistence carries the
latest value forward. Ridge fits input weights while limiting their size. Mean absolute error
(MAE) is the average size of prediction error, ignoring direction; here its primary units are
log OAR. Mean signed error keeps direction, with negative values indicating predictions that are
too low. A fold is a whole-year training/evaluation split. The paired bootstrap resamples programs
and compares both models on the same draw; it does not create another independent year.

**Timing and decision clarification, 2026-09-05:** The deck's later "2026 PSR" assessment means
the report about calendar year 2026, expected around mid-2027 under
[the V1 reporting-lag specification](../../SPEC.md#reporting-lag). The July 2026 release describes
calendar year 2025. Also, retaining persistence means the specified display rule was followed;
it does not establish that persistence is clinically safer. Ridge had lower average error but
missed the relative-bias rule. The prepared positive/negative narratives must preserve both facts.

## Four-minute talk track

| Slide | Time | Spoken point |
|---|---:|---|
| 1. Kidney Acceptance Signal Monitor | 0:10 | “I built an offline screening signal from public SRTR aggregates to help a kidney transplant program review its own offer-acceptance history. It is not clinical or regulatory decision support.” |
| 2. A program needs context—not a scorecard | 0:25 | “A published offer-acceptance ratio compares observed with expected acceptances; 1.0 is the benchmark. The monitor adds earlier years and donor groups so a program can review the pattern over time.” |
| 3. Nine pinned releases become one defensible annual panel | 0:30 | “The data checks exact file fingerprints for nine releases and reads named source fields. A program is identified by its code and type together. That produces 10,515 signals across 2,103 program-years. The 1.23 MB bundle runs the demo offline.” |
| 4. Time stays in order from features to truth | 0:35 | “Earlier reports predict the next calendar year's published log OAR. Entire years stay together. Missing-input replacement, scaling, and fitting learn only from training data. The frozen replay fit stops at target year 2023; 2024 is reserved for setting the separate forecast-band width.” |
| 5. The product is longitudinal context—not a leaderboard | 0:35 | “The monitor shows one program’s annual OAR, SRTR 95% credible intervals, publication date, volume, and donor groups. Missing values are labeled. Every view identifies the relevant dates, source history, and nonclinical limits.” |
| 6. Ridge lowered error—but still missed the gate | 0:50 | “In the fixed 2025 replay, ridge lowered average absolute log-OAR error from 0.267 to 0.240, a 10.1% improvement. Resampling programs gave an error-difference interval of minus 0.041 to minus 0.013. But its absolute average signed error was 0.011 versus 0.009 for persistence. All prewritten display rules had to pass, including that bias comparison. Ridge was not promoted.” |
| 7. The app makes the conservative decision visible | 0:30 | “The app therefore carries the latest published OAR forward—0.56 in this example—as the 2026 next-calendar-year PSR projection. It labels the output a delayed-report nowcast, shows that 51.5% of the target cohort had elapsed at the prediction origin, and suppresses the ridge band because the point model was not promoted.” |
| 8. The strongest product decision was refusing complexity that missed its gate | 0:20 | “The deliverable is a reproducible historical monitor plus an honest negative model-selection result. The 2025 replay is descriptive retrospective evidence, not prospective validation. A later 2026 PSR release is needed for prospective assessment.” |

Total: approximately 3:55, leaving a few seconds to transition into questions.

## Offline demo path

Before the interview, install the locked environment while networking is available:

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
uv sync --frozen
```

Then disable networking and start the tracked bundle:

```powershell
uv run streamlit run app/streamlit_app.py
```

In the app:

1. On **Program monitor**, select a program and identify the source cohort, publication date,
   overall OAR, SRTR credible interval, and annual history.
2. Scan the donor-stratum table; explain that “Not reported” remains missing and that
   hard-to-place offers may overlap KDRI strata.
3. Open **Projection**; show the persistence value, 2026 target year, prediction origin, elapsed
   target-cohort fraction, and explicit ridge-band suppression.
4. Open **Model evaluation**; show the intact annual folds and the frozen 2025 decision.

The tracked-bundle AppTest and Streamlit health smoke already verify that this path has no live
source dependency. Do not run source sync, model training, or the frozen replay during the demo.

## Backup sequence

If the live app is unavailable, show these files in order:

1. [Program monitor](../demo/program-monitor.png) — selected-program history, interval status,
   volume, and donor-stratum context.
2. [Persistence projection](../demo/persistence-projection.png) — the displayed 2026 projection
   and explicit band suppression.
3. [Model evaluation](../demo/model-evaluation.png) — rolling-year evaluation and frozen replay
   outcome.

`program-monitor-top.png` is a tighter crop suitable for the deck or a low-resolution screen.

## Result narratives

### Actual result: persistence retained

Ridge improved replay MAE, and the program-resampled paired bootstrap interval favored ridge on
that metric. It still failed the prespecified relative-bias criterion. Because every point-model
criterion had to pass, the product retains persistence and suppresses the ridge empirical band.
This is a successful governance outcome: complexity did not earn deployment.

The historical SRTR interval describes uncertainty about its published ratio. The empirical
forecast band uses earlier prediction errors to form a range for a later published ratio.
"Marginal" coverage means coverage averaged across programs; it does not promise that a given
program has an 80% chance of falling in its band. The two intervals answer different questions.

### Counterfactual result: ridge promoted

Had ridge passed every frozen point-model criterion, the app would have displayed the ridge point
projection. Its empirical band would still require a separate band gate; point promotion would
not automatically activate the band. Even then, the 2025 replay would remain descriptive
retrospective product-selection evidence, not prospective or independent validation.

## Likely questions

**Why not predict the credible-interval status?**  
It is a descriptive label derived from the published ratio and interval, not the scientific
target. The target is the continuous next-calendar-year published `log(OAR)`.

**Why annual, non-overlapping cohorts?**  
They match the modeling unit and prevent overlapping observation windows from leaking information
between folds. All rows for an outcome year remain in the same temporal fold.

**Why can the same program appear in multiple years?**  
The product is for established-program monitoring, so repeated program-years are expected.
Uncertainty comparisons resample by program, and first-observed programs are labeled and withheld
from public projection unless an artifact explicitly permits them.

**Why did ridge lose after improving MAE?**  
Every promotion rule had to pass. Ridge passed the required reduction in average error but missed
the frozen relative-bias rule, so persistence remained the specified displayed reference. That
decision does not show that persistence is clinically safer or more accurate on every metric.

**Why was 2024 excluded from replay fitting?**  
The frozen design assigns different roles to those years: fit only through target year 2023,
then use held-out 2024 errors to set the band width. Excluding 2024 from fitting preserves that
separation. It is not a claim that 2024 outcomes were unavailable at the 2025 prediction origin.

**What does the forecast band mean?**  
It is an empirical marginal band across programs, not a center-specific probability statement and
not the SRTR 95% credible interval. Those two uncertainty quantities never share a label.

**How do you handle policy or data-definition drift?**  
Every release has a methodology-ledger entry and a pinned source hash. Unreconciled definition
changes restrict the modeling era rather than being silently pooled.

**Why exclude center identity and geography?**  
Center code, name, type, location, OPO/DSA identity, and future report availability are prohibited
predictors. Program identity is retained only for joining, display, eligibility, and clustered
uncertainty—not for model fit.

**Is this evidence of clinical benefit or an unsafe program?**  
No. It is a public-aggregate screening signal for quality-improvement review. It does not support
patient- or organ-level decisions, causal conclusions, regulatory claims, or national rankings.

**What would you do next?**  
Preserve the frozen result, wait for the later 2026 PSR publication, and assess the already chosen
display prospectively. Do not retune against the 2025 replay.

## Rehearsal checklist

- [ ] Run the deck once in the actual presentation environment and confirm embedded screenshots,
  fonts, and speaker notes.
- [ ] Start the application with networking disabled and follow the four-click demo path above.
- [ ] Keep the live demo under two minutes so the scientific result remains the center of the
  conversation.
- [ ] Practice the actual negative narrative and the ridge-promotion counterfactual.
- [ ] Say “published offer-acceptance ratio,” “next-calendar-year PSR projection,” and
  “delayed-report nowcast”; avoid real-time, clinical, causal, ranking, and regulatory language.
- [ ] Keep the three wide screenshots open locally as the first fallback.
- [ ] End on the prospective limitation and the decision not to promote ridge.
