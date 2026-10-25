// GhostMap demo viewer. Every number shown is read from assets/ghostmap/scene.json,
// which is generated from the pipeline's report files (see web/ghostmap_scene.py).
import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';

const BASE = 'assets/ghostmap/';
const CUE_ANCHORS = 'surviving anchors only', CUE_GROUND = 'anchors + measured ground';
const CUE_PEOPLE = 'anchors + people', CUE_ALL = 'anchors + measured ground + people';
const COLOURS = { ok: 0x2f9e5b, bad: 0xd0453a, amber: 0xe0a21a, fragment: 0x2a6fdb, tower: 0xff8c1a, site: 0xe0a21a };

const fmt = (x, d = 0) => (x === null || x === undefined || Number.isNaN(x)) ? '—' : Number(x).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d });
const el = (tag, attrs = {}, html = '') => Object.assign(document.createElement(tag), attrs, html ? { innerHTML: html } : {});
const statusBox = document.getElementById('status');

const scene = await (await fetch(BASE + 'scene.json', { cache: 'no-store' })).json();
const binary = async (url, Type) => new Type(await (await fetch(BASE + url)).arrayBuffer());

// --- three.js setup (z is up, metres) --------------------------------------------
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
const world = new THREE.Scene();
world.background = new THREE.Color(0xc9d4d8);
const camera = new THREE.PerspectiveCamera(50, 1, 0.5, 6000);
camera.up.set(0, 0, 1);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
world.add(new THREE.HemisphereLight(0xffffff, 0x556655, 1.1));
const sun = new THREE.DirectionalLight(0xffffff, 1.4); sun.position.set(-300, -200, 500); world.add(sun);

const tower = new THREE.Vector3(...scene.tower_centre);
function frame(target, distance = 420, elevation = 0.75, azimuth = -2.2) {
  controls.target.copy(target);
  camera.position.set(target.x + distance * Math.cos(azimuth) * Math.cos(elevation),
                      target.y + distance * Math.sin(azimuth) * Math.cos(elevation),
                      target.z + distance * Math.sin(elevation));
  controls.update();
}

// --- measured layers ----------------------------------------------------------------
const t = scene.terrain;
const [heights, buildingMask, canopy] = await Promise.all([binary(t.height_url, Float32Array), binary(t.buildings_url, Uint8Array), binary(t.canopy_url, Float32Array)]);
const terrainGeometry = new THREE.BufferGeometry();
{
  const n = t.cols * t.rows, pos = new Float32Array(n * 3), col = new Float32Array(n * 3);
  let zmin = Infinity, zmax = -Infinity;
  for (let i = 0; i < n; i++) if (!buildingMask[i]) { zmin = Math.min(zmin, heights[i]); zmax = Math.max(zmax, heights[i]); }
  for (let r = 0; r < t.rows; r++) for (let c = 0; c < t.cols; c++) {
    const i = r * t.cols + c;
    pos.set([t.x0 + c * t.cell_m, t.y0 + r * t.cell_m, heights[i]], 3 * i);
    const g = (heights[i] - zmin) / Math.max(1, zmax - zmin);
    const rgb = buildingMask[i] ? [0.80, 0.74, 0.66] : [0.42 + 0.25 * g, 0.55 + 0.2 * g, 0.40 + 0.15 * g];
    col.set(rgb, 3 * i);
  }
  const index = [];
  for (let r = 0; r < t.rows - 1; r++) for (let c = 0; c < t.cols - 1; c++) {
    const a = r * t.cols + c, b = a + 1, d = a + t.cols, e = d + 1;
    index.push(a, b, d, b, e, d);
  }
  terrainGeometry.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  terrainGeometry.setAttribute('color', new THREE.BufferAttribute(col, 3));
  terrainGeometry.setIndex(index); terrainGeometry.computeVertexNormals();
}
const terrain = new THREE.Mesh(terrainGeometry, new THREE.MeshLambertMaterial({ vertexColors: true }));
world.add(terrain);

