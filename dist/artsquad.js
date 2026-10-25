import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { OBJLoader } from './vendor/OBJLoader.js';
import { MTLLoader } from './vendor/MTLLoader.js';

const $ = selector => document.querySelector(selector);
const manifestPath = 'assets/artsquad/scene.json';
const host = $('#viewport');
const number = value => Number.isFinite(Number(value)) ? Number(value).toLocaleString('en-US') : '—';
const text = (selector, value) => { $(selector).textContent = value; };
const state = { manifest:null, component:null, object:null, cameras:null, renderer:null, scene:null, camera:null, controls:null, serial:0, photoSerial:0, evidencePickSerial:0, evidenceResource:null, activeView:null, radius:1, display:'texture', touring:false, assetErrors:[] };
const normalMaterial = new THREE.MeshNormalMaterial({ side:THREE.DoubleSide });
const wireMaterial = new THREE.MeshBasicMaterial({ color:0xd8d7ba, wireframe:true, side:THREE.DoubleSide });
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

function allowedURL(value) {
  if (!value || typeof value !== 'string') return null;
  try { const url = new URL(value, state.manifest?.asset_base ? new URL(state.manifest.asset_base,location.href) : location.href); return ['http:','https:'].includes(url.protocol) ? url.href : null; } catch { return null; }
}
function link(selector, value) { const element=$(selector), url=allowedURL(value); element.hidden=!url; if(url)element.href=url;else element.removeAttribute('href'); }
function assetError(message) {
  if(!state.assetErrors.includes(message))state.assetErrors.push(message);
  $('#asset-error').hidden=false;
  text('#asset-error', state.assetErrors.join(' · '));
}
function resetErrors() { state.assetErrors=[];$('#asset-error').hidden=true;text('#asset-error',''); }
function status(message) { text('#load-status',message); }
function empty(title,copy) { $('#empty-state').hidden=false;text('#empty-title',title);text('#empty-copy',copy); }
function fieldDisplay(value) {
  if(value===null||value===undefined)return 'Not yet verified';
  if(typeof value==='string')return value.replaceAll('_',' ');
  return fieldDisplay(value.status || value.state || 'not yet verified');
}
function listItem(value) { const li=document.createElement('li');li.textContent=typeof value==='string'?value:value.message||value.reason||JSON.stringify(value);return li; }

