/* Lights Out AI: the 4-step page.
   1 Photo -> 2 Location (tonight's forecast) -> 3 AI decides -> 4 Impact.
   Talks to the backend through Sakshi's window.LO (js/api.js), draws with scene3d.js. */
import { createScene } from "./scene3d.js";
import { initPhotoStep } from "./photostep.js";

const LO = window.LO;
const $ = (id) => document.getElementById(id);
const AI_NAMES = { gemini: "Decided by Gemini", bullsai: "Decided by BullsAI (UB)", fallback: "Rule-based safety net" };
const WAVE_GAP = 80;            // ms between windows, top floor first
const SAMPLE = "Demo Hall";     // generated sample building, only on request
const KEEP = "lightsout_building";

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
const remember = (name) => { try { name ? localStorage.setItem(KEEP, name) : localStorage.removeItem(KEEP); } catch (e) { /* storage blocked */ } };
const remembered = () => { try { return localStorage.getItem(KEEP); } catch (e) { return null; } };

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
function flatFallback(container) {
  const grid = document.createElement("div");
  grid.className = "flat";
  container.appendChild(grid);
  const cells = new Map();
  return {
    setBuilding(b) {
      grid.hidden = false;
      grid.innerHTML = "";
      cells.clear();
      grid.style.gridTemplateColumns = `repeat(${b.cols}, 1fr)`;
      grid.style.gridTemplateRows = `repeat(${b.floors}, 1fr)`;
      const byCell = new Map(b.windows.map((w) => [`${w.floor}:${w.col}`, w]));
      for (let f = b.floors; f >= 1; f--) {
        for (let c = 1; c <= b.cols; c++) {
          const i = document.createElement("i");
          const w = byCell.get(`${f}:${c}`);
          if (w) { i.className = w.state; cells.set(w.id, i); }
          grid.appendChild(i);
        }
      }
    },
    setEmpty() { grid.hidden = true; },
    setWindow(id, state) { const i = cells.get(id); if (i) i.className = state; },
    setWindows(ws) { ws.forEach((w) => this.setWindow(w.id, w.state)); },
    setRiskView() {},
    setBirdMode() {},
    thinking() {},
  };
}

function initViewer() {
  try {
    view = createScene($("scene"));
  } catch (e) {
    console.warn("3D not available, using the flat building", e);
    view = flatFallback($("scene"));
  }
}

function sameShape(a, b) {
  return a && b && a.building === b.building && a.floors === b.floors && a.cols === b.cols;
}

function setChrome(hasBuilding) {
  $("emptyState").hidden = hasBuilding;
  $("buildingName").hidden = !hasBuilding;
  $("riskSwitch").hidden = !hasBuilding || view.setRiskView.length === 0;
  $("legendLight").hidden = !hasBuilding || $("riskToggle").checked;
  $("legendRisk").classList.toggle("hidden", !hasBuilding || !$("riskToggle").checked);
}

function applyBuilding(b, opts = {}) {
  clearWave();
  if (sameShape(building, b) && !opts.rise) view.setWindows(b.windows);
  else view.setBuilding(b, opts);
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
  remember(null);
  LO.api().buildings().then((l) => fillBuildings(l, null)).catch(() => {});
  goTo(1);
}

async function openBuilding(name, { rise = true } = {}) {
  const b = await LO.api().select(name);
  lastDecision = null;
  building = null;
  applyBuilding(b, { rise });
  photo.showResult(b);
  remember(b.building);
  fillBuildings(await LO.api().buildings().catch(() => null), b.building);
  await loadForecast(b);
  goTo(2);
}

