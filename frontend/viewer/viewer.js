import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';

const data=JSON.parse(document.getElementById('scene-data').textContent);
const host=document.getElementById('viewport'), status=document.getElementById('scene-status');
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
let visible=true, loaded=false, model, selected=null, expanded=false, hover=null;
const scene=new THREE.Scene();
scene.background=new THREE.Color('#111b23');
const camera=new THREE.PerspectiveCamera(36,1,.1,100);
const home=new THREE.Vector3(7,5.2,7.7), homeTarget=new THREE.Vector3(0,1.15,0);
camera.position.copy(home);
const dest=home.clone(), target=homeTarget.clone();
let tween=false;
let renderer;
try {
 renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'low-power'});
 renderer.setPixelRatio(Math.min(devicePixelRatio,1.75));
 renderer.outputColorSpace=THREE.SRGBColorSpace;
 renderer.toneMapping=THREE.ACESFilmicToneMapping;
 renderer.toneMappingExposure=1.65;
 renderer.shadowMap.enabled=true;
 renderer.shadowMap.type=THREE.PCFSoftShadowMap;
 host.prepend(renderer.domElement);
 renderer.domElement.setAttribute('aria-label','Interactive illustrative machining cell. Use the component buttons to inspect readings.');
} catch(error) {
 status.textContent='3D unavailable on this device. Use the component buttons or switch to 2D.';
 host.classList.add('unavailable');
}
const controls=renderer ? new OrbitControls(camera,renderer.domElement):null;
if(controls){
 controls.target.copy(homeTarget); controls.enableDamping=true;controls.dampingFactor=.08;
 controls.minDistance=3;controls.maxDistance=15;controls.maxPolarAngle=Math.PI*.48;
 controls.enablePan=false;controls.addEventListener('start',()=>{tween=false;});
}
scene.add(new THREE.HemisphereLight(0xeaf5ff,0x24313a,3));
const key=new THREE.DirectionalLight(0xffe4c8,4);key.position.set(3,8,5);key.castShadow=true;
key.shadow.mapSize.set(1024,1024);key.shadow.camera.left=-5;key.shadow.camera.right=5;
key.shadow.camera.top=5;key.shadow.camera.bottom=-5;key.shadow.normalBias=.025;scene.add(key);
const rim=new THREE.DirectionalLight(0x91cddd,3);rim.position.set(-4,4,-4);scene.add(rim);
const ground=new THREE.Mesh(new THREE.PlaneGeometry(200,200),new THREE.MeshStandardMaterial({color:0x111b23,roughness:.95}));
ground.rotation.x=-Math.PI/2;ground.position.y=-.1;ground.receiveShadow=true;scene.add(ground);
const grid=new THREE.GridHelper(18,36,0x344550,0x22313b);grid.position.y=-.085;scene.add(grid);
const groups={};const ray=new THREE.Raycaster(),pointer=new THREE.Vector2();
const zoneNames={drive:'Drive / spindle',process_chamber:'Process chamber',tool_head:'Tool head'};
const detail=document.getElementById('details');
const globalDetail=document.getElementById('assessment-detail');
if(globalDetail){
 const a=data.assessment;
 globalDetail.textContent=`${a.decision||'Not assessed'} · Record ${a.record_id}\n${a.policy}\nExplanation: ${a.explanation_mode}\n`+(a.score==null?'':`Score ${Number(a.score).toFixed(4)} / threshold ${a.threshold}`);
}
function showZone(id){
 selected=id;
 document.querySelectorAll('[data-zone]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.zone===id)));
 document.getElementById('detail-title').textContent=zoneNames[id]||'Machine overview';
 detail.replaceChildren();
 const zone=data.zones.find(z=>z.id===id);
 if(zone)for(const value of zone.observations){const el=document.createElement('div');el.className='reading';el.textContent=value;detail.appendChild(el);}
 else {const p=document.createElement('p');p.textContent='Select an assembly to inspect the recorded measurements. Drag to orbit. Scroll to zoom.';detail.appendChild(p);}
 const inspections={drive:'Review speed and torque readings; a technician must confirm the component before any parts request.',process_chamber:'Review both temperature readings and verify sensor quality before planning an intervention.',tool_head:'Review recorded tool wear and request an inspection before deciding on replacement.'};
 document.getElementById('detail-note').textContent=zone?`Inspection context: ${inspections[id]} These readings do not diagnose this component. Use the review form below after assessment.`:'Select a part to inspect its recorded data and inspection context. Assessment is machine-wide, not a component diagnosis.';
 if(model){
   if(id&&groups[id]){
    const box=new THREE.Box3().setFromObject(groups[id]);box.getCenter(target);
    dest.copy(target).add(new THREE.Vector3(3.8,2.7,4.4));
   }else{dest.copy(home);target.copy(homeTarget);}
   tween=true;
   if(reduced.matches){camera.position.copy(dest);controls?.target.copy(target);tween=false;}
   model.traverse(o=>{if(o.isMesh){const group=owner(o);o.material.emissive.set(id&&group===id?0x381b09:0x000000);}});
 }
}
function owner(o){while(o&&o!==model){if(zoneNames[o.name])return o.name;o=o.parent;}return null;}
document.querySelectorAll('[data-zone]').forEach(b=>b.addEventListener('click',()=>showZone(b.dataset.zone)));
document.getElementById('reset-view').addEventListener('click',()=>showZone(null));
document.getElementById('explode').addEventListener('click',()=>{
 expanded=!expanded;document.getElementById('explode').setAttribute('aria-pressed',String(expanded));
 document.getElementById('explode').textContent=expanded?'Assemble':'Explode view';
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')showZone(null);});
let startX=0,startY=0;
if(renderer){
 renderer.domElement.addEventListener('pointerdown',e=>{startX=e.clientX;startY=e.clientY;});
 renderer.domElement.addEventListener('pointermove',e=>{
  if(!model||e.buttons)return;
  const r=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);
  ray.setFromCamera(pointer,camera);hover=ray.intersectObject(model,true).map(h=>owner(h.object)).find(Boolean)||null;
  renderer.domElement.style.cursor=hover?'pointer':'grab';
  document.getElementById('hover-label').textContent=hover?zoneNames[hover]:'Drag to orbit · scroll to zoom';
 });
 renderer.domElement.addEventListener('pointerup',e=>{if(Math.hypot(e.clientX-startX,e.clientY-startY)<5&&hover)showZone(hover);});
 const bytes=Uint8Array.from(atob(data.asset),c=>c.charCodeAt(0));
 new GLTFLoader().parse(bytes.buffer,'',gltf=>{
  model=gltf.scene;
  model.traverse(o=>{if(zoneNames[o.name])groups[o.name]=o;if(o.isMesh){o.castShadow=true;o.receiveShadow=true;o.material=o.material.clone();}});
  scene.add(model);loaded=true;status.textContent='MODEL READY';document.body.classList.add('ready');
 },()=>{status.textContent='Model could not load. Component readings remain available.';});
 const resize=()=>{const w=host.clientWidth,h=host.clientHeight;camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h,false);};
 new ResizeObserver(resize).observe(host);resize();
 new IntersectionObserver(es=>{visible=es[0].isIntersecting;}).observe(host);
 const clock=new THREE.Clock();
 function frame(){
  requestAnimationFrame(frame);const dt=Math.min(clock.getDelta(),.05);
  if(!visible||document.hidden)return;
  const k=reduced.matches?1:1-Math.exp(-dt*7);
  if(tween){camera.position.lerp(dest,k);controls.target.lerp(target,k);if(camera.position.distanceTo(dest)<.005)tween=false;}
  for(const [id,g]of Object.entries(groups)){
   const x=expanded?(id==='drive'?-.7:id==='tool_head'?.7:0):0;
   const y=expanded&&id==='process_chamber'?.6:0;
   g.position.x=THREE.MathUtils.lerp(g.position.x,x,k);g.position.y=THREE.MathUtils.lerp(g.position.y,y,k);
  }
  controls.update();renderer.render(scene,camera);
 }
 frame();
}
showZone(null);
