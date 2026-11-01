/* AcreForge Estimator
 * Blueprints in, bid-ready estimates out.
 * - Describe a job (deck, slab, fence, roof, room, shed/garage, house) and get a line-item takeoff.
 * - Pull quantities from the Lot Builder plan saved in this browser.
 * - Open a blueprint PDF or image, set the scale, measure lengths/areas/counts, optionally ask an AI model to read it.
 * - Edit every line, apply markups, export a bid PDF or CSV.
 * Everything runs locally. Nothing leaves the browser unless the user presses "Read with AI".
 */
(() => {
"use strict";
const HOST = window.AcreForgeHost;
if (!HOST) return;

const KEY = "acreforge-estimator-v1";
const AI_KEY = "acreforge-estimator-ai-key";
const PAGE = "estimator";

/* ---------- helpers ---------- */
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v, d = 0) => { const n = Number(v); return Number.isFinite(n) ? n : d; };
const pos = (v, d = 0) => Math.max(0, num(v, d));
const r2 = v => Math.round(v * 100) / 100;
const money = v => (v < 0 ? "-$" : "$") + Math.abs(Math.round(v)).toLocaleString("en-US");
const money2 = v => (v < 0 ? "-$" : "$") + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const qfmt = v => (Math.abs(v - Math.round(v)) < 0.005 ? Math.round(v) : r2(v)).toLocaleString("en-US");
const uid = () => Math.random().toString(36).slice(2, 10);
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const toast = m => { const t = document.createElement("div"); t.className = "af-toast"; t.setAttribute("role", "status"); t.textContent = m; t.style.cssText = "position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#0d8b5a;color:#fff;padding:10px 16px;border-radius:10px;z-index:9999;font-size:13px;box-shadow:0 8px 24px rgba(0,0,0,.35)"; document.body.appendChild(t); setTimeout(() => t.remove(), 2800); };
const download = (name, blob) => { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1500); };

/* Approximate regional adjustment, national average = 1.00. A starting point only. */
const STATES = [["AL","Alabama",.86],["AK","Alaska",1.22],["AZ","Arizona",.93],["AR","Arkansas",.85],["CA","California",1.18],["CO","Colorado",1.0],["CT","Connecticut",1.12],["DE","Delaware",1.04],["DC","District of Columbia",1.06],["FL","Florida",.92],["GA","Georgia",.89],["HI","Hawaii",1.32],["ID","Idaho",.92],["IL","Illinois",1.1],["IN","Indiana",.94],["IA","Iowa",.93],["KS","Kansas",.91],["KY","Kentucky",.91],["LA","Louisiana",.87],["ME","Maine",.95],["MD","Maryland",1.0],["MA","Massachusetts",1.15],["MI","Michigan",.98],["MN","Minnesota",1.05],["MS","Mississippi",.85],["MO","Missouri",.99],["MT","Montana",.92],["NE","Nebraska",.91],["NV","Nevada",1.02],["NH","New Hampshire",.97],["NJ","New Jersey",1.14],["NM","New Mexico",.9],["NY","New York",1.2],["NC","North Carolina",.87],["ND","North Dakota",.92],["OH","Ohio",.95],["OK","Oklahoma",.87],["OR","Oregon",1.03],["PA","Pennsylvania",1.04],["RI","Rhode Island",1.1],["SC","South Carolina",.87],["SD","South Dakota",.88],["TN","Tennessee",.88],["TX","Texas",.88],["UT","Utah",.93],["VT","Vermont",.95],["VA","Virginia",.93],["WA","Washington",1.08],["WV","West Virginia",.95],["WI","Wisconsin",1.0],["WY","Wyoming",.91]];
const DIVS = ["General conditions","Site work","Concrete & foundation","Framing","Roofing","Exterior envelope","Windows & doors","Insulation","Drywall & paint","Flooring & trim","Cabinets & counters","Plumbing","Electrical","HVAC","Decking","Fencing","Custom"];
const FINISH = { basic: .85, standard: 1, premium: 1.45 };

const JOBS = {
  deck: { name: "Deck", fields: [["L","Length along house (ft)",16],["W","Depth (ft)",12],["height","Height above grade (ft)",3],["decking","Decking",[["pt","Pressure-treated"],["cedar","Cedar"],["composite","Composite"]],"pt"],["railingLF","Railing (linear ft)",28],["stairs","Stair flights",1]] },
  slab: { name: "Concrete slab / patio", fields: [["L","Length (ft)",20],["W","Width (ft)",20],["thick","Thickness (in)",4],["reinforce","Reinforcement",[["mesh","Wire mesh"],["rebar","Rebar grid"],["none","None"]],"mesh"],["finish","Finish",[["broom","Broom finish"],["stamped","Stamped & colored"],["exposed","Exposed aggregate"]],"broom"]] },
  fence: { name: "Fence", fields: [["LF","Total length (ft)",150],["height","Height (ft)",6],["type","Type",["wood privacy","vinyl","chain link","ranch rail"],"wood privacy"],["gates","Gates",1]] },
  roof: { name: "Roof replacement", fields: [["footprint","Building footprint (sq ft)",1800],["pitch","Roof pitch (x/12)",6],["overhang","Eave overhang (ft)",1.5],["layers","Layers to tear off",1],["material","Roofing",[["asphalt","Asphalt shingles"],["metal","Standing-seam metal"]],"asphalt"],["stories","Stories",1]] },
  room: { name: "Interior room remodel", fields: [["L","Room length (ft)",14],["W","Room width (ft)",12],["H","Ceiling height (ft)",8],["drywall","New drywall",["yes","no"],"no"],["paint","Paint walls & ceiling",["yes","no"],"yes"],["flooring","New flooring",[["lvp","Luxury vinyl plank"],["carpet","Carpet"],["hardwood","Hardwood"],["tile","Tile"],["none","None"]],"lvp"],["doors","Doors to replace",1],["outlets","Outlets / switches to add",2]] },
  shed: { name: "Shed / garage / shop", fields: [["W","Width (ft)",24],["L","Length (ft)",24],["wallH","Wall height (ft)",9],["pitch","Roof pitch (x/12)",5],["overheadDoors","Overhead doors",2],["entryDoors","Entry doors",1],["windows","Windows",2],["siding","Siding",["vinyl","fiber cement","metal","wood"],"metal"],["electrical","Electrical",["yes","no"],"yes"]] },
  house: { name: "House / building (full quantities)", fields: [] }
};

const BQ_FIELDS = [
  ["floorArea","Total heated floor area (sq ft)"],["footprint","Ground floor footprint (sq ft)"],["perimeter","Footprint perimeter (ft)"],["stories","Stories"],
  ["extWallLF","Exterior wall length, all floors (ft)"],["intWallLF","Interior wall length, all floors (ft)"],["wallH","Wall height (ft)"],["roofPitch","Roof pitch (x/12)"],
  ["overhang","Eave overhang (ft)"],["windows","Windows"],["extDoors","Exterior doors"],["intDoors","Interior doors"],
  ["fullBaths","Full baths"],["halfBaths","Half baths"],["kitchens","Kitchens"],["laundry","Laundry rooms"],["garageArea","Garage area (sq ft, unfinished)"],["fixtures","Plumbing fixtures (0 = auto)"]
];
const BQ_SELECTS = [
  ["foundation","Foundation",["slab","crawlspace","basement"]],["roofType","Roofing",["asphalt","metal"]],["siding","Siding",["vinyl","fiber cement","wood","metal"]],
  ["flooring","Main flooring",["lvp","carpet","hardwood","tile"]],["hvac","Heating & cooling",["heat pump","furnace + AC","none"]],["interior","Interior finish",["finished","shell only"]]
];
const defaultBQ = () => ({ floorArea: 1800, footprint: 1800, perimeter: 180, stories: 1, extWallLF: 180, intWallLF: 160, wallH: 9, roofPitch: 6, overhang: 1.5, windows: 12, extDoors: 2, intDoors: 9, fullBaths: 2, halfBaths: 0, kitchens: 1, laundry: 1, garageArea: 0, fixtures: 0, foundation: "slab", roofType: "asphalt", siding: "fiber cement", flooring: "lvp", hvac: "heat pump", interior: "finished" });

const defaults = () => ({
  v: 1,
  project: { name: "New estimate", client: "", address: "", company: "", contact: "", state: "OR", factor: "", number: "EST-" + today().replace(/-/g, ""), date: today(), validDays: 30, notes: "" },
  settings: { overhead: 10, profit: 10, contingency: 5, tax: 0, permits: 1.5, finish: "standard" },
  mode: "job",
  job: { type: "deck", p: {} },
  bq: defaultBQ(),
  lines: [],
  appliedFactor: null,
  takeoff: { file: "", page: 1, pages: 0, scaleMode: "calibrate", archScale: "0.25", ftPerPx: 0, measures: [] },
  ai: { endpoint: "https://api.openai.com/v1/chat/completions", model: "gpt-4.1-mini", last: null }
});

let S = load();
function load() {
  try {
    const o = JSON.parse(localStorage.getItem(KEY));
    if (o && o.v === 1) {
      const d = defaults();
      return { ...d, ...o, project: { ...d.project, ...o.project }, settings: { ...d.settings, ...o.settings }, bq: { ...d.bq, ...o.bq }, takeoff: { ...d.takeoff, ...o.takeoff }, ai: { ...d.ai, ...o.ai }, job: { ...d.job, ...o.job }, lines: Array.isArray(o.lines) ? o.lines : [] };
    }
  } catch (e) {}
  return defaults();
}
let saveTimer = null;
function save() { clearTimeout(saveTimer); saveTimer = setTimeout(() => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { toast("Could not save: browser storage is full."); } }, 150); }
const factor = () => { const f = num(S.project.factor, NaN); if (Number.isFinite(f) && f > 0) return f; return (STATES.find(s => s[0] === S.project.state) || [0, 0, 1])[2]; };
const stateName = () => (STATES.find(s => s[0] === S.project.state) || [0, "National average"])[1];

/* ---------- assemblies ---------- */
// Line: unit costs are national-average planning figures, multiplied by the location factor at generation time.
function mkLines(list) {
  const f = factor();
  return list.filter(l => l && l[2] > 0).map(([div, desc, qty, unit, mat, lab]) => ({ id: uid(), div, desc, qty: r2(qty), unit, mat: r2(mat * f), lab: r2(lab * f) }));
}

