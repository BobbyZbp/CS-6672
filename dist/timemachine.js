// Cornell Time Machine viewer. All numbers come from assets/timemachine/scene.json
// (built by web/timemachine_scene.py from report files); nothing is typed in here.
import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';

const BASE = 'assets/timemachine/';
const fmt = (x, d = 0) => (x === null || x === undefined || Number.isNaN(x)) ? '—' : Number(x).toLocaleString('en-US', { maximumFractionDigits: d });
const el = (tag, attrs = {}, html = '') => Object.assign(document.createElement(tag), attrs, html ? { innerHTML: html } : {});
const scene = await (await fetch(BASE + 'scene.json', { cache: 'no-store' })).json();
const binary = async (url, Type) => new Type(await (await fetch(BASE + url)).arrayBuffer());
const YEARS = scene.years.map(Number);
const MIN_YEAR = 2002, MAX_YEAR = 2026;

// --- three.js ---------------------------------------------------------------------------
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
renderer.outputColorSpace = THREE.SRGBColorSpace;
const world = new THREE.Scene(); world.background = new THREE.Color(0xdfe6ea);
const camera = new THREE.PerspectiveCamera(48, 1, 0.5, 8000); camera.up.set(0, 0, 1);
const controls = new OrbitControls(camera, canvas); controls.enableDamping = true; controls.maxPolarAngle = Math.PI / 2 - 0.02;
world.add(new THREE.HemisphereLight(0xffffff, 0x8a9a7a, 1.0));
const sun = new THREE.DirectionalLight(0xffffff, 1.1); sun.position.set(-400, -300, 600); world.add(sun);

let flight = null;
function flyTo(target, distance, elevation = 0.7, azimuth = -2.0, seconds = 1.4) {
  const from = { pos: camera.position.clone(), tgt: controls.target.clone() };
  const to = { tgt: new THREE.Vector3(...target) };
  to.pos = new THREE.Vector3(to.tgt.x + distance * Math.cos(azimuth) * Math.cos(elevation), to.tgt.y + distance * Math.sin(azimuth) * Math.cos(elevation), to.tgt.z + distance * Math.sin(elevation));
  flight = { from, to, t0: performance.now(), ms: seconds * 1000 };
}
function stepFlight() {
  if (!flight) return;
  const s = Math.min(1, (performance.now() - flight.t0) / flight.ms), e = s < .5 ? 2 * s * s : 1 - Math.pow(-2 * s + 2, 2) / 2;
  camera.position.lerpVectors(flight.from.pos, flight.to.pos, e); controls.target.lerpVectors(flight.from.tgt, flight.to.tgt, e);
  if (s >= 1) flight = null;
}

