#!/usr/bin/env node
// The talk's slides as a PowerPoint deck: artifacts/presentation/ghostmap-talk.pptx.
//
// Every number is read from the data the demo page reads (dist/assets/timemachine/scene.json) and the reports beside
// it, and every slide's speaker notes are that slide's section of docs/presentation/talk-track.md (English and
// Chinese), so the deck, the page and the script cannot disagree. The pictures are the tour's stills
// (dist/assets/presentation/, written by qa/record_tour.py).
//
// Usage: NODE_PATH=.cache/node/node_modules node pipeline/ghostmap/package/talk_deck.js [--output deck.pptx]
// (pptxgenjs is installed there with `npm install --prefix .cache/node pptxgenjs@3.12.0`.)
'use strict';
const fs = require('fs');
const path = require('path');
const pptxgen = require('pptxgenjs');

const ROOT = path.resolve(__dirname, '../../..');
const DIST = path.join(ROOT, 'dist');
const STILLS = path.join(DIST, 'assets/presentation');
const SCRIPT = path.join(ROOT, 'docs/presentation/talk-track.md');
const args = process.argv.slice(2);
const OUTPUT = args.includes('--output') ? path.resolve(args[args.indexOf('--output') + 1]) : path.join(ROOT, 'artifacts/presentation/ghostmap-talk.pptx');

// --- the data ------------------------------------------------------------------------------------------------------
const scene = JSON.parse(fs.readFileSync(path.join(DIST, 'assets/timemachine/scene.json'), 'utf8'));
const rec = scene.reconstructions[0], cert = rec.placement.certificate, study = scene.placement_study;
const own = scene.photographers.filter(p => p.reconstruction === rec.tag), years = own.filter(p => p.year).map(p => p.year);
const frag = study.fragments.find(f => f.run === rec.tag.slice(0, 8) && String(f.fragment) === rec.tag.split('-')[1]);
const campus = study.fragments.filter(f => f.run !== rec.tag.slice(0, 8));
const gates = campus.find(f => f.geotag_baseline);
const loo = rec.located.leave_one_out;
const hoPlaza = rec.located.photos.find(q => q.photo.includes('Ho_Plaza_w_Tower'));
const [plain, taught] = [rec.splats.find(s => !s.lidar_taught), rec.splats.find(s => s.lidar_taught)];
const heldOut = s => s.psnr.test.reduce((a, t) => a + t.psnr, 0) / s.psnr.test.length;
const ident = Object.fromEntries(study.identifiability.filter(r => r.cues === 'all cues' && r.roof_edge_error_m === 0).map(r => [r.facades, r]));
const cornerWrongEdge = study.identifiability.find(r => r.cues === 'all cues' && r.facades === 'two adjacent facades' && r.roof_edge_error_m > 0);
const mapillary = JSON.parse(fs.readFileSync(path.join(ROOT, 'artifacts/georegistration/new-photos-mapillary.json'), 'utf8'));

const fmt = (x, d = 0) => Number(x).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (x, d = 0) => fmt(100 * x, d) + ' %';
const km = m => m >= 1000 ? fmt(m / 1000, 1) + ' km' : fmt(m) + ' m';

