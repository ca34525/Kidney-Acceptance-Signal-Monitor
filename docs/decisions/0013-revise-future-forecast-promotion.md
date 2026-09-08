# Decision 0013 — Permit a revised forecast-promotion policy

Accepted September 8, 2026 under the request to write Plan 0027 and adjust documentation.

The original V1 Ridge replay improved average absolute log error by 10.13% but failed the
rule requiring absolute mean signed error no greater than persistence's: 0.01145 versus
0.00885. That exact zero-tolerance comparison was a project choice. It does not quantify
the practical importance or uncertainty of a small bias difference and is not a universal
requirement for a useful forecast.

Allow the existing Ridge method or a revised method to be selected for a later release even
when it fails that original comparison. Use the separate
[Plan 0027 specification](../specs/acceptance-forecast-0027.md) to assess useful accuracy,
typical and large errors, calibration, year/subgroup consistency and uncertainty under
explicitly justified bias tolerances. Diagnose errors first; fix the small candidate
comparison and its policy before scoring alternatives. The revision is informed by known
results and must not be represented as prespecified for the original replay.

Preserve original specifications' experiment requirements, frozen configuration values,
canonical results and artifact identities. Record a later selection as a new decision,
not a retroactive pass of the original gate. Scope old no-retuning and promotion language
to that original experiment. New historical development and an explicitly retrospective
display decision are permitted under their own contract; they are not fresh validation.
No prospective outcome must be awaited merely to make that disclosed product decision.

The current app still displays persistence. Changing it requires a separately implemented,
tested, versioned artifact and display decision; forecast bands retain a separate check.
Original V2's nonpromotion requirement and shared data, timing, identity, nonclinical and
nonregulatory safeguards are unchanged. This decision changes documentation and future
policy only; it neither promotes a model now nor authorizes rewriting completed evidence.
