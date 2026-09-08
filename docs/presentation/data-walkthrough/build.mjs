// Reproduce the data walkthrough from its attributed source excerpts and explanation.
// This documentation builder does not parse source workbooks or change analytical results.
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../..');
const { RUNTIME_NODE_MODULES, PRESENTATIONS_SKILL_DIR, RUNTIME_PYTHON } = process.env;
for (const value of [RUNTIME_NODE_MODULES, PRESENTATIONS_SKILL_DIR, RUNTIME_PYTHON]) {
  if (!value || !path.isAbsolute(value)) throw new Error('Set the three absolute runtime paths in README.md.');
}
const buildName = process.env.DATA_SLIDES_BUILD_NAME || 'data-slides-reproduction';
if (!/^[a-zA-Z0-9_-]+$/.test(buildName)) throw new Error('Use a simple directory name for DATA_SLIDES_BUILD_NAME.');
const output = path.join(root, 'data/patient_journey_v2_followup/p4_build', buildName);
await fs.mkdir(path.dirname(output), { recursive: true });
await fs.mkdir(output);
const delivery = path.join(output, 'delivery');
await fs.mkdir(delivery);
const { FileBlob, Presentation, PresentationFile } = await import(pathToFileURL(path.join(RUNTIME_NODE_MODULES, '@oai/artifact-tool/dist/artifact_tool.mjs')));
const { finalizePresentation, makeNativeBulletParagraphs, applyPresentationChartFont } = await import(pathToFileURL(path.join(PRESENTATIONS_SKILL_DIR, 'container_tools/artifact_tool_utils.mjs')));
const contentPath = path.join(here, 'slides.json');
const content = JSON.parse(await fs.readFile(contentPath, 'utf8'));
const referencePath = path.join(root, 'docs/presentation/v2-followup/interview.pptx');
const reference = await PresentationFile.importPptx(await FileBlob.load(referencePath));
const proto = reference.toProto();
const referenceSlides = proto.slides;
// Reuse the current deck's plain text and table layouts, including its theme and masters.
proto.slides = content.slides.map((data, i) => {
  const sourceIndex = ['workbook', 'join', 'table'].includes(data.layout) ? 9 : 2;
  const slide = structuredClone(referenceSlides[sourceIndex]);
  slide.id = `data-walkthrough-${i + 1}`;
  slide.index = i;
  slide.elements = slide.elements.filter(e => ['533', '532'].includes(e.id));
  return slide;
});
proto.charts = [];
proto.images = [];
const presentation = Presentation.load(proto);
const font = 'Helvetica Neue';
function textBox(slide, name, text, left, top, width, height, size) {
  const shape = slide.shapes.add({ name, geometry: 'textbox', position: { left, top, width, height }, fill: 'none', line: { fill: 'none', width: 0 } });
  shape.text = text;
  shape.text.style = { typeface: font, fontSize: size, color: '#222222', autoFit: 'none', verticalAlignment: 'top' };
  return shape;
}
function bullets(slide, name, items, left, top, width, height, size = 26, gap = 17) {
  const body = textBox(slide, name, '', left, top, width, height, size);
  body.text = makeNativeBulletParagraphs(items, { marginLeftPoints: 18, hangingPoints: 10, spaceAfterPoints: gap });
}
const tableOwners = [], chartOwners = [];
for (let i = 0; i < content.slides.length; i++) {
  const slide = presentation.slides.getItem(i);
  const data = content.slides[i];
  const title = slide.shapes.items.find(s => s.id === '533');
  if (!title) throw new Error('The reference title shape changed. Review the layout before rebuilding.');
  title.text = data.title;
  title.text.style = { typeface: font, fontSize: 36, color: '#000000', autoFit: 'none' };
  const number = slide.shapes.items.find(s => s.id === '532');
  number.text = String(i + 1);
  number.text.style = { typeface: font, fontSize: 12, color: '#333333' };
  if (data.layout === 'source') {
    const body = textBox(slide, 'source-bullets', '', 41, 147, 1178, 454, 30);
    body.text = makeNativeBulletParagraphs(data.bullets, { marginLeftPoints: 20, hangingPoints: 11, spaceAfterPoints: 20 });
  } else if (data.layout === 'workbook') {
    textBox(slide, 'table-grain', data.intro, 41, 116, 1197, 79, 26);
    textBox(slide, 'source-dates', data.dates, 41, 202, 1197, 36, 23);
    const values = [data.headers, data.fields, ...data.rows.map(r => [r[0], r[1], String(r[2]), `${r[3].toFixed(2)}%`])];
    const table = slide.tables.add({ rows: values.length, columns: 4, left: 41.333, top: 258, width: 1197.33, height: 235, columnWidths: [225, 225, 292, 455.33], values });
    table.borders.assign({ fill: '#BBBBBB', width: 0.7, style: 'solid' });
    table.cells.block({ row: 0, column: 0, rowCount: values.length, columnCount: 4 }).assign({ fill: '#FFFFFF', textStyle: { typeface: font, fontSize: 26, color: '#000000' }, margins: { left: 10, right: 10, top: 6, bottom: 6 } });
    table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: 4 }).assign({ fill: '#F2F2F2', textStyle: { bold: true, fontSize: 25 } });
    table.cells.block({ row: 1, column: 0, rowCount: 1, columnCount: 4 }).assign({ fill: '#F7F7F7', textStyle: { fontSize: 20, color: '#555555' } });
    [72, 42, 43, 43, 43].forEach((height, index) => { table.rows[index].height = height; });
    tableOwners.push(i + 1);
    textBox(slide, 'display-rounding', data.table_note, 41, 514, 1197, 29, 18);
    textBox(slide, 'example-meaning', data.interpretation, 41, 548, 1197, 65, 25);
    textBox(slide, 'denominator', data.definition, 41, 613, 1197, 30, 20);
  } else if (data.layout === 'qa') {
    textBox(slide, 'contract-meaning', data.intro, 41, 117, 1197, 45, 26);
    const body = textBox(slide, 'qa-bullets', '', 41, 190, 1178, 408, 28);
    body.text = makeNativeBulletParagraphs(data.bullets, { marginLeftPoints: 20, hangingPoints: 11, spaceAfterPoints: 20 });
    textBox(slide, 'qa-limits', data.limitation, 41, 610, 1197, 30, 20);
  } else if (data.layout === 'join') {
    textBox(slide, 'join-example-intro', data.intro, 41, 123, 1197, 55, 28);
    const values = [data.headers, ...data.rows.map(row => row.map(String))];
    const table = slide.tables.add({ rows: 4, columns: 3, left: 41.333, top: 217, width: 1197.33, height: 260, columnWidths: [205, 496, 496.33], values });
    table.borders.assign({ fill: '#BBBBBB', width: 0.7, style: 'solid' });
    table.cells.block({ row: 0, column: 0, rowCount: 4, columnCount: 3 }).assign({ fill: '#FFFFFF', textStyle: { typeface: font, fontSize: 29, color: '#000000' }, margins: { left: 12, right: 12, top: 8, bottom: 8 } });
    table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: 3 }).assign({ fill: '#F2F2F2', textStyle: { bold: true, fontSize: 26 } });
    [82, 55, 55, 55].forEach((height, index) => { table.rows[index].height = height; });
    tableOwners.push(i + 1);
    textBox(slide, 'positional-join-error', data.interpretation, 41, 500, 1197, 42, 27);
    textBox(slide, 'identity-match', data.correct_match, 41, 556, 1197, 42, 27);
    textBox(slide, 'time-check', data.limitation, 41, 613, 1197, 30, 20);
  } else if (data.layout === 'oar') {
    textBox(slide, 'oar-purpose', data.intro, 41, 122, 1197, 46, 27);
    textBox(slide, 'oar-equation', data.formula, 41, 202, 590, 70, 43);
    textBox(slide, 'oar-inputs', data.definitions, 41, 295, 567, 155, 25);
    textBox(slide, 'oar-adjustment', data.adjustment, 41, 456, 567, 77, 23);
    textBox(slide, 'oar-example', data.example, 41, 541, 580, 65, 24);
    const meanings = textBox(slide, 'oar-interpretation', '', 668, 204, 565, 402, 25);
    meanings.text = makeNativeBulletParagraphs(data.interpretation, { marginLeftPoints: 18, hangingPoints: 10, spaceAfterPoints: 20 });
    textBox(slide, 'published-values', data.limitation, 41, 616, 1197, 30, 18);
  } else if (data.layout === 'v1-method') {
    textBox(slide, 'v1-purpose', data.intro, 41, 122, 1197, 45, 27);
    textBox(slide, 'comparison-heading', data.left_heading, 41, 200, 565, 40, 28);
    textBox(slide, 'evaluation-heading', data.right_heading, 658, 200, 575, 40, 28);
    const left = textBox(slide, 'comparison-method', '', 41, 260, 558, 285, 26);
    left.text = makeNativeBulletParagraphs(data.left_bullets, { marginLeftPoints: 18, hangingPoints: 10, spaceAfterPoints: 19 });
    const right = textBox(slide, 'evaluation-method', '', 658, 260, 575, 285, 26);
    right.text = makeNativeBulletParagraphs(data.right_bullets, { marginLeftPoints: 18, hangingPoints: 10, spaceAfterPoints: 19 });
    textBox(slide, 'v1-result', data.result, 41, 561, 1197, 75, 26);
  } else if (data.layout === 'columns') {
    textBox(slide, 'purpose', data.intro, 41, 122, 1197, 63, 27);
    textBox(slide, 'left-heading', data.left_heading, 41, 209, 568, 66, 28);
    textBox(slide, 'right-heading', data.right_heading, 665, 209, 573, 66, 28);
    bullets(slide, 'left-explanation', data.left_bullets, 41, 281, 567, 299);
    bullets(slide, 'right-explanation', data.right_bullets, 665, 281, 573, 299);
    textBox(slide, 'conclusion', data.result, 41, 591, 1197, 53, 24);
  } else if (data.layout === 'table') {
    textBox(slide, 'purpose', data.intro, 41, 122, 1197, 66, 27);
    const values = data.table, rows = values.length, columns = values[0].length;
    const height = rows > 6 ? 360 : rows > 4 ? 316 : 236;
    const table = slide.tables.add({ rows, columns, left: 41, top: rows > 6 ? 190 : 209, width: 1197, height,
      columnWidths: data.column_widths, values });
    table.borders.assign({ fill: '#BBBBBB', width: 0.7, style: 'solid' });
    table.cells.block({ row: 0, column: 0, rowCount: rows, columnCount: columns }).assign({ fill: '#FFFFFF',
      textStyle: { typeface: font, fontSize: data.table_font || 27, color: '#222222' },
      margins: { left: 12, right: 12, top: rows > 6 ? 4 : 8, bottom: rows > 6 ? 4 : 8 } });
    table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: columns }).assign({ fill: '#F2F2F2', textStyle: { bold: true } });
    if (rows > 6) for (const row of table.rows) row.height = 40;
    tableOwners.push(i + 1);
    if (data.detail) textBox(slide, 'table-detail', data.detail, 41, 547, 1197, 39, 22);
    textBox(slide, 'conclusion', data.result, 41, 591, 1197, 53, 24);
  } else if (data.layout === 'chart') {
    textBox(slide, 'purpose', data.intro, 41, 122, 1197, 64, 27);
    const config = data.chart;
    const chart = slide.charts.add(config.type, {
      position: { left: 41, top: 204, width: 733, height: 366 },
      categories: config.categories,
      series: config.series.map((series, j) => ({ ...series, fill: j ? '#304F65' : '#7BADC9',
        ...(config.type === 'line' ? { line: { fill: '#304F65', width: 3 } } : {}) })),
      ...(config.type === 'bar' ? { barOptions: { direction: 'column', grouping: 'clustered', gapWidth: 100 } }
        : { lineOptions: { grouping: 'standard', smooth: false } }),
      hasLegend: config.series.length > 1,
      legend: { position: 'top', textStyle: { fontSize: 18 } },
      dataLabels: { showValue: true, position: config.type === 'line' ? 'above' : 'outEnd', textStyle: { fontSize: 18 } },
      xAxis: { textStyle: { fontSize: 18 } },
      yAxis: { min: 0, max: config.max, numberFormatCode: config.number_format,
        title: { text: config.axis_title, textStyle: { fontSize: 18 } },
        textStyle: { fontSize: 18 }, majorGridlines: { fill: '#EEEEEE', width: 1 } },
      chartFill: '#FFFFFF', chartLine: { fill: 'none', width: 0 }
    });
    for (const series of chart.series.items) series.valuesFormatCode = config.number_format === '0%' ? '0.00%' : config.number_format;
    applyPresentationChartFont(chart, { fontFamily: font });
    chartOwners.push(i + 1);
    textBox(slide, 'chart-heading', data.right_heading, 823, 202, 410, 77, 27);
    bullets(slide, 'chart-interpretation', data.right_bullets, 823, 290, 410, 286, 24, 16);
    textBox(slide, 'conclusion', data.result, 41, 591, 1197, 53, 24);
  } else {
    throw new Error(`No layout for slide ${i + 1}`);
  }
  textBox(slide, 'source-caption', data.caption, 41, 649, 1185, 23, 14);
  textBox(slide, 'claim-boundary', `Version ${content.package_version}. ${content.banner}`, 41, 678, 1185, 23, 15);
  slide.speakerNotes.textFrame.setText(`${data.appendix ? 'Optional reference slide.\n\n' : ''}${data.notes}\n\nSources (repository-relative unless URL):\n${data.sources.join('\n')}\n\nDocumentation version ${content.package_version}. ${content.banner}`);
}
const draft = path.join(output, 'draft.pptx');
const finalPath = path.join(delivery, 'data-walkthrough-with-introduction.pptx');
await (await PresentationFile.exportPptx(presentation)).save(draft);
const sha = async file => createHash('sha256').update(await fs.readFile(file)).digest('hex');
await finalizePresentation({ workspaceDir: output, candidatePath: draft, finalPath,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(PRESENTATIONS_SKILL_DIR, 'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(PRESENTATIONS_SKILL_DIR, 'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-bullet-geometry', '--validate-heading-fit',
    ...tableOwners.flatMap(n => ['--require-native-table-slide', String(n)])],
  explicitTotalSlideCount: content.slides.length, requiredNativeTableOwnerSlides: tableOwners, requiredNativeChartOwnerSlides: chartOwners,
  materializeLiteralChartWorkbooks: true,
  fontPolicy: { basis: 'reference', families: [font], referencePath, referenceSha256: await sha(referencePath) },
  verifyArtifactToolImport: true, receiptPath: path.join(output, 'validation.json') });