function houseLines(b, fin) {
  const fm = FINISH[fin] || 1;
  const stories = Math.max(1, Math.round(pos(b.stories, 1)));
  const floorArea = pos(b.floorArea);
  const fp = pos(b.footprint) || floorArea / stories;
  const perim = pos(b.perimeter) || 4 * Math.sqrt(fp);
  const extLF = pos(b.extWallLF) || perim * stories;
  const intLF = pos(b.intWallLF);
  const wallH = pos(b.wallH, 9) || 9;
  const pitch = pos(b.roofPitch);
  const oh = pos(b.overhang);
  const win = Math.round(pos(b.windows)), exd = Math.round(pos(b.extDoors)), ind = Math.round(pos(b.intDoors));
  const fb = Math.round(pos(b.fullBaths)), hb = Math.round(pos(b.halfBaths)), kit = Math.round(pos(b.kitchens)), lau = Math.round(pos(b.laundry));
  const garage = Math.min(pos(b.garageArea), floorArea);
  const finished = b.interior !== "shell only";
  const finArea = Math.max(0, floorArea - garage);
  const extArea = extLF * wallH;
  const netExt = Math.max(0, extArea - win * 15 - exd * 21);
  const slopeF = Math.sqrt(1 + (pitch / 12) ** 2);
  const roofPlan = pos(b.roofPlanArea) || fp + perim * oh;
  const roofArea = roofPlan * slopeF;
  const sq = roofArea / 100 * 1.1;
  const wallScale = wallH / 8;
  const L = [];
  const add = (...a) => L.push(a);
  // General conditions
  add("General conditions", "Dumpsters & haul-off (30 yd)", Math.ceil(Math.max(floorArea, fp) / 800), "ea", 575, 0);
  add("General conditions", "Temporary toilet & power (per month)", Math.max(2, Math.ceil(floorArea / 450)), "mo", 380, 0);
  add("General conditions", "Final construction cleaning", floorArea, "sf", 0.05, 0.3);
  // Site
  add("Site work", "Clear & rough grade building pad", fp * 1.3, "sf", 0, 0.85);
  add("Site work", "Excavate footings (24\" x 18\")", perim * 2 * 1.5 / 27, "cy", 0, 48);
  // Foundation
  const ftgCY = perim * (20 / 12) * 1 / 27 * 1.05;
  add("Concrete & foundation", "Footing concrete 20\" x 12\" (3,000 psi)", ftgCY, "cy", 178, 95);
  add("Concrete & foundation", "Footing rebar, 2 #4 continuous", perim * 2 * 0.668 * 1.1, "lb", 1.05, 0.65);
  if (b.foundation === "crawlspace") {
    add("Concrete & foundation", "Stem wall concrete 8\" x 24\"", perim * (8 / 12) * 2 / 27 * 1.05, "cy", 178, 145);
    add("Concrete & foundation", "Stem wall forms", perim * 2, "sf", 1.2, 4.2);
    add("Framing", "Floor system: sill, joists, 3/4\" subfloor", fp, "sf", 6.6, 4.2);
    add("Concrete & foundation", "Crawlspace vapor barrier & vents", fp, "sf", 0.32, 0.25);
  } else if (b.foundation === "basement") {
    add("Site work", "Basement excavation & backfill", fp * 8.5 / 27 * 1.35, "cy", 0, 15);
    add("Concrete & foundation", "Basement walls 8\" x 8 ft", perim * (8 / 12) * 8 / 27 * 1.05, "cy", 178, 225);
    add("Concrete & foundation", "Foundation waterproofing & drain tile", perim * 8, "sf", 1.25, 1.65);
  }
  if (b.foundation !== "crawlspace") {
    add("Concrete & foundation", "Slab concrete 4\"", fp * (4 / 12) / 27 * 1.05, "cy", 178, 0);
    add("Concrete & foundation", "Gravel base 4\" & 10 mil vapor barrier", fp, "sf", 0.95, 0.45);
    add("Concrete & foundation", "Slab reinforcement (wire mesh)", fp, "sf", 0.48, 0.3);
    add("Concrete & foundation", "Place, finish & cure slab", fp, "sf", 0.12, 2.35);
    add("Concrete & foundation", "Slab edge forms", perim, "lf", 1.5, 3.2);
  }
  // Framing
  const extStuds = Math.ceil(extLF * 0.75 * 1.18), intStuds = Math.ceil(intLF * 0.75 * 1.12);
  add("Framing", `Exterior walls 2x6 @ 16" o.c. (~${extStuds} studs + plates)`, extLF, "lf", 11.8 * wallScale, 14.5 * wallScale);
  if (intLF > 0) add("Framing", `Interior walls 2x4 @ 16" o.c. (~${intStuds} studs + plates)`, intLF, "lf", 6.4 * wallScale, 9.2 * wallScale);
  add("Framing", "Headers at window & door openings", win + exd + ind, "ea", 42, 34);
  if (stories > 1) {
    add("Framing", "Upper floor system: joists & 3/4\" subfloor", fp * (stories - 1), "sf", 6.6, 4.2);
    add("Framing", "Interior stair flight", stories - 1, "ea", 950, 1150);
  }
  add("Framing", pitch > 0 ? `Roof trusses @ 24" o.c. (${pitch}/12 pitch)` : "Low-slope roof framing", roofPlan, "sf", 4.4, 2.2);
  add("Framing", "Wall sheathing 7/16\" OSB (4x8 sheets)", Math.ceil(extArea / 32 * 1.1), "sht", 19, 14);
  add("Framing", "Roof sheathing 7/16\" OSB (4x8 sheets)", Math.ceil(roofArea / 32 * 1.1), "sht", 19, 16);
  add("Framing", "Framing hardware, nails & adhesives", floorArea, "sf", 0.55, 0);
  // Roofing
  if (b.roofType === "metal") add("Roofing", "Standing-seam metal roofing", sq, "sq", 420, 330);
  else add("Roofing", "Architectural asphalt shingles", sq, "sq", 152, 190);
  add("Roofing", "Synthetic underlayment & ice/water shield", sq, "sq", 32, 14);
  add("Roofing", "Drip edge & rake trim", perim * 1.2, "lf", 1.6, 1.2);
  if (pitch > 0) add("Roofing", "Ridge vent", perim / 4 * 1.25, "lf", 5, 4);
  add("Roofing", "Gutters & downspouts (5\" aluminum)", perim, "lf", 6.2, 5);
  // Envelope
  const sid = { vinyl: [2.6, 3], "fiber cement": [3.9, 4.8], wood: [6, 5.5], metal: [3.4, 3.2] }[b.siding] || [3.9, 4.8];
  add("Exterior envelope", "Weather-resistive barrier (house wrap)", extArea, "sf", 0.26, 0.3);
  add("Exterior envelope", `Siding, ${b.siding || "fiber cement"}`, netExt * 1.1, "sf", sid[0] * fm, sid[1]);
  add("Exterior envelope", "Fascia, soffit & exterior trim", perim, "lf", 8.2 * fm, 9);
  if (b.siding === "fiber cement" || b.siding === "wood") add("Exterior envelope", "Exterior paint (2 coats)", netExt, "sf", 0.45, 1.55);
  // Openings
  add("Windows & doors", "Windows, vinyl double-hung avg 3x5 (installed)", win, "ea", 640 * fm, 260);
  add("Windows & doors", "Exterior doors, prehung with hardware", exd, "ea", 1100 * fm, 380);
  if (finished) add("Windows & doors", "Interior doors, prehung with hardware", ind, "ea", 210 * fm, 160);
  if (garage > 0) add("Windows & doors", "Garage door 16x7 with opener", Math.max(1, Math.round(garage / 400)), "ea", 1650, 650);
  // Insulation
  if (finished) {
    add("Insulation", "Wall insulation R-21 batts", netExt, "sf", 1.05, 0.7);
    add("Insulation", "Attic insulation R-49 blown", fp, "sf", 1.4, 0.55);
  }
  // Drywall & paint
  if (finished) {
    const dwWall = (extLF + 2 * intLF) * wallH, dwCeil = finArea, dw = (dwWall + dwCeil) * 1.1;
    add("Drywall & paint", `Drywall 1/2" (4x12 sheets, ${Math.round(dwWall + dwCeil).toLocaleString()} sf surface)`, Math.ceil(dw / 48), "sht", 22, 0);
    add("Drywall & paint", "Hang, tape & finish drywall (level 4)", dwWall + dwCeil, "sf", 0.22, 1.95);
    add("Drywall & paint", "Interior paint, primer + 2 coats", dwWall + dwCeil, "sf", 0.34 * fm, 1.25);
  }
  // Flooring & trim
  if (finished) {
    const tileArea = Math.min(finArea, fb * 55 + hb * 25 + lau * 40);
    const fl = { lvp: [3.5, 2.4], carpet: [3, 1.2], hardwood: [7, 4.5], tile: [4.5, 8] }[b.flooring] || [3.5, 2.4];
    if (tileArea > 0) add("Flooring & trim", "Tile flooring in baths & laundry", tileArea * 1.1, "sf", 4.5 * fm, 8);
    add("Flooring & trim", `Main flooring, ${b.flooring || "lvp"}`, Math.max(0, finArea - tileArea) * 1.08, "sf", fl[0] * fm, fl[1]);
    add("Flooring & trim", "Baseboard", extLF + 2 * intLF, "lf", 1.8 * fm, 2.5);
    add("Flooring & trim", "Door & window casing", ind * 34 + exd * 17 + win * 14, "lf", 1.8 * fm, 3);
  }
  // Cabinets
  if (finished && kit > 0) {
    add("Cabinets & counters", "Kitchen cabinets (base + wall)", kit * 22, "lf", 380 * fm, 95);
    add("Cabinets & counters", "Countertops", kit * 38, "sf", 62 * fm, 20);
  }
  if (finished && fb + hb > 0) add("Cabinets & counters", "Bath vanity with top", fb + hb, "ea", 650 * fm, 250);
  // Plumbing
  const fixtures = Math.round(pos(b.fixtures)) || fb * 3 + hb * 2 + kit * 2 + lau * 2;
  if (fixtures > 0) {
    add("Plumbing", "Rough-in supply, drain & vent (per fixture)", fixtures, "ea", 280, 650);
    add("Plumbing", "Fixtures, set & trim out", fixtures, "ea", 380 * fm, 260);
    add("Plumbing", "Water heater 50 gal", 1, "ea", 1650, 650);
  }
  // Electrical
  add("Electrical", finished ? "Wiring, boxes & devices" : "Basic wiring, lights & outlets", floorArea, "sf", finished ? 2.4 : 1.4, finished ? 4.2 : 2.4);
  add("Electrical", "200 A service panel", 1, "ea", 1850, 1400);
  if (finished) add("Electrical", "Light fixtures (allowance)", Math.ceil(finArea / 90), "ea", 120 * fm, 75);
  // HVAC
  if (b.hvac === "heat pump") add("HVAC", "Ducted heat pump system with ductwork", finArea, "sf", 5, 3.5);
  else if (b.hvac === "furnace + AC") add("HVAC", "Gas furnace + AC with ductwork", finArea, "sf", 4.2, 3.2);
  return L;
}

