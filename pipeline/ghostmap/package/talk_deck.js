#!/usr/bin/env node
// The talk's slides as a PowerPoint deck: artifacts/presentation/ghostmap-talk.pptx.
//
// About eight minutes: what was done and why (the three directions tried first), the pipeline step by step, what is
// new and what is still open; two backup slides for questions. Every number is read from the data the demo page reads
// (dist/assets/timemachine/scene.json) and the reports beside it, the method's own constants from
// anchor/georegister.py and anchor/locate.py, and every slide's speaker notes are that slide's section of
// docs/presentation/talk-track.md (English and Chinese), so the deck, the page, the code and the script cannot
// disagree. The pictures are the tour's stills (dist/assets/presentation/, written by qa/record_tour.py), two crops of
// the state's aerial flights and one public-domain postcard.
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
const campus = study.fragments.filter(f => f.run !== rec.tag.slice(0, 8)), campusRun = study.campus_run;
const gates = campus.find(f => f.geotag_baseline);
const loo = rec.located.leave_one_out;
const hoPlaza = rec.located.photos.find(q => q.photo.includes('Ho_Plaza_w_Tower'));
const [plain, taught] = [rec.splats.find(s => !s.lidar_taught), rec.splats.find(s => s.lidar_taught)];
const heldOut = s => s.psnr.test.reduce((a, t) => a + t.psnr, 0) / s.psnr.test.length;
const ident = Object.fromEntries(study.identifiability.filter(r => r.cues === 'all cues' && r.roof_edge_error_m === 0).map(r => [r.facades, r]));
const cornerWrongEdge = study.identifiability.find(r => r.cues === 'all cues' && r.facades === 'two adjacent facades' && r.roof_edge_error_m > 0);
const mapillary = JSON.parse(fs.readFileSync(path.join(ROOT, 'artifacts/georegistration/new-photos-mapillary.json'), 'utf8'));
const lidar = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/lidar/NY_FingerLakes_1_2020/report.json'), 'utf8'));
const footprints = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/footprints/buildings-utm18n.json'), 'utf8')).buildings.length;
const POSTCARD = path.join(ROOT, 'data/raw/historical/114317667_Cornell_-_Boardman_Hall_and_the_library.jpg');   // 1934, public domain
const AERIAL = year => path.join(ROOT, `data/orthoimagery/gates-site/${year}-utm18n.jpg`);
const CLIPS = path.join(ROOT, 'artifacts/presentation/clips');   // written by package/talk_clips.py from the tour video and the fly-through
const splatViews = JSON.parse(fs.readFileSync(path.join(ROOT, 'artifacts/presentation/splat-views-report.json'), 'utf8'));
const agreement = study.agreement_with_validated_frame;
const fragmentName = id => {   // 'run/fragment' as the evaluation writes it, named by its building and size, never by its run
  const [run, k] = id.split('/'), f = study.fragments.find(f => run.startsWith(f.run) && String(f.fragment) === k);
  return f ? `${f.building.replace('Bill and Melinda ', '')}, ${fmt(f.cameras)} photos${f === frag ? ' (certified)' : ''}` : id;
};

// The method's constants, read from the modules so the slides cannot drift from the code: module-level literals
// (`NAME = 1.6`, `A, B = 1.6, 0.3`, tuples) and the numeric entries of the one-line dicts (LIMITS, WEIGHTS, the
// feature configuration).
function pyConstants(file) {
  const src = fs.readFileSync(file, 'utf8'), out = {};
  for (const m of src.matchAll(/^([A-Z][A-Z0-9_]*(?:,\s*[A-Z][A-Z0-9_]*)*)\s*=\s*([^#\n]+)/gm)) {
    const names = m[1].split(',').map(n => n.trim());
    try {
      const v = JSON.parse('[' + m[2].trim().replace(/\(/g, '[').replace(/\)/g, ']').replace(/'/g, '"').replace(/,\s*\]/g, ']') + ']');
      names.forEach((n, i) => { out[n] = names.length === 1 ? v[0] : v[i]; });
    } catch (e) { /* a path, or a dict that spans lines: not a literal */ }
  }
  for (const m of src.matchAll(/'([a-z_0-9]+)':\s*(-?[\d.]+)/g)) out[m[1]] = +m[2];
  return out;
}
const G = pyConstants(path.join(ROOT, 'pipeline/ghostmap/anchor/georegister.py'));
const L = pyConstants(path.join(ROOT, 'pipeline/ghostmap/anchor/locate.py'));

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
const glue = t => typeof t === 'string' ? t.replace(/(\d) (?=(m|km|%|dB|s|px)\b)/g, '$1 ') : t;   // a number never wraps away from its unit
const text = (s, t, o) => s.addText(glue(t), Object.assign({ isTextBox: true, margin: 0, fontSize: 16, color: INK, valign: 'top' }, o));
function picture(s, file, x, y, w, h, name, align = 'center') {   // fit inside the box, keep the shape
  const [iw, ih] = imageSize(file), k = Math.min(w / iw, h / ih), pw = iw * k, ph = ih * k;
  const px = align === 'left' ? x : align === 'right' ? x + w - pw : x + (w - pw) / 2;
  s.addImage({ path: file, x: px, y, w: pw, h: ph, altText: name, objectName: name });
  return { x: px, y, w: pw, h: ph };
}
// The Gates Hall site cut from a flight's 2,500-pixel orthoimage: the block north of the baseball field.
const AERIAL_CROP = { x: 0.40, y: 0.30, w: 0.45, h: 0.32 };   // fractions of the whole image
function aerial(s, year, x, y, w, name) {
  const S = w / AERIAL_CROP.w, c = AERIAL_CROP;
  s.addImage({ path: AERIAL(year), x, y, w: S, h: S, sizing: { type: 'crop', x: c.x * S, y: c.y * S, w: c.w * S, h: c.h * S }, altText: name, objectName: name });
  return { x, y, w, h: c.h * S };
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
const card = (s, x, y, w, h, name, { fill = MIST, line = MIST } = {}) => s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: line, width: line === fill ? 0 : 1 }, objectName: name });
function stat(s, big, label, x, y, w, { size = 30, color = TERRA, labelSize = 14, labelH = 0.62 } = {}) {
  text(s, big, { x, y, w, h: size / 72 + 0.1, fontSize: size, bold: true, color, fontFace: THEME.headFontFace });
  text(s, label, { x, y: y + size / 72 + 0.12, w, h: labelH, fontSize: labelSize, color: SLATE });
}
const arrow = (s, x1, y1, x2, y2, name) => s.addShape(pres.ShapeType.line, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001, line: { color: GREY, width: 1.5, endArrowType: 'triangle' }, flipH: x2 < x1, flipV: y2 < y1, objectName: name });
const numbered = (s, n, x, y, d = 0.5) => {   // a number in a terracotta circle
  s.addShape(pres.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color: TERRA }, line: { color: TERRA, width: 0 }, objectName: 'number ' + n });
  text(s, String(n), { x, y, w: d, h: d, fontSize: d > 0.45 ? 16 : 13, bold: true, color: WHITE, align: 'center', valign: 'middle' });
};
const still = name => path.join(STILLS, name);
function video(s, clip, cover, x, y, w, h, name) {   // an embedded clip with a still as its poster
  s.addMedia({ type: 'video', path: path.join(CLIPS, clip), x, y, w, h, cover: 'image/png;base64,' + fs.readFileSync(still(cover)).toString('base64'), objectName: name });
}
const AXIS = { catAxisLabelColor: HEX.slate, valAxisLabelColor: HEX.slate, catAxisLabelFontSize: 10, valAxisLabelFontSize: 10, catAxisLabelFontFace: '+mn-lt', valAxisLabelFontFace: '+mn-lt',
  valGridLine: { color: 'D6DBDA', size: 0.5 }, catGridLine: { style: 'none' }, legendFontFace: '+mn-lt', legendFontSize: 11, legendColor: HEX.slate, titleFontFace: '+mn-lt', titleFontSize: 12, titleColor: HEX.slate };
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

