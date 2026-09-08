# Earlier acceptance and reported deceased-donor transplant receipt

Adding earlier acceptance information **did not meet the prespecified continuation rule**.

It reduced average absolute error from **8.888 to 8.774 percentage points** compared with
receipt history plus access information: an improvement of **0.113 points (1.27%)**. The fixed
minimum required both 0.5 points and 5%. The added acceptance inputs slightly worsened error
in the first evaluation period and improved it in the second. The descriptive interval for
the error difference was **[-0.459, 0.274] points**, spanning both improvement and worsening.

The full model improved on both simple forecasts and met the specified bias limits, but those
successes do not override the failed incremental-improvement rule. **Development of this
acceptance extension stops under Plan 0023.** This finding does not establish that acceptance
information has no value in other settings; it does not justify changing this study's fixed
question, features or comparisons after seeing the results.

Completed September 8, 2026 UTC. Governed by the [separate specification](specs/deceased-donor-receipt-0023.md),
[fixed configuration](../configs/receipt_study/experiment.yaml),
[source audit](audits/source-binding-0023.md), and [Plan 0023](plans/0023-deceased-donor-receipt-study.md).

This exploratory study predicts the percentage of a kidney program's original listing group recorded as removed for deceased-donor transplant within 18 months. The target is derived from five published statuses, including unknown post-transplant health status. It is not survival among recipients or a patient-level probability.

Each row represents one program and a July-June listing group. All models use identical evaluation rows. The two evaluation groups are July 2022-June 2023 and July 2023-June 2024; predictions originate at the July 2022 and July 2023 report releases. Both fits use the July 2019-June 2020 listing group, whose outcome was public in July 2022. Earlier reports supply only information actually public by each origin.

Average errors below give each evaluation period equal weight. Hypothetical example: a
prediction of 40% against a derived 30% outcome has a 10-percentage-point absolute error.
Signed error is prediction minus observed; positive means too high on average. Ridge is a
regression model that limits how strongly it weights its inputs.

| Forecast | Average absolute error (points) | Signed error (points) | Volume-weighted error (points) |
|---|---:|---:|---:|
| Latest earlier receipt percentage | 10.267 | -3.856 | 8.333 |
| Mean earlier receipt percentage | 10.411 | -5.486 | 9.331 |
| Ridge: receipt history | 8.913 | -1.466 | 7.389 |
| Ridge: history and access | 8.888 | -1.945 | 7.294 |
| Ridge: history, access and acceptance | 8.774 | -0.637 | 7.234 |

## Each evaluation period

Volume weighting uses each program's original listed-candidate count within a period, then gives
the two periods equal weight. It does not count unique patients across programs. All five
forecasts use 435 program-cohort rows from 222 distinct programs: 218 in the first period and
217 in the second. Both fits use the same 215 eligible training rows.

| Model | Origin / outcome report | Programs | Absolute error (points) | Signed error (points) |
|---|---|---:|---:|---:|
| Latest earlier receipt percentage | 2205 / 2505 | 218 | 10.455 | -3.810 |
| Latest earlier receipt percentage | 2305 / 2605 | 217 | 10.078 | -3.901 |
| Mean earlier receipt percentage | 2205 / 2505 | 218 | 10.525 | -5.436 |
| Mean earlier receipt percentage | 2305 / 2605 | 217 | 10.298 | -5.536 |
| Ridge: receipt history | 2205 / 2505 | 218 | 9.072 | -1.334 |
| Ridge: receipt history | 2305 / 2605 | 217 | 8.755 | -1.598 |
| Ridge: history and access | 2205 / 2505 | 218 | 8.891 | -1.737 |
| Ridge: history and access | 2305 / 2605 | 217 | 8.884 | -2.154 |
| Ridge: history, access and acceptance | 2205 / 2505 | 218 | 8.898 | -0.177 |
| Ridge: history, access and acceptance | 2305 / 2605 | 217 | 8.651 | -1.098 |

The release codes `2205 / 2505` refer to the July 2022 prediction origin and July 2025
outcome report; `2305 / 2605` refer to July 2023 and July 2026. Codes are source identifiers,
not exact publication dates. The source manifest preserves each date's stated precision.

## Fixed paired comparisons

The difference is added-input model minus comparator average error, in percentage points. Negative favors the added-input model. These descriptive 95% intervals resample whole programs, keeping repeated cohorts together; they do not measure accuracy in a new period.