// --- the speaker notes: each slide's section of the script ------------------------------------------------------
function notes() {
  const text = fs.readFileSync(SCRIPT, 'utf8'), out = {};
  const parts = text.split(/^### Slide (\d+) · .*$/m);
  for (let i = 1; i < parts.length; i += 2) {
    const body = parts[i + 1].split(/^## /m)[0];
    const field = label => { const m = body.match(new RegExp(`^\\*\\*${label}[^*]*:\\*\\*\\s*([\\s\\S]*?)(?=\\n\\n|$)`, 'm')); return m ? m[1].replace(/\s*\n\s*/g, ' ').replace(/\*\*|`/g, '').trim() : ''; };
    const show = field('Show'), say = field('Say'), jiang = field('讲'), next = field('Transition');
    out[+parts[i]] = [show && 'SHOW / 操作: ' + show, say && 'EN: ' + say, jiang && '中文: ' + jiang, next && 'NEXT / 过渡: ' + next].filter(Boolean).join('\n\n');
  }
  return out;
}
const NOTES = notes();

// --- picture sizes (PNG and JPEG headers), so every picture keeps its own shape ----------------------------------
function imageSize(file) {
  const b = fs.readFileSync(file);
  if (b.readUInt32BE(0) === 0x89504e47) return [b.readUInt32BE(16), b.readUInt32BE(20)];
  for (let i = 2; i < b.length;) {   // JPEG: walk the markers to the frame header
    const marker = b[i + 1], len = b.readUInt16BE(i + 2);
    if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) return [b.readUInt16BE(i + 7), b.readUInt16BE(i + 5)];
    i += 2 + len;
  }
  throw new Error('unknown image format: ' + file);
}

// --- the theme -----------------------------------------------------------------------------------------------------
const HEX = { ink: '1B2329', white: 'FFFFFF', slate: '33414A', mist: 'EEF1F0', terra: 'B5532C', green: '2F7D4F', red: 'B4372F', amber: 'B07A10', grey: '7C8790', light: 'E8A07E' };
const THEME = { name: 'GhostMap', headFontFace: 'Cambria', bodyFontFace: 'Calibri',
  colors: { dk1: HEX.ink, lt1: HEX.white, dk2: HEX.slate, lt2: HEX.mist, accent1: HEX.terra, accent2: HEX.green, accent3: HEX.red, accent4: HEX.amber, accent5: HEX.grey, accent6: HEX.light, hlink: HEX.terra, folHlink: '7A3A20' } };

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';   // 13.333 x 7.5 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = 'GhostMap'; pres.subject = 'Putting COLMAP reconstructions into the real world, without GPS'; pres.author = 'GhostMap, CS 6672';
const C = pres.SchemeColor;
const INK = C.text1, WHITE = C.background1, SLATE = C.text2, MIST = C.background2, TERRA = C.accent1, GREEN = C.accent2, RED = C.accent3, AMBER = C.accent4, GREY = C.accent5, LIGHT = C.accent6;
const X0 = 0.6, W = 12.13;   // content margins

pres.defineSlideMaster({ title: 'DARK', background: { color: INK },
  objects: [{ placeholder: { options: { name: 'title', type: 'title', x: 0.7, y: 0.8, w: 6.2, h: 2.7, fontFace: THEME.headFontFace, fontSize: 48, bold: true, color: WHITE, valign: 'bottom', margin: 0 }, text: '' } }] });
pres.defineSlideMaster({ title: 'DARK_CLOSE', background: { color: INK },
  objects: [{ placeholder: { options: { name: 'title', type: 'title', x: 0.7, y: 0.9, w: 6.2, h: 2.5, fontFace: THEME.headFontFace, fontSize: 40, bold: true, color: WHITE, valign: 'bottom', margin: 0 }, text: '' } }] });
pres.defineSlideMaster({ title: 'CONTENT', background: { color: WHITE },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: X0, y: 0.32, w: W, h: 0.8, fontFace: THEME.headFontFace, fontSize: 32, bold: true, color: INK, valign: 'middle', margin: 0 }, text: '' } },
    { text: { text: 'GhostMap · CS 6672      map data © OpenStreetMap contributors · lidar USGS 3DEP · aerial imagery NYS GIS Program Office', options: { x: X0, y: 7.02, w: 10.5, h: 0.3, fontSize: 10, color: GREY, margin: 0 } } }],
  slideNumber: { x: 12.23, y: 7.02, w: 0.5, h: 0.3, fontSize: 10, color: GREY, align: 'right' } });

// --- building blocks -----------------------------------------------------------------------------------------------
const glue = t => typeof t === 'string' ? t.replace(/(\d) (?=(m|km|%|dB|s)\b)/g, '$1\u00a0') : t;   // a number never wraps away from its unit
const text = (s, t, o) => s.addText(glue(t), Object.assign({ isTextBox: true, margin: 0, fontSize: 16, color: INK, valign: 'top' }, o));
function picture(s, file, x, y, w, h, name, align = 'center') {   // fit inside the box, keep the shape
  const [iw, ih] = imageSize(file), k = Math.min(w / iw, h / ih), pw = iw * k, ph = ih * k;
  const px = align === 'left' ? x : align === 'right' ? x + w - pw : x + (w - pw) / 2;
  s.addImage({ path: file, x: px, y, w: pw, h: ph, altText: name, objectName: name });
  return { x: px, y, w: pw, h: ph };
}
const caption = (s, t, x, y, w, h = 0.5) => text(s, t, { x, y, w, h, fontSize: 11, color: GREY });
// The motif: COLMAP leaves seven numbers free; a row of seven dots says which a cue or a certificate fixes.
const DOF = ['tilt', 'tilt', 'heading', 'scale', 'east', 'north', 'height'];
function dots(s, x, y, states, { d = 0.32, step = 0.6, labels = false, labelColor = GREY, name = 'dofs' } = {}) {
  states.forEach((st, i) => {
    const fill = st === 'fixed' ? TERRA : st === 'ok' ? GREEN : null, line = st === 'free' ? RED : st === 'unknown' ? GREY : fill;
    s.addShape(pres.ShapeType.ellipse, { x: x + i * step, y, w: d, h: d, fill: fill ? { color: fill } : { color: WHITE, transparency: 100 }, line: { color: line, width: 1.5 }, objectName: `${name} ${DOF[i]}` });
    if (labels) text(s, DOF[i], { x: x + i * step - (step - d) / 2, y: y + d + 0.05, w: step, h: 0.25, fontSize: 10, color: labelColor, align: 'center' });
  });
}
const card = (s, x, y, w, h, name) => s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.08, fill: { color: MIST }, line: { color: MIST, width: 0 }, objectName: name });
function stat(s, big, label, x, y, w, { size = 30, color = TERRA, labelSize = 14 } = {}) {
  text(s, big, { x, y, w, h: size / 72 + 0.1, fontSize: size, bold: true, color, fontFace: THEME.headFontFace });
  text(s, label, { x, y: y + size / 72 + 0.12, w, h: 0.62, fontSize: labelSize, color: SLATE });
}
const arrow = (s, x1, y1, x2, y2, name) => s.addShape(pres.ShapeType.line, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001, line: { color: GREY, width: 1.5, endArrowType: 'triangle' }, flipH: x2 < x1, flipV: y2 < y1, objectName: name });
const still = name => path.join(STILLS, name);
const credit = q => `Photograph: ${q.artist.replace(/<[^>]+>/g, '')}, ${q.license} (${q.source_url.includes('flickr') ? 'Flickr' : 'Wikimedia Commons'})`;
let number = 0, section = null;
function slide(master, newSection, title) {   // every slide carries its section, or it lands in a stray default one
  number += 1; if (newSection) { pres.addSection({ title: newSection }); section = newSection; }
  const s = pres.addSlide({ masterName: master, sectionTitle: section });
  if (title) s.addText(title, { placeholder: 'title' });
  if (NOTES[number]) s.addNotes(NOTES[number]);
  return s;
}

// --- 1 · title -----------------------------------------------------------------------------------------------------
{ const s = slide('DARK', 'Opening', 'GhostMap');
  text(s, 'CS 6672 · COLMAP HACKER PROJECT', { x: 0.7, y: 2.15, w: 6.2, h: 0.4, fontSize: 14, bold: true, color: LIGHT, charSpacing: 2 });
  text(s, 'Putting COLMAP reconstructions into the real world, without GPS', { x: 0.7, y: 3.6, w: 5.7, h: 1.2, fontSize: 24, color: WHITE });
  text(s, 'Public data only: USGS 3DEP lidar · OpenStreetMap footprints · New York State aerial imagery · licensed photographs from Wikimedia Commons and Flickr', { x: 0.7, y: 5.55, w: 5.6, h: 0.8, fontSize: 12, color: 'A4ADB3' });
  const r = picture(s, still('photo-stand.png'), 7.15, 1.55, 5.5, 4.4, 'A photograph painted onto the lidar city from where its photographer stood');
  caption(s, 'A photograph painted onto the lidar model of Cornell from where it was taken. ' + credit(hoPlaza) + '.', r.x, r.y + r.h + 0.12, r.w, 0.55); }

// --- 2 · the hook ----------------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Where was this photograph taken?');
  const r = picture(s, path.join(DIST, 'assets/timemachine', hoPlaza.photo), X0, 1.4, 6.9, 4.95, 'A photograph of McGraw Tower from Ho Plaza', 'left');
  caption(s, `${credit(hoPlaza)}. Taken out of the reconstruction first, then placed again from scratch.`, r.x, r.y + r.h + 0.1, r.w);
  ['No GPS.', 'No EXIF.', 'Only the pixels.'].forEach((t, i) => text(s, t, { x: 8.0, y: 1.6 + 0.75 * i, w: 4.7, h: 0.7, fontSize: 36, bold: true, fontFace: THEME.headFontFace, color: i === 2 ? TERRA : INK }));
  s.addShape(pres.ShapeType.roundRect, { x: 8.0, y: 4.1, w: 3.3, h: 0.55, rectRadius: 0.1, fill: { color: TERRA }, line: { color: TERRA, width: 0 }, objectName: 'demo cue' });
  text(s, 'live demo · chapter 11', { x: 8.0, y: 4.1, w: 3.3, h: 0.55, fontSize: 16, bold: true, color: WHITE, align: 'center', valign: 'middle' });
  text(s, 'Placed in 1–2 s on a laptop GPU, then painted back onto a 3D model of the campus from where the photographer stood.', { x: 8.0, y: 4.9, w: 4.7, h: 1.2, fontSize: 16, color: SLATE }); }

// --- 3 · what COLMAP gives ----------------------------------------------------------------------------------------
{ const s = slide('CONTENT', 'The problem', 'COLMAP gives a model in its own frame');
  const r = picture(s, still('void.png'), X0, 1.4, 7.3, 4.6, 'The reconstruction floating in COLMAP\'s own frame', 'left');
  caption(s, 'COLMAP\'s cameras (blue) and points, at their native size and orientation (live demo, chapter 1).', r.x, r.y + r.h + 0.1, r.w);
  stat(s, fmt(own.length), 'licensed photographs of McGraw Tower and Uris Library', 8.35, 1.45, 4.3);
  stat(s, fmt(rec.points), '3D points (SuperPoint, LightGlue, pycolmap incremental mapping)', 8.35, 2.6, 4.3);
  stat(s, fmt(new Set(own.map(p => p.artist)).size), `photographers; the dated photographs span ${Math.min(...years)}–${Math.max(...years)}`, 8.35, 3.75, 4.3);
  dots(s, 8.4, 5.05, DOF.map(() => 'unknown'), { labels: true, step: 0.6 });
  text(s, 'seven numbers COLMAP leaves free: 1 scale, 3 rotations, 3 translations', { x: 8.35, y: 5.75, w: 4.3, h: 0.6, fontSize: 14, bold: true, color: INK }); }

// --- 4 · why not GPS -------------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Why not just use GPS?');
  const g = frag.geotags, cards = [
    [fmt(g.carried), `GPS tag among ${fmt(own.length)} photographs`, `and it is ${g.wrong_off_m.map(km).join(', ')} off: it points to downtown Ithaca`],
    [fmt(g.without_metadata), `of the ${fmt(own.length)} are Flickr web copies`, 'downloaded without any metadata at all, so their GPS is unknown'],
    ['≈' + fmt(gates.geotag_baseline.leave_one_out_error_m.median) + ' m', 'GPS fit error at Gates Hall', `the one fragment with ${gates.geotags.plausible} tags: where it puts a held-out camera`]];
  cards.forEach(([big, label, detail], i) => {
    const x = X0 + i * (3.83 + 0.32); card(s, x, 1.45, 3.83, 3.35, 'gps card ' + (i + 1));
    text(s, big, { x: x + 0.3, y: 1.7, w: 3.3, h: 1.0, fontSize: 54, bold: true, color: TERRA, fontFace: THEME.headFontFace });
    text(s, label, { x: x + 0.3, y: 2.8, w: 3.3, h: 0.7, fontSize: 18, bold: true, color: INK });
    text(s, detail, { x: x + 0.3, y: 3.55, w: 3.3, h: 1.1, fontSize: 14, color: SLATE });
  });
  text(s, `COLMAP's model aligner needs known camera positions: at least three good, well-spread ones per fragment. Across the collection, ${fmt(study.geotags.with_gps)} of ${fmt(study.geotags.photographs)} Commons photographs do carry GPS, just not where it matters, and a wrong tag never announces itself.`, { x: X0, y: 5.15, w: W, h: 1.2, fontSize: 18, color: INK }); }

// --- 5 · the idea ----------------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'The world already has a 3D model');
  const r = picture(s, still('above.png'), 6.1, 1.4, 6.63, 4.25, 'The campus: lidar terrain and buildings draped with an aerial photograph', 'right');
  caption(s, 'Cornell from USGS lidar, OpenStreetMap footprints and the 2023 New York State flight (live demo, chapter 6).', r.x, r.y + r.h + 0.1, r.w);
  [['USGS 3DEP airborne lidar', 'public domain, in metres, most of the US'], ['OpenStreetMap footprints', 'every building\'s outline, raised to its lidar roof'], ['New York State aerial imagery', 'six flights, 2002 to 2023, draped on the terrain']].forEach(([h, d], i) => {
    const y = 1.5 + i * 0.95; s.addShape(pres.ShapeType.ellipse, { x: X0, y: y + 0.07, w: 0.26, h: 0.26, fill: { color: TERRA }, line: { color: TERRA, width: 0 }, objectName: 'source ' + (i + 1) });
    text(s, h, { x: X0 + 0.45, y, w: 4.8, h: 0.4, fontSize: 18, bold: true });
    text(s, d, { x: X0 + 0.45, y: y + 0.4, w: 4.8, h: 0.45, fontSize: 14, color: SLATE });
  });
  card(s, X0, 4.45, 5.2, 1.85, 'the question');
  text(s, 'Can public measurements fix COLMAP\'s seven free numbers instead of GPS, and say so when they can\'t?', { x: X0 + 0.3, y: 4.65, w: 4.6, h: 1.5, fontSize: 20, bold: true, color: INK, fontFace: THEME.headFontFace }); }

// --- 6 · where it plugs into COLMAP ----------------------------------------------------------------------------------
{ const s = slide('CONTENT', 'The method', 'Where it plugs into COLMAP');
  const cw = 2.2, gap = (W - 5 * cw) / 4, colX = i => X0 + i * (cw + gap);
  [[GREY, 'COLMAP / pycolmap'], [TERRA, 'added in GhostMap']].forEach(([c, t], i) => {
    s.addShape(pres.ShapeType.roundRect, { x: X0 + i * 2.9, y: 1.35, w: 0.3, h: 0.3, rectRadius: 0.05, fill: { color: c }, line: { color: c, width: 0 }, objectName: 'legend ' + t });
    text(s, t, { x: X0 + 0.42 + i * 2.9, y: 1.33, w: 2.4, h: 0.35, fontSize: 14, color: SLATE }); });
  const colmap = [['Features + matches', 'hloc: SuperPoint, LightGlue, NetVLAD pairs'], ['Incremental mapping', 'pycolmap\'s incremental_mapping'], ['Align to the world', 'model_aligner: needs GPS or known camera positions'],
    ['Register a new image', 'absolute pose (RANSAC), into COLMAP\'s own frame'], ['Undistort', 'undistort_images, for dense models and splats']];
  colmap.forEach(([h, d], i) => {
    s.addShape(pres.ShapeType.roundRect, { x: colX(i), y: 1.95, w: cw, h: 1.45, rectRadius: 0.08, fill: { color: MIST }, line: { color: GREY, width: 1 }, objectName: 'colmap step ' + (i + 1) });
    text(s, h, { x: colX(i) + 0.15, y: 2.05, w: cw - 0.3, h: 0.5, fontSize: 15, bold: true });
    text(s, d, { x: colX(i) + 0.15, y: 2.55, w: cw - 0.3, h: 0.8, fontSize: 12, color: SLATE });
    if (i < 4) arrow(s, colX(i) + cw + 0.02, 2.675, colX(i + 1) - 0.02, 2.675, 'flow ' + (i + 1));
  });
  const ours = [['Cue-based similarity + certificate', 'public lidar and footprints, no GPS; applied with transform(Sim3d)'], ['Register into the world', `${fmt(loo.placed)} of ${fmt(loo.with_a_plausible_reference_pose)} placed, median ${fmt(loo.placed_position_error_m.median, 1)} m; three verdicts`], ['Splats checked and taught by the lidar', 'every Gaussian scored against measured free space']];
  ours.forEach(([h, d], k) => {
    const i = k + 2; arrow(s, colX(i) + cw / 2, 3.45, colX(i) + cw / 2, 3.95, 'replaces ' + (i + 1));
    s.addShape(pres.ShapeType.roundRect, { x: colX(i), y: 4.0, w: cw, h: 1.85, rectRadius: 0.08, fill: { color: TERRA }, line: { color: TERRA, width: 0 }, objectName: 'ghostmap step ' + (k + 1) });
    text(s, h, { x: colX(i) + 0.15, y: 4.1, w: cw - 0.3, h: 0.75, fontSize: 15, bold: true, color: WHITE });
    text(s, d, { x: colX(i) + 0.15, y: 4.85, w: cw - 0.3, h: 0.95, fontSize: 12, color: WHITE });
  });
  text(s, 'COLMAP does these as they are', { x: X0, y: 4.4, w: 2 * cw + gap, h: 0.4, fontSize: 14, italic: true, color: GREY, align: 'center' });
  text(s, 'Everything after mapping now lives in metres on the real campus.', { x: X0, y: 6.2, w: W, h: 0.5, fontSize: 18, italic: true, color: INK }); }

// --- 7 · cues and the seven numbers ----------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Each cue fixes some of the seven numbers');
  const dx = 8.25, step = 0.62;
  DOF.forEach((d, i) => text(s, d, { x: dx + i * step - 0.15, y: 1.35, w: step, h: 0.3, fontSize: 11, bold: true, color: SLATE, align: 'center' }));
  const F = 'fixed', U = 'unknown', rows = [
    ['Facade normals', 'walls are vertical', [F, F, U, U, U, U, U]],
    ['Photographers\' heights', 'people stand at eye height on the lidar ground', [F, F, U, U, U, U, F]],
    ['OpenStreetMap walls', 'points sit on the footprint walls', [U, U, F, U, F, F, U]],
    ['Lidar roof edges', 'a facade\'s top meets its lidar roof', [U, U, U, F, U, U, U]],
    ['Parallel walls', 'their spacing is known in metres', [U, U, U, F, U, U, U]],
    ['McGraw Tower top', 'the tower\'s top and axis in the lidar', [U, U, U, F, F, F, U]],
    ['Free space', 'no line of sight passes through a building', [U, U, U, U, U, U, U]]];
  rows.forEach(([cue, what, st], i) => {
    const y = 1.8 + i * 0.66;
    if (i % 2 === 0) s.addShape(pres.ShapeType.rect, { x: X0, y: y - 0.08, w: W, h: 0.66, fill: { color: MIST }, line: { color: MIST, width: 0 }, objectName: 'row band ' + (i + 1) });
    text(s, cue, { x: X0 + 0.15, y, w: 3.4, h: 0.5, fontSize: 16, bold: true, valign: 'middle' });
    text(s, what, { x: 4.15, y, w: 3.95, h: 0.5, fontSize: 14, color: SLATE, valign: 'middle' });
    dots(s, dx, y + 0.09, st, { d: 0.32, step, name: cue });
  });
  caption(s, 'Filled: the cue fixes that number. Free space fixes none on its own; it rules out placements that put a camera\'s line of sight through a building.', X0, 6.45, W, 0.45); }

// --- 8 · it lands, with a certificate --------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'It lands, with a certificate');
  const r = picture(s, still('snap.png'), X0, 1.4, 7.4, 4.75, 'The fragment placed in the lidar campus', 'left');
  caption(s, 'The same COLMAP cameras and points, placed in metres among the lidar buildings (live demo, chapter 2).', r.x, r.y + r.h + 0.1, r.w);
  s.addShape(pres.ShapeType.roundRect, { x: 8.4, y: 1.45, w: 3.4, h: 0.5, rectRadius: 0.1, fill: { color: GREEN }, line: { color: GREEN, width: 0 }, objectName: 'verdict' });
  text(s, 'certificate: ' + cert.verdict, { x: 8.4, y: 1.45, w: 3.4, h: 0.5, fontSize: 18, bold: true, color: WHITE, align: 'center', valign: 'middle' });
  const rows = [['±' + pct(cert.scale_uncertainty_relative, 1), `scale, fixed ${cert.scale_fixed_by.length} independent ways: tower top, parallel walls, roof edges`],
    [pct(cert.yaw_contrast.runner_up_outside_20deg), 'the best other heading\'s score against the winner'],
    [fmt(cert.levelling_correction_deg, 1) + '°', 'vertical levelled by the photographers\' heights'],
    [pct(rec.placement.sparse_points_free_space.surface), 'of COLMAP\'s points within 2.5 m of a lidar surface']];
  rows.forEach(([big, label], i) => {
    const y = 2.2 + i * 0.95; text(s, big, { x: 8.4, y, w: 1.7, h: 0.6, fontSize: 26, bold: true, color: TERRA, fontFace: THEME.headFontFace, valign: 'middle' });
    text(s, label, { x: 10.15, y, w: 2.55, h: 0.85, fontSize: 14, color: SLATE, valign: 'middle' }); });
  dots(s, 8.45, 6.0, DOF.map(() => 'ok'), { d: 0.3, step: 0.52, name: 'all fixed' });
  text(s, 'all seven fixed', { x: 8.45, y: 6.4, w: 4.2, h: 0.35, fontSize: 14, bold: true, color: GREEN }); }

// --- 9 · knowing when it can't ---------------------------------------------------------------------------------------
{ const s = slide('CONTENT', 'When it can\'t', 'Knowing when it can\'t');
  const cr = study.campus_run, hd = o => ({ text: o, options: { bold: true, color: INK, fill: { color: MIST } } });
  const rows = [[hd('Fragment (named by its photographs)'), hd('Photos'), hd('Certificate'), hd('Checked by GPS')]].concat(campus.map(f => [
    f.building.replace('Bill and Melinda ', ''), { text: fmt(f.cameras), options: { align: 'right' } }, { text: 'refused: ' + f.failure_mode, options: { color: RED } },
    f.ours_vs_geotags_m ? { text: km(f.ours_vs_geotags_m.median) + ' off', options: { bold: true } } : { text: 'no usable GPS', options: { color: GREY } }]));
  s.addTable(rows, { x: X0, y: 1.45, w: 8.6, colW: [2.55, 1.25, 3.3, 1.5], fontSize: 14, color: SLATE, valign: 'middle', rowH: 0.44, border: { type: 'solid', pt: 0.75, color: 'D6DBDA' }, margin: [0.04, 0.1, 0.04, 0.1], objectName: 'campus fragments' });
  caption(s, `The whole campus collection reconstructed at once: ${fmt(cr.photographs)} photographs, ${fmt(cr.fragments)} fragments; the ${campus.length} with eight or more cameras are listed.`, X0, 6.05, 8.6);
  const checked = campus.filter(f => f.ours_vs_geotags_m), offs = checked.map(f => f.ours_vs_geotags_m.median);
  card(s, 9.6, 1.45, 3.13, 4.2, 'callout');
  text(s, `${checked.length} of ${checked.length}`, { x: 9.85, y: 1.7, w: 2.7, h: 1.0, fontSize: 54, bold: true, color: TERRA, fontFace: THEME.headFontFace });
  text(s, `placements GPS could check were ${km(Math.min(...offs))} to ${km(Math.max(...offs))} off, and all were refused`, { x: 9.85, y: 2.75, w: 2.7, h: 1.3, fontSize: 16, color: INK });
  text(s, 'none certified and then found wrong', { x: 9.85, y: 4.4, w: 2.7, h: 0.9, fontSize: 16, bold: true, color: GREEN }); }

// --- 10 · geometry decides -------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Geometry decides');
  const pw = 2.8, gap = (W - 4 * pw) / 3, OK = 'ok', FR = 'free';
  const cases = [
    ['one facade', 'One facade', 'scale undetermined', RED, [OK, OK, OK, FR, OK, OK, OK]],
    ['two parallel facades', 'Two parallel facades', 'position undetermined', RED, [OK, OK, OK, OK, FR, OK, OK]],
    ['two adjacent facades', 'A corner', 'usable', GREEN, DOF.map(() => OK)],
    ['three facades', 'Three facades', 'usable', GREEN, DOF.map(() => OK)]];
  cases.forEach(([key, name, verdict, vc, st], i) => {
    const px = X0 + i * (pw + gap), py = 1.45, r = ident[key];
    card(s, px, py, pw, 2.2, 'plan ' + name);
    const wall = (x1, y1, x2, y2) => s.addShape(pres.ShapeType.line, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001, line: { color: TERRA, width: 5 }, objectName: 'seen facade' });
    const block = (x, y, w, h) => s.addShape(pres.ShapeType.rect, { x, y, w, h, fill: { color: 'C9CFCD' }, line: { color: 'C9CFCD', width: 0 }, objectName: 'building' });
    const cams = pts => pts.forEach(([x, y]) => s.addShape(pres.ShapeType.ellipse, { x: x - 0.06, y: y - 0.06, w: 0.12, h: 0.12, fill: { color: INK }, line: { color: INK, width: 0 }, objectName: 'camera' }));
    const bx = px + 0.7, by = py + 0.4, bw = 1.4, bh = 0.85;
    if (key === 'two parallel facades') {
      block(bx - 0.25, py + 0.25, bw + 0.5, 0.45); block(bx - 0.25, py + 1.5, bw + 0.5, 0.45);
      wall(bx - 0.25, py + 0.7, bx + bw + 0.25, py + 0.7); wall(bx - 0.25, py + 1.5, bx + bw + 0.25, py + 1.5);
      cams([[bx + 0.2, py + 1.1], [bx + 0.7, py + 1.1], [bx + 1.2, py + 1.1]]);
      s.addShape(pres.ShapeType.line, { x: px + 0.25, y: py + 1.1, w: 0.35, h: 0.001, line: { color: RED, width: 1.5, beginArrowType: 'triangle', endArrowType: 'triangle' }, objectName: 'slides along' });
    } else {
      block(bx, by, bw, bh); wall(bx, by + bh, bx + bw, by + bh);
      if (key !== 'one facade') wall(bx + bw, by, bx + bw, by + bh);
      if (key === 'three facades') wall(bx, by, bx, by + bh);
      cams(key === 'one facade' ? [[bx + 0.3, py + 1.75], [bx + 0.7, py + 1.85], [bx + 1.1, py + 1.75]] : key === 'two adjacent facades' ? [[bx + 0.5, py + 1.8], [bx + bw + 0.4, py + 1.75], [bx + bw + 0.45, py + 0.75]] : [[bx - 0.4, py + 0.8], [bx + 0.7, py + 1.85], [bx + bw + 0.4, py + 0.8]]);
    }
    text(s, name, { x: px, y: 3.8, w: pw, h: 0.4, fontSize: 16, bold: true });
    dots(s, px, 4.3, st, { d: 0.26, step: 0.38, name });
    text(s, verdict, { x: px, y: 4.75, w: pw, h: 0.4, fontSize: 15, bold: true, color: vc });
    text(s, `scale ×${fmt(r.scale_ratio, 3)}\nheading ${fmt(r.yaw_error_deg, r.yaw_error_deg < 1 ? 2 : 1)}° off`, { x: px, y: 5.15, w: pw, h: 0.7, fontSize: 14, color: SLATE });
  });
  caption(s, 'A synthetic hall with a known answer, seen from above; cameras in black, the facades they see in colour. Exact lidar roof edges, every cue on. Dots: tilt · tilt · heading · scale · east · north · height; red outline = not fixed.', X0, 6.0, W, 0.6); }

// --- 11 · a new photograph -------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', 'A new photograph', 'A photograph it has never seen');
  const cw = (W - 3 * 0.22) / 4;
  [['1 · Retrieve', `NetVLAD: the most similar of the ${fmt(own.length)}`], ['2 · Match', 'SuperPoint + LightGlue'], ['3 · Solve the pose', 'pycolmap RANSAC from four focal-length guesses'], ['4 · Certificate', 'placed · distance open · refused']].forEach(([h, d], i) => {
    const x = X0 + i * (cw + 0.22); card(s, x, 1.35, cw, 0.95, 'step ' + (i + 1));
    text(s, h, { x: x + 0.18, y: 1.43, w: cw - 0.36, h: 0.4, fontSize: 16, bold: true, color: TERRA });
    text(s, d, { x: x + 0.18, y: 1.83, w: cw - 0.36, h: 0.42, fontSize: 13, color: SLATE }); });
  const iw = (W - 0.25) / 2;
  const a = picture(s, still('photo-stand.png'), X0, 2.55, iw, 3.75, 'The photograph painted onto the lidar city from where it was placed', 'left');
  const b = picture(s, still('photo-city.png'), X0 + iw + 0.25, 2.55, iw, 3.75, 'The same spot without the photograph', 'left');
  caption(s, 'From where it was placed: the photograph painted onto the lidar city (inside the white frame).', a.x, a.y + a.h + 0.08, a.w, 0.4);
  caption(s, `The same spot, the bare lidar city: the tower is where the photograph says. ${credit(hoPlaza)}.`, b.x, b.y + b.h + 0.08, b.w, 0.4); }