// --- 3 · three things tried first ------------------------------------------------------------------------------------
{ const s = slide('CONTENT', 'What we did, and why', 'Three things we tried first');
  const cw = (W - 2 * 0.3) / 3, colX = i => X0 + i * (cw + 0.3), picH = 2.1;
  const columns = [
    { idea: 'Bring back a demolished building from old postcards', big: 'mirror images', detail: 'Each placed view fits the tower to a few pixels, from the wrong side: the tower\'s four faces look alike, and nobody photographed it from the postcards\' side.', tag: 'stopped by the record and the geometry' },
    { idea: 'One 3D model of the whole Arts Quad', big: `${fmt(campusRun.fragments)} pieces`, detail: `${fmt(campusRun.photographs)} photographs reconstructed at once come out as ${fmt(campusRun.fragments)} separate fragments: people photograph landmarks, not the walls between them.`, tag: 'stopped by coverage' },
    { idea: 'Watch the campus change in 3D, 2002 to 2026', big: '0 photographs', detail: 'Not one licensed photograph of any construction site before its building went up; the "before" exists only from the air.', tag: 'stopped by the record; the mechanism dates from 2014' }];
  const a = picture(s, POSTCARD, colX(0), 1.4, cw, picH, 'Boardman Hall and the library on a 1934 postcard', 'left');
  caption(s, 'A 1934 postcard (public domain).', a.x, a.y + a.h + 0.05, cw, 0.3);
  const b = picture(s, still('refuse.png'), colX(1), 1.4, cw, picH, 'The campus fragments, each refused with a reason', 'left');
  caption(s, 'The campus fragments, refused (demo, chapter 3).', b.x, b.y + b.h + 0.05, cw, 0.3);
  const aw = (cw - 0.12) / 2, c1 = aerial(s, 2007, colX(2), 1.4, aw, 'The Gates Hall site in the 2007 flight: a parking lot'), c2 = aerial(s, 2015, colX(2) + aw + 0.12, 1.4, aw, 'The Gates Hall site in the 2015 flight: the building');
  caption(s, '2007: a parking lot', c1.x, c1.y + c1.h + 0.05, aw, 0.3); caption(s, '2015: Gates Hall', c2.x, c2.y + c2.h + 0.05, aw, 0.3);
  columns.forEach((c, i) => {
    const x = colX(i); numbered(s, i + 1, x, 3.95, 0.42);
    text(s, c.idea, { x: x + 0.55, y: 3.93, w: cw - 0.55, h: 0.8, fontSize: 16, bold: true });
    text(s, c.big, { x, y: 4.8, w: cw, h: 0.5, fontSize: 26, bold: true, color: TERRA, fontFace: THEME.headFontFace });
    text(s, c.detail, { x, y: 5.35, w: cw, h: 0.95, fontSize: 12, color: SLATE });
    text(s, c.tag, { x, y: 6.3, w: cw, h: 0.4, fontSize: 11, italic: true, color: GREY }); });
  text(s, 'All three needed the same thing: a COLMAP model that knows where it is.', { x: X0, y: 6.7, w: W, h: 0.32, fontSize: 15, bold: true, color: INK }); }

// --- 4 · seven free numbers, and why not GPS --------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Seven free numbers, and why GPS can\'t fix them here');
  const r = picture(s, still('void.png'), X0, 1.4, 6.3, 3.6, 'The reconstruction floating in COLMAP\'s own frame', 'left');
  caption(s, 'COLMAP\'s cameras (blue) and points, at their native size and orientation (live demo, chapter 1).', r.x, r.y + r.h + 0.08, r.w, 0.35);
  text(s, `${fmt(own.length)} licensed photographs · ${fmt(new Set(own.map(p => p.artist)).size)} photographers · ${fmt(rec.points)} points · dated ${Math.min(...years)}–${Math.max(...years)}`, { x: X0, y: 5.45, w: 6.3, h: 0.5, fontSize: 13, bold: true, color: SLATE });
  dots(s, X0 + 0.05, 6.0, DOF.map(() => 'unknown'), { labels: true, step: 0.6 });
  text(s, 'seven numbers COLMAP leaves free: 1 scale, 3 rotations, 3 translations', { x: X0 + 4.4, y: 6.02, w: 2.3, h: 0.7, fontSize: 12, bold: true, color: INK });
  const rx = 7.35, rw = W + X0 - rx, g = frag.geotags;
  text(s, 'COLMAP\'s own fix: model_aligner, from known camera positions, usually GPS', { x: rx, y: 1.4, w: rw, h: 0.75, fontSize: 16, bold: true, color: GREY });
  [[fmt(g.carried) + ' tag', `GPS among the ${fmt(own.length)} photographs, and it is ${g.wrong_off_m.map(km).join(', ')} off: it points to downtown Ithaca`],
   [fmt(g.without_metadata), `of the ${fmt(own.length)} are Flickr web copies downloaded without any metadata, so their GPS is unknown`],
   ['≈' + fmt(gates.geotag_baseline.leave_one_out_error_m.median) + ' m', `GPS fit error at Gates Hall, the one fragment with ${gates.geotags.plausible} tags: where it puts a held-out camera`]].forEach(([big, label], i) => {
    const y = 2.3 + i * 1.2; text(s, big, { x: rx, y, w: 1.8, h: 0.55, fontSize: 26, bold: true, color: TERRA, fontFace: THEME.headFontFace, valign: 'middle' });
    text(s, label, { x: rx + 1.9, y, w: rw - 1.9, h: 1.05, fontSize: 13, color: SLATE }); });
  card(s, rx, 5.95, rw, 0.95, 'gps rule');
  text(s, `A similarity needs at least three good, well-spread positions per fragment; ${fmt(study.geotags.with_gps)} of ${fmt(study.geotags.photographs)} Commons photographs carry GPS, just not where it matters, and a wrong tag never announces itself.`, { x: rx + 0.2, y: 6.03, w: rw - 0.4, h: 0.8, fontSize: 12, color: INK }); }

// --- 5 · the world's model ---------------------------------------------------------------------------------------------
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

