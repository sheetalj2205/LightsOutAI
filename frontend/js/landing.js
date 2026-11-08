/* Landing page: stars, the hero building whose lights go out, and the Davis Hall example. */
import { renderCompare } from "./compare.js";

const $ = (id) => document.getElementById(id);
const SVG = "http://www.w3.org/2000/svg";

// ---------------------------------------------------------------- stars
function stars() {
  const box = $("stars");
  for (let i = 0; i < 60; i++) {
    const s = document.createElement("i");
    s.style.left = `${Math.random() * 100}%`;
    s.style.top = `${Math.random() * 60}%`;
    s.style.animationDelay = `${Math.random() * 5}s`;
    box.appendChild(s);
  }
}

// ---------------------------------------------------------------- hero building
const FLOORS = 7, COLS = 5;

function heroBuilding() {
  const svg = $("heroBuilding");
  const add = (tag, attrs, parent = svg) => {
    const e = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    parent.appendChild(e);
    return e;
  };
  const defs = add("defs", {});
  const glow = add("filter", { id: "glow", x: "-50%", y: "-50%", width: "200%", height: "200%" }, defs);
  add("feGaussianBlur", { stdDeviation: "3", result: "b" }, glow);
  const merge = add("feMerge", {}, glow);
  add("feMergeNode", { in: "b" }, merge);
  add("feMergeNode", { in: "SourceGraphic" }, merge);
  const facade = add("linearGradient", { id: "facade", x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
  add("stop", { offset: "0", "stop-color": "#2a3163" }, facade);
  add("stop", { offset: "1", "stop-color": "#171c40" }, facade);

  // ground glow, building body, roof
  add("ellipse", { cx: 180, cy: 430, rx: 170, ry: 12, fill: "rgba(255,190,100,.12)" });
  add("rect", { x: 60, y: 40, width: 240, height: 390, rx: 6, fill: "url(#facade)", stroke: "rgba(255,255,255,.08)" });
  add("rect", { x: 50, y: 30, width: 260, height: 16, rx: 4, fill: "#323a72" });
  add("rect", { x: 160, y: 8, width: 40, height: 24, rx: 3, fill: "#262d5c" });

  const wins = [];
  const w = 34, h = 36, gx = 10, gy = 14, left = 80, top = 62;
  for (let f = FLOORS; f >= 1; f--) {
    const row = FLOORS - f;
    for (let c = 0; c < COLS; c++) {
      const r = add("rect", { x: left + c * (w + gx), y: top + row * (h + gy), width: w, height: h, rx: 3, class: "win on" });
      wins.push({ el: r, floor: f });
    }
  }
  add("rect", { x: 160, y: 400, width: 40, height: 30, rx: 2, fill: "#ffcf6e", filter: "url(#glow)" });  // door
  return wins;
}

function lightsLoop(wins) {
  const upper = wins.filter((w) => w.floor > 1);  // top floor first (array is already top-down)
  const cycle = () => {
    wins.forEach((w) => { w.el.classList.add("on"); w.el.classList.remove("off"); });
    setTimeout(() => upper.forEach((w, i) => setTimeout(() => {
      if ((i * 7) % 11 === 3) return;  // a few rooms stay lit, like the AI does
      w.el.classList.remove("on");
      w.el.classList.add("off");
    }, i * 70)), 2200);
  };
  cycle();
  setInterval(cycle, 9000);
}

// ---------------------------------------------------------------- example
let demo = null;

function count(el, to, fmt, ms = 1400) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) { el.textContent = fmt(to); return; }
  const t0 = performance.now();
  const tick = (now) => {
    const p = Math.min((now - t0) / ms, 1);
    el.textContent = fmt(to * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function showDemo(animate) {
  renderCompare($("demoCompare"), {
    photo: demo.photo, width: demo.image_width, height: demo.image_height,
    windows: demo.windows, actions: demo.actions, animate, gap: 55,
  });
  const drop = Math.round(((demo.estimate || {}).reduction || 0) * 100);  // Van Doren et al. 2021 estimate
  const sign = (demo.estimate || {}).at_least ? "≥" : "";
  count($("demoDrop"), drop, (v) => `${sign}${Math.round(v)}%`);
  count($("demoChanged"), demo.actions.length, (v) => Math.round(v));
  count($("demoUsd"), demo.money_saved_usd, (v) => `$${v.toFixed(2)}`);
}

async function loadDemo() {
  try {
    const r = await fetch("demo/davis-hall/demo.json");
    if (!r.ok) throw new Error(r.status);
    demo = await r.json();
  } catch (e) {
    $("demoCompare").innerHTML = '<p class="loading">The example could not be loaded.</p>';
    ["demoDrop", "demoChanged", "demoUsd"].forEach((id) => { $(id).textContent = "–"; });
    return;
  }
  // Play the lights-out animation when the example scrolls into view.
  $("demoCompare").removeAttribute("aria-busy");
  showDemo(false);
  const io = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting)) { showDemo(true); io.disconnect(); }
  }, { threshold: .35 });
  io.observe($("demoCompare"));
}

stars();
lightsLoop(heroBuilding());
loadDemo();