const final = await PresentationFile.importPptx(await FileBlob.load(finalPath));
for (let i = 0; i < content.slides.length; i++) {
  const slide = final.slides.getItem(i);
  await fs.writeFile(path.join(output, `slide-${i + 1}.png`), new Uint8Array(await (await slide.export({ format: 'png', scale: 1 })).arrayBuffer()));
}
const git = args => execFileSync('git', args, { cwd: root, encoding: 'utf8' }).trim();
const inputs = ['configs/data_sources.yaml', 'configs/patient_journey_v2/methodology.yaml', 'SPEC.md', 'docs/specs/patient-journey-v2.md', 'docs/model_card.md', 'docs/patient_journey_v2_followup_results.md', 'docs/patient_journey_v2_component_results.md', 'docs/presentation/v2-followup/program-case.md', 'src/kasm/data/parse.py', 'src/kasm/data/cache.py', 'docs/presentation/v2-followup/interview.pptx', 'docs/presentation/data-walkthrough/slides.json', 'docs/presentation/data-walkthrough/build.mjs', 'uv.lock'];
const provenance = { package_version: content.package_version, kind: 'presentation_documentation', source_scope: 'Excerpt metadata below describes the opening workbook examples. Later source releases, periods and results are identified in each slide’s notes.', git_commit: git(['rev-parse', 'HEAD']), git_branch: git(['branch', '--show-current']), git_worktree_dirty: Boolean(git(['status', '--porcelain'])), built_at_utc: new Date().toISOString(), runtime_bundle: '26.905.11957', node_version: process.version, model_parameters: 'Not applicable: no model is fitted or evaluated by this documentation build.', source_release: '2505', source_workbook_sha256: '032584a0a1fe3df70c1f4cc9806f9a2756f8d378795534dae38a47d441422ac5', source_archive_sha256: '359723874d5cdc2acaae98e0ebd3385f4a7d2f4dcc255e4dba90dba2a6036b8b', source_sheet: 'Table B7', source_excel_rows: [3, 4, 5], listing_period: ['2022-07-01', '2023-06-30'], published_date: '2025-07-08', displayed_fields: content.slides.find(data => data.layout === 'workbook').fields, input_sha256: Object.fromEntries(await Promise.all(inputs.map(async p => [p, await sha(path.join(root, p))]))), output_sha256: await sha(finalPath) };
provenance.additional_source_excerpt = { sheets: ['Table B7', 'Table B11 & Figures B10-B14'], excel_rows: [3, 4, 5], identity_fields: ['CTR_CD', 'CTR_TY'], record_counts: [234, 230], matched_identity_count: 229, correct_match: { program_key: 'ALUA:TX1', b7_excel_row: 4, b11_excel_row: 74 }, acceptance_cohort: ['2024-01-01', '2024-12-31'], role: 'source QA illustration only; not a prediction-data join' };
await fs.writeFile(path.join(delivery, 'package-provenance-with-introduction.json'), JSON.stringify(provenance, null, 2) + '\n');
console.log(JSON.stringify({ finalPath, output, slides: content.slides.length, tableOwners, chartOwners }));