// --- terrain draped with the selected year's aerial image -----------------------------------
const loader = new THREE.TextureLoader();
const textures = {};
function texture(url) {
  if (!textures[url]) { const t = loader.load(BASE + url); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; textures[url] = t; }
  return textures[url];
}
const qt = scene.sites.quad.terrain;  // extent of the Quad terrain grid, used to trim the other sites' terrains
const quadExtent = [qt.x0, qt.y_top - (qt.rows - 1) * qt.cell_m, qt.x0 + (qt.cols - 1) * qt.cell_m, qt.y_top];
const terrains = {};
const changed = scene.buildings.filter(b => b.documented && !b.documented.stable);
function presentFrom(b) {
  const d = b.documented; const y = (d.dedicated || d.completed || d.opened || d.occupied || '').slice(0, 4); return y ? +y : null;
}
function worksFrom(b) { const d = b.documented; return d.construction_start ? +d.construction_start.slice(0, 4) : null; }
function inside(ring, x, y) {  // ray casting
  let c = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c;
  }
  return c;
}
for (const [site, s] of Object.entries(scene.sites)) {
  const t = s.terrain;
  const [heights, mask] = await Promise.all([binary(t.height_url, Float32Array), binary(t.buildings_url, Uint8Array)]);
  const n = t.rows * t.cols, pos = new Float32Array(n * 3), uv = new Float32Array(n * 2);
  for (let r = 0; r < t.rows; r++) for (let c = 0; c < t.cols; c++) {
    const i = r * t.cols + c, x = t.x0 + c * t.cell_m, y = t.y_top - r * t.cell_m;
    pos.set([x, y, heights[i] + t.z_offset], 3 * i); uv.set([c / (t.cols - 1), 1 - r / (t.rows - 1)], 2 * i);
  }
  const index = [];
  // Cells of the other sites that lie wholly under the Quad terrain are dropped; cells straddling its edge are kept,
  // so the meshes overlap by up to one cell instead of leaving a gap (the overlap is pushed back by polygon offset).
  const clip = site !== 'quad';
  const under = (i) => { const x = pos[3 * i], y = pos[3 * i + 1]; return x >= quadExtent[0] && x <= quadExtent[2] && y >= quadExtent[1] && y <= quadExtent[3]; };
  for (let r = 0; r < t.rows - 1; r++) for (let c = 0; c < t.cols - 1; c++) {
    const a = r * t.cols + c, b = a + 1, d = a + t.cols, e = d + 1;
    if (clip && under(a) && under(b) && under(d) && under(e)) continue;
    index.push(a, d, b, b, d, e);  // y decreases with the row index: this winding faces up
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.BufferAttribute(uv, 2)); g.setIndex(index); g.computeVertexNormals();
  const mesh = new THREE.Mesh(g, new THREE.MeshLambertMaterial({ map: null, polygonOffset: clip, polygonOffsetFactor: 1, polygonOffsetUnits: 1 }));
  world.add(mesh);
  // Vertices inside each changed building's footprint: flattened to the ground for years before it stood.
  const flats = [];
  for (const b of changed.filter(b => b.site === site)) {
    const idx = [];
    for (let i = 0; i < n; i++) if (inside(b.ring, pos[3 * i], pos[3 * i + 1])) idx.push(i);
    flats.push({ building: b, idx, original: idx.map(i => pos[3 * i + 2]) });
  }
  // Steep faces are building walls in the lidar surface; they get a flat wall colour instead of the aerial image
  // smeared down them. Walls of a changed building are listed with it, so they vanish when its site is flattened.
  const owner = new Int32Array(n).fill(-1);
  flats.forEach((f, k) => { f.walls = []; f.idx.forEach(i => owner[i] = k); });
  const wallsStatic = [];
  for (let k = 0; k < index.length; k += 3) {
    const i0 = index[k], i1 = index[k + 1], i2 = index[k + 2];
    const ax = pos[3 * i1] - pos[3 * i0], ay = pos[3 * i1 + 1] - pos[3 * i0 + 1], az = pos[3 * i1 + 2] - pos[3 * i0 + 2];
    const bx = pos[3 * i2] - pos[3 * i0], by = pos[3 * i2 + 1] - pos[3 * i0 + 1], bz = pos[3 * i2 + 2] - pos[3 * i0 + 2];
    const nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx;
    if (nz / Math.hypot(nx, ny, nz) > 0.5) continue;  // flatter than 60 degrees: ground, lawn or roof
    const o = Math.max(owner[i0], owner[i1], owner[i2]);
    (o < 0 ? wallsStatic : flats[o].walls).push(i0, i1, i2);
  }
  const wg = new THREE.BufferGeometry(); wg.setAttribute('position', g.getAttribute('position')); wg.setIndex(wallsStatic); wg.computeVertexNormals();
  world.add(new THREE.Mesh(wg, new THREE.MeshLambertMaterial({ color: 0xbdb7aa, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 })));
  terrains[site] = { mesh, geometry: g, flats, walls: wg, wallsStatic, wallKey: '', box: s.ortho_box_local, orthos: s.orthoimagery };
}

// --- footprints and lidar volumes of the changed buildings ----------------------------------
const outlines = new THREE.Group(), volumes = new THREE.Group(); world.add(outlines, volumes);
for (const b of scene.buildings) {
  const z = b.ground + 0.6;
  const g = new THREE.BufferGeometry().setFromPoints(b.ring.map(([x, y]) => new THREE.Vector3(x, y, z)));
  const line = new THREE.Line(g, new THREE.LineBasicMaterial({ color: b.documented ? 0xb5532c : 0x303030, transparent: true, opacity: b.documented ? 1 : 0.55 }));
  line.userData = b; outlines.add(line);
  if (b.documented && !b.documented.stable) {
    const shape = new THREE.Shape(b.ring.map(([x, y]) => new THREE.Vector2(x, y)));
    const geom = new THREE.ExtrudeGeometry(shape, { depth: Math.max(3, b.lidar_top - b.ground), bevelEnabled: false });
    const vol = new THREE.Mesh(geom, new THREE.MeshLambertMaterial({ color: 0xe9d9c0, transparent: true, opacity: 0.85 }));
    vol.position.z = b.ground; vol.userData = b; volumes.add(vol);
    const wire = new THREE.LineSegments(new THREE.EdgesGeometry(geom, 20), new THREE.LineBasicMaterial({ color: 0xb5532c }));
    wire.position.z = b.ground; wire.userData = { works: b }; volumes.add(wire);
  }
}

