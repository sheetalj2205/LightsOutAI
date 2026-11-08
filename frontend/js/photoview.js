/* Lights Out AI: the main view, the building's real photo in 3D.

   createPhotoView(container) -> {
     setBuilding(b), setEmpty(), setWindow(id, state), setWindows(windows),
     thinking(bool), setBirdMode(), setRiskView()
   }
   b.photos = {front: {photo, image_width, image_height, lights}, right: ...}.

   The photo is split into two layers: the full photo, dimmed, at the back, and the building's facade
   (the area around its detected windows) floating in front. The scene tilts in perspective, swaying
   slowly or following a drag, so the building stands out from its surroundings. The facade layer is
   scaled so both layers line up exactly when seen straight on.
   Window lights sit on the facade layer at their real positions: the ones the AI turns off go dark
   (with a short "click" flash), dimmed ones get a softer shade, both outlined. On a day photo
   tonight's lights are drawn on. One tab per side photo. */

const SVG = "http://www.w3.org/2000/svg";
const SIDES = ["front", "right", "back", "left"];
const NAMES = { front: "Front", right: "Right side", back: "Back", left: "Left side" };
const PERSPECTIVE = 1600, DEPTH = 70;               // px; facade layer floats DEPTH in front
const REST = { x: 4, y: -12 };                      // degrees: resting three-quarter view
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

