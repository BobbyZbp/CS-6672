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
Object.assign(sun.shadow.camera, { left: -560, right: 560, top: 560, bottom: -560, near: 10, far: 2400 });
world.add(sun); world.add(sun.target);
// The shadow box follows the light's axis: centre it between the Quad and the Gates Hall site so both cast shadows.
const sceneCentre = new THREE.Vector3(260, 120, 245); sun.target.position.copy(sceneCentre); sun.position.add(sceneCentre);

let flight = null;
function flyTo(target, distance, elevation = 0.7, azimuth = -2.0, seconds = 1.4) {
  const from = { pos: camera.position.clone(), tgt: controls.target.clone() };
  const to = { tgt: new THREE.Vector3(...target) };
  to.pos = new THREE.Vector3(to.tgt.x + distance * Math.cos(azimuth) * Math.cos(elevation), to.tgt.y + distance * Math.sin(azimuth) * Math.cos(elevation), to.tgt.z + distance * Math.sin(elevation));
  lookUp(false); flight = { from, to, t0: performance.now(), ms: seconds * 1000, fov: { from: camera.fov, to: 48 } };
}
// Orbiting stays above the horizon; a photographer looking up at the tower needs the camera below its target, and the
// clamp would otherwise lift the camera tens of metres off the photographer's spot.
function lookUp(on) { controls.maxPolarAngle = on ? Math.PI - 0.02 : Math.PI / 2 - 0.02; }
// Stand where a photographer stood, looking where the photograph looks, with its field of view: a splat is only
// trustworthy near the views it was trained from (and a held-out photographer's view is the honest test).
function flyToPhotographer(p, seconds = 1.6) {
  const R = p.rotation, fwd = new THREE.Vector3(...R[2]).normalize(), pos = new THREE.Vector3(...p.centre);
  const fov = 2 * Math.atan(p.height / 2 / p.focal_px) * 180 / Math.PI;
  lookUp(true); flight = { from: { pos: camera.position.clone(), tgt: controls.target.clone() }, to: { pos, tgt: pos.clone().addScaledVector(fwd, 60) },
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

// --- a photograph painted back onto the city from where it was taken ------------------------------------------------
// Every surface of the lidar city is projected into the photograph from the photographer's pose; it takes the
// photograph's colour only where it is the nearest surface along that ray (a depth map rendered from the pose) and
// faces the camera. If the placement is right, the photograph's walls land on the lidar's walls.
const PROJ_LAYER = 1, PROJ_NEAR = 2, PROJ_FAR = 2500;
const projector = { camera: new THREE.PerspectiveCamera(50, 1, PROJ_NEAR, PROJ_FAR), target: new THREE.WebGLRenderTarget(2048, 2048), on: 0, pose: null };
projector.target.depthTexture = new THREE.DepthTexture(2048, 2048); projector.target.depthTexture.type = THREE.UnsignedIntType;
projector.camera.layers.set(PROJ_LAYER);
const projUniforms = { uProjTex: { value: null }, uProjDepth: { value: projector.target.depthTexture }, uProjMat: { value: new THREE.Matrix4() },
                       uProjPos: { value: new THREE.Vector3() }, uProjOn: { value: 0 }, uProjNearFar: { value: new THREE.Vector2(PROJ_NEAR, PROJ_FAR) } };
function projectable(mat) {
  mat.onBeforeCompile = shader => {
    Object.assign(shader.uniforms, projUniforms);
    shader.vertexShader = shader.vertexShader.replace('#include <common>', '#include <common>\nuniform mat4 uProjMat; varying vec4 vProj; varying vec3 vPW; varying vec3 vPN;')
      .replace('#include <project_vertex>', `#include <project_vertex>
        vec4 pw = vec4(transformed, 1.0); vec3 pn = objectNormal;
        #ifdef USE_INSTANCING
          pw = instanceMatrix * pw; mat3 pim = mat3(instanceMatrix);   // each tree is turned and scaled on its own
          pn = pim * (pn / vec3(dot(pim[0], pim[0]), dot(pim[1], pim[1]), dot(pim[2], pim[2])));
        #endif
        pw = modelMatrix * pw; vPW = pw.xyz; vProj = uProjMat * pw; vPN = normalize(mat3(modelMatrix) * pn);`);
    shader.fragmentShader = shader.fragmentShader.replace('#include <common>', `#include <common>
      uniform sampler2D uProjTex; uniform sampler2D uProjDepth; uniform vec3 uProjPos; uniform float uProjOn; uniform vec2 uProjNearFar;
      varying vec4 vProj; varying vec3 vPW; varying vec3 vPN;
      float projLinear(float z) { float n = uProjNearFar.x, f = uProjNearFar.y; return 2.0 * n * f / (f + n - (2.0 * z - 1.0) * (f - n)); }`)
      .replace('#include <opaque_fragment>', `#include <opaque_fragment>
      if (uProjOn > 0.001 && vProj.w > 0.0) {
        vec3 ndc = vProj.xyz / vProj.w; vec2 puv = ndc.xy * 0.5 + 0.5;
        if (puv.x > 0.0 && puv.x < 1.0 && puv.y > 0.0 && puv.y < 1.0 && ndc.z < 1.0) {
          float seen = projLinear(texture2D(uProjDepth, puv).x), here = projLinear(ndc.z * 0.5 + 0.5);
          float facing = dot(normalize(vPN), normalize(uProjPos - vPW));
          if (here <= seen + 0.6 + 0.004 * here && facing > 0.02) {
            float edge = smoothstep(0.0, 0.02, min(min(puv.x, 1.0 - puv.x), min(puv.y, 1.0 - puv.y)));
            gl_FragColor.rgb = mix(gl_FragColor.rgb, texture2D(uProjTex, puv).rgb, uProjOn * edge * smoothstep(0.02, 0.2, facing));
          }
        }
      }`);
  };
  mat.customProgramCacheKey = () => 'projectable'; mat.needsUpdate = true;
}
const depthOnly = new THREE.MeshBasicMaterial({ colorWrite: false });
function projectFrom(p, url) {   // p: {centre, rotation (camera from world, rows), focal_px, width, height}
  const R = p.rotation, C = new THREE.Vector3(...p.centre), cam = projector.camera;
  cam.position.copy(C); cam.up.set(...R[1]).negate(); cam.lookAt(C.clone().add(new THREE.Vector3(...R[2])));
  cam.fov = 2 * Math.atan(p.height / 2 / p.focal_px) * 180 / Math.PI; cam.aspect = p.width / p.height; cam.updateProjectionMatrix(); cam.updateMatrixWorld();
  projUniforms.uProjMat.value.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse); projUniforms.uProjPos.value.copy(C);
  projUniforms.uProjTex.value = texture(url); projector.pose = p;
  const keep = [world.overrideMaterial, world.background, world.fog];
  world.overrideMaterial = depthOnly; world.background = null; world.fog = null;
  renderer.setRenderTarget(projector.target); renderer.clear(); renderer.render(world, cam); renderer.setRenderTarget(null);
  [world.overrideMaterial, world.background, world.fog] = keep;
}
function projectionOn(v) { projector.on = v; }
for (const m of [...Object.values(terrains).map(t => t.mesh), ...cityParts.roofs, ...cityParts.walls, ...cityParts.trees, ...Object.values(specialMeshes).flat()]) {
  m.layers.enable(PROJ_LAYER); projectable(m.material);
}
// The photographer of a placed photograph: a camera frustum, and the segment it may stand on when the distance is open.
const placedGroup = new THREE.Group(); world.add(placedGroup);
function showPlaced(p) {
  placedGroup.clear(); placedGroup.visible = true; if (!p || !p.centre) return;
  const R = p.rotation, C = new THREE.Vector3(...p.centre), fwd = new THREE.Vector3(...R[2]), right = new THREE.Vector3(...R[0]), down = new THREE.Vector3(...R[1]);
  const d = 14, hw = d * p.width / 2 / p.focal_px, hh = d * p.height / 2 / p.focal_px;
  const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([a, b]) => C.clone().addScaledVector(fwd, d).addScaledVector(right, a * hw).addScaledVector(down, b * hh));
  const pts = corners.flatMap(c => [C, c]).concat(corners.flatMap((c, i) => [c, corners[(i + 1) % 4]]));
  placedGroup.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: 0xe02924 })));
  const s = new THREE.Mesh(new THREE.SphereGeometry(2.2, 14, 10), new THREE.MeshBasicMaterial({ color: 0xe02924 })); s.position.copy(C); placedGroup.add(s);
  if (p.segment && p.segment.length === 2 && (p.distance_uncertainty_m || 0) > 25) {
    const [a, b] = p.segment.map(v => new THREE.Vector3(...v));
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]), new THREE.LineDashedMaterial({ color: 0xe02924, dashSize: 4, gapSize: 3 }));
    line.computeLineDistances(); placedGroup.add(line);
  }
}
// Standing where a photographer stood, the photograph covers only its own field of view: a viewfinder draws that frame
// on the screen (the frustum's corners projected every frame) and dims the city around it.
const viewfinder = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
viewfinder.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;display:none';
viewfinder.innerHTML = '<path fill="rgba(12,14,16,.5)" fill-rule="evenodd"/><polygon fill="none" stroke="#fff" stroke-width="2"/>';
canvas.after(viewfinder);
let standing = null;   // the pose whose frame is drawn
function drawViewfinder() {
  if (!standing) { viewfinder.style.display = 'none'; return; }
  const p = standing, R = p.rotation, C = new THREE.Vector3(...p.centre), fwd = new THREE.Vector3(...R[2]), right = new THREE.Vector3(...R[0]), down = new THREE.Vector3(...R[1]);
  const w = canvas.clientWidth, h = canvas.clientHeight, hw = 50 * p.width / 2 / p.focal_px, hh = 50 * p.height / 2 / p.focal_px;
  const xy = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([a, b]) => C.clone().addScaledVector(fwd, 50).addScaledVector(right, a * hw).addScaledVector(down, b * hh).project(camera));
  if (xy.some(v => v.z > 1)) { viewfinder.style.display = 'none'; return; }   // a corner behind the camera
  const pts = xy.map(v => [((v.x + 1) / 2 * w).toFixed(1), ((1 - v.y) / 2 * h).toFixed(1)]);
  viewfinder.setAttribute('viewBox', `0 0 ${w} ${h}`); viewfinder.style.display = '';
  viewfinder.firstChild.setAttribute('d', `M0 0H${w}V${h}H0Z M${pts.map(q => q.join(' ')).join(' L')}Z`);
  viewfinder.lastChild.setAttribute('points', pts.map(q => q.join(',')).join(' '));
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
const dist = m => m >= 1000 ? fmt(m / 1000, 1) + ' km' : fmt(m) + ' m';
// A fragment's GPS, as the evaluation found it (evaluate/georegistration.py): the tags it carries, how far the wrong ones
// lie from where the placement puts their cameras, and how many photographs came as web copies without any metadata.
function gpsSentence(g, n) {
  const off = g.wrong_off_m || [], none = g.without_metadata;
  return `GPS on ${fmt(g.carried)} of ${fmt(n)} photographs${off.length ? `, ${off.length === 1 ? 'and it is' : 'and they are'} ${off.map(dist).join(', ')} off` : ''}` +
    (none ? `; ${fmt(none)} are Flickr copies with no metadata at all` : '');
}
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
// Where the photographers stood, as seen from the tower: the side from which the splat is best seen.
function photographersAzimuth(tower) {
  const c = centroid(tower.ring), own = scene.photographers.filter(p => p.reconstruction === (mainCloud() || {}).meta?.tag);
  const v = own.reduce((a, p) => [a[0] + p.centre[0] - c[0], a[1] + p.centre[1] - c[1]], [0, 0]);
  return Math.atan2(v[1], v[0]);
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
  const MAP_W = 290, MAP_H = 190;   // the map's box; the panes get what is left after the header and the footer
  const pw = Math.floor(Math.min((W - 10) / 2, (H - MAP_H - 70) * ar)), ph = Math.round(pw / ar);
  const who = keys.map(k => scene.photographers.find(p => p.name === k.image));
  overlay.innerHTML = `<div class="fly" style="width:${2 * pw + 10}px">
    <div class="flyhead"><b>A camera path no photographer took.</b> It walks between the spots where ${keys.length} photographers stood (map, lower left; McGraw Tower in gold). Both splats were trained on the same photographs.</div>
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
  const s = Math.min(MAP_W / (x1 - x0), MAP_H / (y1 - y0)), mw = Math.round((x1 - x0) * s), mh = Math.round((y1 - y0) * s);
  const X = x => ((x - x0) * s).toFixed(1), Y = y => ((y1 - y) * s).toFixed(1);
  svg.setAttribute('viewBox', `0 0 ${mw} ${mh}`); svg.style.width = mw + 'px'; svg.style.height = mh + 'px';
  const near = scene.buildings.filter(bd => bd.ring.some(([x, y]) => x > x0 && x < x1 && y > y0 && y < y1));
  const own = scene.photographers.filter(p => p.reconstruction === (mainCloud() || {}).meta?.tag && p.centre[0] > x0 && p.centre[0] < x1 && p.centre[1] > y0 && p.centre[1] < y1);
  svg.innerHTML = `<rect width="${mw}" height="${mh}" fill="#20262c"/>
    ${near.map(bd => `<polygon points="${bd.ring.map(([x, y]) => X(x) + ',' + Y(y)).join(' ')}" fill="${bd.name === 'McGraw Tower' ? '#c8a96a' : '#4a525a'}" stroke="#6b747d" stroke-width="0.6"/>`).join('')}
    ${own.map(p => `<circle cx="${X(p.centre[0])}" cy="${Y(p.centre[1])}" r="1.8" fill="#7d8b99"/>`).join('')}
    <polyline points="${cams.map(c => X(c.centre[0]) + ',' + Y(c.centre[1])).join(' ')}" fill="none" stroke="#e8e2d0" stroke-width="1.2" stroke-dasharray="3 2"/>
    ${keys.map((k, i) => `<g><circle cx="${X(k.centre[0])}" cy="${Y(k.centre[1])}" r="6.5" fill="#2a6fdb" stroke="#fff" stroke-width="1"/><text x="${X(k.centre[0])}" y="${(+Y(k.centre[1]) + 3.2).toFixed(1)}" text-anchor="middle" font-size="8.5" font-weight="700" fill="#fff">${i + 1}</text></g>`).join('')}
    <path class="cone" fill="rgba(224,41,36,.28)" stroke="#e02924" stroke-width="1"/><circle class="cam" r="3.6" fill="#e02924" stroke="#fff" stroke-width="1"/>
    <text x="6" y="${mh - 6}" font-size="9" fill="#c8c2b4">N ↑</text>
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

// --- chapters, each a sequence of steps ---------------------------------------------------------------
// A chapter: { id, part, title, purpose, setup() -> ctx, steps }. A step: { title, see, body(ctx), after(ctx), view(ctx), sum(ctx) }.
// `see` is the one sentence the viewport caption shows (what the 3D view is showing now), `body` the step's text and
// result, `after` binds the controls once the body is in the page, `view` sets the 3D view, `sum` the one-line result
// the step collapses to once it is taken. Steps are self-contained: any step can be opened from a link.
const stat = (v, label, meaning, wide) => `<div class="r${wide ? ' wide' : ''}"><div class="v">${v}</div><div class="l">${label}</div>${meaning ? `<div class="m">${meaning}</div>` : ''}</div>`;
const results = (...cards) => `<div class="result">${cards.join('')}</div>`;
const strong = (v, unit = '') => `<b>${v}</b>${unit}`;
// The cues of the placement (anchor/georegister.py), in words; their scores at the optimum come from the certificate.
const CUES = [
  ['walls', 'Walls', 'the reconstructed points should lie on the footprint walls, and every wall in view should carry points'],
  ['roof_edges', 'Roof edges', 'where a wall meets the lidar roof fixes the height of that facade, and with it the scale'],
  ['camera_height', 'Camera height', 'photographers stand at eye height on the lidar ground'],
  ['landmark', 'Tower top', 'the highest cluster of points is the top of McGraw Tower, whose lidar height is known'],
  ['free_space', 'Free space', 'the line from a camera to each point it saw must not pass through a building'],
  ['outside', 'Cameras outside', 'no photographer stands inside a footprint'],
];
const cueCards = scores => `<div class="cuelist">${CUES.map(([k, name, what]) => `<div class="cue"><div class="head"><b>${name}</b>${scores ? `<span class="score">${fmt(scores[k], 2)}</span>` : ''}</div><div class="what">${what}</div>${scores ? `<div class="bar"><i style="width:${(100 * scores[k]).toFixed(0)}%"></i></div>` : ''}</div>`).join('')}</div>`;
const towerView = (distance = 240, elevation = 0.42) => { const t = building('McGraw Tower'), c = centroid(t.ring); flyTo([c[0], c[1], t.ground + 20], distance, elevation, photographersAzimuth(t), 1.6); };
const campusView = () => { const t = building('McGraw Tower'), c = centroid(t.ring); flyTo([c[0] + 60, c[1] + 120, t.ground], 760, 0.95, -1.9); };
const settled = () => { if (placement.mode !== 'placed') { placement.mode = 'placed'; poseAt(1, 0); } };   // the fragment in its placed pose
const fragmentOf = tag => scene.photographers.filter(p => p.reconstruction === tag);
const CITY_LEGEND = [['#c8a96a', 'buildings: OpenStreetMap footprints raised to the USGS lidar roofs'], ['#4f7a3a', 'trees: one per lidar canopy peak']];
const CHANGED_LEGEND = [['#b5532c', 'buildings that changed (outline; volume from 2020 lidar when standing)'], ['#303030', 'other footprints (OpenStreetMap)']];

// What the page shows of a building that changed: documented dates, the flights, the ground record, one flight per step.
function buildingSteps(name, intro, years) {
  const b = building(name), d = b.documented, g = b.ground_photographs;
  const label = y => ({ before: `not yet built — ${d.before}`, works: 'under construction', present: 'standing' })[state(b, y)] || 'standing';
  const go = y => {
    const c = centroid(b.ring), span = Math.max(...b.ring.map(p => p[0])) - Math.min(...b.ring.map(p => p[0]));
    setView(); flyTo([c[0], c[1], b.ground + 5], Math.max(160, span * 2.4), 0.55, -2.3); legend(CHANGED_LEGEND); setYear(y);
  };
  const crops = Object.keys(b.aerial_crops || {});
  return {
    setup: () => ({ b }),
    steps: [
      { title: 'Documented', see: () => `the site in the ${flightYearFor(years[0])} flight: ${label(years[0])}.`,
        body: () => `<p>${intro}</p><p><span class="state" data-state-of="${name}"></span></p><p><b>Documented.</b> ${d.documented}${d.source ? ` <a href="${d.source}" target="_blank" rel="noopener">source</a>` : ''}.</p>`,
        view: () => go(years[0]), sum: () => d.documented },
      { title: 'From the air', see: () => `the site in the ${flightYearFor(years[1])} flight. The strip shows it in every flight, this one outlined; the volume follows the documented dates, not the picture.`,
        body: () => `<p>New York State orthoimagery, one flight every few years, draped on the lidar terrain. The number under each crop is the building's own-outline edge score, a diagnostic: it rises when the building appears, but stable buildings vary between flights by as much, so the dates on this page are the documented ones.</p>${strip(b)}`,
        view: () => go(years[1]), sum: () => `${crops.length} flights, ${crops[0]}–${crops[crops.length - 1]}` },
      { title: 'From the ground', see: () => `${years[2]}: ${label(years[2])}. The volume is the 2020 lidar shape, drawn only in years the documented dates say the building stood.`,
        body: () => `<p>${g ? `${fmt(g.points)} reconstructed points on this building; first photographed ${g.earliest_photograph}, last ${g.latest_photograph}.` : groundRecord(b)}</p>${recordStrip(b)}`,
        view: () => go(years[2]), sum: () => g ? `first photographed from the ground ${g.earliest_photograph}` : (b.ground_record ? `${fmt(b.ground_record.photographs)} licensed photographs; no anchored ground model` : 'no licensed photographs in the collection') },
    ],
  };
}

const chapters = [
  { id: 'colmap', part: 'Beyond COLMAP', title: '0 · Where COLMAP stops', purpose: 'What the page starts from, where COLMAP stops on internet photographs of a real place, and what GhostMap adds.',
    setup() {
      const r = mainCloud().meta, st = scene.placement_study || {}, own = fragmentOf(r.tag);
      const tagged = (st.fragments || []).find(f => f.run === r.tag.slice(0, 8) && String(f.fragment) === r.tag.split('-')[1]);
      const frs = (st.fragments || []).filter(f => f.run !== r.tag.slice(0, 8)), refused = frs.filter(f => f.verdict !== 'usable');
      const agree = (st.agreement_with_validated_frame || []).filter(a => a.building === 'McGraw Tower').map(a => a.median_distance_m);
      const years = own.filter(p => p.year).map(p => p.year), S = r.splats || [];
      const t = scene.sites.quad.terrain;
      return { r, own, tagged, frs, refused, agree, years, plain: S.find(s => !s.lidar_taught), taught: S.find(s => s.lidar_taught), box: t.x1 - t.x0, buildings: scene.buildings.length };
    },
    steps: [
      { title: 'The world already has a 3D model',
        see: ctx => `the campus from measurement only: OpenStreetMap footprints raised to the USGS lidar roofs, one tree per lidar canopy peak, the 2023 aerial flight draped over the lidar ground.`,
        body: ctx => `<p>Everything here starts from COLMAP's cameras and points (pycolmap, SuperPoint and LightGlue). GhostMap puts them inside <b>this</b> model, with public data only: USGS 3DEP airborne lidar, in metres, and OpenStreetMap building footprints. No GPS, no hand-picked point.</p>
          ${results(stat(fmt(ctx.buildings), 'buildings', 'footprints inside the lidar box, each raised to its lidar roof'), stat(fmt(ctx.box) + ' m', 'lidar box', 'bare ground and surface, from the public lidar'))}
          <p class="note">The chapters: <b>where</b> a fragment stands (1–3, and 11 for a photograph it has never seen), <b>how it looked</b> (4–5: Gaussian splats refereed and taught by the lidar), <b>when</b> (6–10: twenty years of aerial flights and dated points).</p>`,
        view() { setView({ points: false, photographers: false }); legend(CITY_LEGEND); const t = building('McGraw Tower'), c = centroid(t.ring); flyTo([c[0] + 90, c[1] + 140, t.ground], 820, 0.62, -2.05); setYear(2023); },
        sum: ctx => `public lidar and footprints: ${fmt(ctx.buildings)} buildings in a ${fmt(ctx.box)} m box` },
      { title: 'Six limits, six answers',
        see: 'the same campus. The tower-and-library fragment, COLMAP\'s output, is not in it yet: that is chapter 1.',
        body: ctx => {
          const { r, own, tagged, frs, refused, agree, years, plain, taught } = ctx;
          const go = (id, label) => `<button type="button" class="jump" data-go="${id}">${label} →</button>`;
          const rows = [
            ['A model in its own frame (no scale, north or up); a map needs GPS or hand-picked control points.', 'Placement without GPS, inside public lidar and building footprints.', tagged ? gpsSentence(tagged.geotags, own.length) : '', go('void', 'chapters 1–2')],
            ['Never says when a placement cannot be trusted.', 'A certificate: which cue fixed what, or a refusal with the reason.', `${refused.length} of ${frs.length} campus fragments refused, each with a stated reason`, go('refuse', 'chapter 3')],
            ['Disconnected fragments, each in its own frame.', 'One shared world frame.', agree.length ? `wherever the tower pins another fragment, its tower points coincide within ${fmt(Math.min(...agree), 1)}–${fmt(Math.max(...agree), 1)} m` : '', go('refuse', 'chapter 3')],
            ['Splats trained on its output float paint in mid-air, unchecked.', 'The lidar as referee and as teacher.', plain && taught ? `on lidar surfaces ${pct(plain.free_space.on_surfaces)} → ${pct(taught.free_space.on_surfaces)}; under the ground ${pct(plain.free_space.buried)} → ${pct(taught.free_space.buried)}` : '', go('referee', 'chapters 4–5')],
            ['One static scene: twenty years blended into one moment.', 'Years per point; dated buildings and aerial flights.', years.length ? `${years.length} dated photographs, ${Math.min(...years)}–${Math.max(...years)}; ${YEARS.length} aerial flights, ${YEARS[0]}–${YEARS[YEARS.length - 1]}` : '', go('above', 'chapters 6–9')],
            ['Registers a new photograph only into that same frame of its own.', 'A new photograph placed on the campus in seconds, with its own certificate, and painted back onto the lidar city.', r.located && r.located.leave_one_out ? `taken out and placed again: median ${fmt(r.located.leave_one_out.placed_position_error_m.median, 1)} m from the reconstruction's own pose` : '', go('photo', 'chapter 11')]];
          return `${rows.map(([lim, add, ev, link], i) => `<div class="limit"><div class="n">${i + 1}</div><div><p class="lim"><b>COLMAP:</b> ${lim}</p><p><b>GhostMap:</b> ${add}</p><p class="ev">${ev} ${link}</p></div></div>`).join('')}
            <p class="note">The hack in one line: COLMAP's frame is arbitrary, so search for the one similarity transform that puts the reconstruction inside the lidar campus you see here, and say when no such transform is determined.</p>
            <p><button type="button" id="start">Start: the fragment in its void →</button></p>`;
        },
        after() { for (const b of body.querySelectorAll('[data-go]')) b.onclick = () => show(b.dataset.go); document.getElementById('start').onclick = () => show('void'); },
        view() { setView({ points: false, photographers: false }); legend(CITY_LEGEND); setYear(2023); },
        sum: () => 'COLMAP\'s frame is arbitrary; GhostMap searches for the one similarity transform that puts it inside the lidar campus, and says when none is determined' },
    ] },

  { id: 'void', part: 'Where', title: '1 · Lost in space', purpose: 'What COLMAP hands over, why the photographs\' GPS cannot fix it here, and what the world already knows.',
    setup() {
      const c = mainCloud(), r = c.meta, st = scene.placement_study || {}, own = fragmentOf(r.tag), years = own.filter(p => p.year).map(p => p.year);
      const tagged = (st.fragments || []).find(f => f.run === r.tag.slice(0, 8) && String(f.fragment) === r.tag.split('-')[1]);
      const t = scene.sites.quad.terrain;
      return { c, r, own, years, tagged, gt: st.geotags || {}, artists: new Set(own.map(p => p.artist)).size, box: t.x1 - t.x0, buildings: scene.buildings.length };
    },
    steps: [
      { title: 'What COLMAP hands over',
        see: ctx => `the fragment in a void: ${fmt(ctx.own.length)} photographers (blue) and their ${fmt(ctx.r.points)} points in COLMAP's own coordinates, slowly turning. No scale, no north, no up.`,
        body: ctx => `<p>${fmt(ctx.own.length)} licensed internet photographs of McGraw Tower and Uris Library by ${fmt(ctx.artists)} photographers${ctx.years.length ? ` (the dated ones ${Math.min(...ctx.years)}–${Math.max(...ctx.years)})` : ''}, reconstructed with pycolmap, SuperPoint and LightGlue. Structure from motion recovers a scene only up to a similarity: <b>one scale, three rotations and three translations</b>, seven numbers, are free.</p>
          ${results(stat(fmt(ctx.own.length), 'photographs', 'Wikimedia Commons and Flickr (via Openverse), each with its licence'), stat(fmt(ctx.r.points), 'points', 'COLMAP\'s sparse reconstruction'), stat(fmt(ctx.artists), 'photographers', 'different people, different cameras, different years'), stat('7', 'free numbers', 'scale, heading, two tilts, three positions'))}`,
        view(ctx) { setView({ terrain: false, outlines: false, volumes: false, dark: true, allPhotographers: true }); float(); const ac = ctx.c.anchoredCentre || centroid3(ctx.c.anchored); flyTo([ac[0] - 150, ac[1] - 110, ac[2] + 140], 150, 0.25, -2.2); legend([['#2a6fdb', 'photographers, as COLMAP placed them'], ['#c8c2b4', 'reconstructed points (photo colours)']]); setYear(2023); },
        sum: ctx => `${fmt(ctx.own.length)} photographs, ${fmt(ctx.r.points)} points, seven free numbers` },
      { title: 'Why GPS cannot fix it here',
        see: 'the same fragment, still turning in its void.',
        body: ctx => { const g = ctx.tagged ? ctx.tagged.geotags : null;
          return `<p>COLMAP's own fix, <code>model_aligner</code>, needs the cameras' positions, usually from GPS tags. Here they are missing where they matter.</p>
          ${results(stat(`${fmt(ctx.gt.with_gps)} of ${fmt(ctx.gt.photographs)}`, 'Commons photographs with any GPS tag', 'across the whole campus collection'),
                    g ? stat(`${fmt(g.carried)} of ${fmt(ctx.own.length)}`, 'tags in this fragment', (g.wrong_off_m || []).length ? `and ${g.wrong_off_m.length === 1 ? 'it is' : 'they are'} ${g.wrong_off_m.map(dist).join(', ')} off` : '') : '',
                    g && g.without_metadata ? stat(fmt(g.without_metadata), 'with no metadata at all', 'Flickr web copies: no camera, no date, no place', true) : '')}
          <p class="note">A similarity needs at least three good tags; the fit cannot even start. Where tags exist elsewhere on the campus, some are kilometres off (chapter 3).</p>`; },
        sum: ctx => { const g = ctx.tagged ? ctx.tagged.geotags : null; return g ? `${fmt(g.carried)} GPS tag in ${fmt(ctx.own.length)} photographs${(g.wrong_off_m || []).length ? ', ' + g.wrong_off_m.map(dist).join(', ') + ' off' : ''}` : 'no usable GPS'; } },
      { title: 'But the world already has a 3D model',
        see: ctx => `the campus as the lidar measured it, ${fmt(ctx.buildings)} buildings in a ${fmt(ctx.box)} m box, with the fragment still floating above it in its own frame.`,
        body: () => `<p>Public USGS airborne lidar covers most of the United States, in metres; OpenStreetMap maps every building's footprint. Between them they know where the walls, the roofs, the ground and the tower top are. The question becomes: <b>which similarity transform puts COLMAP's fragment into this model?</b></p>
          <p><button type="button" id="go-snap">Place it in the world →</button></p>`,
        after() { document.getElementById('go-snap').onclick = () => show('snap'); },
        view(ctx) { setView({ allPhotographers: true }); float(); const ac = ctx.c.anchoredCentre || centroid3(ctx.c.anchored); flyTo([ac[0] - 60, ac[1] - 40, ac[2] + 60], 420, 0.45, -2.2, 1.6); legend([['#2a6fdb', 'photographers, as COLMAP placed them'], ...CITY_LEGEND]); setYear(2023); },
        sum: () => 'public lidar and OpenStreetMap footprints: walls, roofs, ground, tower top' },
    ] },

  { id: 'snap', part: 'Where', title: '2 · Snap to the world', purpose: 'Six cues from public data and physics, a search over every heading and scale, and a certificate that says which cue fixed what.',
    setup() {
      const c = mainCloud(), r = c.meta, P = r.placement || {}, cert = P.certificate, fs = P.sparse_points_free_space || {};
      const tower = building('McGraw Tower'), tc = centroid(tower.ring), az = photographersAzimuth(tower);
      const other = Math.max(...Object.entries(cert.cue_ablation).filter(([k]) => k !== 'landmark').map(([, v]) => v.position_shift_m));
      return { c, r, cert, fs, tower, tc, az, own: fragmentOf(r.tag), runnerUp: Math.max(...Object.values(cert.yaw_contrast).filter(v => v !== null)), other };
    },
    steps: [
      { title: 'Six cues, from public data and physics',
        see: ctx => `the fragment floating above the campus in COLMAP's own frame: ${fmt(ctx.own.length)} photographers (blue) and ${fmt(ctx.r.points)} points at an arbitrary size and heading. The lidar city below is what it has to agree with.`,
        body: () => `<p>Any candidate placement (a scale, a heading, two tilts, a position) gets a score from six cues. None needs a GPS tag or a hand-picked point:</p>${cueCards(null)}`,
        view(ctx) { setView({ allPhotographers: true }); float(); const ac = ctx.c.anchoredCentre || centroid3(ctx.c.anchored); flyTo([ac[0] - 60, ac[1] - 40, ac[2] + 60], 420, 0.45, -2.2, 1.0); legend([['#2a6fdb', 'photographers, as COLMAP placed them'], ['#303030', 'OpenStreetMap footprints']]); setYear(2023); },
        sum: () => 'walls, roof edges, camera height, tower top, free space, cameras outside' },
      { title: 'The search',
        see: 'the fragment turning, shrinking and sliding into the lidar campus: the placement that scores best over every heading and a band of scales, its position settled by descent.',
        body: () => `<p>Every heading is tried at every scale of the band; at each, the position settles by descent and the vertical is levelled by the photographers' heights. <b>Every placement keeps its score</b>, not only the winner: the certificate reads those scores afterwards.</p>
          <p><button type="button" id="replay">↺ replay the snap</button></p>`,
        after(ctx) { document.getElementById('replay').onclick = () => ctx.go(); },
        view(ctx) {
          ctx.go = () => { float(); placement.t0 = performance.now(); snapIntoPlace(); placement.done = () => flyTo([ctx.tc[0], ctx.tc[1], ctx.tower.ground + 20], 240, 0.42, ctx.az, 1.6); };
          setView({ allPhotographers: true }); const ac = ctx.c.anchoredCentre || centroid3(ctx.c.anchored); flyTo([ac[0] - 60, ac[1] - 40, ac[2] + 60], 420, 0.45, -2.2, 1.0); ctx.go();
          legend([['#2a6fdb', 'photographers, placed'], ['#303030', 'OpenStreetMap footprints'], ['#b5532c', 'buildings that changed since 2002']]); setYear(2023);
        },
        sum: ctx => `placed: ${fmt(ctx.cert.scale_m_per_unit, 2)} m per model unit` },
      { title: 'The certificate',
        see: 'the fragment placed: its points on the lidar walls and roofs, the photographers on Ho Plaza and Libe Slope at eye height, McGraw Tower in the middle.',
        body: ctx => { const { cert, fs, runnerUp } = ctx;
          return `<p>${verdictBadge(cert.verdict, cert.failure_mode)} scale fixed by ${cert.scale_fixed_by.join(', ')}.</p>
          ${results(stat(fmt(cert.scale_m_per_unit, 2) + ' m', 'per model unit', `the scale, known to ±${fmt(100 * cert.scale_uncertainty_relative, 1)} %: three cues fix it independently and agree`),
                    stat(pct(runnerUp), 'runner-up heading', 'the best other heading scores this much of the winner: the heading is settled, not a near tie'),
                    cert.levelling_correction_deg ? stat(fmt(cert.levelling_correction_deg, 1) + '°', 'levelled', `the photographers' heights over the lidar ground showed a ${fmt(cert.levelling_tilt_deg, 1)}° tilt in the facades' vertical; turning by this much scored best on all cues together`) : '',
                    stat(pct(fs.surface), 'points on lidar surfaces', 'of COLMAP\'s points within 2.5 m of a lidar return; ' + pct(cert.points_within_1m_of_walls) + ' within 1 m of a footprint wall'),
                    stat(`${fmt(cert.cameras_in_height_band)} of ${fmt(cert.cameras)}`, 'photographers at eye height', 'the rest stand on stairs, slopes and the tower itself: the cue has a low weight for that reason', true))}`; },
        view(ctx) { settled(); setView({ allPhotographers: true }); flyTo([ctx.tc[0], ctx.tc[1], ctx.tower.ground + 20], 240, 0.42, ctx.az, 1.6); legend([['#2a6fdb', 'photographers, placed'], ['#303030', 'OpenStreetMap footprints']]); setYear(2023); },
        sum: ctx => `${verdictBadge(ctx.cert.verdict, ctx.cert.failure_mode)} scale ±${fmt(100 * ctx.cert.scale_uncertainty_relative, 1)} %, runner-up heading ${pct(ctx.runnerUp)}` },
      { title: 'Which cue fixed what',
        see: 'the placed fragment, from the photographers\' side.',
        body: ctx => { const { cert } = ctx;
          return `<p>Each cue's score at the optimum, and how far the optimum moves when that cue is left out of the fit:</p>
          ${cueCards(cert.cue_scores)}
          <table><tr><th>without</th><th class="num">the optimum moves</th><th class="num">the scale changes</th></tr>${Object.entries(cert.cue_ablation).map(([k, v]) => `<tr><td>${CUES.find(c => c[0] === k)?.[1] || k.replace(/_/g, ' ')}</td><td class="num">${fmt(v.position_shift_m, 1)} m, ${fmt(Math.abs(v.yaw_shift_deg), 1)}°</td><td class="num">${pct(Math.abs(v.scale_ratio - 1), 1)}</td></tr>`).join('')}</table>
          <p class="note">The tower top matters most: without it the optimum moves ${fmt(cert.cue_ablation.landmark.position_shift_m, 1)} m; without any other single cue, under ${fmt(Math.ceil(ctx.other * 10) / 10, 1)} m. The walls score low here because airborne lidar and footprints see walls thinly; they still fix the scale on their own (parallel walls in view).</p>
          ${profileChart(cert)}`; },
        view(ctx) { settled(); setView({ allPhotographers: true }); flyTo([ctx.tc[0], ctx.tc[1], ctx.tower.ground + 20], 240, 0.42, ctx.az, 1.6); legend([['#2a6fdb', 'photographers, placed'], ['#303030', 'OpenStreetMap footprints']]); setYear(2023); },
        sum: ctx => `the tower top fixes most: without it the optimum moves ${fmt(ctx.cert.cue_ablation.landmark.position_shift_m, 1)} m` },
    ] },

  { id: 'refuse', part: 'Where', title: "3 · Knowing when it can't", purpose: 'The whole campus reconstructed at once: every fragment the evidence cannot pin down is refused, with the reason, and a synthetic hall shows why.',
    setup() {
      const st = scene.placement_study || {}, tag = (mainCloud().meta.tag || '').slice(0, 8);
      const frs = (st.fragments || []).filter(f => f.run !== tag), refused = frs.filter(f => f.verdict !== 'usable');
      const checked = frs.filter(f => f.ours_vs_geotags_m).map(f => f.ours_vs_geotags_m.median);
      const agree = (st.agreement_with_validated_frame || []).filter(a => a.building === 'McGraw Tower').map(a => a.median_distance_m);
      const lib = (st.agreement_with_validated_frame || []).filter(a => a.building === 'Uris Library');
      const synth = (st.identifiability || []).filter(x => x.cues === 'all cues' && x.camera_height_noise_m === 0 && x.seed === 0);
      return { st, frs, refused, checked, agree, lib, synth, run: st.campus_run || {} };
    },
    steps: [
      { title: 'The whole campus at once',
        see: 'the campus from above, with the placed tower-and-library fragment in the middle. The other fragments are not drawn: none could be placed.',
        body: ctx => `<p>Every licensed photograph of the campus collection, reconstructed in one run on the GPU: many fragments, each in its own frame, named by the building most of its photographs show.</p>
          ${results(stat(fmt(ctx.run.photographs), 'photographs', 'the whole campus collection'), stat(fmt(ctx.run.registered), 'registered', 'placed by COLMAP in some fragment'), stat(fmt(ctx.run.fragments), 'fragments', 'disconnected pieces'), stat(fmt(ctx.frs.length), 'with eight or more cameras', 'the ones the placement was tried on'))}`,
        view() { setView({ allPhotographers: true }); legend([['#303030', 'OpenStreetMap footprints']]); campusView(); setYear(2023); },
        sum: ctx => `${fmt(ctx.run.photographs)} photographs → ${fmt(ctx.run.fragments)} fragments, ${fmt(ctx.frs.length)} with eight or more cameras` },
      { title: 'Every one refused, with its reason',
        see: 'the same view.',
        body: ctx => `<table><tr><th>fragment</th><th class="num">cameras</th><th>certificate</th><th class="num">GPS tags</th><th class="num">off by</th></tr>
          ${ctx.frs.map(f => `<tr><td>${f.building.replace('Bill and Melinda ', '')}</td><td class="num">${f.cameras}</td><td>${verdictBadge(f.verdict, f.failure_mode)}</td><td class="num">${f.geotags.plausible}/${f.geotags.carried}</td><td class="num">${f.ours_vs_geotags_m ? fmt(f.ours_vs_geotags_m.median) + ' m' : '—'}</td></tr>`).join('')}</table>
          <p class="note">"GPS tags": plausible tags of all carried. "Off by": how far the fit's cameras land from those tags. ${ctx.checked.length ? `Every placement the tags could check was ${fmt(Math.min(...ctx.checked))}–${fmt(Math.max(...ctx.checked))} m off, and every one of them was refused: the certificate caught each wrong placement without seeing a single tag.` : ''}</p>`,
        view() { setView({ allPhotographers: true }); legend([['#303030', 'OpenStreetMap footprints']]); campusView(); setYear(2023); },
        sum: ctx => `${fmt(ctx.refused.length)} of ${fmt(ctx.frs.length)} refused${ctx.checked.length ? `; the ${ctx.checked.length} that GPS could check were ${fmt(Math.min(...ctx.checked))}–${fmt(Math.max(...ctx.checked))} m off` : ''}` },
      { title: 'The same tower through two fragments',
        see: 'the placed tower-and-library fragment; the campus fragments that also see McGraw Tower put its points within about a metre of these.',
        body: ctx => `<p>A free check: where two fragments contain the same building, their placed copies of it should coincide.</p>
          ${results(ctx.agree.length ? stat(`${fmt(Math.min(...ctx.agree), 1)}–${fmt(Math.max(...ctx.agree), 1)} m`, 'McGraw Tower, fragment to fragment', 'median distance between the tower points of a campus fragment and of the validated fragment, wherever the tower pins the campus fragment') : '',
                    ctx.lib.length ? stat(fmt(ctx.lib[0].median_distance_m) + ' m', 'Uris Library, the largest campus fragment', 'its heading around the tower is wrong, and that fragment was refused: the disagreement is on the refused side') : '')}`,
        view() { settled(); setView({ allPhotographers: true }); legend([['#2a6fdb', 'photographers, placed'], ['#303030', 'OpenStreetMap footprints']]); towerView(260, 0.5); setYear(2023); },
        sum: ctx => ctx.agree.length ? `tower points agree within ${fmt(Math.min(...ctx.agree), 1)}–${fmt(Math.max(...ctx.agree), 1)} m${ctx.lib.length ? `; the library ${fmt(ctx.lib[0].median_distance_m)} m off where the heading was refused` : ''}` : '' },
      { title: 'Why: a synthetic hall with a known answer',
        see: 'the campus; the hall is synthetic, not drawn.',
        body: ctx => `<p>A hall whose true placement is known, seen through one facade, two parallel facades, a corner or three facades, with and without a ${fmt(Math.max(...ctx.synth.map(x => x.roof_edge_error_m)))} m error in the lidar roof edge:</p>
          <table><tr><th>facades in view</th><th class="num">roof-edge error</th><th class="num">scale</th><th class="num">heading</th><th>certificate</th></tr>
          ${ctx.synth.map(x => `<tr><td>${x.facades}</td><td class="num">${fmt(x.roof_edge_error_m)} m</td><td class="num">×${fmt(x.scale_ratio, 3)}</td><td class="num">${fmt(x.yaw_error_deg, 1)}°</td><td>${verdictBadge(x.verdict, x.failure_mode)}</td></tr>`).join('')}</table>
          <p class="note">One facade cannot fix its own scale; two parallel facades slide along each other; a wrong lidar roof edge is caught when the walls fix the scale independently ("cues disagree"), and otherwise shows up as the stated scale uncertainty.</p>`,
        view() { setView({ allPhotographers: true }); legend([['#303030', 'OpenStreetMap footprints']]); campusView(); setYear(2023); },
        sum: () => 'one facade: scale undetermined; two parallel: position undetermined; a corner or three facades: usable' },
    ] },

  { id: 'referee', part: 'How it looked', title: '4 · The lidar as referee', purpose: 'A Gaussian splat trained from the same photographs, in the lidar\'s metres, so every Gaussian can be checked against what the lidar measured.',
    setup() {
      const r = mainCloud().meta, plain = (r.splats || []).find(s => !s.lidar_taught) || (r.splats || [])[0];
      if (!plain) return { r };
      const pb = Object.entries(plain.per_building).sort((a, b) => b[1].gaussians - a[1].gaussians).slice(0, 4);
      return { r, plain, fs: r.placement ? r.placement.sparse_points_free_space : null, pb, poses: (plain.views && plain.views.poses) || [], tower: building('McGraw Tower') };
    },
    steps: [
      { title: 'The splat, from where a photographer stood',
        see: ctx => ctx.plain ? 'left, the photograph; right, the Gaussian splat rendered from the same pose. Drag the divider across.' : 'the campus; no splat has been trained for this fragment yet.',
        body: ctx => { const { plain, poses } = ctx; if (!plain) return '<p>No Gaussian splat has been trained for this fragment yet.</p>';
          return `<p>A Gaussian splat trained from ${fmt(plain.images ? plain.images.train : null)} of the photographs (${fmt(plain.images ? plain.images.test : null)} held out), ${fmt(plain.steps)} steps, directly in the lidar frame. Near the photographers' viewpoints it reproduces the photographs; away from them, a splat of internet photographs is only half constrained.</p>
          <div class="cues" id="refmode">
            ${poses.map((p, i) => `<label><input type="radio" name="refmode" value="pose-${i}" ${i === 0 ? 'checked' : ''}>${poseLabel(p, i)}</label>`).join('')}
            <label><input type="radio" name="refmode" value="campus" ${poses.length ? '' : 'checked'}>in the lidar campus</label>
            <label><input type="radio" name="refmode" value="verdict">the lidar's verdict on every Gaussian</label></div>
          <p class="note" id="refhint"></p>
          ${results(stat(plain.psnr && plain.psnr.test_mean ? fmt(plain.psnr.test_mean, 1) + ' dB' : '—', 'held-out PSNR, mean', `over the ${fmt(plain.images ? plain.images.test : null)} held-out photographs; the best-covered view reaches ${fmt(plain.psnr_best_covered_view, 1)} dB`), stat(fmt(plain.seconds / 60) + ' min', 'training', 'on a laptop GPU'))}`; },
        after(ctx) { if (!ctx.plain) return;
          const { plain, poses, tower } = ctx, c = centroid(tower.ring);
          const apply = () => {
            const mode = document.querySelector('input[name=refmode]:checked').value, hint = document.getElementById('refhint');
            if (mode.startsWith('pose-')) {
              const p = poses[+mode.slice(5)], ph = photographerOf(p);
              setView({ points: false, photographers: false, splat: null }); legend([]);
              showWipe({ url: p.photo_url, label: 'the photograph' }, { url: p.render_url, label: 'the splat, from the same pose' }, p.size);
              if (ph) flyToPhotographer(ph, 0.01);
              hint.textContent = (p.held_out ? 'A photograph the splat never saw. ' : 'A training photograph. ') + 'gsplat renders from the photographer\'s pose, colour fitted to the photograph as in the held-out PSNR.';
            } else {
              hideOverlay(); const verdict = mode === 'verdict';
              setView({ points: false, photographers: false, splat: verdict ? null : plain.name, splatLayer: verdict ? plain.name : null });
              legend(verdict ? LEGEND_LIDAR : [['#b5532c', 'buildings that changed since 2002']]); setYear(year);
              if (!verdict) showSplat(plain.name, 'referee');
              flyTo([c[0], c[1], tower.ground + 18], 190, 0.35, photographersAzimuth(tower));
              hint.textContent = verdict ? 'Every opaque Gaussian inside the lidar\'s measured volume, coloured by what the lidar says about where it sits.' : 'The live splat inside the lidar campus: what you see from up here is the reason it needs a referee.';
            }
          };
          for (const x of document.querySelectorAll('input[name=refmode]')) x.onchange = apply;
          ctx.apply = apply;
        },
        view(ctx) { if (ctx.apply) ctx.apply(); else { setView(); legend([]); } setYear(2023); },
        sum: ctx => ctx.plain ? `held-out PSNR ${fmt(ctx.plain.psnr.test_mean, 1)} dB mean, ${fmt(ctx.plain.psnr_best_covered_view, 1)} dB on the best-covered view` : 'no splat yet' },
      { title: 'Every Gaussian, judged by the lidar',
        see: 'every opaque Gaussian inside the lidar\'s measured volume, coloured by the lidar\'s verdict: green on a measured surface, red in air the lidar saw empty, purple under the bare ground.',
        body: ctx => { const s = ctx.plain; if (!s) return '';
          return `<p>Because the splat lives in the lidar frame, each Gaussian's distance to the nearest lidar return is a measurement, not an impression.</p>
          ${results(stat(pct(s.free_space.on_surfaces), 'on lidar surfaces', 'within 2.5 m of a lidar return: the paint that is where the world is'),
                    stat(pct(s.free_space.in_free_air), 'in air the lidar saw empty', 'paint floating in mid-air to explain the photographs'),
                    stat(pct(s.free_space.buried), 'under the bare ground', 'paint below the terrain, invisible from the photographs'),
                    stat(fmt(s.overall.median_m, 2) + ' m', 'median distance to the lidar', `over the ${fmt(s.splat_gaussians)} Gaussians inside the measured volume`))}
          ${ctx.fs ? `<p class="note">For scale: COLMAP's own sparse points of this fragment sit on lidar surfaces ${pct(ctx.fs.surface)} of the time (${pct(ctx.fs.air)} in free air).</p>` : ''}`; },
        view(ctx) { if (!ctx.plain) return; hideOverlay(); const t = ctx.tower, c = centroid(t.ring); setView({ points: false, photographers: false, splatLayer: ctx.plain.name }); legend(LEGEND_LIDAR); flyTo([c[0], c[1], t.ground + 18], 190, 0.35, photographersAzimuth(t)); setYear(2023); },
        sum: ctx => ctx.plain ? `${pct(ctx.plain.free_space.on_surfaces)} on lidar surfaces, ${pct(ctx.plain.free_space.in_free_air)} in empty air, ${pct(ctx.plain.free_space.buried)} under the ground` : '' },
      { title: 'Building by building',
        see: 'the same verdict layer.',
        body: ctx => { if (!ctx.plain) return '';
          return `<table><tr><th>building</th><th class="num">Gaussians</th><th class="num">median to lidar</th><th class="num">in free air</th><th class="num">covers the lidar building</th></tr>
          ${ctx.pb.map(([n, v]) => `<tr><td>${n}</td><td class="num">${fmt(v.gaussians)}</td><td class="num">${fmt(v.median_m, 2)} m</td><td class="num">${pct(v.in_free_air)}</td><td class="num">${pct(v.coverage)}</td></tr>`).join('')}</table>
          <p class="note">Airborne lidar sees roofs and ground densely and walls thinly, so a Gaussian on a wall is judged against the nearest roof edge or ground return: the distance is a conservative score for walls.</p>`; },
        view(ctx) { if (!ctx.plain) return; hideOverlay(); const t = ctx.tower, c = centroid(t.ring); setView({ points: false, photographers: false, splatLayer: ctx.plain.name }); legend(LEGEND_LIDAR); flyTo([c[0], c[1], t.ground + 18], 190, 0.35, photographersAzimuth(t)); setYear(2023); },
        sum: ctx => ctx.pb && ctx.pb.length ? `${ctx.pb[0][0]}: ${fmt(ctx.pb[0][1].median_m, 2)} m median to the lidar` : '' },
    ] },

  { id: 'teacher', part: 'How it looked', title: '5 · The lidar as teacher', purpose: 'The same photographs and the same steps, with one extra rule from the lidar; what the rule changes, in a fly-through and in numbers.',
    setup() {
      const r = mainCloud().meta, S = r.splats || [], plain = S.find(s => !s.lidar_taught), taught = S.find(s => s.lidar_taught);
      if (!plain || !taught) return { r };
      const poses = (plain.views && taught.views) ? plain.views.poses.filter(p => taught.views.poses.some(q => q.photo === p.photo)) : [];
      return { r, plain, taught, poses, fly: !!(plain.views && taught.views && plain.views.fly && taught.views.fly), tower: building('McGraw Tower') };
    },
    steps: [
      { title: 'One extra rule',
        see: ctx => ctx.fly ? 'the same camera path through both splats, plain on the left, lidar-taught on the right. It pauses where a photographer stood and shows the photograph taken there.' : 'the campus; the lidar-taught splat has not been trained yet.',
        body: ctx => { const { plain, taught, poses, fly } = ctx; if (!taught) return '<p>The lidar-taught splat has not been trained yet.</p>';
          return `<p>Same photographs, same steps, one extra rule from the lidar: <b>the air above the measured surface is empty</b>, and nothing lies under the bare ground. Gaussians that break it are made transparent, and the ones far out in the air are removed.</p>
          <div class="cues" id="tchmode">
            ${fly ? `<label><input type="radio" name="tchmode" value="fly" checked>fly-through</label>` : ''}
            ${poses.map((p, i) => `<label><input type="radio" name="tchmode" value="pose-${i}" ${!fly && i === 0 ? 'checked' : ''}>${poseLabel(p, i)}</label>`).join('')}
            <label><input type="radio" name="tchmode" value="campus" ${!fly && !poses.length ? 'checked' : ''}>in the lidar campus</label></div>
          <div class="cues" id="tchcampus" hidden><label><input type="radio" name="tch" value="${taught.name}" checked>lidar-taught</label><label><input type="radio" name="tch" value="${plain.name}">plain</label><label><input type="checkbox" id="tch-layer">show the lidar's verdict</label></div>
          <p class="note" id="tchhint"></p>
          ${taught.prior ? `<p class="note">Removed during training: ${fmt(taught.prior.pruned)} Gaussians more than ${fmt(taught.prior.prune_above_m)} m into measured free air.</p>` : ''}`; },
        after(ctx) { if (!ctx.taught) return;
          const { plain, taught, poses, tower } = ctx, c = centroid(tower.ring);
          const apply = () => {
            const mode = document.querySelector('input[name=tchmode]:checked').value, hint = document.getElementById('tchhint');
            document.getElementById('tchcampus').hidden = mode !== 'campus';
            if (mode === 'fly') {
              setView({ points: false, photographers: false }); legend([]);
              showFly({ views: plain.views, label: 'plain splat', splat: plain }, { views: taught.views, label: 'lidar-taught splat', splat: taught });
              hint.textContent = 'It pauses at each photographer\'s spot and shows the photograph taken there; tick the box to paint every Gaussian by what the lidar says about it.';
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
          ctx.apply = apply;
        },
        view(ctx) { if (ctx.apply) ctx.apply(); else { setView(); legend([]); } setYear(2023); },
        sum: () => 'the air above the measured surface is empty; nothing under the bare ground' },
      { title: 'What the rule changed, in numbers',
        see: ctx => ctx.fly && !overlay.hidden ? 'the fly-through, still running. Tick the box under it to paint every Gaussian by the lidar\'s verdict: red is paint in air the lidar measured empty.' : 'the same camera path through both splats.',
        body: ctx => { const { plain, taught } = ctx; if (!taught) return '';
          const row = (label, f, cls) => `<tr><td>${label}</td><td class="num">${f(plain)}</td><td class="num ${cls || ''}">${f(taught)}</td></tr>`;
          return `<table><tr><th></th><th class="num">plain</th><th class="num">lidar-taught</th></tr>
            ${row('on lidar surfaces', s => pct(s.free_space.on_surfaces, 1), taught.free_space.on_surfaces > plain.free_space.on_surfaces ? 'ok' : '')}
            ${row('under the bare ground', s => pct(s.free_space.buried, 1), taught.free_space.buried < plain.free_space.buried ? 'ok' : '')}
            ${row('in air the lidar saw empty', s => pct(s.free_space.in_free_air, 1), taught.free_space.in_free_air < plain.free_space.in_free_air ? 'ok' : 'bad')}
            ${row('median distance to the lidar', s => fmt(s.overall.median_m, 2) + ' m', taught.overall.median_m < plain.overall.median_m ? 'ok' : '')}
            ${row('Gaussians in the measured volume', s => fmt(s.gaussians.in_measured_volume))}
            ${row('held-out PSNR (mean of ' + fmt(plain.images ? plain.images.test : null) + ')', s => s.psnr && s.psnr.test_mean ? fmt(s.psnr.test_mean, 1) + ' dB' : '—')}
            ${row('training time', s => s.seconds ? fmt(s.seconds / 60) + ' min' : '—')}</table>
          <p class="note">Read it as: the paint moved from the empty air and from under the ground onto the measured surfaces, and the photographs are reproduced as well as before. The far field (sky and the background beyond the lidar crop) is not judged and not shown.</p>`; },
        view(ctx) { if (ctx.taught && ctx.fly && overlay.hidden) { setView({ points: false, photographers: false }); legend([]); showFly({ views: ctx.plain.views, label: 'plain splat', splat: ctx.plain }, { views: ctx.taught.views, label: 'lidar-taught splat', splat: ctx.taught }); } },
        sum: ctx => ctx.taught ? `on lidar surfaces ${pct(ctx.plain.free_space.on_surfaces)} → ${pct(ctx.taught.free_space.on_surfaces)}; in empty air ${pct(ctx.plain.free_space.in_free_air)} → ${pct(ctx.taught.free_space.in_free_air)}; PSNR ${fmt(ctx.plain.psnr.test_mean, 1)} → ${fmt(ctx.taught.psnr.test_mean, 1)} dB` : '' },
      { title: 'How far can the teacher go?',
        see: 'the same fly-through.',
        body: ctx => { const { r, taught } = ctx; if (!taught) return '';
          return (r.splat_ablations || []).map(a => {
            const floor = r.placement ? r.placement.sparse_points_free_space.surface : null, drop = taught.psnr_best_covered_view - a.psnr_best_covered_view;
            return `<p class="finding">A ${fmt(a.prior.weight / taught.prior.weight)}-times stronger rule puts ${pct(a.free_space.on_surfaces)} of the Gaussians on lidar surfaces${floor === null ? '' : a.free_space.on_surfaces > floor ? ` — more than COLMAP's own points (${pct(floor)})` : ` (COLMAP's own points: ${pct(floor)})`}, and the best-covered held-out view goes from ${fmt(taught.psnr_best_covered_view, 1)} to ${fmt(a.psnr_best_covered_view, 1)} dB${drop > 1 ? ': at that strength it carves real structure that the lidar\'s 2.5 m tolerance and the placement\'s error put outside. The page keeps the gentler rule.' : '.'}</p>`; }).join('') || '<p class="note">No stronger rule has been tried yet.</p>'; },
        view(ctx) { if (ctx.taught && ctx.fly && overlay.hidden) { setView({ points: false, photographers: false }); legend([]); showFly({ views: ctx.plain.views, label: 'plain splat', splat: ctx.plain }, { views: ctx.taught.views, label: 'lidar-taught splat', splat: ctx.taught }); } },
        sum: ctx => { const a = (ctx.r.splat_ablations || [])[0]; return a && ctx.taught ? `a ${fmt(a.prior.weight / ctx.taught.prior.weight)}-times stronger rule: ${pct(a.free_space.on_surfaces)} on surfaces, but ${fmt(ctx.taught.psnr_best_covered_view - a.psnr_best_covered_view, 1)} dB lost on the best-covered view` : ''; } },
    ] },

  { id: 'above', part: 'When', title: '6 · From above', purpose: 'Public aerial flights, one every few years, draped on the lidar terrain; the buildings that changed, shown only in the years they stood.',
    setup: () => ({}),
    steps: [
      { title: `${YEARS.length} flights, ${YEARS[0]}–${YEARS[YEARS.length - 1]}`,
        see: `the Quad from above in the ${YEARS[0]} flight: New York State orthoimagery draped on the lidar terrain. Drag the year, or play it.`,
        body: () => `<p>Between flights the latest earlier image is shown. The same frame holds the lidar, the footprints, the placed fragment and every flight, so the years line up to the metre.</p>
          <p><button type="button" id="play">▶ play the years</button></p><p class="note">Flight years: ${YEARS.join(', ')}.</p>`,
        after() { document.getElementById('play').onclick = play; },
        view() { setView(); legend(CHANGED_LEGEND); const t = building('McGraw Tower'), c = centroid(t.ring); flyTo([c[0] + 60, c[1] + 40, t.ground], 900, 0.95, -1.9); setYear(YEARS[0]); },
        sum: () => `${YEARS.length} flights, ${YEARS.join(', ')}` },
      { title: `Three buildings that did not exist in ${YEARS[0]}`,
        see: `${YEARS[YEARS.length - 1]}: the three outlined buildings standing. Each is drawn only in the years the documented dates say it stood.`,
        body: () => `<ul>${changed.map(b => `<li><b>${b.name.replace('Bill and Melinda ', '')}</b> — <span class="state" data-state-of="${b.name}"></span></li>`).join('')}</ul>
          <p class="note">Building volumes are the 2020 lidar shape, shown only in years the documented dates say the building stood. The next chapters take each in turn.</p>`,
        view() { setView(); legend(CHANGED_LEGEND); setYear(YEARS[YEARS.length - 1]); },
        sum: () => changed.map(b => b.name.replace('Bill and Melinda ', '')).join(', ') },
    ] },

  { id: 'gates', part: 'When', title: '7 · Gates Hall', purpose: 'A parking lot until 2012, a Thom Mayne building from 2014: documented, from the air, from the ground.',
    ...buildingSteps('Bill and Melinda Gates Hall', 'Slide from 2007 to 2015 and watch the air photographs change; the volume is the lidar shape of the finished building.', [2007, 2013, 2016]) },
  { id: 'klarman', part: 'When', title: '8 · Klarman Hall', purpose: 'The courtyard behind Goldwin Smith Hall until the 2012 flight, a glass atrium from 2016: documented, from the air, from the ground.',
    ...buildingSteps('Klarman Hall', 'The courtyard behind Goldwin Smith Hall until the 2012 flight, under construction in the 2015 flight, a glass atrium from 2016.', [2012, 2015, 2018]) },

  { id: 'tower', part: 'When', title: '9 · Twenty years of one tower', purpose: 'Every reconstructed point carries the years in which photographs observed it; the photographers carry their dates.',
    setup() {
      const r = mainCloud().meta, own = fragmentOf(r.tag), dated = own.filter(p => p.year), counts = {};
      for (const p of dated) counts[p.year] = (counts[p.year] || 0) + 1;
      return { r, own, dated, counts, maxc: Math.max(1, ...Object.values(counts)), tower: building('McGraw Tower') };
    },
    steps: [
      { title: 'Every point knows its years',
        see: 'the tower fragment: points seen by the selected year in colour, the rest grey. The bars under the text count the dated photographs per year.',
        body: ctx => `<p>${fmt(ctx.own.length)} photographs of the tower and Uris Library, ${fmt(ctx.r.dated_photographs)} of them dated, from ${Math.min(...ctx.dated.map(p => p.year))} to ${Math.max(...ctx.dated.map(p => p.year))}. Each reconstructed point carries the years in which photographs observed it; the slider shows the points seen by that year.</p>
          <div class="yearbar">${Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i).map(y => `<div data-year="${y}" style="height:${100 * (ctx.counts[y] || 0) / ctx.maxc}%" title="${y}: ${ctx.counts[y] || 0} dated photographs"></div>`).join('')}</div>
          <div class="yearlabels"><span>${MIN_YEAR}</span><span>dated photographs per year</span><span>${MAX_YEAR}</span></div>
          <div class="cues"><label><input type="radio" name="col" value="photo" ${colourMode === 'photo' ? 'checked' : ''}>photo colours</label><label><input type="radio" name="col" value="first" ${colourMode === 'first' ? 'checked' : ''}>colour by first year seen</label>${ctx.r.mesh ? `<label><input type="checkbox" id="surface" ${mainCloud().surface ? '' : 'disabled'}>dense surface (${fmt(ctx.r.mesh.faces)} faces)</label>` : ''}</div>`,
        after() {
          for (const x of document.querySelectorAll('input[name=col]')) x.onchange = () => { colourMode = x.value; setYear(year); };
          const sf = document.getElementById('surface'); if (sf) sf.onchange = () => { setView({ surface: sf.checked, points: !sf.checked }); setYear(year); };
        },
        view(ctx) { setView(); legend([['#2a6fdb', 'photographers before the selected year'], ['#d0453a', 'photographers in the selected year'], ['#9aa5b1', 'later photographers']]); const c = centroid(ctx.tower.ring); flyTo([c[0], c[1], ctx.tower.ground + 20], 220, 0.35, photographersAzimuth(ctx.tower)); setYear(year); },
        sum: ctx => `${fmt(ctx.r.dated_photographs)} dated photographs, ${Math.min(...ctx.dated.map(p => p.year))}–${Math.max(...ctx.dated.map(p => p.year))}` },
      { title: 'Click a photographer',
        see: 'the photographers as spheres: blue before the selected year, red in it, grey after. Click one to see the photograph and jump to its year.',
        body: () => `<p>Each sphere is where a photographer stood, as the placement puts them. The photograph, its date, its author and its licence come up below.</p><div id="pick"></div>`,
        view(ctx) { setView(); legend([['#2a6fdb', 'photographers before the selected year'], ['#d0453a', 'photographers in the selected year'], ['#9aa5b1', 'later photographers']]); const c = centroid(ctx.tower.ring); flyTo([c[0], c[1], ctx.tower.ground + 15], 200, 0.3, photographersAzimuth(ctx.tower)); setYear(year); },
        sum: () => 'each photograph, its date, author and licence' },
    ] },

  { id: 'limits', part: 'When', title: '10 · What the record cannot show', purpose: 'The limits, said out loud: of the placement, of the public record, and of the time machine.',
    setup() { const st = scene.placement_study || {}, tag = (mainCloud().meta.tag || '').slice(0, 8); return { frs: (st.fragments || []).filter(f => f.run !== tag) }; },
    steps: [
      { title: 'Of the placement',
        see: 'the campus.',
        body: ctx => `<ul>
          <li><b>Most fragments cannot be placed yet.</b> Of the campus-wide run's ${ctx.frs.length} larger fragments none is certified: a square tower cannot fix its own heading, one facade cannot fix its own scale, and close-ups of an entrance show no facade the map knows. The certificate says which, instead of placing them wrongly.</li>
          <li><b>Airborne lidar sees roofs and ground, not walls.</b> A Gaussian on a wall is judged against the nearest roof edge or ground return, so the distance score is conservative there; the free-air test tolerates 2.5 m horizontally for the same reason.</li></ul>`,
        view() { setView(); legend([]); campusView(); setYear(year); },
        sum: () => 'a square tower cannot fix its heading; one facade cannot fix its scale; lidar sees walls thinly' },
      { title: 'Of the public record',
        see: 'the campus.',
        body: () => `<ul>
          <li><b>No licensed ground-level photograph of any site before construction exists online.</b> The "before" is aerial only; no 3D of the old parking lots or the courtyard is shown.</li>
          <li><b>Boardman Hall (demolished 1959)</b> is beyond the time machine: its postcards can be matched to the surviving tower and library, but every recovered pose is a mirror image, because no licensed modern photograph looks at the tower from the Arts Quad side.</li></ul>`,
        view() { setView(); legend([]); setYear(year); },
        sum: () => 'no licensed ground photograph before construction; Boardman Hall only as mirror images' },
      { title: 'Of the time machine',
        see: 'the campus.',
        body: () => `<ul>
          <li><b>Building volumes are the 2020 lidar shape</b>, displayed only in years the documented dates say the building stood.</li>
          <li><b>The automatic aerial test is a diagnostic.</b> Its outline score rises at every site when the building appears, but stable buildings vary between flights by as much, so the dates on this page are the documented ones.</li></ul>`,
        view() { setView(); legend([]); setYear(year); },
        sum: () => 'volumes are the 2020 shape; dates are the documented ones' },
    ] },

  { id: 'photo', part: 'A new photograph', title: '11 · A photograph it has never seen', purpose: 'A photograph lands on the campus in seconds without GPS, with its own verdict, and is painted back onto the lidar city from where it was taken.',
    setup() {
      const r = mainCloud().meta, L = r.located || { photos: [] }, tower = building('McGraw Tower');
      return { r, L, loo: L.leave_one_out, street: L.street_test, tower, tc: centroid(tower.ring), az: photographersAzimuth(tower), n: fragmentOf(r.tag).length, selected: null };
    },
    steps: [
      { title: 'Pick a photograph, or drop your own',
        see: 'the lidar city around McGraw Tower, waiting for a photograph.',
        body: ctx => { const badge = v => v === 'placed' ? '<span class="state present">placed</span>' : v === 'refused' ? '<span class="state before">refused</span>' : '<span class="state works">direction placed, distance open</span>';
          return `<p>COLMAP can register a new photograph, but only into its own frame. Here it lands on the campus, in three moves: the most similar of the fragment's ${fmt(ctx.n)} photographs are found (NetVLAD), matched (SuperPoint, LightGlue), and RANSAC says where the photographer stood and which way they looked, <b>without GPS</b>. The verdict says how far to trust it.</p>
          <div class="tray">${ctx.L.photos.map((q, i) => `<button type="button" class="pick" data-i="${i}" aria-pressed="${ctx.selected === q}"><img src="${BASE + q.photo}" alt=""><span>${badge(q.verdict)}</span><span>${q.left_out ? 'taken out, placed again' : 'never in the reconstruction'}</span></button>`).join('')}</div>
          <label class="drop" id="drop">Drop a photograph of McGraw Tower or Uris Library here, or <input type="file" accept="image/*" id="drop-file"></label>
          <div id="located"></div>`; },
        after(ctx) {
          const panel = document.getElementById('located');
          const choose = q => { ctx.selected = q; show('photo', 1); };
          for (const b of body.querySelectorAll('.pick')) b.onclick = () => choose(ctx.L.photos[+b.dataset.i]);
          // Live placement through the demo server (web/demo_server.py); a page served by a plain file server says so.
          const place = async file => {
            panel.innerHTML = `<p class="note">placing ${file.name}…</p>`;
            try {
              const res = await fetch('api/locate', { method: 'POST', headers: { 'X-Filename': encodeURIComponent(file.name) }, body: file });
              if (!res.ok) { const j = await res.json().catch(() => null);
                throw new Error(res.status === 404 || res.status === 501 ? 'live placement needs the demo server: PYTHONPATH=pipeline python -m ghostmap.web.demo_server' : (j && j.error) || 'the server answered ' + res.status); }
              choose(await res.json());
            } catch (e) { panel.innerHTML = `<p class="note">${e.message}</p>`; }
          };
          const drop = document.getElementById('drop');
          drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); }; drop.ondragleave = () => drop.classList.remove('over');
          drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); if (e.dataTransfer.files[0]) place(e.dataTransfer.files[0]); };
          document.getElementById('drop-file').onchange = e => { if (e.target.files[0]) place(e.target.files[0]); };
        },
        view(ctx) { stopPaint(); projectionOn(0); showPlaced(null); standing = null; setView({ points: false, photographers: false }); legend([]); flyTo([ctx.tc[0], ctx.tc[1], ctx.tower.ground + 15], 230, 0.42, ctx.az); setYear(2023); },
        sum: ctx => ctx.selected ? ctx.selected.title.replace(/^File:/, '') : `${fmt(ctx.L.photos.length)} prepared photographs, or your own` },
      { title: 'Where the photographer stood',
        see: ctx => { const q = ctx.selected; if (!q) return 'the lidar city; pick a photograph first.';
          return !q.centre || q.verdict === 'refused' ? 'the lidar city; this photograph was refused, so nothing is drawn for it.' : q.verdict === 'placed' ? 'the photographer (red sphere) and the frame of the photograph, seen from the side; the tower in the direction they faced.' : 'the photographer\'s direction, seen from the side; the dashed line is where along the line of sight they may have stood.'; },
        body: ctx => { const q = ctx.selected; if (!q) return '<p class="note">Pick a photograph in step 1.</p>';
          const badge = v => v === 'placed' ? '<span class="state present">placed</span>' : v === 'refused' ? '<span class="state before">refused</span>' : '<span class="state works">direction placed, distance open</span>';
          const d = q.centre ? Math.hypot(q.centre[0] - ctx.tc[0], q.centre[1] - ctx.tc[1]) : null;
          return `<div class="placed-card"><img src="${BASE + q.photo}" alt=""><div>
            <p>${badge(q.verdict)} <span class="note">${q.seconds ? 'in ' + fmt(q.seconds, 1) + ' s' : ''}</span></p>
            <p class="note">${q.left_out ? `In the reconstruction, but taken out of it first and placed from scratch: it lands ${fmt(q.reconstruction_pose_error_m, 1)} m from where the reconstruction had it.` : q.live ? 'Dropped in just now.' : 'A photograph the reconstruction never used.'}</p>
            ${q.reasons.length ? `<p>${q.reasons.join('; ')}.</p>` : ''}${q.notes.length ? `<p class="note">${q.notes.join('; ')}.</p>` : ''}
            <p class="note">${q.title.replace(/^File:/, '')}${q.artist ? ' · ' + q.artist.replace(/<[^>]+>/g, '') : ''}${q.license ? ' · ' + q.license : ''}</p></div></div>
            ${q.centre && q.verdict === 'placed' ? results(stat(fmt(d) + ' m', 'from McGraw Tower', 'where the photographer stood'), stat(fmt(q.height_over_ground_m, 1) + ' m', 'above the lidar ground', 'eye height is the plausible band'), stat(compass(q.heading_deg), 'facing', 'the direction of the photograph'), stat(fmt(q.inliers), 'matched points that agree', 'correspondences to the fragment that fit one pose')) +
              `<p><button type="button" id="stand">stand where the photographer stood</button> <button type="button" id="side">see it from the side</button></p>
              <label class="note">city <input type="range" id="blend" min="0" max="100" value="100"> photograph</label>` : ''}
            ${q.centre && q.verdict !== 'placed' && q.verdict !== 'refused' ? '<p class="note">Not painted onto the city: from the wrong distance the photograph would land on the wrong walls. The dashed line on the map is where along its line of sight the photographer may have stood.</p>' : ''}`; },
        after(ctx) { const q = ctx.selected; if (!q || !q.centre || q.verdict !== 'placed') return;
          const placedLegend = () => legend([['#e02924', 'the photographer, as placed; dashed: where along the line of sight they may stand']]);
          const d = Math.hypot(q.centre[0] - ctx.tc[0], q.centre[1] - ctx.tc[1]);
          ctx.side = () => { const R = q.rotation, C = new THREE.Vector3(...q.centre), f = new THREE.Vector3(...R[2]); f.z = 0; f.normalize();
            const look = C.clone().addScaledVector(f, Math.min(80, d * 0.6)); look.z = ctx.tower.ground + 12;
            const from = C.clone().addScaledVector(f, -40).add(new THREE.Vector3(-f.y, f.x, 0).multiplyScalar(45)); from.z = C.z + 35;
            lookUp(false); flight = { from: { pos: camera.position.clone(), tgt: controls.target.clone() }, to: { pos: from, tgt: look }, t0: performance.now(), ms: 1400, fov: { from: camera.fov, to: 48 } }; };
          document.getElementById('stand').onclick = () => { placedGroup.visible = false; standing = q; flyToPhotographer(q);   // inside its own frustum the outline is in the way
            legend([['#3a3d40', 'dimmed: the lidar city; inside the white frame: the photograph, painted onto it from where it was taken']]); };
          document.getElementById('side').onclick = () => { placedGroup.visible = true; standing = null; placedLegend(); ctx.side(); };
          document.getElementById('blend').oninput = e => projectionOn(+e.target.value / 100);
        },
        view(ctx) { const q = ctx.selected; stopPaint(); standing = null; showPlaced(q && q.centre ? q : null); legend([['#e02924', 'the photographer, as placed; dashed: where along the line of sight they may stand']]);
          setView({ points: false, photographers: false }); setYear(2023);
          if (!q || !q.centre || q.verdict === 'refused') { projectionOn(0); flyTo([ctx.tc[0], ctx.tc[1], ctx.tower.ground + 15], 230, 0.42, ctx.az); return; }
          if (q.verdict !== 'placed') {   // the direction is placed, the distance is not: painted from the wrong distance it would land on the wrong walls
            projectionOn(0);
            const C = q.segment && q.segment.length === 2 ? q.segment.map(v => new THREE.Vector3(...v)) : [new THREE.Vector3(...q.centre)];
            const mid = C.reduce((a, v) => a.add(v), new THREE.Vector3()).multiplyScalar(1 / C.length);
            flyTo([(mid.x + ctx.tc[0]) / 2, (mid.y + ctx.tc[1]) / 2, ctx.tower.ground + 5], 420, 0.9, -2.0); return;
          }
          projectFrom(q, q.photo); projectionOn(1); ctx.side(); },
        sum: ctx => { const q = ctx.selected; if (!q) return ''; const badge = q.verdict === 'placed' ? 'placed' : q.verdict === 'refused' ? 'refused' : 'direction placed, distance open';
          return q.centre && q.verdict === 'placed' ? `${badge}${q.seconds ? ' in ' + fmt(q.seconds, 1) + ' s' : ''}: ${fmt(Math.hypot(q.centre[0] - ctx.tc[0], q.centre[1] - ctx.tc[1]))} m from the tower, facing ${compass(q.heading_deg)}, ${fmt(q.inliers)} points agree` : badge; } },
      { title: 'Painted back onto the city',
        see: ctx => ctx.selected && ctx.selected.centre && ctx.selected.verdict === 'placed' ? 'the lidar city from where the photographer stood, the photograph painted onto it inside the white frame. If the placement is right, its walls land on the lidar\'s walls.' : 'the lidar city; only a photograph placed with its distance can be painted back.',
        body: ctx => `<p>Every surface of the lidar city is projected into the photograph from the recovered pose and takes the photograph's colour where it is the nearest surface along that ray. ${ctx.selected && ctx.selected.verdict === 'placed' ? 'Drag the slider to blend between the bare city and the photograph.' : ''}</p>
          ${ctx.selected && ctx.selected.verdict === 'placed' ? `<label class="note">city <input type="range" id="blend" min="0" max="100" value="100"> photograph</label>` : ''}
          <p><button type="button" id="paint-all">▶ paint the ${fmt(ctx.n)} photographs back, one by one</button></p>
          <p class="note">The same projection, for every photograph of the fragment from its own placed pose: a lap around the tower through the photographers' eyes.</p>`,
        after(ctx) { document.getElementById('paint-all').onclick = () => { standing = null; paintAll(ctx.r, ctx.tower); }; const b = document.getElementById('blend'); if (b) b.oninput = e => projectionOn(+e.target.value / 100); },
        view(ctx) { const q = ctx.selected; stopPaint(); setView({ points: false, photographers: false }); setYear(2023);
          if (q && q.centre && q.verdict === 'placed') { projectFrom(q, q.photo); projectionOn(1); showPlaced(q); placedGroup.visible = false; standing = q; flyToPhotographer(q); legend([['#3a3d40', 'dimmed: the lidar city; inside the white frame: the photograph, painted onto it from where it was taken']]); }
          else { projectionOn(0); showPlaced(null); standing = null; legend([]); flyTo([ctx.tc[0], ctx.tc[1], ctx.tower.ground + 15], 230, 0.42, ctx.az); } },
        sum: () => 'its walls land on the lidar\'s walls' },
      { title: `Tested on all ${fmt(fragmentOf(mainCloud().meta.tag).length)}`,
        see: 'the lidar city around the tower.',
        body: ctx => { const { loo, street } = ctx; if (!loo) return '<p class="note">The leave-one-out test has not been run.</p>';
          return `<p>Each photograph was taken out of the reconstruction and placed again from scratch by the same rule, against the reconstruction's own pose for it (${fmt(loo.with_a_plausible_reference_pose)} of ${fmt(loo.photographs)} have a trustworthy one).</p>
          ${results(stat(fmt(loo.placed), 'placed', `median ${fmt(loo.placed_position_error_m.median, 1)} m from the reconstruction's own pose, nine in ten within ${fmt(loo.placed_position_error_m.p90, 1)} m, none beyond ${fmt(Math.ceil(loo.placed_position_error_m.max / 5) * 5)} m`),
                    stat(fmt(loo.placed_distance_uncertain), 'distance stated as open', `a long lens on a distant tower fixes the direction only; the true spot lies a median ${fmt(loo.distance_uncertain_truth_to_segment_m.median, 1)} m from the stated line`),
                    stat(fmt(loo.refused), 'refused', `each would have been about ${fmt(loo.refused_position_error_m_median)} m wrong: refusing was right`),
                    street ? stat(`${fmt(street.refused)} of ${fmt(street.frames)}`, 'street photographs refused', 'Mapillary frames from the Arts Quad side, which the internet\'s photographers never covered: the rule refuses what the fragment cannot know') : '')}`; },
        view(ctx) { stopPaint(); projectionOn(0); showPlaced(null); standing = null; setView({ points: false, photographers: false }); legend([]); flyTo([ctx.tc[0], ctx.tc[1], ctx.tower.ground + 15], 230, 0.42, ctx.az); setYear(2023); },
        sum: ctx => ctx.loo ? `${fmt(ctx.loo.placed)} placed (median ${fmt(ctx.loo.placed_position_error_m.median, 1)} m), ${fmt(ctx.loo.placed_distance_uncertain)} distance open, ${fmt(ctx.loo.refused)} refused` : '' },
    ] },
];
// The fragment's photographs, painted back onto the city from their own poses, one after another.
let paintTimer = null;
function stopPaint() { if (paintTimer) { clearTimeout(paintTimer); paintTimer = null; } }
function paintAll(r, tower) {
  stopPaint(); showPlaced(null); standing = null;
  const c = centroid(tower.ring), own = scene.photographers.filter(p => p.reconstruction === r.tag && p.photo_large);
  own.sort((a, b) => Math.atan2(a.centre[1] - c[1], a.centre[0] - c[0]) - Math.atan2(b.centre[1] - c[1], b.centre[0] - c[0]));
  for (const p of own.slice(0, 6)) texture(p.photo_large);
  flyTo([c[0], c[1], tower.ground + 15], 200, 0.4, photographersAzimuth(tower));
  let i = 0;
  const step = () => {
    const p = own[i % own.length]; texture(own[(i + 3) % own.length].photo_large);   // load a few ahead
    projectFrom(p, p.photo_large); projectionOn(1); showPlaced(p);
    status(`photograph ${i % own.length + 1} of ${own.length}${p.year ? ' · ' + p.year : ''}${p.artist ? ' · ' + p.artist.replace(/<[^>]+>/g, '') : ''}`);
    i++; paintTimer = setTimeout(step, 1600);
  };
  step();
}
const compass = deg => { const b = (90 - deg + 360) % 360; return ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west'][Math.round(b / 45) % 8]; };

// --- showing a chapter at a step ------------------------------------------------------------------------------
const stepnav = document.getElementById('stepnav'), now = document.getElementById('now');
let current = null, stepIndex = 0;
let reveal = new URLSearchParams(location.search).get('reveal') === 'all';   // every step of a chapter open at once
document.body.classList.toggle('reveal', reveal);
const chapterName = ch => ch.title.replace(/^\d+ · /, '');
function caption(text) { now.innerHTML = text ? '<b>You are looking at</b> ' + text : ''; }
function render(ch) {
  const k = stepIndex, ctx = ch.ctx, n = ch.steps.length;
  const items = ch.steps.map((s, i) => {
    const open = reveal || i === k, cls = reveal ? (i === k ? 'now' : 'open') : i < k ? 'done' : i === k ? 'now' : 'todo';
    const sum = !open && i < k && s.sum ? s.sum(ctx) : '';
    return `<li class="${cls}" data-step="${i}"><span class="n">${!reveal && i < k ? '✓' : i + 1}</span><div class="step">
      <div class="step-title">${s.title}</div>${sum ? `<div class="sum">${sum}</div>` : ''}
      ${open ? `<div class="step-body">${s.body ? s.body(ctx) : ''}</div>` : ''}</div></li>`;
  });
  body.innerHTML = `<div class="chapter-head"><div class="part">${ch.part}</div><h2>${ch.title}</h2><p class="purpose">${ch.purpose}</p></div><ol class="steps">${items.join('')}</ol>`;
  for (const li of body.querySelectorAll('li[data-step]')) li.querySelector('.step-title').onclick = () => show(ch.id, +li.dataset.step);
  for (const [i, s] of ch.steps.entries()) if ((reveal || i === k) && s.after) s.after(ctx);
  if (ch.steps[k].view) ch.steps[k].view(ctx);
  const i = chapters.indexOf(ch), last = k === n - 1, nextCh = chapters[i + 1];
  stepnav.innerHTML = `<button type="button" class="prev" ${k === 0 && i === 0 ? 'disabled' : ''} aria-label="previous step">←</button><span class="pos">step ${k + 1} of ${n}</span>
    <button type="button" class="next" ${last && !nextCh ? 'disabled' : ''}>${last ? (nextCh ? 'Next chapter: ' + chapterName(nextCh) : 'The end') : 'Next: ' + ch.steps[k + 1].title} →</button>`;
  stepnav.querySelector('.prev').onclick = prev; stepnav.querySelector('.next').onclick = next;
}
function show(id, k = 0) {
  if (!chapters.some(c => c.id === id)) id = 'colmap';
  const ch = chapters.find(c => c.id === id);
  if (id !== current) {   // a new chapter: nothing of the previous chapter's view carries over
    current = id;
    for (const b of nav.querySelectorAll('button')) b.setAttribute('aria-current', String(b.dataset.chapter === id));
    if (id !== 'void' && placement.mode === 'floating') { placement.mode = 'placed'; poseAt(1, 0); }
    placement.done = null;   // a snap still running from the previous chapter must not move this chapter's camera
    stopPaint(); projectionOn(0); showPlaced(null); lookUp(false); standing = null;   // a photograph painted on the city belongs to its chapter
    status(''); hideOverlay();
    ch.ctx = ch.setup ? ch.setup() : {};
  }
  stepIndex = Math.max(0, Math.min(ch.steps.length - 1, k));
  render(ch);
  const s = ch.steps[stepIndex]; caption(typeof s.see === 'function' ? s.see(ch.ctx) : s.see);
  body.scrollTop = 0; history.replaceState(null, '', '#' + id + (stepIndex ? '/' + (stepIndex + 1) : ''));
}
// The next step, or the next chapter after the last step; back likewise. Returns whether a step of the same chapter was shown.
function next() { const ch = chapters.find(c => c.id === current), i = chapters.indexOf(ch); if (stepIndex < ch.steps.length - 1) { show(current, stepIndex + 1); return true; } if (chapters[i + 1]) show(chapters[i + 1].id); return false; }
function prev() { const ch = chapters.find(c => c.id === current), i = chapters.indexOf(ch); if (stepIndex > 0) { show(current, stepIndex - 1); return true; } if (chapters[i - 1]) show(chapters[i - 1].id, chapters[i - 1].steps.length - 1); return false; }
function setReveal(on) { reveal = on; document.body.classList.toggle('reveal', on); show(current, stepIndex); }
// Links: #snap opens the chapter at its first step, #snap/3 at its third.
function fromHash() { const [id, s] = (location.hash || '#colmap').slice(1).split('/'); return [id.replace(/[^a-z]/g, ''), Math.max(0, (parseInt(s, 10) || 1) - 1)]; }

let lastPart = null;
for (const ch of chapters) {
  if (ch.part !== lastPart) { nav.append(el('span', { className: 'part' }, ch.part)); lastPart = ch.part; }
  const [n, ...name] = ch.title.split(' · '), b = el('button', { type: 'button', title: ch.title });
  b.innerHTML = `<span class="n">${n}</span><span class="t"> · ${name.join(' · ')}</span>`;   // a short screen shows the numbers only
  nav.append(Object.assign(b, { onclick: () => show(ch.id) }));
  b.dataset.chapter = ch.id;   // the recorded tour and the checks find chapters by id
}

// --- presenter keys: arrows step, page keys change chapter, A opens the whole chapter, F toggles full screen -------
addEventListener('keydown', e => {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === ' ' && e.target instanceof HTMLButtonElement) return;   // a focused button (the step bar's) takes the space itself
  const i = chapters.findIndex(c => c.id === current);
  if (['ArrowRight', ' '].includes(e.key)) { e.preventDefault(); next(); }
  else if (e.key === 'ArrowLeft') { e.preventDefault(); prev(); }
  else if (e.key === 'PageDown' && i < chapters.length - 1) { e.preventDefault(); show(chapters[i + 1].id); }
  else if (e.key === 'PageUp' && i > 0) { e.preventDefault(); show(chapters[i - 1].id); }
  else if (e.key === 'a' || e.key === 'A') setReveal(!reveal);
  else if (e.key === 'f' || e.key === 'F') { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen().catch(() => {}); }
});
addEventListener('hashchange', () => { const [id, k] = fromHash(); if (id !== current || k !== stepIndex) show(id, k); });

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
renderer.setAnimationLoop(() => {
  stepFlight(); stepPlacement(); controls.update(); drawViewfinder();
  projUniforms.uProjOn.value += (projector.on - projUniforms.uProjOn.value) * 0.15;
  renderer.render(world, camera);
});
document.getElementById('attribution').textContent = scene.attribution.join(' ');
document.getElementById('status').textContent = '';
setYear(2007);
show(...fromHash());
// for the headless checks and the recorded tour
window.__tm = { terrains, textures, scene, clouds, view, placement, show, next, prev, step: () => stepIndex, steps: () => chapters.find(c => c.id === current).steps.length, reveal: setReveal,
                camera, controls, cityParts, specialMeshes, gpuName, projector, projUniforms, projectFrom, projectionOn, flyToPhotographer };
document.documentElement.dataset.ready = 'true';