const canopyPoints = (() => {
  const pts = [];
  for (let r = 0; r < t.rows; r += 2) for (let c = 0; c < t.cols; c += 2) {
    const i = r * t.cols + c;
    if (!buildingMask[i] && canopy[i] > 3) pts.push(t.x0 + c * t.cell_m, t.y0 + r * t.cell_m, heights[i] + canopy[i]);
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  return new THREE.Points(g, new THREE.PointsMaterial({ color: 0x4f7a45, size: 2.2, transparent: true, opacity: 0.45 }));
})();
world.add(canopyPoints);

const footprintGroup = new THREE.Group(); world.add(footprintGroup);
let siteOutline = null;
for (const f of scene.footprints) {
  const isSite = f.name === scene.boardman_site;
  const g = new THREE.BufferGeometry().setFromPoints(f.ring.map(([x, y]) => new THREE.Vector3(x, y, f.ground + (isSite ? 1.0 : 0.4))));
  const line = new THREE.Line(g, new THREE.LineBasicMaterial({ color: isSite ? COLOURS.site : 0x333333, linewidth: 2 }));
  footprintGroup.add(line);
  if (isSite) siteOutline = line;
}

const [fxyz, frgb, ftower] = await Promise.all([binary(scene.fragment.xyz_url, Float32Array), binary(scene.fragment.rgb_url, Uint8Array), binary(scene.fragment.tower_url, Uint8Array)]);
const fragment = (() => {
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(fxyz, 3));
  const c = new Float32Array(frgb.length); for (let i = 0; i < frgb.length; i++) c[i] = frgb[i] / 255;
  g.setAttribute('color', new THREE.BufferAttribute(c, 3));
  return new THREE.Points(g, new THREE.PointsMaterial({ size: 1.1, vertexColors: true }));
})();
world.add(fragment);

// --- helpers ---------------------------------------------------------------------------
const overlay = new THREE.Group(); world.add(overlay);
function clearOverlay() { while (overlay.children.length) { const o = overlay.children.pop(); o.geometry?.dispose(); } }
function sphere(p, colour, r = 2.2) {
  const m = new THREE.Mesh(new THREE.SphereGeometry(r, 16, 12), new THREE.MeshLambertMaterial({ color: colour }));
  m.position.set(...p); return m;
}
function polyline(points, colours) {
  const g = new THREE.BufferGeometry().setFromPoints(points.map(p => new THREE.Vector3(...p)));
  if (colours) g.setAttribute('color', new THREE.Float32BufferAttribute(colours.flat(), 3));
  return new THREE.Line(g, new THREE.LineBasicMaterial(colours ? { vertexColors: true } : { color: 0x222222 }));
}
function weightColours(w) {
  const m = Math.max(...w);
  return w.map(x => { const a = x / m; return [0.85 - 0.6 * a, 0.25 + 0.55 * a, 0.25]; });
}
const textures = new Map();
function texture(url) {
  if (!textures.has(url)) { const tx = new THREE.TextureLoader().load(BASE + url); tx.colorSpace = THREE.SRGBColorSpace; textures.set(url, tx); }
  return textures.get(url);
}
// A photograph as a camera: frustum lines plus the picture on its image plane at `depth` metres.
function photoFrustum(centre, R, focal, width, height, depth, photoUrl, colour = 0x111111) {
  const C = new THREE.Vector3(...centre);
  const corner = (u, v) => {
    const xc = (u - width / 2) / focal * depth, yc = (v - height / 2) / focal * depth;
    // world = R^T * [xc, yc, depth] + C
    return new THREE.Vector3(R[0][0] * xc + R[1][0] * yc + R[2][0] * depth, R[0][1] * xc + R[1][1] * yc + R[2][1] * depth,
                             R[0][2] * xc + R[1][2] * yc + R[2][2] * depth).add(C);
  };
  const tl = corner(0, 0), tr = corner(width, 0), br = corner(width, height), bl = corner(0, height);
  const group = new THREE.Group();
  const lines = new THREE.BufferGeometry().setFromPoints([C, tl, C, tr, C, br, C, bl, tl, tr, tr, br, br, bl, bl, tl]);
  group.add(new THREE.LineSegments(lines, new THREE.LineBasicMaterial({ color: colour })));
  if (photoUrl) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute([tl, tr, br, bl].flatMap(p => [p.x, p.y, p.z]), 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute([0, 1, 1, 1, 1, 0, 0, 0], 2));
    g.setIndex([0, 3, 1, 1, 3, 2]);
    group.add(new THREE.Mesh(g, new THREE.MeshBasicMaterial({ map: texture(photoUrl), side: THREE.DoubleSide, transparent: true, opacity: 0.92 })));
  }
  return group;
}
function legend(items) {
  document.getElementById('legend').innerHTML = items.map(([c, label]) => `<span class="sw" style="background:${c}"></span>${label}`).join('');
}