export function createPhotoView(container) {
  container.innerHTML = `
    <div class="pv" hidden>
      <div class="pv-tabs" hidden></div>
      <div class="pv-stage">
        <div class="pv-frame">
          <div class="pv-back"><img alt="" /></div>
          <div class="pv-front"><div class="pv-facade"><img alt="The building" /><svg></svg><i class="pv-scan"></i></div></div>
        </div>
        <div class="pv-floor"></div>
      </div>
      <span class="pv-hint">Drag to turn</span>
    </div>`;
  const root = container.querySelector(".pv");
  const tabs = root.querySelector(".pv-tabs");
  const stage = root.querySelector(".pv-stage");
  const frame = root.querySelector(".pv-frame");
  const front = root.querySelector(".pv-front");
  const facade = root.querySelector(".pv-facade");
  const imgs = frame.querySelectorAll("img");
  const svg = facade.querySelector("svg");
  stage.style.perspective = `${PERSPECTIVE}px`;
  front.style.transform = `translateZ(${DEPTH}px) scale(${(PERSPECTIVE - DEPTH) / PERSPECTIVE})`;

  let photos = {}, side = "front";
  let windows = [];              // all sides
  const state = new Map();       // id -> on/dim/off now
  const original = new Map();    // id -> state in the photo
  const rects = new Map();       // id -> <rect> on the side shown

  // ---- size: fit the photo inside the stage ----
  function fit() {
    const p = photos[side];
    if (!p) return;
    const k = Math.min(stage.clientWidth * 0.86 / p.image_width, stage.clientHeight * 0.9 / p.image_height);
    frame.style.width = `${Math.floor(p.image_width * k)}px`;
    frame.style.height = `${Math.floor(p.image_height * k)}px`;
  }
  new ResizeObserver(fit).observe(stage);

  // ---- tilt: slow sway, drag to turn, straight on while the AI works ----
  let rot = { ...REST }, drag = null, idleUntil = 0, focus = false;
  function apply() { frame.style.transform = `rotateX(${rot.x}deg) rotateY(${rot.y}deg)`; }
  function tick(t) {
    if (!drag && !root.hidden && !reduceMotion && t > idleUntil) {
      const goal = focus ? { x: 2, y: -4 } : { x: REST.x + Math.sin(t / 2600) * 2, y: REST.y + Math.sin(t / 4200) * 9 };
      rot.x += (goal.x - rot.x) * 0.04;
      rot.y += (goal.y - rot.y) * 0.04;
      apply();
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
  stage.addEventListener("pointerdown", (e) => {
    drag = { x: e.clientX, y: e.clientY, rx: rot.x, ry: rot.y };
    stage.setPointerCapture(e.pointerId);
    root.classList.add("dragging");
  });
  stage.addEventListener("pointermove", (e) => {
    if (!drag) return;
    rot.y = Math.max(-35, Math.min(35, drag.ry + (e.clientX - drag.x) * 0.15));
    rot.x = Math.max(-12, Math.min(16, drag.rx - (e.clientY - drag.y) * 0.1));
    apply();
  });
  const endDrag = () => { if (!drag) return; drag = null; idleUntil = performance.now() + 2500; root.classList.remove("dragging"); };
  stage.addEventListener("pointerup", endDrag);
  stage.addEventListener("pointercancel", endDrag);

  // ---- drawing ----
  function classFor(id) {
    const st = state.get(id) || "on";
    return `pw ${st}${st !== original.get(id) ? " changed" : ""}`;
  }

  // The facade: bounding box of this side's windows, with room for the roof and entrance.
  function facadeClip(p, ws) {
    if (!ws.length) return "none";
    const x0 = Math.min(...ws.map((w) => w.x)), y0 = Math.min(...ws.map((w) => w.y));
    const x1 = Math.max(...ws.map((w) => w.x + w.w)), y1 = Math.max(...ws.map((w) => w.y + w.h));
    const W = p.image_width, H = p.image_height, bw = x1 - x0, bh = y1 - y0;
    const left = Math.max(0, x0 - bw * 0.06), right = Math.min(W, x1 + bw * 0.06);
    const top = Math.max(0, y0 - bh * 0.12), bottom = Math.min(H, y1 + bh * 0.06);
    const pct = (v, of) => `${((v / of) * 100).toFixed(2)}%`;
    return `inset(${pct(top, H)} ${pct(W - right, W)} ${pct(H - bottom, H)} ${pct(left, W)} round 6px)`;
  }

  function draw() {
    const p = photos[side];
    if (!p) return;
    imgs.forEach((i) => { i.src = p.photo; });
    svg.setAttribute("viewBox", `0 0 ${p.image_width} ${p.image_height}`);
    svg.setAttribute("preserveAspectRatio", "none");
    frame.classList.toggle("sim", p.lights === "simulated");
    svg.innerHTML = "";
    rects.clear();
    const ws = windows.filter((w) => (w.face || "front") === side);
    facade.style.clipPath = facadeClip(p, ws);
    for (const w of ws) {
      const r = document.createElementNS(SVG, "rect");
      const pad = Math.max(1, Math.round(Math.min(w.w, w.h) * 0.04));
      r.setAttribute("x", w.x - pad);
      r.setAttribute("y", w.y - pad);
      r.setAttribute("width", w.w + pad * 2);
      r.setAttribute("height", w.h + pad * 2);
      r.setAttribute("rx", 2);
      r.setAttribute("class", classFor(w.id));
      svg.appendChild(r);
      rects.set(w.id, r);
    }
    tabs.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.side === side));
    fit();
  }

  function drawTabs() {
    const list = SIDES.filter((s) => photos[s]);
    tabs.hidden = list.length < 2;
    tabs.innerHTML = "";
    for (const s of list) {
      const b = document.createElement("button");
      b.type = "button";
      b.dataset.side = s;
      b.textContent = NAMES[s];
      b.addEventListener("click", () => { side = s; draw(); });
      tabs.appendChild(b);
    }
  }

  return {
    setBuilding(b, opts = {}) {
      photos = b.photos || {};
      windows = b.windows || [];
      state.clear(); original.clear();
      for (const w of windows) { state.set(w.id, w.state || "on"); original.set(w.id, w.state || "on"); }
      side = photos[side] ? side : "front";
      root.hidden = !photos.front;
      drawTabs();
      draw();
      if (opts.rise) {
        rot = { x: 10, y: -28 };  // swing in from the side
        apply();
        frame.classList.remove("appear"); void frame.offsetWidth; frame.classList.add("appear");
      }
    },
    setEmpty() {
      root.hidden = true;
      photos = {}; windows = [];
      state.clear(); original.clear(); rects.clear();
    },
    setWindow(id, st) {
      if (!state.has(id) || !["on", "dim", "off"].includes(st)) return;
      const was = state.get(id);
      state.set(id, st);
      const r = rects.get(id);  // windows on other sides update when their tab is opened
      if (!r) return;
      r.setAttribute("class", classFor(id));
      if (st === "off" && was !== "off") {
        r.classList.add("flash");
        setTimeout(() => r.classList.remove("flash"), 140);
      }
    },
    setWindows(ws) {
      for (const w of ws) if (state.has(w.id)) state.set(w.id, w.state || "on");
      for (const [id, r] of rects) r.setAttribute("class", classFor(id));
    },
    thinking(on) {
      frame.classList.toggle("scanning", !!on);
      if (on) focus = true;  // face the viewer while the AI scans and the lights go out
    },
    setBirdMode(mode) { if (mode === "safe") focus = false; },  // "safe" = lights-out wave finished
    setRiskView() {},
  };
}