// --- 12 · leave-one-out ----------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Tested by taking each photograph out');
  s.addChart(pres.ChartType.bar, [{ name: 'photographs', labels: ['placed', 'distance open', 'refused'], values: [loo.placed, loo.placed_distance_uncertain, loo.refused] }], {
    x: X0, y: 1.45, w: 6.6, h: 3.7, barDir: 'bar', catAxisOrientation: 'maxMin', chartColors: [HEX.green, HEX.amber, HEX.red], barGapWidthPct: 45,
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 16, dataLabelFontBold: true, dataLabelColor: HEX.ink, dataLabelFontFace: '+mn-lt',
    catAxisLabelColor: HEX.slate, catAxisLabelFontSize: 14, catAxisLabelFontFace: '+mn-lt', catAxisLineShow: false, valAxisHidden: true, valGridLine: { style: 'none' }, catGridLine: { style: 'none' },
    showLegend: false, showTitle: true, title: `${fmt(loo.with_a_plausible_reference_pose)} photographs with a trustworthy reference pose`, titleFontSize: 14, titleColor: HEX.slate, titleFontFace: '+mn-lt', objectName: 'leave-one-out verdicts' });
  caption(s, `Each of the ${fmt(loo.photographs)} photographs taken out of the reconstruction and placed again from scratch, scored where COLMAP's own pose of it is trustworthy.`, X0, 5.3, 6.6, 0.55);
  const e = loo.placed_position_error_m, rows = [
    [fmt(e.median, 1) + ' m', `median error of the ${loo.placed} placed (90th percentile ${fmt(e.p90, 1)} m, worst ${fmt(e.max)} m)`],
    [fmt(loo.distance_uncertain_truth_to_segment_m.median, 1) + ' m', `median distance of the true spot from the stated line, for the ${loo.placed_distance_uncertain} with the distance open`],
    ['≈' + fmt(Math.round(loo.refused_position_error_m_median / 5) * 5) + ' m', `how far off the ${loo.refused} refused would have been`],
    [`${mapillary.rows.length} / ${mapillary.rows.length}`, 'street photographs from the Arts Quad side refused: nobody online photographed the tower from there']];
  rows.forEach(([big, label], i) => {
    const y = 1.5 + i * 1.12; text(s, big, { x: 7.6, y, w: 2.1, h: 0.6, fontSize: 26, bold: true, color: TERRA, fontFace: THEME.headFontFace, valign: 'middle' });
    text(s, label, { x: 9.8, y, w: 2.93, h: 1.0, fontSize: 14, color: SLATE, valign: 'middle' }); }); }

