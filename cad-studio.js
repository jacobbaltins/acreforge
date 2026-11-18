/* AcreForge CAD Studio core: conceptual 2D drafting engine. Units: inches, y up. DXF export only; no DWG. */
(function(){
"use strict";
const KEY="acreforge-cad-v1";
const COLORS={red:1,yellow:2,green:3,cyan:4,blue:5,magenta:6,white:7};
const HEX={1:"#ff4040",2:"#ffe040",3:"#40e070",4:"#40e0e0",5:"#5080ff",6:"#e060e0",7:"#e8e8e8"};
const LTYPES=["CONTINUOUS","DASHED","CENTER","HIDDEN"];
const LIB={sofa:[84,36],bed:[60,80],desk:[60,30],table:[48,30],cabinet:[36,24],counter:[96,25],range:[30,26],fridge:[36,30],sink:[24,20],toilet:[20,28],tub:[60,30],stair:[36,120]};
function defaults(){
  const L={};
  [["0",7],["A-WALL",7],["A-DOOR",3],["A-GLAZ",4],["A-ANNO",2],["A-DIMS",1],["A-ROOM",6],["A-FURN",5],["E-POWR",1],["P-PLMB",5],["M-HVAC",3]].forEach(([n,c])=>L[n]={color:c,ltype:"CONTINUOUS",on:true,lock:false});
  return {layers:L,ents:[],cur:"0",nid:1,ceil:96,wallTh:6,grid:6,hist:[],redo:[],units:"in",title:"Untitled",sheet:"A",scale:"1/4"};
}
let doc=defaults();
let log=[];
const note=m=>{log.push(m);if(log.length>200)log.shift();};
/* ---------- health / recovery state (NORMAL -> WARNING -> ERROR -> RECOVERY -> NORMAL) ---------- */
const BKEY=KEY+"-backup",SKEY=KEY+"-session";
const health={state:"NORMAL",sev:"INFO",msg:"",crashed:false,recovered:"",storageFull:false,devLog:[]};
const SEV=["INFO","WARNING","ERROR","CRITICAL","FATAL"];
const HSTATE={INFO:"NORMAL",WARNING:"WARNING",ERROR:"ERROR",CRITICAL:"ERROR",FATAL:"ERROR"};
function setHealth(sev,msg){health.sev=sev;health.state=HSTATE[sev]||"NORMAL";health.msg=msg||"";if(sev!=="INFO")note(msg);return msg}
function recoverTo(msg){health.state="RECOVERY";health.msg=msg;note(msg);return msg}
function clearHealth(){health.state="NORMAL";health.sev="INFO";health.msg=""}
const devlog=m=>{health.devLog.push(m);if(health.devLog.length>50)health.devLog.shift()};
function backupNow(){try{localStorage.setItem(BKEY,JSON.stringify({ts:Date.now(),doc:doc}));return true}catch(e){return false}}
function isQuota(e){return !!e&&(e.name==="QuotaExceededError"||e.name==="NS_ERROR_DOM_QUOTA_REACHED"||e.code===22||e.code===1014)}
let lastBackup=0;
function save(){
  let s;try{s=JSON.stringify(doc)}catch(e){setHealth("ERROR","Could not save right now. Your drawing is still open; try again or download a backup.");return false}
  try{localStorage.setItem(KEY,s);health.storageFull=false;if(health.state!=="NORMAL"&&health.state!=="RECOVERY"&&health.msg.indexOf("save")>=0)clearHealth();
    if(Date.now()-lastBackup>30000){lastBackup=Date.now();backupNow()}return true}
  catch(e){if(isQuota(e)){health.storageFull=true;setHealth("CRITICAL","Browser storage is full. Exporting backup recommended. Your drawing is still open and nothing was lost.")}
    else{devlog("save_failure");setHealth("WARNING","Could not save automatically. Your changes are still safe on screen. Will retry.")}return false}
}
function exportBackup(){const s=JSON.stringify({app:"AcreForge CAD",saved:new Date().toISOString(),doc:doc});if(typeof Blob!=="undefined"&&typeof document!=="undefined"){const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([s],{type:"application/json"}));a.download="acreforge-cad-backup.json";document.body.appendChild(a);a.click();a.remove()}if(health.storageFull)recoverTo("Backup downloaded. Free some browser storage, then keep drawing.");return s}
function load(){
  let raw=null;try{raw=localStorage.getItem(KEY)}catch(e){}
  if(raw){let j=null;try{j=JSON.parse(raw)}catch(e){}
    if(j&&j.layers&&j.ents){doc=Object.assign(defaults(),j)}
    else{try{localStorage.setItem(KEY+"-corrupt",raw)}catch(e){}
      let b=null;try{b=JSON.parse(localStorage.getItem(BKEY))}catch(e){}
      if(b&&b.doc&&b.doc.layers&&b.doc.ents){doc=Object.assign(defaults(),b.doc);const m=Math.max(0,Math.round((Date.now()-(b.ts||Date.now()))/60000));health.recovered="Recovered from backup created "+m+(m===1?" minute":" minutes")+" ago.";recoverTo("Latest project file appears damaged. "+health.recovered)}
      else setHealth("ERROR","Saved drawing could not be read. The damaged copy was kept; starting a new drawing.")}}
  try{const s=JSON.parse(localStorage.getItem(SKEY));if(s&&s.open){health.crashed=true}}catch(e){}
  try{localStorage.setItem(SKEY,JSON.stringify({open:true,ts:Date.now()}))}catch(e){}
}
function closeSession(){try{localStorage.setItem(SKEY,JSON.stringify({open:false,ts:Date.now()}))}catch(e){}}
function restoreSession(){health.crashed=false;clearHealth();return true}
function discardSession(){if(doc.ents.length)backupNow();lastBackup=Date.now();health.crashed=false;const d=defaults();doc.layers=d.layers;doc.ents=[];doc.cur="0";doc.nid=1;doc.hist=[];doc.redo=[];save();return true}
if(typeof window!=="undefined"){window.addEventListener("pagehide",closeSession);window.addEventListener("beforeunload",closeSession)}
load();
const snapshot=()=>{doc.hist.push(JSON.stringify({layers:doc.layers,ents:doc.ents,cur:doc.cur,nid:doc.nid}));if(doc.hist.length>100)doc.hist.shift();doc.redo=[]};
function restore(s){const o=JSON.parse(s);doc.layers=o.layers;doc.ents=o.ents;doc.cur=o.cur;doc.nid=o.nid}
function undo(){if(!doc.hist.length)return false;doc.redo.push(JSON.stringify({layers:doc.layers,ents:doc.ents,cur:doc.cur,nid:doc.nid}));restore(doc.hist.pop());save();return true}
function redo(){if(!doc.redo.length)return false;doc.hist.push(JSON.stringify({layers:doc.layers,ents:doc.ents,cur:doc.cur,nid:doc.nid}));restore(doc.redo.pop());save();return true}
function add(e){snapshot();e.id=doc.nid++;e.layer=e.layer||doc.cur;doc.ents.push(e);save();return e}
const byId=id=>doc.ents.find(e=>e.id===id);
/* ---------- parsing ---------- */
const UNITS={in:{f:1,n:"inches",s:'"',d:3},mm:{f:1/25.4,n:"millimeters",s:" mm",d:1},cm:{f:1/2.54,n:"centimeters",s:" cm",d:2},m:{f:1/0.0254,n:"meters",s:" m",d:3}};
const unit=()=>UNITS[doc.units]||UNITS.in;
function setUnits(u){if(!UNITS[u])return false;doc.units=u;save();return true}
function parseLen(s){
  s=String(s).trim();let m;
  if(/'/.test(s))return NaN;
  if(m=s.match(/^(-?\d*\.?\d+)\s*(mm|cm|m|in|")?$/i)){const u=(m[2]||"").toLowerCase();const f=u==='"'||u==="in"?1:u?UNITS[u].f:unit().f;return +m[1]*f}
  return NaN;
}
function parsePoint(s,last){
  s=String(s).trim();let m;
  if(m=s.match(/^@(.+)<(.+)$/)){const d=parseLen(m[1]),a=parseFloat(m[2]);if(isNaN(d)||isNaN(a)||!last)return null;return [last[0]+d*Math.cos(a*Math.PI/180),last[1]+d*Math.sin(a*Math.PI/180)]}
  if(m=s.match(/^(@?)([^,]+),([^,]+)$/)){const x=parseLen(m[2]),y=parseLen(m[3]);if(isNaN(x)||isNaN(y))return null;if(m[1]){if(!last)return null;return [last[0]+x,last[1]+y]}return [x,y]}
  if(m=s.match(/^(.+)<(.+)$/)){const d=parseLen(m[1]),a=parseFloat(m[2]);if(isNaN(d)||isNaN(a))return null;return [d*Math.cos(a*Math.PI/180),d*Math.sin(a*Math.PI/180)]}
  return null;
}
const fmtIn=v=>{const u=unit(),x=v/u.f;let t=(+x.toFixed(u.d)).toString();if(t==="-0")t="0";return t+u.s};
const fmtArea=v=>{const u=unit(),x=v/(u.f*u.f);return (+x.toFixed(u.d>2?2:u.d)).toString()+(doc.units==="in"?" sq in":doc.units==="mm"?" sq mm":doc.units==="cm"?" sq cm":" sq m")};
const gcd=(a,b)=>b?gcd(b,a%b):a;
const dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
/* ---------- geometry ---------- */
function segs(e){
  if(e.t==="line")return [[e.a,e.b]];
  if(e.t==="wall")return [[e.a,e.b]];
  if(e.t==="pline"){const o=[];for(let i=0;i<e.pts.length-1;i++)o.push([e.pts[i],e.pts[i+1]]);if(e.closed&&e.pts.length>2)o.push([e.pts[e.pts.length-1],e.pts[0]]);return o}
  if(e.t==="dim")return [[e.a,e.b]];
  return [];
}
function segInt(p,q,r,s){
  const d=(q[0]-p[0])*(s[1]-r[1])-(q[1]-p[1])*(s[0]-r[0]);if(Math.abs(d)<1e-9)return null;
  const t=((r[0]-p[0])*(s[1]-r[1])-(r[1]-p[1])*(s[0]-r[0]))/d,u=((r[0]-p[0])*(q[1]-p[1])-(r[1]-p[1])*(q[0]-p[0]))/d;
  if(t<-1e-9||t>1+1e-9||u<-1e-9||u>1+1e-9)return null;return [p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])];
}
function lineInt(p,q,r,s){const d=(q[0]-p[0])*(s[1]-r[1])-(q[1]-p[1])*(s[0]-r[0]);if(Math.abs(d)<1e-9)return null;const t=((r[0]-p[0])*(s[1]-r[1])-(r[1]-p[1])*(s[0]-r[0]))/d;return {pt:[p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])],t}}
function area(pts){let a=0;for(let i=0;i<pts.length;i++){const p=pts[i],q=pts[(i+1)%pts.length];a+=p[0]*q[1]-q[0]*p[1]}return a/2}
function visible(e){const l=doc.layers[e.layer];return !l||l.on}
function locked(e){const l=doc.layers[e.layer];return l&&l.lock}
function ptSegDist(p,a,b){const dx=b[0]-a[0],dy=b[1]-a[1],L=dx*dx+dy*dy;let t=L?((p[0]-a[0])*dx+(p[1]-a[1])*dy)/L:0;t=Math.max(0,Math.min(1,t));return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)}
const rad=d=>d*Math.PI/180,deg=r=>r*180/Math.PI,norm=a=>((a%360)+360)%360;
function onArc(e,p){const a=norm(deg(Math.atan2(p[1]-e.c[1],p[0]-e.c[0]))),s=norm(e.a0),n=norm(e.a1);return s<=n?(a>=s&&a<=n):(a>=s||a<=n)}
const arcPt=(e,a)=>[e.c[0]+e.r*Math.cos(rad(a)),e.c[1]+e.r*Math.sin(rad(a))];
function entDist(e,p){
  if(e.t==="arc")return onArc(e,p)?Math.abs(dist(p,e.c)-e.r):Math.min(dist(p,arcPt(e,e.a0)),dist(p,arcPt(e,e.a1)));
  if(e.t==="hatch"){let m=1e9;for(let i=0;i<e.pts.length;i++)m=Math.min(m,ptSegDist(p,e.pts[i],e.pts[(i+1)%e.pts.length]));return m}
  if(e.t==="circle")return Math.abs(dist(p,e.c)-e.r);
  if(e.t==="text"||e.t==="outlet"||e.t==="fixture"){const q=e.p;return dist(p,q)}
  if(e.t==="door"||e.t==="window"){const g=openGeom(e);return g?ptSegDist(p,g[0],g[1]):1e9}
  let m=1e9;segs(e).forEach(s=>{m=Math.min(m,ptSegDist(p,s[0],s[1]))});return m;
}
function pick(p,tol){let best=null,bd=tol;for(let i=doc.ents.length-1;i>=0;i--){const e=doc.ents[i];if(!visible(e))continue;const d=entDist(e,p);if(d<bd){bd=d;best=e}}return best}
function openGeom(e){const w=byId(e.wall);if(!w)return null;const L=dist(w.a,w.b);if(!L)return null;const ux=(w.b[0]-w.a[0])/L,uy=(w.b[1]-w.a[1])/L;const a=[w.a[0]+ux*e.pos,w.a[1]+uy*e.pos],b=[a[0]+ux*e.w,a[1]+uy*e.w];return [a,b,[ux,uy],w]}
function moveEnt(e,dx,dy){
  const mv=p=>[p[0]+dx,p[1]+dy];
  if(e.a)e.a=mv(e.a);if(e.b)e.b=mv(e.b);if(e.pts)e.pts=e.pts.map(mv);if(e.c)e.c=mv(e.c);if(e.p)e.p=mv(e.p);
}
const rotP=(p,b,a)=>{const c=Math.cos(rad(a)),s=Math.sin(rad(a)),x=p[0]-b[0],y=p[1]-b[1];return [b[0]+x*c-y*s,b[1]+x*s+y*c]};
function rotEnt(e,b,a){const r=p=>rotP(p,b,a);if(e.a)e.a=r(e.a);if(e.b)e.b=r(e.b);if(e.pts)e.pts=e.pts.map(r);if(e.c)e.c=r(e.c);if(e.p)e.p=r(e.p);if(e.t==="arc"){e.a0=norm(e.a0+a);e.a1=norm(e.a1+a)}}
function mirP(p,a,b){const dx=b[0]-a[0],dy=b[1]-a[1],L=dx*dx+dy*dy,t=((p[0]-a[0])*dx+(p[1]-a[1])*dy)/L,fx=a[0]+t*dx,fy=a[1]+t*dy;return [2*fx-p[0],2*fy-p[1]]}
function mirEnt(e,a,b){const m=p=>mirP(p,a,b);if(e.a)e.a=m(e.a);if(e.b)e.b=m(e.b);if(e.pts)e.pts=e.pts.map(m);if(e.c)e.c=m(e.c);if(e.p)e.p=m(e.p);
  if(e.t==="arc"){const th=deg(Math.atan2(b[1]-a[1],b[0]-a[0])),s=norm(2*th-e.a1),n=norm(2*th-e.a0);e.a0=s;e.a1=n}}
