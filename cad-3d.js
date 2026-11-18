/* AcreForge CAD Studio linked 3D preview: orthographic block model built from the plan (inches). Conceptual only. */
(function(){
"use strict";
const C=window.AcreCADCore;
const VIEWS={top:{yaw:0,pitch:90,label:"Top"},front:{yaw:0,pitch:0,label:"Front"},right:{yaw:-90,pitch:0,label:"Right"},back:{yaw:180,pitch:0,label:"Back"},left:{yaw:90,pitch:0,label:"Left"},iso:{yaw:35,pitch:28,label:"Home"}};
const COL={wall:[196,178,150],top:[222,208,184],roof:[140,86,70],roofTop:[168,104,84],open:[90,150,200],door:[120,84,52],ground:[34,44,36]};
function walls(){return C.doc.ents.filter(e=>e.t==="wall"&&C.doc.layers[e.layer]&&!C.doc.layers[e.layer].off)}
function bbox(ws){let x0=1e18,y0=1e18,x1=-1e18,y1=-1e18;ws.forEach(e=>[e.a,e.b].forEach(p=>{x0=Math.min(x0,p[0]);x1=Math.max(x1,p[0]);y0=Math.min(y0,p[1]);y1=Math.max(y1,p[1])}));return {x0,y0,x1,y1}}
/* Faces: {pts:[[x,y,z]...], c:[r,g,b], k:"wall|top|roof|open"} */
function model(){
  const D=C.doc,ws=walls(),faces=[];if(!ws.length)return {faces,box:null,height:D.ceil,walls:0};
  const H=D.ceil;
  ws.forEach(e=>{
    const dx=e.b[0]-e.a[0],dy=e.b[1]-e.a[1],L=Math.hypot(dx,dy);if(L<1e-6)return;
    const ux=dx/L,uy=dy/L,nx=-uy*(e.th||6)/2,ny=ux*(e.th||6)/2;
    const A=[e.a[0]+nx,e.a[1]+ny],B=[e.b[0]+nx,e.b[1]+ny],Cc=[e.b[0]-nx,e.b[1]-ny],Dd=[e.a[0]-nx,e.a[1]-ny];
    const q=(p,r,z0,z1)=>[[p[0],p[1],z0],[r[0],r[1],z0],[r[0],r[1],z1],[p[0],p[1],z1]];
    faces.push({pts:q(A,B,0,H),c:COL.wall,k:"wall"},{pts:q(Dd,Cc,0,H),c:COL.wall,k:"wall"},{pts:q(B,Cc,0,H),c:COL.wall,k:"wall"},{pts:q(Dd,A,0,H),c:COL.wall,k:"wall"});
    faces.push({pts:[[A[0],A[1],H],[B[0],B[1],H],[Cc[0],Cc[1],H],[Dd[0],Dd[1],H]],c:COL.top,k:"top"});
    C.doc.ents.filter(o=>(o.t==="door"||o.t==="window")&&o.wall===e.id).forEach(o=>{
      const z0=o.t==="door"?0:(o.sill||36),z1=o.head||80;
      [[1,A],[-1,Dd]].forEach(([sd,p])=>{const a=[p[0]+ux*o.pos+nx*sd*0.02,p[1]+uy*o.pos+ny*sd*0.02],b=[a[0]+ux*o.w,a[1]+uy*o.w];
        faces.push({pts:[[a[0],a[1],z0],[b[0],b[1],z0],[b[0],b[1],z1],[a[0],a[1],z1]],c:o.t==="door"?COL.door:COL.open,k:"open",bias:1})});
    });
  });
  const box=bbox(ws),r=C.doc.roof||{},type=["gable","hip","shed","gambrel","barn"].includes(r.type)?r.type:"gable",p=(r.pitch>0?r.pitch:6)/12,ov=r.ov>=0?r.ov:12;
  const w=box.x1-box.x0,d=box.y1-box.y0,alongX=w>=d,S=Math.min(w,d)+2*ov,rise=type==="shed"?S*p:S/2*p;
  const x0=box.x0-ov,x1=box.x1+ov,y0=box.y0-ov,y1=box.y1+ov,cx=(x0+x1)/2,cy=(y0+y1)/2;
  const P=(x,y,z)=>[x,y,H+z],add=(pts,top)=>faces.push({pts,c:top?COL.roofTop:COL.roof,k:"roof"});
  if(type==="shed"){
    if(alongX){add([P(x0,y0,0),P(x1,y0,0),P(x1,y1,rise),P(x0,y1,rise)],true);add([P(x0,y0,0),P(x1,y0,0),P(x1,y0,-0.1),P(x0,y0,-0.1)])}
    else add([P(x0,y0,0),P(x0,y1,0),P(x1,y1,rise),P(x1,y0,rise)],true);
  }else if(type==="hip"){
    const r0=S/2,a=alongX?[x0+r0,cy]:[cx,y0+r0],b=alongX?[x1-r0,cy]:[cx,y1-r0];
    add([P(x0,y0,0),P(x1,y0,0),P(b[0],b[1],rise),P(a[0],a[1],rise)],true);
    add([P(x1,y0,0),P(x1,y1,0),P(b[0],b[1],rise)]);add([P(x1,y1,0),P(x0,y1,0),P(a[0],a[1],rise),P(b[0],b[1],rise)],true);add([P(x0,y1,0),P(x0,y0,0),P(a[0],a[1],rise)]);
  }else{
    const ra=alongX?[x0,cy,x1,cy]:[cx,y0,cx,y1];
    if(alongX){add([P(x0,y0,0),P(x1,y0,0),P(ra[2],ra[3],rise),P(ra[0],ra[1],rise)],true);add([P(x1,y1,0),P(x0,y1,0),P(ra[0],ra[1],rise),P(ra[2],ra[3],rise)],true);
      add([P(x0,y0,0),P(x0,y1,0),P(ra[0],ra[1],rise)]);add([P(x1,y1,0),P(x1,y0,0),P(ra[2],ra[3],rise)])}
    else{add([P(x0,y0,0),P(x0,y1,0),P(ra[2],ra[3],rise),P(ra[0],ra[1],rise)],true);add([P(x1,y1,0),P(x1,y0,0),P(ra[0],ra[1],rise),P(ra[2],ra[3],rise)],true);
      add([P(x1,y0,0),P(x0,y0,0),P(ra[0],ra[1],rise)]);add([P(x0,y1,0),P(x1,y1,0),P(ra[2],ra[3],rise)])}
  }
  return {faces,box,height:H+rise,walls:ws.length,roofType:type};
}
function project(p,yaw,pitch){
  const y=yaw*Math.PI/180,t=pitch*Math.PI/180,c=Math.cos(y),s=Math.sin(y),X=p[0]*c-p[1]*s,Y=p[0]*s+p[1]*c;
  return {x:X,y:p[2]*Math.cos(t)+Y*Math.sin(t),d:Y*Math.cos(t)-p[2]*Math.sin(t)};
}
function view(m,yaw,pitch){
  const out=m.faces.map(f=>{const q=f.pts.map(p=>project(p,yaw,pitch));return {q,c:f.c,k:f.k,d:q.reduce((a,b)=>a+b.d,0)/q.length-(f.bias||0)}});
  out.sort((a,b)=>b.d-a.d);
  let x0=1e18,y0=1e18,x1=-1e18,y1=-1e18;out.forEach(f=>f.q.forEach(p=>{x0=Math.min(x0,p.x);x1=Math.max(x1,p.x);y0=Math.min(y0,p.y);y1=Math.max(y1,p.y)}));
  return {faces:out,x0,x1,y0,y1,w:x1-x0,h:y1-y0};
}
function render(cv,st,dpr){
  const g=cv.getContext("2d"),W=cv.clientWidth||cv.width,Hh=cv.clientHeight||cv.height;dpr=dpr||1;cv.width=Math.round(W*dpr);cv.height=Math.round(Hh*dpr);g.setTransform(dpr,0,0,dpr,0,0);
  g.fillStyle="#12151a";g.fillRect(0,0,W,Hh);
  const m=model();if(!m.faces.length){g.fillStyle="#9aa5b1";g.font="13px sans-serif";g.textAlign="center";g.fillText("Draw walls or a room to see the 3D model.",W/2,Hh/2);return m}
  const v=view(m,st.yaw,st.pitch),sc=Math.min((W-40)/Math.max(v.w,1),(Hh-40)/Math.max(v.h,1))*st.zoom,mx=(v.x0+v.x1)/2,my=(v.y0+v.y1)/2;
  const T=p=>[W/2+(p.x-mx)*sc,Hh/2-(p.y-my)*sc];
  const shade=(c,f,k)=>{const t=k==="wall"?0.82:k==="top"?1:0.92;return "rgb("+c.map(n=>Math.round(Math.min(255,n*t*f))).join(",")+")"};
  v.faces.forEach((f,i)=>{g.beginPath();f.q.forEach((p,j)=>{const s=T(p);j?g.lineTo(s[0],s[1]):g.moveTo(s[0],s[1])});g.closePath();
    g.fillStyle=shade(f.c,1,f.k);g.fill();g.strokeStyle="rgba(0,0,0,.45)";g.lineWidth=1;g.stroke()});
  return m;
}
window.AcreCAD3D={VIEWS,model,view,project,render};
})();