| Added-input model | Comparator | Difference | Descriptive interval |
|---|---|---:|---:|
| Ridge: receipt history | Latest earlier receipt percentage | -1.353 | [-1.710, -1.016] |
| Ridge: receipt history | Mean earlier receipt percentage | -1.498 | [-2.139, -0.907] |
| Ridge: history and access | Latest earlier receipt percentage | -1.379 | [-1.786, -0.965] |
| Ridge: history and access | Mean earlier receipt percentage | -1.523 | [-2.169, -0.871] |
| Ridge: history, access and acceptance | Latest earlier receipt percentage | -1.492 | [-2.031, -0.911] |
| Ridge: history, access and acceptance | Mean earlier receipt percentage | -1.637 | [-2.442, -0.801] |
| Ridge: history and access | Ridge: receipt history | -0.026 | [-0.327, 0.302] |
| Ridge: history, access and acceptance | Ridge: receipt history | -0.139 | [-0.553, 0.338] |
| Ridge: history, access and acceptance | Ridge: history and access | -0.113 | [-0.459, 0.274] |

## Prespecified population sensitivities

These rescore the same fixed predictions among larger listing groups, without refitting.

| Minimum listed candidates | Forecast | Program-cohort rows | Absolute error (points) |
|---|---|---:|---:|
| 20 | Latest earlier receipt percentage | 406 | 9.891 |
| 20 | Mean earlier receipt percentage | 406 | 10.239 |
| 20 | Ridge: receipt history | 406 | 8.509 |
| 20 | Ridge: history and access | 406 | 8.579 |
| 20 | Ridge: history, access and acceptance | 406 | 8.404 |
| 30 | Latest earlier receipt percentage | 387 | 10.014 |
| 30 | Mean earlier receipt percentage | 387 | 10.277 |
| 30 | Ridge: receipt history | 387 | 8.622 |
| 30 | Ridge: history and access | 387 | 8.687 |
| 30 | Ridge: history, access and acceptance | 387 | 8.494 |

## Decision and limits

Continuation requires at least 0.5 points and 5% improvement versus both simple forecasts and history-plus-access, improvement in both periods, and the fixed absolute-bias limits. These are project-use rules, not clinical-benefit thresholds.

- The 0.113-point improvement over history plus access is below 0.5 points.
- Its 1.27% improvement is below 5%.
- Error did not improve over history plus access at the July 2022 origin.

Seven releases have independent report evidence. The 2018 and 2020 releases are excluded because their source-bound date evidence could not be recovered. Six historical reports are bound through saved cached PDF text; the newest has a verified PDF. Historical PDF-byte fingerprints are not claimed. This restriction leaves both evaluation origins using the same earlier training cohort.

The 18-month outcome uses a conservative December 31 follow-up bound for temporal checks, not an invented source censor date. Month-only publication values retain their precision. Missing future reports and components are unknown outcomes, not zero receipt. Larger listing groups receive more weight only in the secondary summary; candidates may be listed at more than one program.

Original V1/V2 and both completed follow-ups remain unchanged. These already-inspected historical sources provide exploratory evidence, not fresh or prospective validation. No model is promoted. No causal, patient-level, clinical or regulatory conclusion follows from the comparison.

## Population accounting

Counts describe programs at each origin before checking their later outcomes. A program can have more than one exclusion reason. Full identifiers and exact lists remain in `qa.json`.

| Earlier / later release | Origin programs | Eligible rows | Missing future report | New later programs | Exclusion reasons (counts) |
|---|---:|---:|---:|---:|---|
| 1905->2205 | 246 | 215 | 17 | 5 | missing future report: 17; missing prior receipt: 7; target n below 10: 12 |
| 2105->2405 | 241 | 216 | 10 | 5 | missing future report: 10; missing prior receipt: 5; target n below 10: 13 |
| 2205->2505 | 236 | 218 | 6 | 6 | missing future report: 6; missing prior receipt: 2; target n below 10: 11 |
| 2305->2605 | 238 | 217 | 9 | 4 | missing future report: 9; missing prior receipt: 4; target n below 10: 9 |

Here, "missing future report" means no future outcome row, whether or not the program remains
in the later directory. The six missing future outcomes in the first evaluation period comprise
five programs absent from the later directory and one still listed there without an outcome row.
In the second period, the corresponding counts are six and three. These are absent records,
not proof of program closure. No new later program is retroactively added to an earlier
prediction universe. The `2105→2405` pair is retained for panel accounting only: its July 2024
outcome was unavailable at both evaluation origins and enters neither fit.

## Saved evidence and reproduction

The command completed once from the verified immutable workbook cache and the exact saved
source-text evidence. It produced 961 panel rows, 1,638 source-accounting rows, and 2,175
predictions (435 matched program-cohort rows times five forecasts). All nine comparisons use
2,000 program-resampling draws with seed `20260908`; none needed a rejected draw. The source
check, panel build, six fixed Ridge fits, predictions, summaries and packaging ran in one command.
The trusted loader then rechecked file identities, source accounting, temporal metadata,
fitted-parameter identities, matched predictions, summaries, sensitivities and continuation.
An independent review recomputed all summary arithmetic and all nine bootstrap intervals
directly from saved predictions; they matched within 1e-10. Neither check refitted models.