// --- 6 · the pipeline --------------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', 'The pipeline, step by step', 'The pipeline');
  const lane = (x, w, head, headColor, line, steps, name) => {   // a card with a heading and its steps joined by arrows
    card(s, x, 1.35, w, 2.05, name, { line });
    text(s, head, { x: x + 0.2, y: 1.45, w: w - 0.4, h: 0.3, fontSize: 12, bold: true, color: headColor, charSpacing: 1 });
    const sw = (w - 0.4 - (steps.length - 1) * 0.3) / steps.length;
    steps.forEach(([h, d], i) => { const sx = x + 0.2 + i * (sw + 0.3);
      text(s, h, { x: sx, y: 1.85, w: sw, h: 0.5, fontSize: 13, bold: true });
      text(s, d, { x: sx, y: 2.4, w: sw, h: 0.95, fontSize: 11, color: SLATE });
      if (i < steps.length - 1) arrow(s, sx + sw + 0.03, 2.08, sx + sw + 0.27, 2.08, name + ' flow ' + (i + 1)); }); };
  const half = (W - 0.3) / 2;
  lane(X0, half, 'COLMAP · PYCOLMAP · HLOC', GREY, GREY, [['Licensed photographs', 'Wikimedia Commons and Flickr; licence and duplicate checks'], ['Features and matches', 'NetVLAD pairs, SuperPoint keypoints, LightGlue matches'], ['Incremental mapping', `pycolmap: ${fmt(own.length)} cameras, ${fmt(rec.points)} points, in a frame of its own`]], 'colmap lane');
  lane(X0 + half + 0.3, half, 'THE PUBLIC WORLD', GREEN, GREEN, [['USGS 3DEP lidar', `a ${fmt(lidar.box_utm[2] - lidar.box_utm[0])} m box as two rasters, the surface and the bare ground, ${lidar.raster_cell_m} m cells, UTM 18N`], ['OpenStreetMap footprints', `${fmt(footprints)} outlines: wall distance fields, roof edges, inside masks`], ['The city', 'each footprint raised from the lidar ground to the lidar roof; what the page draws']], 'world lane');
  s.addShape(pres.ShapeType.roundRect, { x: X0, y: 3.8, w: W, h: 1.55, rectRadius: 0.08, fill: { color: TERRA }, line: { color: TERRA, width: 0 }, objectName: 'ghostmap lane' });
  text(s, 'GHOSTMAP', { x: X0 + 0.2, y: 3.88, w: 3, h: 0.3, fontSize: 12, bold: true, color: WHITE, charSpacing: 1 });
  const ours = [['Cues', 'walls · roof edges · photographers\' heights · tower top · free space · cameras outside'], ['Search', 'over the seven numbers: a heading × scale grid, position by descent, refinement, levelling; every score kept'], ['Certificate', 'bands, runner-up heading, per-cue ablation, cue profiles: usable, or refused with the reason'], ['Apply', 'Reconstruction.transform(Sim3d): the fragment in metres on the campus']];
  const ow = (W - 0.4 - 3 * 0.3) / 4;
  ours.forEach(([h, d], i) => { const sx = X0 + 0.2 + i * (ow + 0.3);
    text(s, h, { x: sx, y: 4.22, w: ow, h: 0.35, fontSize: 14, bold: true, color: WHITE });
    text(s, d, { x: sx, y: 4.58, w: ow, h: 0.72, fontSize: 11, color: WHITE });
    if (i < 3) s.addShape(pres.ShapeType.line, { x: sx + ow + 0.04, y: 4.39, w: 0.22, h: 0.001, line: { color: LIGHT, width: 1.5, endArrowType: 'triangle' }, objectName: 'ghostmap flow ' + (i + 1) }); });
  arrow(s, X0 + half / 2, 3.45, X0 + half / 2, 3.77, 'the fragment goes in'); arrow(s, X0 + half + 0.3 + half / 2, 3.45, X0 + half + 0.3 + half / 2, 3.77, 'the world goes in');
  arrow(s, X0 + W / 2, 5.4, X0 + W / 2, 5.67, 'the placed fragment comes out');
  const uses = [['A new photograph', 'retrieve · match · RANSAC pose · placed, distance open, or refused; painted onto the city'], ['Splats refereed and taught', 'every Gaussian scored against lidar free space; one lidar rule in training'], ['Time', `${scene.years.length} aerial flights ${scene.years[0]}–${scene.years.at(-1)}, dated buildings, years per point`]];
  const uw = (W - 2 * 0.3) / 3;
  uses.forEach(([h, d], i) => { const ux = X0 + i * (uw + 0.3); card(s, ux, 5.7, uw, 1.2, 'use ' + (i + 1));
    text(s, h, { x: ux + 0.2, y: 5.8, w: uw - 0.4, h: 0.35, fontSize: 14, bold: true, color: TERRA });
    text(s, d, { x: ux + 0.2, y: 6.15, w: uw - 0.4, h: 0.7, fontSize: 11, color: SLATE }); }); }

// --- 7 · step 1: the two inputs ---------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Step 1 · the two inputs');
  const half = (W - 0.4) / 2, rx = X0 + half + 0.4;
  const column = (x, head, color, pic, name, rows) => {
    text(s, head, { x, y: 1.3, w: half, h: 0.4, fontSize: 18, bold: true, color });
    picture(s, still(pic), x, 1.75, half, 2.4, name, 'left');
    rows.forEach(([big, label], i) => { const y = 4.35 + i * 0.85;
      text(s, big, { x, y, w: half, h: 0.4, fontSize: big.length > 14 ? 15 : 22, bold: true, color: TERRA, fontFace: THEME.headFontFace, valign: 'middle' });
      text(s, label, { x, y: y + 0.42, w: half, h: 0.42, fontSize: 12, color: SLATE }); }); };
  column(X0, 'The fragment, from COLMAP', GREY, 'void.png', 'The reconstruction in COLMAP\'s own frame', [
    [fmt(own.length) + ' photographs', `licensed, ${fmt(new Set(own.map(p => p.artist)).size)} photographers, the dated ones ${Math.min(...years)}–${Math.max(...years)}`],
    ['NetVLAD · SuperPoint · LightGlue', 'pairs, keypoints and matches (hloc), then pycolmap\'s incremental mapper'],
    [fmt(rec.points) + ' points', `and ${fmt(own.length)} cameras, with the facade normals and the photographers' positions the cues read`]]);
  column(rx, 'The world, from public data', GREEN, 'above.png', 'The lidar campus', [
    [`${fmt(lidar.box_utm[2] - lidar.box_utm[0])} m box, ${lidar.raster_cell_m} m cells`, 'USGS 3DEP lidar in UTM 18N as two rasters: the surface and the bare ground'],
    [fmt(footprints) + ' footprints', 'OpenStreetMap outlines: wall distance fields, roof edges read from the lidar just inside each wall, inside masks'],
    ['the city', 'each footprint raised from the lidar ground to the lidar roof; the model the page draws and paints on']]); }

// --- 8 · step 2: the cues -------------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Step 2 · each cue fixes some of the seven numbers');
  const dx = 8.55, step = 0.58;
  DOF.forEach((d, i) => text(s, d, { x: dx + i * step - 0.15, y: 1.35, w: step, h: 0.3, fontSize: 11, bold: true, color: SLATE, align: 'center' }));
  const F = 'fixed', U = 'unknown', rows = [
    ['Facade normals', 'walls are vertical: the up direction, before the search', [F, F, U, U, U, U, U]],
    ['Photographers\' heights', `people stand ${G.EYE_M} ± ${G.EYE_SD_M} m above the lidar ground`, [F, F, U, U, U, U, F]],
    ['OpenStreetMap walls', 'points on the walls: precision over every wall, recall over the named building\'s', [U, U, F, U, F, F, U]],
    ['Lidar roof edges', `a facade's top meets the lidar roof just inside it, ± ${G.ROOF_EDGE_SD_M} m`, [U, U, U, F, U, U, U]],
    ['Parallel walls', 'their spacing is known in metres', [U, U, U, F, U, U, U]],
    ['McGraw Tower top', 'the tower\'s axis on its footprint, its top at the lidar top', [U, U, U, F, F, F, U]],
    ['Free space', `${G.FREE_SPACE_SAMPLES} samples per camera-to-point ray, none inside a building (after Kaminsky 2009)`, [U, U, U, U, U, U, U]]];
  rows.forEach(([cue, what, st], i) => {
    const y = 1.8 + i * 0.66;
    if (i % 2 === 0) s.addShape(pres.ShapeType.rect, { x: X0, y: y - 0.08, w: W, h: 0.66, fill: { color: MIST }, line: { color: MIST, width: 0 }, objectName: 'row band ' + (i + 1) });
    text(s, cue, { x: X0 + 0.15, y, w: 2.9, h: 0.5, fontSize: 16, bold: true, valign: 'middle' });
    text(s, what, { x: 3.65, y, w: 4.75, h: 0.5, fontSize: 13, color: SLATE, valign: 'middle' });
    dots(s, dx, y + 0.09, st, { d: 0.32, step, name: cue });
  });
  const weights = Object.entries(G.WEIGHTS).map(([k, v]) => `${k.replace('_', ' ')} ${v}`).join(' · ');
  caption(s, `Filled: the cue fixes that number. Free space fixes none on its own; it rules out placements that put a line of sight through a building. The objective is the weighted sum of the bounded cue scores: ${weights}.`, X0, 6.45, W, 0.5); }

