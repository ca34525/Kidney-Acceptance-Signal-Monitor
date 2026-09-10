# Decision 0016 — Retire the exact-bias gate and correct interview readiness

Accepted September 8, 2026 under [Plan 0029](../plans/0029-interview-readiness-corrections.md).

The original rule requiring Ridge's absolute mean signed error to be no greater than
persistence's was a design mistake. It rejected an accuracy improvement for a tiny difference
in mean error without a demonstrated connection to the intended review task. Remove its
endorsement and its use as a general model-selection rule. The original configuration,
recorded result and code needed to reproduce that historical decision remain audit evidence;
they do not govern future model selection. Preserving a result does not require endorsing it.

Plan 0027's numerical comparison remains the research actually performed. Its selected
one-input adjustment is a provisional research choice, with only a small observed advantage
over full Ridge. The revised numerical tolerances are project judgments, not demonstrated
thresholds of usefulness. They must not become automatic deployment requirements in a later
release merely because they were configured and tested. This interpretation supersedes
current claims of deployment readiness, without relabeling an original result as a pass.

For future choices, compare methods on a declared primary loss and the same temporal
population. Explain signed errors, tails, groups and simplicity alongside that comparison.
Decide whether deployment is worthwhile using a specific user task and explicit consequences
of errors. Keep forecast bands withheld. A later band study should examine calibration and
width jointly using a proper interval score, with year/group results as diagnostics rather
than requiring every confidence interval to contain the nominal coverage. See
[Gneiting and Raftery, 2007](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jasa.pdf),
section 6.2. No new score, threshold or fit is computed by this correction.

The outside review identified an unrecorded SRTR offer-cohort definition change, a missing
app-time release check and inaccurate presentation cohort dates. Resolve those before a
future release decision. The app must validate one complete release before displaying it,
including when environment overrides select a reproduced bundle. Retain the offline workflow
and explicit eligibility. The current historical product remains available; Plan 0028's new
forecast is not deployed by this decision.

This work changes current interpretation and trusted loading, not original study data or
numerical evidence. Audit source definitions against release-bound evidence, document limits,
and never infer that a preserved hash proves stable scientific meaning or original availability.
