import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { OBJLoader } from './vendor/OBJLoader.js';
import { MTLLoader } from './vendor/MTLLoader.js';

const $ = s => document.querySelector(s);
const host = $('#viewport');
const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
host.prepend(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color('#151713');
const camera = new THREE.PerspectiveCamera(50,1,.001,10000);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
let manifest, model, object, serial = 0, radius = 1, activeView = null;
const solid = new THREE.MeshNormalMaterial({side:THREE.DoubleSide});
const wire = new THREE.MeshBasicMaterial({color:0xe5ddd0,wireframe:true,side:THREE.DoubleSide});

function projection(){
  camera.updateProjectionMatrix();
  if(!activeView)return;
  const w=host.clientWidth,h=host.clientHeight,v=activeView,s=Math.min(w/v.width,h/v.height);
  const cx=(w-s*v.width)/2+s*v.K[0][2],cy=(h-s*v.height)/2+s*v.K[1][2];
  const n=camera.near,f=camera.far;
  camera.projectionMatrix.set(2*s*v.K[0][0]/w,0,1-2*cx/w,0, 0,2*s*v.K[1][1]/h,2*cy/h-1,0, 0,0,-(f+n)/(f-n),-2*f*n/(f-n), 0,0,-1,0);
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
}
function resize(){const w=host.clientWidth,h=host.clientHeight;renderer.setSize(w,h);camera.aspect=w/h;projection();}
new ResizeObserver(resize).observe(host);
renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera);});

function fit(){if(!object)return;activeView=null;const box=new THREE.Box3().setFromObject(object);const center=box.getCenter(new THREE.Vector3());radius=Math.max(box.getSize(new THREE.Vector3()).length()/2,.001);camera.near=radius/10000;camera.far=radius*100;camera.position.copy(center.clone().add(new THREE.Vector3(radius*.8,radius*.4,radius*2)));camera.lookAt(center);camera.fov=50;projection();controls.target.copy(center);controls.update();}

function photoView(index){
  const view=model.cameras[index];if(!view)return;
  activeView=view;
  $('#source-photo').src=view.photo;
  const matrix=new THREE.Matrix4();matrix.set(...view.world_matrix.flat());
  camera.position.setFromMatrixPosition(matrix);camera.quaternion.setFromRotationMatrix(matrix);
  camera.up.setFromMatrixColumn(matrix,1);
  camera.fov=THREE.MathUtils.radToDeg(2*Math.atan(view.height/(2*view.K[1][1])));
  projection();
  const direction=new THREE.Vector3(0,0,-1).applyQuaternion(camera.quaternion);
  const center=new THREE.Box3().setFromObject(object).getCenter(new THREE.Vector3());
  controls.target.copy(camera.position.clone().addScaledVector(direction,camera.position.distanceTo(center)));
  controls.update();
}

function display(){const choice=$('#display').value;object?.traverse(child=>{if(child.isMesh)child.material=choice==='solid'?solid:choice==='wire'?wire:child.userData.photoMaterial;});}

function disposeMesh(root){
  const textures=new Set(),materials=new Set();
  root.traverse(child=>{if(!child.isMesh)return;child.geometry.dispose();const source=child.userData.photoMaterial||child.material;for(const m of (Array.isArray(source)?source:[source])){if(m===solid||m===wire)continue;materials.add(m);if(m.map)textures.add(m.map);}});
  textures.forEach(t=>t.dispose());materials.forEach(m=>m.dispose());
}

async function select(index,chooseDefault=false){
  const request=++serial;model=manifest.models[index];$('#load-status').textContent='Loading measured mesh and photo atlas…';
  $('#geometry option[value="exposure"]').disabled=!model.has_exposure_mesh;
  if(chooseDefault)$('#geometry').value=model.has_exposure_mesh?'exposure':'native';
  if($('#geometry').value==='exposure'&&!model.has_exposure_mesh)$('#geometry').value='native';
  const choice=$('#geometry').value;
  const basename=choice==='exposure'?'exposure-supported':choice==='supported'&&model.has_supported_mesh?'supported':model.mesh_basename||'textured';
  $('#verdict').textContent=model.verdict;$('#report').href=model.path+'report.json';$('#download').href=model.path+'surface-download.zip';
  $('#projection').src=model.path+(['supported','exposure-supported'].includes(basename)?basename+'-projections.jpg':'surface-projections.jpg');
  const materials=await new MTLLoader().setPath(model.path).loadAsync(basename+'.mtl');materials.preload();
  const next=await new OBJLoader().setMaterials(materials).setPath(model.path).loadAsync(basename+'.obj');
  if(request!==serial){disposeMesh(next);return;}
  if(object){scene.remove(object);disposeMesh(object);}object=next;
  let triangles=0;object.traverse(child=>{if(child.isMesh){const photo=m=>{if(m.map){m.map.flipY=basename!=='textured';m.map.colorSpace=THREE.SRGBColorSpace;m.map.needsUpdate=true;}return new THREE.MeshBasicMaterial({map:m.map,color:m.map?0xffffff:m.color,side:THREE.DoubleSide});};child.material=Array.isArray(child.material)?child.material.map(photo):photo(child.material);child.userData.photoMaterial=child.material;triangles+=(child.geometry.index?.count||child.geometry.attributes.position.count)/3;}});
  scene.add(object);fit();display();
  $('#camera').replaceChildren(...model.cameras.map((v,i)=>new Option(v.name.split('__').pop().replace(/_/g,' '),i)));
  photoView(0);
  $('#mesh-stats').textContent=`${model.report.registered_images} recovered cameras · ${model.report.outputs.dense.vertex.toLocaleString()} fused depth points · ${Math.round(triangles).toLocaleString()} triangles`;
  $('#load-status').textContent='COMPUTED SURFACE · EXPERIMENTAL'+(choice==='exposure'?' · SCAN-GROUP FILTERED FACETS':'');
}

$('#experiment').addEventListener('change',e=>select(Number(e.target.value),true).catch(error));
$('#geometry').addEventListener('change',()=>select(Number($('#experiment').value)).catch(error));
$('#camera').addEventListener('change',e=>photoView(Number(e.target.value)));
$('#display').addEventListener('change',display);$('#fit').addEventListener('click',fit);
function error(e){console.error(e);$('#load-status').textContent='Artifact load failed: '+e.message;}
try{
  const response=await fetch('assets/repair/manifest.json',{cache:'no-store'});if(!response.ok)throw new Error('Manifest HTTP '+response.status);manifest=await response.json();
  $('#experiment').replaceChildren(...manifest.models.map((m,i)=>new Option(m.label,i)));
  $('#sensitivity').innerHTML=manifest.focal_sensitivity.map(r=>`<tr><td>${r.focal_refinement?'unconstrained':r.focal_prior}</td><td>${r.registered}</td><td>${r.points}</td></tr>`).join('');
  resize();await select(0,true);
}catch(e){error(e);}
