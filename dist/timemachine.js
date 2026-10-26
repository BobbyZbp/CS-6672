// GhostMap viewer: internet photographs of Cornell placed in the world's own 3D model (USGS lidar), rendered as
// Gaussian splats scored and taught by that lidar, and replayed over twenty years. All numbers come from
// assets/timemachine/scene.json (built by web/timemachine_scene.py from report files); nothing is typed in here.
import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import * as GaussianSplats3D from './vendor/gaussian-splats-3d.module.js';

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
const world = new THREE.Scene();
// A real GPU gets sun shadows; a browser that renders WebGL on the CPU (headless checks) does not.
const gpuName = (() => { const gl = renderer.getContext(), d = gl.getExtension('WEBGL_debug_renderer_info'); return d ? gl.getParameter(d.UNMASKED_RENDERER_WEBGL) : ''; })();
const SOFTWARE = /swiftshader|llvmpipe|software/i.test(gpuName);
renderer.shadowMap.enabled = !SOFTWARE; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
const sky = (() => {   // a vertical gradient for the background, from haze at the horizon to blue overhead
  const c = document.createElement('canvas'); c.width = 2; c.height = 256; const g = c.getContext('2d'), gr = g.createLinearGradient(0, 0, 0, 256);
  gr.addColorStop(0, '#8fb4d9'); gr.addColorStop(0.55, '#c9dbea'); gr.addColorStop(1, '#eef2f2'); g.fillStyle = gr; g.fillRect(0, 0, 2, 256);
  const tx = new THREE.CanvasTexture(c); tx.colorSpace = THREE.SRGBColorSpace; return tx;
})();
world.background = sky; world.fog = new THREE.Fog(0xe6edf0, 900, 2600);
const camera = new THREE.PerspectiveCamera(48, 1, 0.5, 8000); camera.up.set(0, 0, 1);
const controls = new OrbitControls(camera, canvas); controls.enableDamping = true; controls.maxPolarAngle = Math.PI / 2 - 0.02;
world.add(new THREE.HemisphereLight(0xe8f0f8, 0x6f7d5c, 0.95));
const sun = new THREE.DirectionalLight(0xfff1dc, 1.7); sun.position.set(-260, -340, 520);
sun.castShadow = !SOFTWARE; sun.shadow.mapSize.set(4096, 4096); sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.6;
Object.assign(sun.shadow.camera, { left: -520, right: 520, top: 520, bottom: -520, near: 10, far: 2000 });
world.add(sun); world.add(sun.target);

let flight = null;
function flyTo(target, distance, elevation = 0.7, azimuth = -2.0, seconds = 1.4) {
  const from = { pos: camera.position.clone(), tgt: controls.target.clone() };
  const to = { tgt: new THREE.Vector3(...target) };
  to.pos = new THREE.Vector3(to.tgt.x + distance * Math.cos(azimuth) * Math.cos(elevation), to.tgt.y + distance * Math.sin(azimuth) * Math.cos(elevation), to.tgt.z + distance * Math.sin(elevation));
  flight = { from, to, t0: performance.now(), ms: seconds * 1000, fov: { from: camera.fov, to: 48 } };
}
// Stand where a photographer stood, looking where the photograph looks, with its field of view: a splat is only
// trustworthy near the views it was trained from (and a held-out photographer's view is the honest test).
function flyToPhotographer(p, seconds = 1.6) {
  const R = p.rotation, fwd = new THREE.Vector3(...R[2]).normalize(), pos = new THREE.Vector3(...p.centre);
  const fov = 2 * Math.atan(p.height / 2 / p.focal_px) * 180 / Math.PI;
  flight = { from: { pos: camera.position.clone(), tgt: controls.target.clone() }, to: { pos, tgt: pos.clone().addScaledVector(fwd, 60) },
             t0: performance.now(), ms: seconds * 1000, fov: { from: camera.fov, to: Math.min(75, Math.max(20, fov)) } };
}
function stepFlight() {
  if (!flight) return;
  const s = Math.min(1, (performance.now() - flight.t0) / flight.ms), e = s < .5 ? 2 * s * s : 1 - Math.pow(-2 * s + 2, 2) / 2;
  camera.position.lerpVectors(flight.from.pos, flight.to.pos, e); controls.target.lerpVectors(flight.from.tgt, flight.to.tgt, e);
  if (flight.fov) { camera.fov = flight.fov.from + (flight.fov.to - flight.fov.from) * e; camera.updateProjectionMatrix(); }
  if (s >= 1) flight = null;
}

// --- the world: bare-earth ground and roofs draped with the year's aerial image, lidar walls, lidar trees ----------
const loader = new THREE.TextureLoader();
const textures = {};
function texture(url) {
  if (!textures[url]) { const t = loader.load(BASE + url); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; textures[url] = t; }
  return textures[url];
}
const covered = new Set(scene.reconstructions.flatMap(r => r.covers || []));  // buildings a measured surface replaces when shown
let surfaceOn = false;
const qt = scene.sites.quad.terrain;  // extent of the Quad terrain grid, used to trim the other sites' terrains
const quadExtent = [qt.x0, qt.y_top - (qt.rows - 1) * qt.cell_m, qt.x0 + (qt.cols - 1) * qt.cell_m, qt.y_top];
const terrains = {}, cityParts = { roofs: [], walls: [], trees: [] }, specialMeshes = {};
const changed = scene.buildings.filter(b => b.documented && !b.documented.stable);
function presentFrom(b) {
  const d = b.documented; const y = (d.dedicated || d.completed || d.opened || d.occupied || '').slice(0, 4); return y ? +y : null;
}
function worksFrom(b) { const d = b.documented; return d.construction_start ? +d.construction_start.slice(0, 4) : null; }
const lin = (c) => Math.pow(c, 2.2);   // vertex colours are given in sRGB; three.js lights in linear space
// A lumpy unit sphere for tree crowns (one shape shared by every tree), and a unit cylinder standing on z for trunks.
const crownGeometry = (() => { const g = new THREE.IcosahedronGeometry(1, 2), p = g.attributes.position;
  for (let i = 0; i < p.count; i++) { const v = new THREE.Vector3().fromBufferAttribute(p, i), k = 1 + 0.13 * Math.sin(5.1 * v.x + 2.3 * v.y) * Math.cos(4.3 * v.z + 1.7 * v.x); p.setXYZ(i, v.x * k, v.y * k, v.z * k); }
  g.computeVertexNormals(); return g; })();