// --- reconstructed points with their observed intervals ---------------------------------------
const clouds = [];
for (const r of scene.reconstructions) {
  const [xyz, rgb, first, last] = await Promise.all([binary(r.xyz_url, Float32Array), binary(r.rgb_url, Uint8Array), binary(r.first_url, Int16Array), binary(r.last_url, Int16Array)]);
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(xyz, 3));
  const colour = new Float32Array(rgb.length); for (let i = 0; i < rgb.length; i++) colour[i] = rgb[i] / 255;
  g.setAttribute('color', new THREE.BufferAttribute(colour, 3));
  const pts = new THREE.Points(g, new THREE.PointsMaterial({ size: 1.3, vertexColors: true }));
  world.add(pts); clouds.push({ pts, g, rgb: colour, first, last, meta: r });
}
const photographerGroup = new THREE.Group(); world.add(photographerGroup);
for (const p of scene.photographers) {
  const m = new THREE.Mesh(new THREE.SphereGeometry(1.8, 12, 10), new THREE.MeshLambertMaterial({ color: 0x2a6fdb }));
  m.position.set(...p.centre); m.userData = p; photographerGroup.add(m);
}

// --- time ---------------------------------------------------------------------------------------
let year = MIN_YEAR; let colourMode = 'photo';
function flightYearFor(y) { let best = YEARS[0]; for (const f of YEARS) if (f <= y) best = f; return best; }
function state(b, y) {
  if (!b.documented) return null;
  if (b.documented.stable) return 'stable';
  const from = presentFrom(b), works = worksFrom(b);
  if (from !== null && y >= from) return 'present';
  if (works !== null && y >= works) return 'works';
  return 'before';
}
function setYear(y) {
  year = y; document.getElementById('year').textContent = y; document.getElementById('slider').value = y;
  const fy = flightYearFor(y);
  for (const t of Object.values(terrains)) {
    const o = t.orthos[String(fy)]; if (o) t.mesh.material.map = texture(o.url); t.mesh.material.needsUpdate = true;
    const z = t.geometry.attributes.position;
    for (const f of t.flats) { const s = state(f.building, y); f.idx.forEach((i, k) => z.setZ(i, s === 'present' ? f.original[k] : f.building.ground + 0.1)); }
    z.needsUpdate = true;
    // Which changed buildings stand this year decides the flattened sites, so the walls and normals follow that key.
    const key = t.flats.map(f => state(f.building, y) === 'present' ? '1' : '0').join('');
    if (key !== t.wallKey) {
      t.wallKey = key; t.geometry.computeVertexNormals();
      t.walls.setIndex(t.wallsStatic.concat(...t.flats.filter((f, k) => key[k] === '1').map(f => f.walls))); t.walls.computeVertexNormals();
    }
  }
  for (const v of volumes.children) {
    const b = v.userData.works || v.userData; const s = state(b, y);
    v.visible = v.userData.works ? s === 'works' : s === 'present';
  }
  for (const c of clouds) {
    const col = c.g.attributes.color;
    for (let i = 0; i < c.first.length; i++) {
      const seen = c.first[i] > 0 && c.first[i] <= y;
      if (colourMode === 'first') { const h = seen ? (c.first[i] - 2002) / 24 : 0; col.setXYZ(i, seen ? 0.2 + 0.8 * h : 0.6, seen ? 0.9 - 0.7 * h : 0.6, seen ? 0.4 : 0.6); }
      else col.setXYZ(i, seen ? c.rgb[3 * i] : 0.75, seen ? c.rgb[3 * i + 1] : 0.75, seen ? c.rgb[3 * i + 2] : 0.75);
    }
    col.needsUpdate = true;
  }
  for (const m of photographerGroup.children) { const py = m.userData.year; m.visible = py !== null; m.material.color.set(py === y ? 0xd0453a : py && py < y ? 0x2a6fdb : 0x9aa5b1); m.scale.setScalar(py === y ? 1.8 : 1); }
  document.getElementById('basis').textContent = `aerial image: ${fy} flight (${y === fy ? 'same year' : 'latest before ' + y}) · buildings by documented dates · points by photograph dates`;
  for (const f of document.querySelectorAll('.strip figure')) f.classList.toggle('on', +f.dataset.year === fy);
  for (const bar of document.querySelectorAll('.yearbar div')) bar.classList.toggle('on', +bar.dataset.year === y);
  for (const badge of document.querySelectorAll('[data-state-of]')) {
    const b = scene.buildings.find(x => x.name === badge.dataset.stateOf), s = state(b, y);
    badge.className = 'state ' + s; badge.textContent = { before: 'not yet built — ' + (b.documented.before || 'site before construction'), works: 'under construction', present: 'standing', stable: 'unchanged' }[s];
  }
}
const slider = document.getElementById('slider'); slider.oninput = () => setYear(+slider.value);
document.getElementById('ticks').innerHTML = Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i).filter(y => y % 2 === 0 || YEARS.includes(y)).map(y => `<span class="${YEARS.includes(y) ? 'flight' : ''}">${y % 4 === 2 || YEARS.includes(y) ? y : ''}</span>`).join('');
let timer = null;
function play() { if (timer) { clearInterval(timer); timer = null; return; } timer = setInterval(() => setYear(year >= MAX_YEAR ? MIN_YEAR : year + 1), 700); }

