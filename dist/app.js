const state = { classic: null, cross: null, joint: null, dense: null, manifest: null, viewer: null };
const $ = selector => document.querySelector(selector);
const fmt = (value, digits = 0) => value == null ? "—" : Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"})[c]);

async function json(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return response.json();
}

function metric(value, label) {
  return `<div><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`;
}

function stage(number, title, detail, status, word) {
  return `<article class="stage ${status}"><span class="number">${number}</span><i class="dot"></i><h3>${esc(title)}</h3><p>${esc(detail)}</p><b>${esc(word)}</b></article>`;
}

function badge(status) {
  return `<span class="badge ${status}">${status.toUpperCase()}</span>`;
}

function render() {
  const { classic, cross, joint, dense, manifest } = state;
  const inputs = Object.values(manifest.sets).reduce((sum, set) => sum + set.accepted_count, 0);
  const crossVerified = cross.geometric_verification?.nondegenerate_pairs ?? cross.geometric_verification?.verified_pairs ?? 0;
  const reconstruction = joint.reconstruction || {};
  const byEra = reconstruction.registered_by_era || { historical: 0, modern: 0 };
  const coverage = joint.target_coverage || {};
  const gate = joint.quality_gate || {};
  const targetPass = Boolean(joint.passed);
  const densePass = dense.status === "patch_match_complete";
  const releasePass = targetPass && densePass;

  $("#sum-inputs").textContent = fmt(inputs);
  $("#sum-cross-pairs").textContent = fmt(crossVerified);
  $("#sum-cameras").textContent = `${fmt(byEra.historical)} + ${fmt(byEra.modern)}`;
  $("#global-status").className = `status-chip ${releasePass ? "pass" : "fail"}`;
  $("#global-status").innerHTML = `<span></span>${releasePass ? "RELEASE GATE PASSED" : "RELEASE GATE FAILED · NO 3D CLAIM"}`;
  $("#footer-status").textContent = releasePass ? "RELEASE · PASS" : "RELEASE · REJECT";

  const learnedPairs = joint.learned_matches?.pairs_with_matches ?? 0;
  const targetStatus = targetPass ? "pass" : "fail";
  const targetWord = targetPass ? "PASS" : "FAIL";
  const denseStatus = densePass ? "pass" : "blocked";
  $("#stage-flow").innerHTML = [
    stage("01", "Acquire", `${inputs} licensed public images`, "pass", "PASS"),
    stage("02", "Retrieve", `${fmt(joint.candidate_pairs)} candidate overlaps`, "pass", "PASS"),
    stage("03", "Learned match", `${fmt(learnedPairs)} pairs with matches`, "pass", "PASS"),
    stage("04", "Verify + SfM", `${fmt(byEra.historical)} historical + ${fmt(byEra.modern)} modern cameras`, "pass", "PASS"),
    stage("05", "Boardman gate", `${fmt(coverage.boardman_multiview_historical_only_points)} target-only multiview points`, targetStatus, targetWord),
    stage("06", "Dense surface", densePass ? "PatchMatch completed" : "COLMAP PatchMatch unavailable", denseStatus, densePass ? "PASS" : "BLOCKED / FAIL"),
  ].join("");

  const targetPoints = coverage.boardman_multiview_historical_only_points || 0;
  const boardmanCameras = coverage.registered_boardman_images || 0;
  $("#target-explanation").textContent = targetPass
    ? "The sparse target-coverage gate passed, but publication still requires a validated dense surface."
    : `Only ${fmt(targetPoints)} tracks were observed by at least two Boardman-labelled historical images without relying on a modern observation. The v1 release minimum is ${fmt(gate.min_boardman_multiview_historical_only_points || 1000)}.`;
  $("#target-metrics").innerHTML = [
    [boardmanCameras, `registered Boardman images · need ${gate.min_registered_boardman_images || 3}`, boardmanCameras >= (gate.min_registered_boardman_images || 3)],
    [targetPoints, `Boardman multiview historical-only points · need ${gate.min_boardman_multiview_historical_only_points || 1000}`, targetPoints >= (gate.min_boardman_multiview_historical_only_points || 1000)],
    [coverage.cross_era_points || 0, "tracks observed across both eras", true],
    [0, "accepted dense Boardman surfaces · need 1", false],
  ].map(([value,label,pass]) => `<div class="${pass ? "" : "miss"}"><strong>${fmt(value)}</strong><span>${esc(label)}</span></div>`).join("");

  const classicJoint = classic.runs?.joint || {};
  const classicSelected = classicJoint.selected_model || {};
  const classicEra = classicSelected.registered_by_era || { historical: 0, modern: 0 };
  $("#classic-metrics").innerHTML = [
    metric(classicJoint.database?.verified_pairs || 0, "verified pairs"),
    metric(`${classicEra.historical || 0} + ${classicEra.modern || 0}`, "joint cameras H + M"),
    metric(classicSelected.sparse_points || 0, "sparse points"),
  ].join("");
  $("#hloc-metrics").innerHTML = [
    metric(crossVerified, "verified cross-era pairs"),
    metric(`${byEra.historical || 0} + ${byEra.modern || 0}`, "joint cameras H + M"),
    metric(reconstruction.points3D || 0, "joint sparse points"),
  ].join("");

  const requiredPairs = gate.min_cross_era_nondegenerate_pairs || 3;
  const requiredBoardman = gate.min_registered_boardman_images || 3;
  const requiredPoints = gate.min_boardman_multiview_historical_only_points || 1000;
  const rows = [
    ["Cross-era geometric bridge", `≥ ${requiredPairs} nondegenerate verified pairs`, fmt(joint.geometric_verification?.nondegenerate_pairs || 0), (joint.geometric_verification?.nondegenerate_pairs || 0) >= requiredPairs ? "pass" : "fail"],
    ["Boardman camera coverage", `≥ ${requiredBoardman} registered Boardman images`, fmt(boardmanCameras), boardmanCameras >= requiredBoardman ? "pass" : "fail"],
    ["Boardman-only multiview structure", `≥ ${fmt(requiredPoints)} triangulated points`, fmt(targetPoints), targetPoints >= requiredPoints ? "pass" : "fail"],
    ["Dense surface", "COLMAP-derived surface required", densePass ? "PatchMatch complete" : `0 · ${dense.status}`, densePass ? "pass" : "blocked"],
    ["Public 3D demo", "all preceding gates pass", releasePass ? "released" : "withheld", releasePass ? "pass" : "fail"],
  ];
  $("#gate-body").innerHTML = rows.map(row => `<tr><td>${esc(row[0])}</td><td>${esc(row[1])}</td><td>${esc(row[2])}</td><td>${badge(row[3])}</td></tr>`).join("");
  $("#viewer-points").textContent = fmt(reconstruction.points3D || 0);
  $("#viewer-cameras").textContent = fmt(reconstruction.registered_images || 0);
  renderSources();
}