const crownMaterial = new THREE.MeshLambertMaterial({ color: 0xffffff, flatShading: true });
const trunkGeometry = new THREE.CylinderGeometry(1, 1, 1, 6).rotateX(Math.PI / 2);
const trunkMaterial = new THREE.MeshLambertMaterial({ color: 0x5b4a3a });
const discTexture = (() => { const c = document.createElement('canvas'); c.width = c.height = 32; const g = c.getContext('2d');
  const gr = g.createRadialGradient(16, 16, 2, 16, 16, 15); gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.75, 'rgba(255,255,255,0.9)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.beginPath(); g.arc(16, 16, 15, 0, 2 * Math.PI); g.fill(); return new THREE.CanvasTexture(c); })();
for (const [site, s] of Object.entries(scene.sites)) {
  const t = s.terrain, ob = s.ortho_box_local;   // texture coordinates come from the aerial image's own box
  const uvOf = (x, y) => [(x - ob[0]) / (ob[2] - ob[0]), (y - ob[1]) / (ob[3] - ob[1])];
  const heights = await binary(t.height_url, Float32Array);
  const n = t.rows * t.cols, pos = new Float32Array(n * 3), uv = new Float32Array(n * 2);
  for (let r = 0; r < t.rows; r++) for (let c = 0; c < t.cols; c++) {
    const i = r * t.cols + c, x = t.x0 + c * t.cell_m, y = t.y_top - r * t.cell_m;
    pos.set([x, y, heights[i] + t.z_offset], 3 * i); uv.set(uvOf(x, y), 2 * i);
  }
  // Cells of the other sites that lie wholly under the Quad terrain are dropped; cells straddling its edge are kept,
  // so the meshes overlap by up to one cell instead of leaving a gap (the overlap is pushed back by polygon offset).
  const clip = site !== 'quad';
  const under = (i) => { const x = pos[3 * i], y = pos[3 * i + 1]; return x >= quadExtent[0] && x <= quadExtent[2] && y >= quadExtent[1] && y <= quadExtent[3]; };
  const index = [];
  for (let r = 0; r < t.rows - 1; r++) for (let c = 0; c < t.cols - 1; c++) {
    const a = r * t.cols + c, b = a + 1, d = a + t.cols, e = d + 1;
    if (clip && under(a) && under(b) && under(d) && under(e)) continue;
    index.push(a, d, b, b, d, e);  // y decreases with the row index: this winding faces up
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.BufferAttribute(uv, 2)); g.setIndex(index); g.computeVertexNormals();
  const material = new THREE.MeshLambertMaterial({ map: null, polygonOffset: clip, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
  const mesh = new THREE.Mesh(g, material); mesh.receiveShadow = true;
  world.add(mesh);
  terrains[site] = { mesh, geometry: g, box: s.ortho_box_local, orthos: s.orthoimagery };
  // The city model (web/city_model.py): roofs share the ground's material, so they show the same year's aerial image.
  const C = s.city; if (!C) continue;
  const [xyz, shade, roofIdx, wallIdx, txyz, trgb] = await Promise.all([binary(C.xyz_url, Float32Array), binary(C.shade_url, Uint8Array), binary(C.roof_url, Uint32Array),
    binary(C.wall_url, Uint32Array), binary(C.trees_url, Float32Array), binary(C.trees_rgb_url, Uint8Array)]);
  const nv = xyz.length / 3, cuv = new Float32Array(nv * 2), col = new Float32Array(nv * 3);
  for (let i = 0; i < nv; i++) {
    cuv.set(uvOf(xyz[3 * i], xyz[3 * i + 1]), 2 * i);
    const k = shade[i] / 255; col.set([0.84 * k, 0.80 * k, 0.72 * k].map(lin), 3 * i);   // limestone, darker towards the ground
  }
  const posAttr = new THREE.BufferAttribute(xyz, 3), uvAttr = new THREE.BufferAttribute(cuv, 2), colAttr = new THREE.BufferAttribute(col, 3);
  const wallMaterial = new THREE.MeshLambertMaterial({ vertexColors: true });
  const part = (idx, [start, count], mat) => {
    const geo = new THREE.BufferGeometry(); geo.setAttribute('position', posAttr); geo.setAttribute('uv', uvAttr); geo.setAttribute('color', colAttr);
    geo.setIndex(new THREE.BufferAttribute(idx.subarray(start, start + count), 1)); geo.computeVertexNormals();
    const m = new THREE.Mesh(geo, mat); m.castShadow = true; m.receiveShadow = true; world.add(m); return m;
  };
  cityParts.roofs.push(part(roofIdx, C.static.roof, material)); cityParts.walls.push(part(wallIdx, C.static.wall, wallMaterial));
  for (const [name, gr] of Object.entries(C.special)) specialMeshes[name] = [part(roofIdx, gr.roof, material), part(wallIdx, gr.wall, wallMaterial)];
  // One tree per lidar canopy maximum (x, y, ground, top, crown radius): a crown of the measured area on a trunk.
  const nt = txyz.length / 5, crowns = new THREE.InstancedMesh(crownGeometry, crownMaterial, nt), trunks = new THREE.InstancedMesh(trunkGeometry, trunkMaterial, nt);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), zAxis = new THREE.Vector3(0, 0, 1), tint = new THREE.Color();
  for (let i = 0; i < nt; i++) {
    const [x, y, g, top, r] = txyz.subarray(5 * i, 5 * i + 5), h = top - g, base = g + Math.max(1.8, 0.3 * h), half = (top - base) / 2;
    q.setFromAxisAngle(zAxis, (i * 2.39996) % (2 * Math.PI));   // the shared crown shape, turned differently per tree
    m4.compose(new THREE.Vector3(x, y, base + half), q, new THREE.Vector3(r, r, Math.max(half, 0.8))); crowns.setMatrixAt(i, m4);
    tint.setRGB(lin(trgb[3 * i] / 255), lin(trgb[3 * i + 1] / 255), lin(trgb[3 * i + 2] / 255)); crowns.setColorAt(i, tint);
    m4.compose(new THREE.Vector3(x, y, g + (base - g + half * 0.4) / 2), q.identity(), new THREE.Vector3(0.12 + 0.012 * h, 0.12 + 0.012 * h, base - g + half * 0.4)); trunks.setMatrixAt(i, m4);
  }
  for (const m of [crowns, trunks]) { m.castShadow = true; m.receiveShadow = true; m.computeBoundingSphere(); world.add(m); cityParts.trees.push(m); }
}

// --- outlines of the buildings that changed, and the construction-site frame while they were built ---------------
const outlines = new THREE.Group(), volumes = new THREE.Group(); world.add(outlines, volumes);
for (const b of scene.buildings) {
  if (!b.documented) continue;
  const z = b.ground + 0.6;
  const g = new THREE.BufferGeometry().setFromPoints(b.ring.map(([x, y]) => new THREE.Vector3(x, y, z)));
  const line = new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0xb5532c })); line.userData = b; outlines.add(line);
  if (!b.documented.stable) {
    const shape = new THREE.Shape(b.ring.map(([x, y]) => new THREE.Vector2(x, y)));
    const geom = new THREE.ExtrudeGeometry(shape, { depth: Math.max(3, b.lidar_top - b.ground), bevelEnabled: false });
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
  const pts = new THREE.Points(g, new THREE.PointsMaterial({ size: 1.1, vertexColors: true, map: discTexture, alphaTest: 0.5 }));
  world.add(pts); const cloud = { pts, g, rgb: colour, first, last, meta: r, surface: null, splats: [], native: null, anchored: xyz.slice() }; clouds.push(cloud);
  // Each Gaussian splat of the fragment: a layer of its centres coloured by their lidar class (loaded now, small) and
  // the splat itself, rendered by the vendored Gaussian-splat viewer when a chapter first asks for it.
  for (const s of r.splats || []) {
    const entry = { meta: s, layer: null, viewer: null, loading: null }; cloud.splats.push(entry);
    Promise.all([binary(s.xyz_url, Float32Array), binary(s.rgb_url, Uint8Array)]).then(([xyz, rgb]) => {
      const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.BufferAttribute(xyz, 3));
      const col = new Float32Array(rgb.length); for (let i = 0; i < rgb.length; i++) col[i] = rgb[i] / 255;
      sg.setAttribute('color', new THREE.BufferAttribute(col, 3));
      entry.layer = new THREE.Points(sg, new THREE.PointsMaterial({ size: 1.0, vertexColors: true, map: discTexture, alphaTest: 0.5 })); entry.layer.visible = false; world.add(entry.layer);
      applyView();
    }).catch(e => console.warn('splat layer not loaded', e));
  }
  if (r.placement) binary(r.placement.native_url, Float32Array).then(a => { cloud.native = a; }).catch(e => console.warn('native fragment not loaded', e));
  // A dense surface of the fragment (vertex colours from the dense cloud), loaded in the background and shown on request.
  if (r.mesh && r.mesh.faces_url) {
    Promise.all([binary(r.mesh.xyz_url, Float32Array), binary(r.mesh.rgb_url, Uint8Array), binary(r.mesh.faces_url, Uint32Array)]).then(([xyz, rgb, faces]) => {
      const mg = new THREE.BufferGeometry(); mg.setAttribute('position', new THREE.BufferAttribute(xyz, 3));
      const col = new Float32Array(rgb.length); for (let i = 0; i < rgb.length; i++) col[i] = rgb[i] / 255;
      mg.setAttribute('color', new THREE.BufferAttribute(col, 3)); mg.setIndex(new THREE.BufferAttribute(faces, 1));
      const surface = new THREE.Mesh(mg, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide }));
      surface.visible = false; world.add(surface); cloud.surface = surface;
      const box = document.getElementById('surface'); if (box) box.disabled = false; applyView();
    }).catch(e => console.warn('dense surface not loaded', e));
  }
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
  for (const t of Object.values(terrains)) { const o = t.orthos[String(fy)]; if (o) t.mesh.material.map = texture(o.url); t.mesh.material.needsUpdate = true; }
  // Buildings that changed stand only from their documented dates; a building a measured surface covers steps aside for it.
  for (const [name, meshes] of Object.entries(specialMeshes)) {
    const b = scene.buildings.find(x => x.name === name), s = b ? state(b, y) : 'stable';
    const show = view.terrain && (s === 'present' || ((s === 'stable' || s === null) && !(surfaceOn && covered.has(name))));
    for (const m of meshes) m.visible = show;
  }
  for (const v of volumes.children) v.visible = state(v.userData.works, y) === 'works';
  for (const c of clouds) {
    const col = c.g.attributes.color;
    for (let i = 0; i < c.first.length; i++) {
      const seen = c.first[i] > 0 && c.first[i] <= y;
      if (colourMode === 'first') { const h = seen ? (c.first[i] - 2002) / 24 : 0; col.setXYZ(i, seen ? 0.2 + 0.8 * h : 0.6, seen ? 0.9 - 0.7 * h : 0.6, seen ? 0.4 : 0.6); }
      else col.setXYZ(i, seen ? c.rgb[3 * i] : 0.75, seen ? c.rgb[3 * i + 1] : 0.75, seen ? c.rgb[3 * i + 2] : 0.75);
    }
    col.needsUpdate = true;
  }
  for (const m of photographerGroup.children) {
    const py = m.userData.year;
    if (view.allPhotographers) { m.visible = true; m.material.color.set(0x2a6fdb); m.scale.setScalar(1); continue; }
    m.visible = py !== null; m.material.color.set(py === y ? 0xd0453a : py && py < y ? 0x2a6fdb : 0x9aa5b1); m.scale.setScalar(py === y ? 1.8 : 1);
  }
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

