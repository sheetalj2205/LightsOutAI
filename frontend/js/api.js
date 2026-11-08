/* Lights Out AI: talking to Sheetal's backend (REST + WebSocket), plus a fake mode
   so the pages still work if the backend is down. */
(function () {
  "use strict";

  // ---------- where is the backend? ----------
  // 1. ?api=http://1.2.3.4:8000 in the URL (remembered for next time)
  // 2. opened as a file, or from a local dev server -> same host, port 8000
  // 3. deployed on Vultr (frontend and API on the same server) -> same origin
  function pickBase() {
    const params = new URLSearchParams(location.search);
    let saved = null;
    try { saved = localStorage.getItem("lightsout_api"); } catch (e) { /* storage blocked */ }
    const fromUrl = params.get("api");
    if (fromUrl) {
      try { localStorage.setItem("lightsout_api", fromUrl); } catch (e) { /* ignore */ }
      return fromUrl.replace(/\/$/, "");
    }
    if (saved) return saved.replace(/\/$/, "");
    if (location.protocol === "file:") return "http://localhost:8000";
    const port = location.port;
    if (port && port !== "80" && port !== "443" && port !== "8000") {
      return `${location.protocol}//${location.hostname}:8000`;
    }
    return location.origin;
  }

  const BASE = pickBase();
  const url = (path) => (path && path.startsWith("http") ? path : BASE + path);

  async function request(method, path, body, isForm) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      if (isForm) {
        const fd = new FormData();
        Object.entries(body).forEach(([k, v]) => { if (v !== undefined && v !== null) fd.append(k, v); });
        opts.body = fd;
      } else {
        opts.headers["Content-Type"] = "application/json";
        opts.body = JSON.stringify(body);
      }
    }
    const r = await fetch(url(path), opts);
    if (!r.ok) {
      let detail = `${r.status}`;
      try { detail = (await r.json()).detail || detail; } catch (e) { /* not json */ }
      throw new Error(`${method} ${path} failed: ${detail}`);
    }
    return r.json();
  }

  const real = {
    conditions: () => request("GET", "/api/conditions"),
    windows: () => request("GET", "/api/windows"),
    buildings: () => request("GET", "/api/buildings"),
    lastDecision: () => request("GET", "/api/decision"),
    simulate: (scenario) => request("POST", "/api/simulate", { scenario }),
    decide: (building) => request("POST", "/api/decide", { building }),
    reset: (building) => request("POST", "/api/reset", building ? { building } : {}, true),
    select: (building) => request("POST", "/api/select", { building }, true),
  };

  // ---------- fake mode ----------
  const PRESETS = {
    live: { summary: "Mostly cloudy, NW wind 9 mph (fake data)", sky_cover: 70, fog: false, rain: false,
            wind_dir: "NW", wind_speed_mph: 9, migration_level: "medium", sky_danger: 0.55 },
    clear: { summary: "Clear sky, light south wind. Few birds flying.", sky_cover: 5, fog: false, rain: false,
             wind_dir: "S", wind_speed_mph: 6, migration_level: "low", sky_danger: 0.15 },
    foggy_migration: { summary: "Fog and low clouds, steady NW wind. Heavy migration night.", sky_cover: 95,
                       fog: true, rain: false, wind_dir: "NW", wind_speed_mph: 14,
                       migration_level: "high", sky_danger: 0.9 },
  };
  const MIG = { low: 0.25, medium: 0.6, high: 1.0 };

  function makeFakeBuilding() {
    const floors = 7, cols = 10, windows = [];
    let id = 1, seed = 7;
    const rnd = () => ((seed = (seed * 9301 + 49297) % 233280) / 233280);
    for (let f = 1; f <= floors; f++) {
      for (let c = 1; c <= cols; c++) {
        if (f > 1 && rnd() > 0.72) continue; // unlit in the "photo"
        windows.push({ id: id++, floor: f, col: c, x: 0, y: 0, w: 0, h: 0, state: "on",
                       brightness: +(0.6 + rnd() * 0.4).toFixed(2), color: rnd() > 0.5 ? "white" : "yellow",
                       risk: 0 });
      }
    }
    return { building: "Demo Hall (fake mode)", floors, cols, image_width: 0, image_height: 0,
             photo_url: "", debug_url: "", after_url: "", method: "fake", windows };
  }

  const fakeState = { scenario: "live", building: null, original: null, decision: {} };

  function fakeConditions() {
    return Object.assign({ time: new Date().toISOString().slice(0, 16), location: "Offline demo",
                           migration_estimated: true, scenario: fakeState.scenario,
                           source: "Built-in demo data (offline, not a real forecast)", source_url: "", updated: "" },
                         PRESETS[fakeState.scenario]);
  }
  const stateFactor = { on: 1, dim: 0.35, off: 0 };
  function scoreAll(windows, cond, floors) {
    windows.forEach((w) => {
      const height = 0.5 + 0.5 * (w.floor / floors);
      const r = MIG[cond.migration_level] * (0.3 + 0.7 * cond.sky_danger) * w.brightness * height * stateFactor[w.state];
      w.risk = +Math.min(1, r).toFixed(3);
    });
  }
  const avgRisk = (ws) => (ws.length ? +(ws.reduce((s, w) => s + w.risk, 0) / ws.length).toFixed(3) : 0);

  function ensureFake() {
    if (!fakeState.building) {
      fakeState.building = makeFakeBuilding();
      fakeState.original = JSON.parse(JSON.stringify(fakeState.building.windows));
    }
    scoreAll(fakeState.building.windows, fakeConditions(), fakeState.building.floors);
    return fakeState.building;
  }

  const fake = {
    conditions: async () => fakeConditions(),
    windows: async () => { const b = ensureFake(); return Object.assign({}, b, { risk: avgRisk(b.windows) }); },
    buildings: async () => ({ current: ensureFake().building, buildings: [{ building: ensureFake().building }] }),
    lastDecision: async () => fakeState.decision,
    simulate: async (scenario) => { fakeState.scenario = scenario; ensureFake(); return fakeConditions(); },
    select: async () => ensureFake(),
    reset: async () => {
      const b = ensureFake();
      b.windows = JSON.parse(JSON.stringify(fakeState.original));
      fakeState.decision = {};
      ensureFake();
      return b;
    },
    decide: async () => {
      const b = ensureFake();
      const cond = fakeConditions();
      const before = avgRisk(b.windows);
      const ranked = b.windows.filter((w) => w.floor > 1 && w.state !== "off").sort((a, z) => z.risk - a.risk);
      const share = { low: 0.25, medium: 0.5, high: 0.8 }[cond.migration_level];
      const n = Math.round(ranked.length * share);
      const actions = ranked.slice(0, n).map((w, i) => ({ id: w.id, state: i < n * 0.7 ? "off" : "dim" }));
      actions.forEach((a) => { b.windows.find((w) => w.id === a.id).state = a.state; });
      scoreAll(b.windows, cond, b.floors);
      const after = avgRisk(b.windows);
      const offs = actions.filter((a) => a.state === "off").length;
      const floorsHit = [...new Set(actions.map((a) => b.windows.find((w) => w.id === a.id).floor))].sort((x, y) => x - y);
      const kwh = +(actions.reduce((s, a) => s + (a.state === "off" ? 0.06 : 0.04), 0) * 8).toFixed(2);
      fakeState.decision = {
        building: b.building, actions: actions.sort((x, y) => {
          const fx = b.windows.find((w) => w.id === x.id), fy = b.windows.find((w) => w.id === y.id);
          return fy.floor - fx.floor || fx.col - fy.col;
        }),
        risk_before: before, risk_after: after, source: "fallback", conditions: cond,
        reason: `${cond.migration_level[0].toUpperCase() + cond.migration_level.slice(1)} migration tonight. ` +
                `I turned off ${offs} windows and dimmed ${actions.length - offs} on floors ${floorsHit[0]} to ${floorsHit[floorsHit.length - 1]}. The lobby stays on.`,
        windows: b.windows, energy_saved_kwh: kwh, money_saved_usd: +(kwh * 0.17).toFixed(2),
        photo_url: "", after_url: "",
      };
      return fakeState.decision;
    },
  };

  // ---------- WebSocket ----------
  // handlers: { building(msg), decision(msg), conditions(msg), command(msg) -> applied?, status(bool) }
  function connectSocket(handlers) {
    let ws = null, closedByUs = false, timer = null;
    const wsUrl = BASE.replace(/^http/, "ws") + "/ws";

    function open() {
      try { ws = new WebSocket(wsUrl); } catch (e) { retry(); return; }
      ws.onopen = () => handlers.status && handlers.status(true);
      ws.onmessage = (e) => {
        let msg;
        try { msg = JSON.parse(e.data); } catch (err) { return; }
        if (msg.type === "building") handlers.building && handlers.building(msg);
        else if (msg.type === "decision") handlers.decision && handlers.decision(msg);
        else if (msg.type === "conditions") handlers.conditions && handlers.conditions(msg);
        else if ("id" in msg) {
          if (handlers.command) handlers.command(msg);
          ws.send(JSON.stringify(Object.assign({}, msg, { ok: true })));
        }
      };
      ws.onclose = () => { handlers.status && handlers.status(false); if (!closedByUs) retry(); };
      ws.onerror = () => { /* onclose follows */ };
    }
    function retry() { clearTimeout(timer); timer = setTimeout(open, 2000); }

    open();
    return {
      isOpen: () => !!ws && ws.readyState === WebSocket.OPEN,
      close: () => { closedByUs = true; clearTimeout(timer); if (ws) ws.close(); },
    };
  }

  // ---------- voice alert ----------
  let currentAudio = null;
  async function speak(text) {
    if (!text) return "none";
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    if (!LO.fake) {
      try {
        const r = await fetch(url("/api/alert"), {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }),
        });
        if (r.ok) {
          const blob = await r.blob();
          currentAudio = new Audio(URL.createObjectURL(blob));
          await currentAudio.play();
          return "elevenlabs";
        }
      } catch (e) { /* fall through to the browser voice */ }
    }
    if (window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(text);
      u.rate = 0.95;
      window.speechSynthesis.speak(u);
      return "browser";
    }
    return "none";
  }

  const LO = {
    BASE, url,
    fake: false,
    api: () => (LO.fake ? fake : real),
    connectSocket, speak,
  };
  window.LO = LO;
})();