// --- 13 · what a world frame buys ------------------------------------------------------------------------------------
{ const s = slide('CONTENT', 'What it buys, what it can\'t', 'What a world frame buys you');
  text(s, 'The lidar as referee and teacher', { x: X0, y: 1.35, w: 6.0, h: 0.4, fontSize: 18, bold: true, color: TERRA });
  const a = picture(s, still('verdict-plain-vs-lidar-taught.jpg'), X0, 1.85, 6.0, 2.3, 'Plain and lidar-taught splats from a new viewpoint, painted by the lidar\'s verdict', 'left');
  caption(s, 'A view no photographer took; every Gaussian painted by the lidar: red in measured-empty air, purple underground. Plain splat left, lidar-taught right.', X0, a.y + a.h + 0.08, 6.0, 0.55);
  const f = (o, k) => o.free_space[k];
  [[`${pct(f(plain, 'buried'))} → ${pct(f(taught, 'buried'))}`, 'of Gaussians under the bare ground'], [`${pct(f(plain, 'on_surfaces'))} → ${pct(f(taught, 'on_surfaces'))}`, 'on lidar surfaces'], [`${fmt(heldOut(plain), 1)} → ${fmt(heldOut(taught), 1)}`, 'dB on held-out photos: no worse']].forEach(([big, label], i) =>
    stat(s, big, label, X0 + i * 2.05, 4.95, 1.95, { size: 17, labelSize: 13 }));
  text(s, 'Time, for free', { x: 6.95, y: 1.35, w: 5.78, h: 0.4, fontSize: 18, bold: true, color: TERRA });
  const b = picture(s, still('gates.png'), 6.95, 1.85, 5.78, 3.65, 'Gates Hall in the time machine', 'left');
  caption(s, `Gates Hall in the 2016 flight: a parking lot until 2012. ${scene.years.length} aerial flights, ${scene.years[0]}–${scene.years.at(-1)}, on the same terrain (live demo, chapter 7).`, b.x, b.y + b.h + 0.08, b.w, 0.55); }

