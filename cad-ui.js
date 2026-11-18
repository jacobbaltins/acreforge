/* AcreForge CAD Studio UI: dark model-space canvas, snaps, panels, command line. Conceptual only. */
(function(){
"use strict";
const C=window.AcreCADCore,M=window.AcreCADCmd,R=M.R;
const U={v3:{on:false,yaw:35,pitch:28,zoom:1},osnap:true,grid:true,snap:false,ortho:false,polar:false,cx:120,cy:90,s:2,w:800,h:500,dpr:1,mx:0,my:0,snapHit:null,drag:null,interaction:"READY",root:null,cv:null,fresh:true,listeners:false,full:false,importedDXF:null,toolFilter:"",rootListenerController:null,pdfPreviewUrl:null};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const toS=p=>[(p[0]-U.cx)*U.s+U.w/2,U.h/2-(p[1]-U.cy)*U.s];
const toW=(x,y)=>[(x-U.w/2)/U.s+U.cx,U.cy-(y-U.h/2)/U.s];
const INTERACTION_TRANSITIONS=[
  {from:"*",event:"COMMAND_READY",to:"READY"},
  {from:"*",event:"COMMAND_CANCELLED",to:"READY"},
  {from:"*",event:"COMMAND_SELECTED",to:"SELECTED"},
  {from:"*",event:"COMMAND_WORKING",to:"COMMAND"},
  {from:"*",event:"REQUEST_POINT",to:"POINT"},
  {from:"*",event:"REQUEST_NUMBER",to:"NUMBER"},
  {from:"*",event:"REQUEST_OPTION",to:"OPTION"},
  {from:"*",event:"REQUEST_TEXT",to:"TEXT"},
  {from:"*",event:"REQUEST_OBJECT",to:"OBJECT"},
  {from:"*",event:"REQUEST_SELECTION",to:"SELECTION"},
  {from:["READY","SELECTED","COMMAND","POINT","NUMBER","OPTION","TEXT","OBJECT","SELECTION"],event:"DRAG_START",to:"DRAG"},
  {from:"*",event:"PAN_START",to:"PAN"},
  {from:["DRAG","WINDOW","CROSSING"],event:"WINDOW_MOVE",to:"WINDOW"},
  {from:["DRAG","WINDOW","CROSSING"],event:"CROSSING_MOVE",to:"CROSSING"},
  {from:["PAN","DRAG","WINDOW","CROSSING"],event:"POINTER_UP",to:"READY"}
];
const INTERACTION_LABELS={READY:"Ready",SELECTED:"Selection ready",COMMAND:"Working",POINT:"Pick point",NUMBER:"Enter number",OPTION:"Choose option",TEXT:"Enter text",OBJECT:"Pick object",SELECTION:"Select objects",PAN:"Panning",DRAG:"Selecting",WINDOW:"Window select",CROSSING:"Crossing select"};
function applyInteractionTransition(event){
  const rule=INTERACTION_TRANSITIONS.find(t=>(t.from==="*"||t.from.includes(U.interaction))&&t.event===event);
  if(!rule)return false;
  U.interaction=rule.to;updateInteraction();return true
}
function syncInteraction(){
  const request=R.req&&({pt:"REQUEST_POINT",num:"REQUEST_NUMBER",kw:"REQUEST_OPTION",str:"REQUEST_TEXT",ent:"REQUEST_OBJECT",sel:"REQUEST_SELECTION"}[R.req.k]);
  applyInteractionTransition(request|| (R.gen?"COMMAND_WORKING":R.sel.length?"COMMAND_SELECTED":"COMMAND_READY"))
}
function updateInteraction(){
  const el=U.root&&U.root.querySelector("#cadmode"),label="Mode: "+INTERACTION_LABELS[U.interaction];
  if(el){if(el.textContent!==label){el.textContent=label;el.dataset.state=U.interaction}}
}
function filterTools(value){
  const term=String(value||"").trim().toLowerCase(),root=U.root;
  if(!root)return;
  let visible=0;
  root.querySelectorAll(".cadgrp").forEach(group=>{
    let groupVisible=0;
    group.querySelectorAll("[data-cmd]").forEach(button=>{
      const match=!term||(button.dataset.cmd+" "+button.textContent).toLowerCase().includes(term);
      button.hidden=!match;
      if(match){visible++;groupVisible++}
    });
    group.hidden=groupVisible===0;
  });
  const status=root.querySelector("#cadtoolfilterstatus");
  if(status){status.hidden=!term||visible>0;status.textContent="No CAD commands match “"+String(value).trim()+"”."}
}
function quickBuildDialog(){
  return '<dialog id="cadquickbuild" aria-labelledby="cadquickbuildtitle" aria-describedby="cadquickbuilddescription"><h3 id="cadquickbuildtitle">Quick Build Wizard</h3><p id="cadquickbuilddescription">Create an editable rectangular building concept without using command prompts. New geometry is appended beside the current drawing and can be removed with one Undo.</p><div class="quickbuildfields"><label>Plan name <input id="cadquickbuildname" maxlength="40" value="Quick Build"></label><label>Room layout <select id="cadquickbuildlayout"><option value="open">Open plan · 1 room</option><option value="two">Two rooms</option><option value="three">Three rooms</option></select></label><label>Outside width (ft) <input id="cadquickbuildwidth" type="number" min="18" max="200" step="1" value="40"></label><label>Outside depth (ft) <input id="cadquickbuilddepth" type="number" min="18" max="200" step="1" value="30"></label></div><p class="cadexportlimit">Adds 6 in conceptual walls, room labels, one 36 in door, and one 36 in window. Dimensions are converted to drawing inches. No building code, structure, egress, or construction details are evaluated.</p><p id="cadquickbuildstatus" role="status" aria-live="polite"></p><div class="cadexportactions"><button class="btn" id="cadquickbuildcancel" type="button">Cancel</button><button class="btn" id="cadquickbuildgo" type="button">Add plan</button></div></dialog>';
}
function mount(root){
  if(!root)return;releasePdfPreview();U.root=root;
  root.innerHTML='<div id="cadwrap" class="cadwrap'+(U.full?" cadfull":"")+'">'+
  '<div class="cadtop"><b>📐 CAD Studio</b> <span id="cadmodes"></span> <span class="cadspc"></span><button class="btn" id="cad3d" type="button" aria-pressed="false" title="Show a linked 3D model beside the plan">Split 3D</button><button class="btn" id="cadfs" type="button">'+(U.full?"Exit full view":"Full viewport")+'</button><button class="btn" id="cadtakeoffopen" type="button">Takeoffs / cost</button><button class="btn" id="cadimportopen" type="button">Import DXF…</button><button class="btn" id="cadexportopen" type="button">Export…</button></div>'+
  '<dialog id="cadexport" aria-labelledby="cadexporttitle" aria-describedby="cadexportdescription"><h3 id="cadexporttitle">Export drawing</h3><p>Choose a file format for this CAD Studio drawing.</p><label>File format <select id="cadexportformat"><option value="pdf">PDF drawing set</option><option value="png">PNG sheet</option><option value="dxf">R12 DXF</option></select></label><label id="cadexportpaperwrap">Paper size <select id="cadexportpaper" aria-label="PDF or PNG paper size">'+Object.keys(window.AcreCADSheets.PAPER).map(k=>'<option'+(C.doc.paper===k?' selected':'')+'>'+k+'</option>').join('')+'</select></label><fieldset id="cadexportsheetswrap" style="border:1px solid #ccd5dc;border-radius:8px;margin:12px 0;padding:10px"><legend>Drawing sheets</legend><div id="cadexportsheets"></div></fieldset><p id="cadexportdescription" role="status" aria-live="polite"></p><p class="cadexportlimit">Downloads are created locally. Files are conceptual, not construction documents; DXF is not DWG.</p><div class="cadexportactions"><button class="btn" id="cadexportcancel" type="button">Cancel</button><button class="btn" id="cadexportpreview" type="button">Preview PDF</button><button class="btn" id="cadexportgo" type="button">Download PDF</button></div></dialog>'+
  '<dialog id="cadpdfpreview" aria-labelledby="cadpdfpreviewtitle" aria-describedby="cadpdfpreviewstatus" style="width:min(96vw,1200px);max-width:96vw;height:90vh;box-sizing:border-box"><h3 id="cadpdfpreviewtitle">PDF drawing preview</h3><p id="cadpdfpreviewstatus" role="status" aria-live="polite"></p><iframe id="cadpdfpreviewframe" title="Local PDF drawing preview" referrerpolicy="no-referrer" style="display:block;width:100%;height:min(72vh,800px);border:1px solid #ccd5dc;border-radius:8px"></iframe><p class="cadexportlimit">Preview is generated locally in this browser. PDF display depends on browser support.</p><div class="cadexportactions"><button class="btn" id="cadpdfpreviewclose" type="button">Close preview</button></div></dialog>'+
  '<input id="cadimportfile" type="file" accept=".dxf,application/dxf,text/plain" hidden><dialog id="cadimport" aria-labelledby="cadimporttitle" aria-describedby="cadimportstatus"><h3 id="cadimporttitle">Import 2D DXF</h3><p>Only ASCII R12 LINE, straight-segment 2D POLYLINE, CIRCLE, ARC, and TEXT entities are imported. Geometry is appended to the current drawing; nothing is replaced. Coordinates are converted to inches. Source layers are prefixed with DXF-; layer 0 maps to the existing layer 0.</p><p class="cadexportlimit">Unsupported entities are skipped. Curved polyline segments and non-XY or nonzero-Z geometry are rejected. Imported walls, doors, windows, dimensions, and hatches are ordinary supported primitives, not editable CAD objects. Local file only; no upload.</p><p id="cadimportstatus" role="status" aria-live="polite">Choose a DXF file to preview.</p><div class="cadexportactions"><button class="btn" id="cadimportcancel" type="button">Cancel</button><button class="btn" id="cadimportchoose" type="button">Choose file</button><button class="btn" id="cadimportgo" type="button" disabled>Add to drawing</button></div></dialog>'+
  '<dialog id="cadtakeoff" aria-labelledby="cadtakeofftitle" aria-describedby="cadtakeoffdescription"><h3 id="cadtakeofftitle">Conceptual takeoffs and cost allowance</h3><p id="cadtakeoffdescription">Quantities are derived from the current CAD drawing. Enter your own unit rates to calculate an allowance for those categories.</p><table class="cadtakeofftable"><thead><tr><th>Category</th><th>Quantity</th><th>Unit</th><th>Rate (USD)</th><th>Allowance</th></tr></thead><tbody><tr><th scope="row">Floor area</th><td data-quantity="floor"></td><td>sq ft</td><td><input type="number" min="0" max="1000000" step="0.01" data-rate="floor" aria-label="Floor finish rate per square foot"></td><td data-cost="floor"></td></tr><tr><th scope="row">Wall length</th><td data-quantity="wallLength"></td><td>ft</td><td>—</td><td data-cost="wallLength">Not priced</td></tr><tr><th scope="row">Gross wall area</th><td data-quantity="wall"></td><td>sq ft</td><td><input type="number" min="0" max="1000000" step="0.01" data-rate="wall" aria-label="Wall rate per square foot"></td><td data-cost="wall"></td></tr><tr><th scope="row">Doors</th><td data-quantity="door"></td><td>each</td><td><input type="number" min="0" max="1000000" step="0.01" data-rate="door" aria-label="Door rate each"></td><td data-cost="door"></td></tr><tr><th scope="row">Windows</th><td data-quantity="window"></td><td>each</td><td><input type="number" min="0" max="1000000" step="0.01" data-rate="window" aria-label="Window rate each"></td><td data-cost="window"></td></tr></tbody></table><p id="cadtakeofftotal" role="status" aria-live="polite"></p><p class="cadexportlimit">Gross wall area is wall centerline length × drawing ceiling height; openings are not deducted. Overlapping rooms can double-count floor area. Hidden layers are included. Blank rates are excluded from the subtotal. No market prices, labor, waste, engineering, or code checks are supplied; this is not a bid.</p><div class="cadexportactions"><button class="btn" id="cadtakeoffclose" type="button">Close</button><button class="btn" id="cadtakeoffcsv" type="button">Download takeoff CSV</button></div></dialog>'+
  '<div class="cadmain"><div id="cadtools" class="cadtools"></div><div class="cadcvwrap"><canvas id="cadcv" tabindex="0"></canvas></div><div id="cad3dwrap" class="cad3dwrap" hidden><canvas id="cad3dcv" tabindex="0" aria-label="3D model of your plan. Drag to orbit, wheel to zoom."></canvas><div class="viewcube" role="group" aria-label="3D view buttons">'+Object.keys(window.AcreCAD3D.VIEWS).map(k=>'<button type="button" class="btn" data-v3="'+k+'">'+window.AcreCAD3D.VIEWS[k].label+'</button>').join("")+'</div><div class="cad3dnote">Concept block model from your plan. Not an engineered model.</div></div><div id="cadside" class="cadside"></div></div>'+
  '<div id="cadhealth" class="cadhealth" role="status" aria-live="polite"></div>'+
  '<div id="cadlog" class="cadlog" aria-live="polite"></div>'+
  '<div class="cadcmdrow"><label for="cadcmd" id="cadprompt">Command:</label><input id="cadcmd" autocomplete="off" spellcheck="false" aria-label="CAD command line" placeholder="Type LINE, WALL, ROOM, DOOR… or HELP"></div>'+
  '<div id="cadstatus" class="cadstatus"></div>'+
  '<details id="cadhelp"><summary>Commands, hotkeys &amp; limits</summary><div id="cadhelptxt"></div></details></div>';
  root.insertAdjacentHTML("beforeend",quickBuildDialog());
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
  U.root.querySelector("#cadtools").innerHTML='<label class="cadtoolfilter"><span>Find a command</span><input id="cadtoolfilter" type="search" aria-label="Filter CAD commands" placeholder="Filter commands" autocomplete="off" value="'+esc(U.toolFilter)+'"></label><div id="cadtoolfilterstatus" class="cadtoolfilterstatus" role="status" aria-live="polite" hidden></div><button type="button" class="btn" id="cadquickbuildopen">Quick Build…</button>'+G.map(g=>'<div class="cadgrp"><span class="cadgl">'+g[0]+'</span>'+g[1].map(t=>'<button type="button" class="btn" data-cmd="'+t[0]+'">'+t[1]+'</button>').join("")+'</div>').join("");
  filterTools(U.toolFilter);
  U.root.querySelector("#cadhelptxt").innerHTML='<p>'+esc(M.HELP)+'</p><p><b>Hotkeys:</b> F3 object snap · F7 grid · F8 ortho · F9 grid snap · F10 polar · Esc cancel · Enter/Space repeat last command · Del erase selection · Ctrl+Z / Ctrl+Y undo/redo · Ctrl+A select all · Home zoom extents (User profile) · right-click = Enter · wheel zoom · middle-drag pan. Drag right = window select, drag left = crossing select.</p><p><b>Limits:</b> Conceptual drafting only. DXF R12 export and limited ASCII R12 import; no DWG. No DWG/AutoCAD compatibility claim. Not construction-grade, no code compliance. Snaps: endpoint, midpoint, center, intersection (line-to-line), perpendicular, grid. TRIM, EXTEND and FILLET work on LINEs only; OFFSET works on lines, walls, circles and arcs; HATCH is a simple line pattern (ANSI31, CROSS, SOLID) in the DXF as exploded lines; lineweights show on screen only (DXF R12 has none); doors and windows follow their walls and are skipped by MOVE/COPY/ROTATE/MIRROR/SCALE. Units: inches by default; UNITS switches display/input to mm, cm or m (geometry and DXF stay in inches); feet-and-inches notation is not accepted. Not yet implemented: additional DXF entity types, grips, ZOOM window, editable in-workspace elevation/section/layout views, DWG. ELEV and ROOF reports feed the conceptual PDF sheets; linked Split 3D is a simplified visual model.</p><p><b>User profile</b> (PROFILE command or the selector): aliases C=CIRCLE, R=RECT; Ctrl+Shift+C circle, Ctrl+Shift+T text, Ctrl+Shift+M mirror, Ctrl+Shift+F fillet, Ctrl+R ortho, Ctrl+Shift+P grid snap, Home zoom extents. Some browsers reserve Ctrl+Shift shortcuts. "+esc(M.USER_UNMAPPED)+"</p>';
}
function layout(){const w=U.root.querySelector(".cadcvwrap");if(!w)return;U.w=Math.max(300,w.clientWidth);U.h=Math.max(280,w.clientHeight);U.dpr=Math.max(1,window.devicePixelRatio||1);U.cv.width=Math.round(U.w*U.dpr);U.cv.height=Math.round(U.h*U.dpr);U.cv.style.width=U.w+"px";U.cv.style.height=U.h+"px"}
function healthUI(){const el=U.root.querySelector("#cadhealth");if(!el)return;const h=C.health;
  if(h.crashed){el.innerHTML='<div class="cadmodal cadh-RECOVERY" role="alertdialog" aria-label="Restore previous session"><b>AcreForge closed unexpectedly.</b> Restore previous session? Your last saved drawing is kept either way. <button class="btn" type="button" data-hl="restore">Restore</button> <button class="btn" type="button" data-hl="discard">Discard</button></div>';return}
  const n=h.state;el.innerHTML='<span class="cadh cadh-'+n+'">'+n+'</span> '+esc(h.msg||"Valid. Saved in this browser (local-first; cloud sync is a future feature).")+(h.storageFull?' <button class="btn" type="button" data-hl="backup">Download backup</button>':"")}
function draw3d(){const w=U.root&&U.root.querySelector("#cad3dwrap"),b=U.root&&U.root.querySelector("#cad3d");if(!w)return;w.hidden=!U.v3.on;if(b)b.setAttribute("aria-pressed",String(U.v3.on));if(!U.v3.on)return;
  const cv=w.querySelector("canvas");try{U.v3.last=window.AcreCAD3D.render(cv,U.v3,Math.max(1,window.devicePixelRatio||1));U.v3.err=false}catch(e){U.v3.err=true;C.devlog&&C.devlog("3d_failure "+e.message);C.setHealth("WARNING","Updating 3D model... Showing the plan only for now. Your drawing is unchanged.")}}
function refresh(){if(!U.drag)syncInteraction();panels();status();healthUI();prompt();draw();draw3d()}
function releasePdfPreview(){
  const frame=U.root&&U.root.querySelector("#cadpdfpreviewframe");
  if(frame)frame.src="about:blank";
  if(U.pdfPreviewUrl)URL.revokeObjectURL(U.pdfPreviewUrl);
  U.pdfPreviewUrl=null;
}
function previewPDF(){
  releasePdfPreview();
  const d=U.root.querySelector("#cadexport"),sheets=[...d.querySelectorAll("[data-cad-export-sheet]:checked")].map(input=>input.value);
  const r=window.AcreCADSheets.preview({paper:d.querySelector("#cadexportpaper").value,sheets});
  const status=U.root.querySelector("#cadpdfpreviewstatus");
  if(!r.url){status.textContent=r.message||"PDF preview could not be created.";return}
  U.pdfPreviewUrl=r.url;
  status.textContent="Previewing "+r.pages+" selected conceptual PDF sheet(s) on "+r.paper+" paper."+(r.failed.length?" Some sheets could not be created: "+r.failed.join(", ")+".":"");
  U.root.querySelector("#cadpdfpreviewframe").src=r.url;
  U.root.querySelector("#cadpdfpreview").showModal();
}
function updateExportDetails(){
  const d=U.root&&U.root.querySelector("#cadexport");if(!d)return;
  const format=d.querySelector("#cadexportformat").value,pdf=format==="pdf",png=format==="png",hasSheets=pdf||png;
  const selected=d.querySelectorAll("[data-cad-export-sheet]:checked").length,total=d.querySelectorAll("[data-cad-export-sheet]").length;
  d.querySelector("#cadexportpaperwrap").hidden=!hasSheets;
  d.querySelector("#cadexportsheetswrap").hidden=!hasSheets;
  d.querySelector("#cadexportpreview").hidden=!pdf;
  d.querySelector("#cadexportpreview").disabled=!selected;
  d.querySelector("#cadexportdescription").textContent=pdf
    ?(selected?"Creates "+selected+" of "+total+" selected conceptual vector-PDF sheets using "+d.querySelector("#cadexportpaper").value+" paper.":"Select at least one PDF sheet.")
    :png
      ?(selected===1?"Creates one local PNG drawing sheet using "+d.querySelector("#cadexportpaper").value+" paper, at up to 96 DPI.":"Select exactly one drawing sheet for PNG export.")
      :"Creates an R12 DXF of model-space entities. Geometry remains in inches; this is not a DWG file.";
  d.querySelector("#cadexportgo").textContent=pdf?"Download PDF":png?"Download PNG":"Download DXF";
  d.querySelector("#cadexportgo").disabled=pdf?!selected:png?selected!==1:false;
}
function renderExportSheets(){
  const list=U.root&&U.root.querySelector("#cadexportsheets");if(!list)return;
  list.innerHTML=window.AcreCADSheets.availableSheets().map(sheet=>'<label style="display:inline-flex;align-items:center;gap:6px;margin:4px 12px 4px 0"><input type="checkbox" data-cad-export-sheet value="'+esc(sheet.id)+'" checked> '+esc(sheet.label)+'</label>').join("");
}
const TAKEOFF_ITEMS=[
  {key:"floor",label:"Floor area",quantity:"floorAreaSqFt",unit:"sq ft"},
  {key:"wallLength",label:"Wall length",quantity:"wallLengthFt",unit:"ft",rated:false},
  {key:"wall",label:"Gross wall area",quantity:"grossWallAreaSqFt",unit:"sq ft"},
  {key:"door",label:"Doors",quantity:"doorCount",unit:"each"},
  {key:"window",label:"Windows",quantity:"windowCount",unit:"each"}
];
const takeoffNumber=n=>Number(n||0).toLocaleString("en-US",{maximumFractionDigits:2});
const takeoffMoney=n=>new Intl.NumberFormat("en-US",{style:"currency",currency:"USD"}).format(n);
function updateTakeoffs(){
  const d=U.root&&U.root.querySelector("#cadtakeoff");if(!d)return;
  const q=window.AcreCADSheets.takeoff(),rates=C.doc.takeoffRates||{};let subtotal=0,configured=0;
  TAKEOFF_ITEMS.forEach(i=>{
    const qty=q[i.quantity],raw=i.rated===false?null:rates[i.key],rate=raw===null||raw===undefined||raw===""?null:Number(raw);
    const amount=i.rated!==false&&rate!==null&&Number.isFinite(rate)&&rate>=0&&rate<=1000000?qty*rate:null;
    if(amount!==null){subtotal+=amount;configured++}
    d.querySelector('[data-quantity="'+i.key+'"]').textContent=takeoffNumber(qty);
    d.querySelector('[data-cost="'+i.key+'"]').textContent=amount===null?(i.rated===false?"Not priced":"—"):takeoffMoney(amount);
  });
  d.querySelector("#cadtakeofftotal").textContent=configured
    ?"Configured-category subtotal: "+takeoffMoney(subtotal)+". Categories without rates are excluded."
    :"Enter one or more non-negative rates to calculate a partial allowance.";
}
function openTakeoffs(){
  const d=U.root.querySelector("#cadtakeoff"),rates=C.doc.takeoffRates||{};
  d.querySelectorAll("[data-rate]").forEach(el=>{const n=rates[el.dataset.rate];el.value=n===null||n===undefined?"":String(n)});
  updateTakeoffs();if(!d.open)d.showModal();
}
function downloadTakeoffCSV(){
  const q=window.AcreCADSheets.takeoff(),rates=C.doc.takeoffRates||{};
  const cell=v=>{const s=String(v===null||v===undefined?"":v);return /[",]/.test(s)||s.indexOf(String.fromCharCode(10))>=0||s.indexOf(String.fromCharCode(13))>=0?'"'+s.replace(/"/g,'""')+'"':s};
  const rows=[["Category","Quantity","Unit","Rate (USD/unit)","Allowance (USD)"]];
  TAKEOFF_ITEMS.forEach(i=>{const raw=i.rated===false?null:rates[i.key],rate=raw===null||raw===undefined||raw===""?null:Number(raw);
    const valid=i.rated!==false&&rate!==null&&Number.isFinite(rate)&&rate>=0&&rate<=1000000;rows.push([i.label,takeoffNumber(q[i.quantity]),i.unit,valid?rate:"",valid?takeoffMoney(q[i.quantity]*rate):""])});
  rows.push(["Note","Conceptual quantities only; gross wall area does not deduct openings.","","",""]);
  rows.push(["Note","User-entered rates only; blank-rate categories are excluded from the subtotal.","","",""]);
  const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([rows.map(r=>r.map(cell).join(",")).join(String.fromCharCode(13,10))],{type:"text/csv;charset=utf-8"}));
  a.download="acreforge-cad-takeoff.csv";document.body.appendChild(a);a.click();a.remove();C.note("Concept takeoff CSV downloaded locally.");after();
}
function createQuickBuild(){
  const d=U.root.querySelector("#cadquickbuild"),status=d.querySelector("#cadquickbuildstatus"),name=d.querySelector("#cadquickbuildname").value.trim();
  const widthFt=Number(d.querySelector("#cadquickbuildwidth").value),depthFt=Number(d.querySelector("#cadquickbuilddepth").value),layout=d.querySelector("#cadquickbuildlayout").value;
  if(!name||name.length>40){status.textContent="Enter a plan name from 1 to 40 characters.";return}
  if(!Number.isFinite(widthFt)||widthFt<18||widthFt>200||!Number.isFinite(depthFt)||depthFt<18||depthFt>200){status.textContent="Width and depth must each be from 18 to 200 feet.";return}
  if(!["open","two","three"].includes(layout)){status.textContent="Choose one of the available room layouts.";return}
  const D=C.doc,layers=["A-WALL","A-ROOM","A-DOOR","A-GLAZ"];
  const unavailable=layers.filter(n=>!D.layers[n]||D.layers[n].lock||!D.layers[n].on);
  if(unavailable.length){status.textContent="Turn on and unlock these layers before building: "+unavailable.join(", ")+". The drawing was not changed.";return}
  let maxX=-Infinity,minY=Infinity;
  D.ents.forEach(e=>{const b=C.bbox(e);if(b){maxX=Math.max(maxX,b[2]);minY=Math.min(minY,b[1])}});
  const x0=Number.isFinite(maxX)?maxX+120:0,y0=Number.isFinite(minY)?minY:0;
  const w=widthFt*12,h=depthFt*12;
  if(!Number.isFinite(x0+w)||!Number.isFinite(y0+h)||Math.max(Math.abs(x0),Math.abs(x0+w),Math.abs(y0),Math.abs(y0+h))>1e7){status.textContent="There is not enough coordinate range beside this drawing for the selected plan.";return}
  const perimeter=[[x0,y0],[x0+w,y0],[x0+w,y0+h],[x0,y0+h]];
  M.cancel();R.sel=[];
  C.snapshot();
  const add=entity=>{entity.id=D.nid++;D.ents.push(entity);return entity};
  const outer=perimeter.map((a,i)=>add({t:"wall",a,b:perimeter[(i+1)%4],th:D.wallTh,layer:"A-WALL"}));
  add({t:"door",wall:outer[0].id,pos:(w-36)/2,w:36,sill:0,head:80,layer:"A-DOOR"});
  add({t:"window",wall:outer[2].id,pos:(w-36)/2,w:36,sill:36,head:80,layer:"A-GLAZ"});
  const rooms=[];
  if(layout==="open")rooms.push({name:name,pts:perimeter});
  else if(layout==="two"){
    const x=x0+w/2;add({t:"wall",a:[x,y0],b:[x,y0+h],th:D.wallTh,layer:"A-WALL"});
    rooms.push({name:name+" · Room 1",pts:[[x0,y0],[x,y0],[x,y0+h],[x0,y0+h]]});
    rooms.push({name:name+" · Room 2",pts:[[x,y0],[x0+w,y0],[x0+w,y0+h],[x,y0+h]]});
  }else{
    const x=x0+w*0.58,y=y0+h/2;add({t:"wall",a:[x,y0],b:[x,y0+h],th:D.wallTh,layer:"A-WALL"});
    add({t:"wall",a:[x,y],b:[x0+w,y],th:D.wallTh,layer:"A-WALL"});
    rooms.push({name:name+" · Room 1",pts:[[x0,y0],[x,y0],[x,y0+h],[x0,y0+h]]});
    rooms.push({name:name+" · Room 2",pts:[[x,y0],[x0+w,y0],[x0+w,y],[x,y]]});
    rooms.push({name:name+" · Room 3",pts:[[x,y],[x0+w,y],[x0+w,y0+h],[x,y0+h]]});
  }
  rooms.forEach(room=>add({t:"room",pts:room.pts,name:room.name,layer:"A-ROOM"}));
  const saved=C.save();
  U.cx=x0+w/2;U.cy=y0+h/2;U.s=Math.min(U.w/(w*1.25),U.h/(h*1.25));
  d.close();
  C.note((saved?"":"Quick Build is on screen but could not be saved. ")+name+" concept added; one Undo removes it. Conceptual only, not for construction.");
  after();
}
function prompt(){const p=U.root.querySelector("#cadprompt"),l=U.root.querySelector("#cadlog");if(p)p.textContent=R.prompt;if(l){l.innerHTML=C.log.slice(-6).map(esc).join("<br>");l.scrollTop=l.scrollHeight}}
function status(){
  const t=(k,l,on)=>'<button type="button" class="btn'+(on?" on":"")+'" data-tg="'+k+'" aria-pressed="'+on+'">'+l+'</button>';
  const c=U.root.querySelector("#cadstatus");
  const mode=U.interaction;
  c.innerHTML='<span id="cadcoord">'+coordTxt()+'</span> <span id="cadmode" data-state="'+mode+'" aria-live="polite">Mode: '+INTERACTION_LABELS[mode]+'</span> '+t("osnap","OSNAP F3",U.osnap)+t("grid","GRID F7",U.grid)+t("ortho","ORTHO F8",U.ortho)+t("snap","SNAP F9",U.snap)+t("polar","POLAR F10",U.polar)+' <span>Layer: <b>'+esc(C.doc.cur)+'</b> · Sel: '+R.sel.length+' · Ceiling '+C.fmtIn(C.doc.ceil)+' · Wall '+C.fmtIn(C.doc.wallTh)+'</span> <label>Units <select id="cadunits" aria-label="Display units">'+Object.keys(C.UNITS).map(k=>'<option value="'+k+'"'+(C.doc.units===k?' selected':'')+'>'+k+'</option>').join('')+'</select></label> <label>Profile <select id="cadprofile" aria-label="Keyboard profile"><option value="DEFAULT"'+(R.profile==="DEFAULT"?' selected':'')+'>Default</option><option value="USER"'+(R.profile==="USER"?' selected':'')+'>User</option></select></label>';
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
  else if(v.op==="PDF"){const r=window.AcreCADSheets.download({paper:C.doc.paper,sheets:v.sheets});C.note(r.message||("PDF with "+r.pages+" page(s), "+r.paper+" ("+r.size[0]+" x "+r.size[1]+" in). Vector PDF; conceptual, not for construction."))}
  else if(v.op==="DXF"){const t=M.exportDXF();window.__cadLastDxf=t;const b=new Blob([t],{type:"application/dxf"}),a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="acreforge-cad-studio.dxf";document.body.appendChild(a);a.click();a.remove();C.note("DXF R12 exported ("+t.split("\r\n").length+" lines). DXF only; not DWG.")}
}
function fit(){
  let b=null;C.doc.ents.forEach(e=>{if(!C.visible(e))return;const x=C.bbox(e);if(!x)return;b=b?[Math.min(b[0],x[0]),Math.min(b[1],x[1]),Math.max(b[2],x[2]),Math.max(b[3],x[3])]:x});
  if(!b)return;U.cx=(b[0]+b[2])/2;U.cy=(b[1]+b[3])/2;U.s=Math.min(U.w/Math.max(60,(b[2]-b[0])*1.2),U.h/Math.max(60,(b[3]-b[1])*1.2));
}
function bind(){
  const root=U.root,cv=U.cv,inp=root.querySelector("#cadcmd");
  if(U.rootListenerController)U.rootListenerController.abort();
  U.rootListenerController=new AbortController();
  const rootListenerOptions={signal:U.rootListenerController.signal};
  cv.addEventListener("mousemove",ev=>{if(U.drag&&U.drag.pan){U.cx-=(ev.clientX-U.drag.x)/U.s;U.cy+=(ev.clientY-U.drag.y)/U.s;U.drag.x=ev.clientX;U.drag.y=ev.clientY}
    const c=cursorFrom(ev);if(U.drag&&!U.drag.pan){U.drag.b=c.raw;if(Math.hypot(c.x-U.drag.sx,c.y-U.drag.sy)>4){U.drag.box=true;applyInteractionTransition(U.drag.b[0]<U.drag.a[0]?"CROSSING_MOVE":"WINDOW_MOVE")}}draw()});
  cv.addEventListener("mousedown",ev=>{cv.focus();if(ev.button===1){U.drag={pan:true,x:ev.clientX,y:ev.clientY};applyInteractionTransition("PAN_START");ev.preventDefault();return}
    if(ev.button===0){const c=cursorFrom(ev);U.drag={a:c.raw,b:c.raw,sx:c.x,sy:c.y,box:false,snapP:c.p};applyInteractionTransition("DRAG_START")}});
  window.addEventListener("mouseup",ev=>{const d=U.drag;U.drag=null;if(!d)return;applyInteractionTransition("POINTER_UP");if(d.pan){after();return}if(ev.button!==0){after();return}
    const c=cursorFrom(ev);
    if(d.box||Math.hypot(c.x-d.sx,c.y-d.sy)>4){const ids=C.selectBox(d.a,c.raw,c.raw[0]<d.a[0]);M.windowSelect(ids);after();return}
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
    else if(ev.key==="Escape"){M.cancel();R.sel=[];R._pending=null;inp.value="";applyInteractionTransition("COMMAND_CANCELLED");C.note("*Cancel*");after()}
    else if(ev.key===" "&&inp.value.trim()===""&&R.gen==null){run("");ev.preventDefault()}
    else if(ev.key===" "&&R.req&&R.req.k==="sel"){run("");ev.preventDefault()}
  });
  root.addEventListener("click",ev=>{
    const b=ev.target.closest("[data-cmd]");if(b){M.cancel();run(b.dataset.cmd);inp.focus();return}
    const t=ev.target.closest("[data-tg]");if(t){U[t.dataset.tg]=!U[t.dataset.tg];refresh();return}
    if(ev.target.id==="cadfs"){U.full=!U.full;mount(U.root);return}
    if(ev.target.id==="cadquickbuildopen"){root.querySelector("#cadquickbuildstatus").textContent="";root.querySelector("#cadquickbuild").showModal();return}
    if(ev.target.id==="cadquickbuildcancel"){root.querySelector("#cadquickbuild").close();return}
    if(ev.target.id==="cadquickbuildgo"){createQuickBuild();return}
    if(ev.target.id==="cadtakeoffopen"){openTakeoffs();return}
    if(ev.target.id==="cadtakeoffclose"){root.querySelector("#cadtakeoff").close();return}
    if(ev.target.id==="cadtakeoffcsv"){downloadTakeoffCSV();return}
    if(ev.target.id==="cadimportopen"||ev.target.id==="cadimportchoose"){root.querySelector("#cadimportfile").click();return}
    if(ev.target.id==="cadimportcancel"){root.querySelector("#cadimport").close();U.importedDXF=null;return}
    if(ev.target.id==="cadimportgo"){
      if(!U.importedDXF)return;
      try{const result=M.commitDXFImport(U.importedDXF);U.importedDXF=null;root.querySelector("#cadimport").close();
        C.note("Imported "+result.added+" DXF entities; skipped "+result.skipped+" unsupported records.");after()}
      catch(e){root.querySelector("#cadimportstatus").textContent=e.message}
      return
    }
    if(ev.target.id==="cadexportopen"){const d=root.querySelector("#cadexport");root.querySelector("#cadexportpaper").value=window.AcreCADSheets.PAPER[C.doc.paper]?C.doc.paper:"Letter";root.querySelector("#cadexportformat").value="pdf";renderExportSheets();updateExportDetails();if(!d.open)d.showModal();return}
    if(ev.target.id==="cadexportcancel"){root.querySelector("#cadexport").close();return}
    if(ev.target.id==="cadexportpreview"){previewPDF();return}
    if(ev.target.id==="cadpdfpreviewclose"){releasePdfPreview();root.querySelector("#cadpdfpreview").close();return}
    if(ev.target.id==="cadexportgo"){
      const d=root.querySelector("#cadexport"),format=root.querySelector("#cadexportformat").value;
      if(format==="png"){
        const paper=d.querySelector("#cadexportpaper").value,sheets=[...d.querySelectorAll("[data-cad-export-sheet]:checked")].map(input=>input.value);
        d.close();
        window.AcreCADSheets.downloadPNG({paper,sheets}).then(r=>{
          if(!r.blob){C.note(r.message||"PNG export could not be created.");return}
          C.doc.paper=paper;C.save();C.note("PNG sheet download started locally ("+r.width+" × "+r.height+" pixels).")
        }).catch(e=>C.note("PNG export failed: "+e.message));
        return
      }
      if(format==="pdf"){C.doc.paper=root.querySelector("#cadexportpaper").value;C.save()}
      d.close();      R.viewReq={op:format==="dxf"?"DXF":"PDF",sheets:format==="pdf"?[...d.querySelectorAll("[data-cad-export-sheet]:checked")].map(input=>input.value):undefined};viewOp();after();return
    }
    const hl=ev.target.getAttribute&&ev.target.getAttribute("data-hl");if(hl){if(hl==="restore")C.restoreSession();else if(hl==="discard")C.discardSession();else if(hl==="backup")C.exportBackup();refresh();return}
    if(ev.target.id==="cad3d"){if(ev.__c3)return;ev.__c3=1;U.v3.on=!U.v3.on;refresh();return}
    const vv=ev.target.getAttribute&&ev.target.getAttribute("data-v3");if(vv){const V=window.AcreCAD3D.VIEWS[vv];U.v3.yaw=V.yaw;U.v3.pitch=V.pitch;U.v3.zoom=1;draw3d();return}
    const l=ev.target.closest(".cadlay");if(l&&ev.target.closest("button")){const n=l.dataset.lay,L=C.doc.layers[n],a=ev.target.closest("button").dataset.act;C.snapshot();
      if(a==="set")C.doc.cur=n;if(a==="on")L.on=!L.on;if(a==="lock")L.lock=!L.lock;C.save();refresh()}
  },rootListenerOptions);
  root.addEventListener("input",ev=>{
    if(ev.target.id!=="cadtoolfilter")return;
    U.toolFilter=ev.target.value;
    filterTools(U.toolFilter);
  },rootListenerOptions);
  root.querySelector("#cadpdfpreview").addEventListener("close",releasePdfPreview);
  root.addEventListener("change",async ev=>{
    if(ev.target.id==="cadimportfile"){
      const input=ev.target,file=input.files&&input.files[0],d=root.querySelector("#cadimport"),go=root.querySelector("#cadimportgo"),status=root.querySelector("#cadimportstatus");
      U.importedDXF=null;go.disabled=true;input.value="";
      if(!file)return;
      if(file.size>5*1024*1024){status.textContent="DXF files must be 5 MiB or smaller.";if(!d.open)d.showModal();return}
      status.textContent="Reading and validating "+file.name+" locally…";if(!d.open)d.showModal();
      try{
        const parsed=M.parseDXF(await file.text());U.importedDXF=parsed;
        status.textContent=parsed.entities.length
          ?parsed.entities.length+" supported entities are ready; "+parsed.skipped+" unsupported records will be skipped. Units: "+parsed.units+". Adding will preserve the current drawing."
          :"No supported 2D entities found. No drawing changes will be made.";
        go.disabled=!parsed.entities.length;
      }catch(e){status.textContent="Import not ready: "+e.message}
      return
    }
    if(ev.target.dataset.rate){
      const key=ev.target.dataset.rate,raw=ev.target.value.trim(),rate=raw===""?null:Number(raw);
      if(rate!==null&&(!Number.isFinite(rate)||rate<0||rate>1000000)){root.querySelector("#cadtakeofftotal").textContent="Enter a rate from $0 to $1,000,000.";return}
      if(!C.doc.takeoffRates||typeof C.doc.takeoffRates!=="object"||Array.isArray(C.doc.takeoffRates))C.doc.takeoffRates={floor:null,wall:null,door:null,window:null};
      C.doc.takeoffRates[key]=rate;C.save();updateTakeoffs();return
    }
    if(ev.target.id==="cadexportformat"||ev.target.id==="cadexportpaper"||ev.target.matches("[data-cad-export-sheet]")){updateExportDetails();return}
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
      C.snapshot();e[k]=v;C.save();refresh()}},rootListenerOptions);
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
  if(k==="Escape"){M.cancel();R.sel=[];R._pending=null;applyInteractionTransition("COMMAND_CANCELLED");C.note("*Cancel*");refresh();return}
  if(k==="Delete"&&R.sel.length&&!R.gen){run("ERASE");return}
  if(!ev.ctrlKey&&!ev.metaKey&&!ev.altKey&&k.length===1){const i=document.getElementById("cadcmd");if(i){i.focus()}}
}
setInterval(()=>{if(!U.root||!U.root.isConnected)return;if(C.health.storageFull||C.health.sev==="WARNING"&&C.health.msg.indexOf("save")>=0){const was=C.health.state;C.save();if(was!==C.health.state)healthUI()}else C.save()},20000);
window.AcreCAD={mount,state:U,run,fit,draw,refresh,core:C,cmd:M};
})();
