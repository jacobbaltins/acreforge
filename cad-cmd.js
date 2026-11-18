/* AcreForge CAD Studio command runner + DXF. Conceptual only; DXF R12 export, no DWG. */
(function(){
"use strict";
const C=window.AcreCADCore;
const R={gen:null,req:null,name:"",last:"",sel:[],lastPt:null,prompt:"Command:",view:{cx:0,cy:0,s:2},viewReq:null,profile:(()=>{try{return localStorage.getItem("acreforge-cad-profile")==="USER"?"USER":"DEFAULT"}catch(e){return"DEFAULT"}})()};
const ALIAS={L:"LINE",PL:"PLINE",REC:"RECT",RECTANG:"RECT",C:"CIRCLE",M:"MOVE",CO:"COPY",CP:"COPY",E:"ERASE",U:"UNDO",Z:"ZOOM",DI:"DIST",DIM:"DIM",T:"TEXT",LA:"LAYER",W:"WALL",D:"DOOR",WIN:"WINDOW",O:"OUTLET",AA:"AREA",ALL:"SELECTALL",F:"FIXTURE",RO:"ROTATE",MI:"MIRROR",OF:"OFFSET",TR:"TRIM",EX:"EXTEND",FI:"FILLET",A:"ARC",H:"HATCH",SC:"SCALE",UN:"UNITS",PR:"PROFILE"};
/* AcreForge-own "User" profile: aliases mapped from the user's own keyboard config (only commands that exist here). */
const USER_ALIAS={C:"CIRCLE",R:"RECT"};
const USER_KEYS={"Ctrl+Shift+C":"CIRCLE","Ctrl+Shift+T":"TEXT","Ctrl+Shift+M":"MIRROR","Ctrl+Shift+F":"FILLET","Home":"ZOOM E","Ctrl+R":"@ortho","Ctrl+Shift+P":"@snap"};
const USER_UNMAPPED="Not mapped (no equivalent here): Inventor-only commands (Mold, Frame, Assembly, Part), F6 (3D toggle), Ctrl+P (print).";
const HELP="Commands: PDF ROOF ELEV LINE PLINE RECT CIRCLE ARC HATCH MOVE COPY ROTATE MIRROR SCALE OFFSET TRIM EXTEND FILLET ID UNITS PROFILE ERASE WALL ROOM DOOR WINDOW OUTLET FIXTURE STAIR DIM TEXT DIST AREA LAYER ZOOM SELECTALL UNDO REDO CEILING WALLTH GRID DXF BACKUP VIEW3D HELP. Aliases: L PL REC C A H M CO RO MI SC OF TR EX FI E U Z W D WIN O DI T LA UN PR. Points: x,y  @dx,dy  @dist<angle  or a bare distance toward the cursor. Lengths are in the selected unit (inches by default): 12, 12\", 12in, 300mm, 30cm, 2m. Feet-and-inches notation (3'6\") is not accepted.";
const KWS={};
const cmds={};
function say(m){C.note(m)}
function warn(m){C.setHealth("WARNING",m)}
/* generator request helpers */
const pt=(msg,from)=>({k:"pt",msg,from});
const num=(msg,def,from)=>({k:"num",msg,def,from});
const kw=(msg,opts)=>({k:"kw",msg,opts});
const ent=(msg,types)=>({k:"ent",msg,types});
const str=(msg,def)=>({k:"str",msg,def});
const sel=(msg)=>({k:"sel",msg});
function* getSel(){
  if(R.sel.length){const ids=R.sel.slice();return ids.map(C.byId).filter(e=>e&&!C.locked(e))}
  const ids=yield sel("Select objects (click, window, or Enter to finish):");
  return (ids||[]).map(C.byId).filter(e=>e&&!C.locked(e));
}
cmds.LINE=function*(){
  let p=yield pt("Specify first point:"),pts=[p];
  for(;;){const q=yield pt("Specify next point or [Close/Undo]:",p,["C","U"]);
    if(q===null)break;
    if(q==="C"&&pts.length>2){C.add({t:"line",a:p,b:pts[0]});break}
    if(q==="U"){if(pts.length>1){const last=C.doc.ents[C.doc.ents.length-1];if(last&&last.t==="line"){C.undo()}pts.pop();p=pts[pts.length-1]}continue}
    if(!Array.isArray(q))continue;if(C.dist(p,q)<=6){warn("Wall must be longer than 6 inches.");continue}
    C.add({t:"line",a:p,b:q});pts.push(q);p=q}
};
cmds.PLINE=function*(){
  const pts=[yield pt("Specify start point:")];let closed=false;
  for(;;){const q=yield pt("Specify next point or [Close]:",pts[pts.length-1]);
    if(q===null)break;if(q==="C"&&pts.length>2){closed=true;break}if(Array.isArray(q))pts.push(q)}
  if(pts.length>1)C.add({t:"pline",pts,closed});
};
cmds.RECT=function*(){
  const a=yield pt("Specify first corner:");const b=yield pt("Specify opposite corner (or @w,h):",a);
  if(!Array.isArray(b))return;C.add({t:"pline",closed:true,pts:[a,[b[0],a[1]],b,[a[0],b[1]]]});
};
cmds.CIRCLE=function*(){
  const c=yield pt("Specify center:");const r=yield num("Specify radius:",null,c);
  if(r>0)C.add({t:"circle",c,r});else say("Radius must be positive");
};
cmds.ERASE=function*(){const s=yield*getSel();if(!s.length)return;const ids=s.map(e=>e.id);C.snapshot();C.doc.ents=C.doc.ents.filter(e=>!ids.includes(e.id)&&!(e.wall&&ids.includes(e.wall)));R.sel=[];C.save();say(ids.length+" erased")};
cmds.MOVE=function*(){const s=yield*getSel();if(!s.length)return;const a=yield pt("Specify base point:");const b=yield pt("Specify second point:",a);if(!Array.isArray(b))return;
  C.snapshot();s.forEach(e=>{if(e.t!=="door"&&e.t!=="window")C.moveEnt(e,b[0]-a[0],b[1]-a[1])});C.save()};
cmds.COPY=function*(){const s=yield*getSel();if(!s.length)return;const a=yield pt("Specify base point:");
  for(;;){const b=yield pt("Specify second point or Enter to finish:",a);if(!Array.isArray(b))break;
    C.snapshot();s.forEach(e=>{if(e.t==="door"||e.t==="window")return;const n=JSON.parse(JSON.stringify(e));n.id=C.doc.nid++;C.moveEnt(n,b[0]-a[0],b[1]-a[1]);C.doc.ents.push(n)});C.save()}};
const movable=e=>e.t!=="door"&&e.t!=="window";
cmds.ROTATE=function*(){const s=(yield*getSel()).filter(movable);if(!s.length)return;const b=yield pt("Specify base point:");if(!Array.isArray(b))return;
  const a=parseFloat(yield str("Rotation angle in degrees (counter-clockwise) <90>:","90"));if(isNaN(a)){say("Angle must be a number");return}
  C.snapshot();s.forEach(e=>C.rotEnt(e,b,a));C.save();say(s.length+" rotated "+a+"°")};
cmds.MIRROR=function*(){const s=(yield*getSel()).filter(movable);if(!s.length)return;const a=yield pt("First point of mirror line:");const b=yield pt("Second point of mirror line:",a);if(!Array.isArray(b)||C.dist(a,b)<1e-6){say("Mirror line needs two different points");return}
  const k=yield kw("Erase source objects? [Yes/No] <No>:",["Yes","No"]);C.snapshot();
  const out=s.map(e=>{const n=k==="Yes"?e:JSON.parse(JSON.stringify(e));if(k!=="Yes")n.id=C.doc.nid++;C.mirEnt(n,a,b);return n});
  if(k!=="Yes")out.forEach(n=>C.doc.ents.push(n));C.save();say(s.length+(k==="Yes"?" mirrored":" mirrored copies added"))};
cmds.SCALE=function*(){const s=(yield*getSel()).filter(movable);if(!s.length)return;const b=yield pt("Specify base point:");if(!Array.isArray(b))return;
  const f=parseFloat(yield str("Scale factor:","2"));if(!(f>0)||f>1000){say("Scale factor must be between 0 and 1000");return}
  C.snapshot();const sc=p=>[b[0]+(p[0]-b[0])*f,b[1]+(p[1]-b[1])*f];
  s.forEach(e=>{if(e.a)e.a=sc(e.a);if(e.b)e.b=sc(e.b);if(e.pts)e.pts=e.pts.map(sc);if(e.c)e.c=sc(e.c);if(e.p)e.p=sc(e.p);if(e.r)e.r*=f;if(e.w&&e.t==="fixture"){e.w*=f;e.d*=f}if(e.t==="text")e.h*=f;if(e.t==="wall")e.th*=f});C.save();say(s.length+" scaled by "+f)};
cmds.OFFSET=function*(){const d=yield num("Offset distance:");if(!(d>0)){say("Offset distance must be positive");return}
  for(;;){const e=yield ent("Select LINE, WALL, CIRCLE or ARC to offset (Enter to finish):",["line","wall","circle","arc"]);if(!e)break;
    const p=yield pt("Click the side to offset toward:");if(!Array.isArray(p))break;
    const n=C.offsetEnt(e,d,p);if(!n){say("Cannot offset that object by this distance");continue}n.id=C.doc.nid++;C.snapshot();C.doc.ents.push(n);C.save();say("Offset created")}};
cmds.TRIM=function*(){for(;;){const p=yield pt("Click the part of a LINE to trim (Enter to finish):");if(!Array.isArray(p))break;say(C.trimAt(p))}};
cmds.EXTEND=function*(){for(;;){const p=yield pt("Click the end of a LINE to extend (Enter to finish):");if(!Array.isArray(p))break;say(C.extendAt(p))}};
cmds.FILLET=function*(){const r=yield num("Fillet radius <0>:",0);if(r<0){say("Radius cannot be negative");return}
  const a=yield pt("Click first LINE (away from the corner):");if(!Array.isArray(a))return;const b=yield pt("Click second LINE (away from the corner):");if(!Array.isArray(b))return;say(C.filletAt(a,b,r))};
cmds.ARC=function*(){const c=yield pt("Specify arc center:");if(!Array.isArray(c))return;const s=yield pt("Specify start point (sets radius):",c);if(!Array.isArray(s))return;
  const r=C.dist(c,s);if(r<1e-6){say("Start point must differ from center");return}
  const e=yield pt("Specify end point (counter-clockwise from start):",c);if(!Array.isArray(e))return;
  const a0=C.norm(C.deg(Math.atan2(s[1]-c[1],s[0]-c[0]))),a1=C.norm(C.deg(Math.atan2(e[1]-c[1],e[0]-c[0])));if(Math.abs(a0-a1)<1e-6){say("End point must differ in angle from start");return}
  C.add({t:"arc",c,r,a0,a1})};
cmds.HATCH=function*(){const e=yield ent("Select a closed polyline or ROOM to hatch:",["pline","room"]);if(!e)return;if(e.t==="pline"&&!e.closed){say("Polyline must be closed");return}
  const k=yield kw("Pattern [ANSI31/CROSS/SOLID] <ANSI31>:",["ANSI31","CROSS","SOLID"]);const pat=k||"ANSI31";const sp=yield num("Line spacing <6>:",6);if(!(sp>=0.5)){say("Spacing must be at least 0.5 inches");return}
  C.add({t:"hatch",pts:e.pts.map(p=>p.slice()),pat,sp,layer:C.doc.cur==="0"?"A-ANNO":C.doc.cur})};
cmds.ID=function*(){const p=yield pt("Specify point:");if(Array.isArray(p))say("X = "+C.fmtIn(p[0])+"  Y = "+C.fmtIn(p[1]))};
cmds.UNITS=function*(){const u=yield kw("Display units [in/mm/cm/m] <"+C.doc.units+">:",["in","mm","cm","m"]);if(!u){say("Units: "+C.unit().n);return}C.setUnits(u);say("Units set to "+C.unit().n+" (stored geometry stays in inches; DXF is written in inches)")};
cmds.PROFILE=function*(){const k=yield kw("Keyboard profile [Default/User] <"+R.profile+">:",["Default","User"]);if(!k)return;R.profile=k.toUpperCase();try{localStorage.setItem("acreforge-cad-profile",R.profile)}catch(e){}say("Profile: "+k)};
cmds.WALL=function*(){
  let p=yield pt("Specify wall start (centerline), thickness "+C.doc.wallTh+"\":");
  for(;;){const q=yield pt("Specify next wall point or [Close]:",p);if(q===null)break;if(!Array.isArray(q))continue;if(C.dist(p,q)<=6){warn("Wall must be longer than 6 inches.");continue}
    C.add({t:"wall",a:p,b:q,th:C.doc.wallTh,layer:"A-WALL"});p=q}
};
cmds.ROOM=function*(){
  const a=yield pt("Specify first corner of room (outside corner):");const b=yield pt("Specify opposite corner:",a);if(!Array.isArray(b))return;if(Math.abs(b[0]-a[0])<24||Math.abs(b[1]-a[1])<24){warn("Room size below minimum dimensions (24 x 24 inches). Pick a larger opposite corner.");return}
  const name=yield str("Room name:","Room");
  const P=[a,[b[0],a[1]],b,[a[0],b[1]]];
  for(let i=0;i<4;i++)C.add({t:"wall",a:P[i],b:P[(i+1)%4],th:C.doc.wallTh,layer:"A-WALL"});
  C.add({t:"room",pts:P,name:name||"Room",layer:"A-ROOM"});
};
function* hostWall(msg){const e=yield ent(msg,["wall"]);return e}
function placeOpening(type,layer,defW,sill,head){return function*(){
  const w=yield ent("Click wall for "+type+":",["wall"]);if(!w){warn((type==="door"?"Doors":"Windows")+" must be attached to a wall. Click a wall to place one.");return}
  const L=C.dist(w.a,w.b);const wd=yield num("Width in inches <"+defW+">:",defW);if(!(wd>0)||wd>L){warn((type==="door"?"Door":"Window")+" is wider than the wall. Choose a smaller width.");return}const pos=yield num("Distance from wall start to opening edge (inches) <"+Math.max(0,(L-wd)/2).toFixed(0)+">:",Math.max(0,(L-wd)/2));
  if(pos<0||pos+wd>L+1e-6){say("Opening does not fit on the wall");return}
  const clash=C.doc.ents.some(o=>(o.t==="door"||o.t==="window")&&o.wall===w.id&&pos<o.pos+o.w&&o.pos<pos+wd);if(clash){warn("That spot overlaps another opening on this wall. Choose a different position.");return}
  C.clearHealth();C.add({t:type,wall:w.id,pos,w:wd,sill,head,layer})}}
cmds.DOOR=placeOpening("door","A-DOOR",36,0,80);
cmds.WINDOW=placeOpening("window","A-GLAZ",36,36,80);
cmds.OUTLET=function*(){const p=yield pt("Specify outlet location:");const h=yield num("Height above floor in inches <16>:",16);C.add({t:"outlet",p,h,layer:"E-POWR"})};
cmds.FIXTURE=function*(){const n=yield kw("Fixture ["+Object.keys(C.LIB).join("/")+"]:",Object.keys(C.LIB));const d=C.LIB[n];if(!d){say("Unknown fixture");return}
  const p=yield pt("Specify center:");C.add({t:"fixture",kind:n,p,w:d[0],d:d[1],layer:n==="sink"||n==="toilet"||n==="tub"?"P-PLMB":"A-FURN"})};
cmds.STAIR=function*(){const p=yield pt("Specify stair center:");C.add({t:"fixture",kind:"stair",p,w:36,d:120,layer:"A-FURN"})};
cmds.DIM=function*(){const a=yield pt("Specify first point:");const b=yield pt("Specify second point:",a);if(!Array.isArray(b))return;const o=yield pt("Specify dimension line location (Enter for 12\" offset):",b);
  let off=12;if(Array.isArray(o)){const dx=b[0]-a[0],dy=b[1]-a[1],L=Math.hypot(dx,dy);if(L)off=((o[0]-a[0])*(-dy)+(o[1]-a[1])*dx)/L}
  C.add({t:"dim",a,b,off,layer:"A-DIMS"})};
cmds.TEXT=function*(){const p=yield pt("Specify text position:");const h=yield num("Height <9>:",9);const s=yield str("Text:");if(s)C.add({t:"text",p,h,s,layer:"A-ANNO"})};
cmds.DIST=function*(){const a=yield pt("First point:");const b=yield pt("Second point:",a);if(!Array.isArray(b))return;const d=C.dist(a,b);say("Distance = "+C.fmtIn(d)+" ("+d.toFixed(2)+"\"), angle "+(Math.atan2(b[1]-a[1],b[0]-a[0])*180/Math.PI).toFixed(1)+"°, dX "+(b[0]-a[0]).toFixed(2)+" dY "+(b[1]-a[1]).toFixed(2))};
cmds.AREA=function*(){const pts=[];for(;;){const q=yield pt(pts.length?"Next corner or Enter to finish:":"First corner:",pts[pts.length-1]);if(q===null)break;if(Array.isArray(q))pts.push(q)}
  if(pts.length<3){say("Need at least 3 points");return}let per=0;for(let i=0;i<pts.length;i++)per+=C.dist(pts[i],pts[(i+1)%pts.length]);const a=Math.abs(C.area(pts));say("Area = "+C.fmtArea(a)+", perimeter "+C.fmtIn(per))};
cmds.LAYER=function*(){
  const op=yield kw("Layer option [New/Set/On/Off/Lock/Unlock/Color/Ltype/List]:",["NEW","SET","ON","OFF","LOCK","UNLOCK","COLOR","LTYPE","LIST"]);const D=C.doc;
  if(op==="LIST"){say("Layers: "+Object.keys(D.layers).map(n=>n+(D.layers[n].on?"":" (off)")+(D.layers[n].lock?" (locked)":"")+(n===D.cur?" *":"")).join(", "));return}
  const n=String(yield str("Layer name:")||"").toUpperCase();if(!n)return;
  if(op==="NEW"){if(D.layers[n]){say("Layer exists");return}C.snapshot();D.layers[n]={color:7,ltype:"CONTINUOUS",on:true,lock:false};D.cur=n;C.save();return}
  const L=D.layers[n];if(!L){say("No such layer: "+n);return}
  C.snapshot();
  if(op==="SET")D.cur=n;else if(op==="ON")L.on=true;else if(op==="OFF")L.on=false;else if(op==="LOCK")L.lock=true;else if(op==="UNLOCK")L.lock=false;
  else if(op==="COLOR"){const c=String(yield str("Color [red/yellow/green/cyan/blue/magenta/white]:")||"").toLowerCase();if(!C.COLORS[c]){say("Unknown color");C.undo();return}L.color=C.COLORS[c]}
  else if(op==="LTYPE"){const t=String(yield str("Linetype [CONTINUOUS/DASHED/CENTER/HIDDEN]:")||"").toUpperCase();if(!C.LTYPES.includes(t)){say("Unknown linetype");C.undo();return}L.ltype=t}
  C.save();
};
cmds.SELECTALL=function*(){R.sel=C.doc.ents.filter(e=>C.visible(e)&&!C.locked(e)).map(e=>e.id);say(R.sel.length+" selected")};
cmds.UNDO=function*(){if(C.undo()){say("Undone");C.clearHealth()}else warn("No more actions to undo.")};
cmds.REDO=function*(){if(C.redo()){say("Redone");C.clearHealth()}else warn("No more actions to redo.")};
cmds.CEILING=function*(){const h=yield num("Ceiling height in inches <"+C.doc.ceil+">:",C.doc.ceil);if(h>=48&&h<=240){C.doc.ceil=h;C.save()}else say("Ceiling must be 48-240 inches")};
cmds.WALLTH=function*(){const h=yield num("Default wall thickness in inches <"+C.doc.wallTh+">:",C.doc.wallTh);if(h>=2&&h<=36){C.doc.wallTh=h;C.save()}else say("Thickness must be 2-36 inches")};
cmds.GRID=function*(){const h=yield num("Grid spacing in inches <"+C.doc.grid+">:",C.doc.grid);if(h>=1&&h<=120){C.doc.grid=h;C.save()}else say("Grid must be 1-120 inches")};
cmds.ZOOM=function*(){const o=yield kw("Zoom [Extents/In/Out]:",["E","IN","OUT"]);R.viewReq={op:o}};
cmds.HELP=function*(){say(HELP)};
cmds.DXF=function*(){R.viewReq={op:"DXF"}};
cmds.VIEW3D=function*(){const k=yield kw("View [Top/Front/Right/Back/Left/Home/Off] <Home>:",["Top","Front","Right","Back","Left","Home","Off"]);const s=String(k||"Home").toLowerCase();R.viewReq={op:"3D",k:s==="home"?"iso":s}};
cmds.BACKUP=function*(){C.exportBackup();say("Backup file downloaded (JSON, inches). Keep it somewhere safe.")};
cmds.PDF=function*(){const S=window.AcreCADSheets;const p=yield kw("Paper ["+Object.keys(S.PAPER).join("/")+"] <"+(C.doc.paper||"Letter")+">:",Object.keys(S.PAPER).concat([""]));if(p&&S.PAPER[p])C.doc.paper=p;R.viewReq={op:"PDF"}};
cmds.ROOF=function*(){const S=window.AcreCADSheets;const ty=yield kw("Roof type ["+S.ROOFS.join("/")+"]:",S.ROOFS);if(!S.ROOFS.includes(ty)){say("Unknown roof type");return}const pi=yield num("Pitch rise per 12 <"+S.roofCfg().pitch+">:",S.roofCfg().pitch);const ov=yield num("Overhang in inches <"+S.roofCfg().ov+">:",S.roofCfg().ov);if(!(pi>0&&pi<=24)||!(ov>=0)){say("Pitch must be 0-24 and overhang >= 0");return}C.doc.roof={type:ty,pitch:pi,ov};C.save();const r=S.roof();if(!r){say("Roof set; draw walls to compute area");return}say(r.type+" roof "+r.pitch+"/12: area "+Math.round(r.area)+" sq in, ridge "+C.fmtIn(r.ridgeLength)+", ridge height "+C.fmtIn(r.ridgeHeight)+" (conceptual)")};
cmds.ELEV=function*(){const S=window.AcreCADSheets;if(!S.bbox()){say("Draw walls first");return}S.ROOFS;["front","rear","left","right"].forEach(s=>{const e=S.elevation(s);say(s+" elevation: width "+C.fmtIn(e.width)+", "+e.openings.length+" opening(s)")})};
const NAMES=Object.keys(cmds);
/* ---------- runner ---------- */
function resolve(n){n=n.toUpperCase();if(R.profile==="USER"&&USER_ALIAS[n])n=USER_ALIAS[n];else if(ALIAS[n])n=ALIAS[n];if(cmds[n])return n;const m=NAMES.filter(x=>x.startsWith(n));return m.length===1?m[0]:null}
function advance(v){
  let r;try{r=R.gen.next(v)}catch(err){say("Error: "+err.message);cancel();return}
  if(r.done){R.gen=null;R.req=null;R.prompt="Command:";return}
  R.req=r.value;R.prompt=r.value.msg;
}
function start(name,args){
  const n=resolve(name);
  if(!n){say("Unknown command: "+name+". Type HELP.");return false}
  R.name=n;R.last=n;R.gen=cmds[n]();R.viewReq=null;advance();
  (args||[]).forEach(a=>{if(R.gen)feed(a)});
  return true;
}
function cancel(){if(R.gen){try{R.gen.return()}catch(e){}}R.gen=null;R.req=null;R.prompt="Command:";R.sel=R.sel}
function parseReq(s){
  const q=R.req;if(!q)return undefined;s=s.trim();
  if(q.k==="pt"){
    if(/^[A-Za-z]$/.test(s)&&/Close|Undo/.test(q.msg))return s.toUpperCase();
    const p=C.parsePoint(s,q.from||R.lastPt);if(p)return p;
    const d=C.parseLen(s);if(!isNaN(d)&&q.from&&R.cursor){const dx=R.cursor[0]-q.from[0],dy=R.cursor[1]-q.from[1],L=Math.hypot(dx,dy)||1;return [q.from[0]+dx/L*d,q.from[1]+dy/L*d]}
    return undefined}
  if(q.k==="num"){const d=C.parseLen(s);if(!isNaN(d))return d;if(q.from&&R.cursor){/* radius via point */}return undefined}
  if(q.k==="kw"){const u=s.toUpperCase();const ex=q.opts.find(o=>o.toUpperCase()===u);if(ex)return ex;const m=q.opts.filter(o=>u&&o.toUpperCase().startsWith(u));return m.length===1?m[0]:undefined}
  if(q.k==="str")return s;
  if(q.k==="sel"){if(/^all$/i.test(s))return C.doc.ents.filter(e=>C.visible(e)&&!C.locked(e)).map(e=>e.id);return undefined}
  return undefined;
}
function feed(s){
  if(!R.gen){
    s=String(s).trim();
    if(!s){if(R.last)return start(R.last);return false}
    const parts=s.split(/\s+/);return start(parts[0],parts.slice(1));
  }
  const q=R.req;s=String(s);
  if(s.trim()===""){
    if(q.k==="num"&&q.def!=null){const d=q.def;advance(d);return true}
    if(q.k==="str"&&q.def!=null){advance(q.def);return true}
    if(q.k==="sel"){/* Enter finishes */advance(R._pending||[]);R._pending=null;return true}
    advance(null);return true}
  const v=parseReq(s);
  if(v===undefined){say("Invalid input for: "+q.msg);return false}
  if(q.k==="pt"&&Array.isArray(v))R.lastPt=v;
  if(q.k==="sel"){advance(v);return true}
  advance(v);return true;
}
function clickPoint(p){if(R.req&&R.req.k==="pt"){R.lastPt=p;advance(p);return true}if(R.req&&R.req.k==="num"&&R.req.from){advance(C.dist(R.req.from,p));return true}return false}
function clickEnt(e){
  if(R.req&&R.req.k==="ent"){if(e&&R.req.types.includes(e.t)){advance(e);return true}say("Select a "+R.req.types.join("/"));return false}
  if(R.req&&R.req.k==="sel"){if(e){R._pending=(R._pending||[]);if(!R._pending.includes(e.id)&&!C.locked(e))R._pending.push(e.id);return true}}
  return false;
}
function windowSelect(ids){if(R.req&&R.req.k==="sel"){R._pending=Array.from(new Set((R._pending||[]).concat(ids)));return true}R.sel=ids;return true}
/* ---------- DXF R12 export ---------- */
function exportDXF(){
  const D=C.doc,o=[];const g=(c,v)=>{o.push(String(c));o.push(String(v))};
  const lt={CONTINUOUS:[ "Solid line",[]],DASHED:["Dashed",[0.5,-0.25]],CENTER:["Center",[1.25,-0.25,0.25,-0.25]],HIDDEN:["Hidden",[0.25,-0.125]]};
  g(0,"SECTION");g(2,"HEADER");g(9,"$ACADVER");g(1,"AC1009");g(9,"$INSUNITS");g(70,1);g(0,"ENDSEC");
  g(0,"SECTION");g(2,"TABLES");g(0,"TABLE");g(2,"LTYPE");g(70,4);
  C.LTYPES.forEach(n=>{g(0,"LTYPE");g(2,n);g(70,0);g(3,lt[n][0]);g(72,65);g(73,lt[n][1].length);g(40,lt[n][1].reduce((a,b)=>a+Math.abs(b),0));lt[n][1].forEach(d=>g(49,d))});
  g(0,"ENDTAB");g(0,"TABLE");g(2,"LAYER");g(70,Object.keys(D.layers).length);
  Object.keys(D.layers).forEach(n=>{const L=D.layers[n];g(0,"LAYER");g(2,n);g(70,L.lock?4:0);g(62,L.on?L.color:-L.color);g(6,L.ltype)});
  g(0,"ENDTAB");g(0,"ENDSEC");g(0,"SECTION");g(2,"ENTITIES");
  const f=v=>(Math.round(v*10000)/10000);
  const LINE=(a,b,l)=>{g(0,"LINE");g(8,l);g(10,f(a[0]));g(20,f(a[1]));g(30,0);g(11,f(b[0]));g(21,f(b[1]));g(31,0)};
  const POLY=(pts,closed,l)=>{g(0,"POLYLINE");g(8,l);g(66,1);g(70,closed?1:0);pts.forEach(p=>{g(0,"VERTEX");g(8,l);g(10,f(p[0]));g(20,f(p[1]));g(30,0)});g(0,"SEQEND");g(8,l)};
  const TEXT=(p,h,s,l)=>{g(0,"TEXT");g(8,l);g(10,f(p[0]));g(20,f(p[1]));g(30,0);g(40,h);g(1,s)};
  const ARC=(c,r,a0,a1,l)=>{g(0,"ARC");g(8,l);g(10,f(c[0]));g(20,f(c[1]));g(30,0);g(40,f(r));g(50,f(a0));g(51,f(a1))};
  const CIRC=(c,r,l)=>{g(0,"CIRCLE");g(8,l);g(10,f(c[0]));g(20,f(c[1]));g(30,0);g(40,f(r))};
  D.ents.forEach(e=>{const l=e.layer;
    if(e.t==="line")LINE(e.a,e.b,l);
    else if(e.t==="pline")POLY(e.pts,e.closed,l);
    else if(e.t==="circle")CIRC(e.c,e.r,l);
    else if(e.t==="arc")ARC(e.c,e.r,e.a0,e.a1,l);
    else if(e.t==="hatch"){C.hatchSegs(e,true).forEach(s=>LINE(s[0],s[1],l))}
    else if(e.t==="text")TEXT(e.p,e.h,e.s,l);
    else if(e.t==="wall"){const L=C.dist(e.a,e.b);if(!L)return;const nx=-(e.b[1]-e.a[1])/L*e.th/2,ny=(e.b[0]-e.a[0])/L*e.th/2;LINE([e.a[0]+nx,e.a[1]+ny],[e.b[0]+nx,e.b[1]+ny],l);LINE([e.a[0]-nx,e.a[1]-ny],[e.b[0]-nx,e.b[1]-ny],l)}
    else if(e.t==="door"||e.t==="window"){const og=C.openGeom(e);if(!og)return;const nx=-og[2][1]*og[3].th/2,ny=og[2][0]*og[3].th/2;LINE([og[0][0]+nx,og[0][1]+ny],[og[1][0]+nx,og[1][1]+ny],l);LINE([og[0][0]-nx,og[0][1]-ny],[og[1][0]-nx,og[1][1]-ny],l)}
    else if(e.t==="outlet"){CIRC(e.p,3,l)}
    else if(e.t==="fixture"){const x=e.w/2,y=e.d/2;POLY([[e.p[0]-x,e.p[1]-y],[e.p[0]+x,e.p[1]-y],[e.p[0]+x,e.p[1]+y],[e.p[0]-x,e.p[1]+y]],true,l);TEXT([e.p[0]-x,e.p[1]],4,e.kind.toUpperCase(),l)}
    else if(e.t==="room"){const a=Math.abs(C.area(e.pts));const cx=e.pts.reduce((s,p)=>s+p[0],0)/e.pts.length,cy=e.pts.reduce((s,p)=>s+p[1],0)/e.pts.length;TEXT([cx-30,cy],6,e.name+" "+roomSize(e)+" "+C.fmtArea(a),l)}
    else if(e.t==="dim"){const L=C.dist(e.a,e.b);if(!L)return;const nx=-(e.b[1]-e.a[1])/L*e.off,ny=(e.b[0]-e.a[0])/L*e.off;const a2=[e.a[0]+nx,e.a[1]+ny],b2=[e.b[0]+nx,e.b[1]+ny];LINE(e.a,a2,l);LINE(e.b,b2,l);LINE(a2,b2,l);TEXT([(a2[0]+b2[0])/2,(a2[1]+b2[1])/2+2],5,C.fmtIn(L),l)}
  });
  g(0,"ENDSEC");g(0,"EOF");return o.join("\r\n")+"\r\n";
}
function parseDXF(text){
  if(typeof text!=="string"||!text.trim())throw new Error("The selected file is empty.");
  if(text.length>5*1024*1024)throw new Error("DXF files must be 5 MiB or smaller.");
  const lines=text.replace(/^\uFEFF/,"").split(/\r?\n/);
  while(lines.length&&lines[lines.length-1].trim()==="")lines.pop();
  if(lines.length%2)throw new Error("The DXF ends with an incomplete group pair.");
  const pairs=[];
  for(let i=0;i<lines.length;i+=2){
    const raw=lines[i].trim();if(!/^\d+$/.test(raw))throw new Error("Invalid DXF group code near line "+(i+1)+".");
    const code=Number(raw);if(!Number.isInteger(code)||code>1071)throw new Error("Unsupported DXF group code near line "+(i+1)+".");
    pairs.push({code,value:lines[i+1].trim()});
  }
  let unitCode=0,hasUnits=false;
  for(let i=0;i<pairs.length;i++)if(pairs[i].code===9&&pairs[i].value.toUpperCase()==="$INSUNITS"){
    const unit=pairs[i+1];if(!unit||unit.code!==70)throw new Error("The DXF unit declaration is incomplete.");
    unitCode=Number(unit.value);hasUnits=true;break;
  }
  const unitInfo={0:{factor:1,label:"unitless; assumed inches"},1:{factor:1,label:"inches"},2:{factor:12,label:"feet"},4:{factor:1/25.4,label:"millimeters"},5:{factor:1/2.54,label:"centimeters"},6:{factor:1/0.0254,label:"meters"}}[unitCode];
  if(!unitInfo)throw new Error("Unsupported DXF units code "+unitCode+". Use inches, feet, millimeters, centimeters or meters.");
  const factor=unitInfo.factor,records=[];let section="",record=null,foundEntities=false,closedEntities=false;
  const saveRecord=()=>{if(record){records.push(record);record=null;if(records.length>50000)throw new Error("The DXF contains too many records.")}};
  for(let i=0;i<pairs.length;i++){
    const p=pairs[i],v=p.value.toUpperCase();
    if(p.code===0&&v==="SECTION"){
      saveRecord();const name=pairs[++i];if(!name||name.code!==2)throw new Error("A DXF section is missing its name.");
      section=name.value.toUpperCase();if(section==="ENTITIES")foundEntities=true;continue;
    }
    if(p.code===0&&v==="ENDSEC"){saveRecord();if(section==="ENTITIES")closedEntities=true;section="";continue}
    if(section!=="ENTITIES")continue;
    if(p.code===0){saveRecord();record={type:v,groups:[]}}
    else if(record)record.groups.push(p);
  }
  saveRecord();
  if(!foundEntities||!closedEntities)throw new Error("The file has no complete ENTITIES section.");
  const group=(r,code)=>{const p=r.groups.find(g=>g.code===code);return p&&p.value};
  const number=(r,code,label,optional)=>{
    const raw=group(r,code);if(raw===undefined&&optional)return 0;
    if(raw===undefined||raw==="")throw new Error("Missing "+label+" in DXF "+r.type+".");
    const n=Number(raw);if(!Number.isFinite(n))throw new Error("Invalid "+label+" in DXF "+r.type+".");return n;
  };
  const checkExtrusion=r=>{
    const x=number(r,210,"extrusion X",true),y=number(r,220,"extrusion Y",true),z=group(r,230)===undefined?1:number(r,230,"extrusion Z");
    if(Math.abs(x)>1e-8||Math.abs(y)>1e-8||Math.abs(z-1)>1e-8)throw new Error("Only 2D DXF geometry in the XY plane is supported.");
  };
  const scaled=(n,label)=>{const v=n*factor;if(!Number.isFinite(v)||Math.abs(v)>1e7)throw new Error(label+" exceeds the supported coordinate range.");return v};
  const point=(r,xCode,yCode,zCode,label)=>{
    const z=number(r,zCode,label+" elevation",true);if(Math.abs(z)>1e-8)throw new Error("Only 2D DXF geometry at zero elevation is supported.");
    return [scaled(number(r,xCode,label+" X"),label+" X"),scaled(number(r,yCode,label+" Y"),label+" Y")];
  };
  const layerOf=r=>{const name=group(r,8)||"0";if(name.length>255)throw new Error("A DXF layer name is too long.");return name};
  const entities=[],layerNames=new Set();let skipped=0,vertices=0;
  const add=(entity,layer)=>{if(entities.length>=10000)throw new Error("DXF imports are limited to 10,000 supported entities.");layerNames.add(layer);if(layerNames.size>64)throw new Error("DXF imports are limited to 64 source layers.");entities.push(Object.assign(entity,{layer}))};
  for(let i=0;i<records.length;i++){
    const r=records[i],layer=layerOf(r);
    if(r.type==="LINE"){
      checkExtrusion(r);
      const a=point(r,10,20,30,"line start"),b=point(r,11,21,31,"line end");
      if(C.dist(a,b)<=1e-9)throw new Error("Zero-length DXF lines are not supported.");
      add({t:"line",a,b},layer);
    }else if(r.type==="POLYLINE"){
      checkExtrusion(r);
      const flags=Math.trunc(number(r,70,"polyline flags",true));
      if(flags&((1<<3)|(1<<4)|(1<<6)))throw new Error("Only 2D DXF polylines are supported.");
      if(Math.abs(number(r,30,"polyline elevation",true))>1e-8)throw new Error("Only 2D DXF geometry at zero elevation is supported.");
      const pts=[];let j=i+1;
      while(j<records.length&&records[j].type==="VERTEX"){
        if(++vertices>50000)throw new Error("DXF imports are limited to 50,000 polyline vertices.");
        if(Math.abs(number(records[j],42,"polyline bulge",true))>1e-12)throw new Error("Curved DXF polyline segments are not supported.");
        pts.push(point(records[j],10,20,30,"polyline vertex"));j++;
      }
      if(j>=records.length||records[j].type!=="SEQEND")throw new Error("A DXF polyline is missing its sequence end.");
      i=j;if(pts.length<2)throw new Error("DXF polylines need at least two vertices.");
      add({t:"pline",pts,closed:!!(flags&1)},layer);
    }else if(r.type==="CIRCLE"){
      checkExtrusion(r);
      const c=point(r,10,20,30,"circle center"),radius=scaled(number(r,40,"circle radius"),"Circle radius");
      if(radius<=0)throw new Error("DXF circles need a positive radius.");
      add({t:"circle",c,r:radius},layer);
    }else if(r.type==="ARC"){
      checkExtrusion(r);
      const c=point(r,10,20,30,"arc center"),radius=scaled(number(r,40,"arc radius"),"Arc radius");
      const a0=number(r,50,"arc start angle"),a1=number(r,51,"arc end angle");
      if(radius<=0||Math.abs(a0)>360000||Math.abs(a1)>360000)throw new Error("DXF arcs have invalid radius or angles.");
      add({t:"arc",c,r:radius,a0:C.norm(a0),a1:C.norm(a1)},layer);
    }else if(r.type==="TEXT"){
      checkExtrusion(r);
      const p=point(r,10,20,30,"text position"),h=scaled(number(r,40,"text height"),"Text height"),s=group(r,1);
      if(h<=0||s===undefined)throw new Error("DXF text needs a positive height and content.");
      add({t:"text",p,h,s},layer);
    }else if(r.type!=="VERTEX"&&r.type!=="SEQEND")skipped++;
  }
  return {entities,layers:Array.from(layerNames),skipped,units:hasUnits?unitInfo.label:"unitless; assumed inches"};
}
function commitDXFImport(parsed){
  if(!parsed||!Array.isArray(parsed.entities)||!parsed.entities.length)throw new Error("No supported 2D entities are ready to import.");
  const D=C.doc,reserved=new Set(Object.keys(D.layers)),layerMap=new Map(),newLayers=[];
  parsed.layers.forEach(source=>{
    if(source==="0"){layerMap.set(source,"0");return}
    const safe=String(source).toUpperCase().replace(/[^A-Z0-9_-]/g,"_").replace(/_+/g,"_").replace(/^_+|_+$/g,"").slice(0,26)||"IMPORT";
    const base=("DXF-"+safe).slice(0,31);let name=base,n=2;
    while(reserved.has(name)){const suffix="_"+n++;name=base.slice(0,31-suffix.length)+suffix}
    reserved.add(name);layerMap.set(source,name);newLayers.push(name);
  });
  if(Object.keys(D.layers).length+newLayers.length>128)throw new Error("This drawing has reached the 128-layer limit.");
  C.snapshot();
  newLayers.forEach(name=>{D.layers[name]={color:7,ltype:"CONTINUOUS",on:true,lock:false}});
  parsed.entities.forEach(source=>{
    const e=Object.assign({},source,{id:D.nid++,layer:layerMap.get(source.layer)||"0"});
    if(e.a)e.a=e.a.slice();if(e.b)e.b=e.b.slice();if(e.c)e.c=e.c.slice();if(e.p)e.p=e.p.slice();if(e.pts)e.pts=e.pts.map(p=>p.slice());
    D.ents.push(e);
  });
  C.save();
  return {added:parsed.entities.length,layers:newLayers.length,skipped:parsed.skipped||0};
}
function roomSize(e){const xs=e.pts.map(p=>p[0]),ys=e.pts.map(p=>p[1]);return C.fmtIn(Math.max(...xs)-Math.min(...xs))+" x "+C.fmtIn(Math.max(...ys)-Math.min(...ys))}
window.AcreCADCmd={R,cmds,NAMES,HELP,start,feed,cancel,clickPoint,clickEnt,windowSelect,exportDXF,parseDXF,commitDXFImport,roomSize,resolve,USER_ALIAS,USER_KEYS,USER_UNMAPPED};
})();