// --- 9 · step 3: the search -----------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Step 3 · the search keeps everything it looks at');
  const steps = [
    ['Vertical first', 'from the facade normals; a fragment with one facade falls back to the cameras\' own up, and the certificate records which rule was used'],
    ['Landmark', 'pins the position: when the photographs name a tower and the model holds a tower-like cluster, its axis goes onto the footprint centre; the walls then decide the heading, the top the scale'],
    ['Grid', 'heading every 3°, scale from a third to three times a prior from the facade\'s height; in each cell the position descends along the wall distance field'],
    ['Refine', 'the best cells, at least 5° apart, refined jointly with an explicit simplex; then a 0.5° heading scan around the winner'],
    ['Level', 'a robust plane through the well-observed photographers\' heights proposes the remaining tilt; fits turned by ⅓, ⅔ and all of it compete with the facade vertical on the joint objective'],
    ['Keep every score', 'each cue\'s score is stored per cell, so the profile of any cue subset over scale or heading is read off afterwards, without a second search']];
  const cw = (W - 2 * 0.3) / 3, ch = 2.45;
  steps.forEach(([h, d], i) => {
    const x = X0 + (i % 3) * (cw + 0.3), y = 1.4 + Math.floor(i / 3) * (ch + 0.25); card(s, x, y, cw, ch, 'step ' + (i + 1));
    numbered(s, i + 1, x + 0.25, y + 0.25, 0.5);
    text(s, h, { x: x + 0.9, y: y + 0.25, w: cw - 1.1, h: 0.5, fontSize: 17, bold: true, valign: 'middle' });
    text(s, d, { x: x + 0.25, y: y + 0.9, w: cw - 0.5, h: ch - 1.05, fontSize: 13, color: SLATE }); });
  caption(s, 'The output of the search is not one similarity but the objective over the whole grid; the certificate is read from that.', X0, 6.8, W, 0.3); }

// --- 10 · step 4: the certificate ------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Step 4 · the certificate');
  const items = [
    ['Bands', `how far each number can move before the objective drops by ${pct(G.BAND_DROP)} of its range`],
    ['Runner-up heading', `the best heading more than 20° away must score under ${pct(G.yaw_contrast)} of the winner`],
    ['Ablation', 'each cue removed in turn and the fit repeated: how far the optimum moves'],
    ['Cue profiles', `the walls alone, the roof edges and the tower each imply a scale; more than ${pct(G.scale_disagreement)} apart is "cues disagree"`],
    ['Structural rules', `a roof-edge score under ${G.roof_edge_min} with no landmark: no facade was seen; more than ${pct(G.cameras_inside)} of the photographers inside a building: refused`],
    ['Verdict', 'usable, or a named failure mode, with the scale uncertainty the fixing cue implies']];
  items.forEach(([h, d], i) => {
    const y = 1.4 + i * 0.88; s.addShape(pres.ShapeType.ellipse, { x: X0, y: y + 0.08, w: 0.22, h: 0.22, fill: { color: TERRA }, line: { color: TERRA, width: 0 }, objectName: 'item ' + (i + 1) });
    text(s, h, { x: X0 + 0.4, y, w: 2.1, h: 0.8, fontSize: 15, bold: true });
    text(s, d, { x: X0 + 2.5, y, w: 4.0, h: 0.85, fontSize: 12, color: SLATE }); });
  const rx = 7.3, rw = W + X0 - rx;
  const r = picture(s, still('snap.png'), rx, 1.4, rw, 2.75, 'The fragment placed in the lidar campus', 'right');
  caption(s, 'In metres among the lidar buildings (live demo, chapter 2).', r.x, r.y + r.h + 0.06, r.w, 0.3);
  s.addShape(pres.ShapeType.roundRect, { x: rx, y: 4.6, w: 3.2, h: 0.45, rectRadius: 0.1, fill: { color: GREEN }, line: { color: GREEN, width: 0 }, objectName: 'verdict' });
  text(s, 'certificate: ' + cert.verdict, { x: rx, y: 4.6, w: 3.2, h: 0.45, fontSize: 16, bold: true, color: WHITE, align: 'center', valign: 'middle' });
  [['±' + pct(cert.scale_uncertainty_relative, 1), `scale, fixed ${cert.scale_fixed_by.length} independent ways: tower top, parallel walls, roof edges`],
   [pct(cert.yaw_contrast.runner_up_outside_20deg), 'the best other heading\'s score against the winner'],
   [fmt(cert.levelling_correction_deg, 1) + '°', 'levelled by the photographers\' heights'],
   [pct(rec.placement.sparse_points_free_space.surface), 'of COLMAP\'s points within 2.5 m of a lidar surface']].forEach(([big, label], i) => {
    const y = 5.15 + i * 0.46; text(s, big, { x: rx, y, w: 1.5, h: 0.42, fontSize: 20, bold: true, color: TERRA, fontFace: THEME.headFontFace, valign: 'middle' });
    text(s, label, { x: rx + 1.6, y, w: rw - 1.6, h: 0.42, fontSize: 12, color: SLATE, valign: 'middle' }); }); }

// --- 11 · the certificate's numbers, explained ----------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'The certificate\'s numbers, explained');
  const hd = o => ({ text: o, options: { bold: true, color: INK, fill: { color: MIST } } }), big = o => ({ text: o, options: { bold: true, color: TERRA, fontSize: 18, fontFace: THEME.headFontFace } });
  const yc = cert.yaw_contrast, cs = cert.cue_scores;
  const rows = [[hd('Number'), hd('What it measures'), hd('The rule'), hd('Why it matters')],
    [big('±' + pct(cert.scale_uncertainty_relative, 1)), `the tower top fixes the scale to about 2 m over the tower's height; the walls alone and the roof edges of 4 walls land inside that band`, 'scale fixed by at least one cue, and the cues that measure it must agree', `three independent measurements give the same ${fmt(cert.scale_m_per_unit, 1)} m per COLMAP unit`],
    [big(pct(yc.runner_up_outside_20deg)), `the best heading more than 20° away scores this much of the winner (the quadrants: ${pct(yc['+90'])}, ${pct(yc['+180'])}, ${pct(yc['+270'])})`, `under ${pct(G.yaw_contrast)}, or the heading is ambiguous; a square tower alone gives about 95 %`, 'the heading is unique, not one of four look-alike faces'],
    [big(fmt(cert.levelling_correction_deg, 1) + '°'), `the facade vertical was tilted; the photographers' heights over the lidar ground proposed ${fmt(cert.levelling_tilt_deg, 1)}°, and two thirds of it won on the joint objective`, 'camera height corrects tilt only as far as the other cues agree', `${fmt(cert.cameras_in_height_band)} of ${fmt(cert.cameras)} photographers end at eye height; the rest are far away and poorly placed along their rays`],
    [big(pct(rec.placement.sparse_points_free_space.surface)), `of COLMAP's own points within 2.5 m of a lidar surface; ${pct(cert.points_within_1m_of_walls)} within 1 m of a footprint wall`, 'a structural check, not a fit term', 'the noise floor every splat is later compared with'],
    [big('1.00 · 0.85 · 0.25'), `cue scores at the optimum: tower ${fmt(cs.landmark, 2)}, free space ${fmt(cs.free_space, 2)}, cameras outside ${fmt(cs.outside, 2)}, roof edges ${fmt(cs.roof_edges, 2)}, walls ${fmt(cs.walls, 2)}, camera height ${fmt(cs.camera_height, 2)}`, 'each bounded 0 to 1 with a stated noise model', 'who did the work: the tower, confirmed by the walls and the roof edges']];
  s.addTable(rows, { x: X0, y: 1.4, w: W, colW: [1.7, 4.3, 3.0, 3.13], fontSize: 11, color: SLATE, valign: 'middle', rowH: 0.86, border: { type: 'solid', pt: 0.75, color: 'D6DBDA' }, margin: [0.05, 0.1, 0.05, 0.1], objectName: 'certificate numbers' }); }