// --- chapters -------------------------------------------------------------------------------------
const body = document.getElementById('chapter-body'), nav = document.getElementById('chapters');
function legend(items) { document.getElementById('legend').innerHTML = items.map(([c, l]) => `<span class="sw" style="background:${c}"></span>${l}`).join(''); }
function centroid(ring) { const n = ring.length - 1 || 1; return [ring.slice(0, n).reduce((a, p) => a + p[0], 0) / n, ring.slice(0, n).reduce((a, p) => a + p[1], 0) / n]; }
function building(name) { return scene.buildings.find(b => b.name === name); }
function strip(b) {
  return `<div class="strip">${Object.entries(b.aerial_crops || {}).map(([y, u]) => `<figure data-year="${y}"><img src="${BASE + u}" alt="${b.name} from the air, ${y}"><figcaption>${y}${b.aerial_outline_score ? '<br>' + fmt(b.aerial_outline_score[y], 2) : ''}</figcaption></figure>`).join('')}</div>`;
}
function evidence(b) {
  const d = b.documented, g = b.ground_photographs;
  return `<p><span class="state" data-state-of="${b.name}"></span></p>
    <p><b>Documented.</b> ${d.documented}${d.source ? ` <a href="${d.source}" target="_blank" rel="noopener">source</a>` : ''}.</p>
    <p><b>From the air</b> (NYS orthoimagery; number = own-outline edge score, a diagnostic):</p>${strip(b)}
    <p><b>From the ground.</b> ${g ? `${fmt(g.points)} reconstructed points on this building; first photographed ${g.earliest_photograph}, last ${g.latest_photograph}.` : groundRecord(b)}</p>${recordStrip(b)}`;
}
function groundRecord(b) {
  const r = b.ground_record;
  if (!r) return 'no licensed photographs of this building are in the collection yet.';
  const who = `${fmt(r.photographs)} licensed photograph${r.photographs === 1 ? '' : 's'} by ${r.photographers} photographer${r.photographers === 1 ? '' : 's'}`;
  const when = r.dated ? `, ${r.dated} with capture dates (first ${r.earliest}, last ${r.latest})` : ', none with a capture date';
  const rc = r.reconstruction;
  if (!rc) return `${who}${when}; not yet reconstructed.`;
  const biggest = rc.largest_fragment ? ` (the largest holds ${rc.largest_fragment.cameras} cameras and ${fmt(rc.largest_fragment.points)} points)` : '';
  const tried = rc.anchoring.filter(a => !a.usable);
  const why = tried.length ? ` Anchoring the largest fragment to the lidar through the footprint of ${tried[0].building} was attempted and is not usable: only ${Math.round(100 * (tried[0].points_within_1m_of_walls || 0))} % of its points lie within a metre of any wall, because these photographs are close-ups of the entrance, not of the facades the lidar measures. No ground model is shown; the dates above are the ground record.` : '';
  return `${who}${when}. ${rc.registered} of ${rc.photographs_mapped} register, in ${rc.fragments} fragment${rc.fragments === 1 ? '' : 's'}${biggest}.${why}`;
}
function recordStrip(b) {
  const r = b.ground_record;
  if (!r || !r.strip.length) return '';
  return `<div class="strip">${r.strip.map(s => `<figure><a href="${s.source_url || '#'}" target="_blank" rel="noopener"><img src="${BASE + s.photo}" alt="${s.title || ''}" title="${(s.title || '') + ' — ' + (s.artist || '') + ', ' + (s.license || '')}"></a><figcaption>${s.date}</figcaption></figure>`).join('')}</div>`;
}
function buildingChapter(name, intro) {
  const b = building(name); const c = centroid(b.ring);
  body.innerHTML = `<h2>${name.replace('Bill and Melinda ', '')}</h2><p>${intro}</p>${evidence(b)}`;
  const span = Math.max(...b.ring.map(p => p[0])) - Math.min(...b.ring.map(p => p[0]));
  flyTo([c[0], c[1], b.ground + 5], Math.max(160, span * 2.4), 0.55, -2.3);
  setYear(year);
}
const chapters = [
  { id: 'above', title: '1 · From above', render() {
      body.innerHTML = `<h2>The campus from above, 2002 to 2023</h2>
        <p>Public New York State orthoimagery, one flight every few years, draped on USGS lidar terrain. Drag the year. The three outlined buildings did not exist in 2002.</p>
        <p><button type="button" id="play">▶ play the years</button></p>
        <ul>${changed.map(b => `<li><b>${b.name.replace('Bill and Melinda ', '')}</b> — <span class="state" data-state-of="${b.name}"></span></li>`).join('')}</ul>
        <p class="note">Flight years: ${YEARS.join(', ')}. Between flights the latest earlier image is shown. Building volumes are the 2020 lidar shape, shown only in years the documented dates say the building stood.</p>`;
      document.getElementById('play').onclick = play;
      legend([['#b5532c', 'buildings that changed (outline; volume from 2020 lidar when standing)'], ['#303030', 'other footprints (OpenStreetMap)']]);
      const t = scene.buildings.find(b => b.name === 'McGraw Tower'), c = centroid(t.ring);
      flyTo([c[0] + 60, c[1] + 40, t.ground], 900, 0.95, -1.9); setYear(year);
    } },
  { id: 'gates', title: '2 · Gates Hall', render() { buildingChapter('Bill and Melinda Gates Hall', 'A parking lot until 2012; a Thom Mayne building from 2014. Slide from 2007 to 2015 and watch the air photographs change; the volume is the lidar shape of the finished building.'); } },
  { id: 'klarman', title: '3 · Klarman Hall', render() { buildingChapter('Klarman Hall', 'The courtyard behind Goldwin Smith Hall until the 2012 flight, excavation in the 2015 flight, a glass atrium from 2016.'); } },
  { id: 'tower', title: '4 · McGraw Tower', render() {
      const r = scene.reconstructions.find(x => x.anchored_through === 'McGraw Tower') || scene.reconstructions[0];
      const own = scene.photographers.filter(p => p.reconstruction === r.tag); const dated = own.filter(p => p.year);
      const counts = {}; for (const p of dated) counts[p.year] = (counts[p.year] || 0) + 1;
      const maxc = Math.max(1, ...Object.values(counts));
      body.innerHTML = `<h2>McGraw Tower: the thing that does not change</h2>
        <p>${fmt(own.length)} photographs of the tower and Uris Library are registered in one COLMAP model and anchored to the lidar (${r.scale_status}). ${fmt(r.dated_photographs)} carry capture dates from ${Math.min(...dated.map(p => p.year))} to ${Math.max(...dated.map(p => p.year))}.</p>
        <p>Each reconstructed point carries the years in which photographs observed it. The slider shows the points seen by that year; "colour by first year" shows when each point first appeared in a photograph.</p>
        <div class="yearbar">${Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i).map(y => `<div data-year="${y}" style="height:${100 * (counts[y] || 0) / maxc}%" title="${y}: ${counts[y] || 0} dated photographs"></div>`).join('')}</div>
        <div class="yearlabels"><span>${MIN_YEAR}</span><span>dated photographs per year</span><span>${MAX_YEAR}</span></div>
        <div class="cues"><label><input type="radio" name="col" value="photo" checked>photo colours</label><label><input type="radio" name="col" value="first">colour by first year seen</label></div>
        <p>Click a photographer (sphere) to see the photograph; red = taken in the selected year.</p><div id="pick"></div>`;
      for (const x of document.querySelectorAll('input[name=col]')) x.onchange = () => { colourMode = x.value; setYear(year); };
      legend([['#2a6fdb', 'photographers before the selected year'], ['#d0453a', 'photographers in the selected year'], ['#9aa5b1', 'later photographers']]);
      const t = scene.buildings.find(b => b.name === 'McGraw Tower'), c = centroid(t.ring);
      flyTo([c[0], c[1], t.ground + 20], 220, 0.35, -2.4); setYear(year);
    } },
  { id: 'limits', title: '5 · Limits', render() {
      body.innerHTML = `<h2>What the record cannot show</h2>
        <ul>
          <li><b>No licensed ground-level photograph of any site before construction exists online.</b> The "before" is aerial only; no 3D of the old parking lots or the courtyard is shown.</li>
          <li><b>Building volumes are the 2020 lidar shape</b>, displayed only in years the documented dates say the building stood; a ground-level reconstruction replaces the volume only where its photographs could be anchored to the lidar.</li>
          <li><b>One facade cannot fix its own scale.</b> The fifteen photographs around Goldwin Smith Hall see its portico and the A. D. White statue from the lawn; without the tower in view, a single facade matches walls of different heights at different scales (the portico shrunk onto a nine-metre wing wall fits as well as the portico at its own fifteen-metre wall), so that fragment is reported as not anchored and Klarman Hall's chapter rests on the aerial flights and the documented dates.</li>
          <li><b>The automatic aerial test is a diagnostic.</b> Its outline score rises at every site when the building appears, but stable buildings vary between flights by as much, so the dates on this page are the documented ones.</li>
          <li><b>Boardman Hall (demolished 1959)</b> is beyond the time machine: its postcards can be matched to the surviving tower and library, but every recovered pose is a mirror image, because no licensed modern photograph looks at the tower from the Arts Quad side.</li>
        </ul>`;
      legend([]); setYear(year);
    } },
];
for (const ch of chapters) nav.append(Object.assign(el('button', { type: 'button' }, ch.title), { onclick: () => show(ch.id) }));
function show(id) {
  if (!chapters.some(c => c.id === id)) id = 'above';
  for (const b of nav.children) b.setAttribute('aria-current', String(b.textContent === chapters.find(c => c.id === id).title));
  body.innerHTML = ''; chapters.find(c => c.id === id).render(); history.replaceState(null, '', '#' + id);
}

