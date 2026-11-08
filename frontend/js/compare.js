/* Before / after photos side by side, used by the landing demo and the app.
   The "after" photo is drawn in the browser: windows the AI turned off go dark with a green
   outline, dimmed ones get a softer shade with an amber outline. */

const SVG = "http://www.w3.org/2000/svg";

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

function rect(svg, w, cls, delay) {
  const r = document.createElementNS(SVG, "rect");
  const pad = Math.max(2, Math.round(Math.min(w.w, w.h) * 0.06));
  r.setAttribute("x", w.x - pad);
  r.setAttribute("y", w.y - pad);
  r.setAttribute("width", w.w + pad * 2);
  r.setAttribute("height", w.h + pad * 2);
  r.setAttribute("rx", Math.max(2, pad));
  r.setAttribute("class", cls);
  if (delay != null) r.style.animationDelay = `${delay}ms`;
  svg.appendChild(r);
  return r;
}

function panel(label, cls, photo, width, height) {
  const fig = el("figure", `cmp-pane ${cls}`);
  const frame = el("div", "cmp-frame");
  const img = el("img");
  img.src = photo;
  img.alt = label;
  img.decoding = "async";
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("class", "cmp-svg");
  frame.append(img, svg);
  fig.append(el("figcaption", "cmp-tag", label), frame);
  return { fig, frame, svg };
}

/**
 * el:      container to fill
 * photo:   photo URL
 * width, height: photo size in pixels (window boxes use these coordinates)
 * windows: [{id, x, y, w, h, floor, state}] as before the AI acts
 * actions: [{id, state}] the AI's changes, or null if it hasn't decided yet
 * simulated: day photo, so tonight's lights are drawn on top of it
 * outlines: outline every detected window on the "before" photo
 * animate: switch the after-windows off one by one (top floor first)
 */
export function renderCompare(root, { photo, width, height, windows = [], actions = null,
  simulated = false, outlines = false, animate = false, gap = 70 }) {
  root.innerHTML = "";
  root.classList.add("cmp-root");
  if (!photo || !width || !height) return;

  const grid = el("div", "cmp");
  const before = panel("Before", "before", photo, width, height);
  const after = panel("After AI", "after", photo, width, height);
  grid.append(before.fig, after.fig);
  root.appendChild(grid);

  // Before: lights as they are (drawn on a day photo), plus optional outlines.
  for (const w of windows) {
    if (simulated && w.state !== "off") rect(before.svg, w, `glow ${w.state}`);
    if (outlines) rect(before.svg, w, "outline");
  }

  if (!actions) {
    after.fig.classList.add("pending");
    const wait = el("div", "cmp-wait");
    wait.append(el("b", null, "Waiting for the AI"), el("span", null, "Run step 3 to see which lights go out."));
    after.frame.appendChild(wait);
    root.appendChild(el("p", "cmp-summary muted", simulated
      ? "Day photo: floors and windows found, tonight's lights are simulated."
      : "The highlighted result appears here once the AI decides."));
    return;
  }

  const change = new Map(actions.map((a) => [a.id, a.state]));
  const byId = new Map(windows.map((w) => [w.id, w]));
  if (simulated) {
    for (const w of windows) {
      const st = change.get(w.id) || w.state;
      if (st !== "off" && !change.has(w.id)) rect(after.svg, w, `glow ${st}`);
    }
  }
  const order = actions.filter((a) => byId.has(a.id));
  order.forEach((a, i) => {
    rect(after.svg, byId.get(a.id), `mark ${a.state}${animate ? " anim" : ""}`, animate ? i * gap : null);
  });

  const offs = order.filter((a) => a.state === "off").length;
  const dims = order.length - offs;
  const ground = windows.filter((w) => w.floor === 1);
  const groundKept = ground.length > 0 && ground.every((w) => !change.has(w.id));

  const sum = el("div", "cmp-summary");
  const stat = (n, label, cls) => {
    const s = el("span", `cmp-stat ${cls}`);
    s.append(el("i"), el("b", null, String(n)), ` ${label}`);
    return s;
  };
  sum.append(stat(offs, offs === 1 ? "window turned off" : "windows turned off", "off"),
    stat(dims, dims === 1 ? "window dimmed" : "windows dimmed", "dim"));
  if (groundKept) sum.append(el("span", "cmp-stat keep", "Ground floor kept on for safety"));
  root.appendChild(sum);
  if (!order.length) sum.prepend(el("span", "cmp-stat", "The AI left every light on tonight."));
}