function jobParams(type, p0) { const p = { ...(p0 || {}) }; (JOBS[type]?.fields || []).forEach(([k, , a, d]) => { if (p[k] === undefined || p[k] === "") p[k] = Array.isArray(a) ? d : a; }); return p; }
function jobLines(type, p0, fin) {
  const p = jobParams(type, p0);
  const fm = FINISH[fin] || 1;
  const L = [];
  const add = (...a) => L.push(a);
  if (type === "deck") {
    const Lf = pos(p.L, 16), W = pos(p.W, 12), h = pos(p.height, 3);
    const beams = Math.max(1, Math.ceil((W - 1) / 10));
    const ftg = (Math.ceil(Lf / 8) + 1) * beams;
    const joists = Math.ceil(Lf * 12 / 16) + 1;
    const deck = { pt: ["Pressure-treated 5/4x6 decking", 3.2, 4], cedar: ["Cedar 5/4x6 decking", 6.5, 4.5], composite: ["Composite decking with hidden fasteners", 9.2, 5.2] }[p.decking] || ["Pressure-treated 5/4x6 decking", 3.2, 4];
    add("Decking", "Concrete pier footings 12\" dia x 48\" deep", ftg, "ea", 48, 85);
    add("Decking", `6x6 PT posts with post bases (${Math.max(2, Math.ceil(h + 1))} ft)`, ftg, "ea", 35 + Math.max(2, Math.ceil(h + 1)) * 4.6, 42);
    add("Decking", "Beams, doubled 2x10 PT", beams * Lf, "lf", 5.4, 6);
    add("Decking", "Ledger 2x10 PT with flashing & structural screws", Lf, "lf", 9, 12);
    add("Decking", `Joists 2x8 PT @ 16" o.c. (${joists} joists x ${W} ft)`, joists * W, "lf", 1.95, 1.6);
    add("Decking", "Joist hangers, ties & hardware", joists * 2 + ftg * 2, "ea", 3.6, 0.5);
    add("Decking", deck[0], Lf * W * 1.1, "sf", deck[1] * fm, deck[2]);
    if (pos(p.railingLF) > 0) add("Decking", p.decking === "composite" ? "Composite / aluminum railing" : "Wood railing 36\"", pos(p.railingLF), "lf", (p.decking === "composite" ? 55 : 22) * fm, p.decking === "composite" ? 25 : 20);
    const risers = Math.max(1, Math.ceil(h * 12 / 7.5));
    if (pos(p.stairs) > 0 && h > 0.6) add("Decking", `Stairs, 4 ft wide (${risers} risers per flight)`, pos(p.stairs), "ea", 48 * risers * fm, 42 * risers);
    add("General conditions", "Layout, haul-off & cleanup", 1, "ea", 120, 280);
  } else if (type === "slab") {
    const Lf = pos(p.L, 20), W = pos(p.W, 20), t = pos(p.thick, 4) || 4, A = Lf * W;
    add("Site work", "Excavate & compact subgrade", A, "sf", 0, 1.1);
    add("Concrete & foundation", "Gravel base 4\" compacted", A, "sf", 0.9, 0.6);
    add("Concrete & foundation", `Edge forms (${qfmt(2 * (Lf + W))} lf)`, 2 * (Lf + W), "lf", 1.5, 3.5);
    if (p.reinforce === "rebar") add("Concrete & foundation", "Rebar #4 @ 18\" o.c. each way, on chairs", A, "sf", 0.92, 0.62);
    else if (p.reinforce !== "none") add("Concrete & foundation", "Welded wire mesh 6x6 W1.4", A, "sf", 0.46, 0.26);
    add("Concrete & foundation", `Ready-mix concrete ${t}" thick (3,000 psi, +8% waste)`, A * t / 12 / 27 * 1.08, "cy", 178, 0);
    add("Concrete & foundation", "Place, broom finish & control joints", A, "sf", 0.1, 2.6);
    if (p.finish === "stamped") add("Concrete & foundation", "Stamped & colored finish upgrade", A, "sf", 2.6 * fm, 6.5);
    if (p.finish === "exposed") add("Concrete & foundation", "Exposed aggregate finish upgrade", A, "sf", 1.2 * fm, 3.2);
    add("Concrete & foundation", "Cure & seal", A, "sf", 0.2, 0.25);
    add("General conditions", "Mobilization & cleanup", 1, "ea", 150, 350);
  } else if (type === "fence") {
    const LF = pos(p.LF, 150), h = pos(p.height, 6) || 6, g = Math.round(pos(p.gates));
    const posts = Math.ceil(LF / 8) + 1 + g;
    const hs = h / 6;
    const T = { "wood privacy": ["Wood privacy panels / pickets & rails", 14 * hs, 12, 22], vinyl: ["Vinyl privacy panels", 26 * hs, 12, 38], "chain link": ["Chain link fabric, top rail & ties", 9 * hs, 8, 24], "ranch rail": ["3-rail ranch fence rails", 7, 7, 20] }[p.type] || ["Wood privacy panels / pickets & rails", 14 * hs, 12, 22];
    add("Fencing", `Post holes with concrete (${posts} posts @ 8 ft)`, posts, "ea", 14, 36);
    add("Fencing", `Posts, ${p.type || "wood privacy"} (${Math.ceil(h + 2)} ft)`, posts, "ea", T[3] * hs, 12);
    add("Fencing", T[0], LF, "lf", T[1] * fm, T[2]);
    if (g > 0) add("Fencing", "Walk gate with hardware", g, "ea", 350 * fm, 180);
    add("General conditions", "Locate utilities, haul-off & cleanup", 1, "ea", 60, 220);
  } else if (type === "roof") {
    const fp = pos(p.footprint, 1800), pitch = pos(p.pitch, 6), oh = pos(p.overhang, 1.5), layers = Math.max(0, Math.round(pos(p.layers, 1)));
    const perim = 4 * Math.sqrt(fp), area = (fp + perim * oh) * Math.sqrt(1 + (pitch / 12) ** 2), sq = area / 100 * 1.12;
    const steep = (pitch > 8 ? 1.15 : 1) * (pos(p.stories, 1) > 1 ? 1.1 : 1);
    if (layers > 0) add("Roofing", `Tear off ${layers} layer${layers > 1 ? "s" : ""} & dispose`, sq * layers, "sq", 0, 72 * steep);
    add("General conditions", "Dumpsters (20 yd)", Math.max(1, Math.ceil(sq * Math.max(1, layers) / 25)), "ea", 525, 0);
    add("Roofing", "Sheathing repair allowance (10% of deck)", Math.ceil(sq * 0.1 * 100 / 32), "sht", 19, 32);
    add("Roofing", "Synthetic underlayment & ice/water shield", sq, "sq", 32, 14 * steep);
    if (p.material === "metal") add("Roofing", "Standing-seam metal roofing", sq, "sq", 420 * fm, 330 * steep);
    else add("Roofing", "Architectural asphalt shingles", sq, "sq", 152 * fm, 190 * steep);
    add("Roofing", "Drip edge & rake trim", perim * 1.2, "lf", 1.6, 1.2);
    add("Roofing", "Ridge vent & caps", perim / 4 * 1.25, "lf", 6, 4.5);
    add("Roofing", "Flashing, pipe boots & vents (allowance)", 1, "ea", 260, 320);
  } else if (type === "room") {
    const Lf = pos(p.L, 14), W = pos(p.W, 12), H = pos(p.H, 8) || 8, wall = 2 * (Lf + W) * H, ceil = Lf * W;
    add("General conditions", "Protection, haul-off & cleanup", 1, "ea", 90, 260);
    if (p.drywall === "yes") {
      add("Drywall & paint", "Remove existing drywall", wall + ceil, "sf", 0, 0.75);
      add("Drywall & paint", "Drywall 1/2\" (4x12 sheets)", Math.ceil((wall + ceil) * 1.1 / 48), "sht", 22, 0);
      add("Drywall & paint", "Hang, tape & finish drywall", wall + ceil, "sf", 0.22, 1.95);
    }
    if (p.paint === "yes") add("Drywall & paint", "Paint walls & ceiling, primer + 2 coats", wall + ceil, "sf", 0.34 * fm, 1.3);
    const fl = { lvp: [3.5, 2.4, "Luxury vinyl plank"], carpet: [3, 1.2, "Carpet & pad"], hardwood: [7, 4.5, "Hardwood flooring"], tile: [4.5, 8, "Tile flooring"] }[p.flooring];
    if (fl) { add("Flooring & trim", "Remove existing flooring", ceil, "sf", 0, 1.1); add("Flooring & trim", fl[2], ceil * 1.08, "sf", fl[0] * fm, fl[1]); add("Flooring & trim", "Baseboard", 2 * (Lf + W), "lf", 1.8 * fm, 2.5); }
    if (pos(p.doors) > 0) add("Windows & doors", "Replace interior door, prehung with casing", pos(p.doors), "ea", 260 * fm, 210);
    if (pos(p.outlets) > 0) add("Electrical", "Add outlet / switch (old work)", pos(p.outlets), "ea", 25, 145);
  } else if (type === "shed") {
    const W = pos(p.W, 24), Lf = pos(p.L, 24), A = W * Lf;
    const b = { ...defaultBQ(), floorArea: A, footprint: A, perimeter: 2 * (W + Lf), stories: 1, extWallLF: 2 * (W + Lf), intWallLF: 0, wallH: pos(p.wallH, 9) || 9, roofPitch: pos(p.pitch, 5), overhang: 1, windows: pos(p.windows), extDoors: pos(p.entryDoors), intDoors: 0, fullBaths: 0, halfBaths: 0, kitchens: 0, laundry: 0, garageArea: 0, foundation: "slab", roofType: "metal", siding: p.siding || "metal", flooring: "lvp", hvac: "none", interior: "shell only" };
    const lines = houseLines(b, fin).filter(l => !(l[0] === "Electrical" && p.electrical !== "yes") && !/Temporary toilet/.test(l[1]));
    lines.forEach(l => { if (l[1] === "200 A service panel") { l[1] = "100 A subpanel & feeder"; l[4] = 650; l[5] = 750; } });
    L.push(...lines);
    if (pos(p.overheadDoors) > 0) add("Windows & doors", "Overhead door 10x10 insulated steel", pos(p.overheadDoors), "ea", 1750 * fm, 650);
  } else if (type === "house") {
    L.push(...houseLines(S.bq, fin));
  }
  return L;
}

/* ---------- Lot Builder import ---------- */
function readLotBuilder() {
  let H;
  try { H = JSON.parse(localStorage.getItem("oep-home")); } catch (e) {}
  if (!H || !Array.isArray(H.levels) || !H.levels.length) return null;
  const R = 0.5; // ft per raster cell
  let floorArea = 0, extLF = 0, intLF = 0, footprint = 0, perimeter = 0, doors = 0, extDoors = 0, wins = 0, garage = 0;
  const types = {}, fixtures = { toilet: 0, tub: 0, shower: 0, sink: 0, vanity: 0, dishwasher: 0, washer: 0 };
  let levelsUsed = 0;
  H.levels.forEach((l, li) => {
    const rooms = (l.rooms || []).filter(r => num(r.w) > 0 && num(r.h) > 0);
    if (!rooms.length) return;
    levelsUsed++;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    rooms.forEach(r => { x0 = Math.min(x0, r.x); y0 = Math.min(y0, r.y); x1 = Math.max(x1, r.x + r.w); y1 = Math.max(y1, r.y + r.h); });
    const nx = Math.ceil((x1 - x0) / R) + 2, ny = Math.ceil((y1 - y0) / R) + 2;
    if (nx * ny > 6e6) return;
    const g = new Int16Array(nx * ny);
    rooms.forEach((r, i) => {
      const a = Math.round((r.x - x0) / R) + 1, b = Math.round((r.y - y0) / R) + 1, c = Math.round((r.x + r.w - x0) / R) + 1, d = Math.round((r.y + r.h - y0) / R) + 1;
      for (let y = b; y < d; y++) for (let x = a; x < c; x++) g[y * nx + x] = i + 1;
      types[r.t] = (types[r.t] || 0) + 1;
      if (/garage|shop/i.test(r.t)) garage += r.w * r.h;
    });
    let cells = 0, ext = 0, inn = 0;
    for (let y = 0; y < ny; y++) for (let x = 0; x < nx; x++) {
      const v = g[y * nx + x];
      if (v) cells++;
      if (x + 1 < nx) { const w = g[y * nx + x + 1]; if ((v === 0) !== (w === 0)) ext++; else if (v && w && v !== w) inn++; }
      if (y + 1 < ny) { const w = g[(y + 1) * nx + x]; if ((v === 0) !== (w === 0)) ext++; else if (v && w && v !== w) inn++; }
    }
    const area = cells * R * R;
    floorArea += area; extLF += ext * R; intLF += inn * R;
    if (li === 0 || !footprint) { footprint = area; perimeter = ext * R; }
    const covered = (px, py) => { const cx = Math.floor((px - x0) / R) + 1, cy = Math.floor((py - y0) / R) + 1; return cx >= 0 && cy >= 0 && cx < nx && cy < ny && g[cy * nx + cx] > 0; };
    (l.doors || []).forEach(d => { doors++; const o = d.o === "v"; const a = o ? covered(d.x - 0.3, d.y) : covered(d.x, d.y - 0.3), b = o ? covered(d.x + 0.3, d.y) : covered(d.x, d.y + 0.3); if (a !== b) extDoors++; });
    wins += (l.wins || []).length;
    (l.furn || []).forEach(f => { if (f.t in fixtures) fixtures[f.t]++; });
  });
  if (!levelsUsed) return { empty: true, name: H.name };
  const baths = (types.Bath || 0) + (types.Restroom || 0);
  const fixtureCount = Math.max(Object.values(fixtures).reduce((a, b) => a + b, 0), baths * 3 + (types.Kitchen || 0) * 2 + (types.Laundry || 0) * 2);
  return {
    name: H.name || "Lot Builder plan",
    stories: levelsUsed, floorArea: Math.round(floorArea), footprint: Math.round(footprint), perimeter: Math.round(perimeter),
    extWallLF: Math.round(extLF), intWallLF: Math.round(intLF), windows: wins, extDoors: Math.max(extDoors, doors ? 1 : 0), intDoors: Math.max(0, doors - extDoors),
    fullBaths: baths, kitchens: types.Kitchen || 0, laundry: types.Laundry || 0, garageArea: Math.round(garage), fixtures: fixtureCount,
    types
  };
}

/* ---------- takeoff (blueprint) ---------- */
const CATS = {
  len: ["Exterior wall", "Interior wall", "Footing / foundation", "Fence", "Trim", "Other length"],
  area: ["Floor area", "Roof (plan view)", "Slab / patio", "Deck", "Wall area", "Other area"],
  count: ["Window", "Exterior door", "Interior door", "Plumbing fixture", "Light / outlet", "Other count"]
};
const ARCH = [["0.0625","1/16\" = 1'-0\""],["0.09375","3/32\" = 1'-0\""],["0.125","1/8\" = 1'-0\""],["0.1875","3/16\" = 1'-0\""],["0.25","1/4\" = 1'-0\""],["0.375","3/8\" = 1'-0\""],["0.5","1/2\" = 1'-0\""],["0.75","3/4\" = 1'-0\""],["1","1\" = 1'-0\""],["1.5","1-1/2\" = 1'-0\""],["0.1","1\" = 10' (eng)"],["0.05","1\" = 20' (eng)"],["0.0333333","1\" = 30' (eng)"],["0.025","1\" = 40' (eng)"],["0.02","1\" = 50' (eng)"],["0.01","1\" = 100' (eng)"]];
const V = { img: null, pdf: null, renderScale: 1, isPdf: false, zoom: 1, panX: 0, panY: 0, tool: "pan", draft: [], cal: null, drag: null, busy: false, hover: null };
const ftPerPx = () => {
  const t = S.takeoff;
  if (V.isPdf && t.scaleMode === "arch") { const ipf = num(t.archScale, 0.25); return ipf > 0 ? 1 / (ipf * 72 * V.renderScale) : 0; }
  return num(t.ftPerPx);
};
function measureValue(m) {
  const k = ftPerPx();
  if (m.kind === "count") return m.pts.length;
  if (!k) return NaN;
  if (m.kind === "len") { let s = 0; for (let i = 1; i < m.pts.length; i++) s += Math.hypot(m.pts[i][0] - m.pts[i - 1][0], m.pts[i][1] - m.pts[i - 1][1]); return s * k; }
  let a = 0; const p = m.pts; for (let i = 0; i < p.length; i++) { const j = (i + 1) % p.length; a += p[i][0] * p[j][1] - p[j][0] * p[i][1]; } return Math.abs(a) / 2 * k * k;
}
const unitOf = m => m.kind === "len" ? "lf" : m.kind === "area" ? "sf" : "ea";