// --- 12 · how the scale is read: every cue's own profile ------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'How the scale is read: every cue\'s own profile');
  const p = cert.profiles, labels = p.scale_grid_m_per_unit.map(v => fmt(v, 1));
  const series = [['all cues', 'all', HEX.ink], ['walls alone', 'only_walls', HEX.terra], ['roof edges alone', 'only_roof_edges', HEX.amber], ['tower alone', 'only_landmark', HEX.green], ['photographers\' heights alone', 'only_camera_height', HEX.grey]];
  s.addChart(pres.ChartType.line, series.map(([name, key]) => ({ name, labels, values: p[key] })), Object.assign({ x: X0, y: 1.4, w: 7.4, h: 4.9, chartColors: series.map(r => r[2]), lineSize: 2, lineDataSymbol: 'none', lineSmooth: false,
    showLegend: true, legendPos: 'b', showTitle: true, title: 'the objective over scale, each cue on its own (metres per COLMAP unit)', valAxisMinVal: 0, objectName: 'scale profiles' }, AXIS));
  caption(s, `Every cue that measures scale peaks at the same place, ${fmt(cert.scale_m_per_unit, 1)} m per unit; the certificate reads "fixed three independent ways" off these curves.`, X0, 6.35, 7.4, 0.5);
  const rx = 8.35, rw = W + X0 - rx;
  text(s, 'Take one cue away and refit', { x: rx, y: 1.4, w: rw, h: 0.4, fontSize: 16, bold: true, color: TERRA });
  const hd = o => ({ text: o, options: { bold: true, color: INK, fill: { color: MIST } } }), names = { walls: 'walls', roof_edges: 'roof edges', camera_height: 'camera height', landmark: 'tower', free_space: 'free space', outside: 'cameras outside' };
  const rows = [[hd('without'), hd('heading'), hd('scale'), hd('position')]].concat(Object.entries(cert.cue_ablation).map(([k, a]) => [names[k] || k, { text: fmt(Math.abs(a.yaw_shift_deg), 2) + '°', options: { align: 'right' } }, { text: '×' + fmt(a.scale_ratio, 3), options: { align: 'right' } }, { text: fmt(a.position_shift_m, 2) + ' m', options: { align: 'right' } }]));
  s.addTable(rows, { x: rx, y: 1.9, w: rw, colW: [1.6, 0.9, 0.9, 0.98], fontSize: 12, color: SLATE, valign: 'middle', rowH: 0.4, border: { type: 'solid', pt: 0.75, color: 'D6DBDA' }, margin: [0.04, 0.08, 0.04, 0.08], objectName: 'cue ablation' });
  const lm = cert.cue_ablation.landmark, others = Math.max(...Object.entries(cert.cue_ablation).filter(([k]) => k !== 'landmark').map(([, a]) => a.position_shift_m));
  text(s, `Removing the tower moves the optimum ${fmt(lm.position_shift_m, 1)} m and ${fmt(Math.abs(lm.yaw_shift_deg), 1)}°; removing any other cue moves it under ${fmt(Math.ceil(others * 10) / 10, 1)} m. The tower does the work; the walls and the roof edges confirm it, and the certificate says so.`, { x: rx, y: 5.0, w: rw, h: 1.6, fontSize: 13, color: INK }); }

// --- 13 · watch it snap (video) --------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Watch it snap');
  video(s, 'snap.mp4', 'snap.png', X0 + 0.9, 1.35, 10.33, 5.81, 'The fragment snapping into the lidar campus');
  caption(s, 'Recorded from the demo page (chapter 2): the fragment in COLMAP\'s frame, then the placement applied; it lands among the lidar buildings and the certificate appears. Click to play; the live demo does the same.', X0, 6.6, W, 0.4); }

// --- 14 · when it refuses, and why --------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'When it refuses, and why');
  const hd = o => ({ text: o, options: { bold: true, color: INK, fill: { color: MIST } } });
  const rows = [[hd('Fragment (named by its photographs)'), hd('Photos'), hd('Certificate'), hd('Checked by GPS')]].concat(campus.map(f => [
    f.building.replace('Bill and Melinda ', ''), { text: fmt(f.cameras), options: { align: 'right' } }, { text: 'refused: ' + f.failure_mode, options: { color: RED } },
    f.ours_vs_geotags_m ? { text: km(f.ours_vs_geotags_m.median) + ' off', options: { bold: true } } : { text: 'no usable GPS', options: { color: GREY } }]));
  s.addTable(rows, { x: X0, y: 1.4, w: 8.0, colW: [2.3, 0.8, 3.5, 1.4], fontSize: 12, color: SLATE, valign: 'middle', rowH: 0.4, border: { type: 'solid', pt: 0.75, color: 'D6DBDA' }, margin: [0.04, 0.1, 0.04, 0.1], objectName: 'campus fragments' });
  caption(s, `The whole campus collection reconstructed at once: ${fmt(campusRun.photographs)} photographs, ${fmt(campusRun.fragments)} fragments; the ${campus.length} with eight or more cameras are listed.`, X0, 4.85, 8.0, 0.4);
  const checked = campus.filter(f => f.ours_vs_geotags_m), offs = checked.map(f => f.ours_vs_geotags_m.median);
  card(s, X0, 5.45, 8.0, 1.35, 'callout');
  text(s, `${checked.length} of ${checked.length}`, { x: X0 + 0.25, y: 5.55, w: 1.9, h: 1.1, fontSize: 40, bold: true, color: TERRA, fontFace: THEME.headFontFace, valign: 'middle' });
  text(s, `placements GPS could check were ${km(Math.min(...offs))} to ${km(Math.max(...offs))} off, and all were refused: none certified and then found wrong.`, { x: X0 + 2.3, y: 5.55, w: 5.5, h: 1.1, fontSize: 15, color: INK, valign: 'middle' });
  const rx = 8.95, rw = W + X0 - rx, OK = 'ok', FR = 'free';
  text(s, 'Why: geometry, on a synthetic hall with a known answer', { x: rx, y: 1.4, w: rw, h: 0.6, fontSize: 14, bold: true, color: GREY });
  [['one facade', 'One facade', 'scale undetermined', RED, [OK, OK, OK, FR, OK, OK, OK]],
   ['two parallel facades', 'Two parallel facades', 'position undetermined', RED, [OK, OK, OK, OK, FR, OK, OK]],
   ['two adjacent facades', 'A corner', 'usable', GREEN, DOF.map(() => OK)],
   ['three facades', 'Three facades', 'usable', GREEN, DOF.map(() => OK)]].forEach(([key, name, verdict, vc, st], i) => {
    const y = 2.1 + i * 1.15, r = ident[key];
    text(s, name, { x: rx, y, w: rw, h: 0.3, fontSize: 14, bold: true });
    dots(s, rx, y + 0.33, st, { d: 0.24, step: 0.36, name });
    text(s, verdict, { x: rx, y: y + 0.6, w: rw, h: 0.28, fontSize: 12, bold: true, color: vc });
    text(s, `scale ×${fmt(r.scale_ratio, 3)} · heading ${fmt(r.yaw_error_deg, r.yaw_error_deg < 1 ? 2 : 1)}° off`, { x: rx, y: y + 0.87, w: rw, h: 0.27, fontSize: 11, color: SLATE }); });
  caption(s, 'red = not fixed · layouts: backup slide', rx, 6.72, rw, 0.28); }