function offsetEnt(e,d,side){
  const n=JSON.parse(JSON.stringify(e));delete n.id;
  if(e.t==="line"||e.t==="wall"){const L=dist(e.a,e.b);if(!L)return null;const nx=-(e.b[1]-e.a[1])/L,ny=(e.b[0]-e.a[0])/L;const sg=((side[0]-e.a[0])*nx+(side[1]-e.a[1])*ny)>=0?1:-1;n.a=[e.a[0]+sg*nx*d,e.a[1]+sg*ny*d];n.b=[e.b[0]+sg*nx*d,e.b[1]+sg*ny*d];return n}
  if(e.t==="circle"||e.t==="arc"){const r=dist(side,e.c)>e.r?e.r+d:e.r-d;if(r<=0.01)return null;n.r=r;return n}
  return null;
}
function inter(p,q,r,s){const d=(q[0]-p[0])*(s[1]-r[1])-(q[1]-p[1])*(s[0]-r[0]);if(Math.abs(d)<1e-9)return null;const t=((r[0]-p[0])*(s[1]-r[1])-(r[1]-p[1])*(s[0]-r[0]))/d,u=((r[0]-p[0])*(q[1]-p[1])-(r[1]-p[1])*(q[0]-p[0]))/d;return {pt:[p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])],t,u}}
function nearLine(p,tol,skip){let b=null,bd=tol;doc.ents.forEach(e=>{if(e.t!=="line"||!visible(e)||locked(e)||e===skip)return;const d=ptSegDist(p,e.a,e.b);if(d<bd){bd=d;b=e}});return b}
function trimAt(p){
  const e=nearLine(p,24);if(!e)return "No unlocked LINE near that point";
  const L=dist(e.a,e.b);if(!L)return "Zero-length line";
  const ts=[];doc.ents.forEach(o=>{if(o===e||!visible(o))return;segs(o).forEach(s=>{const x=inter(e.a,e.b,s[0],s[1]);if(x&&x.u>=-1e-9&&x.u<=1+1e-9&&x.t>1e-6&&x.t<1-1e-6)ts.push(x.t)})});
  if(!ts.length)return "No cutting edge crosses this line";
  const dx=e.b[0]-e.a[0],dy=e.b[1]-e.a[1];const tp=Math.max(0,Math.min(1,((p[0]-e.a[0])*dx+(p[1]-e.a[1])*dy)/(L*L)));
  const lo=Math.max(...ts.filter(t=>t<tp),-1),hi=Math.min(...ts.filter(t=>t>=tp),2);
  const at=t=>[e.a[0]+dx*t,e.a[1]+dy*t];snapshot();
  if(lo<0){e.a=at(hi)}else if(hi>1){e.b=at(lo)}else{const n=JSON.parse(JSON.stringify(e));n.id=doc.nid++;n.a=at(hi);e.b=at(lo);doc.ents.push(n)}
  save();return "Trimmed";
}
function extendAt(p){
  const e=nearLine(p,24);if(!e)return "No unlocked LINE near that point";
  const endB=dist(p,e.b)<=dist(p,e.a);const O=endB?e.a:e.b,E=endB?e.b:e.a;let best=null;
  doc.ents.forEach(o=>{if(o===e||!visible(o))return;segs(o).forEach(s=>{const x=inter(O,E,s[0],s[1]);if(x&&x.u>=-1e-9&&x.u<=1+1e-9&&x.t>1+1e-6&&(!best||x.t<best.t))best=x})});
  if(!best)return "No boundary edge ahead of that line end";
  snapshot();if(endB)e.b=best.pt;else e.a=best.pt;save();return "Extended";
}
function filletAt(p1,p2,r){
  const l1=nearLine(p1,24),l2=nearLine(p2,24,l1);if(!l1||!l2||l1===l2)return "Pick two different unlocked LINEs";
  const x=inter(l1.a,l1.b,l2.a,l2.b);if(!x)return "Lines are parallel";
  const X=x.pt,dir=(l,p)=>{const L=dist(l.a,l.b),d=((p[0]-X[0])*(l.b[0]-l.a[0])+(p[1]-X[1])*(l.b[1]-l.a[1]))/L;if(Math.abs(d)<1e-9)return null;const s=d>0?1:-1;return [s*(l.b[0]-l.a[0])/L,s*(l.b[1]-l.a[1])/L]};
  const u1=dir(l1,p1),u2=dir(l2,p2);if(!u1||!u2)return "Click each line away from the corner";
  const cs=u1[0]*u2[0]+u1[1]*u2[1],phi=Math.acos(Math.max(-1,Math.min(1,cs)));if(phi<1e-3||phi>Math.PI-1e-3)return "Lines are collinear";
  const pr=(l,u,q)=>[(q[0]-X[0])*u[0]+(q[1]-X[1])*u[1]];
  const far=(l,u)=>Math.max((l.a[0]-X[0])*u[0]+(l.a[1]-X[1])*u[1],(l.b[0]-X[0])*u[0]+(l.b[1]-X[1])*u[1]);
  const t=r>0?r/Math.tan(phi/2):0;if(far(l1,u1)<=t+1e-6||far(l2,u2)<=t+1e-6)return r>0?"Radius too large for these lines":"Lines do not extend away from the corner";
  const T1=[X[0]+u1[0]*t,X[1]+u1[1]*t],T2=[X[0]+u2[0]*t,X[1]+u2[1]*t];
  const setEnd=(l,u,T)=>{const da=(l.a[0]-X[0])*u[0]+(l.a[1]-X[1])*u[1],db=(l.b[0]-X[0])*u[0]+(l.b[1]-X[1])*u[1];if(da<db)l.a=T;else l.b=T};
  snapshot();setEnd(l1,u1,T1);setEnd(l2,u2,T2);
  if(r>0){const bx=u1[0]+u2[0],by=u1[1]+u2[1],bl=Math.hypot(bx,by),k=r/Math.sin(phi/2);const c=[X[0]+bx/bl*k,X[1]+by/bl*k];
    const s1=deg(Math.atan2(T1[1]-c[1],T1[0]-c[0])),s2=deg(Math.atan2(T2[1]-c[1],T2[0]-c[0]));const dl=((s2-s1+540)%360)-180;
    doc.ents.push({t:"arc",c,r,a0:norm(dl>0?s1:s2),a1:norm(dl>0?s2:s1),id:doc.nid++,layer:l1.layer})}
  save();return r>0?"Filleted (radius "+fmtIn(r)+")":"Corner joined";
}
function hatchSegs(e,forExport){
  const pts=e.pts,pat=e.pat||"ANSI31";if(pat==="SOLID"&&!forExport)return [];
  const angs=pat==="CROSS"?[45,135]:[45];let sp=pat==="SOLID"?1:(e.sp||6);const out=[];
  angs.forEach(ang=>{const c=Math.cos(rad(-ang)),s=Math.sin(rad(-ang)),q=pts.map(p=>[p[0]*c-p[1]*s,p[0]*s+p[1]*c]),ys=q.map(p=>p[1]),y0=Math.min(...ys),y1=Math.max(...ys);
    const st=Math.max(sp,(y1-y0)/1500),cb=Math.cos(rad(ang)),sb=Math.sin(rad(ang)),back=p=>[p[0]*cb-p[1]*sb,p[0]*sb+p[1]*cb];
    for(let y=y0+st/2;y<y1;y+=st){const xs=[];for(let i=0;i<q.length;i++){const a=q[i],b=q[(i+1)%q.length];if((a[1]<=y&&b[1]>y)||(b[1]<=y&&a[1]>y))xs.push(a[0]+(y-a[1])/(b[1]-a[1])*(b[0]-a[0]))}
      xs.sort((m,n)=>m-n);for(let i=0;i+1<xs.length;i+=2)out.push([back([xs[i],y]),back([xs[i+1],y])])}});
  return out;
}
/* ---------- snaps ---------- */
function snapPoints(){
  const o=[];
  doc.ents.forEach(e=>{if(!visible(e))return;
    segs(e).forEach(s=>{o.push({p:s[0],k:"end"},{p:s[1],k:"end"},{p:[(s[0][0]+s[1][0])/2,(s[0][1]+s[1][1])/2],k:"mid"})});
    if(e.t==="wall"){const th=e.th/2;/* centerline snap is endpoint/mid above */}
    if(e.t==="circle")o.push({p:e.c,k:"cen"});
    if(e.t==="arc")o.push({p:e.c,k:"cen"},{p:arcPt(e,e.a0),k:"end"},{p:arcPt(e,e.a1),k:"end"});
  });
  const S=[];doc.ents.forEach(e=>{if(visible(e))segs(e).forEach(s=>S.push(s))});
  for(let i=0;i<S.length;i++)for(let j=i+1;j<S.length;j++){const x=segInt(S[i][0],S[i][1],S[j][0],S[j][1]);if(x)o.push({p:x,k:"int"})}
  return o;
}
function osnap(p,tol,opts){
  opts=opts||{};let best=null,bd=tol;const rank={end:0,int:1,mid:2,cen:3};
  if(opts.osnap!==false){snapPoints().forEach(s=>{const d=dist(s.p,p);if(d<bd-1e-9||(best&&Math.abs(d-bd)<1e-9&&rank[s.k]<rank[best.k])){bd=d;best=s}})}
  if(best)return {p:best.p,k:best.k};
  if(opts.perp&&opts.from){let b2=null,bd2=tol;doc.ents.forEach(e=>{if(!visible(e))return;segs(e).forEach(s=>{const dx=s[1][0]-s[0][0],dy=s[1][1]-s[0][1],L=dx*dx+dy*dy;if(!L)return;const t=((opts.from[0]-s[0][0])*dx+(opts.from[1]-s[0][1])*dy)/L;if(t<0||t>1)return;const q=[s[0][0]+t*dx,s[0][1]+t*dy];const d=dist(q,p);if(d<bd2){bd2=d;b2={p:q,k:"per"}}})});if(b2)return b2}
  if(opts.grid){const g=doc.grid;return {p:[Math.round(p[0]/g)*g,Math.round(p[1]/g)*g],k:"grid"}}
  return {p:p,k:null};
}
function constrain(from,p,mode){
  if(!from)return p;const dx=p[0]-from[0],dy=p[1]-from[1];
  if(mode==="ortho")return Math.abs(dx)>=Math.abs(dy)?[p[0],from[1]]:[from[0],p[1]];
  if(mode==="polar"){const d=Math.hypot(dx,dy),a=Math.round(Math.atan2(dy,dx)/(Math.PI/4))*(Math.PI/4);return [from[0]+d*Math.cos(a),from[1]+d*Math.sin(a)]}
  return p;
}
/* ---------- selection ---------- */
function bbox(e){const P=[];if(e.a)P.push(e.a);if(e.b)P.push(e.b);if(e.pts)P.push(...e.pts);if(e.p)P.push(e.p);if(e.c){P.push([e.c[0]-e.r,e.c[1]-e.r],[e.c[0]+e.r,e.c[1]+e.r])}
  if(!P.length){const g=openGeom(e);if(g)P.push(g[0],g[1])}
  if(!P.length)return null;const xs=P.map(p=>p[0]),ys=P.map(p=>p[1]);return [Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)]}