function renderManifest(manifest) {
  if(manifest.pipeline?.length){$('#pipeline-rows').replaceChildren(...manifest.pipeline.map(stage=>{const row=document.createElement('tr');for(const value of [stage.name,stage.detail,stage.status]){const cell=document.createElement('td');cell.textContent=value||'not recorded';row.append(cell);}const href=allowedURL(stage.report_url);if(href){const anchor=document.createElement('a');anchor.href=href;anchor.target='_blank';anchor.rel='noopener noreferrer';anchor.textContent=' Record ↗';row.children[1].append(anchor);}return row;}));}link('#pipeline-report-link',manifest.pipeline_report_url);
  const statuses={not_ready:'D1 NOT READY · DATA & GEOMETRY IN PROGRESS',diagnostic:'DIAGNOSTIC RUN · NOT A COMPLETED DEMO',d0_candidate:'D0 CANDIDATE · VERIFICATION REQUIRED',d1_candidate:'D1 CANDIDATE · ACCEPTANCE REQUIRED'};
  text('#scene-status',statuses[manifest.status]||String(manifest.status||'UNVERIFIED RUN').replaceAll('_',' ').toUpperCase());
  text('#run-label',manifest.run_id?`RUN / ${manifest.run_id}`:'ARTS QUAD ATLAS / RESEARCH PREVIEW');
  text('#data-downloaded',number(manifest.data?.downloaded));text('#data-candidates',number(manifest.data?.scene_candidates));text('#data-train',number(manifest.data?.train_images));text('#data-test',number(manifest.data?.test_images));
  const rows=(manifest.data?.by_target||[]).map(target=>{
    const tr=document.createElement('tr');tr.dataset.target=target.id;
    const td=document.createElement('td'),name=document.createElement('span'),role=document.createElement('span');name.textContent=target.name;role.className='target-role';
    const core=['core','core_target'].includes(target.role);role.textContent=core?'CORE':'CONTEXT';if(!core)tr.className='target-context';td.append(name,role);tr.append(td);
    for(const value of [target.downloaded,target.train,target.test]){const cell=document.createElement('td');cell.textContent=number(value);tr.append(cell);}return tr;
  });
  if(rows.length)$('#coverage-rows').replaceChildren(...rows);else{const row=document.createElement('tr'),cell=document.createElement('td');cell.colSpan=4;cell.textContent='No per-target source inventory has been generated.';row.append(cell);$('#coverage-rows').replaceChildren(row);}
  const limitations=manifest.limitations?.length?manifest.limitations:['No independent geometry validation has been provided for this run.'];$('#limitations').replaceChildren(...limitations.map(listItem));
  for(const id of ['d0','d1','d2','r1'])text(`#milestone-${id}`,fieldDisplay(manifest.milestones?.[id]??manifest.milestones?.[id.toUpperCase()]));
  const resources=manifest.resources||{};
  const summary=typeof resources==='string'?resources:resources.summary||[
    resources.software?.torch?.cuda_available===false?'local CUDA unavailable':resources.software?.torch?.cuda_available===true?'local CUDA available':null,
    resources.host_memory_gib?`${resources.host_memory_gib} GiB host RAM`:null,
    resources.disk_free_gib?`${resources.disk_free_gib} GiB disk free`:null,
    resources.remote_resource_status?`remote compute: ${resources.remote_resource_status}`:null,
  ].filter(Boolean).join(' · ')||Object.entries(resources).filter(([,value])=>['string','number','boolean'].includes(typeof value)).map(([key,value])=>`${key.replaceAll('_',' ')}: ${value}`).join(' · ');
  text('#resource-summary',summary?`Compute environment: ${summary}`:'Compute environment: not recorded in this manifest.');
  link('#project-status-link',manifest.status_url);link('#all-sources-link',manifest.sources_url);link('#source-code-link',manifest.source_code_url);link('#project-contract-link',manifest.project_contract_url);
  text('#generated-label',manifest.generated_utc?`MANIFEST GENERATED / ${manifest.generated_utc}`:'');
  $('#component-select').replaceChildren(...(manifest.components||[]).map((component,index)=>new Option(component.label||component.id,index)));
  $('#component-select').disabled=!(manifest.components?.length);
  if(!manifest.components?.length)$('#component-select').append(new Option('No computed components',''));
}