// --- 14 · limits -----------------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'What it can\'t do yet');
  const items = [
    [`One of ${study.fragments.length} fragments certified`, 'and it has no independent ground truth yet: phone photographs with GPS are the next check.'],
    ['A wrong roof edge can pass', `a synthetic corner with a ${fmt(cornerWrongEdge.roof_edge_error_m)} m roof-edge error is certified ${cornerWrongEdge.verdict} with the scale ${pct(Math.abs(cornerWrongEdge.scale_ratio - 1))} off.`],
    ['The Arts Quad side is blind', `all ${mapillary.rows.length} street photographs from there are refused: no licensed photograph online was taken from that side.`],
    ['The splats are still blurry', `about ${fmt(heldOut(taught), 1)} dB on held-out photographs; the far side of the tower was never photographed.`]];
  items.forEach(([h, d], i) => {
    const x = X0 + (i % 2) * 6.215, y = 1.45 + Math.floor(i / 2) * 2.55; card(s, x, y, 5.915, 2.25, 'limit ' + (i + 1));
    s.addShape(pres.ShapeType.ellipse, { x: x + 0.3, y: y + 0.32, w: 0.55, h: 0.55, fill: { color: TERRA }, line: { color: TERRA, width: 0 }, objectName: 'number ' + (i + 1) });
    text(s, String(i + 1), { x: x + 0.3, y: y + 0.32, w: 0.55, h: 0.55, fontSize: 18, bold: true, color: WHITE, align: 'center', valign: 'middle' });
    text(s, h, { x: x + 1.1, y: y + 0.32, w: 4.55, h: 0.55, fontSize: 18, bold: true, valign: 'middle' });
    text(s, d, { x: x + 1.1, y: y + 1.0, w: 4.55, h: 1.1, fontSize: 16, color: SLATE }); }); }

