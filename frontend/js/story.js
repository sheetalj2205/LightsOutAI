/* Lights Out AI: the 4-step page.
   1 Photo -> 2 Location (tonight's forecast) -> 3 AI decides -> 4 Impact.
   Talks to the backend through Sakshi's window.LO (js/api.js); draws the 3D scene with scene3d.js
   (the building's real photo on a 3D block). */
import { createScene } from "./scene3d.js";
import { createPhotoView } from "./photoview.js";
import { initPhotoStep } from "./photostep.js";
import { renderCompare } from "./compare.js";

const LO = window.LO;
const $ = (id) => document.getElementById(id);
const AI_NAMES = { gemini: "Decided by Gemini", bullsai: "Decided by BullsAI (UB)", fallback: "Rule-based safety net" };
const WAVE_GAP = 80;            // ms between windows, top floor first

let view = null;          // 3D scene, or the flat fallback
let building = null;      // current building summary (null = no building yet)
let lastDecision = null;
let hasForecast = false;
let deciding = false;
let waveTimers = [];
let socket = null;
let photo = null;         // step-1 controller

// ---------------------------------------------------------------- helpers
function toast(msg, ms = 3200) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.remove("show"), ms);
}
const score = (r) => Math.round((r || 0) * 100);
const bust = (u) => (u ? `${LO.url(u)}?t=${Date.now()}` : "");