function createViewer() {
  try {
    const renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
    renderer.domElement.setAttribute('aria-label','Computed reconstruction');host.prepend(renderer.domElement);
    const scene=new THREE.Scene();scene.background=new THREE.Color('#202824');
    const camera=new THREE.PerspectiveCamera(50,1,.001,10000);
    const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=!reducedMotion;controls.dampingFactor=.08;controls.autoRotateSpeed=.6;
    controls.addEventListener('start',()=>{setTour(false);});
    Object.assign(state,{renderer,scene,camera,controls});
    new ResizeObserver(resize).observe(host);resize();
    renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera);});
    renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();assetError('WebGL context lost. Reload the page or use the source photographs and reports.');setTour(false);});
    let pointerStart=null;renderer.domElement.addEventListener('pointerdown',e=>{pointerStart={x:e.clientX,y:e.clientY};});
    const freeCamera=()=>{if(!state.activeView)return;state.activeView=null;projection();status('FREE CAMERA VIEW · source-camera intrinsics no longer locked');};
    // A click must raycast the projection the visitor actually saw. Clearing
    // calibration on OrbitControls' "start" also fires on a stationary click
    // and used to move tiny measured facets away before pointerup picking.
    renderer.domElement.addEventListener('pointermove',e=>{if(pointerStart&&Math.hypot(e.clientX-pointerStart.x,e.clientY-pointerStart.y)>4)freeCamera();},{capture:true});
    renderer.domElement.addEventListener('wheel',freeCamera,{capture:true,passive:true});
    renderer.domElement.addEventListener('pointerup',event=>{if(pointerStart&&Math.hypot(event.clientX-pointerStart.x,event.clientY-pointerStart.y)<5)pickSurface(event);pointerStart=null;});
    return true;
  } catch(error) {assetError(`3D rendering unavailable: ${error.message}`);empty('Your browser cannot open the 3D view.','The source inventory and research reports remain available below. No fallback scene has been fabricated.');return false;}
}
function projection() {
  if(!state.camera)return;
  const camera=state.camera;camera.updateProjectionMatrix();syncPhotoOverlay();const view=state.activeView;if(!view)return;
  const w=Math.max(host.clientWidth,1),h=Math.max(host.clientHeight,1),scale=Math.min(w/view.width,h/view.height),K=view.K;
  const cx=(w-scale*view.width)/2+scale*K[0][2],cy=(h-scale*view.height)/2+scale*K[1][2],n=camera.near,f=camera.far;
  camera.projectionMatrix.set(2*scale*K[0][0]/w,0,1-2*cx/w,0,0,2*scale*K[1][1]/h,2*cy/h-1,0,0,0,-(f+n)/(f-n),-2*f*n/(f-n),0,0,-1,0);
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
}
function resize() {if(!state.renderer)return;const w=Math.max(host.clientWidth,1),h=Math.max(host.clientHeight,1);state.renderer.setSize(w,h);state.camera.aspect=w/h;projection();}
function fitScene() {
  if(!state.object)return;
  const box=new THREE.Box3().setFromObject(state.object);if(box.isEmpty())return;
  const center=box.getCenter(new THREE.Vector3());state.radius=Math.max(box.getSize(new THREE.Vector3()).length()/2,.001);state.activeView=null;
  const camera=state.camera;camera.near=state.radius/10000;camera.far=state.radius*200;camera.fov=50;camera.up.set(0,1,0);
  camera.position.copy(center).add(new THREE.Vector3(state.radius*.8,state.radius*.4,state.radius*2.1));camera.lookAt(center);state.controls.target.copy(center);state.controls.update();projection();
}
function disposeObject(root) {
  const textures=new Set(),materials=new Set();root.traverse(child=>{child.geometry?.dispose();const material=child.userData.photoMaterial||child.material;for(const value of (Array.isArray(material)?material:[material])){if(!value||value===wireMaterial||value===normalMaterial)continue;materials.add(value);for(const key of ['map','normalMap','roughnessMap','alphaMap'])if(value[key])textures.add(value[key]);}});textures.forEach(t=>t.dispose());materials.forEach(m=>m.dispose());
}
function clearObject() {if(state.object){state.scene.remove(state.object);disposeObject(state.object);state.object=null;}if(state.cameras){state.scene.remove(state.cameras);disposeObject(state.cameras);state.cameras=null;}}
function applyDisplay(mode) {
  state.display=mode;document.querySelectorAll('[data-display]').forEach(button=>{const active=button.dataset.display===mode;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
  state.object?.traverse(child=>{if(child.isMesh)child.material=mode==='solid'?normalMaterial:mode==='wire'?wireMaterial:child.userData.photoMaterial;});
}
function cameraMatrix(view) {
  const values=view.world_matrix?.flat();if(values?.length!==16||!values.every(Number.isFinite))return null;
  const matrix=new THREE.Matrix4().set(...values);
  if(view.convention==='opencv'||view.camera_convention==='opencv')matrix.multiply(new THREE.Matrix4().makeScale(1,-1,-1));
  return matrix;
}
function validCamera(view) {return cameraMatrix(view)&&view.K?.length===3&&view.K.flat().every(Number.isFinite)&&view.K[0][0]>0&&view.K[1][1]>0&&view.width>0&&view.height>0;}
function cameraMarkers() {
  const group=new THREE.Group(),vertices=[],scale=state.radius*.035;
  for(const view of state.component?.cameras||[]){if(!validCamera(view))continue;const matrix=cameraMatrix(view),origin=new THREE.Vector3().setFromMatrixPosition(matrix),corners=[[0,0],[view.width,0],[view.width,view.height],[0,view.height]].map(([x,y])=>new THREE.Vector3((x-view.K[0][2])/view.K[0][0]*scale,-(y-view.K[1][2])/view.K[1][1]*scale,-scale).applyMatrix4(matrix));for(let i=0;i<4;i++){vertices.push(...origin.toArray(),...corners[i].toArray());vertices.push(...corners[i].toArray(),...corners[(i+1)%4].toArray());}}
  if(vertices.length){const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));group.add(new THREE.LineSegments(geometry,new THREE.LineBasicMaterial({color:0xd5a373,transparent:true,opacity:.7})));}
  group.visible=$('#show-cameras').checked;state.cameras=group;state.scene.add(group);
}
function selectSource(index) {
  const request=++state.photoSerial,view=state.component?.cameras?.[index];$('#source-photo').hidden=true;$('#photo-empty').hidden=false;$('#snap-camera').disabled=true;
  if(!view){text('#source-name','No recovered source camera');text('#source-metadata','');link('#source-link',null);syncPhotoOverlay();return;}
  text('#source-name',view.name||String(view.id));
  const details=[view.split?`${view.split} image`:null,view.exposure_group_id?`exposure: ${view.exposure_group_id}`:null,view.attribution||null].filter(Boolean);text('#source-metadata',details.join(' · '));
  const photo=allowedURL(view.photo);if(photo){const image=$('#source-photo');image.onload=()=>{if(request!==state.photoSerial)return;image.hidden=false;$('#photo-empty').hidden=true;};image.onerror=()=>{if(request!==state.photoSerial)return;image.hidden=true;$('#photo-empty').hidden=false;assetError('A source photograph could not be loaded.');};image.alt=`Source photograph: ${view.name||view.id}`;image.src=photo;}
  link('#source-link',view.source_url||view.page_url||view.photo);$('#snap-camera').disabled=!state.object||!validCamera(view);syncPhotoOverlay();
}
function syncPhotoOverlay() {
  const selected=state.component?.cameras?.[Number($('#source-select').value)],view=state.activeView;
  const photo=view&&selected===view&&validCamera(view)?allowedURL(view.photo):null;
  const toggle=$('#photo-overlay-toggle'),opacity=$('#photo-overlay-opacity'),image=$('#registered-photo'),panel=$('#photo-overlay');
  toggle.disabled=!photo;opacity.disabled=!photo;
  const amount=Math.max(0,Math.min(100,Number(opacity.value)||0));text('#photo-overlay-value',`${amount}%`);panel.style.opacity=String(amount/100);
  text('#photo-overlay-note',photo?'The undistorted training photograph uses this recovered camera projection. Overlay alignment is not independent geometric validation.':'Choose “View from this camera” to compare the selected photograph. The overlay is hidden in free-camera views.');
  if(!photo||!toggle.checked){panel.hidden=true;return;}
  if(image.src!==photo){panel.hidden=true;image.src=photo;return;}
  panel.hidden=!(image.complete&&image.naturalWidth>0);
}
function snapToCamera() {
  const view=state.component?.cameras?.[Number($('#source-select').value)];if(!state.object||!validCamera(view))return;
  setTour(false);state.activeView=view;const matrix=cameraMatrix(view),camera=state.camera;
  camera.position.setFromMatrixPosition(matrix);camera.quaternion.setFromRotationMatrix(matrix);camera.up.setFromMatrixColumn(matrix,1);
  const direction=new THREE.Vector3(0,0,-1).applyQuaternion(camera.quaternion),center=new THREE.Box3().setFromObject(state.object).getCenter(new THREE.Vector3());state.controls.target.copy(camera.position).addScaledVector(direction,Math.max(camera.position.distanceTo(center),state.radius*.1));state.controls.update();projection();status('CALIBRATED CAMERA VIEW · displayed with the recorded image intrinsics');
}
function setTour(enabled) {state.touring=Boolean(enabled)&&Boolean(state.object)&&!reducedMotion;if(state.controls)state.controls.autoRotate=state.touring;text('#tour-toggle',state.touring?'Ⅱ Stop orbit':'▷ Orbit preview');$('#tour-toggle').setAttribute('aria-pressed',String(state.touring));if(state.touring){state.activeView=null;projection();}}
function clearSurfaceEvidence() {
  ++state.evidencePickSerial;state.evidenceResource?.controller.abort();state.evidenceResource=null;
  $('#surface-evidence').hidden=true;delete $('#surface-evidence').dataset.state;delete $('#surface-evidence').dataset.faceIndex;$('#surface-support-photos').replaceChildren();$('#surface-groups-details').hidden=true;text('#surface-evidence-status','');text('#surface-group-ids','');
}
function basename(value) {return String(value).replaceAll('\\','/').split('/').pop();}
async function surfaceEvidence(hit) {
  const request=++state.evidencePickSerial,component=state.component,componentRequest=state.serial,url=allowedURL(component.face_evidence_url);
  if(!url||!Number.isInteger(hit.faceIndex)){$('#surface-evidence').hidden=true;return;}
  const faceIndex=(hit.object.userData.faceOffset||0)+hit.faceIndex,panel=$('#surface-evidence');panel.hidden=false;panel.dataset.state='loading';panel.dataset.faceIndex=String(faceIndex);text('#surface-evidence-status',`Reading estimated visibility for facet ${faceIndex}…`);$('#surface-support-photos').replaceChildren();$('#surface-groups-details').hidden=true;
  try {
    if(!state.evidenceResource||state.evidenceResource.url!==url){const controller=new AbortController(),resource={url,controller,promise:null};resource.promise=(async()=>{const response=await fetch(url,{signal:controller.signal});if(!response.ok)throw new Error(`Facet records HTTP ${response.status}`);const data=await response.json();if(!Array.isArray(data.faces))throw new Error('Facet visibility records have no indexed faces array');return data;})();state.evidenceResource=resource;}
    const data=await state.evidenceResource.promise;
    if(request!==state.evidencePickSerial||componentRequest!==state.serial||component!==state.component)return;
    const face=data.faces[faceIndex];if(!face)throw new Error(`No visibility record for facet ${faceIndex}`);
    const names=[...new Set((face.common_images||[]).map(basename))],families=[...new Set(face.common_recorded_source_families||[])],exposures=[...new Set(face.common_recorded_exposure_groups||[])];
    const cameras=(component.cameras||[]).map((view,index)=>({view,index})).filter(({view})=>names.includes(basename(view.name)));
    text('#surface-evidence-status',`${names.length} common camera images · ${families.length} recorded source families · ${exposures.length} recorded exposure groups`);
    const buttons=cameras.map(({view,index})=>{const button=document.createElement('button');button.type='button';button.dataset.sourceIndex=String(index);button.dataset.cameraName=view.name;button.title=view.name;button.textContent=basename(view.name).replace(/^modern__/,'').replace(/_/g,' ');button.addEventListener('click',()=>{if(component!==state.component||componentRequest!==state.serial)return;$('#source-select').value=String(index);selectSource(index);text('#evidence-copy','This photograph is recorded in the selected facet’s estimated stereo visibility. It is not necessarily its texture camera, and it does not independently certify geometric accuracy.');});return button;});$('#surface-support-photos').replaceChildren(...buttons);
    if(names.length>cameras.length){const note=document.createElement('p');note.textContent=`${names.length-cameras.length} recorded image(s) are not in the packaged camera set.`;$('#surface-support-photos').append(note);}
    text('#surface-group-ids',`Source families: ${families.join(', ')||'not recorded'}\nExposure groups: ${exposures.join(', ')||'not recorded'}\nTexture material: ${face.texture_material||'not recorded'}`);$('#surface-groups-details').hidden=false;panel.dataset.state='loaded';
  } catch(error){if(request!==state.evidencePickSerial||componentRequest!==state.serial||component!==state.component)return;panel.dataset.state='error';text('#surface-evidence-status',`Facet visibility unavailable: ${error.message}. No support claim is substituted.`);}
}
function pickSurface(event) {
  if(!state.object)return;const rect=host.getBoundingClientRect(),pointer=new THREE.Vector2((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1),raycaster=new THREE.Raycaster();raycaster.params.Points.threshold=state.radius*.01;raycaster.setFromCamera(pointer,state.camera);
  const hit=raycaster.intersectObject(state.object,true)[0];if(!hit)return;
  $('#picked-location').hidden=false;text('#picked-location',`Selected scene position: ${hit.point.toArray().map(v=>v.toFixed(3)).join(', ')} (component units).`);
  const photoMaterials=hit.object.userData.photoMaterial,photoMaterial=Array.isArray(photoMaterials)?photoMaterials[hit.face?.materialIndex||0]:photoMaterials;
  const sourceId=state.component.source_materials?.[photoMaterial?.name],index=sourceId===null||sourceId===undefined?-1:(state.component.cameras||[]).findIndex(view=>String(view.id)===String(sourceId));
  if(index>=0){$('#source-select').value=String(index);selectSource(index);text('#evidence-copy','This selected facet is textured from the photograph shown above. That identifies its texture provenance only—not its independent geometric support, completeness or accuracy. Those checks require the reconstruction and validation records.');}
  else text('#evidence-copy','This selection identifies a location in the computed component. A per-surface observation map has not been supplied; the photographs above are component-level sources, not verified supporters of this selected patch.');
  surfaceEvidence(hit);
}
async function loadMesh(component,request) {
  const url=allowedURL(component.mesh.url);if(!url)throw new Error('Invalid mesh URL');const meshURL=new URL(url);
  const manager=new THREE.LoadingManager();manager.onError=item=>{if(request===state.serial)assetError(`Asset load failed: ${new URL(item,location.href).pathname}`);};
  let materials;
  const releaseUnreferenced=(keep=new Set())=>{const released=new Set();for(const material of Object.values(materials?.materials||{})){for(const value of Object.values(material)){if(value?.isTexture&&!keep.has(value)&&!released.has(value)){value.dispose();released.add(value);}}material.dispose();}};
  try {
    if(component.mesh.mtl_url){const mtlURL=allowedURL(component.mesh.mtl_url);if(!mtlURL)throw new Error('Invalid material URL');materials=await new MTLLoader(manager).setResourcePath(new URL('.',mtlURL).href).loadAsync(mtlURL);materials.preload();}
    const loader=new OBJLoader(manager);if(materials)loader.setMaterials(materials);const object=await loader.loadAsync(meshURL.href),keepTextures=new Set();let faceOffset=0;
    object.traverse(child=>{if(!child.isMesh)return;child.userData.faceOffset=faceOffset;faceOffset+=(child.geometry.index?.count||child.geometry.attributes.position.count)/3;const convert=material=>{if(material.map){material.map.flipY=component.mesh.texture_flip_y!==false;material.map.colorSpace=THREE.SRGBColorSpace;material.map.needsUpdate=true;keepTextures.add(material.map);}const photo=new THREE.MeshBasicMaterial({name:material.name,map:material.map||null,color:material.map?0xffffff:material.color||0xa8afa1,side:THREE.DoubleSide});material.dispose();return photo;};child.material=Array.isArray(child.material)?child.material.map(convert):convert(child.material);child.userData.photoMaterial=child.material;});releaseUnreferenced(keepTextures);return object;
  } catch(error) {releaseUnreferenced();throw error;}
}
async function loadSparse(component) {
  const url=allowedURL(component.sparse.url);if(!url)throw new Error('Invalid point-cloud URL');const response=await fetch(url);if(!response.ok)throw new Error(`Point cloud HTTP ${response.status}`);const data=await response.json(),positions=data.positions?.flat();
  if(!positions?.length||positions.length%3||!positions.every(Number.isFinite))throw new Error('Point-cloud coordinates missing or invalid');
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));const colors=data.colors?.flat();if(colors?.length===positions.length&&colors.every(Number.isFinite)){const scale=colors.some(v=>v>1)?255:1;geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors.map(v=>v/scale),3));}
  geometry.computeBoundingSphere();const pointSize=Math.max(geometry.boundingSphere.radius*.003,.000001),material=new THREE.PointsMaterial({size:pointSize,vertexColors:Boolean(geometry.attributes.color),color:geometry.attributes.color?0xffffff:0xd6dccb,sizeAttenuation:true});return new THREE.Points(geometry,material);
}
async function selectComponent(index) {
  const request=++state.serial,component=state.manifest.components[index];if(!component)return;document.documentElement.dataset.viewerState='loading';clearSurfaceEvidence();state.component=component;resetErrors();setTour(false);if(state.scene)clearObject();state.activeView=null;syncPhotoOverlay();
  document.querySelectorAll('[data-display]').forEach(button=>{button.disabled=true;});
  $('#picked-location').hidden=true;$('#source-select').replaceChildren(...(component.cameras||[]).map((view,i)=>new Option(`${view.split==='test'?'[held out] ':''}${view.name||view.id}`,i)));$('#source-select').disabled=!component.cameras?.length;if(!component.cameras?.length)$('#source-select').append(new Option('No recovered cameras',''));
  selectSource(0);link('#component-report',component.report_url);link('#component-evidence',component.evidence_url);link('#component-model-download',component.model_download_url);link('#component-holdout',component.holdout_report_url);link('#component-dense-support',component.dense_support_report_url);link('#component-face-evidence',component.face_evidence_url);
  const dense=component.stats?.dense_points>0; text('#stat-cameras',number(component.stats?.registered_cameras));text('#stat-points',number(dense?component.stats.dense_points:component.stats?.sparse_points));text('#point-label',dense?'fused depth points':'sparse diagnostic points');text('#stat-faces',number(component.stats?.mesh_faces));
  const coreIds=new Set((state.manifest.data?.by_target||[]).filter(target=>['core','core_target'].includes(target.role)).map(target=>target.id));text('#stat-core',number((component.core_target_ids||[]).filter(id=>coreIds.has(id)).length));
  text('#explorer-title',component.label||component.id);text('#coordinate-label',component.scale_status==='verified'?'SCALE VERIFIED · SEE REPORT':'SCALE UNVERIFIED · COMPONENT UNITS');
  text('#source-explanation','Inspect an image recorded with this component. A recovered camera does not, by itself, verify the entire building.');
  text('#evidence-copy','These are component-level source observations. Per-surface supporting photographs and independent geometric accuracy must be checked in the run reports; they are not inferred from the photo count.');
  const limitations=[...(state.manifest.limitations||[]),...(component.limitations||[])];if(limitations.length)$('#limitations').replaceChildren(...limitations.map(listItem));
  $('#tour-toggle').disabled=true;$('#fit-scene').disabled=true;
  if(!state.renderer){status('3D UNAVAILABLE · source records remain accessible');return;}
  if(!component.mesh?.url&&!component.sparse?.url){text('#geometry-tag','NO COMPUTED GEOMETRY FOR THIS COMPONENT');empty('No geometry has passed into this run.','Source photographs can be inspected, but no artificial building is substituted.');status('WAITING FOR RECONSTRUCTION ARTIFACTS');document.documentElement.dataset.viewerState='empty';return;}
  text('#geometry-tag',component.mesh?.url?'COMPUTED SURFACE · SEE VALIDATION REPORT':'SPARSE CAMERA DIAGNOSTIC · NOT A BUILDING MODEL');empty('Opening the computed component…','Loading the recorded artifact, not a generated replacement.');status(component.mesh?.url?'Loading computed surface and photograph textures…':'Loading sparse SfM diagnostic…');
  try {const object=component.mesh?.url?await loadMesh(component,request):await loadSparse(component);if(request!==state.serial){disposeObject(object);return;}state.object=object;state.scene.add(object);$('#empty-state').hidden=true;fitScene();applyDisplay(state.display);cameraMarkers();selectSource(Number($('#source-select').value)||0);$('#fit-scene').disabled=false;$('#tour-toggle').disabled=reducedMotion;document.querySelectorAll('[data-display]').forEach(button=>{button.disabled=!component.mesh?.url;});
    const cameraIndex=component.default_camera_id!==undefined?(component.cameras||[]).findIndex(view=>String(view.id)===String(component.default_camera_id)):component.mesh?.url?(component.cameras||[]).findIndex(validCamera):-1;
    if(cameraIndex>=0){$('#source-select').value=String(cameraIndex);selectSource(cameraIndex);snapToCamera();}
    status(component.mesh?.url?'COMPUTED SURFACE LOADED · source and validation records remain separate':'SPARSE DIAGNOSTIC ONLY · no dense surface has been supplied');
    document.documentElement.dataset.viewerState=component.mesh?.url?'mesh':'sparse';
  } catch(error){if(request!==state.serial)return;console.error(error);assetError(error.message);empty('The recorded artifact could not be opened.','Its failure is shown here. No replacement geometry has been generated.');status('ARTIFACT LOAD FAILED');document.documentElement.dataset.viewerState='error';}
}

