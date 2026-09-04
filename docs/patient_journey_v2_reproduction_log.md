# Patient-journey V2 reproduction log

## Environment and fixed inputs

- Python: 3.12.13
- Dependency lock SHA-256:
  `9783d6fc61d5c69012494519e674b5c17c0f346ba1923a4758c38fcdc573a687`
- Git commit recorded by the artifacts:
  `cdea5c40302de1797d83698566d2ebb51de16938`
- Worktree state recorded by the artifacts: clean; `canonical_build: true`
- Model/release build time: `2026-09-04T22:40:05.364170Z`
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
| Processed | 966 panel rows, 5,678 safety rows, artifact-set SHA-256 `66602b3775675bceb8dd57061bcb8b98520b3f9029c0fca222127d3a5f844409` |
| Modeling | 3,685 historical prediction rows, artifact-set SHA-256 `6e6ebacbbb63f14382f2cb9e0521e03995594ff9d497bc009b3ab89e93f60775` |
| Release | Four payload files, 679,407 bytes, content SHA-256 `ce2844edbcec92c09d0053720d5331dd37ed43ab75de7aa4dd1de431c79a9eee` |

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

Canonical publication was committed and pushed as `0353f99`. GitHub Actions run
[33926762819](https://github.com/ca34525/Kidney-Acceptance-Signal-Monitor/actions/runs/33926762819)
passed both quality and container jobs. Local verification passed 236 tests at 83.93% core
branch coverage, locked dependency checks, formatting, lint, strict mypy, both application
health endpoints, and non-root Docker startup. Exporting the staged checkout with Windows
line-ending conversion enabled preserved every V2 bundle byte and passed the offline AppTest.

The published bundle was regenerated from a clean isolated checkout of `cdea5c4`. The three
Parquet payloads have identical analytical values to the prior development build, and
`evaluation.json` is byte-identical. Only build provenance and the dependent content identities
changed. All embedded processed and modeling provenance records were checked for the same source
commit, clean worktree, and canonical status before publication.

The isolated source checkout used `core.autocrlf=false` to preserve the pinned configuration and
lock bytes and `core.longpaths=true` for the V1 hash-addressed paths on Windows. Its builds used
the already synchronized Python 3.12.13 environment with `PYTHONPATH` pointing to that checkout's
`src` directory (the imported package location was verified), and the data build received the
original verified cache through `--cache-dir`. The source checkout was clean before both data
and model generation; publishing the release directory was the final generation step.

For a later canonical rebuild, use a clean source checkout and move any previously generated
untracked release bundle outside it before running the three V2 build commands. Commit the
resulting bundle only after generation and validation. A new build timestamp changes artifact
identities even when the analytical content is unchanged. The bundle's Git SHA identifies the
source build commit, not the subsequent commit that adds its generated files.

Both approved release roots are required by the repository tests. V2 release files are marked
binary in `.gitattributes`, as V1 already was, to preserve their exact hashes across checkouts.