function renderSources() {
  const cards = [];
  for (const setName of ["historical", "modern"]) {
    for (const item of state.manifest.sets[setName].images.slice(0, 5)) cards.push({ ...item, setName });
  }
  $("#source-grid").innerHTML = cards.map(item => `<a class="source-card" href="${esc(item.source_url)}" target="_blank" rel="noreferrer"><img loading="lazy" src="assets/inputs/${esc(item.setName)}__${esc(item.filename)}" alt="${esc(item.title)}"><strong>${esc(item.title.replace(/^File:/,""))}</strong><span>${esc(item.setName)} · ${esc(item.license || item.usage_terms)}</span></a>`).join("");
}

class PointViewer {
  constructor(canvas) {
    this.canvas = canvas; this.gl = canvas.getContext("webgl", { antialias: true });
    this.yaw = -.65; this.pitch = -.28; this.zoom = 3.2; this.drag = null; this.count = 0;
    if (!this.gl) throw new Error("WebGL unavailable");
    this.initGL(); this.bind(); this.resize(); requestAnimationFrame(() => this.draw());
  }
  shader(type, source) { const s=this.gl.createShader(type);this.gl.shaderSource(s,source);this.gl.compileShader(s);if(!this.gl.getShaderParameter(s,this.gl.COMPILE_STATUS))throw new Error(this.gl.getShaderInfoLog(s));return s; }
  initGL() { const gl=this.gl;const vs=this.shader(gl.VERTEX_SHADER,`attribute vec3 aPosition;attribute vec3 aColor;attribute float aSize;uniform mat4 uMatrix;varying vec3 vColor;void main(){gl_Position=uMatrix*vec4(aPosition,1.0);gl_PointSize=aSize*(2.4/gl_Position.w+1.0);vColor=aColor;}`);const fs=this.shader(gl.FRAGMENT_SHADER,`precision mediump float;varying vec3 vColor;void main(){vec2 p=gl_PointCoord-.5;if(dot(p,p)>.25)discard;gl_FragColor=vec4(vColor,1.0);}`);this.program=gl.createProgram();gl.attachShader(this.program,vs);gl.attachShader(this.program,fs);gl.linkProgram(this.program);gl.useProgram(this.program);this.pos=gl.createBuffer();this.color=gl.createBuffer();this.size=gl.createBuffer();this.uMatrix=gl.getUniformLocation(this.program,"uMatrix");this.aPosition=gl.getAttribLocation(this.program,"aPosition");this.aColor=gl.getAttribLocation(this.program,"aColor");this.aSize=gl.getAttribLocation(this.program,"aSize");gl.enable(gl.DEPTH_TEST);gl.clearColor(.05,.055,.047,1); }
  bind() { this.canvas.addEventListener("pointerdown",e=>{this.drag=[e.clientX,e.clientY];this.canvas.setPointerCapture(e.pointerId)});this.canvas.addEventListener("pointermove",e=>{if(!this.drag)return;this.yaw+=(e.clientX-this.drag[0])*.008;this.pitch=Math.max(-1.45,Math.min(1.45,this.pitch+(e.clientY-this.drag[1])*.008));this.drag=[e.clientX,e.clientY]});this.canvas.addEventListener("pointerup",()=>this.drag=null);this.canvas.addEventListener("wheel",e=>{e.preventDefault();this.zoom=Math.max(1.15,Math.min(8,this.zoom*Math.exp(e.deltaY*.001)))},{passive:false});addEventListener("resize",()=>this.resize()); }
  reset(){this.yaw=-.65;this.pitch=-.28;this.zoom=3.2}
  resize(){const d=Math.min(devicePixelRatio||1,2),w=Math.round(this.canvas.clientWidth*d),h=Math.round(this.canvas.clientHeight*d);if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=w;this.canvas.height=h;this.gl.viewport(0,0,w,h)}}
  setData(model){const points=model.points||[],cameras=model.cameras||[],fit=points.length?points.map(x=>x.p):cameras.map(x=>x.center);if(!fit.length)return;const bounds=[0,1,2].map(axis=>{const v=fit.map(p=>p[axis]).sort((a,b)=>a-b),at=q=>v[Math.max(0,Math.min(v.length-1,Math.round(q*(v.length-1))))];return v.length>=30?[at(.03),at(.97)]:[v[0],v[v.length-1]]});const center=bounds.map(([a,b])=>(a+b)/2),scale=2.4/Math.max(...bounds.map(([a,b])=>b-a),1e-6),positions=[],colors=[],sizes=[];points.forEach(x=>{positions.push(...x.p.map((v,i)=>(v-center[i])*scale));colors.push(...x.c.map(v=>Math.max(.18,v/255)));sizes.push(3)});cameras.forEach(x=>{positions.push(...x.center.map((v,i)=>(v-center[i])*scale));colors.push(.96,.29,.18);sizes.push(8)});const gl=this.gl;this.count=sizes.length;[[this.pos,positions],[this.color,colors],[this.size,sizes]].forEach(([b,d])=>{gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(d),gl.STATIC_DRAW)});}
  mul(a,b){const o=new Float32Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)o[c*4+r]=a[r]*b[c*4]+a[4+r]*b[c*4+1]+a[8+r]*b[c*4+2]+a[12+r]*b[c*4+3];return o}
  matrix(){const a=this.canvas.width/this.canvas.height,n=.1,f=30,t=1/Math.tan(.75/2),p=new Float32Array([t/a,0,0,0,0,t,0,0,0,0,(f+n)/(n-f),-1,0,0,2*f*n/(n-f),0]),cy=Math.cos(this.yaw),sy=Math.sin(this.yaw),cx=Math.cos(this.pitch),sx=Math.sin(this.pitch),ry=new Float32Array([cy,0,-sy,0,0,1,0,0,sy,0,cy,0,0,0,0,1]),rx=new Float32Array([1,0,0,0,0,cx,sx,0,0,-sx,cx,0,0,0,0,1]),tr=new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,-this.zoom,1]);return this.mul(p,this.mul(tr,this.mul(rx,ry)))}
  draw(){this.resize();const gl=this.gl;gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);if(this.count){gl.useProgram(this.program);gl.uniformMatrix4fv(this.uMatrix,false,this.matrix());[[this.pos,this.aPosition,3],[this.color,this.aColor,3],[this.size,this.aSize,1]].forEach(([b,a,n])=>{gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,n,gl.FLOAT,false,0,0)});gl.drawArrays(gl.POINTS,0,this.count)}requestAnimationFrame(()=>this.draw())}
}

async function loadDiagnostic() {
  if (state.viewer) return;
  try {
    const model = await json("assets/hloc-joint-viewer.json");
    state.viewer = new PointViewer($("#point-viewer"));
    state.viewer.setData(model);
    $("#reset-view").addEventListener("click", () => state.viewer.reset());
  } catch (error) {
    console.error(error);
    $(".diagnostic-warning").textContent += ` Viewer unavailable: ${error.message}`;
  }
}

async function init() {
  try {
    [state.classic,state.cross,state.joint,state.dense,state.manifest] = await Promise.all([
      json("assets/report.json"), json("assets/hloc-cross-era-report.json"), json("assets/hloc-joint-report.json"), json("assets/dense-mvs-report.json"), json("assets/manifest.json")
    ]);
    render();
    $("#diagnostic").addEventListener("toggle", event => { if (event.target.open) loadDiagnostic(); });
  } catch (error) {
    console.error(error);
    $("#global-status").className = "status-chip fail";
    $("#global-status").innerHTML = `<span></span>REPORT UNAVAILABLE · ${esc(error.message)}`;
  }
}

init();