$('#component-select').addEventListener('change',event=>selectComponent(Number(event.target.value)));
$('#source-select').addEventListener('change',event=>selectSource(Number(event.target.value)));
$('#photo-overlay-toggle').addEventListener('change',syncPhotoOverlay);
$('#photo-overlay-opacity').addEventListener('input',syncPhotoOverlay);
$('#registered-photo').addEventListener('load',syncPhotoOverlay);
$('#registered-photo').addEventListener('error',()=>{assetError('The registered photo overlay could not be loaded.');$('#photo-overlay').hidden=true;});
$('#snap-camera').addEventListener('click',snapToCamera);
$('#fit-scene').addEventListener('click',()=>{setTour(false);fitScene();status('COMPONENT VIEW · orbit and zoom to explore the measured support');});
$('#show-cameras').addEventListener('change',event=>{if(state.cameras)state.cameras.visible=event.target.checked;});
$('#tour-toggle').addEventListener('click',()=>setTour(!state.touring));
document.querySelectorAll('[data-display]').forEach(button=>button.addEventListener('click',()=>applyDisplay(button.dataset.display)));
host.addEventListener('keydown',event=>{if(event.key==='Escape'){setTour(false);fitScene();}if(event.key.toLowerCase()==='f'){event.preventDefault();fitScene();}});

