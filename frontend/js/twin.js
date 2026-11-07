/* Lights Out AI: the digital twin building.
   Draws the window grid (floors x columns) from the backend's window list and
   switches windows on / dim / off with a short fade. */
(function () {
  "use strict";

  function riskClass(r) {
    if (r >= 0.45) return "r-high";
    if (r >= 0.2) return "r-mid";
    return "r-low";
  }

  class Twin {
    constructor(el) {
      this.el = el;
      this.el.classList.add("twin");
      this.cells = new Map(); // window id -> element
      this.windows = new Map(); // window id -> window data
      this.timers = [];
      this._stars();
      this.roof = document.createElement("div");
      this.roof.className = "roof";
      this.tower = document.createElement("div");
      this.tower.className = "tower";
      this.ground = document.createElement("div");
      this.ground.className = "ground";
      this.el.append(this.roof, this.tower, this.ground);
    }

    _stars() {
      const s = document.createElement("div");
      s.className = "stars";
      for (let i = 0; i < 60; i++) {
        const d = document.createElement("i");
        d.className = "star";
        d.style.left = Math.random() * 100 + "%";
        d.style.top = Math.random() * 55 + "%";
        d.style.opacity = (0.2 + Math.random() * 0.6).toFixed(2);
        s.appendChild(d);
      }
      this.el.appendChild(s);
    }

    /** Draw a whole building: {floors, cols, windows:[...]} */
    draw(building) {
      this.stopWave();
      this.cells.clear();
      this.windows.clear();
      const ws = building.windows || [];
      const floors = building.floors || Math.max(1, ...ws.map((w) => w.floor));
      const cols = building.cols || Math.max(1, ...ws.map((w) => w.col));
      const byCell = new Map(ws.map((w) => [`${w.floor}-${w.col}`, w]));

      this.tower.innerHTML = "";
      this.tower.style.gridTemplateColumns = `22px repeat(${cols}, 1fr)`;
      this.el.style.setProperty("--ratio", (cols / floors).toFixed(3));
      for (let f = floors; f >= 1; f--) {
        const label = document.createElement("div");
        label.className = "floorlabel";
        label.textContent = f;
        this.tower.appendChild(label);
        for (let c = 1; c <= cols; c++) {
          const cell = document.createElement("div");
          const w = byCell.get(`${f}-${c}`);
          if (w) {
            cell.dataset.id = w.id;
            this.cells.set(w.id, cell);
            this.windows.set(w.id, Object.assign({}, w));
            this._paint(w.id);
          } else {
            cell.className = "win empty"; // no lit window detected here
            cell.title = `Floor ${f}, column ${c}: dark in the photo`;
          }
          this.tower.appendChild(cell);
        }
      }
    }

    _paint(id) {
      const cell = this.cells.get(id);
      const w = this.windows.get(id);
      if (!cell || !w) return;
      const cool = /white|blue|cool/i.test(w.color || "");
      cell.className = `win ${w.state}${cool ? " cool" : ""} ${riskClass(w.risk || 0)}${w.floor === 1 ? " essential" : ""}`;
      cell.style.opacity = w.state === "on" ? (0.55 + 0.45 * (w.brightness ?? 1)).toFixed(2) : "";
      cell.title = `Window ${w.id} · floor ${w.floor}, col ${w.col} · ${w.state} · risk ${Math.round((w.risk || 0) * 100)}%` +
                   (w.floor === 1 ? " · lobby, always on" : "");
    }

    /** Switch one window: state = "on" | "dim" | "off" */
    setWindow(id, state) {
      const w = this.windows.get(Number(id));
      if (!w) return false;
      w.state = state;
      this._paint(w.id);
      return true;
    }

    /** Update risk numbers (for the risk colors) without changing on/off states */
    setRisks(windows) {
      (windows || []).forEach((n) => {
        const w = this.windows.get(n.id);
        if (w) { w.risk = n.risk; this._paint(n.id); }
      });
    }

    /** Apply a list of {id, state} commands one by one (used when no WebSocket is driving us) */
    wave(actions, gap = 80) {
      this.stopWave();
      actions.forEach((a, i) => {
        this.timers.push(setTimeout(() => this.setWindow(a.id, a.state), i * gap));
      });
    }

    stopWave() { this.timers.forEach(clearTimeout); this.timers = []; }

    showRisk(on) { this.el.classList.toggle("show-risk", !!on); }
    setFog(on) { this.el.classList.toggle("fog", !!on); }

    counts() {
      const c = { on: 0, dim: 0, off: 0 };
      this.windows.forEach((w) => { c[w.state] = (c[w.state] || 0) + 1; });
      return c;
    }
  }

  window.Twin = Twin;
})();
