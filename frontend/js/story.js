/* Lights Out AI: the 3-step story page.
   Talks to the backend only through Sakshi's window.LO (js/api.js), draws with scene3d.js. */
import { createScene } from "./scene3d.js";

const LO = window.LO;
const $ = (id) => document.getElementById(id);
const AI_NAMES = { gemini: "Decided by Gemini", bullsai: "Decided by BullsAI (UB)", fallback: "Rule-based safety net" };
const WAVE_GAP = 80; // ms between windows, top floor first

let view = null;          // 3D scene, or the flat fallback
let building = null;      // current building summary from the backend
let lastDecision = null;
let step = 1;
let deciding = false;
let waveTimers = [];
let socket = null;

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
  const from = 0, start = performance.now();
  const tick = (now) => {
    const p = Math.min((now - start) / ms, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = fmt(from + (to - from) * eased);
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// ---------------------------------------------------------------- viewer
function flatFallback(container) {
  const grid = document.createElement("div");
  grid.className = "flat";
  container.appendChild(grid);
  const cells = new Map();
  return {
    setBuilding(b) {
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
    $("riskToggle").closest("label").classList.add("hidden");
  }
}

function sameShape(a, b) {
  return a && b && a.building === b.building && a.floors === b.floors && a.cols === b.cols;
}

function applyBuilding(b) {
  clearWave();
  if (sameShape(building, b)) view.setWindows(b.windows);
  else view.setBuilding(b);
  view.setBirdMode(b.windows.some((w) => w.state === "off") && lastDecision ? "safe" : "attracted");
  building = b;
  $("buildingName").textContent = b.building;
  if (typeof b.risk === "number") setRiskNow(b.risk);
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
  if (n === 3 && !lastDecision) { toast("Run step 2 first: let the AI decide."); n = 2; }
  step = n;
  document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("active", +p.dataset.step === n));
  document.querySelectorAll(".step").forEach((s) => {
    const k = +s.dataset.go;
    s.classList.toggle("active", k === n);
    s.classList.toggle("done", k < n);
  });
}

// ---------------------------------------------------------------- step 1: conditions
function showConditions(c) {
  $("condSummary").textContent = c.summary || "Tonight in Buffalo";
  const mig = c.migration_level || "medium";
  const badge = $("migBadge");
  badge.textContent = mig.toUpperCase();
  badge.className = `badge ${mig}`;
  const sd = score(c.sky_danger);
  $("skyDanger").textContent = `${sd}%`;
  const bar = $("skyBar");
  bar.style.width = `${sd}%`;
  bar.className = sd >= 65 ? "bad" : sd >= 35 ? "" : "good";
  document.querySelectorAll(".segmented button").forEach((b) => b.classList.toggle("active", b.dataset.s === (c.scenario || "live")));
}

function setRiskNow(r) {
  const s = score(r);
  $("riskNow").textContent = `${s} / 100`;
  const bar = $("riskNowBar");
  bar.style.width = `${Math.min(100, s / 0.6)}%`;
  bar.className = s >= 30 ? "bad" : s >= 12 ? "" : "good";
}

async function refreshRisk() {
  try {
    const b = await LO.api().windows();
    if (sameShape(building, b)) { view.setWindows(b.windows); building = b; }
    else applyBuilding(b);
    setRiskNow(b.risk);
  } catch (e) { /* keep the old numbers */ }
}

async function simulate(name) {
  try {
    const c = await LO.api().simulate(name);
    showConditions(c);
    await refreshRisk();
    toast(name === "live" ? "Back to tonight's real weather" : `Simulating a ${name === "clear" ? "clear, calm" : "foggy migration"} night`);
  } catch (e) { toast(`Could not switch scenario: ${e.message}`); }
}

// ---------------------------------------------------------------- step 2: decide
async function decide() {
  if (deciding) return;
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
    goTo(3);
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

// ---------------------------------------------------------------- step 3: impact
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

async function startOver() {
  clearWave();
  try {
    const b = await LO.api().reset();
    lastDecision = null;
    applyBuilding(b);
    view.setBirdMode("attracted");
    await refreshRisk();
    goTo(1);
  } catch (e) { toast(`Reset failed: ${e.message}`); }
}

// ---------------------------------------------------------------- photo compare
function showPhoto() {
  const sec = $("photoSection");
  if (!building || !building.photo_url) { sec.hidden = true; return; }
  sec.hidden = false;
  const before = $("debugToggle").checked && building.debug_url ? building.debug_url : building.photo_url;
  $("imgBefore").src = bust(before);
  if (building.after_url) { $("imgAfter").src = bust(building.after_url); $("afterTag").textContent = "After the AI acts"; }
  else { $("imgAfter").src = bust(building.photo_url); $("afterTag").textContent = "After: run step 2"; }
}

function setSlider(pct) {
  $("afterClip").style.clipPath = `inset(0 0 0 ${pct}%)`;
  $("handle").style.left = `${pct}%`;
}

// ---------------------------------------------------------------- top bar
function setStatus(kind, text) {
  const s = $("status");
  s.className = `status ${kind}`;
  $("statusText").textContent = text;
}

function fillBuildings(list, current) {
  const sel = $("buildingSelect");
  sel.innerHTML = "";
  const names = (list && list.buildings ? list.buildings.map((b) => b.building) : [current]).filter(Boolean);
  for (const name of names) {
    const o = document.createElement("option");
    o.value = o.textContent = name;
    o.selected = name === current;
    sel.appendChild(o);
  }
  sel.closest("label").classList.toggle("hidden", names.length < 2);
}

function tickClock() {
  $("clock").textContent = new Date().toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" });
}

// ---------------------------------------------------------------- loading + live updates
async function loadAll() {
  const api = LO.api();
  const [b, c] = await Promise.all([api.windows(), api.conditions()]);
  building = null; // force a rebuild for a fresh load
  applyBuilding(b);
  showConditions(c);
  fillBuildings(await api.buildings().catch(() => null), b.building);
}

function connectLive() {
  socket = LO.connectSocket({
    status: (ok) => { if (!LO.fake) setStatus(ok ? "live" : "off", ok ? "Live" : "Offline · retrying"); },
    building: (msg) => { if (!LO.fake && !deciding) applyBuilding(msg); },
    command: (msg) => { if (!LO.fake) view.setWindow(msg.id, msg.state); },
    conditions: (msg) => { if (!LO.fake) { showConditions(msg); refreshRisk(); } },
    decision: (msg) => {
      // A decision started somewhere else (classic page, API docs): show it here too.
      if (LO.fake || deciding) return;
      lastDecision = msg;
      showDecision(msg);
      goTo(3);
      setTimeout(() => view.setBirdMode("safe"), ((msg.actions || []).length * WAVE_GAP) + 600);
    },
  });
}

async function setFake(on, quiet) {
  LO.fake = on;
  $("fakeBtn").textContent = `Fake mode: ${on ? "on" : "off"}`;
  if (on) setStatus("fake", "Fake data");
  else setStatus(socket && socket.isOpen() ? "live" : "off", socket && socket.isOpen() ? "Live" : "Connecting…");
  lastDecision = null;
  try { await loadAll(); goTo(1); if (!quiet) toast(on ? "Fake mode: built-in data" : "Back to the live backend"); }
  catch (e) { toast(`Could not load: ${e.message}`); }
}

// ---------------------------------------------------------------- wire up
function wire() {
  document.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => goTo(+b.dataset.go)));
  document.querySelectorAll(".segmented button").forEach((b) => b.addEventListener("click", () => simulate(b.dataset.s)));
  $("decideBtn").addEventListener("click", decide);
  $("startOver").addEventListener("click", startOver);
  $("replayBtn").addEventListener("click", () => lastDecision && speak(lastDecision.reason));
  $("riskToggle").addEventListener("change", (e) => {
    view.setRiskView(e.target.checked);
    $("legendLight").classList.toggle("hidden", e.target.checked);
    $("legendRisk").classList.toggle("hidden", !e.target.checked);
  });
  $("debugToggle").addEventListener("change", showPhoto);
  $("slider").addEventListener("input", (e) => setSlider(e.target.value));
  $("buildingSelect").addEventListener("change", async (e) => {
    try { const b = await LO.api().select(e.target.value); lastDecision = null; applyBuilding(b); await refreshRisk(); goTo(1); }
    catch (err) { toast(`Could not switch building: ${err.message}`); }
  });
  $("fakeBtn").addEventListener("click", () => { $("fakeBtn").closest("details").open = false; setFake(!LO.fake); });
  $("docsLink").href = LO.url("/docs");
  tickClock();
  setInterval(tickClock, 30000);
  setSlider(50);
}

async function main() {
  wire();
  initViewer();
  goTo(1);
  connectLive();
  try {
    await loadAll();
  } catch (e) {
    console.warn("Backend not reachable, switching to fake mode", e);
    await setFake(true, true);
    toast("Backend not reachable: showing built-in demo data");
  }
}

main();