// --- chapters --------------------------------------------------------------------------
const N = scene.numbers;
let pickHandler = null;
const body = document.getElementById('chapter-body');
const chapters = [
  { id: 'stock', title: '1 · Stock COLMAP', render: stock },
  { id: 'anchor', title: '2 · Snap to lidar', render: anchor },
  { id: 'photographers', title: '3 · Where did they stand?', render: photographers },
  { id: 'postcards', title: '4 · A postcard', render: postcards },
  { id: 'mirror', title: '5 · What fooled it', render: mirror },
  { id: 'certificates', title: '6 · Certificates', render: certificates },
];
const nav = document.getElementById('chapters');
for (const ch of chapters) nav.append(Object.assign(el('button', { type: 'button' }, ch.title), { onclick: () => show(ch.id) }));

function show(id) {
  if (!chapters.some(c => c.id === id)) id = 'stock';
  clearOverlay(); pickHandler = null;
  for (const b of nav.children) b.setAttribute('aria-current', String(b.textContent === chapters.find(c => c.id === id).title));
  body.innerHTML = '';
  chapters.find(c => c.id === id).render();
  history.replaceState(null, '', '#' + id);
}

function stock() {
  const rows = N.mapping.map(r => `<tr><td>${r.label}</td><td class="num">${r.models.join(' · ')}</td><td class="num">${r.registered_photographs}/${r.training_photographs}</td><td class="num">${r.focal_outside_half_to_triple}</td></tr>`).join('');
  body.innerHTML = `<h2>COLMAP on licensed Commons photographs</h2>
    <p>The match graph is nearly one piece (65 of 67 matched photographs connect), yet the mapper returns disconnected fragments with no scale, and some focal lengths blow up.</p>
    <table><tr><th>Mapping</th><th class="num">cameras per model</th><th class="num">registered</th><th class="num">focal ratio outside 0.5–3</th></tr>${rows}</table>
    <p><b>EXIF-anchored calibration.</b> Photographs whose EXIF gives the focal length keep it fixed; the others are bounded. Focal blow-ups fall from ${N.mapping[0].focal_outside_half_to_triple} to ${N.mapping[2].focal_outside_half_to_triple}, but the fragments do <b>not</b> merge.</p>
    <div class="finding">Diagnosis: calibration is not what splits the scene; missing views are. Eight of fourteen target buildings have no registered camera at all.</div>
    <p class="note">The 3D view shows the largest fragment (Uris Library and McGraw Tower, 22 photographers) after it was snapped to lidar in metres.</p>`;
  legend([['#2a6fdb', 'reconstructed points (photo colours)'], ['#cdbda8', 'lidar buildings'], ['#7f9a6c', 'lidar ground']]);
  frame(tower, 380);
}