// --- 15 · the synthetic hall, all sixteen cases -----------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'The synthetic hall, all sixteen cases');
  const order = ['one facade', 'two parallel facades', 'two adjacent facades', 'three facades'], labels = ['one facade', 'two parallel', 'a corner', 'three facades'];
  const pick = (cues, err) => order.map(f => study.identifiability.find(r => r.cues === cues && r.facades === f && r.roof_edge_error_m === err));
  const series = [['exact roof edges, all cues', pick('all cues', 0), HEX.green], ['3 m roof-edge error, all cues', pick('all cues', 3), HEX.red], ['3 m error, without the roof-edge cue', pick('without roof edges', 3), HEX.grey]];
  s.addChart(pres.ChartType.bar, series.map(([name, rows]) => ({ name, labels, values: rows.map(r => r.scale_ratio) })), Object.assign({ x: X0, y: 1.4, w: 7.6, h: 3.4, barDir: 'col', barGapWidthPct: 60, chartColors: series.map(r => r[2]),
    showValue: true, dataLabelFormatCode: '0.00', dataLabelPosition: 'outEnd', dataLabelFontSize: 9, dataLabelColor: HEX.slate, dataLabelFontFace: '+mn-lt', valAxisMinVal: 0.8, valAxisMaxVal: 1.3, valAxisLabelFormatCode: '0.0',
    showLegend: true, legendPos: 'b', showTitle: true, title: 'recovered scale ÷ true scale (1.00 is exact)', objectName: 'synthetic sweep' }, AXIS));
  const hd = o => ({ text: o, options: { bold: true, color: INK, fill: { color: MIST } } }), v = r => ({ text: r.verdict === 'usable' ? 'usable' : r.failure_mode, options: { color: r.verdict === 'usable' ? HEX.green : HEX.red, bold: true } });
  const rows = [[hd('verdict'), ...labels.map(hd)], ...series.slice(0, 2).map(([name, rs]) => [name.replace(', all cues', ''), ...rs.map(v)])];
  s.addTable(rows, { x: X0, y: 4.95, w: 7.6, colW: [1.9, 1.35, 1.45, 1.45, 1.45], fontSize: 11, color: SLATE, valign: 'middle', rowH: 0.42, border: { type: 'solid', pt: 0.75, color: 'D6DBDA' }, margin: [0.04, 0.08, 0.04, 0.08], objectName: 'sweep verdicts' });
  const rx = 8.5, rw = W + X0 - rx;
  [['With exact roof edges', `every placement is within 3 % in scale (the one-facade case is refused anyway: nothing in it fixes the scale) and the verdicts are right.`],
   ['With a 3 m roof-edge error', `the corner comes out ${pct(Math.abs(cornerWrongEdge.scale_ratio - 1))} too large and is still certified ${cornerWrongEdge.verdict}: nothing else in a corner fragment measures scale, so the certificate cannot see it. Where the walls do measure scale (parallel walls, three facades) the same error is caught as "cues disagree".`],
   ['So', 'the certificate\'s known hole is a map error it has no second opinion on; measuring that false-acceptance rate is on the plan.']].forEach(([h, d], i) => {
    const y = 1.4 + i * 1.75; text(s, h, { x: rx, y, w: rw, h: 0.35, fontSize: 15, bold: true, color: i === 1 ? RED : TERRA });
    text(s, d, { x: rx, y: y + 0.38, w: rw, h: 1.35, fontSize: 12, color: SLATE }); }); }

// --- 16 · the same building through two fragments ---------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'The same building through two fragments');
  const hd = o => ({ text: o, options: { bold: true, color: INK, fill: { color: MIST } } });
  const rows = [[hd('Building'), hd('Fragment'), hd('against'), hd('Verdicts'), hd('Median'), hd('90th pct')]].concat(agreement.map(a => [a.building, fragmentName(a.fragments[0]), fragmentName(a.fragments[1]),
    { text: a.verdicts.join(' / '), options: { color: a.verdicts.every(v => v === 'usable') ? HEX.green : a.verdicts.some(v => v === 'usable') ? HEX.amber : HEX.red } },
    { text: fmt(a.median_distance_m, 1) + ' m', options: { align: 'right', bold: a.median_distance_m > 5, color: a.median_distance_m > 5 ? HEX.red : HEX.ink } }, { text: fmt(a.p90_distance_m, 1) + ' m', options: { align: 'right' } }]));
  s.addTable(rows, { x: X0, y: 1.4, w: W, colW: [1.9, 3.3, 3.0, 1.73, 1.1, 1.1], fontSize: 11, color: SLATE, valign: 'middle', rowH: 0.36, border: { type: 'solid', pt: 0.75, color: 'D6DBDA' }, margin: [0.03, 0.08, 0.03, 0.08], objectName: 'cross-fragment agreement' });
  const withCertified = b => agreement.filter(a => a.building === b && a.verdicts.includes('usable')).map(a => a.median_distance_m);
  const tower = withCertified('McGraw Tower'), library = withCertified('Uris Library'), refusedPairs = agreement.filter(a => !a.verdicts.includes('usable'));
  const between = refusedPairs.length ? ` Between two refused fragments: ${refusedPairs.map(a => `${a.building} ${fmt(a.median_distance_m, 1)} m`).join(', ')}.` : '';
  const tableH = 0.36 * rows.length + 0.1;
  card(s, X0, 1.5 + tableH, W, 1.75, 'reading');
  text(s, [{ text: 'A check that needs no ground truth. ', options: { bold: true, color: TERRA } }, { text: `The same building reconstructed in two fragments, each placed on its own: McGraw Tower agrees within ${fmt(Math.max(...tower), 1)} m against every campus fragment (the landmark pins it); Uris Library is ${fmt(Math.min(...library))}–${fmt(Math.max(...library))} m apart where the campus fragment's heading was refused.${between} Refused frames disagree by tens of metres; nothing certified disagrees.` }], { x: X0 + 0.25, y: 1.65 + tableH, w: W - 0.5, h: 1.5, fontSize: 14, color: INK }); }

// --- 17 · step 5: a photograph it has never seen ------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Step 5 · a photograph it has never seen');
  const steps = [['1 · Retrieve', `NetVLAD: the ${L.RETRIEVE} most similar of the ${fmt(own.length)}`], ['2 · Match', `SuperPoint (${fmt(L.max_keypoints)} keypoints at ${fmt(L.resize_max)} px) + LightGlue`],
    ['3 · Pose', `pycolmap RANSAC (${fmt(L.RANSAC_PX)} px) from the EXIF focal length and ${L.FOCAL_PRIORS.length} guesses, then refined with the focal free; most inliers wins, at least ${L.MIN_INLIERS}`],
    ['4 · Distance', `poses from the other guesses keeping ${pct(L.VALLEY_SHARE)} of the inliers form a segment; longer than ${fmt(L.UNCERTAIN_M)} m: the distance stays open`],
    ['5 · Paint', 'the photograph projected onto the lidar city from that pose, with a depth test']];
  const cw = (W - 4 * 0.2) / 5;
  steps.forEach(([h, d], i) => { const x = X0 + i * (cw + 0.2); card(s, x, 1.35, cw, 1.4, 'step ' + (i + 1));
    text(s, h, { x: x + 0.15, y: 1.42, w: cw - 0.3, h: 0.35, fontSize: 14, bold: true, color: TERRA });
    text(s, d, { x: x + 0.15, y: 1.76, w: cw - 0.3, h: 0.97, fontSize: 11, color: SLATE }); });
  const iw = (W - 0.25) / 2;
  const a = picture(s, still('photo-stand.png'), X0, 2.85, iw, 2.55, 'The photograph painted onto the lidar city from where it was placed', 'left');
  const b = picture(s, still('photo-city.png'), X0 + iw + 0.25, 2.85, iw, 2.55, 'The same spot without the photograph', 'left');
  caption(s, 'From where it was placed: the photograph painted onto the lidar city (inside the white frame).', a.x, a.y + a.h + 0.06, iw, 0.4);
  caption(s, `The same spot, the bare lidar city: the tower is where the photograph says. ${credit(hoPlaza)}.`, b.x, b.y + b.h + 0.06, iw, 0.4);
  const e = loo.placed_position_error_m, sw = (W - 3 * 0.25) / 4;
  text(s, `Tested by taking each of the ${fmt(loo.photographs)} photographs out and placing it again (${fmt(loo.with_a_plausible_reference_pose)} with a trustworthy reference pose):`, { x: X0, y: 5.95, w: W, h: 0.3, fontSize: 12, bold: true, color: SLATE });
  [[`${loo.placed} placed`, `median ${fmt(e.median, 1)} m from the reconstruction's own pose`], [`${loo.placed_distance_uncertain} distance open`, `the true spot a median ${fmt(loo.distance_uncertain_truth_to_segment_m.median, 1)} m from the stated line`],
   [`${loo.refused} refused`, `each would have been about ${fmt(Math.round(loo.refused_position_error_m_median / 5) * 5)} m wrong`], [`${mapillary.rows.length} of ${mapillary.rows.length} refused`, 'Mapillary photographs from the Arts Quad side']].forEach(([big, label], i) =>
    stat(s, big, label, X0 + i * (sw + 0.25), 6.25, sw, { size: 16, labelSize: 11, labelH: 0.4 })); }

