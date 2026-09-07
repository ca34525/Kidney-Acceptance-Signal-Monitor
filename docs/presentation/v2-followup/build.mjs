// Reproduce documentation from fixed slide copy and the selected presentation template.
// This authoring script never reads source workbooks, fits models or writes analytical bundles.
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../..');
const { RUNTIME_NODE_MODULES, PRESENTATIONS_SKILL_DIR, PRESENTATION_TEMPLATE, RUNTIME_PYTHON } = process.env;
for (const value of [RUNTIME_NODE_MODULES, PRESENTATIONS_SKILL_DIR, PRESENTATION_TEMPLATE, RUNTIME_PYTHON]) {
  if (!value || !path.isAbsolute(value)) throw new Error('Set the four absolute runtime/template paths documented in README.md.');
}
const output = path.join(root, 'data/patient_journey_v2_followup/p4_build', process.env.P4_BUILD_NAME || 'reproduction');
// A new directory keeps prior authoring evidence intact. The directory name has no path semantics.
if (path.basename(output) !== (process.env.P4_BUILD_NAME || 'reproduction') || !/^[a-zA-Z0-9_-]+$/.test(path.basename(output))) {
  throw new Error('P4_BUILD_NAME must contain only letters, numbers, underscores or hyphens.');
}
await fs.mkdir(path.dirname(output), {recursive:true});
await fs.mkdir(output);
const delivery = path.join(output, 'delivery');
await fs.mkdir(delivery);
const { FileBlob, Presentation, PresentationFile } = await import(pathToFileURL(path.join(RUNTIME_NODE_MODULES, '@oai/artifact-tool/dist/artifact_tool.mjs')));
const { finalizePresentation, applyPresentationChartFont } = await import(pathToFileURL(path.join(PRESENTATIONS_SKILL_DIR, 'container_tools/artifact_tool_utils.mjs')));
const content = JSON.parse(await fs.readFile(path.join(here, 'slides.json'), 'utf8'));
const source = await PresentationFile.importPptx(await FileBlob.load(PRESENTATION_TEMPLATE));
const proto = source.toProto();
const referenceSlides = proto.slides;
proto.slides = content.slides.map((data, i) => {
  const slide = structuredClone(referenceSlides[data.template_slide - 1]);
  slide.id = `v2-interview-${i + 1}`;
  slide.index = i;
  // Retain the template layouts and element geometry, replacing sample content in place.
  if (data.layout === 'table') slide.elements = slide.elements.filter(e => e.type !== 9);
  if (data.layout === 'chart') slide.elements = slide.elements.filter(e => e.type !== 6);
  return slide;
});
// No sample charts or images remain in the selected layouts.
proto.charts = [];
proto.images = [];
const presentation = Presentation.load(proto);
const font = 'Helvetica Neue';
function setText(slide, id, text, size = 24) {
  const shape = slide.shapes.items.find(s => s.id === id);
  if (!shape) throw new Error(`Missing retained template shape ${id}`);
  shape.text = text;
  shape.text.style = { typeface: font, fontSize: size, color: '#000000', autoFit: 'none', verticalAlignment: 'top' };
  return shape;
}
function textBox(slide, name, text, left, top, width, height, size) {
  const shape = slide.shapes.add({name, geometry:'textbox',position:{left,top,width,height},fill:'none',line:{fill:'none',width:0}});
  shape.text = text;
  shape.text.style = {typeface:font,fontSize:size,color:'#333333',autoFit:'none'};
  return shape;
}
const chartOwners = [], tableOwners = [];
for (const [i, data] of content.slides.entries()) {
  const slide = presentation.slides.getItem(i);
  if (data.layout === 'cover') {
    setText(slide,'4',data.title,86);
    setText(slide,'5',data.subtitle,24);
    setText(slide,'6',data.label,24);
  } else {
    const titleId = ['chart','timeline'].includes(data.layout) ? '11' : '533';
    setText(slide,titleId,data.title,36);
    setText(slide,['chart','timeline'].includes(data.layout)?'4':'532',String(i+1),12);
    const footerId = data.layout === 'chart' ? '10' : data.layout === 'timeline' ? '7' : '3';
    setText(slide,footerId,'',12);
  }
  if (data.layout === 'columns') {
    setText(slide,'7',data.left,27);
    setText(slide,'8',data.right,27);
  }
  if (data.layout === 'timeline') {
    ['9','13','14'].forEach((id,j)=>{
      const date=setText(slide,id,data.dates[j],24);
      date.position={...date.position,width:330};
    });
    ['15','8','19'].forEach((id,j)=>setText(slide,id,data.events[j],24));
    // The reference rule extends past its page. Keep its intended full-width appearance inside the page.
    const rule=slide.shapes.items.find(s=>s.id==='2');
    if(rule) rule.position={...rule.position,width:1200};
  }
  if (data.layout === 'chart') {
    const frame=slide.shapes.items.find(s=>s.id==='2');
    if(frame) frame.position={...frame.position,height:528};
    setText(slide,'6',data.explanation,26);
    setText(slide,'38',data.stat1,52);
    setText(slide,'39',data.stat1_label,22);
    setText(slide,'41',data.stat2,52);
    setText(slide,'42',data.stat2_label,22);
    const chart=slide.charts.add('bar',{
      position:{left:66.611,top:138.84,width:528.58,height:488},
      categories:data.chart.categories,
      series:data.chart.series.map((s,j)=>({...s,fill:j?'#3D8DFF':'#6DCBF4'})),
      barOptions:{direction:'column',grouping:'clustered',gapWidth:80},
      hasLegend:data.chart.series.length>1,
      legend:{position:'top',textStyle:{fontSize:18}},
      dataLabels:{showValue:true,position:'outEnd',textStyle:{fontSize:17}},
      xAxis:{textStyle:{fontSize:18}},
      yAxis:{min:0,max:data.chart.max,numberFormatCode:data.chart.number_format,
        title:{text:data.chart.axis_title,textStyle:{fontSize:18}},textStyle:{fontSize:18},majorGridlines:{fill:'#EEEEEE',width:1}},
      chartFill:'#FFFFFF',chartLine:{fill:'none',width:0},
    });
    for (let j=0;j<chart.series.items.length;j++) chart.series.items[j].valuesFormatCode=data.chart.number_format==='0%'?'0.00%':data.chart.number_format;
    applyPresentationChartFont(chart,{fontFamily:font});
    chartOwners.push(i+1);
  }
  if (data.layout === 'table') {
    setText(slide,'14',data.intro,24);
    const rows=data.table.length;
    const table=slide.tables.add({rows,columns:3,left:41.333,top:236.33,width:1197.33,height:rows===9?365:340,
      columnWidths:[650,190,357.33],values:data.table});
    table.borders.assign({fill:'#BBBBBB',width:0.7,style:'solid'});
    table.cells.block({row:0,column:0,rowCount:rows,columnCount:3}).assign({fill:'#FFFFFF',textStyle:{typeface:font,fontSize:22,color:'#000000'},margins:{left:8,right:8,top:5,bottom:5}});
    table.cells.block({row:0,column:0,rowCount:1,columnCount:3}).assign({textStyle:{bold:true},fill:'#F2F2F2'});
    tableOwners.push(i+1);
  }
  textBox(slide,'evidence-caption',data.caption||'Package version September 7, 2026. Original results and completed follow-up evidence.',41,640,1185,25,14);
  textBox(slide,'claim-boundary',`Package ${content.package_version}. ${content.banner}`,41,678,1185,25,15);
  const notes=`${data.minutes ? `Planned speaking time: ${data.minutes} minutes. Not a measured rehearsal.` : 'Appendix, outside the 18-minute story.'}\n\n${data.notes}\n\nSources (repository-relative unless URL):\n${data.sources.join('\n')}\n\nStudy package ${content.package_version}. ${content.banner}`;
  slide.speakerNotes.textFrame.setText(notes);
}
const draft=path.join(output,'draft.pptx');
await (await PresentationFile.exportPptx(presentation)).save(draft);
await finalizePresentation({workspaceDir:output,candidatePath:draft,finalPath:path.join(delivery,'interview.pptx'),
  pythonExecutable:RUNTIME_PYTHON,
  integrityValidatorPath:path.join(PRESENTATIONS_SKILL_DIR,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(PRESENTATIONS_SKILL_DIR,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit',
    ...tableOwners.flatMap(n=>['--require-native-table-slide',String(n)])],
  explicitTotalSlideCount:content.slides.length,requiredNativeChartOwnerSlides:chartOwners,
  requiredNativeTableOwnerSlides:tableOwners,materializeLiteralChartWorkbooks:true,
  fontPolicy:{basis:'reference',families:[font],referencePath:PRESENTATION_TEMPLATE,
    referenceSha256:createHash('sha256').update(await fs.readFile(PRESENTATION_TEMPLATE)).digest('hex')},
  verifyArtifactToolImport:true,receiptPath:path.join(output,'validation.json')});
const final=await PresentationFile.importPptx(await FileBlob.load(path.join(delivery,'interview.pptx')));
for(let i=0;i<content.slides.length;i++) {
  const slide=final.slides.getItem(i);
  await fs.writeFile(path.join(output,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await (await slide.export({format:'png',scale:1})).arrayBuffer()));
}
// Self-contained, semantic HTML survives loss of the app, PowerPoint, or network.
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
function htmlTable(rows) {return `<table>${rows.map((r,i)=>`<tr>${r.map(x=>`<${i?'td':'th'}>${esc(x).replaceAll('\n','<br>')}</${i?'td':'th'}>`).join('')}</tr>`).join('')}</table>`;}
const sections=content.slides.map((d,i)=>{
 let body='';
 if(d.left) body=`<div class="columns"><p>${esc(d.left)}</p><p>${esc(d.right)}</p></div>`;
 if(d.subtitle) body=`<p class="large">${esc(d.subtitle)}</p><p>${esc(d.label)}</p>`;
 if(d.table) body=`<p>${esc(d.intro)}</p>${htmlTable(d.table)}`;
 if(d.chart){
  const percent=d.chart.number_format==='0%';
  const rows=[['Measure',...d.chart.series.map(s=>s.name)],...d.chart.categories.map((c,j)=>[c,...d.chart.series.map(s=>percent?`${(100*s.values[j]).toFixed(2)}%`:s.values[j])])];
  body=`<p>${esc(d.chart.axis_title)}</p>${htmlTable(rows)}<p>${esc(d.explanation)}</p><p><strong>${esc(d.stat1)}</strong> ${esc(d.stat1_label)}. <strong>${esc(d.stat2)}</strong> ${esc(d.stat2_label)}.</p>`;
 }
 if(d.dates)body=`<div class="timeline">${d.dates.map((date,j)=>`<div><h3>${esc(date)}</h3><p>${esc(d.events[j])}</p></div>`).join('')}</div>`;
 return `<section id="slide-${i+1}"><small>${i+1}/${content.slides.length} · ${d.minutes?`${d.minutes} minutes planned`:'Appendix'} · V2 package ${content.package_version}</small><h2>${esc(d.title)}</h2>${body}<p class="caption">${esc(d.caption||'Original V2 and completed exploratory follow-up.')}</p><p class="boundary">${esc(content.banner)}</p><details><summary>Speaking notes and sources</summary><p>${esc(d.notes)}</p><ul>${d.sources.map(s=>`<li>${esc(s)}</li>`).join('')}</ul></details></section>`;
}).join('\n');
const html=`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>V2 follow-up interview backup</title><style>
body{font:20px/1.45 Arial,sans-serif;color:#111;margin:0;background:#eee}header,section{background:white;padding:36px 48px;margin:20px auto;max-width:1180px;box-sizing:border-box}h1{font-size:40px}h2{font-size:36px;font-weight:500;margin:16px 0 32px}p{white-space:pre-line}small,.caption{color:#444;font-size:16px}.columns,.timeline{display:grid;grid-template-columns:1fr 1fr;gap:48px}.timeline{grid-template-columns:repeat(3,1fr)}.large{font-size:30px}table{border-collapse:collapse;width:100%;font-size:20px}th,td{text-align:left;border-bottom:1px solid #bbb;padding:10px 8px}th{background:#f3f3f3}.boundary{font-size:16px;border-top:1px solid #bbb;padding-top:10px}details{font-size:18px;margin-top:24px}summary{cursor:pointer}a{color:#174c87}a:focus,summary:focus{outline:3px solid #174c87}nav{display:flex;gap:14px;flex-wrap:wrap}section{scroll-margin-top:20px}li{overflow-wrap:anywhere}@media(max-width:700px){header,section{padding:24px}.columns,.timeline{display:block}h2{font-size:28px}table{font-size:16px}}@media print{body{background:white}header{display:none}section{break-after:page;margin:0;padding:16px;max-width:none}details{display:none}h2{font-size:28px}p,table{font-size:18px}}
</style><header><h1>Kidney patient-journey prediction</h1><p>Self-contained interview backup. Fifteen main slides total 18 planned minutes, followed by two reference slides. Tables retain the chart values. Author walkthrough and timed rehearsal remain pending.</p><nav aria-label="Slides">${content.slides.map((d,i)=>`<a href="#slide-${i+1}">${i+1}</a>`).join('')}</nav></header>${sections}</html>`;
await fs.writeFile(path.join(delivery,'interview-backup.html'),html);
const fingerprint=async file=>({bytes:(await fs.stat(file)).size,sha256:createHash('sha256').update(await fs.readFile(file)).digest('hex')});
const inputPaths=['docs/presentation/v2-followup/slides.json','docs/presentation/v2-followup/build.mjs',
  'configs/data_sources.yaml','configs/patient_journey_v2/experiment.yaml','configs/patient_journey_v2/methodology.yaml',
  'configs/patient_journey_v2_followup/experiment.yaml','configs/patient_journey_v2_followup/outcome_components.yaml',
  'artifacts/patient_journey_v2/release_manifest.json','docs/patient_journey_v2_followup_results.md',
  'docs/patient_journey_v2_component_results.md','docs/presentation/v2-followup/program-case.md','uv.lock'];
const inputs={};
for(const name of inputPaths) inputs[name]=await fingerprint(path.join(root,name));
const outputs={};
for(const name of ['interview.pptx','interview-backup.html']) outputs[name]=await fingerprint(path.join(delivery,name));
const git=process.env.P4_GIT_EXECUTABLE||'git';
const provenance={package_version:content.package_version,kind:'presentation_documentation',build_timestamp_utc:new Date().toISOString(),
  git_commit:execFileSync(git,['-C',root,'rev-parse','HEAD'],{encoding:'utf8'}).trim(),
  git_worktree_dirty:execFileSync(git,['-C',root,'status','--porcelain'],{encoding:'utf8'}).trim().length>0,
  template:await fingerprint(PRESENTATION_TEMPLATE),template_slides:content.slides.map(s=>s.template_slide),font,
  runtime:{node:process.version,artifact_tool:'2.8.59',bundle:'26.905.11957'},inputs,outputs,
  original_bundle_sha256:'ce2844edbcec92c09d0053720d5331dd37ed43ab75de7aa4dd1de431c79a9eee',
  report_count_run:'c6cc2cea133e7e61e9e42ac284f170baef43d9989d3ab04eea543ffb47af1cfa',
  component_run:'e95ab9db56aad000f6a296c33fb4ad981a57b39f70ba2a6a0adb4b3fe388171b',
  model_fitting_performed:false,feature_schema:[],model_parameters:{},
  interpretation:'No new analytical release, model comparison, promotion or future forecast. Original configurations retain fitted-model parameters.',
  reproducibility:'HTML, displayed values and rendered slides reproduce. PPTX container metadata and generated object identifiers may vary.'};
await fs.writeFile(path.join(delivery,'package-provenance.json'),JSON.stringify(provenance,null,2)+'\n');
console.log(JSON.stringify({output,slides:content.slides.length,chartOwners,tableOwners}));