// --- picking ----------------------------------------------------------------------------------
const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
canvas.addEventListener('click', e => {
  const r = canvas.getBoundingClientRect(); mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(mouse, camera);
  const hit = ray.intersectObjects(photographerGroup.children)[0];
  const pick = document.getElementById('pick'); if (!hit || !pick) return;
  const p = hit.object.userData;
  pick.innerHTML = `<img class="photo" src="${BASE + p.photo}" alt=""><p class="note">${p.title.replace(/^File:/, '')} · ${p.date || 'undated'} · ${p.artist || ''} · <a href="${p.source_url}" target="_blank" rel="noopener">${p.license || 'licence'}</a></p>`;
  if (p.year) setYear(p.year);
});

// --- loop -----------------------------------------------------------------------------------------
function resize() { const { clientWidth: w, clientHeight: h } = canvas.parentElement; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }
new ResizeObserver(resize).observe(canvas.parentElement); resize();
renderer.setAnimationLoop(() => { stepFlight(); controls.update(); renderer.render(world, camera); });
document.getElementById('attribution').textContent = scene.attribution.join(' ');
document.getElementById('status').textContent = '';
setYear(2007);
show((location.hash || '#above').slice(1).replace(/[^a-z]/g, ''));
window.__tm = { terrains, textures, scene };  // for the headless checks
document.documentElement.dataset.ready = 'true';