// --- 18 · placing a photograph, live (video) -----------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Placing a photograph, live');
  video(s, 'photo.mp4', 'photo-stand.png', X0 + 0.9, 1.35, 10.33, 5.81, 'A photograph dropped on the demo page, placed and painted onto the lidar city');
  caption(s, `Recorded from the demo page (chapter 11): a photograph from the tray, placed in about two seconds without GPS; the camera moves to where the photographer stood and the photograph is painted onto the city; then all ${fmt(own.length)} photographs painted back. Click to play; or do it live with your own phone photograph.`, X0, 6.6, W, 0.4); }

// --- 19 · tested by taking each photograph out ---------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Tested by taking each photograph out');
  s.addChart(pres.ChartType.bar, [{ name: 'photographs', labels: ['placed', 'distance open', 'refused'], values: [loo.placed, loo.placed_distance_uncertain, loo.refused] }], Object.assign({
    x: X0, y: 1.45, w: 6.3, h: 3.5, barDir: 'bar', catAxisOrientation: 'maxMin', chartColors: [HEX.green, HEX.amber, HEX.red], barGapWidthPct: 45,
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 16, dataLabelFontBold: true, dataLabelColor: HEX.ink, dataLabelFontFace: '+mn-lt',
    catAxisLabelFontSize: 14, catAxisLineShow: false, valAxisHidden: true, valGridLine: { style: 'none' },
    showLegend: false, showTitle: true, title: `${fmt(loo.with_a_plausible_reference_pose)} photographs with a trustworthy reference pose`, objectName: 'leave-one-out verdicts' }, AXIS, { catAxisLabelFontSize: 14 }));
  caption(s, `Each of the ${fmt(loo.photographs)} photographs taken out of the reconstruction and placed again from scratch, scored where COLMAP's own pose of it is trustworthy (${fmt(loo.photographs - loo.with_a_plausible_reference_pose)} are not: COLMAP had put one 37 km away).`, X0, 5.1, 6.3, 0.6);
  const e = loo.placed_position_error_m, rows = [
    [fmt(e.median, 1) + ' m', `median error of the ${loo.placed} placed: half of them land within a footstep of where the reconstruction had them; 90th percentile ${fmt(e.p90, 1)} m, worst ${fmt(e.max)} m`],
    [fmt(loo.distance_uncertain_truth_to_segment_m.median, 1) + ' m', `for the ${loo.placed_distance_uncertain} long-lens shots the direction is right and the distance is the open part: the true spot lies this far from the stated line`],
    ['≈' + fmt(Math.round(loo.refused_position_error_m_median / 5) * 5) + ' m', `what a wrong acceptance would have cost: the ${loo.refused} refused would each have been this far off`],
    [`${mapillary.rows.length} / ${mapillary.rows.length}`, 'street photographs from the Arts Quad side refused as a block: a whole side of the tower nobody online photographed']];
  rows.forEach(([big, label], i) => {
    const y = 1.45 + i * 1.3; text(s, big, { x: 7.2, y, w: 1.9, h: 0.6, fontSize: 24, bold: true, color: TERRA, fontFace: THEME.headFontFace, valign: 'middle' });
    text(s, label, { x: 9.15, y, w: 3.58, h: 1.2, fontSize: 12, color: SLATE, valign: 'middle' }); }); }

// --- 20 · what a world frame buys ------------------------------------------------------------------------------------
{ const s = slide('CONTENT', 'What it buys', 'What a world frame buys you');
  text(s, 'The lidar as referee and teacher', { x: X0, y: 1.35, w: 6.0, h: 0.4, fontSize: 18, bold: true, color: TERRA });
  const a = picture(s, still('verdict-plain-vs-lidar-taught.jpg'), X0, 1.85, 6.0, 2.3, 'Plain and lidar-taught splats from a new viewpoint, painted by the lidar\'s verdict', 'left');
  caption(s, 'A view no photographer took; every Gaussian painted by the lidar: red in measured-empty air, purple underground. Plain splat left, lidar-taught right.', X0, a.y + a.h + 0.08, 6.0, 0.55);
  const f = (o, k) => o.free_space[k];
  [[`${pct(f(plain, 'buried'))} → ${pct(f(taught, 'buried'))}`, 'of Gaussians under the bare ground'], [`${pct(f(plain, 'on_surfaces'))} → ${pct(f(taught, 'on_surfaces'))}`, 'on lidar surfaces'], [`${fmt(heldOut(plain), 1)} → ${fmt(heldOut(taught), 1)}`, 'dB on held-out photos: no worse']].forEach(([big, label], i) =>
    stat(s, big, label, X0 + i * 2.05, 4.95, 1.95, { size: 17, labelSize: 13 }));
  text(s, 'Time, for free', { x: 6.95, y: 1.35, w: 5.78, h: 0.4, fontSize: 18, bold: true, color: TERRA });
  const b = picture(s, still('gates.png'), 6.95, 1.85, 5.78, 3.65, 'Gates Hall in the time machine', 'left');
  caption(s, `Gates Hall in the 2016 flight: a parking lot until 2012. ${scene.years.length} aerial flights, ${scene.years[0]}–${scene.years.at(-1)}, on the same terrain (live demo, chapter 7).`, b.x, b.y + b.h + 0.08, b.w, 0.55); }

// --- 21 · held-out photographs: photograph, plain splat, lidar-taught ------------------------------------------------------
{ const s = slide('CONTENT', null, 'Held-out photographs, rendered by both splats');
  const psnr = name => Object.fromEntries(splatViews[name].poses.map(([id, v, held]) => [id, { v, held }]));
  const pp = psnr('tower-and-library'), pt = psnr('tower-and-library-lidar-taught');
  const views = Object.keys(pp).filter(id => pp[id].held).sort((a, b) => pt[b].v - pt[a].v).slice(0, 2);
  const cw = (W - 2 * 0.2) / 3, rh = 2.3;
  ['the photograph', 'the plain splat, from its placed pose', 'the lidar-taught splat, same pose'].forEach((h, j) => text(s, h, { x: X0 + j * (cw + 0.2), y: 1.3, w: cw, h: 0.3, fontSize: 13, bold: true, color: j === 2 ? GREEN : SLATE }));
  views.forEach((id, i) => {
    const y = 1.65 + i * (rh + 0.15);
    [[`view-${id}-photo.jpg`, ''], [`view-${id}-tower-and-library.jpg`, `${fmt(pp[id].v, 1)} dB`], [`view-${id}-tower-and-library-lidar-taught.jpg`, `${fmt(pt[id].v, 1)} dB`]].forEach(([file, label], j) => {
      const r = picture(s, still(file), X0 + j * (cw + 0.2), y, cw, rh, `${label || 'photograph'} ${id}`, 'left');
      if (label) text(s, label, { x: r.x + r.w - 1.0, y: r.y + r.h - 0.35, w: 0.95, h: 0.3, fontSize: 12, bold: true, color: WHITE, align: 'right' }); }); });
  caption(s, 'Two photographs never used in training, rendered by each splat from the pose the placement gave them; dB is PSNR against the photograph after a per-image colour fit. They look alike: the lidar rule costs no image quality. The difference is where the paint is, which the next clip shows.', X0, 6.5, W, 0.5); }