// --- what is shown: one view per chapter -------------------------------------------------------------
const DEFAULT_VIEW = { terrain: true, outlines: true, volumes: true, points: true, photographers: true, surface: false, splat: null, splatLayer: null, dark: false, allPhotographers: false };
const view = { ...DEFAULT_VIEW };
function applyView() {
  for (const t of Object.values(terrains)) t.mesh.visible = view.terrain;
  for (const m of [...cityParts.roofs, ...cityParts.walls, ...cityParts.trees]) m.visible = view.terrain;
  outlines.visible = view.outlines; volumes.visible = view.volumes;
  world.background = view.dark ? new THREE.Color(0x15191e) : sky; world.fog = view.dark ? null : new THREE.Fog(0xe6edf0, 900, 2600);
  for (const c of clouds) {
    c.pts.visible = view.points;
    if (c.surface) c.surface.visible = view.surface;
    for (const s of c.splats) {
      if (s.layer) s.layer.visible = view.splatLayer === s.meta.name;
      if (s.viewer) s.viewer.visible = view.splat === s.meta.name;
    }
  }
  photographerGroup.visible = view.photographers;
}
function setView(v = {}) {
  Object.assign(view, DEFAULT_VIEW, v);
  surfaceOn = !!(view.surface || view.splat);   // a measured surface replaces the lidar shape of the buildings it covers
  applyView();
}
const mainCloud = () => clouds.find(c => c.meta.placement) || clouds[0];
const status = text => { document.getElementById('status').textContent = text; };

// --- Gaussian splats, loaded on first use ------------------------------------------------------------
function splatEntry(name) { const c = mainCloud(); return c ? c.splats.find(s => s.meta.name === name) : null; }
// `?splats=N` loads only the N most important Gaussians of each splat (the files are sorted by size times opacity):
// for browsers that render WebGL on the CPU, such as the headless checks and the recorded tour.
const SPLAT_CAP = Math.max(0, parseInt(new URLSearchParams(location.search).get('splats') || '0', 10)) || null;
function loadSplat(entry) {
  if (!entry.loading) entry.loading = (async () => {
    const viewer = new GaussianSplats3D.DropInViewer({ gpuAcceleratedSort: false, sharedMemoryForWorkers: false, integerBasedSort: true, halfPrecisionCovariancesOnGPU: false });
    const options = { showLoadingUI: false, splatAlphaRemovalThreshold: 5, format: GaussianSplats3D.SceneFormat.Splat };
    let url = BASE + entry.meta.splat_url;
    if (SPLAT_CAP) { const buf = await (await fetch(url)).arrayBuffer(); url = URL.createObjectURL(new Blob([buf.slice(0, 32 * SPLAT_CAP)])); }
    await viewer.addSplatScene(url, options);
    viewer.visible = false; world.add(viewer); entry.viewer = viewer; return viewer;
  })();
  return entry.loading;
}
async function showSplat(name, chapterId) {
  const e = splatEntry(name); if (!e) return;
  if (!e.viewer) {
    status('Loading the Gaussian splat (' + fmt(SPLAT_CAP ? Math.min(SPLAT_CAP, e.meta.splat_gaussians) : e.meta.splat_gaussians) + ' Gaussians)…');
    try { await loadSplat(e); } catch (err) { console.warn('splat not loaded', err); status('The splat could not be loaded in this browser; the lidar check layer still works.'); return; }
    status('');
  }
  if (current === chapterId) applyView();
}

// --- the fragment before and after placement ---------------------------------------------------------
// scene local = scale * R * native + translation. The floating pose keeps the raw COLMAP frame (its arbitrary
// orientation) at half the true scale, above the campus, slowly turning: no scale, no north, no up.
const placement = { mode: 'placed', t0: 0, ms: 3200 };
function centroid3(a) { const c = [0, 0, 0], n = a.length / 3; for (let i = 0; i < a.length; i += 3) { c[0] += a[i]; c[1] += a[i + 1]; c[2] += a[i + 2]; } return c.map(v => v / n); }
function poseAt(alpha, spin) {
  const c = mainCloud(); if (!c || !c.native || !c.meta.placement) return;
  const P = c.meta.placement;
  if (!c.nativeCentre) { c.nativeCentre = centroid3(c.native); c.anchoredCentre = centroid3(c.anchored); }
  const q1 = new THREE.Quaternion(...P.quaternion_xyzw), q0 = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), spin);
  const q = q0.clone().slerp(q1, alpha);
  const s = Math.exp((1 - alpha) * Math.log(P.scale / 2) + alpha * Math.log(P.scale));
  const start = new THREE.Vector3(c.anchoredCentre[0] - 150, c.anchoredCentre[1] - 110, c.anchoredCentre[2] + 140);
  const centre = start.lerp(new THREE.Vector3(...c.anchoredCentre), alpha);
  const R = new THREE.Matrix3().setFromMatrix4(new THREE.Matrix4().makeRotationFromQuaternion(q)).elements;  // column-major
  const [nx, ny, nz] = c.nativeCentre;
  const move = (x, y, z, out, k) => {
    x -= nx; y -= ny; z -= nz;
    out[k] = s * (R[0] * x + R[3] * y + R[6] * z) + centre.x; out[k + 1] = s * (R[1] * x + R[4] * y + R[7] * z) + centre.y; out[k + 2] = s * (R[2] * x + R[5] * y + R[8] * z) + centre.z;
  };
  const pos = c.g.attributes.position.array;
  if (alpha >= 1) pos.set(c.anchored); else for (let i = 0; i < c.native.length; i += 3) move(c.native[i], c.native[i + 1], c.native[i + 2], pos, i);
  c.g.attributes.position.needsUpdate = true; c.g.computeBoundingSphere();
  const tmp = [0, 0, 0];
  for (const m of photographerGroup.children) {
    const p = m.userData; if (p.reconstruction !== c.meta.tag) continue;
    if (alpha >= 1 || !p.centre_native) m.position.set(...p.centre); else { move(...p.centre_native, tmp, 0); m.position.set(...tmp); }
  }
  return centre;
}
function float() { placement.mode = 'floating'; placement.t0 = performance.now(); }
function snapIntoPlace() { placement.mode = 'snapping'; placement.t0 = performance.now(); }
function stepPlacement() {
  const now = performance.now();
  if (placement.mode === 'floating') poseAt(0, (now - placement.t0) / 1000 * 0.25);
  else if (placement.mode === 'snapping') {
    const s = Math.min(1, (now - placement.t0) / placement.ms), e = s < .5 ? 4 * s * s * s : 1 - Math.pow(-2 * s + 2, 3) / 2;
    poseAt(e, 0);
    if (s >= 1) { placement.mode = 'placed'; poseAt(1, 0); if (placement.done) placement.done(); }
  }
}

