# V2 follow-up interview package

> **Correction for the next presentation revision, 2026-09-07:** The timing slide's notes
> incorrectly describe the July 2026 report as calendar 2023 with overlapping listings.
> Its cohort is **July 2023–June 2024**. “One period” describes the original fitted study,
> not the maximum possible public-source history. See the
> [source audit](../../audits/source-feasibility-0022.md). The slide source, PowerPoint, HTML
> backup and build metadata are preserved in this audit session; correct and rebuild the
> presentation package before using the affected material.

Start with the [editable presentation](interview.pptx), then use the
[rehearsal guide](rehearsal-guide.md). The 15 main slides allocate 18 minutes, leaving two
minutes for questions or delay. Two appendix slides retain the complete model comparison
and source details. Times are planned allocations, not a measured author rehearsal.

- [Offline HTML backup](interview-backup.html): open directly in a browser. All content,
  chart-value tables and speaking notes are inside the file. No server, JavaScript, network,
  font download, source cache or application installation is needed.
- [Illustrative program case](program-case.md): University of Alabama Hospital, with the
  disclosed selection rule, exact source values, denominators, dates and provenance.
- [Speaking and demo guide](rehearsal-guide.md): standalone two-minute app route, compressed
  90-second route, likely panel questions and an unfilled author walkthrough/timing log.

This package presents the original V2 results and the completed P1–P3 investigations. The
original app still presents the original study. The package does not change the app, train a
model, publish a new analytical release or make a future forecast available. The
[original V1 deck](../kidney-acceptance-signal-monitor-interview.pptx) and
[V1 guide](../interview-rehearsal-guide.md) remain separate retained deliverables.

## Authoring and source trail

[slides.json](slides.json) is the complete slide-copy and numeric-display source. It includes
speaking notes and source references for every slide. [build.mjs](build.mjs) imports the
selected Simple Light Mode reference, reuses its layouts, and exports an editable PowerPoint
plus the independent HTML backup. The native charts contain rounded display values from the
completed studies, with embedded data workbooks. The two comparison tables remain editable.
Full-precision analytical evidence stays in its original location.

The chosen reference has SHA-256
`2ae8105571f68403f438458cd51e6ad14f0d989c7af64239e280437a4ac2a633`.
The deck retains its light background, Helvetica Neue typography, 13⅓-by-7½-inch canvas,
two-column, timeline and chart layouts. Content adaptations add the required provenance and
claim footers, replace sample charts/tables, and resize their frames to fit those disclosures.
The original template is unchanged and is not copied into this repository.

[Package provenance](package-provenance.json) records input and output hashes, template identity,
Git commit, dirty status, dependency-lock identity, build time in UTC and the existing analytical
run identities. This is documentation build metadata, not a new study manifest. Earlier
specifications and configurations remain the authority for features and fitted parameters.

## Reproduce the presentation

Presentation authoring uses the supplied desktop artifact runtime, outside the Python
application's dependencies. No package or lockfile change is required. The paths below record
the verified local runtime version; on another machine set them to that same supplied version.
The `uv.lock` environment alone does not include the presentation exporter or template.

Run from the repository root. Choose a fresh `P4_BUILD_NAME`; the script refuses an existing
directory. Its outputs stay under ignored `data/patient_journey_v2_followup/p4_build`.

```powershell
$p4Node = 'C:/Users/chris/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
$env:RUNTIME_NODE_MODULES = 'C:/Users/chris/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:RUNTIME_PYTHON = 'C:/Users/chris/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PRESENTATIONS_SKILL_DIR = 'C:/Users/chris/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations'
$env:PRESENTATION_TEMPLATE = 'C:/Users/chris/.codex/plugins/cache/openai-curated-remote/openai-templates/0.1.1/skills/artifact-template-simple-light-mode/assets/reference.pptx'
$env:P4_BUILD_NAME = 'reproduction'
& $p4Node docs/presentation/v2-followup/build.mjs
```

The fresh directory contains `delivery/interview.pptx`, `delivery/interview-backup.html`,
`delivery/package-provenance.json`, 17 rendered slide PNGs and a private validation receipt.
The source deck and checked-in package are never overwritten by this command. Copy only a
reviewed final delivery into this documentation directory when deliberately updating the package.

Reproduction compares HTML bytes, rendered slide pixels, numeric chart/table content and
speaking notes. PowerPoint ZIP metadata, build timestamps and generated object IDs can vary;
byte-identical PPTX files are not claimed. The script performs no source parsing or fitting.

## Verification and remaining preparation

Every final slide was rendered and inspected. Package, slide-size, heading-fit and native
chart/workbook checks pass. Independent review checked all four charts, all 13 approaches,
six displayed contrast intervals and the selected case against completed evidence. The
original V2 app's ALUA route was exercised with network connections blocked. The required
repository checks and preservation evidence are recorded in
[Plan 0020](../../plans/0020-v2-follow-up-and-interview-story.md).

Rendering uses the artifact runtime, which reports an unsupported embedded-font decode for
one template font payload. The PPTX retains the reference font family and the rendered slides
were checked visually. Native PowerPoint/Google Slides rendering has not been inspected.
The self-contained HTML uses a system font and remains the independent fallback. Open the
PPTX on the presentation machine during the pending rehearsal to check native font appearance.

The author's own-words walkthrough, timed spoken rehearsal and presentation-machine checks
remain pending. Package preparation alone does not complete P4 or establish interview readiness.

Public aggregate research prototype — not clinical or regulatory decision support.