async function openFile(file) {
  if (!file) return;
  V.busy = true; paintStatus("Opening " + file.name + "…");
  try {
    if (file.type === "application/pdf" || /\.pdf$/i.test(file.name)) {
      const pdfjs = await import("./vendor/pdfjs/pdf.min.mjs");
      pdfjs.GlobalWorkerOptions.workerSrc = new URL("./vendor/pdfjs/pdf.worker.min.mjs", location.href).href;
      const data = new Uint8Array(await file.arrayBuffer());
      V.pdf = await pdfjs.getDocument({ data, standardFontDataUrl: new URL("./vendor/pdfjs/standard_fonts/", location.href).href }).promise;
      V.isPdf = true;
      const sameFile = S.takeoff.file === file.name;
      S.takeoff.file = file.name; S.takeoff.pages = V.pdf.numPages;
      if (!sameFile) { S.takeoff.page = 1; S.takeoff.measures = []; S.takeoff.ftPerPx = 0; S.takeoff.scaleMode = "arch"; }
      S.takeoff.page = Math.min(Math.max(1, S.takeoff.page), V.pdf.numPages);
      await renderPdfPage();
    } else if (/^image\//.test(file.type) || /\.(png|jpe?g|webp|gif)$/i.test(file.name)) {
      const url = URL.createObjectURL(file);
      const img = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(Error("This image could not be read.")); i.src = url; });
      const c = document.createElement("canvas"); c.width = img.naturalWidth; c.height = img.naturalHeight; c.getContext("2d").drawImage(img, 0, 0);
      URL.revokeObjectURL(url);
      const sameFile = S.takeoff.file === file.name;
      V.img = c; V.pdf = null; V.isPdf = false; V.renderScale = 1;
      S.takeoff.file = file.name; S.takeoff.pages = 1; S.takeoff.page = 1; S.takeoff.scaleMode = "calibrate";
      if (!sameFile) { S.takeoff.measures = []; S.takeoff.ftPerPx = 0; }
      fitView();
    } else throw Error("Choose a PDF, PNG, JPG or WebP file.");
    save();
  } catch (e) { alert("Could not open the blueprint: " + (e.message || e)); }
  V.busy = false; draw(); renderTakeoffSide();
}
async function renderPdfPage() {
  if (!V.pdf) return;
  const page = await V.pdf.getPage(S.takeoff.page);
  const base = page.getViewport({ scale: 1 });
  const scale = Math.min(3, Math.max(1, 2600 / Math.max(base.width, base.height)));
  const vp = page.getViewport({ scale });
  const c = document.createElement("canvas"); c.width = Math.round(vp.width); c.height = Math.round(vp.height);
  const ctx = c.getContext("2d"); ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, c.width, c.height);
  await page.render({ canvasContext: ctx, viewport: vp, canvas: c }).promise;
  V.img = c; V.renderScale = scale; fitView();
}
function fitView() {
  const cv = document.getElementById("estCanvas"); if (!cv || !V.img) return;
  const w = cv.clientWidth || 800, h = cv.clientHeight || 560;
  V.zoom = Math.min(w / V.img.width, h / V.img.height) * 0.96;
  V.panX = (w - V.img.width * V.zoom) / 2; V.panY = (h - V.img.height * V.zoom) / 2;
}
const toImg = (cv, e) => { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left - V.panX) / V.zoom, (e.clientY - r.top - V.panY) / V.zoom]; };
const COLORS = { len: "#2563eb", area: "#16a34a", count: "#dc2626", cal: "#f59e0b" };
function draw() {
  const cv = document.getElementById("estCanvas"); if (!cv) return;
  const dpr = window.devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
  const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.fillStyle = "#1d2a24"; g.fillRect(0, 0, w, h);
  if (!V.img) {
    g.fillStyle = "#9aa9a0"; g.font = "14px system-ui,sans-serif"; g.textAlign = "center";
    g.fillText(S.takeoff.file ? `Re-open "${S.takeoff.file}" to see its markup (${S.takeoff.measures.length} saved measurements).` : "Open a blueprint PDF or image to start measuring.", w / 2, h / 2);
    return;
  }
  g.save(); g.translate(V.panX, V.panY); g.scale(V.zoom, V.zoom);
  g.imageSmoothingEnabled = true; g.drawImage(V.img, 0, 0);
  const lw = 2.5 / V.zoom, k = ftPerPx(), placed = [];
  const drawShape = (m, color, active) => {
    const p = m.pts; if (!p.length) return;
    g.strokeStyle = color; g.fillStyle = color; g.lineWidth = active ? lw * 1.6 : lw;
    if (m.kind === "count") { p.forEach(([x, y], i) => { g.beginPath(); g.arc(x, y, 7 / V.zoom, 0, 7); g.globalAlpha = .85; g.fill(); g.globalAlpha = 1; g.fillStyle = "#fff"; g.font = `bold ${10 / V.zoom}px system-ui`; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(i + 1, x, y); g.fillStyle = color; }); return; }
    g.beginPath(); g.moveTo(p[0][0], p[0][1]); p.slice(1).forEach(q => g.lineTo(q[0], q[1])); if (m.kind === "area" && !active) g.closePath();
    if (m.kind === "area") { g.globalAlpha = .18; g.fill(); g.globalAlpha = 1; }
    g.stroke();
    p.forEach(([x, y]) => { g.beginPath(); g.arc(x, y, 3.5 / V.zoom, 0, 7); g.fill(); });
    if (!active && k) {
      const v = measureValue(m); let cx = 0, cy = 0;
      if (m.kind === "len") { let best = 0; for (let i = 1; i < p.length; i++) { const d = Math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]); if (d > best) { best = d; cx = (p[i][0] + p[i - 1][0]) / 2; cy = (p[i][1] + p[i - 1][1]) / 2; } } }
      else { p.forEach(q => { cx += q[0]; cy += q[1]; }); cx /= p.length; cy /= p.length; }
      const label = `${m.label || m.cat}: ${qfmt(v)} ${unitOf(m)}`;
      g.font = `600 ${12 / V.zoom}px system-ui`; g.textAlign = "center"; g.textBaseline = "middle";
      const tw = g.measureText(label).width, bh = 20 / V.zoom;
      for (let guard = 0; guard < 12 && placed.some(r => Math.abs(r[0] - cx) < (r[2] + tw) / 2 + 4 / V.zoom && Math.abs(r[1] - cy) < bh); guard++) cy += bh;
      placed.push([cx, cy, tw]); g.fillStyle = "rgba(255,255,255,.92)"; g.fillRect(cx - tw / 2 - 4 / V.zoom, cy - 9 / V.zoom, tw + 8 / V.zoom, 18 / V.zoom);
      g.fillStyle = color; g.fillText(label, cx, cy);
    }
  };
  S.takeoff.measures.filter(m => (m.page || 1) === S.takeoff.page).forEach(m => drawShape(m, COLORS[m.kind], false));
  if (V.draft.length) {
    const kind = V.tool === "cal" ? "len" : V.tool;
    const pts = V.hover && V.tool !== "count" ? [...V.draft, V.hover] : V.draft;
    drawShape({ kind, pts }, V.tool === "cal" ? COLORS.cal : COLORS[kind], true);
  }
  if (V.cal) drawShape({ kind: "len", pts: V.cal }, COLORS.cal, true);
  g.restore();
}
function paintStatus(msg) { const el = document.getElementById("estTakeStatus"); if (el) el.textContent = msg; }
function toolHelp() {
  const k = ftPerPx();
  const scaleTxt = k ? `Scale set: 1 ft = ${qfmt(1 / k)} px.` : "Scale not set yet: calibrate or pick the drawing scale before measuring lengths or areas.";
  const t = { pan: "Drag to pan, scroll to zoom.", cal: "Click both ends of a dimension you know, then enter its real length.", len: "Click points along the line. Double-click or press Enter to finish.", area: "Click each corner of the area. Double-click or press Enter to close it.", count: "Click each item to count it. Press Enter or Finish when done." }[V.tool];
  return `${t} ${scaleTxt}`;
}
function finishDraft() {
  if (V.tool === "cal") return;
  const need = V.tool === "len" ? 2 : V.tool === "area" ? 3 : 1;
  if (V.draft.length >= need) {
    const kind = V.tool, cat = document.getElementById("estCat")?.value || CATS[kind][0];
    S.takeoff.measures.push({ id: uid(), kind, cat, label: cat, pts: V.draft.map(p => [r2(p[0]), r2(p[1])]), page: S.takeoff.page });
    save();
  }
  V.draft = []; V.hover = null; draw(); renderTakeoffSide();
}
function mountCanvas() {
  const cv = document.getElementById("estCanvas"); if (!cv || cv.dataset.wired) return;
  cv.dataset.wired = "1";
  if (V.img && !V.zoom) fitView();
  cv.addEventListener("wheel", e => { if (!V.img) return; e.preventDefault(); const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top, f = Math.exp(-e.deltaY * 0.0015), nz = Math.min(20, Math.max(0.02, V.zoom * f)); V.panX = mx - (mx - V.panX) * nz / V.zoom; V.panY = my - (my - V.panY) * nz / V.zoom; V.zoom = nz; draw(); }, { passive: false });
  cv.addEventListener("pointerdown", e => {
    if (!V.img) return;
    cv.setPointerCapture(e.pointerId);
    if (V.tool === "pan" || e.button === 1 || e.button === 2 || e.shiftKey) { V.drag = { x: e.clientX, y: e.clientY, px: V.panX, py: V.panY }; return; }
    const p = toImg(cv, e);
    if (V.tool === "cal") { V.draft.push(p); if (V.draft.length === 2) { V.cal = V.draft; V.draft = []; renderTakeoffSide(); setTimeout(() => document.getElementById("estCalLen")?.focus(), 0); } draw(); return; }
    if (e.detail >= 2 && V.tool !== "count") { finishDraft(); return; }
    V.draft.push(p); draw();
    if (V.tool === "count") paintStatus(`${V.draft.length} counted. Press Enter or Finish to save.`);
  });
  cv.addEventListener("pointermove", e => {
    if (V.drag) { V.panX = V.drag.px + e.clientX - V.drag.x; V.panY = V.drag.py + e.clientY - V.drag.y; draw(); return; }
    if (V.draft.length) { V.hover = toImg(cv, e); draw(); }
  });
  cv.addEventListener("pointerup", () => { V.drag = null; });
  cv.addEventListener("contextmenu", e => e.preventDefault());
  new ResizeObserver(() => draw()).observe(cv);
  draw();
}
document.addEventListener("keydown", e => {
  if (HOST.getPage() !== PAGE || S.mode !== "blueprint") return;
  if (/^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
  if (e.key === "Enter" && V.draft.length) { e.preventDefault(); finishDraft(); }
  else if (e.key === "Escape") { V.draft = []; V.cal = null; V.hover = null; draw(); renderTakeoffSide(); }
  else if (e.key === "Backspace" && V.draft.length) { e.preventDefault(); V.draft.pop(); draw(); }
});

function takeoffToBQ() {
  const sums = {};
  S.takeoff.measures.forEach(m => { const v = measureValue(m); if (Number.isFinite(v)) sums[m.cat] = (sums[m.cat] || 0) + v; });
  const b = S.bq, set = (k, v) => { if (v > 0) b[k] = Math.round(v); };
  set("floorArea", sums["Floor area"]);
  if (sums["Floor area"]) b.footprint = Math.round(sums["Floor area"] / Math.max(1, b.stories));
  set("extWallLF", sums["Exterior wall"]);
  if (sums["Exterior wall"]) b.perimeter = Math.round(sums["Exterior wall"] / Math.max(1, b.stories));
  set("intWallLF", sums["Interior wall"]);
  set("windows", sums["Window"]); set("extDoors", sums["Exterior door"]); set("intDoors", sums["Interior door"]); set("fixtures", sums["Plumbing fixture"]);
  if (sums["Roof (plan view)"]) b.roofPlanArea = Math.round(sums["Roof (plan view)"]); else delete b.roofPlanArea;
  return Object.keys(sums).length;
}

/* ---------- AI reading ---------- */
const AI_SYS = `You are a senior construction estimator doing a quantity takeoff from an architectural drawing image.
Read dimensions, room labels, door and window symbols, notes and the drawing scale. Use printed dimensions over scaled measurements.
Return ONLY a JSON object with these keys (numbers in feet / square feet; use null when you cannot tell):
{"drawingType": string, "scaleNote": string|null, "stories": number|null, "floorAreaSqft": number|null, "footprintSqft": number|null,
 "perimeterLF": number|null, "exteriorWallLF": number|null, "interiorWallLF": number|null, "wallHeightFt": number|null, "roofPitch": number|null,
 "windows": number|null, "exteriorDoors": number|null, "interiorDoors": number|null, "fullBaths": number|null, "halfBaths": number|null,
 "kitchens": number|null, "laundry": number|null, "garageAreaSqft": number|null, "foundation": "slab"|"crawlspace"|"basement"|null,
 "rooms": [{"name": string, "widthFt": number|null, "lengthFt": number|null}], "confidence": "low"|"medium"|"high", "notes": [string]}
Count only what is visible on this sheet. Put assumptions and anything that needs field verification in "notes".`;
function aiImage() {
  const src = V.img; const max = 2048, s = Math.min(1, max / Math.max(src.width, src.height));
  const c = document.createElement("canvas"); c.width = Math.round(src.width * s); c.height = Math.round(src.height * s);
  const g = c.getContext("2d"); g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height); g.drawImage(src, 0, 0, c.width, c.height);
  return { url: c.toDataURL("image/jpeg", 0.86), s };
}
async function readWithAI() {
  if (!V.img) { alert("Open a blueprint first."); return; }
  let key = ""; try { key = localStorage.getItem(AI_KEY) || ""; } catch (e) {}
  const endpoint = (S.ai.endpoint || "").trim();
  if (!endpoint) { alert("Enter an AI endpoint in AI settings."); return; }
  const isOpenAI = /api\.openai\.com/.test(endpoint);
  if (!key && isOpenAI) { alert("Add your API key in AI settings first. It stays in this browser."); openDetails("estAiSettings"); return; }
  const { url, s } = aiImage(); const k = ftPerPx();
  const hint = k ? `Known scale for this image: 1 foot = ${(1 / (k / s)).toFixed(2)} image pixels (image is ${Math.round(V.img.width * s)} x ${Math.round(V.img.height * s)} px).` : "The drawing scale has not been set; rely on printed dimensions.";
  const body = { model: S.ai.model || "gpt-4.1-mini", response_format: { type: "json_object" }, messages: [{ role: "system", content: AI_SYS }, { role: "user", content: [{ type: "text", text: `Sheet: "${S.takeoff.file}" page ${S.takeoff.page}. ${hint} Project location: ${stateName()}. Return the JSON takeoff.` }, { type: "image_url", image_url: { url, detail: "high" } }] }] };
  const btn = document.getElementById("estAiBtn"); if (btn) { btn.disabled = true; btn.textContent = "Reading blueprint…"; }
  paintStatus("Sending this page to " + new URL(endpoint).host + "…");
  try {
    const res = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json", ...(key ? { Authorization: "Bearer " + key } : {}) }, body: JSON.stringify(body) });
    const txt = await res.text(); let j; try { j = JSON.parse(txt); } catch (e) { throw Error(`The AI service returned ${res.status}: ${txt.slice(0, 200)}`); }
    if (!res.ok) throw Error(j?.error?.message || `The AI service returned ${res.status}.`);
    let content = j?.choices?.[0]?.message?.content ?? j?.output_text ?? "";
    if (Array.isArray(content)) content = content.map(c => c.text || "").join("");
    const m = String(content).match(/\{[\s\S]*\}/); if (!m) throw Error("The AI reply did not include a JSON takeoff.");
    const out = JSON.parse(m[0]);
    applyAI(out);
    S.ai.last = { at: new Date().toISOString(), file: S.takeoff.file, page: S.takeoff.page, result: out };
    save(); toast("AI takeoff loaded. Review the building quantities before generating.");
  } catch (e) { alert("AI reading failed: " + (e.message || e)); }
  if (btn) { btn.disabled = false; btn.textContent = "Read with AI"; }
  renderTakeoffSide(); renderBQCard();
}
function applyAI(o) {
  const b = S.bq, n = v => (v === null || v === undefined || v === "" ? NaN : Number(v));
  const map = { stories: "stories", floorAreaSqft: "floorArea", footprintSqft: "footprint", perimeterLF: "perimeter", exteriorWallLF: "extWallLF", interiorWallLF: "intWallLF", wallHeightFt: "wallH", roofPitch: "roofPitch", windows: "windows", exteriorDoors: "extDoors", interiorDoors: "intDoors", fullBaths: "fullBaths", halfBaths: "halfBaths", kitchens: "kitchens", laundry: "laundry", garageAreaSqft: "garageArea" };
  Object.entries(map).forEach(([a, k]) => { const v = n(o[a]); if (Number.isFinite(v) && v >= 0) b[k] = r2(v); });
  if (["slab", "crawlspace", "basement"].includes(o.foundation)) b.foundation = o.foundation;
  if (!(n(o.footprintSqft) > 0) && b.floorArea && b.stories) b.footprint = Math.round(b.floorArea / Math.max(1, b.stories));
}