function animateNumber(el, to, fmt, ms = 1200) {
  const start = performance.now();
  const tick = (now) => {
    const p = Math.min((now - start) / ms, 1);
    el.textContent = fmt(to * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function fmtTime(iso) {
  const d = iso ? new Date(iso) : null;
  return d && !isNaN(d) ? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "";
}

// ---------------------------------------------------------------- viewer
function initViewer() {
  try {
    view = createScene($("scene"));
  } catch (e) {
    console.warn("3D not available, showing the photo", e);  // no WebGL: the real photo with its lights
    view = createPhotoView($("scene"));
  }
}

function sameShape(a, b) {
  return a && b && a.building === b.building && a.floors === b.floors && a.cols === b.cols;
}

function setChrome(hasBuilding) {
  $("emptyState").hidden = hasBuilding;
  $("buildingName").hidden = !hasBuilding;
  $("legendLight").hidden = !hasBuilding;
}

function applyBuilding(b, opts = {}) {
  clearWave();
  if (sameShape(building, b) && !opts.rise) view.setWindows(b.windows);
  else view.setBuilding({ ...b, photos: photosOf(b) }, opts);
  view.setBirdMode(lastDecision ? "safe" : "attracted");
  building = b;
  setChrome(true);
  const chip = $("buildingName");
  chip.innerHTML = "";
  chip.append(b.building);
  const place = b.location && b.location.place;
  if (place) {
    const where = document.createElement("span");
    where.className = "where";
    where.textContent = ` · ${place}`;
    chip.append(where);
  }
  setRiskNow(b.risk);
  showPhoto();
}

const SIDE_NAMES = { front: "Front", right: "Right side", back: "Back", left: "Left side" };

// Photo of each side: {front: {photo, image_width, image_height, lights}, right: ...}
function photosOf(b) {
  const faces = b.faces && Object.keys(b.faces).length ? b.faces
    : (b.photo_url ? { front: { photo_url: b.photo_url, image_width: b.image_width, image_height: b.image_height, lights: b.lights } } : {});
  const out = {};
  for (const [face, f] of Object.entries(faces)) out[face] = { ...f, photo: bust(f.photo_url) };
  return out;
}

function clearWave() {
  waveTimers.forEach(clearTimeout);
  waveTimers = [];
}

function playWave(actions, finalWindows) {
  clearWave();
  actions.forEach((a, i) => waveTimers.push(setTimeout(() => view.setWindow(a.id, a.state), i * WAVE_GAP)));
  if (finalWindows) waveTimers.push(setTimeout(() => view.setWindows(finalWindows), actions.length * WAVE_GAP + 300));
  return actions.length * WAVE_GAP;
}

// ---------------------------------------------------------------- steps
function goTo(n) {
  if (n >= 2 && !building) { toast("Start with a photo of the building."); n = 1; }
  if (n >= 3 && !hasForecast) { toast("Add the building's address first."); n = 2; }
  if (n === 4 && !lastDecision) n = 3;
  document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("active", +p.dataset.step === n));
  document.querySelectorAll(".step").forEach((s) => {
    const k = +s.dataset.go;
    s.classList.toggle("active", k === n);
    s.classList.toggle("done", k < n);
  });
  document.querySelectorAll(".step-line").forEach((line, i) => line.classList.toggle("filled", i + 1 < n));
}

// No building yet: empty plot in 3D and the upload form.
function startEmpty() {
  clearWave();
  building = null;
  lastDecision = null;
  view.setEmpty();
  setChrome(false);
  $("photoSection").hidden = true;
  askForLocation();
  photo.reset();
  goTo(1);
}

// ---------------------------------------------------------------- step 1 result
async function photoAnalyzed(b) {
  lastDecision = null;
  building = null;
  applyBuilding(b, { rise: true });
  if (b.conditions) showConditions(b.conditions);
  else askForLocation();
}

// ---------------------------------------------------------------- step 2: tonight's forecast
function showConditions(c) {
  hasForecast = true;
  $("condSummary").textContent = c.summary || "Tonight's forecast";
  $("whereForm").hidden = true;
  $("whereLine").hidden = false;
  $("wherePlace").textContent = c.location || "";
  $("whereChange").hidden = LO.fake;
  $("condTiles").hidden = false;
  $("nextBtn").disabled = false;

  // Where the forecast came from, linked to the source's own page.
  const src = $("sourceLine");
  src.innerHTML = "";
  if (c.source) {
    src.append("Forecast: ");
    if (c.source_url) {
      const a = document.createElement("a");
      a.href = c.source_url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = `${c.source} ↗`;
      src.append(a);
    } else {
      src.append(c.source);
    }
    const t = fmtTime(c.updated);
    if (t) src.append(` · updated ${t}`);
  }
  src.hidden = !c.source;

  showMigrationWhy(c);
  const mig = c.migration_level || "medium";
  const badge = $("migBadge");
  badge.textContent = mig.toUpperCase();
  badge.className = `badge ${mig}`;
  const sd = score(c.sky_danger);
  $("skyDanger").textContent = `${sd}%`;
  const bar = $("skyBar");
  bar.style.width = `${sd}%`;
  bar.className = sd >= 65 ? "bad" : sd >= 35 ? "" : "good";
}

// The factors behind tonight's migration level, its source, and live eBird sightings.
function showMigrationWhy(c) {
  const factors = c.migration_factors || [];
  $("whyBox").hidden = !factors.length;
  $("whyLevel").textContent = c.migration_level || "";
  const chips = $("whyChips");
  chips.innerHTML = "";
  for (const f of factors) {
    const el = document.createElement("span");
    el.className = `chip-why ${f.effect}`;
    const arrow = document.createElement("i");
    arrow.textContent = f.effect === "up" ? "↑" : f.effect === "down" ? "↓" : "·";
    el.append(arrow, f.label);
    el.title = f.effect === "up" ? "More birds flying" : f.effect === "down" ? "Fewer birds flying" : "Little effect";
    chips.appendChild(el);
  }
  const src = $("migSourceLine");
  src.innerHTML = "";
  if (c.migration_source) {
    src.append(`Estimate: ${c.migration_source}`);
    if (c.birdcast_url) {
      const a = document.createElement("a");
      a.href = c.birdcast_url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = "Compare with BirdCast radar ↗";
      src.append(" · ", a);
    }
  }
  const e = c.ebird;
  const line = $("ebirdLine");
  line.hidden = !e;
  if (e) {
    line.innerHTML = '<svg class="ic"><use href="#i-bird"/></svg>';
    const text = document.createElement("span");
    const examples = e.examples && e.examples.length ? ` (e.g. ${e.examples.slice(0, 3).join(", ")})` : "";
    text.append(`${e.migrant_species} night-migrating species reported within ${e.radius_km} km in the last ${e.days} days${examples}. `);
    const a = document.createElement("a");
    a.href = e.url;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = `${e.source} ↗`;
    text.append(a);
    line.appendChild(text);
  }
}

function askForLocation(prefill = "") {
  hasForecast = false;
  $("condSummary").textContent = "Where is this building?";
  $("whereForm").hidden = false;
  $("whereLine").hidden = true;
  $("sourceLine").hidden = true;
  $("condTiles").hidden = true;
  $("whyBox").hidden = true;
  $("ebirdLine").hidden = true;
  $("nextBtn").disabled = true;
  $("whereError").hidden = true;
  $("whereInput").value = prefill;
}

async function submitLocation(ev) {
  ev.preventDefault();
  const address = $("whereInput").value.trim();
  if (!address) { $("whereInput").focus(); return; }
  const btn = $("whereBtn");
  btn.disabled = true;
  btn.textContent = "Finding it…";
  $("whereError").hidden = true;
  try {
    const r = await fetch(LO.url("/api/location"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address, building: building && building.building }),
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`);
    applyBuilding({ ...building, location: body.location, risk: body.risk });
    showConditions(body.conditions);
  } catch (e) {
    $("whereError").textContent = e.message;
    $("whereError").hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = "Get tonight's forecast";
  }
}

// Forecast for the current building, or the address prompt if it has none yet.
async function loadForecast(b) {
  if (!LO.fake && !(b && b.location)) { askForLocation(); return; }
  try { showConditions(await LO.api().conditions()); }
  catch (e) { askForLocation(b && b.location ? b.location.address : ""); toast(`Couldn't load the forecast: ${e.message}`); }
}

function setRiskNow(r) {
  if (typeof r !== "number") {
    $("riskNow").textContent = "–";
    $("riskNowBar").style.width = "0";
    return;
  }
  const s = score(r);
  $("riskNow").textContent = `${s} / 100`;
  const bar = $("riskNowBar");
  bar.style.width = `${Math.min(100, s / 0.6)}%`;
  bar.className = s >= 30 ? "bad" : s >= 12 ? "" : "good";
}

// ---------------------------------------------------------------- step 3: decide
async function decide() {
  if (deciding) return;
  if (!hasForecast) { goTo(2); return; }
  deciding = true;
  const btn = $("decideBtn");
  btn.classList.add("busy");
  btn.disabled = true;
  view.thinking(true);
  try {
    const d = await LO.api().decide(building.building);
    lastDecision = d;
    view.thinking(false);
    const waveMs = playWave(d.actions || [], d.windows);
    // Birds stay trapped while the lights click off, then fly free.
    waveTimers.push(setTimeout(() => view.setBirdMode("safe"), waveMs + 600));
    showDecision(d);
    showPhoto();
    goTo(4);
    speak(d.reason);
  } catch (e) {
    view.thinking(false);
    view.setBirdMode("attracted");
    toast(`The AI could not decide: ${e.message}`);
  } finally {
    deciding = false;
    btn.classList.remove("busy");
    btn.disabled = false;
  }
}

// ---------------------------------------------------------------- step 4: impact
function link(text, url) {
  const a = document.createElement("a");
  a.href = url;
  a.target = "_blank";
  a.rel = "noopener";
  a.textContent = `${text} ↗`;
  return a;
}

function showDecision(d) {
  const est = d.estimate || {};
  const sign = est.at_least ? "≥" : "−";  // "at least" when more than half the lit area went dark
  animateNumber($("riskDrop"), Math.round((est.reduction || 0) * 100), (v) => `${sign}${Math.round(v)}%`);
  animateNumber($("areaOff"), Math.round((est.lit_area_off || 0) * 100), (v) => `${Math.round(v)}%`);
  animateNumber($("kwh"), d.energy_saved_kwh || 0, (v) => `${v.toFixed(1)} kWh`);
  animateNumber($("usd"), d.money_saved_usd || 0, (v) => `$${v.toFixed(2)}`);

  // Tonight's rule and where it comes from.
  const rule = d.rule || {};
  const line = $("ruleLine");
  line.innerHTML = "";
  if (rule.text) {
    const b = document.createElement("b");
    b.textContent = "Tonight's rule: ";
    line.append(b, rule.text, " ");
    if (rule.source) line.append(link(rule.source.name, rule.source.url));
  }
  line.hidden = !rule.text;

  // How the collision estimate is made.
  const es = $("estimateSource");
  es.innerHTML = "";
  if (est.source) {
    es.append(`Estimate: halving a building's lit window area cut bird collisions ${est.halving_factor}× in ${est.season} `
      + "(21 years of data at one Chicago building). ", link(est.source.name, est.source.url));
  }
  es.hidden = !est.source;

  $("reason").textContent = d.reason || "";
  showSwitchList(d);
  const src = $("source");
  src.textContent = AI_NAMES[d.source] || d.source || "";
  src.className = `source ${d.source === "fallback" ? "fallback" : ""}`;
}

// Floor and window number for every changed window, so staff can reach the right room or flat.
// Grouped by side and floor, top floor first; window numbers count from the left.
function switchListLines(d) {
  const all = (building && building.windows) || d.windows || [];
  const byId = new Map(all.map((w) => [w.id, w]));
  // Window number = position from the left on its floor and side (unique, unlike detected columns).
  const number = new Map();
  const rows = new Map();
  for (const w of all) {
    const k = `${w.face || "front"}|${w.floor}`;
    if (!rows.has(k)) rows.set(k, []);
    rows.get(k).push(w);
  }
  for (const row of rows.values()) {
    row.sort((a, b) => a.x - b.x || a.col - b.col).forEach((w, i) => number.set(w.id, i + 1));
  }
  const groups = new Map();
  for (const a of d.actions || []) {
    const w = byId.get(a.id);
    if (!w) continue;
    const face = w.face || "front";
    const key = `${face}|${w.floor}|${a.state}`;
    if (!groups.has(key)) groups.set(key, { face, floor: w.floor, state: a.state, cols: [] });
    groups.get(key).cols.push(number.get(w.id));
  }
  const faces = ["front", "right", "back", "left"];
  const multi = new Set([...groups.values()].map((g) => g.face)).size > 1;
  return [...groups.values()]
    .sort((a, b) => faces.indexOf(a.face) - faces.indexOf(b.face) || b.floor - a.floor
      || (a.state === "off" ? -1 : 1))
    .map((g) => {
      const cols = g.cols.sort((x, y) => x - y);
      const side = multi ? `${SIDE_NAMES[g.face]}, ` : "";
      const verb = g.state === "off" ? "off" : "dim";
      return { text: `${side}Floor ${g.floor}: window${cols.length > 1 ? "s" : ""} ${cols.join(", ")}`, verb };
    });
}

function showSwitchList(d) {
  const lines = switchListLines(d);
  const box = $("switchList");
  box.hidden = !lines.length;
  const ul = $("switchRows");
  ul.innerHTML = "";
  for (const l of lines) {
    const li = document.createElement("li");
    const tag = document.createElement("span");
    tag.className = `switch-tag ${l.verb}`;
    tag.textContent = l.verb === "off" ? "Off" : "Dim";
    li.append(tag, l.text);
    ul.appendChild(li);
  }
  const n = (d.actions || []).length;
  $("switchCount").textContent = n ? `(${n})` : "";
}

async function copySwitchList() {
  if (!lastDecision) return;
  const name = (building && building.building) || "the building";
  const text = [`Lights Out tonight at ${name}. Please switch these lights:`,
    ...switchListLines(lastDecision).map((l) => `- ${l.verb === "off" ? "Off" : "Dim"}: ${l.text}`)].join("\n");
  try {
    await navigator.clipboard.writeText(text);
    toast("List copied");
  } catch (e) { toast("Could not copy the list"); }
}

async function speak(text) {
  try { await LO.speak(text); } catch (e) { /* voice is a bonus */ }
}

async function runAgain() {
  clearWave();
  try {
    const b = await LO.api().reset(building && building.building);
    lastDecision = null;
    applyBuilding(b);
    view.setBirdMode("attracted");
    goTo(3);
  } catch (e) { toast(`Reset failed: ${e.message}`); }
}

// ---------------------------------------------------------------- photo compare (below the fold)
function showPhoto() {
  const sec = $("photoSection");
  if (!building || !building.photo_url) { sec.hidden = true; return; }
  sec.hidden = false;
  const box = $("compare");
  box.innerHTML = "";
  const photos = photosOf(building);
  const multi = Object.keys(photos).length > 1;
  for (const face of ["front", "right", "back", "left"]) {
    const f = photos[face];
    if (!f) continue;
    const block = document.createElement("div");
    block.className = "face-block";
    if (multi) {
      const title = document.createElement("h3");
      title.className = "face-title";
      title.textContent = SIDE_NAMES[face];
      block.appendChild(title);
    }
    const inner = document.createElement("div");
    block.appendChild(inner);
    box.appendChild(block);
    const ws = (building.windows || []).filter((w) => (w.face || "front") === face);
    const ids = new Set(ws.map((w) => w.id));
    renderCompare(inner, {
      photo: f.photo, width: f.image_width, height: f.image_height, windows: ws,
      actions: lastDecision ? (lastDecision.actions || []).filter((a) => ids.has(a.id)) : null,
      simulated: f.lights === "simulated",
      outlines: $("debugToggle").checked,
      animate: !!lastDecision,
    });
  }
}

// ---------------------------------------------------------------- top bar
function setStatus(kind, text) {
  $("status").className = `status ${kind}`;
  $("statusText").textContent = text;
}

// ---------------------------------------------------------------- loading + live updates
// Every visit starts fresh: no earlier buildings or results are shown.
async function loadStart() {
  await LO.api().conditions().catch((e) => { if (e instanceof TypeError) throw e; });  // backend reachable?
  startEmpty();
}

const isMine = (msg) => building && msg.building === building.building;

function connectLive() {
  socket = LO.connectSocket({
    status: (ok) => {
      if (ok && LO.fake) { setFake(false); return; }  // server is back: leave the offline data
      if (!LO.fake) setStatus(ok ? "live" : "off", ok ? "Live" : "Offline · retrying");
    },
    building: (msg) => { if (!LO.fake && !deciding && isMine(msg)) applyBuilding(msg); },
    command: (msg) => { if (!LO.fake && building) view.setWindow(msg.id, msg.state); },
    conditions: (msg) => { if (!LO.fake && building && building.location && msg.location) showConditions(msg); },
    decision: (msg) => {
      // A decision started somewhere else (classic page, API docs) for this building.
      if (LO.fake || deciding || !isMine(msg)) return;
      lastDecision = msg;
      showDecision(msg);
      showPhoto();
      goTo(4);
      setTimeout(() => view.setBirdMode("safe"), ((msg.actions || []).length * WAVE_GAP) + 600);
    },
  });
}

async function setFake(on) {
  LO.fake = on;
  lastDecision = null;
  try {
    if (on) {
      setStatus("fake", "Offline demo");
      const b = await LO.api().windows();
      building = null;
      applyBuilding(b, { rise: true });
      photo.showResult(b);
      showConditions(await LO.api().conditions());
      goTo(2);
    } else {
      setStatus(socket && socket.isOpen() ? "live" : "off", socket && socket.isOpen() ? "Live" : "Connecting…");
      await loadStart();
    }
  } catch (e) { toast(`Could not load: ${e.message}`); }
}

// ---------------------------------------------------------------- wire up
function wire() {
  document.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => goTo(+b.dataset.go)));
  $("decideBtn").addEventListener("click", decide);
  $("startOver").addEventListener("click", runAgain);
  $("replayBtn").addEventListener("click", () => lastDecision && speak(lastDecision.reason));
  $("copyList").addEventListener("click", copySwitchList);
  $("debugToggle").addEventListener("change", showPhoto);
  $("whereForm").addEventListener("submit", submitLocation);
  $("whereChange").addEventListener("click", () => askForLocation(building && building.location ? building.location.address : ""));
  $("newBtn").addEventListener("click", () => { if (LO.fake) setFake(false); else startEmpty(); });
  $("anotherPhoto").addEventListener("click", startEmpty);
  $("emptyUpload").addEventListener("click", () => { goTo(1); photo.pick(); });
}

async function main() {
  initViewer();
  photo = initPhotoStep({ toast, onAnalyzed: photoAnalyzed });
  wire();
  goTo(1);
  connectLive();
  try {
    await loadStart();
  } catch (e) {
    console.warn("Backend not reachable, switching to offline demo data", e);
    await setFake(true);
    toast("Backend not reachable: showing offline demo data");
  }
}

main();
