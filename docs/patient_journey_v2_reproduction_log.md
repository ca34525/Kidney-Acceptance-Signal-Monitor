# Patient-journey V2 reproduction log

## Environment and fixed inputs

- Python: 3.12.13
- Dependency lock SHA-256:
  `9783d6fc61d5c69012494519e674b5c17c0f346ba1923a4758c38fcdc573a687`
- Git commit recorded by the artifacts:
  `9357a33f96a19b4024d222a526e696b297740738`
- Worktree state recorded by the artifacts: dirty; build classified noncanonical
- Source manifest SHA-256:
  `5b30cd508a10e9cc24a6097f0eea868447c168b2744b50977aa56db43a6b86e5`
- Experiment freeze SHA-256:
  `ab8c01453c36039b293a8e7453b17b2b326faf734a081a4b67f8bfe132b1de79`
- Methodology configuration SHA-256:
  `ba254a7cecb346618b863ce9a248e12ae5ed552bcd88a1e0cf1a6f2b0a9e8620`

## Offline reproduction

From the repository root, after the nine-source immutable cache has been populated and verified:

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
uv sync --frozen
uv run kasm data verify-cache
uv run kasm patient-journey data build
uv run kasm patient-journey model evaluate
uv run kasm patient-journey artifacts build
uv run streamlit run app/patient_journey_v2.py
```

Only `data sync` is networked. The commands above consume the verified cache and do not change V1
processed, modeling, release, frozen-configuration, or default-app assets.

## Generated identities

| Stage | Evidence |
|---|---|
| Processed | 966 panel rows, 5,678 safety rows, artifact-set SHA-256 `dc5f96040d5a3f3dd0ec644c72f9d011c12aeb162e03f43ae878e9715eb98ba8` |
| Modeling | 3,685 historical prediction rows, artifact-set SHA-256 `ac579a8891d01d71b6a52a83c90c19874da9a6594fab33940b2e646983dbdf68` |
| Release | Four payload files, 679,407 bytes, content SHA-256 `6542fc61968b4cda95a33dcb5057b41b37d6fc3ba5ad40397ee8e7a1ed2cc205` |

The release payload is exactly:

- `patient_journey_panel.parquet`
- `safety_measures.parquet`
- `predictions.parquet`
- `evaluation.json`

`release_manifest.json` binds those files to their individual hashes and records the processed and
modeling artifact identities, source/configuration/methodology/lock hashes, source-file hashes,
Python version, Git commit and dirty state, build time, evidence status, and nonpromotion contract.

The release validates offline before the Streamlit view reads any payload. Schema disagreement,
hash mismatch, mixed artifact generations, an unexpected file, or loss of the permanent
nonpromotion state is a hard error.

These hashes establish internal consistency and detect accidental tampering or mixed generations;
they are not a digital signature and do not authenticate a publisher against an attacker able to
replace every payload and manifest consistently. The product boundary therefore requires the
checked-in bundle to come from a trusted repository checkout.

## Verification record

The final command evidence for this plan is recorded in
`docs/plans/0019-patient-journey-v2-completion.md`. The Streamlit AppTest covers offline loading,
program selection, missing-value text, target and safety timing, provenance, and the explicit
no-promotion/no-future-forecast state.

The workspace artifact is a development reproduction because the requested work remains
uncommitted.
After an explicit commit, a clean rebuild will record a new Git commit, build time, and canonical
status and can therefore have a different artifact-set identity even when analytical content is
unchanged.