// ---------------------------------------------------------------- step 1 result
async function photoAnalyzed(b) {
  lastDecision = null;
  building = null;
  applyBuilding(b, { rise: true });
  remember(b.building);
  fillBuildings(await LO.api().buildings().catch(() => null), b.building);
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

function askForLocation(prefill = "") {
  hasForecast = false;
  $("condSummary").textContent = "Where is this building?";
  $("whereForm").hidden = false;
  $("whereLine").hidden = true;
  $("sourceLine").hidden = true;
  $("condTiles").hidden = true;
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
    const d = await LO.api().decide();
    lastDecision = d;
    view.thinking(false);
    const waveMs = playWave(d.actions || [], d.windows);
    // Birds stay trapped while the lights click off, then fly free.
    waveTimers.push(setTimeout(() => view.setBirdMode("safe"), waveMs + 600));
    showDecision(d);
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
function showDecision(d) {
  const before = score(d.risk_before), after = score(d.risk_after);
  const drop = before > 0 ? Math.round((1 - after / before) * 100) : 0;
  animateNumber($("riskDrop"), drop, (v) => `−${Math.round(v)}%`);
  animateNumber($("riskBefore"), before, (v) => Math.round(v));
  animateNumber($("riskAfter"), after, (v) => Math.round(v));
  const scale = Math.max(before, 1);
  $("barBefore").style.width = "0";
  $("barAfter").style.width = "0";
  requestAnimationFrame(() => {
    $("barBefore").style.width = `${(before / scale) * 100}%`;
    $("barAfter").style.width = `${(after / scale) * 100}%`;
  });
  const acts = d.actions || [];
  const offs = acts.filter((a) => a.state === "off").length;
  $("countOff").textContent = `${offs} / ${acts.length - offs}`;
  animateNumber($("kwh"), d.energy_saved_kwh || 0, (v) => `${v.toFixed(1)} kWh`);
  animateNumber($("usd"), d.money_saved_usd || 0, (v) => `$${v.toFixed(2)}`);
  $("reason").textContent = d.reason || "";
  const src = $("source");
  src.textContent = AI_NAMES[d.source] || d.source || "";
  src.className = `source ${d.source === "fallback" ? "fallback" : ""}`;
  if (d.after_url) { $("imgAfter").src = bust(d.after_url); $("afterTag").textContent = "After the AI acts"; }
}

async function speak(text) {
  try { await LO.speak(text); } catch (e) { /* voice is a bonus */ }
}

async function runAgain() {
  clearWave();
  try {
    const b = await LO.api().reset();
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
  const simulated = building.lights === "simulated";
  $("compare").classList.toggle("single", simulated);
  $("debugToggle").closest("label").classList.toggle("hidden", simulated);
  if (simulated) {
    $("imgBefore").src = bust(building.debug_url || building.photo_url);
    $("beforeTag").textContent = "Floors and windows found · tonight's lights simulated (day photo)";
    return;
  }
  $("beforeTag").textContent = "Before";
  const before = $("debugToggle").checked && building.debug_url ? building.debug_url : building.photo_url;
  $("imgBefore").src = bust(before);
  if (building.after_url) { $("imgAfter").src = bust(building.after_url); $("afterTag").textContent = "After the AI acts"; }
  else { $("imgAfter").src = bust(building.photo_url); $("afterTag").textContent = "After: run step 3"; }
}

function setSlider(pct) {
  $("afterClip").style.clipPath = `inset(0 0 0 ${pct}%)`;
  $("handle").style.left = `${pct}%`;
}

// ---------------------------------------------------------------- top bar
function setStatus(kind, text) {
  $("status").className = `status ${kind}`;
  $("statusText").textContent = text;
}

function fillBuildings(list, current) {
  const sel = $("buildingSelect");
  sel.innerHTML = "";
  const names = (list && list.buildings ? list.buildings.map((b) => b.building) : []).filter(Boolean);
  if (!current) {
    const ph = document.createElement("option");
    ph.textContent = "Switch building…";
    ph.value = "";
    ph.disabled = ph.selected = true;
    sel.appendChild(ph);
  }
  for (const name of names) {
    const o = document.createElement("option");
    o.value = o.textContent = name;
    o.selected = name === current;
    sel.appendChild(o);
  }
  sel.closest("label").classList.toggle("hidden", names.length < (current ? 2 : 1));
}

// ---------------------------------------------------------------- loading + live updates
async function loadStart() {
  const list = await LO.api().buildings();
  fillBuildings(list, null);
  const saved = remembered();
  if (saved && list.buildings.some((b) => b.building === saved)) await openBuilding(saved, { rise: false });
  else startEmpty();
}

const isMine = (msg) => building && msg.building === building.building;

function connectLive() {
  socket = LO.connectSocket({
    status: (ok) => { if (!LO.fake) setStatus(ok ? "live" : "off", ok ? "Live" : "Offline · retrying"); },
    building: (msg) => { if (!LO.fake && !deciding && isMine(msg)) applyBuilding(msg); },
    command: (msg) => { if (!LO.fake && building) view.setWindow(msg.id, msg.state); },
    conditions: (msg) => { if (!LO.fake && building && building.location && msg.location) showConditions(msg); },
    decision: (msg) => {
      // A decision started somewhere else (classic page, API docs) for this building.
      if (LO.fake || deciding || !isMine(msg)) return;
      lastDecision = msg;
      showDecision(msg);
      goTo(4);
      setTimeout(() => view.setBirdMode("safe"), ((msg.actions || []).length * WAVE_GAP) + 600);
    },
  });
}

async function setFake(on) {
  LO.fake = on;
  $("fakeBtn").textContent = `Offline demo data: ${on ? "on" : "off"}`;
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
  $("riskToggle").addEventListener("change", (e) => {
    view.setRiskView(e.target.checked);
    $("legendLight").hidden = e.target.checked;
    $("legendRisk").classList.toggle("hidden", !e.target.checked);
  });
  $("debugToggle").addEventListener("change", showPhoto);
  $("whereForm").addEventListener("submit", submitLocation);
  $("whereChange").addEventListener("click", () => askForLocation(building && building.location ? building.location.address : ""));
  $("slider").addEventListener("input", (e) => setSlider(e.target.value));
  $("newBtn").addEventListener("click", () => { if (LO.fake) setFake(false); else startEmpty(); });
  $("anotherPhoto").addEventListener("click", startEmpty);
  $("emptyUpload").addEventListener("click", () => { goTo(1); photo.pick(); });
  const sample = async () => {
    $("sampleMenuBtn").closest("details").open = false;
    try { await openBuilding(SAMPLE); toast("Sample building loaded. Add its address to get tonight's forecast."); }
    catch (e) { toast("The sample building isn't available on this server."); }
  };
  $("sampleBtn").addEventListener("click", sample);
  $("sampleMenuBtn").addEventListener("click", sample);
  $("buildingSelect").addEventListener("change", (e) => openBuilding(e.target.value).catch((err) => toast(`Could not switch building: ${err.message}`)));
  $("fakeBtn").addEventListener("click", () => { $("fakeBtn").closest("details").open = false; setFake(!LO.fake); });
  $("docsLink").href = LO.url("/docs");
  setSlider(50);
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