The eight-file local directory, including manifest and completion marker, is **377,445 bytes**:

`data/receipt-study/v1/3bca655e1de9580167edd017af62c63bcc1fa9c20fdd4dbfeed0a41d9ad2832e/`

| Identity | Recorded value |
|---|---|
| Study | `kidney_deceased_donor_receipt_0023_v1` |
| Build time | `2026-09-08T04:23:14.846199+00:00` |
| Base Git commit | `ebd29c9fdd46017a40966c2b75ef38b5e1fbc4d7` |
| Working tree | Uncommitted implementation; explicitly marked noncanonical, with every production source file hash recorded |
| Python | `3.12.13` |
| Dependency lock SHA-256 | `34357af7a03a9cec4a1becab5444a047356b0c40d47c18ff79e703b82ec46041` |
| Experiment SHA-256 | `adc6b4196670c0ac91b78021acbe3c982b4df933e9e860376fc667916713a9ec` |
| Source configuration SHA-256 | `4813ae2a67ae8b4d128bb8e33681f9a6a3f81eb09ebe37e40739c19980c7ab79` |
| Specification SHA-256 | `e473208f4154086455b7d0d4b64e49b113bb5b11ff2f653633a3e7a8ee7251b7` |
| Manifest SHA-256 | `a9fac0c6342d560a8d63fd2ea92e8f507305150534e7c4f24ec101fe81396b49` |
| Evaluation JSON SHA-256 | `e0c88d78349ed9b8b9891ac1c10557a8a3a728b9ddc5f11fbde1e1a44655d507` |
| Prediction Parquet SHA-256 | `7a0deacfa2e567fc61c8d5d64f5db91a9e37bc905c3daf469c850bd200b59eed` |

The experiment, source configuration and specification were fingerprinted at 04:07:51 UTC,
before any real-data model errors were calculated. Their bytes remain unchanged. The run
identifier combines those inputs, the source manifest, lock and all production source hashes.
The saved evaluation includes six sets of learned coefficients, intercepts, replacement
statistics and scaling parameters; it accepts no arbitrary serialized model.

To reproduce from the exact implementation in a separate checkout without this completed run,
first restore the immutable cache under `data/raw/srtr/` and the source-text files at the paths
and hashes in [sources.json](../configs/receipt_study/sources.json). Also restore the verified
July 2026 PDF at `data/audit-0022/nynstx1_ki.pdf`: 2,193,208 bytes, SHA-256
`8d0d4a401de55e2ca7fd248168353bb27b0b9846d2f9496688122faaca5095a9`.
These ignored inputs are required; a Git checkout alone is insufficient. Historical URLs
returned 404 during the audit, so the
retained text snapshots must be preserved separately. Do not substitute a current rolling PDF,
recreate text, or accept a new fingerprint automatically. Then run from the repository root:

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
$env:MPLCONFIGDIR = "$PWD/.uv-cache/matplotlib"
uv sync --frozen
uv run kasm data verify-cache
uv run kasm patient-journey receipt-study --check-sources
uv run kasm patient-journey receipt-study
```

The final command refuses an existing run before fitting. In this working tree, inspect the
saved result instead:

```powershell
@'
from pathlib import Path
from kasm.patient_journey.receipt_artifacts import load_receipt_study
root = Path.cwd()
run = root / "data/receipt-study/v1/3bca655e1de9580167edd017af62c63bcc1fa9c20fdd4dbfeed0a41d9ad2832e"
result = load_receipt_study(root, run)
print(result["evaluation"]["continuation"])
'@ | uv run python -
```

The source-only check fits no model. Reproduction is a check of the same retrospective study,
not a new evaluation or opportunity to tune it. Build timestamps and Git cleanliness may change
in another checkout; predictions and fixed comparisons must retain their recorded meaning.
No original V1/V2 backtest or frozen replay is part of this workflow.

## Verification

All **722 tests passed**, with **85.08% overall branch-inclusive coverage** and **85.29% for
patient-journey modules**, exceeding both required 80% gates. Locked environment synchronization,
formatting, lint (including security rules), and type checks passed. Independent agents reviewed
source evidence, temporal rules, model comparisons and artifact loading; observed defects have
regressions that failed before their fixes. Exact SHA-256 comparison preserved all 48 protected
original configuration, source, application, release and lock files. The local output remains
ignored by Git; this document records the result without changing either application.