// --- 15 · related work -----------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'What is new here');
  const hd = o => ({ text: o, options: { bold: true, color: INK, fill: { color: MIST } } });
  const rows = [[hd('Work'), hd('What it does'), hd('What GhostMap adds')],
    ['Kaminsky, Snavely, Seitz, Szeliski · CVPR Workshops 2009', 'aligns a reconstruction to an overhead image: points on its edges, free space', 'lidar heights, explicit metric cues, a certificate per degree of freedom'],
    ['Wang, Wilson, Snavely · 3DV 2013', 'georegistration from Flickr geotags and Google Earth models', 'no geotags; public lidar and OpenStreetMap only'],
    ['Sarlin et al., OrienterNet · CVPR 2023', 'one photograph onto OpenStreetMap, learned, three degrees of freedom', 'whole fragments, seven degrees of freedom, scale from the world'],
    ['Kinoshita, Nishino · ECCV 2024', 'constant camera height as metric supervision for depth', 'the same principle as a placement cue']];
  s.addTable(rows, { x: X0, y: 1.45, w: W, colW: [3.7, 4.2, 4.23], fontSize: 14, color: SLATE, valign: 'middle', rowH: 0.75, border: { type: 'solid', pt: 0.75, color: 'D6DBDA' }, margin: [0.06, 0.12, 0.06, 0.12], objectName: 'related work' });
  text(s, 'Public data only, reproducible wherever USGS 3DEP lidar and OpenStreetMap exist: github.com/BobbyZbp/CS-6672', { x: X0, y: 5.6, w: W, h: 0.8, fontSize: 16, color: INK }); }

