/* AcreForge CAD Studio UI: dark model-space canvas, snaps, panels, command line. Conceptual only. */
(function(){
"use strict";
const C=window.AcreCADCore,M=window.AcreCADCmd,R=M.R;
const U={v3:{on:false,yaw:35,pitch:28,zoom:1},osnap:true,grid:true,snap:false,ortho:false,polar:false,cx:120,cy:90,s:2,w:800,h:500,dpr:1,mx:0,my:0,snapHit:null,drag:null,interaction:"READY",root:null,cv:null,fresh:true,listeners:false,full:false};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const toS=p=>[(p[0]-U.cx)*U.s+U.w/2,U.h/2-(p[1]-U.cy)*U.s];
const toW=(x,y)=>[(x-U.w/2)/U.s+U.cx,U.cy-(y-U.h/2)/U.s];
const INTERACTION_TRANSITIONS=[
  {state:"PAN",label:"Panning",match:()=>U.drag&&U.drag.pan},
  {state:"WINDOW",label:"Window select",match:()=>U.drag&&U.drag.box&&U.drag.b[0]>=U.drag.a[0]},
  {state:"CROSSING",label:"Crossing select",match:()=>U.drag&&U.drag.box&&U.drag.b[0]<U.drag.a[0]},
  {state:"DRAG",label:"Selecting",match:()=>!!U.drag},
  {state:"POINT",label:"Pick point",match:()=>R.req&&R.req.k==="pt"},
  {state:"NUMBER",label:"Enter number",match:()=>R.req&&R.req.k==="num"},
  {state:"OPTION",label:"Choose option",match:()=>R.req&&R.req.k==="kw"},
  {state:"TEXT",label:"Enter text",match:()=>R.req&&R.req.k==="str"},
  {state:"OBJECT",label:"Pick object",match:()=>R.req&&R.req.k==="ent"},
  {state:"SELECTION",label:"Select objects",match:()=>R.req&&R.req.k==="sel"},
  {state:"COMMAND",label:"Working",match:()=>!!R.gen},
  {state:"SELECTED",label:"Selection ready",match:()=>R.sel.length>0},
  {state:"READY",label:"Ready",match:()=>true}
];
function interactionState(){return INTERACTION_TRANSITIONS.find(t=>t.match())||INTERACTION_TRANSITIONS[INTERACTION_TRANSITIONS.length-1]}
function updateInteraction(){
  const t=interactionState(),el=U.root&&U.root.querySelector("#cadmode");
  U.interaction=t.state;
  if(el){const label="Mode: "+t.label;if(el.textContent!==label){el.textContent=label;el.dataset.state=t.state}}
}
function mount(root){
  if(!root)return;U.root=root;
  root.innerHTML='<div id="cadwrap" class="cadwrap'+(U.full?" cadfull":"")+'">'+
  '<div class="cadtop"><b>📐 CAD Studio</b> <span id="cadmodes"></span> <span class="cadspc"></span><button class="btn" id="cad3d" type="button" aria-pressed="false" title="Show a linked 3D model beside the plan">Split 3D</button><button class="btn" id="cadfs" type="button">'+(U.full?"Exit full view":"Full viewport")+'</button><button class="btn" id="caddxf" type="button">Export DXF</button><label>Paper <select id="cadpaper" aria-label="PDF paper size">'+Object.keys(window.AcreCADSheets.PAPER).map(k=>'<option'+(C.doc.paper===k?' selected':'')+'>'+k+'</option>').join('')+'</select></label><button class="btn" id="cadpdf" type="button">Download PDF</button></div>'+
  '<div class="cadmain"><div id="cadtools" class="cadtools"></div><div class="cadcvwrap"><canvas id="cadcv" tabindex="0"></canvas></div><div id="cad3dwrap" class="cad3dwrap" hidden><canvas id="cad3dcv" tabindex="0" aria-label="3D model of your plan. Drag to orbit, wheel to zoom."></canvas><div class="viewcube" role="group" aria-label="3D view buttons">'+Object.keys(window.AcreCAD3D.VIEWS).map(k=>'<button type="button" class="btn" data-v3="'+k+'">'+window.AcreCAD3D.VIEWS[k].label+'</button>').join("")+'</div><div class="cad3dnote">Concept block model from your plan. Not an engineered model.</div></div><div id="cadside" class="cadside"></div></div>'+
  '<div id="cadhealth" class="cadhealth" role="status" aria-live="polite"></div>'+
  '<div id="cadlog" class="cadlog" aria-live="polite"></div>'+
  '<div class="cadcmdrow"><label for="cadcmd" id="cadprompt">Command:</label><input id="cadcmd" autocomplete="off" spellcheck="false" aria-label="CAD command line" placeholder="Type LINE, WALL, ROOM, DOOR… or HELP"></div>'+
  '<div id="cadstatus" class="cadstatus"></div>'+
  '<details id="cadhelp"><summary>Commands, hotkeys &amp; limits</summary><div id="cadhelptxt"></div></details></div>';
  U.cv=root.querySelector("#cadcv");
  tools();bind();layout();refresh();
  const w=root.querySelector("#cadwrap");new ResizeObserver(()=>{layout();draw()}).observe(root.querySelector(".cadcvwrap"));
}
function tools(){
  const G=[["Draw",[["LINE","Line"],["PLINE","Polyline"],["RECT","Rectangle"],["CIRCLE","Circle"],["ARC","Arc"],["HATCH","Hatch"],["WALL","Wall"],["ROOM","Room"],["DOOR","Door"],["WINDOW","Window"],["STAIR","Stair"],["FIXTURE","Fixture"],["OUTLET","Outlet"]]],
    ["Modify",[["MOVE","Move"],["COPY","Copy"],["ROTATE","Rotate"],["MIRROR","Mirror"],["SCALE","Scale"],["OFFSET","Offset"],["TRIM","Trim"],["EXTEND","Extend"],["FILLET","Fillet"],["ERASE","Erase"]]],
    ["Annotate",[["DIM","Dimension"],["TEXT","Text"]]],
    ["Inquiry",[["DIST","Distance"],["AREA","Area"],["ID","Point ID"]]],
    ["History / View",[["UNDO","Undo"],["REDO","Redo"],["ZOOM E","Zoom ext"]]]];
  U.root.querySelector("#cadtools").innerHTML=G.map(g=>'<div class="cadgrp"><span class="cadgl">'+g[0]+'</span>'+g[1].map(t=>'<button type="button" class="btn" data-cmd="'+t[0]+'">'+t[1]+'</button>').join("")+'</div>').join("");
  U.root.querySelector("#cadhelptxt").innerHTML='<p>'+esc(M.HELP)+'</p><p><b>Hotkeys:</b> F3 object snap · F7 grid · F8 ortho · F9 grid snap · F10 polar · Esc cancel · Enter/Space repeat last command · Del erase selection · Ctrl+Z / Ctrl+Y undo/redo · Ctrl+A select all · Home zoom extents (User profile) · right-click = Enter · wheel zoom · middle-drag pan. Drag right = window select, drag left = crossing select.</p><p><b>Limits:</b> Conceptual drafting only. DXF export only (no DWG). No DWG/AutoCAD compatibility claim. Not construction-grade, no code compliance. Snaps: endpoint, midpoint, center, intersection (line-to-line), perpendicular, grid. TRIM, EXTEND and FILLET work on LINEs only; OFFSET works on lines, walls, circles and arcs; HATCH is a simple line pattern (ANSI31, CROSS, SOLID) in the DXF as exploded lines; lineweights show on screen only (DXF R12 has none); doors and windows follow their walls and are skipped by MOVE/COPY/ROTATE/MIRROR/SCALE. Units: inches by default; UNITS switches display/input to mm, cm or m (geometry and DXF stay in inches); feet-and-inches notation is not accepted. Not yet implemented: grips, ZOOM window, DXF import, elevation/3D/layout views inside this workspace (see Lot Builder for linked elevations, 3D and printable sheets).</p><p><b>User profile</b> (PROFILE command or the selector): aliases C=CIRCLE, R=RECT; Ctrl+Shift+C circle, Ctrl+Shift+T text, Ctrl+Shift+M mirror, Ctrl+Shift+F fillet, Ctrl+R ortho, Ctrl+Shift+P grid snap, Home zoom extents. Some browsers reserve Ctrl+Shift shortcuts. "+esc(M.USER_UNMAPPED)+"</p>';
}
function layout(){const w=U.root.querySelector(".cadcvwrap");if(!w)return;U.w=Math.max(300,w.clientWidth);U.h=Math.max(280,w.clientHeight);U.dpr=Math.max(1,window.devicePixelRatio||1);U.cv.width=Math.round(U.w*U.dpr);U.cv.height=Math.round(U.h*U.dpr);U.cv.style.width=U.w+"px";U.cv.style.height=U.h+"px"}
function healthUI(){const el=U.root.querySelector("#cadhealth");if(!el)return;const h=C.health;
  if(h.crashed){el.innerHTML='<div class="cadmodal cadh-RECOVERY" role="alertdialog" aria-label="Restore previous session"><b>AcreForge closed unexpectedly.</b> Restore previous session? Your last saved drawing is kept either way. <button class="btn" type="button" data-hl="restore">Restore</button> <button class="btn" type="button" data-hl="discard">Discard</button></div>';return}
  const n=h.state;el.innerHTML='<span class="cadh cadh-'+n+'">'+n+'</span> '+esc(h.msg||"Valid. Saved in this browser (local-first; cloud sync is a future feature).")+(h.storageFull?' <button class="btn" type="button" data-hl="backup">Download backup</button>':"")}
function draw3d(){const w=U.root&&U.root.querySelector("#cad3dwrap"),b=U.root&&U.root.querySelector("#cad3d");if(!w)return;w.hidden=!U.v3.on;if(b)b.setAttribute("aria-pressed",String(U.v3.on));if(!U.v3.on)return;
  const cv=w.querySelector("canvas");try{U.v3.last=window.AcreCAD3D.render(cv,U.v3,Math.max(1,window.devicePixelRatio||1));U.v3.err=false}catch(e){U.v3.err=true;C.devlog&&C.devlog("3d_failure "+e.message);C.setHealth("WARNING","Updating 3D model... Showing the plan only for now. Your drawing is unchanged.")}}
function refresh(){panels();status();healthUI();prompt();draw();draw3d()}
function prompt(){const p=U.root.querySelector("#cadprompt"),l=U.root.querySelector("#cadlog");if(p)p.textContent=R.prompt;if(l){l.innerHTML=C.log.slice(-6).map(esc).join("<br>");l.scrollTop=l.scrollHeight}}
function status(){
  const t=(k,l,on)=>'<button type="button" class="btn'+(on?" on":"")+'" data-tg="'+k+'" aria-pressed="'+on+'">'+l+'</button>';
  const c=U.root.querySelector("#cadstatus");
  const mode=interactionState();U.interaction=mode.state;
  c.innerHTML='<span id="cadcoord">'+coordTxt()+'</span> <span id="cadmode" data-state="'+mode.state+'" aria-live="polite">Mode: '+mode.label+'</span> '+t("osnap","OSNAP F3",U.osnap)+t("grid","GRID F7",U.grid)+t("ortho","ORTHO F8",U.ortho)+t("snap","SNAP F9",U.snap)+t("polar","POLAR F10",U.polar)+' <span>Layer: <b>'+esc(C.doc.cur)+'</b> · Sel: '+R.sel.length+' · Ceiling '+C.fmtIn(C.doc.ceil)+' · Wall '+C.fmtIn(C.doc.wallTh)+'</span> <label>Units <select id="cadunits" aria-label="Display units">'+Object.keys(C.UNITS).map(k=>'<option value="'+k+'"'+(C.doc.units===k?' selected':'')+'>'+k+'</option>').join('')+'</select></label> <label>Profile <select id="cadprofile" aria-label="Keyboard profile"><option value="DEFAULT"'+(R.profile==="DEFAULT"?' selected':'')+'>Default</option><option value="USER"'+(R.profile==="USER"?' selected':'')+'>User</option></select></label>';
}
const coordTxt=()=>{const p=U.cursor||[0,0];return "X "+C.fmtIn(p[0])+"  Y "+C.fmtIn(p[1])+' '+(U.snapHit?" ["+({end:"ENDPOINT",mid:"MIDPOINT",cen:"CENTER",int:"INTERSECTION",per:"PERPENDICULAR",grid:"GRID"}[U.snapHit]||U.snapHit)+"]":"")};
function panels(){
  const D=C.doc,s=U.root.querySelector("#cadside");
  let h='<h4>Layers</h4><div id="cadlayers">';
  Object.keys(D.layers).forEach(n=>{const L=D.layers[n];h+='<div class="cadlay'+(n===D.cur?" cur":"")+'" data-lay="'+esc(n)+'"><span class="sw" style="background:'+C.HEX[L.color]+'"></span><button type="button" class="lname" data-act="set">'+esc(n)+'</button><button type="button" data-act="on" aria-pressed="'+L.on+'" title="Visibility">'+(L.on?"👁":"–")+'</button><button type="button" data-act="lock" aria-pressed="'+L.lock+'" title="Lock">'+(L.lock?"🔒":"🔓")+'</button><select data-act="ltype" aria-label="Linetype '+esc(n)+'">'+C.LTYPES.map(t=>'<option'+(t===L.ltype?" selected":"")+'>'+t+'</option>').join("")+'</select><select data-act="lw" aria-label="Lineweight '+esc(n)+'">'+[1,1.5,2,3].map(w=>'<option value="'+w+'"'+(w===(L.lw||(n==="A-WALL"?1.5:1))?" selected":"")+'>'+w+'px</option>').join("")+'</select><select data-act="color" aria-label="Color '+esc(n)+'">'+Object.keys(C.COLORS).map(c=>'<option value="'+c+'"'+(C.COLORS[c]===L.color?" selected":"")+'>'+c+'</option>').join("")+'</select></div>'});
  h+='</div><h4>Properties</h4><div id="cadprops">'+props()+'</div>';
  s.innerHTML=h;
}
function fld(k,l,v){return '<label>'+l+' <input data-prop="'+k+'" value="'+esc(C.fmtIn(v))+'" size="9"></label>'}
function props(){
  const D=C.doc;let h=fld("ceil","Ceiling",D.ceil)+fld("wallTh","Default wall",D.wallTh)+fld("grid","Grid",D.grid);
  const e=R.sel.length===1?C.byId(R.sel[0]):null;
  if(R.sel.length>1)h+='<p>'+R.sel.length+' objects selected</p>';
  if(e){h+='<hr><p><b>'+e.t.toUpperCase()+'</b> #'+e.id+' · layer '+esc(e.layer)+'</p>';
    const E=(k,l,u)=>'<label>'+l+' <input data-eprop="'+k+'" value="'+esc(typeof e[k]==="number"?C.fmtIn(e[k]):e[k])+'" size="9"></label>';
    if(e.t==="wall")h+=E("th","Thickness","in")+'<p>Length '+C.fmtIn(C.dist(e.a,e.b))+'</p>';
    if(e.t==="door"||e.t==="window")h+=E("w","Width","in")+E("pos","Offset from wall start","in")+E("sill","Sill height","in")+E("head","Head height","in");
    if(e.t==="outlet")h+=E("h","Height above floor","in");
    if(e.t==="text")h+=E("s","Text")+E("h","Height","in");
    if(e.t==="room")h+=E("name","Name")+'<p>'+esc(M.roomSize(e))+' · '+C.fmtArea(Math.abs(C.area(e.pts)))+'</p>';
    if(e.t==="fixture")h+=E("w","Width","in")+E("d","Depth","in");
    if(e.t==="line")h+='<p>Length '+C.fmtIn(C.dist(e.a,e.b))+'</p>';
    if(e.t==="circle")h+=E("r","Radius","in");}
  return h;
}
/* ---------- rendering ---------- */
function ltDash(t){return {CONTINUOUS:[],DASHED:[8,5],CENTER:[14,4,3,4],HIDDEN:[4,4]}[t]||[]}
function draw(){
  const cv=U.cv;if(!cv)return;const g=cv.getContext("2d"),D=C.doc;g.setTransform(U.dpr,0,0,U.dpr,0,0);g.lineJoin="round";g.lineCap="butt";
  g.fillStyle="#12151a";g.fillRect(0,0,U.w,U.h);
  if(U.grid){const st=D.grid*(U.s*D.grid<8?Math.ceil(8/(U.s*D.grid)):1);const a=toW(0,U.h),b=toW(U.w,0);const px=v=>Math.round(v*U.dpr)/U.dpr+.5/U.dpr;
    [[false,"#20262d"],[true,"#323a45"]].forEach(([major,col])=>{g.strokeStyle=col;g.lineWidth=1;g.beginPath();
      for(let i=Math.floor(a[0]/st);i*st<=b[0];i++){if((i%5===0)!==major)continue;const p=toS([i*st,0]);g.moveTo(px(p[0]),0);g.lineTo(px(p[0]),U.h)}
      for(let j=Math.floor(a[1]/st);j*st<=b[1];j++){if((j%5===0)!==major)continue;const p=toS([0,j*st]);g.moveTo(0,px(p[1]));g.lineTo(U.w,px(p[1]))}g.stroke()})}
  const o=toS([0,0]);g.strokeStyle="#6a3030";g.beginPath();g.moveTo(o[0],0);g.lineTo(o[0],U.h);g.stroke();g.strokeStyle="#306a30";g.beginPath();g.moveTo(0,o[1]);g.lineTo(U.w,o[1]);g.stroke();
  D.ents.forEach(e=>{if(!C.visible(e))return;drawEnt(g,e,R.sel.includes(e.id))});
  if(R._pending)R._pending.forEach(id=>{const e=C.byId(id);if(e)drawEnt(g,e,true)});
  if(U.drag&&U.drag.box){const a=toS(U.drag.a),b=toS(U.drag.b),cr=U.drag.b[0]<U.drag.a[0];g.save();g.strokeStyle=cr?"#40e070":"#5080ff";g.fillStyle=cr?"rgba(64,224,112,.12)":"rgba(80,128,255,.12)";if(cr)g.setLineDash([5,4]);g.fillRect(a[0],a[1],b[0]-a[0],b[1]-a[1]);g.strokeRect(a[0],a[1],b[0]-a[0],b[1]-a[1]);g.restore()}
  const q=R.req;if(q&&q.k==="pt"&&q.from&&U.cursor){const a=toS(q.from),b=toS(U.cursor);g.save();g.strokeStyle="#ffffff";g.setLineDash([4,4]);g.beginPath();g.moveTo(a[0],a[1]);g.lineTo(b[0],b[1]);g.stroke();g.restore();
    g.fillStyle="#ffe040";g.font="12px sans-serif";g.fillText(C.fmtIn(C.dist(q.from,U.cursor))+" ∠"+(Math.atan2(U.cursor[1]-q.from[1],U.cursor[0]-q.from[0])*180/Math.PI).toFixed(0)+"°",b[0]+12,b[1]-12)}
  if(U.cursor){const p=toS(U.cursor);g.strokeStyle="#9aa";g.lineWidth=1;g.beginPath();g.moveTo(0,p[1]);g.lineTo(U.w,p[1]);g.moveTo(p[0],0);g.lineTo(p[0],U.h);g.stroke();g.strokeRect(p[0]-4,p[1]-4,8,8);
    if(U.snapHit){g.strokeStyle="#ffe040";g.lineWidth=2;const k=U.snapHit;g.beginPath();
      if(k==="end")g.rect(p[0]-7,p[1]-7,14,14);else if(k==="mid"){g.moveTo(p[0],p[1]-8);g.lineTo(p[0]+8,p[1]+6);g.lineTo(p[0]-8,p[1]+6);g.closePath()}else if(k==="cen")g.arc(p[0],p[1],7,0,7);else if(k==="int"){g.moveTo(p[0]-7,p[1]-7);g.lineTo(p[0]+7,p[1]+7);g.moveTo(p[0]+7,p[1]-7);g.lineTo(p[0]-7,p[1]+7)}else if(k==="per"){g.moveTo(p[0]-7,p[1]+7);g.lineTo(p[0]-7,p[1]-7);g.moveTo(p[0]-7,p[1]+7);g.lineTo(p[0]+7,p[1]+7)}else g.rect(p[0]-3,p[1]-3,6,6);g.stroke()}}
  const cc=U.root.querySelector("#cadcoord");if(cc)cc.textContent=coordTxt();updateInteraction();
}
function drawEnt(g,e,hot){
  const L=C.doc.layers[e.layer]||{color:7,ltype:"CONTINUOUS"};const col=hot?"#ffffff":C.HEX[L.color];
  g.strokeStyle=col;g.fillStyle=col;g.lineWidth=hot?2:(L.lw||(e.layer==="A-WALL"?1.5:1));g.setLineDash(hot?[6,3]:ltDash(L.ltype));
  const P=p=>toS(p);
  const al=v=>{const d=U.dpr,w=Math.round(g.lineWidth*d),o=(w%2?.5:0);return (Math.round(v*d-o)+o)/d};
  const ln=(a,b)=>{const A=P(a),B=P(b);if(Math.abs(A[0]-B[0])<.01){A[0]=B[0]=al(A[0])}else if(Math.abs(A[1]-B[1])<.01){A[1]=B[1]=al(A[1])}g.beginPath();g.moveTo(A[0],A[1]);g.lineTo(B[0],B[1]);g.stroke()};
  if(e.t==="line")ln(e.a,e.b);
  else if(e.t==="pline"){g.beginPath();e.pts.forEach((p,i)=>{const s=P(p);i?g.lineTo(s[0],s[1]):g.moveTo(s[0],s[1])});if(e.closed)g.closePath();g.stroke()}
  else if(e.t==="circle"){const c=P(e.c);g.beginPath();g.arc(c[0],c[1],e.r*U.s,0,7);g.stroke()}
  else if(e.t==="arc"){const c=P(e.c);g.beginPath();g.arc(c[0],c[1],e.r*U.s,-C.rad(e.a0),-C.rad(e.a1),true);g.stroke()}
  else if(e.t==="hatch"){if((e.pat||"ANSI31")==="SOLID"){g.save();g.globalAlpha=.35;g.beginPath();e.pts.forEach((p,i)=>{const s=P(p);i?g.lineTo(s[0],s[1]):g.moveTo(s[0],s[1])});g.closePath();g.fill();g.restore()}else{g.lineWidth=hot?2:.6;g.setLineDash([]);C.hatchSegs(e).forEach(s=>ln(s[0],s[1]))}}
  else if(e.t==="wall"){const Ln=C.dist(e.a,e.b);if(!Ln)return;const nx=-(e.b[1]-e.a[1])/Ln*e.th/2,ny=(e.b[0]-e.a[0])/Ln*e.th/2;
    const q=[[e.a[0]+nx,e.a[1]+ny],[e.b[0]+nx,e.b[1]+ny],[e.b[0]-nx,e.b[1]-ny],[e.a[0]-nx,e.a[1]-ny]].map(P);g.save();g.fillStyle="#1d2128";g.beginPath();q.forEach((s,i)=>i?g.lineTo(s[0],s[1]):g.moveTo(s[0],s[1]));g.closePath();g.fill();g.restore();ln([e.a[0]+nx,e.a[1]+ny],[e.b[0]+nx,e.b[1]+ny]);ln([e.a[0]-nx,e.a[1]-ny],[e.b[0]-nx,e.b[1]-ny])}
  else if(e.t==="door"||e.t==="window"){const og=C.openGeom(e);if(!og)return;const th=og[3].th/2,u=og[2],n=[-u[1],u[0]];
    const c=(p,k)=>[p[0]+n[0]*th*k,p[1]+n[1]*th*k];const a=og[0],b=og[1];
    g.save();g.setLineDash([]);g.fillStyle="#12151a";const q=[c(a,1),c(b,1),c(b,-1),c(a,-1)].map(P);g.beginPath();q.forEach((s,i)=>i?g.lineTo(s[0],s[1]):g.moveTo(s[0],s[1]));g.closePath();g.fill();g.restore();
    g.setLineDash([]);
    if(e.t==="window"){ln(c(a,1),c(b,1));ln(c(a,-1),c(b,-1));ln(a,b)}
    else{const A=P(a);const r=e.w*U.s;const ang=Math.atan2(-u[1],u[0]);ln(a,[a[0]+n[0]*e.w,a[1]+n[1]*e.w]);g.beginPath();g.arc(A[0],A[1],r,ang-Math.PI/2,ang,false);g.stroke()}}
  else if(e.t==="outlet"){const c=P(e.p);g.beginPath();g.arc(c[0],c[1],4,0,7);g.moveTo(c[0]-6,c[1]);g.lineTo(c[0]+6,c[1]);g.stroke()}
  else if(e.t==="fixture"){const x=e.w/2,y=e.d/2;const a=P([e.p[0]-x,e.p[1]+y]),b=P([e.p[0]+x,e.p[1]-y]);g.strokeRect(a[0],a[1],b[0]-a[0],b[1]-a[1]);g.font="10px sans-serif";g.fillText(e.kind,a[0]+3,a[1]+12);if(e.kind==="stair"){for(let i=1;i<10;i++){const yy=a[1]+(b[1]-a[1])*i/10;g.beginPath();g.moveTo(a[0],yy);g.lineTo(b[0],yy);g.stroke()}}}
  else if(e.t==="room"){const cx=e.pts.reduce((s,p)=>s+p[0],0)/e.pts.length,cy=e.pts.reduce((s,p)=>s+p[1],0)/e.pts.length;const s=P([cx,cy]);g.font="12px sans-serif";g.textAlign="center";g.fillText(e.name,s[0],s[1]-8);g.fillText(M.roomSize(e).replace(/"/g,'"'),s[0],s[1]+6);g.fillText(C.fmtArea(Math.abs(C.area(e.pts))),s[0],s[1]+20);g.textAlign="left"}
  else if(e.t==="text"){const s=P(e.p);g.font=Math.max(8,e.h*U.s)+"px sans-serif";g.fillText(e.s,s[0],s[1])}
  else if(e.t==="dim"){const Ln=C.dist(e.a,e.b);if(!Ln)return;const nx=-(e.b[1]-e.a[1])/Ln*e.off,ny=(e.b[0]-e.a[0])/Ln*e.off;const a2=[e.a[0]+nx,e.a[1]+ny],b2=[e.b[0]+nx,e.b[1]+ny];ln(e.a,a2);ln(e.b,b2);ln(a2,b2);
    const A=P(a2),B=P(b2),ang=Math.atan2(B[1]-A[1],B[0]-A[0]);g.setLineDash([]);const ar=(p,d)=>{g.beginPath();g.moveTo(p[0],p[1]);g.lineTo(p[0]+d*9*Math.cos(ang)-d*3*Math.sin(ang),p[1]+d*9*Math.sin(ang)+d*3*Math.cos(ang));g.lineTo(p[0]+d*9*Math.cos(ang)+d*3*Math.sin(ang),p[1]+d*9*Math.sin(ang)-d*3*Math.cos(ang));g.closePath();g.fill()};ar(A,1);ar(B,-1);
    g.save();g.translate((A[0]+B[0])/2,(A[1]+B[1])/2);g.rotate(Math.cos(ang)<0?ang+Math.PI:ang);g.font="12px sans-serif";g.textAlign="center";g.fillText(C.fmtIn(Ln),0,-4);g.restore()}
  if(hot){const bb=C.bbox(e);if(bb){g.setLineDash([]);g.fillStyle="#5080ff";[[bb[0],bb[1]],[bb[2],bb[3]]].forEach(p=>{const s=P(p);g.fillRect(s[0]-3,s[1]-3,6,6)})}}
  g.setLineDash([]);
}
/* ---------- interaction ---------- */
function cursorFrom(ev){
  const r=U.cv.getBoundingClientRect(),x=ev.clientX-r.left,y=ev.clientY-r.top;let p=toW(x,y);
  const from=R.req&&R.req.k==="pt"?R.req.from:null;
  const tol=10/U.s;const sn=C.osnap(p,tol,{osnap:U.osnap,grid:U.snap,perp:U.osnap&&!!from,from});
  U.snapHit=sn.k;p=sn.p;
  if(!sn.k||sn.k==="grid"){if(from&&U.ortho)p=C.constrain(from,p,"ortho");else if(from&&U.polar)p=C.constrain(from,p,"polar")}
  U.cursor=p;R.cursor=p;return {p,x,y,raw:toW(x,y)};
}
function after(){refresh()}
function run(text){const ok=M.feed(text);if(R.viewReq)viewOp();after();return ok}
function viewOp(){
  const v=R.viewReq;R.viewReq=null;if(!v)return;
  if(v.op==="E")fit();else if(v.op==="IN")U.s*=1.5;else if(v.op==="OUT")U.s/=1.5;
  else if(v.op==="W")C.note("Window zoom: use the mouse wheel or ZOOM IN/OUT/E");
  else if(v.op==="3D"){if(v.k==="off")U.v3.on=false;else{const V=window.AcreCAD3D.VIEWS[v.k]||window.AcreCAD3D.VIEWS.iso;U.v3.on=true;U.v3.yaw=V.yaw;U.v3.pitch=V.pitch;U.v3.zoom=1}}
  else if(v.op==="PDF"){const r=window.AcreCADSheets.download({paper:C.doc.paper});C.note("PDF with "+r.pages+" page(s), "+r.paper+" ("+r.size[0]+" x "+r.size[1]+" in). Vector PDF; conceptual, not for construction.")}
  else if(v.op==="DXF"){const t=M.exportDXF();window.__cadLastDxf=t;const b=new Blob([t],{type:"application/dxf"}),a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="acreforge-cad-studio.dxf";document.body.appendChild(a);a.click();a.remove();C.note("DXF R12 exported ("+t.split("\r\n").length+" lines). DXF only; not DWG.")}
}
function fit(){
  let b=null;C.doc.ents.forEach(e=>{if(!C.visible(e))return;const x=C.bbox(e);if(!x)return;b=b?[Math.min(b[0],x[0]),Math.min(b[1],x[1]),Math.max(b[2],x[2]),Math.max(b[3],x[3])]:x});
  if(!b)return;U.cx=(b[0]+b[2])/2;U.cy=(b[1]+b[3])/2;U.s=Math.min(U.w/Math.max(60,(b[2]-b[0])*1.2),U.h/Math.max(60,(b[3]-b[1])*1.2));
}
function bind(){
  const root=U.root,cv=U.cv,inp=root.querySelector("#cadcmd");
  cv.addEventListener("mousemove",ev=>{if(U.drag&&U.drag.pan){U.cx-=(ev.clientX-U.drag.x)/U.s;U.cy+=(ev.clientY-U.drag.y)/U.s;U.drag.x=ev.clientX;U.drag.y=ev.clientY}
    const c=cursorFrom(ev);if(U.drag&&!U.drag.pan){U.drag.b=c.raw;if(Math.hypot(c.x-U.drag.sx,c.y-U.drag.sy)>4)U.drag.box=true}draw()});
  cv.addEventListener("mousedown",ev=>{cv.focus();if(ev.button===1){U.drag={pan:true,x:ev.clientX,y:ev.clientY};ev.preventDefault();return}
    if(ev.button===0){const c=cursorFrom(ev);U.drag={a:c.raw,b:c.raw,sx:c.x,sy:c.y,box:false,snapP:c.p}}});
  window.addEventListener("mouseup",ev=>{const d=U.drag;U.drag=null;if(!d)return;if(d.pan){after();return}if(ev.button!==0){after();return}
    const c=cursorFrom(ev);
    if(d.box){const ids=C.selectBox(d.a,c.raw,c.raw[0]<d.a[0]);M.windowSelect(ids);after();return}
    if(R.req&&R.req.k==="pt"){M.clickPoint(c.p);if(R.viewReq)viewOp();after();return}
    const e=C.pick(c.raw,8/U.s);
    if(R.req&&(R.req.k==="ent"||R.req.k==="sel")){if(e)M.clickEnt(e);after();return}
    if(!R.req){R.sel=e&&!C.locked(e)?(ev.shiftKey&&R.sel.length?Array.from(new Set(R.sel.concat(e.id))):[e.id]):[];after()}else after()});
  cv.addEventListener("contextmenu",ev=>{ev.preventDefault();run("")});
  const c3=U.root.querySelector("#cad3dcv");if(c3){let d3=null;c3.addEventListener("mousedown",ev=>{d3={x:ev.clientX,y:ev.clientY}});window.addEventListener("mouseup",()=>{d3=null});
    c3.addEventListener("mousemove",ev=>{if(!d3)return;U.v3.yaw+=(ev.clientX-d3.x)*0.5;U.v3.pitch=Math.max(0,Math.min(90,U.v3.pitch+(ev.clientY-d3.y)*0.5));d3={x:ev.clientX,y:ev.clientY};draw3d()});
    c3.addEventListener("wheel",ev=>{ev.preventDefault();U.v3.zoom=Math.max(0.3,Math.min(5,U.v3.zoom*(ev.deltaY<0?1.15:1/1.15)));draw3d()},{passive:false})}
  cv.addEventListener("wheel",ev=>{ev.preventDefault();const c=cursorFrom(ev);const f=ev.deltaY<0?1.2:1/1.2;U.s*=f;const w=toW(c.x,c.y);U.cx+=c.raw[0]-w[0];U.cy+=c.raw[1]-w[1];draw()},{passive:false});
  cv.addEventListener("mouseleave",()=>{U.cursor=null;U.snapHit=null;draw()});
  inp.addEventListener("keydown",ev=>{
    if(ev.key==="Enter"){const v=inp.value;inp.value="";if(v.trim()===""&&R.sel.length&&R.sel.length&&!R.gen&&!R.last){}run(v);ev.preventDefault()}
    else if(ev.key==="Escape"){M.cancel();R.sel=[];R._pending=null;inp.value="";C.note("*Cancel*");after()}
    else if(ev.key===" "&&inp.value.trim()===""&&R.gen==null){run("");ev.preventDefault()}
    else if(ev.key===" "&&R.req&&R.req.k==="sel"){run("");ev.preventDefault()}
  });
  root.addEventListener("click",ev=>{
    const b=ev.target.closest("[data-cmd]");if(b){M.cancel();run(b.dataset.cmd);inp.focus();return}
    const t=ev.target.closest("[data-tg]");if(t){U[t.dataset.tg]=!U[t.dataset.tg];refresh();return}
    if(ev.target.id==="cadfs"){U.full=!U.full;mount(U.root);return}
    if(ev.target.id==="caddxf"){run("DXF");return}
    const hl=ev.target.getAttribute&&ev.target.getAttribute("data-hl");if(hl){if(hl==="restore")C.restoreSession();else if(hl==="discard")C.discardSession();else if(hl==="backup")C.exportBackup();refresh();return}
    if(ev.target.id==="cad3d"){if(ev.__c3)return;ev.__c3=1;U.v3.on=!U.v3.on;refresh();return}
    const vv=ev.target.getAttribute&&ev.target.getAttribute("data-v3");if(vv){const V=window.AcreCAD3D.VIEWS[vv];U.v3.yaw=V.yaw;U.v3.pitch=V.pitch;U.v3.zoom=1;draw3d();return}
    if(ev.target.id==="cadpdf"){R.viewReq={op:"PDF"};viewOp();refresh();return}
    const l=ev.target.closest(".cadlay");if(l&&ev.target.closest("button")){const n=l.dataset.lay,L=C.doc.layers[n],a=ev.target.closest("button").dataset.act;C.snapshot();
      if(a==="set")C.doc.cur=n;if(a==="on")L.on=!L.on;if(a==="lock")L.lock=!L.lock;C.save();refresh()}
  });
  root.addEventListener("change",ev=>{
    if(ev.target.id==="cadpaper"){C.doc.paper=ev.target.value;C.save();return}
    if(ev.target.id==="cadunits"){C.setUnits(ev.target.value);C.note("Units: "+C.unit().n);refresh();return}
    if(ev.target.id==="cadprofile"){R.profile=ev.target.value;try{localStorage.setItem("acreforge-cad-profile",R.profile)}catch(e){}C.note("Profile: "+R.profile);refresh();return}
    if(ev.target.dataset.act==="lw"){const l=ev.target.closest(".cadlay");C.snapshot();C.doc.layers[l.dataset.lay].lw=+ev.target.value;C.save();refresh();return}
    const l=ev.target.closest(".cadlay");if(l&&ev.target.dataset.act){const L=C.doc.layers[l.dataset.lay];C.snapshot();if(ev.target.dataset.act==="ltype")L.ltype=ev.target.value;if(ev.target.dataset.act==="color")L.color=C.COLORS[ev.target.value];C.save();refresh();return}
    const p=ev.target.dataset.prop;if(p){const v=C.parseLen(ev.target.value);const lim={ceil:[48,240],wallTh:[2,36],grid:[1,120]}[p];if(isNaN(v)||v<lim[0]||v>lim[1]){C.note(p+" must be "+C.fmtIn(lim[0])+" to "+C.fmtIn(lim[1]))}else{C.doc[p]=v;C.save()}refresh();return}
    const k=ev.target.dataset.eprop;if(k){const e=C.byId(R.sel[0]);if(!e)return;const raw=ev.target.value;
      if(k==="s"||k==="name"){C.snapshot();e[k]=raw;C.save();refresh();return}
      const v=C.parseLen(raw);if(isNaN(v)){C.note("Invalid number");refresh();return}
      const lim={th:[2,36],w:[6,240],pos:[0,1e5],sill:[0,240],head:[12,240],h:[0,240],d:[6,240],r:[0.5,1e5]}[k]||[0,1e5];
      if(v<lim[0]||v>lim[1]){C.note(k+" must be "+C.fmtIn(lim[0])+" to "+C.fmtIn(lim[1]));refresh();return}
      if((e.t==="door"||e.t==="window")&&(k==="w"||k==="pos")){const wl=C.byId(e.wall),L=C.dist(wl.a,wl.b);const w2=k==="w"?v:e.w,p2=k==="pos"?v:e.pos;if(p2+w2>L+1e-6){C.note("Opening does not fit on the wall ("+C.fmtIn(L)+")");refresh();return}}
      C.snapshot();e[k]=v;C.save();refresh()}});
  if(!U.listeners){U.listeners=true;window.addEventListener("keydown",gkey)}
  const a=cv.getBoundingClientRect;
}
function gkey(ev){
  if(!document.getElementById("cadcv"))return;
  const t=ev.target,tag=t&&t.tagName;const typing=tag==="INPUT"&&t.id!=="cadcmd"||tag==="SELECT"||tag==="TEXTAREA";if(typing)return;
  const k=ev.key;
  if(R.profile==="USER"){const nm=(ev.ctrlKey?"Ctrl+":"")+(ev.shiftKey?"Shift+":"")+(k.length===1?k.toUpperCase():k);const act=M.USER_KEYS[nm];
    if(act&&!(t.id==="cadcmd"&&!ev.ctrlKey&&k!=="Home")){ev.preventDefault();if(act==="@ortho"){U.ortho=!U.ortho;refresh()}else if(act==="@snap"){U.snap=!U.snap;refresh()}else{M.cancel();run(act)}return}}
  const fx={F3:"osnap",F7:"grid",F8:"ortho",F9:"snap",F10:"polar"}[k];
  if(fx){U[fx]=!U[fx];ev.preventDefault();refresh();return}
  if(ev.ctrlKey&&!ev.shiftKey&&!ev.altKey&&k.toLowerCase()==="z"){ev.preventDefault();run("UNDO");return}
  if(ev.ctrlKey&&!ev.shiftKey&&!ev.altKey&&k.toLowerCase()==="y"){ev.preventDefault();run("REDO");return}
  if(ev.ctrlKey&&k.toLowerCase()==="a"&&t.id!=="cadcmd"){ev.preventDefault();run("SELECTALL");return}
  if(t.id==="cadcmd")return;
  if(k==="Escape"){M.cancel();R.sel=[];R._pending=null;C.note("*Cancel*");refresh();return}
  if(k==="Delete"&&R.sel.length&&!R.gen){run("ERASE");return}
  if(!ev.ctrlKey&&!ev.metaKey&&!ev.altKey&&k.length===1){const i=document.getElementById("cadcmd");if(i){i.focus()}}
}
setInterval(()=>{if(!U.root||!U.root.isConnected)return;if(C.health.storageFull||C.health.sev==="WARNING"&&C.health.msg.indexOf("save")>=0){const was=C.health.state;C.save();if(was!==C.health.state)healthUI()}else C.save()},20000);
window.AcreCAD={mount,state:U,run,fit,draw,refresh,core:C,cmd:M};
})();
