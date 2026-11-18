/* AcreForge CAD Studio sheets: auto elevations, roof model, section, vector PDF. Conceptual only. */
(function(){
"use strict";
const C=window.AcreCADCore;
const PAPER={Letter:[11,8.5],Legal:[14,8.5],"11x17":[17,11],"ARCH D":[36,24],"ARCH E":[48,36],A:[11,8.5],B:[17,11],A4:[11.69,8.27],A3:[16.54,11.69]};
const ROOFS=["gable","hip","shed","gambrel","barn"];
const SHEETS=[["cover","Cover"],["floor-plan","Floor plan"],["front-elevation","Front elevation"],["rear-elevation","Rear elevation"],["left-elevation","Left elevation"],["right-elevation","Right elevation"],["section-roof","Section and roof"],["foundation","Foundation plan"],["electrical","Electrical plan (concept)"],["plumbing","Plumbing plan (concept)"]];
const SHEET_IDS=new Set(SHEETS.map(([id])=>id));
const walls=()=>C.doc.ents.filter(e=>e.t==="wall");
function takeoff(){
  const ents=C.doc.ents,rooms=ents.filter(e=>e.t==="room"&&Array.isArray(e.pts)&&e.pts.length>=3);
  const w=ents.filter(e=>e.t==="wall"&&Array.isArray(e.a)&&Array.isArray(e.b));
  const floorAreaIn2=rooms.reduce((sum,e)=>{const a=Math.abs(C.area(e.pts));return sum+(Number.isFinite(a)?a:0)},0);
  const wallLengthIn=w.reduce((sum,e)=>{const n=C.dist(e.a,e.b);return sum+(Number.isFinite(n)?n:0)},0);
  const ceilingIn=Math.max(0,Number(C.doc.ceil)||0);
  return {roomCount:rooms.length,wallCount:w.length,floorAreaSqFt:floorAreaIn2/144,wallLengthFt:wallLengthIn/12,
    grossWallAreaSqFt:wallLengthIn*ceilingIn/144,doorCount:ents.filter(e=>e.t==="door").length,
    windowCount:ents.filter(e=>e.t==="window").length,ceilingIn};
}
function bbox(){
  const w=walls();if(!w.length)return null;
  let x0=1e18,y0=1e18,x1=-1e18,y1=-1e18;
  w.forEach(e=>[e.a,e.b].forEach(p=>{x0=Math.min(x0,p[0]);x1=Math.max(x1,p[0]);y0=Math.min(y0,p[1]);y1=Math.max(y1,p[1])}));
  return {x0,y0,x1,y1,w:x1-x0,d:y1-y0};
}
function availableSheets(){return (bbox()?SHEETS:SHEETS.slice(0,1)).map(([id,label])=>({id,label}))}
function roofCfg(){const r=C.doc.roof||{};return {type:ROOFS.includes(r.type)?r.type:"gable",pitch:r.pitch>0?r.pitch:6,ov:r.ov>=0?r.ov:12}}
/* Roof from footprint bounding box. Hip/gambrel/barn are simplified approximations. */
function roof(cfg){
  const b=bbox();if(!b)return null;cfg=Object.assign(roofCfg(),cfg||{});
  const ov=cfg.ov,p=cfg.pitch/12;
  const L=Math.max(b.w,b.d)+2*ov,S=Math.min(b.w,b.d)+2*ov;
  const sf=Math.sqrt(1+p*p);let area,ridge,rise;
  if(cfg.type==="gable"){rise=S/2*p;ridge=L;area=2*L*(S/2)*sf}
  else if(cfg.type==="hip"){rise=S/2*p;ridge=Math.max(0,L-S);area=L*S*sf}
  else if(cfg.type==="shed"){rise=S*p;ridge=L;area=L*S*sf}
  else{const fr=cfg.type==="barn"?0.3:0.25,mul=cfg.type==="barn"?3:2.5;const lr=S*fr,ur=S/2-lr;const lp=Math.min(p*mul,4);
    rise=lr*lp+ur*p;ridge=L;area=2*L*(lr*Math.sqrt(1+lp*lp)+ur*sf)}
  return {type:cfg.type,pitch:cfg.pitch,overhang:ov,span:S,length:L,rise,ridgeLength:ridge,area,ridgeHeight:C.doc.ceil+rise};
}
/* cross-section profile across span (x from -ov..S+ov, z above wall top) */
function profile(cfg,S0){
  const r=roof(cfg),ov=r.overhang,p=r.pitch/12,S=S0,d=ov*p;
  if(r.type==="gable"||r.type==="hip")return [[-ov,-d],[S/2,S/2*p],[S+ov,-d]];
  if(r.type==="shed")return [[-ov,-d],[S+ov,S*p]];
  const fr=r.type==="barn"?0.3:0.25,mul=r.type==="barn"?3:2.5,lp=Math.min(p*mul,4),lr=S*fr;
  const zk=lr*lp,zr=zk+(S/2-lr)*p;
  return [[-ov,-ov*lp],[lr,zk],[S/2,zr],[S-lr,zk],[S+ov,-ov*lp]];
}
const SIDES=["front","rear","left","right"];
/* side: front=south (min y) looking +y, rear=north, left=west, right=east */
function elevation(side){
  const b=bbox();if(!b)return null;const cfg=roofCfg(),r=roof(),H=C.doc.ceil;
  const horiz=side==="front"||side==="rear";
  const W=horiz?b.w:b.d;const ops=[];
  C.doc.ents.filter(e=>e.t==="door"||e.t==="window").forEach(o=>{
    const w=C.doc.ents.find(e=>e.id===o.wall&&e.t==="wall");if(!w)return;
    const dx=w.b[0]-w.a[0],dy=w.b[1]-w.a[1],len=Math.hypot(dx,dy)||1,ux=dx/len,uy=dy/len;
    const p0=[w.a[0]+ux*o.pos,w.a[1]+uy*o.pos],p1=[p0[0]+ux*o.w,p0[1]+uy*o.w];
    const isH=Math.abs(dx)>=Math.abs(dy);if(isH!==horiz)return;
    const mid=horiz?(w.a[1]+w.b[1])/2:(w.a[0]+w.b[0])/2;
    const cen=horiz?(b.y0+b.y1)/2:(b.x0+b.x1)/2;
    const near=side==="front"||side==="left"?mid<=cen:mid>cen;if(!near)return;
    const o0=horiz?p0[0]:p0[1],o1=horiz?p1[0]:p1[1];
    let a=Math.min(o0,o1)-(horiz?b.x0:b.y0),c=Math.max(o0,o1)-(horiz?b.x0:b.y0);
    if(side==="rear"||side==="right"){const t=a;a=W-c;c=W-t}
    ops.push({kind:o.t,x0:a,x1:c,z0:o.sill||0,z1:o.head||80});
  });
  const gableEnd=(horiz?b.w:b.d)<=(horiz?b.d:b.w);/* viewed width is the span */
  let roofPts;
  if(gableEnd||r.type==="shed"&&gableEnd){const pr=profile(null,W);roofPts=pr.map(q=>[q[0],H+q[1]])}
  else{const ov=r.overhang;roofPts=r.type==="hip"?[[-ov,H],[r.span/2,H+r.rise*0.98],[W+ov-r.span/2,H+r.rise*0.98],[W+ov,H]]:[[-ov,H],[-ov,H+(r.type==="shed"?r.rise:r.rise)],[W+ov,H+r.rise],[W+ov,H]];if(r.type==="hip")roofPts=[[-ov,H],[r.span/2-ov,H+r.rise],[W+ov-r.span/2+ov,H+r.rise],[W+ov,H]]}
  return {side,width:W,height:H,openings:ops,roof:roofPts,roofInfo:r,cfg};
}
function section(){
  const b=bbox();if(!b)return null;const S=Math.min(b.w,b.d);
  return {span:S,height:C.doc.ceil,wallTh:C.doc.wallTh,roof:profile(null,S).map(q=>[q[0],C.doc.ceil+q[1]]),roofInfo:roof()};
}
/* ---------- minimal vector PDF writer ---------- */
function esc(s){return String(s).replace(/[^\x20-\x7e]/g,"?").replace(/([\\()])/g,"\\$1")}
function f(n){return (Math.round(n*100)/100).toString()}
function Page(w,h,title,recordCommands){this.w=w;this.h=h;this.title=title;this.o=[];this.commands=recordCommands?[]:null}
Page.prototype={
  S(x){this.o.push(x)},
  lw(v){if(this.commands)this.commands.push({op:"width",value:v});this.S(f(v*72)+" w")},
  dash(a){if(this.commands)this.commands.push({op:"dash",values:a?a.slice():[]});this.S(a?"["+a.map(v=>f(v*72)).join(" ")+"] 0 d":"[] 0 d")},
  line(x1,y1,x2,y2){if(this.commands)this.commands.push({op:"path",points:[[x1,y1],[x2,y2]],closed:false});this.S(f(x1*72)+" "+f(y1*72)+" m "+f(x2*72)+" "+f(y2*72)+" l S")},
  poly(pts,closed){if(pts.length<2)return;if(this.commands)this.commands.push({op:"path",points:pts.map(q=>[q[0],q[1]]),closed:!!closed});this.S(pts.map((q,i)=>f(q[0]*72)+" "+f(q[1]*72)+(i?" l":" m")).join(" ")+(closed?" h S":" S"))},
  rect(x,y,w,h){if(this.commands)this.commands.push({op:"rect",x,y,w,h});this.S(f(x*72)+" "+f(y*72)+" "+f(w*72)+" "+f(h*72)+" re S")},
  text(x,y,s,size,bold,align){size=size||0.12;const value=String(s).replace(/[^\x20-\x7e]/g,"?"),wd=value.length*size*0.5;if(align==="c")x-=wd/2;else if(align==="r")x-=wd;if(this.commands)this.commands.push({op:"text",x,y,text:value,size,bold:!!bold});this.S("BT /"+(bold?"F2":"F1")+" "+f(size*72)+" Tf "+f(x*72)+" "+f(y*72)+" Td ("+esc(value)+") Tj ET")},
  circle(cx,cy,r){const pts=[];for(let i=0;i<36;i++){const a=i/36*Math.PI*2;pts.push([cx+r*Math.cos(a),cy+r*Math.sin(a)])}this.poly(pts,true)},
  arc(cx,cy,r,a0,a1){let e=a1;while(e<a0)e+=Math.PI*2;const n=Math.max(4,Math.ceil((e-a0)/(Math.PI/18))),pts=[];for(let i=0;i<=n;i++){const a=a0+(e-a0)*i/n;pts.push([cx+r*Math.cos(a),cy+r*Math.sin(a)])}this.poly(pts,false)}
};
function buildPDF(pages){
  const objs=[];const add=s=>{objs.push(s);return objs.length};
  add("<< /Type /Catalog /Pages 2 0 R >>");add("");
  add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>");add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>");
  const kids=[];
  pages.forEach(pg=>{
    const st="q 0 G 0 g 1 J 1 j\n"+pg.o.join("\n")+"\nQ";
    const ci=objs.length+2;
    const pi=add("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 "+f(pg.w*72)+" "+f(pg.h*72)+"] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents "+ci+" 0 R >>");
    add("<< /Length "+st.length+" >>\nstream\n"+st+"\nendstream");kids.push(pi+" 0 R");
  });
  objs[1]="<< /Type /Pages /Count "+kids.length+" /Kids ["+kids.join(" ")+"] >>";
  let out="%PDF-1.4\n";const off=[];
  objs.forEach((o,i)=>{off.push(out.length);out+=(i+1)+" 0 obj\n"+o+"\nendobj\n"});
  const x=out.length;out+="xref\n0 "+(objs.length+1)+"\n0000000000 65535 f \n"+off.map(v=>String(v).padStart(10,"0")+" 00000 n \n").join("")+"trailer\n<< /Size "+(objs.length+1)+" /Root 1 0 R >>\nstartxref\n"+x+"\n%%EOF\n";
  return out;
}
/* ---------- sheet drawing ---------- */
const STD=[1,2,4,8,12,16,24,32,48,64,96,128,192,256,384,512,768,1024];
function fitScale(wIn,hIn,aw,ah){for(const n of STD)if(wIn/n<=aw&&hIn/n<=ah)return n;return 2048}
function frame(pg,i,n,title,scaleTxt,north){
  const m=0.4,w=pg.w,h=pg.h,tb=Math.min(1.1,h*0.14);
  pg.lw(0.02);pg.dash(null);pg.rect(m,m,w-2*m,h-2*m);pg.lw(0.01);pg.rect(m,m,w-2*m,tb);
  const fs=Math.min(0.16,w/70);
  pg.text(m+0.15,m+tb-0.3,(C.doc.title||"AcreForge CAD Studio project"),fs*1.3,true);
  pg.text(m+0.15,m+tb-0.3-fs*1.5,title,fs,false);
  pg.text(w-m-0.15,m+tb-0.3,"Sheet "+i+" of "+n,fs,true,"r");
  pg.text(w-m-0.15,m+tb-0.3-fs*1.5,"Units: inches",fs,false,"r");
  pg.text(w/2,m+0.12,"CONCEPTUAL DRAFT - NOT FOR CONSTRUCTION. DXF/PDF only; no DWG. AcreForge is free.",fs*0.75,false,"c");
  if(north){const cx=w-m-0.6,cy=h-m-0.8;pg.circle(cx,cy,0.3);pg.line(cx,cy-0.3,cx,cy+0.45);pg.poly([[cx-0.1,cy+0.2],[cx,cy+0.45],[cx+0.1,cy+0.2]],true);pg.text(cx,cy+0.52,"N",0.16,true,"c")}
  return {x:m+0.3,y:m+tb+0.3,w:w-2*m-0.6,h:h-2*m-tb-0.6};
}
function mapper(box,bx0,by0,bw,bh,n){const sx=bw/n,sy=bh/n,ox=box.x+(box.w-sx)/2,oy=box.y+(box.h-sy)/2;return {n,X:v=>ox+(v-bx0)/n,Y:v=>oy+(v-by0)/n}}
function drawPlan(pg,box,mode){
  const b=bbox();const pad=60;
  const bw=b.w+2*pad,bh=b.d+2*pad;const n=fitScale(bw,bh,box.w,box.h);
  const m=mapper(box,b.x0-pad,b.y0-pad,bw,bh,n);
  walls().forEach(e=>{
    const dx=e.b[0]-e.a[0],dy=e.b[1]-e.a[1],L=Math.hypot(dx,dy)||1,nx=-dy/L*e.th/2,ny=dx/L*e.th/2;
    pg.lw(0.02);pg.dash(null);
    pg.poly([[m.X(e.a[0]+nx),m.Y(e.a[1]+ny)],[m.X(e.b[0]+nx),m.Y(e.b[1]+ny)],[m.X(e.b[0]-nx),m.Y(e.b[1]-ny)],[m.X(e.a[0]-nx),m.Y(e.a[1]-ny)]],true);
    if(mode==="found"){pg.dash([0.08,0.04]);pg.lw(0.008);pg.line(m.X(e.a[0]),m.Y(e.a[1]),m.X(e.b[0]),m.Y(e.b[1]));pg.dash(null)}
  });
  if(mode==="found"){return m}
  C.doc.ents.forEach(e=>{
    pg.lw(0.01);pg.dash(null);
    if(e.t==="door"||e.t==="window"){
      const w=C.doc.ents.find(q=>q.id===e.wall);if(!w)return;
      const dx=w.b[0]-w.a[0],dy=w.b[1]-w.a[1],L=Math.hypot(dx,dy)||1,ux=dx/L,uy=dy/L;
      const p=[w.a[0]+ux*e.pos,w.a[1]+uy*e.pos],q=[p[0]+ux*e.w,p[1]+uy*e.w];
      pg.lw(0.015);pg.line(m.X(p[0]),m.Y(p[1]),m.X(q[0]),m.Y(q[1]));
      if(e.t==="door")pg.arc(m.X(p[0]),m.Y(p[1]),e.w/n,Math.atan2(uy,ux),Math.atan2(uy,ux)+Math.PI/2);
      pg.text(m.X((p[0]+q[0])/2),m.Y((p[1]+q[1])/2)+0.06,e.t==="door"?"D":"W",0.1,false,"c");
    }else if(e.t==="room"){
      const xs=e.pts.map(q=>q[0]),ys=e.pts.map(q=>q[1]),w=Math.max(...xs)-Math.min(...xs),d=Math.max(...ys)-Math.min(...ys);
      const cx=m.X((Math.min(...xs)+Math.max(...xs))/2),cy=m.Y((Math.min(...ys)+Math.max(...ys))/2);
      pg.text(cx,cy+0.1,e.name||"Room",0.13,true,"c");
      pg.text(cx,cy-0.06,C.fmtIn(w)+" x "+C.fmtIn(d),0.1,false,"c");
      pg.text(cx,cy-0.2,Math.round(w*d)+" sq in",0.1,false,"c");
    }else if(e.t==="fixture"){
      pg.rect(m.X(e.p[0]-e.w/2),m.Y(e.p[1]-e.d/2),e.w/n,e.d/n);pg.text(m.X(e.p[0]),m.Y(e.p[1])-0.03,e.kind,0.08,false,"c");
    }else if(e.t==="line"){pg.line(m.X(e.a[0]),m.Y(e.a[1]),m.X(e.b[0]),m.Y(e.b[1]))}
    else if(e.t==="circle"){pg.circle(m.X(e.c[0]),m.Y(e.c[1]),e.r/n)}
    else if(e.t==="text"){pg.text(m.X(e.p[0]),m.Y(e.p[1]),e.s,Math.max(0.08,e.h/n))}
    else if(e.t==="dim"){const L=C.dist(e.a,e.b);pg.line(m.X(e.a[0]),m.Y(e.a[1]),m.X(e.b[0]),m.Y(e.b[1]));pg.text(m.X((e.a[0]+e.b[0])/2),m.Y((e.a[1]+e.b[1])/2)+0.05,C.fmtIn(L),0.1,false,"c")}
  });
  return m;
}
function drawElev(pg,box,el){
  const ov=el.roofInfo.overhang;
  const top=Math.max(...el.roof.map(q=>q[1]),el.height);
  const bw=el.width+2*ov+120,bh=top+60;const n=fitScale(bw,bh,box.w,box.h);
  const sx=box.x+(box.w-bw/n)/2+(ov+60)/n,sy=box.y+(box.h-bh/n)/2+30/n;
  const X=v=>sx+v/n,Y=v=>sy+v/n;
  pg.lw(0.012);pg.dash(null);pg.line(X(-ov-60),Y(0),X(el.width+ov+60),Y(0));
  pg.lw(0.02);pg.rect(X(0),Y(0),el.width/n,el.height/n);
  pg.poly(el.roof.map(q=>[X(q[0]),Y(q[1])]),false);
  el.openings.forEach(o=>{pg.lw(0.015);pg.rect(X(o.x0),Y(o.z0),(o.x1-o.x0)/n,(o.z1-o.z0)/n);
    if(o.kind==="window"){pg.lw(0.008);pg.line(X((o.x0+o.x1)/2),Y(o.z0),X((o.x0+o.x1)/2),Y(o.z1))}
    pg.text(X((o.x0+o.x1)/2),Y(o.z1)+0.05,o.kind==="door"?"DOOR":"WIN",0.08,false,"c")});
  pg.lw(0.008);pg.dash([0.06,0.04]);pg.line(X(0),Y(el.height),X(el.width),Y(el.height));pg.dash(null);
  pg.text(X(el.width)+0.1,Y(el.height),"Ceiling "+C.fmtIn(el.height),0.1);
  pg.text(X(el.width/2),Y(0)-0.2,"Width "+C.fmtIn(el.width),0.11,false,"c");
  return n;
}
function drawSection(pg,box,s){
  const ov=s.roofInfo.overhang,top=Math.max(...s.roof.map(q=>q[1]));
  const bw=s.span+2*ov+120,bh=top+80;const n=fitScale(bw,bh,box.w,box.h);
  const sx=box.x+(box.w-bw/n)/2+(ov+60)/n,sy=box.y+(box.h-bh/n)/2+40/n;
  const X=v=>sx+v/n,Y=v=>sy+v/n,t=s.wallTh;
  pg.lw(0.012);pg.line(X(-ov-60),Y(0),X(s.span+ov+60),Y(0));
  pg.lw(0.02);pg.rect(X(-t/2),Y(0),t/n,s.height/n);pg.rect(X(s.span-t/2),Y(0),t/n,s.height/n);
  pg.line(X(-t/2),Y(s.height),X(s.span+t/2),Y(s.height));
  pg.poly(s.roof.map(q=>[X(q[0]),Y(q[1])]),false);
  pg.text(X(s.span/2),Y(s.height)-0.2,"Ceiling "+C.fmtIn(s.height),0.11,false,"c");
  pg.text(X(s.span/2),Y(0)-0.22,"Floor / foundation level (concept)",0.11,false,"c");
  return n;
}
/* Pages: cover, floor plan, 4 elevations, section+roof, foundation, electrical concept, plumbing concept */
function build(opts,capture){
  if(capture)capture.drawings=[];
  opts=opts||{};const size=PAPER[opts.paper]?opts.paper:"Letter";const [w,h]=PAPER[size];
  const available=new Set(availableSheets().map(sheet=>sheet.id));
  let selected=null;
  if(opts.sheets!==undefined){
    if(!Array.isArray(opts.sheets))return {pdf:"",pages:0,paper:size,size:[w,h],failed:[],message:"PDF sheet selection must be a list.",sheets:[]};
    selected=new Set(opts.sheets);
    if([...selected].some(id=>!SHEET_IDS.has(id)))return {pdf:"",pages:0,paper:size,size:[w,h],failed:[],message:"PDF sheet selection contains an unknown sheet.",sheets:[]};
    if([...selected].some(id=>!available.has(id)))return {pdf:"",pages:0,paper:size,size:[w,h],failed:[],message:"A selected PDF sheet is unavailable for this drawing.",sheets:[]};
    if(!selected.size)return {pdf:"",pages:0,paper:size,size:[w,h],failed:[],message:"Select at least one PDF sheet.",sheets:[]};
  }
  const b=bbox();const pages=[];const r=roof(),own=[];
  const mk=(id,title,fn,north)=>{if(selected&&!selected.has(id))return;const pg=new Page(w,h,title,!!capture);pg.sheetId=id;own.push([pg,title,fn,north]);pages.push(pg)};
  mk("cover","Cover",(pg,box)=>{
    pg.text(box.x+0.2,box.y+box.h-0.5,C.doc.title||"AcreForge CAD Studio project",0.35,true);
    pg.text(box.x+0.2,box.y+box.h-0.95,"Conceptual drawing set (inches) - not construction documents",0.16);
    pg.text(box.x+0.2,box.y+box.h-1.3,"Paper: "+size+"   Date: "+new Date().toISOString().slice(0,10),0.14);
    if(b){pg.text(box.x+0.2,box.y+box.h-1.7,"Footprint "+C.fmtIn(b.w)+" x "+C.fmtIn(b.d)+"   Ceiling "+C.fmtIn(C.doc.ceil),0.14);
      pg.text(box.x+0.2,box.y+box.h-2.0,"Roof: "+r.type+", "+r.pitch+"/12, area "+Math.round(r.area)+" sq in, ridge "+C.fmtIn(r.ridgeLength),0.14)}
    else pg.text(box.x+0.2,box.y+box.h-1.7,"No walls drawn yet.",0.14);
    const included=selected?SHEETS.filter(([id])=>selected.has(id)&&id!=="cover").map(([,label])=>label).join(", ")||"none":"floor plan, 4 elevations, section/roof, foundation, electrical concept, plumbing concept";
    pg.text(box.x+0.2,box.y+box.h-2.4,"Sheets: "+included+".",0.12);
  },false);
  if(b){
    mk("floor-plan","Floor plan",(pg,box)=>drawPlan(pg,box).n,true);
    SIDES.forEach(s=>mk(s+"-elevation",s[0].toUpperCase()+s.slice(1)+" elevation",(pg,box)=>drawElev(pg,box,elevation(s)),false));
    mk("section-roof","Section and roof ("+r.type+" "+r.pitch+"/12, area "+Math.round(r.area)+" sq in, ridge "+C.fmtIn(r.ridgeLength)+")",(pg,box)=>drawSection(pg,box,section()),false);
    mk("foundation","Foundation plan (concept)",(pg,box)=>drawPlan(pg,box,"found").n,true);
    mk("electrical","Electrical plan (CONCEPT)",(pg,box)=>{const m=drawPlan(pg,box,"found");C.doc.ents.filter(e=>e.t==="outlet").forEach(e=>{pg.circle(m.X(e.p[0]),m.Y(e.p[1]),0.05)});return m.n},true);
    mk("plumbing","Plumbing plan (CONCEPT)",(pg,box)=>{const m=drawPlan(pg,box,"found");C.doc.ents.filter(e=>e.t==="fixture"&&e.layer==="P-PLMB").forEach(e=>{pg.rect(m.X(e.p[0]-e.w/2),m.Y(e.p[1]-e.d/2),e.w/m.n,e.d/m.n);pg.text(m.X(e.p[0]),m.Y(e.p[1]),e.kind,0.08,false,"c")});return m.n},true);
  }
  const failed=[];
  own.forEach(([pg,title,fn,north],i)=>{
    try{
      if(opts.failSheet&&title.toLowerCase().indexOf(String(opts.failSheet).toLowerCase())>=0)throw new Error("test");
      const box=frame(pg,i+1,own.length,title,"see note",north);
      const n=fn(pg,box);pg._n=n;
      pg.text(pg.w-0.55,0.4+Math.min(1.1,pg.h*0.14)-0.3-Math.min(0.16,pg.w/70)*3,"Scale: "+(n?"1:"+n:"NTS"),Math.min(0.16,pg.w/70),true,"r");
    }catch(e){failed.push(title);const k=pages.indexOf(pg);if(k>0)pages.splice(k,1)}
  });
  let message="";
  if(failed.length){message=pages.length+" of "+own.length+" sheets generated. "+failed.join(", ")+" could not be created. The rest of your set is complete and your drawing is unchanged.";if(C.setHealth)C.setHealth("WARNING",message)}
  if(capture)capture.drawings=pages;
  const txt=capture?"":buildPDF(pages);
  return {pdf:txt,pages:pages.length,paper:size,size:[w,h],failed,message,sheets:pages.map(pg=>pg.sheetId)};
}
function pdfBlob(pdf){
  const bytes=new Uint8Array(pdf.length);for(let i=0;i<pdf.length;i++)bytes[i]=pdf.charCodeAt(i)&255;
  return new Blob([bytes],{type:"application/pdf"});
}
function preview(opts){
  const r=build(opts);if(!r.pdf)return {...r,url:""};
  return {...r,url:URL.createObjectURL(pdfBlob(r.pdf))};
}
function download(opts){
  const r=build(opts);if(!r.pdf)return r;
  window.__cadLastPdf=r.pdf;
  const a=document.createElement("a");a.href=URL.createObjectURL(pdfBlob(r.pdf));a.download="acreforge-cad-sheets.pdf";document.body.appendChild(a);a.click();a.remove();
  return r;
}
function drawPNGPage(ctx,page,dpi){
  const xy=(x,y)=>[x*dpi,(page.h-y)*dpi];
  ctx.save();ctx.strokeStyle="#000";ctx.fillStyle="#000";ctx.lineCap="round";ctx.lineJoin="round";
  page.commands.forEach(command=>{
    if(command.op==="width"){ctx.lineWidth=command.value*dpi;return}
    if(command.op==="dash"){ctx.setLineDash(command.values.map(value=>value*dpi));return}
    if(command.op==="path"){
      ctx.beginPath();command.points.forEach((point,index)=>{const p=xy(point[0],point[1]);if(index)ctx.lineTo(p[0],p[1]);else ctx.moveTo(p[0],p[1])});
      if(command.closed)ctx.closePath();ctx.stroke();return
    }
    if(command.op==="rect"){ctx.strokeRect(command.x*dpi,(page.h-command.y-command.h)*dpi,command.w*dpi,command.h*dpi);return}
    if(command.op==="text"){
      ctx.font=(command.bold?"bold ":"")+command.size*dpi+"px Helvetica, Arial, sans-serif";
      ctx.textBaseline="alphabetic";const p=xy(command.x,command.y);ctx.fillText(command.text,p[0],p[1])
    }
  });
  ctx.restore()
}
async function renderPNG(opts){
  if(!opts||!Array.isArray(opts.sheets)||opts.sheets.length!==1){
    const paper=opts&&PAPER[opts.paper]?opts.paper:"Letter";
    return {blob:null,pages:0,paper,size:PAPER[paper],failed:[],message:"PNG export requires exactly one selected sheet.",sheets:[]}
  }
  const capture={},r=build(opts,capture),page=capture.drawings[0];
  if(!page)return {blob:null,pages:0,paper:r.paper,size:r.size,failed:r.failed,message:r.message||"The selected sheet could not be created.",sheets:[]};
  const dpi=Math.min(96,4096/page.w,4096/page.h),width=Math.max(1,Math.round(page.w*dpi)),height=Math.max(1,Math.round(page.h*dpi)),
    canvas=document.createElement("canvas");
  canvas.width=width;canvas.height=height;
  const ctx=canvas.getContext("2d");
  if(!ctx)return {blob:null,pages:0,paper:r.paper,size:r.size,failed:r.failed,message:"PNG rendering is unavailable in this browser.",sheets:[]};
  ctx.fillStyle="#fff";ctx.fillRect(0,0,width,height);drawPNGPage(ctx,page,dpi);
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,"image/png"));
  if(!blob)return {blob:null,pages:0,paper:r.paper,size:r.size,failed:r.failed,message:"The browser could not encode this PNG.",sheets:[]};
  return {blob,pages:1,paper:r.paper,size:r.size,failed:r.failed,message:r.message,sheets:r.sheets,width,height,dpi};
}
async function downloadPNG(opts){
  const r=await renderPNG(opts);if(!r.blob)return r;
  const url=URL.createObjectURL(r.blob),a=document.createElement("a");a.href=url;a.download="acreforge-cad-"+r.sheets[0]+".png";document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
  return r;
}
window.AcreCADSheets={PAPER,ROOFS,availableSheets,bbox,takeoff,roof,roofCfg,elevation,section,build,preview,download,renderPNG,downloadPNG,buildPDF,Page};
})();