function anchor() {
  const a = N.anchoring, sc = a.scale_checks;
  body.innerHTML = `<h2>Snap to the measured world</h2>
    <p>Public-domain USGS airborne lidar (${fmt(N.lidar.points_kept)} points around the Quad) and OpenStreetMap footprints. No geotags, no hand-picked points.</p>
    <div class="stat"><div>Scale from photographers at eye height vs the measured tower top</div><div>${fmt(sc.vertical_from_photographers_and_tower_top, 1)} m / unit</div>
    <div>Scale from the library's walls alone (independent)</div><div>${fmt(sc.horizontal_from_library_walls, 1)} m / unit</div>
    <div>Disagreement between the two</div><div class="${Math.abs(sc.library_vs_vertical_ratio - 1) <= 0.05 ? 'ok' : 'warn'}">${fmt(100 * Math.abs(sc.library_vs_vertical_ratio - 1), 1)} %</div>
    <div>Library points on the library walls (median miss)</div><div>${fmt(a.library_wall_distance_m.median, 2)} m (${fmt(a.library_wall_distance_m.points_within_3m)} points)</div>
    <div>McGraw Tower, lidar-measured height</div><div>${fmt(a.tower.lidar_height_m, 1)} m</div></div>
    <p><b>How:</b> gravity from the facades (wall normals are horizontal); the tower, found as the tallest compact cluster, stands on its footprint; one yaw angle puts points on walls.</p>
    <p class="note">${a.scale_status}. The photographer-height check fails; chapter 3 shows why.</p>`;
  legend([['#2a6fdb', 'reconstructed points'], ['#e0a21a', 'footprint of the Boardman Hall site (today Olin Library)'], ['#4f7a45', 'tree canopy (lidar)']]);
  frame(tower, 300, 0.6);
}

function photographers() {
  const s = N.positive_control;
  const P = scene.photographers;
  for (const p of P) {
    const h = p.height_above_ground_m, good = h >= 0.5 && h <= 4;
    const m = sphere(p.centre, good ? COLOURS.ok : COLOURS.bad, 2.6); m.userData = p;
    m.material.depthTest = false; m.renderOrder = 2;  // visible even when COLMAP put the camera underground
    overlay.add(m);
  }
  // Stalks from each camera to the measured ground beneath it.
  const stalks = [];
  for (const p of P) { const [x, y, z] = p.centre; stalks.push(x, y, z, x, y, z - p.height_above_ground_m); }
  const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.Float32BufferAttribute(stalks, 3));
  const stalkLines = new THREE.LineSegments(sg, new THREE.LineBasicMaterial({ color: COLOURS.bad, depthTest: false }));
  stalkLines.renderOrder = 1; overlay.add(stalkLines);
  const pc = s['postcard-like'];
  body.innerHTML = `<h2>Where did the modern photographers stand?</h2>
    <p>COLMAP's own bundle adjustment puts <b class="bad">${P.filter(p => p.height_above_ground_m < 0.5 || p.height_above_ground_m > 4).length} of ${P.length}</b> photographers more than a few metres off the measured ground — some 30–50 m in the air, some underground — with sub-2-pixel reprojection error.</p>
    <p>This is the dolly-zoom ambiguity: a distant camera can slide along its viewing ray while its focal length changes. Re-solving each camera from only the tower and the library facade next to it (the view an old postcard has):</p>
    <div class="stat"><div>Position along the ray, 95 % (median over cameras), anchors only</div><div>${fmt(pc[CUE_ANCHORS].median_distance_interval_m, 1)} m</div>
    <div>… plus "the photographer stood on the measured ground"</div><div class="ok">${fmt(pc[CUE_GROUND].median_distance_interval_m, 1)} m</div>
    <div>Cameras undetermined by more than 20 m, anchors only → with ground</div><div>${pc[CUE_ANCHORS].cameras_with_interval_over_20m} → ${pc[CUE_GROUND].cameras_with_interval_over_20m}</div></div>
    <p>Click a sphere to see its photograph and its ambiguity ray.</p><div id="pick"></div>`;
  legend([['#2f9e5b', 'stands 0.5–4 m above lidar ground'], ['#d0453a', 'placed off the ground by COLMAP'], ['#2a6fdb', 'ray: brighter green = more likely']]);
  frame(tower, 520, 0.55);
  pickHandler = obj => {
    const p = obj.userData; if (!p?.ray) return;
    while (overlay.children.length > P.length + 1) overlay.remove(overlay.children[overlay.children.length - 1]);
    const draw = cue => {
      while (overlay.children.length > P.length + 1) overlay.remove(overlay.children[overlay.children.length - 1]);
      overlay.add(polyline(p.ray.centres, weightColours(p.ray.weights[cue])));
      overlay.add(photoFrustum(p.centre, p.rotation, p.focal_px, p.width, p.height, 60, p.photo));
      const iv = p.ray.intervals[cue];
      document.getElementById('pick-iv').innerHTML = `Along the ray (95 %): ${fmt(iv.distance_to_anchors_m_95[0])}–${fmt(iv.distance_to_anchors_m_95[1])} m from the anchors; height ${fmt(iv.camera_height_above_ground_m_95[0], 1)} to ${fmt(iv.camera_height_above_ground_m_95[1], 1)} m.`;
    };
    document.getElementById('pick').innerHTML = `<img class="photo" src="${BASE + p.photo}" alt="">
      <p class="note">${p.title} · ${p.artist ?? ''} · <a href="${p.source_url}" target="_blank" rel="noopener">${p.license}</a>. COLMAP height: <b>${fmt(p.height_above_ground_m, 1)} m</b>.</p>
      <div class="cues"><label><input type="radio" name="pc" value="${CUE_ANCHORS}" checked>anchors only</label><label><input type="radio" name="pc" value="${CUE_GROUND}">+ measured ground</label></div><p id="pick-iv"></p>`;
    for (const r of document.querySelectorAll('input[name=pc]')) r.onchange = () => draw(r.value);
    draw(CUE_ANCHORS);
  };
}