// --- 16 · closing ----------------------------------------------------------------------------------------------------
{ const s = slide('DARK_CLOSE', 'Close', 'COLMAP\'s frame is arbitrary. The world\'s isn\'t.');
  ['Placed with public lidar and footprints, no GPS', 'Refused, with the reason, when geometry can\'t fix it', 'New photographs placed in seconds'].forEach((t, i) => {
    s.addShape(pres.ShapeType.ellipse, { x: 0.72, y: 3.83 + i * 0.55, w: 0.2, h: 0.2, fill: { color: LIGHT }, line: { color: LIGHT, width: 0 }, objectName: 'point ' + (i + 1) });
    text(s, t, { x: 1.1, y: 3.72 + i * 0.55, w: 5.9, h: 0.45, fontSize: 16, color: WHITE }); });
  dots(s, 0.75, 5.6, DOF.map(() => 'ok'), { d: 0.3, step: 0.5, name: 'all fixed' });
  text(s, 'Questions? The demo stays open.   github.com/BobbyZbp/CS-6672', { x: 0.7, y: 6.25, w: 6.4, h: 0.45, fontSize: 14, color: 'A4ADB3' });
  const r = picture(s, still('snap.png'), 7.3, 1.55, 5.4, 4.4, 'The fragment placed in the lidar campus');
  caption(s, 'The tower-and-library fragment, placed.', r.x, r.y + r.h + 0.1, r.w, 0.4); }