// --- small charts ------------------------------------------------------------------------------------
function profileChart(cert) {
  const P = cert.profiles; if (!P || !P.scale_grid_m_per_unit) return '';
  const g = P.scale_grid_m_per_unit, x = v => Math.log(v / cert.scale_m_per_unit), xs = g.map(x);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), W = 380, H = 150, L = 8, B = 22;
  const series = [['all', 'all cues', 'var(--ink)', 2.6], ['only_landmark', 'tower top alone', 'var(--accent)', 1.6], ['only_roof_edges', 'roof edges alone', 'var(--amber)', 1.6], ['only_walls', 'walls alone', 'var(--ok)', 1.6]];
  const path = v => { const lo = Math.min(...v), hi = Math.max(...v), r = hi - lo || 1; return v.map((y, i) => `${i ? 'L' : 'M'}${(L + (xs[i] - x0) / (x1 - x0) * (W - 2 * L)).toFixed(1)},${(H - B - (y - lo) / r * (H - B - 10)).toFixed(1)}`).join(''); };
  const xFit = L + (0 - x0) / (x1 - x0) * (W - 2 * L);
  return `<figure class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="How well each cue explains the fragment at each scale">
    <line x1="${xFit}" x2="${xFit}" y1="6" y2="${H - B}" stroke="var(--muted)" stroke-dasharray="3 3"/>
    ${series.filter(([k]) => P[k]).map(([k, , c, w]) => `<path d="${path(P[k])}" fill="none" stroke="${c}" stroke-width="${w}"/>`).join('')}
    <text x="${L}" y="${H - 6}" font-size="11" fill="var(--muted)">×${fmt(Math.exp(x0), 2)}</text><text x="${xFit - 24}" y="${H - 6}" font-size="11" fill="var(--muted)">fitted scale</text><text x="${W - L - 30}" y="${H - 6}" font-size="11" fill="var(--muted)">×${fmt(Math.exp(x1), 1)}</text>
  </svg><figcaption>${series.filter(([k]) => P[k]).map(([, l, c]) => `<span class="sw" style="background:${c}"></span>${l}`).join(' ')}<br>How well each cue explains the fragment at each scale (each curve scaled to its own range). The tower top and the roof edges peak at the fitted scale; the walls alone would accept a fragment stretched along its facades.</figcaption></figure>`;
}
const pct = (x, d = 0) => x === null || x === undefined ? '—' : fmt(100 * x, d) + ' %';
function verdictBadge(v, mode) { return v === 'usable' ? '<span class="state present">usable</span>' : `<span class="state before">not usable${mode ? ' — ' + mode : ''}</span>`; }

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
  const why = tried.length ? ` Anchoring the largest fragment to the lidar through the building's footprint was attempted and is not usable: the photographs are close-ups of the entrance, the stairs and the undercroft, not of the facades the lidar measures. No ground model is shown; the dates above are the ground record.` : '';
  return `${who}${when}. Of the ${rc.photographs_mapped} in the training split after the duplicate screen, ${rc.registered} register, in ${rc.fragments} fragment${rc.fragments === 1 ? '' : 's'}${biggest}.${why}`;
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
  legend([['#b5532c', 'buildings that changed (outline; volume from 2020 lidar when standing)'], ['#303030', 'other footprints (OpenStreetMap)']]);
  setYear(year);
}
// Where the photographers stood, as seen from the tower: the side from which the splat is best seen.
function photographersAzimuth(tower) {
  const c = centroid(tower.ring), own = scene.photographers.filter(p => p.reconstruction === (mainCloud() || {}).meta?.tag);
  const v = own.reduce((a, p) => [a[0] + p.centre[0] - c[0], a[1] + p.centre[1] - c[1]], [0, 0]);
  return Math.atan2(v[1], v[0]);
}
function splatNumbers(s) {
  return `<div class="stat">
      <div>Gaussians shown (inside the lidar's measured volume)</div><div>${fmt(s.splat_gaussians)}</div>
      <div>in air the lidar saw empty</div><div class="${s.free_space.in_free_air > 0.1 ? 'bad' : 'ok'}">${pct(s.free_space.in_free_air)}</div>
      <div>buried under the bare ground</div><div>${pct(s.free_space.buried)}</div>
      <div>on lidar surfaces (within 2.5 m)</div><div>${pct(s.free_space.on_surfaces)}</div>
      <div>median distance to the nearest lidar return</div><div>${fmt(s.overall.median_m, 2)} m</div>
      <div>held-out photographs, PSNR (mean; range)</div><div>${s.psnr && s.psnr.test_mean ? fmt(s.psnr.test_mean, 1) + ' dB; ' + fmt(Math.min(...s.psnr.test.map(x => x.psnr)), 0) + '–' + fmt(Math.max(...s.psnr.test.map(x => x.psnr)), 0) : '—'}</div>
    </div>`;
}
// --- the wipe overlay: two images of the same view, a vertical divider to drag ------------------------------
const overlay = document.getElementById('overlay');
let flyTimer = null;
function fitBox(size) {
  const W = overlay.clientWidth - 24, H = overlay.clientHeight - 64, a = size ? size[0] / size[1] : 1.5;
  return W / H > a ? [H * a, H] : [W, W / a];
}
function showWipe(a, b, size) {   // a, b: {url, label}
  stopFly(); overlay.hidden = false;
  const [w, h] = fitBox(size);
  overlay.innerHTML = `<div class="wipe" style="width:${w}px;height:${h}px"><img class="a" src="${BASE + a.url}" alt=""><img class="b" src="${BASE + b.url}" alt=""><div class="bar"></div>
    <span class="lab a">${a.label}</span><span class="lab b">${b.label}</span><input type="range" min="0" max="100" value="50" aria-label="drag to compare"></div>`;
  const ov = overlay.querySelector('.wipe'), range = ov.querySelector('input'), top = ov.querySelector('img.b'), bar = ov.querySelector('.bar');
  range.oninput = () => { top.style.clipPath = `inset(0 0 0 ${range.value}%)`; bar.style.left = range.value + '%'; };
}
// The fly-through, explained: the two splats side by side along one camera path that no photographer took, a map
// of where the camera is among the photographers, the photograph itself whenever the camera reaches the spot
// where it was taken, and a switch that paints every Gaussian by the lidar's verdict.
function showFly(a, b) {   // a, b: {views, label, splat}: the same fly-through of two splats, frame by frame
  stopFly(); overlay.hidden = false;
  const F = a.views.fly, n = Math.min(F.frames, b.views.fly.frames), cams = F.cameras || [], keys = F.keys || [];
  const url = (v, k, verdict) => (verdict && v.fly.verdict_url_pattern ? v.fly.verdict_url_pattern : v.fly.url_pattern).replace('%03d', String(k).padStart(3, '0'));
  for (let k = 0; k < n; k++) for (const v of [a.views, b.views]) for (const d of [false, true]) new Image().src = BASE + url(v, k, d);   // preload
  const W = overlay.clientWidth - 32, H = overlay.clientHeight - 24, ar = F.size ? F.size[0] / F.size[1] : 4 / 3;
  const pw = Math.floor(Math.min((W - 10) / 2, (H - 250) * ar)), ph = Math.round(pw / ar);
  const who = keys.map(k => scene.photographers.find(p => p.name === k.image));
  overlay.innerHTML = `<div class="fly" style="width:${2 * pw + 10}px">
    <div class="flyhead"><b>A camera path no photographer took.</b> It walks between the spots where ${keys.length} photographers stood (map, lower left). Both splats were trained on the same photographs.</div>
    <div class="panes">${[a, b].map((s, i) => `<figure style="width:${pw}px;height:${ph}px"><img src="${BASE + url(s.views, 0)}" alt=""><figcaption>${s.label}</figcaption><span class="share"></span></figure>`).join('')}</div>
    <div class="flyfoot"><svg class="minimap" aria-label="map of the camera path"></svg>
      <div class="flytext"><p class="where"></p><p class="what"></p>
        <div class="ctl"><button type="button">❚❚</button><input type="range" min="0" max="${n - 1}" value="0" aria-label="frame">
          <label><input type="checkbox" class="verdict"> paint each Gaussian by the lidar's verdict</label></div></div>
      <figure class="truth"><img alt=""><figcaption></figcaption></figure></div></div>`;
  const ov = overlay.querySelector('.fly'), imgs = ov.querySelectorAll('.panes img'), shares = ov.querySelectorAll('.panes .share'), scrub = ov.querySelector('.ctl input[type=range]');
  const btn = ov.querySelector('.ctl button'), box = ov.querySelector('.verdict'), where = ov.querySelector('.where'), what = ov.querySelector('.what'), truth = ov.querySelector('.truth');
  // the map: footprints around the path, every photographer of this fragment, the photographers the path joins, the path
  const svg = ov.querySelector('.minimap'), pts = cams.map(c => c.centre).concat(keys.map(k => k.centre));
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]), tower = building('McGraw Tower'), tc = tower ? centroid(tower.ring) : [0, 0];
  const x0 = Math.min(...xs, tc[0]) - 25, x1 = Math.max(...xs, tc[0]) + 25, y0 = Math.min(...ys, tc[1]) - 25, y1 = Math.max(...ys, tc[1]) + 25;
  const mw = 290, s = mw / (x1 - x0), mh = Math.round((y1 - y0) * s), X = x => ((x - x0) * s).toFixed(1), Y = y => ((y1 - y) * s).toFixed(1);
  svg.setAttribute('viewBox', `0 0 ${mw} ${mh}`); svg.style.width = mw + 'px'; svg.style.height = mh + 'px';
  const near = scene.buildings.filter(bd => bd.ring.some(([x, y]) => x > x0 && x < x1 && y > y0 && y < y1));
  const own = scene.photographers.filter(p => p.reconstruction === (mainCloud() || {}).meta?.tag && p.centre[0] > x0 && p.centre[0] < x1 && p.centre[1] > y0 && p.centre[1] < y1);
  svg.innerHTML = `<rect width="${mw}" height="${mh}" fill="#20262c"/>
    ${near.map(bd => `<polygon points="${bd.ring.map(([x, y]) => X(x) + ',' + Y(y)).join(' ')}" fill="${bd.name === 'McGraw Tower' ? '#c8a96a' : '#4a525a'}" stroke="#6b747d" stroke-width="0.6"/>`).join('')}
    ${own.map(p => `<circle cx="${X(p.centre[0])}" cy="${Y(p.centre[1])}" r="1.8" fill="#7d8b99"/>`).join('')}
    <polyline points="${cams.map(c => X(c.centre[0]) + ',' + Y(c.centre[1])).join(' ')}" fill="none" stroke="#e8e2d0" stroke-width="1.2" stroke-dasharray="3 2"/>
    ${keys.map((k, i) => `<g><circle cx="${X(k.centre[0])}" cy="${Y(k.centre[1])}" r="6.5" fill="#2a6fdb" stroke="#fff" stroke-width="1"/><text x="${X(k.centre[0])}" y="${(+Y(k.centre[1]) + 3.2).toFixed(1)}" text-anchor="middle" font-size="8.5" font-weight="700" fill="#fff">${i + 1}</text></g>`).join('')}
    <path class="cone" fill="rgba(224,41,36,.28)" stroke="#e02924" stroke-width="1"/><circle class="cam" r="3.6" fill="#e02924" stroke="#fff" stroke-width="1"/>
    <text x="6" y="${mh - 6}" font-size="9" fill="#c8c2b4">${tower ? 'McGraw Tower in gold · ' : ''}north up</text>
    <line x1="${mw - 6 - 20 * s}" x2="${mw - 6}" y1="${mh - 9}" y2="${mh - 9}" stroke="#c8c2b4" stroke-width="1.5"/><text x="${mw - 6 - 10 * s}" y="${mh - 12}" text-anchor="middle" font-size="8.5" fill="#c8c2b4">20 m</text>`;
  const cone = svg.querySelector('.cone'), cam = svg.querySelector('.cam');
  const share = s => s.splat ? `${pct(s.splat.free_space.in_free_air, 0)} in empty air · ${pct(s.splat.free_space.buried, 0)} under the ground` : '';
  let k = 0, hold = 0;
  const setFrame = i => {
    k = (i + n) % n; const verdict = box.checked;
    imgs[0].src = BASE + url(a.views, k, verdict); imgs[1].src = BASE + url(b.views, k, verdict); scrub.value = k;
    [a, b].forEach((s, j) => { shares[j].textContent = verdict ? share(s) : ''; });
    const c = cams[k];
    if (c) {
      cam.setAttribute('cx', X(c.centre[0])); cam.setAttribute('cy', Y(c.centre[1]));
      const L = 28, h = c.heading_deg * Math.PI / 180, f = (c.fov_deg || 50) * Math.PI / 360, px = +X(c.centre[0]), py = +Y(c.centre[1]);
      const tip = d => [(px + L * s * Math.cos(h + d)).toFixed(1), (py - L * s * Math.sin(h + d)).toFixed(1)].join(',');
      cone.setAttribute('d', `M${px},${py} L${tip(-f)} L${tip(f)} Z`);
    }
    const at = keys.findIndex(q => Math.abs(q.frame - k) < 0.75), next = keys.findIndex(q => q.frame > k);
    if (at >= 0) {
      where.innerHTML = `<b>At photographer ${at + 1}'s spot.</b> This view is one of the training photographs (right): both splats reproduce it.`;
      const p = who[at]; truth.hidden = !p;
      if (p) { truth.querySelector('img').src = BASE + p.photo; truth.querySelector('figcaption').textContent = `the photograph taken here${p.year ? ', ' + p.year : ''}`; }
    } else {
      truth.hidden = true;
      where.innerHTML = `<b>Between photographers ${next} and ${next + 1}.</b> Nobody photographed this exact view${c ? ` (the nearest photograph was taken ${fmt(c.nearest_photographer_m, 0)} m away)` : ''}: the splat has to make it up.`;
    }
    what.innerHTML = verdict
      ? `<span class="sw" style="background:#e02924"></span>in air the lidar measured empty <span class="sw" style="background:#8c40bf"></span>under the bare ground <span class="sw" style="background:#a08c6e"></span>on a lidar surface (own colour)`
      : `Look at the sky and the ground: the plain splat (left) explains the photographs with paint floating in mid-air; the lidar-taught one (right) was told where the air is empty.`;
  };
  scrub.oninput = () => setFrame(+scrub.value); box.onchange = () => setFrame(k);
  const play = () => { flyTimer = setInterval(() => { if (hold > 0) { hold--; return; } setFrame(k + 1); if (keys.some(q => Math.abs(q.frame - k) < 0.5)) hold = 12; }, 110); btn.textContent = '❚❚'; };
  btn.onclick = () => { if (flyTimer) { clearInterval(flyTimer); flyTimer = null; btn.textContent = '▶'; } else play(); };
  setFrame(0); hold = 12; play();
}
function stopFly() { if (flyTimer) { clearInterval(flyTimer); flyTimer = null; } }
function hideOverlay() { stopFly(); overlay.hidden = true; overlay.innerHTML = ''; }
const poseLabel = (p, i) => p.held_out ? `held-out photograph${p.psnr ? ' · ' + fmt(p.psnr, 1) + ' dB' : ''}` : `photographer ${i}`;
const photographerOf = pose => scene.photographers.find(p => p.name === pose.image) || scene.photographers.find(p => p.name.replace(/\.[^.]+$/, '') === pose.photo);