try {
  const response=await fetch(manifestPath,{cache:'no-store'});if(!response.ok)throw new Error(`Scene manifest HTTP ${response.status}`);const manifest=await response.json();if(manifest.schema_version!==1)throw new Error('Unsupported scene manifest version');state.manifest=manifest;renderManifest(manifest);createViewer();
  if(manifest.components?.length){const query=new URLSearchParams(location.search).get('component'),index=Math.max(0,manifest.components.findIndex(component=>component.id===query));$('#component-select').value=String(index);await selectComponent(index);}else{empty('No multi-building reconstruction yet.','The inventory below records the work in hand. A connected Arts Quad model has not been supplied, and no synthetic campus is substituted.');text('#geometry-tag','D1 PENDING · NO CONNECTED CORE-BUILDING SURFACE');status('NO SCENE ARTIFACT · source counts are not a reconstruction');$('#fit-scene').disabled=true;document.documentElement.dataset.viewerState='empty';}
  document.documentElement.dataset.manifestState='loaded';
} catch(error){console.error(error);assetError(error.message);text('#scene-status','RUN MANIFEST UNAVAILABLE');empty('The run manifest is unavailable.','The atlas cannot make claims about data, progress or geometry until its run records are available.');status('MANIFEST LOAD FAILED');document.documentElement.dataset.manifestState='error';}