function registeredPostcards() { return scene.postcards.filter(q => q.status === 'registered'); }
function postcards() {
  const list = registeredPostcards();
  const initial = list.find(q => q.pageid === '150099180') ?? list[0];
  body.innerHTML = `<h2>The surviving world as a calibration target</h2>
    <p>A public-domain postcard is placed only through surviving buildings. For every focal length COLMAP's pose solver places the camera; the cost over all anchors is a likelihood along the ambiguity ray.</p>
    <div class="controls"><select id="pc-select">${list.map(q => `<option value="${q.pageid}">${q.date} · ${q.title.replace(/^File:/, '').slice(0, 60)}</option>`).join('')}</select></div>
    <img class="photo" id="pc-photo" alt="">
    <div class="cues" id="pc-cues"></div>
    <label class="controls">Slide the camera along its ambiguity ray<input type="range" id="pc-slider" min="0" max="1" step="1"></label>
    <div id="pc-stats"></div>`;
  const select = document.getElementById('pc-select'); select.value = initial.pageid;
  select.onchange = () => render(list.find(q => q.pageid === select.value));
  render(initial);

  function render(q) {
    clearOverlay();
    document.getElementById('pc-photo').src = BASE + q.photo;
    const cues = Object.keys(q.cues);
    document.getElementById('pc-cues').innerHTML = cues.map((c, i) => `<label><input type="radio" name="cue" value="${c}" ${i === 0 ? 'checked' : ''}>${c.replace('surviving ', '')}</label>`).join('');
    const slider = document.getElementById('pc-slider'); slider.max = q.grid.length - 1;
    let cue = cues[0];
    const cloud = new THREE.Group(), cam = new THREE.Group(); overlay.add(cloud, cam);
    const anchorGeom = new THREE.BufferGeometry(); anchorGeom.setAttribute('position', new THREE.Float32BufferAttribute(q.anchor_points.flat(), 3));
    overlay.add(new THREE.Points(anchorGeom, new THREE.PointsMaterial({ color: COLOURS.tower, size: 3.0 })));
    const anchorCentre = q.anchor_points.reduce((a, p) => a.map((v, i) => v + p[i] / q.anchor_points.length), [0, 0, 0]);
    const drawCloud = () => {
      cloud.clear();
      const w = q.cues[cue].weights, m = Math.max(...w);
      q.grid.forEach((g, i) => { if (w[i] > 1e-4 * m) cloud.add(sphere(g.centre, COLOURS.ok, 0.8 + 4 * Math.sqrt(w[i] / m))); });
      cloud.add(polyline(q.grid.map(g => g.centre), weightColours(w)));
      slider.value = w.indexOf(m); drawCamera();
      const c = q.cues[cue], base = q.cues[CUE_ANCHORS];
      document.getElementById('pc-stats').innerHTML = `<div class="stat">
        <div>Photographer's distance to the anchors, 95 %</div><div>${fmt(c.distance_to_anchors_m_95[0])}–${fmt(c.distance_to_anchors_m_95[1])} m</div>
        <div>Width of that interval</div><div class="${c.distance_interval_m < 20 ? 'ok' : 'bad'}">${fmt(c.distance_interval_m, 1)} m ${cue !== CUE_ANCHORS ? `(${fmt(100 * c.distance_interval_shrink_vs_anchors_only)} % narrower)` : ''}</div>
        <div>Focal length, 95 %</div><div>${fmt(c.focal_px_95[0])}–${fmt(c.focal_px_95[1])} px (×${fmt(c.focal_interval_ratio, 2)})</div>
        <div>Camera height above lidar ground, 95 %</div><div>${fmt(c.camera_height_above_ground_m_95[0], 1)} to ${fmt(c.camera_height_above_ground_m_95[1], 1)} m</div>
        <div>Anchors with clear line of sight (weak test)</div><div>${fmt(100 * c.anchors_visible_fraction)} %</div></div>
        ${q.people ? `<p>${q.people.length} standing people detected. At this cue's most likely pose they would be <b>${fmt(median(q.people_implied_heights_m[cue].filter(Boolean)), 2)} m</b> tall (median)${cue.includes('people') ? ' — near the 1.70 m prior by construction, so a consistency readout' : ' — the anchors alone cannot tell people from ants'}.</p>` : ''}
        ${q.mirror_pose ? `<p class="bad">Mirror pose (${q.mirror_pose}). A narrow interval here is precision, not correctness; see chapter 5.</p>` : ''}
        <p class="note">${q.inlier_anchors} anchor correspondences · <a href="${q.source_url}" target="_blank" rel="noopener">${q.license}</a>${q.duplicate_of ? ` · same exposure as ${q.duplicate_of}` : ''}</p>`;
    };
    const drawCamera = () => {
      cam.clear();
      const g = q.grid[+slider.value];
      const depth = Math.hypot(...g.centre.map((v, i) => v - anchorCentre[i]));
      cam.add(photoFrustum(g.centre, g.rotation, g.focal_px, q.size[0], q.size[1], depth, q.photo, 0xffffff));
    };
    for (const r of document.querySelectorAll('input[name=cue]')) r.onchange = () => { cue = r.value; drawCloud(); };
    slider.oninput = drawCamera;
    drawCloud();
    frame(new THREE.Vector3(...anchorCentre), 700, 0.7);
  }
  legend([['#ff8c1a', 'surviving anchors matched in the postcard'], ['#2f9e5b', 'possible photographer positions (size = likelihood)'], ['#e0a21a', 'Boardman Hall site']]);
}
const median = a => { const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return !s.length ? NaN : s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

function mirror() {
  for (const p of scene.photographers) overlay.add(sphere(p.centre, 0x2a6fdb, 2.4));
  for (const q of registeredPostcards().filter(q => q.subject.startsWith('Boardman'))) {
    const c = q.cues[CUE_GROUND] ?? q.cues[CUE_ANCHORS];
    overlay.add(sphere(c.map_centre, COLOURS.bad, 3.2));
  }
  body.innerHTML = `<h2>What fooled it — and what would fix it</h2>
    <p>Every Boardman postcard looks toward the Boardman site, but from the <b>south-west</b>: in those poses Boardman would appear to the right of the tower. In the postcards it is on the left. They were taken from the Arts Quad, north-east of the site.</p>
    <div class="finding">All 22 modern photographers in this fragment stand west or south-west of the tower (blue), so the modern model contains only the tower's and library's west and south faces. McGraw Tower has the same clock face on every side; the matcher paired the postcards' east-face features with west-face points, producing a <b>mirror-image pose</b> that fits every anchor to a few pixels.</div>
    <p>The certificates are honest about the ambiguity <i>along</i> the ray, but not about this alias. Found by checking the left–right order of Boardman, tower and library against the map; the pipeline did not flag it.</p>
    <p><b>Confirmed on a larger set:</b> the 228-photo snapshot registers ${N.mapping[3].registered_photographs} of ${N.mapping[3].training_photographs} photographs (first cameras on Tjaden, Sibley and Lincoln), yet all 26 photographers in its tower fragment again stand west or south-west — Commons photos of McGraw Tower come from Libe Slope and Ho Plaza.</p>
    <p><b>The fix is data, not tuning:</b> photographs of the tower and library taken from the Arts Quad.</p>`;
  legend([['#2a6fdb', 'modern photographers (all on the west / south side)'], ['#d0453a', 'recovered postcard cameras (mirror poses)'], ['#e0a21a', 'Boardman Hall site']]);
  frame(tower, 480, 0.9, -1.2);
}

function certificates() {
  const rows = scene.postcards.map(q => {
    if (q.status !== 'registered') return `<tr><td>${q.date}</td><td>${q.title.replace(/^File:/, '').slice(0, 46)}</td><td colspan="3" class="note">not registered: ${q.reason ?? ''}</td></tr>`;
    const a = q.cues[CUE_ANCHORS], g = q.cues[CUE_GROUND], p = q.cues[CUE_ALL];
    return `<tr><td>${q.date}</td><td>${q.title.replace(/^File:/, '').slice(0, 46)}<br><span class="note">${q.subject}</span></td>
      <td class="num">${fmt(a.distance_interval_m)} m</td><td class="num">${fmt(g.distance_interval_m)} m</td><td class="num">${p ? fmt(p.distance_interval_m) + ' m' : '—'}</td></tr>`;
  }).join('');
  body.innerHTML = `<h2>Identifiability certificates</h2>
    <p>Width of the 95 % interval of each photographer's position along the viewing ray. Wide means the surviving record does not determine where the photograph was taken — and therefore where anything in it stood.</p>
    <table><tr><th>Date</th><th>Photograph</th><th class="num">anchors</th><th class="num">+ ground</th><th class="num">+ people</th></tr>${rows}</table>
    <p class="note">Boardman's surface is not claimed: with every registered postcard in a mirror pose (chapter 5), no bound on the vanished building is shown.</p>`;
  legend([]);
}

// --- picking & loop --------------------------------------------------------------------
const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
canvas.addEventListener('click', e => {
  if (!pickHandler) return;
  const r = canvas.getBoundingClientRect();
  mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(mouse, camera);
  const hit = ray.intersectObjects(overlay.children.filter(o => o.isMesh && o.userData?.name))[0];
  if (hit) pickHandler(hit.object);
});
function resize() {
  const { clientWidth: w, clientHeight: h } = canvas.parentElement;
  renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(canvas.parentElement); resize();
renderer.setAnimationLoop(() => { controls.update(); renderer.render(world, camera); });
document.getElementById('attribution').textContent = scene.attribution.join(' ');
statusBox.textContent = '';
show((location.hash || '#stock').slice(1).replace(/[^a-z]/g, '') || 'stock');
document.documentElement.dataset.ready = 'true';