// --- write, then give the deck its own theme colours (pptxgenjs writes Office's palette) ---------------------------
async function applyTheme(file) {
  const JSZip = require(require.resolve('jszip', { paths: [require.resolve('pptxgenjs')] }));
  const zip = await JSZip.loadAsync(fs.readFileSync(file)), part = 'ppt/theme/theme1.xml';
  const slots = ['dk1', 'lt1', 'dk2', 'lt2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6', 'hlink', 'folHlink'];
  const scheme = `<a:clrScheme name="${THEME.name}">` + slots.map(k => `<a:${k}><a:srgbClr val="${THEME.colors[k]}"/></a:${k}>`).join('') + '</a:clrScheme>';
  const xml = (await zip.file(part).async('string')).replace(/<a:clrScheme\b[\s\S]*?<\/a:clrScheme>/, () => scheme).replace(/(<a:(?:theme|fontScheme)\b[^>]*?\bname=")[^"]*"/g, (_, h) => `${h}${THEME.name}"`);
  if (!xml.includes(scheme)) throw new Error('no colour scheme in ' + part);
  zip.file(part, xml);
  for (const name of Object.keys(zip.files)) {   // a scheme colour given to a hex-only option is not a colour
    if (!name.endsWith('.xml')) continue;
    const bad = (await zip.file(name).async('string')).match(/<a:srgbClr val="((?![0-9A-Fa-f]{6}")[^"]*)"/);
    if (bad) throw new Error(`${name}: colour "${bad[1]}" is not six hex digits`);
  }
  fs.writeFileSync(file, await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' }));
}

(async () => {
  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
  await pres.writeFile({ fileName: OUTPUT });
  await applyTheme(OUTPUT);
  const missing = Array.from({ length: number }, (_, i) => i + 1).filter(n => !NOTES[n]);
  console.log(JSON.stringify({ deck: path.relative(ROOT, OUTPUT), slides: number, slides_without_notes: missing }));
})();