/* ---------- totals ---------- */
function totals() {
  const st = S.settings;
  let mat = 0, lab = 0; const byDiv = {};
  S.lines.forEach(l => { const m = num(l.qty) * num(l.mat), b = num(l.qty) * num(l.lab); mat += m; lab += b; (byDiv[l.div] = byDiv[l.div] || { mat: 0, lab: 0 }); byDiv[l.div].mat += m; byDiv[l.div].lab += b; });
  const direct = mat + lab, tax = mat * pos(st.tax) / 100, cont = direct * pos(st.contingency) / 100, permits = direct * pos(st.permits) / 100;
  const sub = direct + tax + cont + permits, overhead = sub * pos(st.overhead) / 100, profit = (sub + overhead) * pos(st.profit) / 100, total = sub + overhead + profit;
  return { mat, lab, direct, tax, cont, permits, sub, overhead, profit, total, byDiv };
}

/* ---------- PDF bid ---------- */
const HW = [278,278,355,556,556,889,667,191,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,278,278,584,584,584,556,1015,667,667,722,722,667,611,778,722,278,500,667,556,833,722,778,667,778,722,667,611,722,667,944,667,667,611,278,278,278,469,556,333,556,556,500,556,556,278,556,556,222,222,500,222,833,556,556,556,556,333,500,278,556,500,722,500,500,500,334,260,334,584];
const pdfText = s => String(s ?? "").replace(/[\u2018\u2019]/g, "'").replace(/[\u201c\u201d\u2033]/g, '"').replace(/[\u2013\u2014]/g, "-").replace(/\u00d7/g, "x").replace(/\u2026/g, "...").replace(/[\u2022\u25cf]/g, "\u00b7").replace(/[^\x20-\x7e\xa0-\xff]/g, "");
const tw = (s, size, bold) => { let w = 0; for (const ch of pdfText(s)) { const c = ch.charCodeAt(0); w += c < 127 ? HW[c - 32] : c === 0xb7 ? 278 : 556; } return w * size / 1000 * (bold ? 1.06 : 1); };
const fit = (s, size, max, bold) => { s = pdfText(s); if (tw(s, size, bold) <= max) return s; while (s.length && tw(s + "...", size, bold) > max) s = s.slice(0, -1); return s + "..."; };
const wrap = (s, size, max) => { const words = pdfText(s).split(/\s+/); const out = []; let cur = ""; words.forEach(w => { const t = cur ? cur + " " + w : w; if (tw(t, size) > max && cur) { out.push(cur); cur = w; } else cur = t; }); if (cur) out.push(cur); return out; };
function buildBidPdf() {
  const P = S.project, t = totals(), W = 612, Hh = 792, M = 40;
  const pages = []; let ops = [], y = 0;
  const esc2 = s => pdfText(s).replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)").replace(/[\xa0-\xff]/g, c => "\\" + c.charCodeAt(0).toString(8));
  const text = (x, yy, s, size = 9, bold = false, color = "0 0 0", align = "left") => { const str = pdfText(s); const xx = align === "right" ? x - tw(str, size, bold) : align === "center" ? x - tw(str, size, bold) / 2 : x; ops.push(`BT /${bold ? "F2" : "F1"} ${size} Tf ${color} rg ${xx.toFixed(2)} ${yy.toFixed(2)} Td (${esc2(str)}) Tj ET`); };
  const rect = (x, yy, w, h, color) => ops.push(`${color} rg ${x} ${yy.toFixed(2)} ${w} ${h} re f`);
  const line = (x1, y1, x2, y2, color = "0.8 0.8 0.8", w = 0.6) => ops.push(`${color} RG ${w} w ${x1} ${y1.toFixed(2)} m ${x2} ${y2.toFixed(2)} l S`);
  const C = { desc: M + 4, qty: 378, unit: 384, mat: 456, lab: 512, tot: W - M - 4 };
  const newPage = (first, noHeader) => {
    if (ops.length) pages.push(ops);
    ops = [];
    if (first) {
      rect(0, Hh - 92, W, 92, "0.051 0.263 0.184");
      text(M, Hh - 44, P.company || "Construction Estimate", 18, true, "1 1 1");
      text(M, Hh - 62, P.contact || "", 9, false, "0.85 0.93 0.89");
      text(W - M, Hh - 42, "ESTIMATE / BID", 16, true, "1 1 1", "right");
      text(W - M, Hh - 60, `${P.number || ""}   ${P.date || ""}`, 9, false, "0.85 0.93 0.89", "right");
      let yy = Hh - 118;
      text(M, yy, "PREPARED FOR", 8, true, "0.4 0.45 0.42"); text(320, yy, "PROJECT", 8, true, "0.4 0.45 0.42"); yy -= 14;
      text(M, yy, P.client || "-", 11, true); text(320, yy, fit(P.name || "-", 11, 252, true), 11, true); yy -= 13;
      text(M, yy, fit(P.address || "", 9, 260), 9); text(320, yy, `Location: ${stateName()} (cost factor ${factor().toFixed(2)})`, 9); yy -= 12;
      const valid = P.date ? new Date(new Date(P.date + "T12:00:00").getTime() + pos(P.validDays, 30) * 864e5).toISOString().slice(0, 10) : "";
      text(320, yy, `Valid until: ${valid || "-"}`, 9);
      y = yy - 24;
    } else { y = Hh - M - 6; text(M, y, `${P.company || "Estimate"} - ${P.number || ""} (continued)`, 9, true, "0.3 0.3 0.3"); y -= 18; }
    if (noHeader) return;
    rect(M, y - 5, W - 2 * M, 17, "0.91 0.94 0.92");
    text(C.desc, y, "DESCRIPTION", 7.5, true, "0.25 0.3 0.27"); text(C.qty, y, "QTY", 7.5, true, "0.25 0.3 0.27", "right"); text(C.unit, y, "UNIT", 7.5, true, "0.25 0.3 0.27");
    text(C.mat, y, "MATERIAL", 7.5, true, "0.25 0.3 0.27", "right"); text(C.lab, y, "LABOR", 7.5, true, "0.25 0.3 0.27", "right"); text(C.tot, y, "TOTAL", 7.5, true, "0.25 0.3 0.27", "right");
    y -= 20;
  };
  const need = (h, noHeader) => { if (y - h < 64) newPage(false, noHeader); };
  newPage(true);
  const divs = [...DIVS, ...new Set(S.lines.map(l => l.div).filter(d => !DIVS.includes(d)))];
  divs.forEach(d => {
    const rows = S.lines.filter(l => l.div === d); if (!rows.length) return;
    need(40); text(C.desc, y, d.toUpperCase(), 8.5, true, "0.05 0.42 0.28"); y -= 13;
    rows.forEach(l => {
      const dl = wrap(l.desc, 8.5, C.qty - C.desc - 48).slice(0, 2); if (dl.length === 2) dl[1] = fit(dl[1], 8.5, C.qty - C.desc - 48);
      need(12.5 * dl.length + 2); const q = num(l.qty), m = q * num(l.mat), b = q * num(l.lab);
      text(C.desc + 8, y, dl[0] || "", 8.5); if (dl[1]) text(C.desc + 8, y - 10.5, dl[1], 8.5); text(C.qty, y, qfmt(q), 8.5, false, "0 0 0", "right"); text(C.unit, y, l.unit || "", 8.5);
      text(C.mat, y, money(m), 8.5, false, "0 0 0", "right"); text(C.lab, y, money(b), 8.5, false, "0 0 0", "right"); text(C.tot, y, money(m + b), 8.5, true, "0 0 0", "right");
      y -= 12.5 + (dl[1] ? 10.5 : 0);
    });
    const s = t.byDiv[d]; line(C.unit, y + 8, C.tot + 4, y + 8);
    text(C.unit, y - 1, "Subtotal", 8, true, "0.35 0.35 0.35"); text(C.mat, y - 1, money(s.mat), 8, false, "0.35 0.35 0.35", "right"); text(C.lab, y - 1, money(s.lab), 8, false, "0.35 0.35 0.35", "right"); text(C.tot, y - 1, money(s.mat + s.lab), 8.5, true, "0 0 0", "right");
    y -= 20;
  });
  if (!S.lines.length) { text(C.desc, y, "No line items yet.", 9); y -= 20; }
  // Summary
  const st = S.settings;
  const sumRows = [["Materials", t.mat], ["Labor", t.lab], ["Direct cost", t.direct, true], [`Sales tax on materials (${pos(st.tax)}%)`, t.tax], [`Contingency (${pos(st.contingency)}%)`, t.cont], [`Permits & fees allowance (${pos(st.permits)}%)`, t.permits], [`Overhead (${pos(st.overhead)}%)`, t.overhead], [`Profit (${pos(st.profit)}%)`, t.profit]];
  need(sumRows.length * 14 + 60, true);
  const sx = 330; line(sx, y + 6, C.tot + 4, y + 6, "0.6 0.6 0.6", 0.8); y -= 8;
  sumRows.forEach(([k, v, b]) => { text(sx, y, k, 9, !!b); text(C.tot, y, money(v), 9, !!b, "0 0 0", "right"); y -= 14; });
  y -= 10; rect(sx - 6, y - 8, C.tot - sx + 14, 24, "0.051 0.263 0.184"); text(sx, y, "TOTAL BID", 11, true, "1 1 1"); text(C.tot, y, money(t.total), 12, true, "1 1 1", "right"); y -= 34;
  if (pos(S.bq.floorArea) > 0 && ["house", "shed"].includes(S.job.type) || S.mode !== "job") { const fa = S.mode === "job" && S.job.type === "shed" ? pos(S.job.p.W, 24) * pos(S.job.p.L, 24) : pos(S.bq.floorArea); if (fa > 0) { text(C.tot, y + 8, `${money(t.total / fa)} per sq ft (${qfmt(fa)} sf)`, 8, false, "0.35 0.35 0.35", "right"); y -= 8; } }
  // Notes & terms
  const notes = [P.notes, "Quantities and unit costs are planning estimates generated from the supplied plans or dimensions and regional averages. Verify on site; final pricing depends on site conditions, selections, supplier quotes and permits.", `This estimate is valid for ${pos(P.validDays, 30)} days. Work not listed above is excluded.`].filter(Boolean);
  notes.forEach((n, i) => { const ls = wrap(n, 8, W - 2 * M); need(ls.length * 10 + 14, true); if (i === 0 && P.notes) { text(M, y, "NOTES", 8, true, "0.4 0.45 0.42"); y -= 11; } ls.forEach(l => { text(M, y, l, 8, false, "0.25 0.25 0.25"); y -= 10; }); y -= 6; });
  need(60, true); y -= 18;
  line(M, y, M + 220, y, "0.4 0.4 0.4", 0.7); line(330, y, W - M, y, "0.4 0.4 0.4", 0.7);
  text(M, y - 11, "Accepted by (client signature)", 7.5, false, "0.4 0.4 0.4"); text(330, y - 11, "Date", 7.5, false, "0.4 0.4 0.4");
  pages.push(ops);
  // assemble
  const objs = [];
  const add = s => { objs.push(s); return objs.length; };
  add("<</Type/Catalog/Pages 2 0 R>>"); add("PAGES");
  const f1 = add("<</Type/Font/Subtype/Type1/BaseFont/Helvetica/Encoding/WinAnsiEncoding>>"), f2 = add("<</Type/Font/Subtype/Type1/BaseFont/Helvetica-Bold/Encoding/WinAnsiEncoding>>");
  const kids = [];
  pages.forEach((p, i) => {
    p.push(`BT /F1 7.5 Tf 0.5 0.5 0.5 rg ${M} 28 Td (${esc2(`${P.number || ""} - ${P.name || ""}`)}) Tj ET`);
    const pn = `Page ${i + 1} of ${pages.length}`; p.push(`BT /F1 7.5 Tf 0.5 0.5 0.5 rg ${(W - M - tw(pn, 7.5)).toFixed(2)} 28 Td (${pn}) Tj ET`);
    const stream = p.join("\n"); const c = add(`<</Length ${stream.length}>>\nstream\n${stream}\nendstream`);
    kids.push(add(`<</Type/Page/Parent 2 0 R/MediaBox[0 0 ${W} ${Hh}]/Resources<</Font<</F1 ${f1} 0 R/F2 ${f2} 0 R>>>>/Contents ${c} 0 R>>`));
  });
  objs[1] = `<</Type/Pages/Kids[${kids.map(k => k + " 0 R").join(" ")}]/Count ${kids.length}>>`;
  let out = "%PDF-1.4\n"; const offs = [];
  objs.forEach((o, i) => { offs.push(out.length); out += `${i + 1} 0 obj\n${o}\nendobj\n`; });
  const xref = out.length;
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n` + offs.map(o => String(o).padStart(10, "0") + " 00000 n \n").join("") + `trailer\n<</Size ${objs.length + 1}/Root 1 0 R/Info<</Title(${esc2("Estimate " + (P.number || ""))})/Producer(AcreForge Estimator)>>>>\nstartxref\n${xref}\n%%EOF`;
  return new Blob([out], { type: "application/pdf" });
}
function exportCsv() {
  const t = totals(), rows = [["Division", "Description", "Qty", "Unit", "Material unit $", "Labor unit $", "Material $", "Labor $", "Total $"]];
  S.lines.forEach(l => { const q = num(l.qty); rows.push([l.div, l.desc, q, l.unit, l.mat, l.lab, r2(q * l.mat), r2(q * l.lab), r2(q * (num(l.mat) + num(l.lab)))]); });
  rows.push([], ["", "Direct cost", "", "", "", "", r2(t.mat), r2(t.lab), r2(t.direct)], ["", "Sales tax", "", "", "", "", "", "", r2(t.tax)], ["", "Contingency", "", "", "", "", "", "", r2(t.cont)], ["", "Permits & fees", "", "", "", "", "", "", r2(t.permits)], ["", "Overhead", "", "", "", "", "", "", r2(t.overhead)], ["", "Profit", "", "", "", "", "", "", r2(t.profit)], ["", "TOTAL BID", "", "", "", "", "", "", r2(t.total)]);
  const csv = rows.map(r => r.map(x => `"${String(x ?? "").replace(/"/g, '""')}"`).join(",")).join("\r\n");
  download(`${(S.project.number || "estimate").replace(/[^\w-]+/g, "_")}.csv`, new Blob([csv], { type: "text/csv" }));
}