function selectBox(a,b,crossing){
  const x0=Math.min(a[0],b[0]),x1=Math.max(a[0],b[0]),y0=Math.min(a[1],b[1]),y1=Math.max(a[1],b[1]);
  return doc.ents.filter(e=>{if(!visible(e)||locked(e))return false;const bb=bbox(e);if(!bb)return false;
    if(crossing)return !(bb[2]<x0||bb[0]>x1||bb[3]<y0||bb[1]>y1);
    return bb[0]>=x0&&bb[2]<=x1&&bb[1]>=y0&&bb[3]<=y1}).map(e=>e.id);
}
window.AcreCADCore={KEY,BKEY,SKEY,health,SEV,setHealth,recoverTo,clearHealth,devlog,backupNow,exportBackup,closeSession,restoreSession,discardSession,COLORS,HEX,LTYPES,LIB,get doc(){return doc},set doc(v){doc=v},get log(){return log},note,save,load,defaults,snapshot,undo,redo,add,byId,parseLen,parsePoint,fmtIn,dist,segs,segInt,lineInt,area,visible,locked,pick,entDist,openGeom,moveEnt,UNITS,unit,setUnits,fmtArea,snapPoints,osnap,constrain,bbox,selectBox,ptSegDist,rotEnt,mirEnt,offsetEnt,trimAt,extendAt,filletAt,hatchSegs,arcPt,norm,deg,rad};
})();