// --- 22 · between the photographers (video) --------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Between the photographers');
  video(s, 'fly-through.mp4', 'walk-plain-vs-lidar-taught.jpg', X0, 1.35, 8.0, 3.0, 'The fly-through: plain splat left, lidar-taught right, every Gaussian painted by the lidar verdict');
  caption(s, `A camera path no photographer took (${fmt(splatViews.walk.frames)} frames between them): ${splatViews.walk.layout}. Red: paint in air the lidar measured empty; purple: under the bare ground. Click to play; the live demo is chapter 5.`, X0, 4.4, 8.0, 0.65);
  const f = (o, k) => o.free_space[k], fl = splatViews.verdict_still.mean_flagged_pixels;
  const rows = [[`${pct(f(plain, 'on_surfaces'))} → ${pct(f(taught, 'on_surfaces'))}`, 'of opaque Gaussians inside the measured volume sit on a lidar surface'], [`${pct(f(plain, 'buried'))} → ${pct(f(taught, 'buried'))}`, 'under the bare ground: the plain splat buries almost half its paint'],
    [`${pct(f(plain, 'in_free_air'))} → ${pct(f(taught, 'in_free_air'))}`, 'in air the lidar measured empty: floaters'], [`${pct(fl['tower-and-library'])} → ${pct(fl['tower-and-library-lidar-taught'])}`, 'of the pixels along this path are paint the lidar refutes'],
    [`${fmt(heldOut(plain), 1)} → ${fmt(heldOut(taught), 1)} dB`, `on held-out photographs (best-covered view ${fmt(plain.psnr_best_covered_view, 1)} → ${fmt(taught.psnr_best_covered_view, 1)} dB): no worse`]];
  rows.forEach(([big, label], i) => { const y = 1.4 + i * 1.08;
    text(s, big, { x: 8.9, y, w: 3.83, h: 0.4, fontSize: 18, bold: true, color: TERRA, fontFace: THEME.headFontFace });
    text(s, label, { x: 8.9, y: y + 0.42, w: 3.83, h: 0.62, fontSize: 11, color: SLATE }); });
  text(s, `One rule in training: opacity times metres into measured-empty air or under the bare ground; same photographs, same ${fmt(plain.steps)} steps.`, { x: X0, y: 5.2, w: 8.0, h: 0.8, fontSize: 13, bold: true, color: INK });
  text(s, 'Plain → lidar-taught is the same training with one added term; the "verdict" colouring is the referee score, computed for every Gaussian against the lidar rasters.', { x: X0, y: 6.05, w: 8.0, h: 0.8, fontSize: 12, color: SLATE }); }

// --- 23 · what is new, honestly ------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', 'What is new, what is next', 'What is new here, honestly');
  const hd = o => ({ text: o, options: { bold: true, color: INK, fill: { color: MIST } } });
  const rows = [[hd('Work'), hd('What it does'), hd('What differs here')],
    ['Kaminsky, Snavely, Seitz, Szeliski · CVPR Workshops 2009', 'SfM to an overhead image: points on its edges, free space; a 2D search', 'lidar heights, explicit metric cues, a diagnosis per number'],
    ['Wang, Wilson, Snavely · 3DV 2013', 'georegistration from Flickr geotags and Google Earth models', 'no geotags; public lidar and OpenStreetMap only'],
    ['Zhang et al. · Remote Sensing 2019', 'ground SfM to airborne lidar through building outlines, GPS-initialised', 'no GPS to start from; refusal when the geometry cannot fix a number'],
    ['Degeneracy-aware registration (Zhang, Kaess, Singh · ICRA 2016; X-ICP · 2023)', 'which directions a scan-to-map fit leaves undetermined', 'an SfM fragment of unknown scale, several heading candidates, cues from public maps'],
    ['Lidar-constrained Gaussian splatting (several, 2024–25)', 'lidar geometry as a training constraint', 'a per-Gaussian referee score, from public airborne lidar, in the placed frame']];
  s.addTable(rows, { x: X0, y: 1.4, w: W, colW: [3.9, 4.1, 4.13], fontSize: 12, color: SLATE, valign: 'middle', rowH: 0.6, border: { type: 'solid', pt: 0.75, color: 'D6DBDA' }, margin: [0.05, 0.1, 0.05, 0.1], objectName: 'related work' });
  card(s, X0, 5.25, W, 1.6, 'the claim');
  text(s, [{ text: 'The claim: ', options: { bold: true, color: TERRA } }, { text: 'cue-based grounding of sparse internet fragments without any GPS, against public lidar and footprints, with a per-number diagnosis that can refuse. A method-and-system claim.' }], { x: X0 + 0.25, y: 5.35, w: W - 0.5, h: 0.75, fontSize: 15, color: INK });
  text(s, [{ text: 'Not shown yet: ', options: { bold: true, color: RED } }, { text: 'that it beats a fair baseline; that the diagnosis cuts wrong acceptances; a second site.' }], { x: X0 + 0.25, y: 6.15, w: W - 0.5, h: 0.6, fontSize: 15, color: INK }); }

// --- 15 · still working on ------------------------------------------------------------------------------------------------
{ const s = slide('CONTENT', null, 'Still working on, as the final project');
  const hd = o => ({ text: o, options: { bold: true, color: INK, fill: { color: MIST } } });
  const rows = [[hd('The gap'), hd('The work'), hd('The hoped end')],
    [{ text: `One certified fragment of ${study.fragments.length}, no independent truth`, options: { bold: true, color: INK } }, 'my own phone photographs with GPS; held-out geotags that no fit ever reads', 'placement error measured, not inferred'],
    [{ text: 'No fair baseline yet', options: { bold: true, color: INK } }, 'footprint-only alignment; a Kaminsky-style edge-and-free-space fit; scale-aware point-cloud registration; this method without its diagnosis', 'the cues and the diagnosis shown to add capability, or shown not to'],
    [{ text: `The certificate is a heuristic: a ${fmt(cornerWrongEdge.roof_edge_error_m)} m roof-edge error passed with the scale ${pct(Math.abs(cornerWrongEdge.scale_ratio - 1))} off`, options: { bold: true, color: INK } }, 'acceptance coverage against false acceptances, on the synthetic hall and the real fragments; calibrate the bands', 'a certificate with a measured false-acceptance rate'],
    [{ text: 'One campus; the Arts Quad side blind; splats blurry', options: { bold: true, color: INK } }, 'more buildings here; a second campus that USGS 3DEP covers; photographs of the tower from the Arts Quad side', 'reproducible wherever USGS lidar and OpenStreetMap exist']];
  s.addTable(rows, { x: X0, y: 1.4, w: W, colW: [3.6, 5.0, 3.53], fontSize: 12, color: SLATE, valign: 'middle', rowH: 0.82, border: { type: 'solid', pt: 0.75, color: 'D6DBDA' }, margin: [0.06, 0.1, 0.06, 0.1], objectName: 'the plan' });
  card(s, X0, 5.8, W, 0.95, 'final project');
  text(s, [{ text: 'From a working pipeline to a tested method: ', options: { bold: true, color: TERRA } }, { text: 'the evaluation above, written up as a workshop paper. A method that places what can be placed and refuses what cannot, measured on two campuses.' }], { x: X0 + 0.25, y: 5.92, w: W - 0.5, h: 0.75, fontSize: 14, color: INK }); }

// --- 16 · closing ----------------------------------------------------------------------------------------------------
{ const s = slide('DARK_CLOSE', 'Close', 'COLMAP\'s frame is arbitrary. The world\'s isn\'t.');
  ['Placed with public lidar and footprints, no GPS', 'Refused, with the reason, when geometry can\'t fix it', 'New photographs placed in seconds'].forEach((t, i) => {
    s.addShape(pres.ShapeType.ellipse, { x: 0.72, y: 3.83 + i * 0.55, w: 0.2, h: 0.2, fill: { color: LIGHT }, line: { color: LIGHT, width: 0 }, objectName: 'point ' + (i + 1) });
    text(s, t, { x: 1.1, y: 3.72 + i * 0.55, w: 5.9, h: 0.45, fontSize: 16, color: WHITE }); });
  dots(s, 0.75, 5.6, DOF.map(() => 'ok'), { d: 0.3, step: 0.5, name: 'all fixed' });
  text(s, 'Questions? The demo stays open.   github.com/BobbyZbp/CS-6672', { x: 0.7, y: 6.25, w: 6.4, h: 0.45, fontSize: 14, color: 'A4ADB3' });
  const r = picture(s, still('snap.png'), 7.3, 1.55, 5.4, 4.4, 'The fragment placed in the lidar campus');
  caption(s, 'The tower-and-library fragment, placed.', r.x, r.y + r.h + 0.1, r.w, 0.4); }

// --- 17 · backup: the synthetic hall ------------------------------------------------------------------------------------
{ const s = slide('CONTENT', 'Backup', 'Backup · the synthetic hall');
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
  console.log(JSON.stringify({ deck: path.relative(ROOT, OUTPUT), slides: number, slides_without_notes: missing, constants: { eye_m: G.EYE_M, retrieve: L.RETRIEVE } }));
})();