/* ---------- UI ---------- */
const sel = (attr, opts, val) => `<select class="input" ${attr}>${opts.map(o => Array.isArray(o) ? `<option value="${esc(o[0])}" ${String(o[0]) === String(val) ? "selected" : ""}>${esc(o[1])}</option>` : `<option ${String(o) === String(val) ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
const fld = (label, inner, extra = "") => `<label class="field" ${extra}><span class="label">${esc(label)}</span>${inner}</label>`;
const inp = (attr, val, type = "text", more = "") => `<input class="input" type="${type}" ${attr} value="${esc(val)}" ${more}>`;
function css() {
  if (document.getElementById("estCss")) return;
  const s = document.createElement("style"); s.id = "estCss";
  s.textContent = `#est .est-tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}#est .est-tab{border:1px solid var(--line);background:#19251f;border-radius:999px;padding:7px 14px;font-size:12px;font-weight:600;color:var(--text);cursor:pointer}#est .est-tab.on{background:#0d8b5a;border-color:#0d8b5a;color:#fff}
#est .est-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px}#est .est-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}#est .est-hint{font-size:12px;color:var(--muted)}
#est table.est-t{width:100%;border-collapse:collapse;font-size:12px}#est table.est-t th{text-align:left;color:var(--muted);font-weight:600;padding:6px 4px;border-bottom:1px solid var(--line);white-space:nowrap}#est table.est-t td{padding:3px 4px;border-bottom:1px solid rgba(255,255,255,.04);vertical-align:middle}
#est table.est-t input{width:100%;background:transparent;border:1px solid transparent;border-radius:6px;padding:4px 6px;color:var(--text);font:inherit}#est table.est-t input:hover{border-color:#304238}#est table.est-t input:focus{border-color:#0d8b5a;background:#0c1511;outline:none}
#est table.est-t .n{text-align:right;white-space:nowrap}#est table.est-t input.n{text-align:right}#est tr.est-div td{background:#13201a;color:#91e7bd;font-weight:700;font-size:11px;letter-spacing:.04em;text-transform:uppercase;padding:8px 6px}#est tr.est-sub td{color:var(--muted);font-size:11px}
#est .est-x{background:none;border:0;color:#9aa9a0;cursor:pointer;font-size:15px;padding:2px 6px;border-radius:6px}#est .est-x:hover{color:#fb7185;background:rgba(251,113,133,.1)}
#est .est-sum .key-value,#est .est-kv{display:flex;justify-content:space-between;gap:10px;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.05);font-size:13px}#est .est-total{display:flex;justify-content:space-between;margin-top:10px;padding:12px 14px;border-radius:10px;background:#0d8b5a;color:#fff;font-weight:800;font-size:18px}
#est .est-canvas{width:100%;height:min(66vh,620px);display:block;border-radius:10px;border:1px solid var(--line);touch-action:none;background:#1d2a24}#est .est-tools{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}#est .est-tool{border:1px solid var(--line);background:#19251f;border-radius:8px;padding:6px 10px;font-size:12px;font-weight:600;color:var(--text);cursor:pointer}#est .est-tool.on{background:#1f6f4f;border-color:#34d399}
#est .est-take{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:14px}@media(max-width:1000px){#est .est-take{grid-template-columns:1fr}}#est .est-mlist{max-height:330px;overflow:auto}#est .est-dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:-1px}
#est details>summary{cursor:pointer;font-weight:600}#est .est-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:14px}#est .est-kpi{background:#13201a;border:1px solid var(--line);border-radius:12px;padding:10px 12px}#est .est-kpi span{display:block;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}#est .est-kpi b{font-size:20px}`;
  document.head.appendChild(s);
}
function page() {
  const P = S.project;
  const tabs = [["job", "Describe a job"], ["plan", "From Lot Builder plan"], ["blueprint", "Blueprint takeoff"]];
  return `<div id="est"><div class="page-head"><div><div class="eyebrow">ESTIMATING</div><h2>Estimator</h2><p>Blueprints in, bid-ready estimates out. Describe a job, use your Lot Builder plan, or measure a blueprint, then edit the line items and export a bid.</p></div><div class="actions"><button class="btn" data-est="save-json">Save estimate file</button><button class="btn" data-est="open-json">Open estimate file</button><button class="btn" data-est="new">New estimate</button></div></div>
<div class="card" style="margin-bottom:14px"><details ${P.client || P.company ? "" : "open"}><summary>Project & bid details</summary><div class="est-grid" style="margin-top:10px">
${fld("Project name", inp('data-p="name"', P.name))}${fld("Client", inp('data-p="client"', P.client))}${fld("Job site address", inp('data-p="address"', P.address))}${fld("Your company", inp('data-p="company"', P.company))}${fld("Phone / email / license #", inp('data-p="contact"', P.contact))}
${fld("Estimate #", inp('data-p="number"', P.number))}${fld("Date", inp('data-p="date"', P.date, "date"))}${fld("Valid for (days)", inp('data-p="validDays"', P.validDays, "number", 'min="1"'))}
${fld("Location (state)", sel('data-p="state"', STATES.map(s => [s[0], `${s[1]} (${s[2].toFixed(2)})`]), P.state))}${fld("Custom cost factor (optional)", inp('data-p="factor"', P.factor, "number", 'step="0.01" min="0.3" max="3" placeholder="e.g. 1.07"'))}
${fld("Finish level", sel('data-s="finish"', [["basic", "Basic / builder grade"], ["standard", "Standard"], ["premium", "Premium"]], S.settings.finish))}
</div><label class="field" style="margin-top:10px"><span class="label">Notes shown on the bid</span><textarea class="input" data-p="notes" rows="2" placeholder="Scope, exclusions, payment terms…">${esc(P.notes)}</textarea></label>
<p class="est-hint" style="margin-top:8px">Location factors are approximate regional adjustments (national average = 1.00) for a first-pass number. For a bid you'll sign, replace unit costs with your supplier and sub quotes.</p></details></div>
<div class="est-tabs" role="tablist">${tabs.map(([k, l]) => `<button class="est-tab ${S.mode === k ? "on" : ""}" role="tab" aria-selected="${S.mode === k}" data-est="mode" data-v="${k}">${l}</button>`).join("")}</div>
<div id="estSource">${S.mode === "job" ? jobCard() : S.mode === "plan" ? planCard() : blueprintCard()}</div>
<div id="estBQWrap">${S.mode !== "job" || S.job.type === "house" ? bqCard() : ""}</div>
<div id="estLines">${linesCard()}</div></div>`;
}
function jobCard() {
  const j = JOBS[S.job.type] || JOBS.deck, p = S.job.p;
  return `<div class="card" style="margin-bottom:14px"><div class="between"><h3>Describe the job</h3><span class="pill">No plans needed</span></div>
<div class="est-grid" style="margin-top:8px">${fld("Job type", sel('data-est-job="type"', Object.entries(JOBS).map(([k, v]) => [k, v.name]), S.job.type))}
${j.fields.map(([k, label, a, d]) => Array.isArray(a) ? fld(label, sel(`data-jp="${k}"`, a, p[k] ?? d)) : fld(label, inp(`data-jp="${k}"`, p[k] ?? a, "number", 'min="0" step="any"'))).join("")}</div>
${S.job.type === "house" ? `<p class="est-hint" style="margin-top:8px">Enter the building quantities below, or use the Lot Builder or Blueprint tabs to fill them in.</p>` : `<div class="est-row" style="margin-top:12px"><button class="btn primary" data-est="gen" data-v="replace">Generate estimate</button><button class="btn" data-est="gen" data-v="append">Add to current estimate</button></div>`}</div>`;
}
function planCard() {
  const q = readLotBuilder();
  if (!q) return `<div class="card" style="margin-bottom:14px"><h3>From Lot Builder plan</h3><p class="est-hint">No Lot Builder plan was found in this browser yet.</p><button class="btn primary" data-page="homes">Open Lot Builder</button></div>`;
  if (q.empty) return `<div class="card" style="margin-bottom:14px"><h3>From Lot Builder plan</h3><p class="est-hint">"${esc(q.name)}" has no rooms yet. Draw rooms in the Lot Builder, then come back.</p><button class="btn primary" data-page="homes">Open Lot Builder</button></div>`;
  const kv = (k, v) => `<div class="est-kv"><span>${k}</span><strong>${v}</strong></div>`;
  return `<div class="card" style="margin-bottom:14px"><div class="between"><h3>From Lot Builder plan: ${esc(q.name)}</h3><span class="pill">Read from your saved plan</span></div>
<div class="grid g2" style="margin-top:8px"><div>${kv("Levels", q.stories)}${kv("Floor area (all levels)", qfmt(q.floorArea) + " sf")}${kv("Ground floor footprint", qfmt(q.footprint) + " sf")}${kv("Footprint perimeter", qfmt(q.perimeter) + " ft")}${kv("Exterior walls", qfmt(q.extWallLF) + " ft")}${kv("Interior walls", qfmt(q.intWallLF) + " ft")}</div>
<div>${kv("Windows", q.windows)}${kv("Exterior / interior doors", `${q.extDoors} / ${q.intDoors}`)}${kv("Baths / kitchens / laundry", `${q.fullBaths} / ${q.kitchens} / ${q.laundry}`)}${kv("Garage / shop area", qfmt(q.garageArea) + " sf")}${kv("Plumbing fixtures", q.fixtures)}${kv("Room types", esc(Object.entries(q.types).map(([t, n]) => `${n} ${t}`).join(", ")))}</div></div>
<div class="est-row" style="margin-top:12px"><button class="btn primary" data-est="use-plan">Use these quantities</button><span class="est-hint">Fills the building quantities below. Review them, then generate.</span></div></div>`;
}
function blueprintCard() {
  const t = S.takeoff;
  const tools = [["pan", "✋ Pan"], ["cal", "📏 Calibrate"], ["len", "─ Length"], ["area", "▱ Area"], ["count", "• Count"]];
  return `<div class="card" style="margin-bottom:14px"><div class="between"><h3>Blueprint takeoff</h3><span class="pill">Files stay in your browser</span></div>
<div class="est-row" style="margin:8px 0 10px"><label class="btn primary" style="cursor:pointer">Open blueprint (PDF or image)<input type="file" id="estFile" accept="application/pdf,.pdf,image/png,image/jpeg,image/webp" hidden></label>
${t.pages > 1 ? `<span class="est-row"><button class="btn" data-est="pg" data-v="-1" ${t.page <= 1 ? "disabled" : ""}>‹</button><span class="small">Page ${t.page} of ${t.pages}</span><button class="btn" data-est="pg" data-v="1" ${t.page >= t.pages ? "disabled" : ""}>›</button></span>` : ""}
<span class="est-hint">${t.file ? esc(t.file) : "Tip: export each plan sheet as a PDF for the sharpest result."}</span></div>
<div class="est-take"><div><div class="est-tools">${tools.map(([k, l]) => `<button class="est-tool ${V.tool === k ? "on" : ""}" data-est="tool" data-v="${k}">${l}</button>`).join("")}
<button class="est-tool" data-est="finish">Finish</button><button class="est-tool" data-est="zoom" data-v="1.25">＋</button><button class="est-tool" data-est="zoom" data-v="0.8">－</button><button class="est-tool" data-est="fit">Fit</button></div>
<canvas id="estCanvas" class="est-canvas" aria-label="Blueprint viewer. Use the tools above to calibrate and measure."></canvas><div id="estTakeStatus" class="est-hint" style="margin-top:6px">${esc(toolHelp())}</div></div>
<div id="estTakeSide">${takeoffSide()}</div></div></div>`;
}
function takeoffSide() {
  const t = S.takeoff, k = ftPerPx();
  const kind = ["len", "area", "count"].includes(V.tool) ? V.tool : "len";
  const ms = t.measures.filter(m => (m.page || 1) === t.page);
  let key = ""; try { key = localStorage.getItem(AI_KEY) || ""; } catch (e) {}
  const last = S.ai.last && S.ai.last.file === t.file && S.ai.last.page === t.page ? S.ai.last.result : null;
  return `<div class="stack" style="display:grid;gap:12px">
<div class="card" style="padding:12px"><h4 style="margin:0 0 6px">Scale</h4>
${V.isPdf ? `<div class="est-row" style="margin-bottom:6px">${sel('data-t="scaleMode"', [["arch", "Use drawing scale"], ["calibrate", "Calibrate from a dimension"]], t.scaleMode)}</div>` : ""}
${V.isPdf && t.scaleMode === "arch" ? fld("Drawing scale (from the title block)", sel('data-t="archScale"', ARCH, t.archScale)) : V.cal ? `<div class="est-row"><input class="input" id="estCalLen" type="number" min="0" step="any" placeholder="Real length in feet" style="flex:1"><button class="btn primary" data-est="cal-apply">Set scale</button></div><p class="est-hint">Tip: 12'-6" = 12.5</p>` : `<p class="est-hint" style="margin:0">${k ? `Calibrated: 1 ft = ${qfmt(1 / k)} px.` : "Pick 📏 Calibrate and click both ends of a known dimension."}</p>`}</div>
<div class="card" style="padding:12px"><h4 style="margin:0 0 6px">Measurements (page ${t.page})</h4>${fld("Next measurement is", sel('id="estCat"', CATS[kind], document.getElementById("estCat")?.value && CATS[kind].includes(document.getElementById("estCat").value) ? document.getElementById("estCat").value : CATS[kind][0]))}
<div class="est-mlist" style="margin-top:8px">${ms.length ? ms.map(m => { const v = measureValue(m); return `<div class="est-kv" style="align-items:center"><span style="min-width:0;flex:1"><span class="est-dot" style="background:${COLORS[m.kind]}"></span>${sel(`data-mcat="${m.id}"`, CATS[m.kind], m.cat).replace('class="input"', 'class="input" style="display:inline-block;width:auto;padding:3px 6px"')}</span><strong>${Number.isFinite(v) ? qfmt(v) + " " + unitOf(m) : "set scale"}</strong><button class="est-x" title="Add as a line item" data-est="m-line" data-id="${m.id}">＋</button><button class="est-x" title="Delete" data-est="m-del" data-id="${m.id}">×</button></div>`; }).join("") : `<p class="est-hint">No measurements on this page yet.</p>`}</div>
${t.measures.length ? `<div class="est-row" style="margin-top:8px"><button class="btn primary" data-est="take-bq">Send totals to building quantities</button></div>` : ""}</div>
<div class="card" style="padding:12px"><h4 style="margin:0 0 6px">AI blueprint reading <span class="pill warn">Optional</span></h4><p class="est-hint" style="margin:0 0 8px">Sends only this page image to your AI provider and fills in the building quantities for you to review.</p>
<button class="btn primary" id="estAiBtn" data-est="ai" ${V.img ? "" : "disabled"}>Read with AI</button>
<details id="estAiSettings" style="margin-top:8px"><summary class="small">AI settings</summary><div style="display:grid;gap:8px;margin-top:8px">${fld("Endpoint (OpenAI-compatible)", inp('data-ai="endpoint"', S.ai.endpoint))}${fld("Model (must support images)", inp('data-ai="model"', S.ai.model))}${fld("API key (saved only in this browser)", `<input class="input" type="password" id="estAiKey" autocomplete="off" placeholder="${key ? "Saved. Type to replace" : "sk-..."}">`)}<div class="est-row"><button class="btn" data-est="ai-key">Save key</button>${key ? `<button class="btn" data-est="ai-key-clear">Remove key</button>` : ""}</div><p class="est-hint">For a public launch, point the endpoint at your own server proxy so customers don't need a key.</p></div></details>
${last ? `<div style="margin-top:10px"><div class="est-kv"><span>AI confidence</span><strong>${esc(last.confidence || "?")}</strong></div>${last.scaleNote ? `<div class="est-kv"><span>Scale read</span><strong>${esc(last.scaleNote)}</strong></div>` : ""}${Array.isArray(last.rooms) && last.rooms.length ? `<details><summary class="small">${last.rooms.length} rooms found</summary>${last.rooms.map(r => `<div class="est-kv"><span>${esc(r.name)}</span><strong>${r.widthFt && r.lengthFt ? `${r2(r.widthFt)} × ${r2(r.lengthFt)} ft` : "-"}</strong></div>`).join("")}</details>` : ""}${Array.isArray(last.notes) ? last.notes.slice(0, 6).map(n => `<p class="est-hint" style="margin:4px 0">• ${esc(n)}</p>`).join("") : ""}</div>` : ""}</div></div>`;
}
function renderTakeoffSide() { const el = document.getElementById("estTakeSide"); if (el) el.innerHTML = takeoffSide(); paintStatus(toolHelp()); document.querySelectorAll('#est [data-est="tool"]').forEach(b => b.classList.toggle("on", b.dataset.v === V.tool)); }
function bqCard() {
  const b = S.bq;
  return `<div class="card" style="margin-bottom:14px" id="estBQ"><div class="between"><h3>Building quantities</h3><span class="pill warn">Review before generating</span></div>
<div class="est-grid" style="margin-top:8px">${BQ_FIELDS.map(([k, l]) => fld(l, inp(`data-bq="${k}"`, b[k] ?? "", "number", 'min="0" step="any"'))).join("")}${BQ_SELECTS.map(([k, l, o]) => fld(l, sel(`data-bq="${k}"`, o, b[k]))).join("")}</div>
${b.roofPlanArea ? `<p class="est-hint" style="margin-top:6px">Roof plan area from takeoff: ${qfmt(b.roofPlanArea)} sf. <button class="btn" data-est="clear-roof">Use footprint instead</button></p>` : ""}
<div class="est-row" style="margin-top:12px"><button class="btn primary" data-est="gen-house" data-v="replace">Generate estimate</button><button class="btn" data-est="gen-house" data-v="append">Add to current estimate</button><button class="btn" data-est="bq-reset">Reset quantities</button></div></div>`;
}
function renderBQCard() { const el = document.getElementById("estBQWrap"); if (el) el.innerHTML = S.mode !== "job" || S.job.type === "house" ? bqCard() : ""; }
function linesCard() {
  const t = totals(), st = S.settings;
  const divs = [...DIVS, ...new Set(S.lines.map(l => l.div).filter(d => !DIVS.includes(d)))];
  const body = divs.map(d => {
    const rows = S.lines.filter(l => l.div === d); if (!rows.length) return "";
    const s = t.byDiv[d];
    return `<tr class="est-div"><td colspan="8">${esc(d)}</td></tr>` + rows.map(l => { const q = num(l.qty); return `<tr data-line="${l.id}"><td style="min-width:300px;width:50%"><input data-l="desc" value="${esc(l.desc)}" aria-label="Description"></td><td style="width:84px"><input class="n" data-l="qty" type="number" step="any" value="${esc(l.qty)}" aria-label="Quantity"></td><td style="width:58px"><input data-l="unit" value="${esc(l.unit)}" aria-label="Unit"></td><td style="width:96px"><input class="n" data-l="mat" type="number" step="any" value="${esc(l.mat)}" aria-label="Material unit cost"></td><td style="width:96px"><input class="n" data-l="lab" type="number" step="any" value="${esc(l.lab)}" aria-label="Labor unit cost"></td><td class="n" style="width:110px" data-tot="${l.id}"><b>${money(q * (num(l.mat) + num(l.lab)))}</b></td><td style="width:30px"><button class="est-x" title="Remove line" data-est="del" data-id="${l.id}">×</button></td></tr>`; }).join("")
      + `<tr class="est-sub"><td colspan="5" class="n">${esc(d)} subtotal</td><td class="n" data-dtot="${esc(d)}">${money(s.mat + s.lab)}</td><td></td></tr>`;
  }).join("");
  const pct = (k, l) => `<div class="est-kv"><span>${l} <input class="input" style="display:inline-block;width:64px;padding:3px 6px;margin-left:4px" type="number" step="0.5" min="0" data-s="${k}" value="${esc(st[k])}">%</span><strong data-sum="${k}"></strong></div>`;
  const fa = S.mode === "job" && S.job.type !== "house" ? 0 : pos(S.bq.floorArea);
  return `<div class="est-kpis"><div class="est-kpi"><span>Total bid</span><b data-kpi="total">${money(t.total)}</b></div><div class="est-kpi"><span>Materials</span><b data-kpi="mat">${money(t.mat)}</b></div><div class="est-kpi"><span>Labor</span><b data-kpi="lab">${money(t.lab)}</b></div><div class="est-kpi"><span>${fa ? "Per sq ft" : "Line items"}</span><b data-kpi="psf">${fa ? money(t.total / fa) : S.lines.length}</b></div></div>
<div class="grid g2" style="grid-template-columns:minmax(0,2.2fr) minmax(260px,1fr);align-items:start"><div class="card"><div class="between"><h3>Line items</h3><span class="est-hint">Prices for ${esc(stateName())} × ${factor().toFixed(2)}. Click any cell to edit.</span></div>
<div class="table-wrap" style="overflow:auto"><table class="est-t"><thead><tr><th>Description</th><th class="n">Qty</th><th>Unit</th><th class="n">Material $/unit</th><th class="n">Labor $/unit</th><th class="n">Line total</th><th></th></tr></thead><tbody>${body || `<tr><td colspan="7" class="est-hint" style="padding:18px 6px">No line items yet. Generate an estimate above, or add a line.</td></tr>`}</tbody></table></div>
<div class="est-row" style="margin-top:10px">${sel('id="estNewDiv"', DIVS, "Custom").replace('class="input"', 'class="input" style="width:auto"')}<button class="btn" data-est="add">+ Add line</button>${S.lines.length ? `<button class="btn" data-est="clear">Remove all lines</button>` : ""}</div></div>
<div class="card est-sum"><h3>Bid summary</h3><div class="est-kv"><span>Materials</span><strong data-sum="mat"></strong></div><div class="est-kv"><span>Labor</span><strong data-sum="lab"></strong></div><div class="est-kv"><span><b>Direct cost</b></span><strong data-sum="direct"></strong></div>
${pct("tax", "Sales tax on materials")}${pct("contingency", "Contingency")}${pct("permits", "Permits & fees")}${pct("overhead", "Overhead")}${pct("profit", "Profit")}
<div class="est-total"><span>Total bid</span><span data-sum="total"></span></div>
<div style="display:grid;gap:8px;margin-top:14px"><button class="btn primary" data-est="pdf" ${S.lines.length ? "" : "disabled"}>Download bid PDF</button><button class="btn" data-est="csv" ${S.lines.length ? "" : "disabled"}>Export spreadsheet (CSV)</button></div>
<p class="est-hint" style="margin-top:10px">Planning estimate only. Quantities come from your inputs and unit costs are editable regional averages, not quotes. Verify before you sign a contract.</p></div></div>`;
}
function updateTotals() {
  const t = totals(), root = document.getElementById("est"); if (!root) return;
  const set = (sel, v) => { const el = root.querySelector(sel); if (el) el.textContent = v; };
  ["mat", "lab", "direct", "tax", "permits", "overhead", "profit", "total"].forEach(k => set(`[data-sum="${k}"]`, money(t[k])));
  set('[data-sum="contingency"]', money(t.cont));
  set('[data-kpi="total"]', money(t.total)); set('[data-kpi="mat"]', money(t.mat)); set('[data-kpi="lab"]', money(t.lab));
  const fa = S.mode === "job" && S.job.type !== "house" ? 0 : pos(S.bq.floorArea);
  set('[data-kpi="psf"]', fa ? money(t.total / fa) : String(S.lines.length));
  S.lines.forEach(l => { const el = root.querySelector(`[data-tot="${l.id}"]`); if (el) el.innerHTML = `<b>${money(num(l.qty) * (num(l.mat) + num(l.lab)))}</b>`; });
  Object.entries(t.byDiv).forEach(([d, s]) => { const el = root.querySelector(`[data-dtot="${CSS.escape(d)}"]`); if (el) el.textContent = money(s.mat + s.lab); });
}
function renderLines() { const el = document.getElementById("estLines"); if (el) { el.innerHTML = linesCard(); updateTotals(); } }
function renderAll() {
  const c = HOST.content(); if (!c) return;
  css(); c.innerHTML = page(); updateTotals();
  if (S.mode === "blueprint") { mountCanvas(); requestAnimationFrame(() => { if (V.img && !document.getElementById("estCanvas")?.dataset.fitted) { fitView(); document.getElementById("estCanvas").dataset.fitted = "1"; } draw(); }); }
}
function setLines(newLines, how) {
  if (how === "replace" && S.lines.length && !confirm("Replace the current line items with the new estimate?")) return false;
  S.lines = how === "append" ? [...S.lines, ...newLines] : newLines;
  S.appliedFactor = factor(); save(); renderLines();
  document.getElementById("estLines")?.scrollIntoView({ behavior: "smooth", block: "start" });
  toast(`${newLines.length} line items ${how === "append" ? "added" : "generated"}.`);
  return true;
}
function openDetails(id) { const d = document.getElementById(id); if (d) d.open = true; }

/* ---------- events (scoped to #est) ---------- */
document.addEventListener("click", e => {
  const b = e.target.closest && e.target.closest("#est [data-est]"); if (!b || HOST.getPage() !== PAGE) return;
  const a = b.dataset.est, v = b.dataset.v;
  if (a === "mode") { S.mode = v; save(); renderAll(); }
  else if (a === "gen") { setLines(mkLines(jobLines(S.job.type, S.job.p, S.settings.finish)), v); }
  else if (a === "gen-house") { if (!(pos(S.bq.floorArea) > 0)) { alert("Enter the floor area first."); return; } setLines(mkLines(houseLines(S.bq, S.settings.finish)), v); }
  else if (a === "use-plan") { const q = readLotBuilder(); if (!q || q.empty) return; const b2 = S.bq; ["stories", "floorArea", "footprint", "perimeter", "extWallLF", "intWallLF", "windows", "extDoors", "intDoors", "fullBaths", "kitchens", "laundry", "garageArea", "fixtures"].forEach(k => b2[k] = q[k]); b2.halfBaths = 0; delete b2.roofPlanArea; save(); renderBQCard(); document.getElementById("estBQ")?.scrollIntoView({ behavior: "smooth", block: "start" }); toast("Plan quantities loaded. Review and generate."); }
  else if (a === "bq-reset") { S.bq = defaultBQ(); save(); renderBQCard(); }
  else if (a === "clear-roof") { delete S.bq.roofPlanArea; save(); renderBQCard(); }
  else if (a === "del") { S.lines = S.lines.filter(l => l.id !== b.dataset.id); save(); renderLines(); }
  else if (a === "add") { const d = document.getElementById("estNewDiv")?.value || "Custom"; S.lines.push({ id: uid(), div: d, desc: "New item", qty: 1, unit: "ea", mat: 0, lab: 0 }); save(); renderLines(); const rows = document.querySelectorAll(`#est tr[data-line] input[data-l="desc"]`); const last = [...rows].find(i => i.closest("tr").dataset.line === S.lines.at(-1).id); last?.focus(); last?.select(); }
  else if (a === "clear") { if (confirm("Remove all line items?")) { S.lines = []; save(); renderLines(); } }
  else if (a === "pdf") { download(`${(S.project.number || "estimate").replace(/[^\w-]+/g, "_")}-bid.pdf`, buildBidPdf()); }
  else if (a === "csv") exportCsv();
  else if (a === "new") { if (confirm("Start a new estimate? Save an estimate file first if you want to keep this one.")) { const keepAi = S.ai, keepCo = { company: S.project.company, contact: S.project.contact, state: S.project.state }; S = defaults(); S.ai = { ...keepAi, last: null }; Object.assign(S.project, keepCo); V.img = null; V.pdf = null; save(); renderAll(); } }
  else if (a === "save-json") download(`${(S.project.number || "estimate").replace(/[^\w-]+/g, "_")}.estimate.json`, new Blob([JSON.stringify({ ...S, ai: { endpoint: S.ai.endpoint, model: S.ai.model } }, null, 2)], { type: "application/json" }));
  else if (a === "open-json") { const i = document.createElement("input"); i.type = "file"; i.accept = ".json,application/json"; i.onchange = async () => { try { const o = JSON.parse(await i.files[0].text()); if (!o || o.v !== 1 || !Array.isArray(o.lines)) throw 0; localStorage.setItem(KEY, JSON.stringify({ ...o, ai: { ...S.ai, ...o.ai } })); S = load(); V.img = null; V.pdf = null; renderAll(); toast("Estimate opened."); } catch (err) { alert("That file is not an AcreForge estimate."); } }; i.click(); }
  else if (a === "tool") { V.tool = v; V.draft = []; V.hover = null; if (v !== "cal") V.cal = null; renderTakeoffSide(); draw(); }
  else if (a === "finish") finishDraft();
  else if (a === "zoom") { const cv = document.getElementById("estCanvas"); if (!cv || !V.img) return; const f = num(v, 1), mx = cv.clientWidth / 2, my = cv.clientHeight / 2, nz = Math.min(20, Math.max(.02, V.zoom * f)); V.panX = mx - (mx - V.panX) * nz / V.zoom; V.panY = my - (my - V.panY) * nz / V.zoom; V.zoom = nz; draw(); }
  else if (a === "fit") { fitView(); draw(); }
  else if (a === "pg") { const n = S.takeoff.page + num(v); if (n < 1 || n > S.takeoff.pages) return; S.takeoff.page = n; save(); if (V.pdf) renderPdfPage().then(() => { draw(); renderTakeoffSide(); }); renderAll(); }
  else if (a === "cal-apply") { const len = num(document.getElementById("estCalLen")?.value, 0); if (!(len > 0) || !V.cal) { alert("Enter the real length in feet."); return; } const px = Math.hypot(V.cal[1][0] - V.cal[0][0], V.cal[1][1] - V.cal[0][1]); if (px < 2) { alert("Those points are too close together."); return; } S.takeoff.ftPerPx = len / px; S.takeoff.scaleMode = "calibrate"; V.cal = null; V.tool = "len"; save(); renderTakeoffSide(); draw(); toast("Scale set."); }
  else if (a === "m-del") { S.takeoff.measures = S.takeoff.measures.filter(m => m.id !== b.dataset.id); save(); renderTakeoffSide(); draw(); }
  else if (a === "m-line") { const m = S.takeoff.measures.find(x => x.id === b.dataset.id); if (!m) return; const v2 = measureValue(m); if (!Number.isFinite(v2)) { alert("Set the scale first."); return; } S.lines.push({ id: uid(), div: "Custom", desc: `${m.cat} (from ${S.takeoff.file || "blueprint"} p.${m.page || 1})`, qty: r2(v2), unit: unitOf(m), mat: 0, lab: 0 }); save(); renderLines(); toast("Added. Enter unit costs in the line items."); }
  else if (a === "take-bq") { const n = takeoffToBQ(); if (!n) { alert("Set the scale and add measurements first."); return; } save(); renderBQCard(); document.getElementById("estBQ")?.scrollIntoView({ behavior: "smooth", block: "start" }); toast("Measurements sent to building quantities."); }
  else if (a === "ai") readWithAI();
  else if (a === "ai-key") { const k = document.getElementById("estAiKey")?.value.trim(); if (!k) return; try { localStorage.setItem(AI_KEY, k); } catch (err) {} renderTakeoffSide(); openDetails("estAiSettings"); toast("Key saved in this browser."); }
  else if (a === "ai-key-clear") { try { localStorage.removeItem(AI_KEY); } catch (err) {} renderTakeoffSide(); openDetails("estAiSettings"); }
});
document.addEventListener("input", e => {
  const el = e.target; if (!el.closest || !el.closest("#est") || HOST.getPage() !== PAGE) return;
  if (el.dataset.l) { const id = el.closest("tr")?.dataset.line, l = S.lines.find(x => x.id === id); if (!l) return; l[el.dataset.l] = ["qty", "mat", "lab"].includes(el.dataset.l) ? num(el.value) : el.value; save(); updateTotals(); }
  else if (el.dataset.p && el.tagName !== "SELECT" && el.dataset.p !== "factor") { S.project[el.dataset.p] = el.value; save(); }
  else if (el.dataset.s && el.tagName !== "SELECT") { S.settings[el.dataset.s] = num(el.value); save(); updateTotals(); }
  else if (el.dataset.bq && el.tagName !== "SELECT") { S.bq[el.dataset.bq] = el.value === "" ? "" : num(el.value); save(); }
  else if (el.dataset.jp && el.tagName !== "SELECT") { S.job.p[el.dataset.jp] = num(el.value); save(); }
  else if (el.dataset.ai) { S.ai[el.dataset.ai] = el.value; save(); }
});
document.addEventListener("change", e => {
  const el = e.target; if (!el.closest || !el.closest("#est") || HOST.getPage() !== PAGE) return;
  if (el.id === "estFile") { openFile(el.files[0]); el.value = ""; return; }
  if (el.dataset.p === "state" || el.dataset.p === "factor") {
    const old = factor(); S.project[el.dataset.p] = el.value; const nf = factor();
    if (S.lines.length && Math.abs(nf - old) > 1e-6 && confirm(`Re-price all ${S.lines.length} line items for the new location factor (${old.toFixed(2)} → ${nf.toFixed(2)})?`)) S.lines.forEach(l => { l.mat = r2(num(l.mat) * nf / old); l.lab = r2(num(l.lab) * nf / old); });
    save(); renderLines(); return;
  }
  if (el.dataset.p) { S.project[el.dataset.p] = el.value; save(); }
  else if (el.dataset.s) { S.settings[el.dataset.s] = el.tagName === "SELECT" ? el.value : num(el.value); save(); updateTotals(); }
  else if (el.dataset.bq && el.tagName === "SELECT") { S.bq[el.dataset.bq] = el.value; save(); }
  else if (el.dataset.estJob) { S.job.type = el.value; S.job.p = {}; save(); document.getElementById("estSource").innerHTML = jobCard(); renderBQCard(); updateTotals(); }
  else if (el.dataset.jp && el.tagName === "SELECT") { S.job.p[el.dataset.jp] = el.value; save(); }
  else if (el.dataset.t) { S.takeoff[el.dataset.t] = el.value; save(); renderTakeoffSide(); draw(); }
  else if (el.dataset.mcat) { const m = S.takeoff.measures.find(x => x.id === el.dataset.mcat); if (m) { m.cat = el.value; m.label = el.value; save(); draw(); } }
});