const LEGEND_LIDAR = [['#28b34a', 'on a lidar surface'], ['#d9b316', '3 m or more from the nearest lidar return'], ['#e02924', 'in air the lidar saw empty'], ['#8c40bf', 'under the bare ground']];

const chapters = [
  { id: 'colmap', part: 'Beyond COLMAP', title: '0 · Where COLMAP stops', render() {
      const r = mainCloud().meta, st = scene.placement_study || {}, own = scene.photographers.filter(p => p.reconstruction === r.tag);
      const tagged = (st.fragments || []).find(f => f.run === r.tag.slice(0, 8) && String(f.fragment) === r.tag.split('-')[1]);
      const frs = (st.fragments || []).filter(f => f.run !== (r.tag || '').slice(0, 8)), refused = frs.filter(f => f.verdict !== 'usable');
      const agree = (st.agreement_with_validated_frame || []).filter(a => a.building === 'McGraw Tower').map(a => a.median_distance_m);
      const years = own.filter(p => p.year).map(p => p.year), S = r.splats || [], plain = S.find(s => !s.lidar_taught), taught = S.find(s => s.lidar_taught);
      const go = (id, label) => `<button type="button" class="jump" data-go="${id}">${label} →</button>`;
      const rows = [
        ['A model in its own frame (no scale, north or up); a map needs GPS or hand-picked control points.',
         'Placement without GPS, inside public lidar and building footprints.',
         tagged ? `${tagged.geotags.carried} of ${own.length} photographs carry GPS${tagged.geotags.wrong ? ', and it is 2,000 km off' : ''}` : '', go('void', 'chapters 1–2')],
        ['Never says when a placement cannot be trusted.',
         'A certificate: which cue fixed what, or a refusal with the reason.',
         `${refused.length} of ${frs.length} campus fragments refused, each with a stated reason`, go('refuse', 'chapter 3')],
        ['Disconnected fragments, each in its own frame.',
         'One shared world frame.',
         agree.length ? `the tower in separate fragments coincides within ${fmt(Math.min(...agree), 1)}–${fmt(Math.max(...agree), 1)} m` : '', go('refuse', 'chapter 3')],
        ['Splats trained on its output float paint in mid-air, unchecked.',
         'The lidar as referee and as teacher.',
         plain && taught ? `on lidar surfaces ${pct(plain.free_space.on_surfaces)} → ${pct(taught.free_space.on_surfaces)}; under the ground ${pct(plain.free_space.buried)} → ${pct(taught.free_space.buried)}` : '', go('referee', 'chapters 4–5')],
        ['One static scene: twenty years blended into one moment.',
         'Years per point; dated buildings and aerial flights.',
         years.length ? `${years.length} dated photographs, ${Math.min(...years)}–${Math.max(...years)}; 6 aerial flights, 2002–2023` : '', go('above', 'chapters 6–9')]];
      body.innerHTML = `<h2>Where COLMAP stops</h2>
        <p>Everything here starts from COLMAP's cameras and points (pycolmap, SuperPoint and LightGlue). On internet photographs of a real place, five of its limits show; GhostMap builds past each one with public data only.</p>
        ${rows.map(([lim, add, ev, link], i) => `<div class="limit"><div class="n">${i + 1}</div><div>
          <p class="lim"><b>COLMAP:</b> ${lim}</p><p><b>GhostMap:</b> ${add}</p><p class="ev">${ev} ${link}</p></div></div>`).join('')}
        <p class="note">The hack in one line: COLMAP's frame is arbitrary, so search for the one similarity transform that puts the reconstruction inside the lidar campus you see here — and say when no such transform is determined.</p>`;
      for (const b of body.querySelectorAll('[data-go]')) b.onclick = () => show(b.dataset.go);
      setView({ points: false, photographers: false }); legend([['#c8a96a', 'buildings: OpenStreetMap footprints raised to the USGS lidar roofs'], ['#4f7a3a', 'trees: one per lidar canopy peak']]);
      const t = building('McGraw Tower'), c = centroid(t.ring); flyTo([c[0] + 90, c[1] + 140, t.ground], 820, 0.62, -2.05);
      setYear(2023);
    } },
  { id: 'void', part: 'Where', title: '1 · Lost in space', render() {
      const c = mainCloud(), r = c.meta, cert = r.placement && r.placement.certificate, st = scene.placement_study || {}, gt = st.geotags || {};
      const own = scene.photographers.filter(p => p.reconstruction === r.tag);
      const tagged = (st.fragments || []).find(f => f.run === r.tag.slice(0, 8) && String(f.fragment) === r.tag.split('-')[1]);
      body.innerHTML = `<h2>What COLMAP gives you: a model in a void</h2>
        <p>${fmt(own.length)} licensed internet photographs of McGraw Tower and Uris Library, reconstructed by COLMAP (SuperPoint and LightGlue features). The result floats in its own coordinate frame: <b>no scale, no north, no up</b>.</p>
        <div class="stat"><div>photographs in the collection</div><div>${fmt(gt.photographs)}</div><div>with a GPS tag at all</div><div>${fmt(gt.with_gps)}</div>
          <div>GPS tags among this fragment's ${fmt(own.length)} photographs</div><div>${tagged ? tagged.geotags.carried + (tagged.geotags.wrong ? ', and it is 2,000 km off' : '') : '—'}</div></div>
        <p>The usual fix, aligning to the photographs' GPS, cannot even start. But the world already has a 3D model: public USGS airborne lidar covers most of the United States, and OpenStreetMap knows every building's footprint.</p>
        <p><button type="button" id="go-snap">Place it in the world →</button></p>`;
      document.getElementById('go-snap').onclick = () => show('snap');
      setView({ terrain: false, outlines: false, volumes: false, dark: true, allPhotographers: true });
      float();
      const ac = c.anchoredCentre || centroid3(c.anchored);
      flyTo([ac[0] - 150, ac[1] - 110, ac[2] + 140], 150, 0.25, -2.2);
      legend([['#2a6fdb', 'photographers, as COLMAP placed them'], ['#c8c2b4', 'reconstructed points (photo colours)']]);
      setYear(2023);
    } },
  { id: 'snap', part: 'Where', title: '2 · Snap to the world', render() {
      const r = mainCloud().meta, P = r.placement || {}, cert = P.certificate, fs = P.sparse_points_free_space || {};
      body.innerHTML = `<h2>Snap to the world, with a certificate</h2>
        <p>Placed in metres in the 2020 USGS lidar using only public data and physics: building walls from OpenStreetMap, the lidar roof edges, the tower top, photographers standing at eye height on the lidar ground, and free space along every camera ray. <b>No GPS tag, no hand-picked point.</b></p>
        ${cert ? `<p>${verdictBadge(cert.verdict, cert.failure_mode)} scale fixed by ${cert.scale_fixed_by.join(' and ')} (±${fmt(100 * cert.scale_uncertainty_relative, 1)} %)</p>
        <div class="stat"><div>scale</div><div>${fmt(cert.scale_m_per_unit, 2)} m per model unit</div>
          <div>its points on lidar surfaces (within 2.5 m)</div><div>${pct(fs.surface)}</div>
          <div>best other heading reaches</div><div>${pct(Math.max(...Object.values(cert.yaw_contrast).filter(v => v !== null)))} of the best</div></div>
        ${profileChart(cert)}
        <table><tr><th>cue</th><th class="num">score</th><th class="num">removing it moves the scale by</th></tr>${Object.entries(cert.cue_scores).map(([k, v]) => `<tr><td>${k.replace(/_/g, ' ')}</td><td class="num">${fmt(v, 2)}</td><td class="num">${pct(Math.abs((cert.cue_ablation[k] || {}).scale_ratio - 1), 1)}</td></tr>`).join('')}</table>` : ''}
        <p><button type="button" id="replay">↺ replay the snap</button></p>`;
      setView({ allPhotographers: true });
      const tower = building('McGraw Tower'), tc = centroid(tower.ring), az = photographersAzimuth(tower);
      const go = () => { float(); placement.t0 = performance.now(); snapIntoPlace(); placement.done = () => flyTo([tc[0], tc[1], tower.ground + 20], 240, 0.42, az, 1.6); };
      document.getElementById('replay').onclick = go;
      const ac = mainCloud().anchoredCentre || centroid3(mainCloud().anchored);
      flyTo([ac[0] - 60, ac[1] - 40, ac[2] + 60], 420, 0.45, -2.2, 1.0); go();
      legend([['#2a6fdb', 'photographers, placed'], ['#303030', 'OpenStreetMap footprints'], ['#b5532c', 'buildings that changed since 2002']]);
      setYear(2023);
    } },
  { id: 'refuse', part: 'Where', title: "3 · Knowing when it can't", render() {
      const st = scene.placement_study || {}, frs = (st.fragments || []).filter(f => f.run !== (mainCloud().meta.tag || '').slice(0, 8));
      const agree = (st.agreement_with_validated_frame || []).filter(a => a.building === 'McGraw Tower').map(a => a.median_distance_m);
      const lib = (st.agreement_with_validated_frame || []).filter(a => a.building === 'Uris Library');
      const synth = (st.identifiability || []).filter(x => x.cues === 'all cues' && x.camera_height_noise_m === 0 && x.seed === 0);
      body.innerHTML = `<h2>Knowing when it can't</h2>
        <p>The whole campus collection reconstructed at once on the GPU (${fmt(st.campus_run ? st.campus_run.photographs : null)} photographs in minutes, ${fmt(st.campus_run ? st.campus_run.registered : null)} registered): ${frs.length} fragments with eight or more cameras. The certificate refuses every one, each for a stated reason, and every placement the photographs' own GPS tags could check was far off, and refused.</p>
        <table><tr><th>fragment</th><th class="num">cameras</th><th>certificate</th><th class="num">GPS tags</th><th class="num">off by</th></tr>
          ${frs.map(f => `<tr><td>${f.building.replace('Bill and Melinda ', '')}</td><td class="num">${f.cameras}</td><td>${verdictBadge(f.verdict, f.failure_mode)}</td><td class="num">${f.geotags.plausible}/${f.geotags.carried}</td><td class="num">${f.ours_vs_geotags_m ? fmt(f.ours_vs_geotags_m.median) + ' m' : '—'}</td></tr>`).join('')}</table>
        ${agree.length ? `<p class="note">Against the validated tower-and-library placement: wherever the tower pins a campus fragment, its tower points coincide within ${fmt(Math.min(...agree), 1)}–${fmt(Math.max(...agree), 1)} m${lib.length ? `; the largest fragment's library points are ${fmt(lib[0].median_distance_m)} m off — its heading around the tower is wrong, and it was refused` : ''}.</p>` : ''}
        <h3>Why: a synthetic hall with a known answer</h3>
        <table><tr><th>facades in view</th><th class="num">roof-edge error</th><th class="num">scale</th><th class="num">heading</th><th>certificate</th></tr>
          ${synth.map(x => `<tr><td>${x.facades}</td><td class="num">${fmt(x.roof_edge_error_m)} m</td><td class="num">×${fmt(x.scale_ratio, 3)}</td><td class="num">${fmt(x.yaw_error_deg, 1)}°</td><td>${verdictBadge(x.verdict, x.failure_mode)}</td></tr>`).join('')}</table>
        <p class="note">One facade cannot fix its own scale; two parallel facades slide along each other; a wrong lidar roof edge is caught when walls fix the scale independently ("cues disagree"), and otherwise shows up as the stated scale uncertainty.</p>`;
      setView({ allPhotographers: true }); legend([['#303030', 'OpenStreetMap footprints']]);
      const t = building('McGraw Tower'), c = centroid(t.ring); flyTo([c[0] + 60, c[1] + 120, t.ground], 760, 0.95, -1.9);
      setYear(2023);
    } },
  { id: 'referee', part: 'How it looked', title: '4 · The lidar as referee', render() {
      const r = mainCloud().meta, plain = (r.splats || []).find(s => !s.lidar_taught) || (r.splats || [])[0];
      if (!plain) { body.innerHTML = '<h2>The lidar as referee</h2><p>No Gaussian splat has been trained for this fragment yet.</p>'; setView(); setYear(2023); return; }
      const fs = r.placement ? r.placement.sparse_points_free_space : null;
      const pb = Object.entries(plain.per_building).sort((a, b) => b[1].gaussians - a[1].gaussians).slice(0, 4);
      const poses = (plain.views && plain.views.poses) || [];
      body.innerHTML = `<h2>How it looked, checked against the world</h2>
        <p>A Gaussian splat trained from the same ${fmt(plain.images ? plain.images.train : null)} photographs (${fmt(plain.images ? plain.images.test : null)} held out), directly in the lidar's metres. Because it lives in the lidar frame, every Gaussian can be checked against what the lidar measured.</p>
        <div class="cues" id="refmode">
          ${poses.map((p, i) => `<label><input type="radio" name="refmode" value="pose-${i}" ${i === 0 ? 'checked' : ''}>${poseLabel(p, i)}</label>`).join('')}
          <label><input type="radio" name="refmode" value="campus" ${poses.length ? '' : 'checked'}>in the lidar campus</label>
          <label><input type="radio" name="refmode" value="verdict">the lidar's verdict on every Gaussian</label></div>
        <p class="note" id="refhint"></p>
        ${splatNumbers(plain)}
        <table><tr><th>building</th><th class="num">Gaussians</th><th class="num">median to lidar</th><th class="num">in free air</th><th class="num">covers the lidar building</th></tr>
          ${pb.map(([n, v]) => `<tr><td>${n}</td><td class="num">${fmt(v.gaussians)}</td><td class="num">${fmt(v.median_m, 2)} m</td><td class="num">${pct(v.in_free_air)}</td><td class="num">${pct(v.coverage)}</td></tr>`).join('')}</table>
        ${fs ? `<p class="note">For scale: COLMAP's own sparse points of this fragment sit on lidar surfaces ${pct(fs.surface)} of the time (${pct(fs.air)} in free air). Airborne lidar sees roofs and ground densely and walls thinly, so the distance is a conservative score for wall Gaussians.</p>` : ''}`;
      const tower = building('McGraw Tower'), c = centroid(tower.ring);
      const apply = () => {
        const mode = document.querySelector('input[name=refmode]:checked').value, hint = document.getElementById('refhint');
        if (mode.startsWith('pose-')) {
          const p = poses[+mode.slice(5)], ph = photographerOf(p);
          setView({ points: false, photographers: false, splat: null }); legend([]);
          showWipe({ url: p.photo_url, label: 'the photograph' }, { url: p.render_url, label: 'the splat, from the same pose' }, p.size);
          if (ph) flyToPhotographer(ph, 0.01);
          hint.textContent = (p.held_out ? 'A photograph the splat never saw. ' : 'A training photograph. ') + 'Drag across the image to compare; gsplat renders from the photographer\'s pose, colour fitted to the photograph as in the held-out PSNR.';
        } else {
          hideOverlay();
          const verdict = mode === 'verdict';
          setView({ points: false, photographers: false, splat: verdict ? null : plain.name, splatLayer: verdict ? plain.name : null });
          legend(verdict ? LEGEND_LIDAR : [['#b5532c', 'buildings that changed since 2002']]); setYear(year);
          if (!verdict) showSplat(plain.name, 'referee');
          flyTo([c[0], c[1], tower.ground + 18], 190, 0.35, photographersAzimuth(tower));
          hint.textContent = verdict ? 'Every opaque Gaussian inside the lidar\'s measured volume, coloured by what the lidar says about where it sits.' : 'The live splat inside the lidar campus. Away from the photographers\' viewpoints a splat of internet photographs is only half constrained: what you see from up here is the reason it needs a referee.';
        }
      };
      for (const x of document.querySelectorAll('input[name=refmode]')) x.onchange = apply;
      apply(); setYear(2023);
    } },
  { id: 'teacher', part: 'How it looked', title: '5 · The lidar as teacher', render() {
      const r = mainCloud().meta, S = r.splats || [], plain = S.find(s => !s.lidar_taught), taught = S.find(s => s.lidar_taught);
      if (!plain || !taught) { body.innerHTML = '<h2>The lidar as teacher</h2><p>The lidar-taught splat has not been trained yet.</p>'; setView(); setYear(2023); return; }
      const row = (label, f, cls) => `<tr><td>${label}</td><td class="num">${f(plain)}</td><td class="num ${cls || ''}">${f(taught)}</td></tr>`;
      const poses = (plain.views && taught.views) ? plain.views.poses.filter(p => taught.views.poses.some(q => q.photo === p.photo)) : [];
      const fly = plain.views && taught.views && plain.views.fly && taught.views.fly;
      body.innerHTML = `<h2>The lidar as teacher</h2>
        <p>Same photographs, same steps, one extra rule from the lidar: <b>the air above the measured surface is empty</b>, and nothing lies under the bare ground. Gaussians that break it are made transparent, and the ones far in the air are removed.</p>
        <div class="cues" id="tchmode">
          ${fly ? `<label><input type="radio" name="tchmode" value="fly" checked>fly-through</label>` : ''}
          ${poses.map((p, i) => `<label><input type="radio" name="tchmode" value="pose-${i}" ${!fly && i === 0 ? 'checked' : ''}>${poseLabel(p, i)}</label>`).join('')}
          <label><input type="radio" name="tchmode" value="campus" ${!fly && !poses.length ? 'checked' : ''}>in the lidar campus</label></div>
        <div class="cues" id="tchcampus" hidden><label><input type="radio" name="tch" value="${taught.name}" checked>lidar-taught</label><label><input type="radio" name="tch" value="${plain.name}">plain</label><label><input type="checkbox" id="tch-layer">show the lidar's verdict</label></div>
        <p class="note" id="tchhint"></p>
        <table><tr><th></th><th class="num">plain</th><th class="num">lidar-taught</th></tr>
          ${row('on lidar surfaces', s => pct(s.free_space.on_surfaces, 1), taught.free_space.on_surfaces > plain.free_space.on_surfaces ? 'ok' : '')}
          ${row('under the bare ground', s => pct(s.free_space.buried, 1), taught.free_space.buried < plain.free_space.buried ? 'ok' : '')}
          ${row('in air the lidar saw empty', s => pct(s.free_space.in_free_air, 1), taught.free_space.in_free_air < plain.free_space.in_free_air ? 'ok' : 'bad')}
          ${row('median distance to the lidar', s => fmt(s.overall.median_m, 2) + ' m', taught.overall.median_m < plain.overall.median_m ? 'ok' : '')}
          ${row('Gaussians in the measured volume', s => fmt(s.gaussians.in_measured_volume))}
          ${row('held-out PSNR (mean of ' + fmt(plain.images ? plain.images.test : null) + ')', s => s.psnr && s.psnr.test_mean ? fmt(s.psnr.test_mean, 1) + ' dB' : '—')}
          ${row('training time', s => s.seconds ? fmt(s.seconds / 60) + ' min' : '—')}</table>
        <p class="note">${taught.prior ? `Removed during training: ${fmt(taught.prior.pruned)} Gaussians more than ${fmt(taught.prior.prune_above_m)} m into measured free air.` : ''} The far field (sky and the background beyond the lidar crop) is not judged and not shown.</p>
        ${(r.splat_ablations || []).map(a => `<p class="finding">How far can the teacher go? A ${fmt(a.prior.weight / taught.prior.weight)}-times stronger rule puts ${pct(a.free_space.on_surfaces)} of the Gaussians on lidar surfaces — more than COLMAP's own points (${pct(r.placement ? r.placement.sparse_points_free_space.surface : null)}) — but the best-covered held-out view drops from ${fmt(taught.psnr_best_covered_view, 1)} to ${fmt(a.psnr_best_covered_view, 1)} dB: at that strength it carves real structure that the lidar's 2.5 m tolerance and the placement's few-metre error put outside. The demo keeps the gentler rule.</p>`).join('')}`;
      const tower = building('McGraw Tower'), c = centroid(tower.ring);
      const apply = () => {
        const mode = document.querySelector('input[name=tchmode]:checked').value, hint = document.getElementById('tchhint');
        document.getElementById('tchcampus').hidden = mode !== 'campus';
        if (mode === 'fly') {
          setView({ points: false, photographers: false }); legend([]);
          showFly({ views: plain.views, label: 'plain splat', splat: plain }, { views: taught.views, label: 'lidar-taught splat', splat: taught });
          hint.textContent = 'The same camera path through both splats, between the photographers who face the tower. It pauses at each photographer\'s spot and shows the photograph taken there; tick the box to paint every Gaussian by what the lidar says about it.';
        } else if (mode.startsWith('pose-')) {
          const p = poses[+mode.slice(5)], q = taught.views.poses.find(x => x.photo === p.photo), ph = photographerOf(p);
          setView({ points: false, photographers: false }); legend([]);
          showWipe({ url: p.render_url, label: 'plain' + (p.psnr ? ' · ' + fmt(p.psnr, 1) + ' dB' : '') }, { url: q.render_url, label: 'lidar-taught' + (q.psnr ? ' · ' + fmt(q.psnr, 1) + ' dB' : '') }, p.size);
          if (ph) flyToPhotographer(ph, 0.01);
          hint.textContent = (p.held_out ? 'A photograph neither splat saw. ' : 'A training photograph. ') + 'Drag across the image: plain on the left, lidar-taught on the right.';
        } else {
          hideOverlay();
          const name = document.querySelector('input[name=tch]:checked').value, layer = document.getElementById('tch-layer').checked;
          setView({ points: false, photographers: false, splat: layer ? null : name, splatLayer: layer ? name : null });
          legend(layer ? LEGEND_LIDAR : [['#b5532c', 'buildings that changed since 2002']]); setYear(year); if (!layer) showSplat(name, 'teacher');
          flyTo([c[0], c[1], tower.ground + 18], 190, 0.35, photographersAzimuth(tower));
          hint.textContent = 'Inside the lidar campus; switch between the two splats, or show the lidar\'s verdict on every Gaussian.';
        }
      };
      for (const x of document.querySelectorAll('input[name=tchmode], input[name=tch], #tch-layer')) x.onchange = apply;
      apply(); setYear(2023);
    } },
  { id: 'above', part: 'When', title: '6 · From above', render() {
      body.innerHTML = `<h2>The campus from above, 2002 to 2023</h2>
        <p>Public New York State orthoimagery, one flight every few years, draped on USGS lidar terrain. Drag the year. The three outlined buildings did not exist in 2002.</p>
        <p><button type="button" id="play">▶ play the years</button></p>
        <ul>${changed.map(b => `<li><b>${b.name.replace('Bill and Melinda ', '')}</b> — <span class="state" data-state-of="${b.name}"></span></li>`).join('')}</ul>
        <p class="note">Flight years: ${YEARS.join(', ')}. Between flights the latest earlier image is shown. Building volumes are the 2020 lidar shape, shown only in years the documented dates say the building stood.</p>`;
      document.getElementById('play').onclick = play;
      setView();
      legend([['#b5532c', 'buildings that changed (outline; volume from 2020 lidar when standing)'], ['#303030', 'other footprints (OpenStreetMap)']]);
      const t = building('McGraw Tower'), c = centroid(t.ring);
      flyTo([c[0] + 60, c[1] + 40, t.ground], 900, 0.95, -1.9); setYear(year);
    } },
  { id: 'gates', part: 'When', title: '7 · Gates Hall', render() { setView(); buildingChapter('Bill and Melinda Gates Hall', 'A parking lot until 2012; a Thom Mayne building from 2014. Slide from 2007 to 2015 and watch the air photographs change; the volume is the lidar shape of the finished building.'); } },
  { id: 'klarman', part: 'When', title: '8 · Klarman Hall', render() { setView(); buildingChapter('Klarman Hall', 'The courtyard behind Goldwin Smith Hall until the 2012 flight, under construction in the 2015 flight, a glass atrium from 2016.'); } },
  { id: 'tower', part: 'When', title: '9 · Twenty years of one tower', render() {
      const r = mainCloud().meta;
      const own = scene.photographers.filter(p => p.reconstruction === r.tag); const dated = own.filter(p => p.year);
      const counts = {}; for (const p of dated) counts[p.year] = (counts[p.year] || 0) + 1;
      const maxc = Math.max(1, ...Object.values(counts));
      body.innerHTML = `<h2>McGraw Tower: the thing that does not change</h2>
        <p>${fmt(own.length)} photographs of the tower and Uris Library, ${fmt(r.dated_photographs)} of them dated from ${Math.min(...dated.map(p => p.year))} to ${Math.max(...dated.map(p => p.year))}. Each reconstructed point carries the years in which photographs observed it; the slider shows the points seen by that year.</p>
        <div class="yearbar">${Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i).map(y => `<div data-year="${y}" style="height:${100 * (counts[y] || 0) / maxc}%" title="${y}: ${counts[y] || 0} dated photographs"></div>`).join('')}</div>
        <div class="yearlabels"><span>${MIN_YEAR}</span><span>dated photographs per year</span><span>${MAX_YEAR}</span></div>
        <div class="cues"><label><input type="radio" name="col" value="photo" ${colourMode === 'photo' ? 'checked' : ''}>photo colours</label><label><input type="radio" name="col" value="first" ${colourMode === 'first' ? 'checked' : ''}>colour by first year seen</label>${r.mesh ? `<label><input type="checkbox" id="surface" ${mainCloud().surface ? '' : 'disabled'}>dense surface (${fmt(r.mesh.faces)} faces)</label>` : ''}</div>
        <p>Click a photographer (sphere) to see the photograph; red = taken in the selected year.</p><div id="pick"></div>`;
      for (const x of document.querySelectorAll('input[name=col]')) x.onchange = () => { colourMode = x.value; setYear(year); };
      setView();
      const sf = document.getElementById('surface'); if (sf) sf.onchange = () => { setView({ surface: sf.checked, points: !sf.checked }); setYear(year); };
      legend([['#2a6fdb', 'photographers before the selected year'], ['#d0453a', 'photographers in the selected year'], ['#9aa5b1', 'later photographers']]);
      const t = building('McGraw Tower'), c = centroid(t.ring);
      flyTo([c[0], c[1], t.ground + 20], 220, 0.35, photographersAzimuth(t)); setYear(year);
    } },
  { id: 'limits', part: 'When', title: '10 · What the record cannot show', render() {
      const st = scene.placement_study || {};
      body.innerHTML = `<h2>What the record cannot show</h2>
        <ul>
          <li><b>Most fragments cannot be placed yet.</b> Of the campus-wide run's ${(st.fragments || []).filter(f => f.run !== (mainCloud().meta.tag || '').slice(0, 8)).length} larger fragments none is certified: a square tower cannot fix its own heading, one facade cannot fix its own scale, and close-ups of an entrance show no facade the map knows. The certificate says which, instead of placing them wrongly.</li>
          <li><b>No licensed ground-level photograph of any site before construction exists online.</b> The "before" is aerial only; no 3D of the old parking lots or the courtyard is shown.</li>
          <li><b>Airborne lidar sees roofs and ground, not walls.</b> A Gaussian on a wall is judged against the nearest roof edge or ground return, so the distance score is conservative there; the free-air test tolerates 2.5 m horizontally for the same reason.</li>
          <li><b>Building volumes are the 2020 lidar shape</b>, displayed only in years the documented dates say the building stood.</li>
          <li><b>The automatic aerial test is a diagnostic.</b> Its outline score rises at every site when the building appears, but stable buildings vary between flights by as much, so the dates on this page are the documented ones.</li>
          <li><b>Boardman Hall (demolished 1959)</b> is beyond the time machine: its postcards can be matched to the surviving tower and library, but every recovered pose is a mirror image, because no licensed modern photograph looks at the tower from the Arts Quad side.</li>
        </ul>`;
      setView(); legend([]); setYear(year);
    } },
];
let current = null;
let lastPart = null;
for (const ch of chapters) {
  if (ch.part !== lastPart) { nav.append(el('span', { className: 'part' }, ch.part)); lastPart = ch.part; }
  nav.append(Object.assign(el('button', { type: 'button' }, ch.title), { onclick: () => show(ch.id) }));
  nav.lastChild.dataset.chapter = ch.id;   // the recorded tour and the checks find chapters by id
}
function show(id) {
  if (!chapters.some(c => c.id === id)) id = 'colmap';
  const ch = chapters.find(c => c.id === id); current = id;
  for (const b of nav.querySelectorAll('button')) b.setAttribute('aria-current', String(b.textContent === ch.title));
  if (id !== 'void' && placement.mode === 'floating') { placement.mode = 'placed'; poseAt(1, 0); }
  placement.done = null;   // a snap still running from the previous chapter must not move this chapter's camera
  status(''); hideOverlay(); body.innerHTML = ''; ch.render(); body.scrollTop = 0; history.replaceState(null, '', '#' + id);
}

// --- presenter keys: arrows or page keys step through the chapters, F toggles full screen ------------------
addEventListener('keydown', e => {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.metaKey || e.ctrlKey || e.altKey) return;
  const i = chapters.findIndex(c => c.id === current);
  if (['ArrowRight', 'PageDown'].includes(e.key) && i < chapters.length - 1) { e.preventDefault(); show(chapters[i + 1].id); }
  else if (['ArrowLeft', 'PageUp'].includes(e.key) && i > 0) { e.preventDefault(); show(chapters[i - 1].id); }
  else if (e.key === 'f' || e.key === 'F') { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen().catch(() => {}); }
});

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
renderer.setAnimationLoop(() => { stepFlight(); stepPlacement(); controls.update(); renderer.render(world, camera); });
document.getElementById('attribution').textContent = scene.attribution.join(' ');
document.getElementById('status').textContent = '';
setYear(2007);
show((location.hash || '#colmap').slice(1).replace(/[^a-z]/g, ''));
window.__tm = { terrains, textures, scene, clouds, view, placement, show, camera, controls, cityParts, specialMeshes, gpuName };  // for the headless checks and the recorded tour
document.documentElement.dataset.ready = 'true';