/* ---------- integrate with the app ---------- */
const navItems = HOST.navItems;
if (!navItems.some(n => n[0] === PAGE)) { const i = navItems.findIndex(n => n[0] === "homes"); navItems.splice(i >= 0 ? i + 1 : navItems.length, 0, [PAGE, "▧", "Estimator"]); }
HOST.wrapRender(() => {
  const p = HOST.getPage();
  if (p === PAGE) renderAll();
});
new MutationObserver(() => { if (HOST.getPage() === "homes") addLotBuilderButton(); }).observe(document.body, { childList: true, subtree: true });
function addLotBuilderButton() {
  const sched = document.getElementById("hbsched");
  if (!sched || document.getElementById("hbToEstimate")) return;
  const b = document.createElement("button"); b.id = "hbToEstimate"; b.className = "hbb"; b.type = "button"; b.textContent = "Estimate this plan in Estimator →";
  b.style.cssText = "margin-top:8px;width:100%;background:#0d8b5a;color:#fff;border:0;border-radius:8px;padding:8px 10px;font-weight:700;cursor:pointer";
  b.onclick = () => { S.mode = "plan"; save(); HOST.setPage(PAGE); };
  sched.insertAdjacentElement("afterend", b);
}
// Expose for testing / other modules.
window.AcreForgeEstimator = { state: () => S, view: V, houseLines, jobLines, readLotBuilder, totals, buildBidPdf, applyAI, takeoffToBQ, measureValue };
HOST.rerender();
})();
