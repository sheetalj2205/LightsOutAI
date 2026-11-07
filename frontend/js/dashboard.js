/* Lights Out AI: dashboard page logic */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const pct = (x) => `${Math.round((x || 0) * 100)}%`;

  const twin = new Twin($("twin"));
  let socket = null;
  let building = null;
  let lastDecisionKey = "";
  let lastReason = "";
  let imgStamp = Date.now();
  let offline = false;

  // ---------- small helpers ----------
  function toast(msg) {
    const t = $("toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => t.classList.remove("show"), 5000);
  }

  function setStatus(kind, text) {
    $("status").className = `status ${kind}`;
    $("statusText").textContent = text;
  }

  setInterval(() => {
    $("clock").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }, 1000);

  // ---------- conditions ----------
  function showConditions(c) {
    if (!c) return;
    $("condSummary").textContent = c.summary || "-";
    const chip = $("migChip");
    chip.textContent = c.migration_level || "-";
    chip.className = `chip ${c.migration_level || "medium"}`;
    $("skyDanger").textContent = pct(c.sky_danger);
    const bar = $("skyBar");
    bar.style.width = pct(c.sky_danger);
    bar.style.background = c.sky_danger >= 0.65 ? "var(--bad)" : c.sky_danger >= 0.35 ? "var(--mid)" : "var(--good)";
    $("wind").innerHTML = `${c.wind_dir || "-"} ${Math.round(c.wind_speed_mph || 0)}<small> mph · ${c.sky_cover ?? "-"}%</small>`;
    const s = c.scenario || "live";
    $("scenarioTag").innerHTML = s === "live"
      ? `<span class="tag">live · api.weather.gov</span>`
      : `<span class="tag" style="color:var(--mid)">simulated: ${s.replace("_", " ")}</span>`;
    document.querySelectorAll(".scen").forEach((b) => b.classList.toggle("active", b.dataset.s === s));
    twin.setFog(c.fog);
  }

  // ---------- building + photos ----------
  function showBuilding(b) {
    building = b;
    $("buildingName").textContent = b.building || "-";
    twin.draw(b);
    twin.showRisk($("riskToggle").checked);
    imgStamp = Date.now();
    showPhotos();
  }

  function img(src, alt) {
    return `<img src="${LO.url(src)}?t=${imgStamp}" alt="${alt}" />`;
  }

  function showPhotos(afterUrl) {
    const b = building || {};
    const before = $("debugToggle").checked && b.debug_url ? b.debug_url : b.photo_url;
    $("beforeLabel").textContent = $("debugToggle").checked ? "detected windows boxed" : "as photographed";
    $("beforeBox").innerHTML = before
      ? img(before, "Night photo of the building")
      : `<div class="empty-img">No photo in fake mode.<br/>Turn fake mode off to see the real building.</div>`;
    const after = afterUrl || b.after_url;
    $("afterBox").innerHTML = after
      ? img(after, "Same photo with the chosen windows darkened")
      : `<div class="empty-img">Run the AI decision to see<br/>which windows go dark.</div>`;
  }

  async function loadBuildings() {
    try {
      const list = await LO.api().buildings();
      const sel = $("buildingSelect");
      sel.innerHTML = "";
      (list.buildings || []).forEach((b) => {
        const o = document.createElement("option");
        o.value = o.textContent = b.building;
        if (b.building === list.current) o.selected = true;
        sel.appendChild(o);
      });
    } catch (e) { /* not critical */ }
  }

  // ---------- decision ----------
  function clearDecision() {
    lastDecisionKey = "";
    lastReason = "";
    $("riskAfter").textContent = "-";
    $("barAfter").style.width = "0";
    $("riskDrop").textContent = "";
    $("reason").innerHTML = `<span class="muted">Press "Let the AI decide" to choose which windows to turn off.</span>`;
    $("source").textContent = "";
    $("countOff").textContent = $("kwh").textContent = $("usd").textContent = "-";
    $("replayBtn").disabled = true;
    $("voiceInfo").textContent = "";
  }

  function showRiskBefore(r) {
    $("riskBefore").textContent = pct(r);
    $("barBefore").style.width = pct(r);
  }

  function showDecision(d, { fromSocket = false } = {}) {
    if (!d || !d.reason) return;
    const key = `${d.building}|${d.reason}|${d.risk_before}|${d.risk_after}`;
    const isNew = key !== lastDecisionKey;
    lastDecisionKey = key;

    showRiskBefore(d.risk_before);
    $("riskAfter").textContent = pct(d.risk_after);
    $("barAfter").style.width = pct(d.risk_after);
    const drop = d.risk_before > 0 ? Math.round((1 - d.risk_after / d.risk_before) * 100) : 0;
    $("riskDrop").textContent = drop > 0 ? `▼ ${drop}% lower risk for birds tonight` : "No change needed tonight";

    $("reason").textContent = d.reason;
    lastReason = d.reason;
    $("source").innerHTML = d.source === "gemini"
      ? `<span class="tag" style="color:var(--accent)">decided by Gemini</span>`
      : `<span class="tag">rule-based fallback</span>`;
    const acts = d.actions || [];
    const offs = acts.filter((a) => a.state === "off").length;
    $("countOff").innerHTML = `${offs}<small> / ${acts.length - offs}</small>`;
    $("kwh").innerHTML = `${(d.energy_saved_kwh ?? 0).toFixed(1)}<small> kWh</small>`;
    $("usd").innerHTML = `$${(d.money_saved_usd ?? 0).toFixed(2)}`;
    $("replayBtn").disabled = false;

    if (d.windows) twin.setRisks(d.windows);
    if (d.after_url) { imgStamp = Date.now(); showPhotos(d.after_url); }

    // If no WebSocket is switching the windows for us, animate them here.
    if (!fromSocket && !(socket && socket.isOpen())) twin.wave(acts);

    if (isNew && $("voiceToggle").checked) playVoice();
  }

  async function playVoice() {
    if (!lastReason) return;
    $("voiceInfo").textContent = "speaking…";
    const how = await LO.speak(lastReason);
    $("voiceInfo").textContent = how === "elevenlabs" ? "voice: ElevenLabs"
      : how === "browser" ? "voice: browser (ElevenLabs not set up)" : "";
  }

  // ---------- full refresh ----------
  async function refresh() {
    try {
      const [cond, b, last] = await Promise.all([LO.api().conditions(), LO.api().windows(), LO.api().lastDecision()]);
      showConditions(cond);
      showBuilding(b);
      if (last && last.reason) showDecision(last, { fromSocket: true });
      else { clearDecision(); showRiskBefore(b.risk); }
      await loadBuildings();
      offline = false;
      return true;
    } catch (e) {
      offline = true;
      toast(`Backend not reachable at ${LO.BASE}. Turn on fake mode, or start the backend.`);
      setStatus("", "Backend offline");
      return false;
    }
  }

  // ---------- socket ----------
  function startSocket() {
    socket = LO.connectSocket({
      status: (ok) => {
        setStatus(ok ? "live" : "", ok ? "Live" : "Reconnecting…");
        if (ok && offline) refresh(); // backend came back: load everything again
      },
      building: (msg) => {
        const changed = !building || msg.building !== building.building;
        showBuilding(msg);
        if (changed) loadBuildings();
      },
      command: (msg) => twin.setWindow(msg.id, msg.state),
      decision: (msg) => showDecision(msg, { fromSocket: true }),
      conditions: (msg) => { showConditions(msg); refreshRisks(); },
    });
  }

  async function refreshRisks() {
    try {
      const b = await LO.api().windows();
      twin.setRisks(b.windows);
      if (!lastDecisionKey) showRiskBefore(b.risk);
    } catch (e) { /* ignore */ }
  }

  // ---------- buttons ----------
  async function run(btn, fn) {
    btn.disabled = true;
    try { await fn(); } catch (e) { toast(e.message); } finally { btn.disabled = false; }
  }

  $("decideBtn").addEventListener("click", (e) => run(e.currentTarget, async () => {
    $("decideBtn").textContent = "⏳ Thinking…";
    try {
      const d = await LO.api().decide();
      showDecision(d);
    } finally {
      $("decideBtn").textContent = "⚡ Let the AI decide";
    }
  }));

  $("resetBtn").addEventListener("click", (e) => run(e.currentTarget, async () => {
    const b = await LO.api().reset();
    showBuilding(b);
    clearDecision();
    refreshRisks();
  }));

  document.querySelectorAll(".scen").forEach((btn) => btn.addEventListener("click", () => run(btn, async () => {
    const c = await LO.api().simulate(btn.dataset.s);
    showConditions(c);
    await refreshRisks();
  })));

  $("buildingSelect").addEventListener("change", (e) => run(e.currentTarget, async () => {
    const b = await LO.api().select(e.target.value);
    showBuilding(b);
    clearDecision();
    refreshRisks();
  }));

  $("riskToggle").addEventListener("change", (e) => twin.showRisk(e.target.checked));
  $("debugToggle").addEventListener("change", () => showPhotos());
  $("replayBtn").addEventListener("click", playVoice);

  $("fakeBtn").addEventListener("click", async () => {
    LO.fake = !LO.fake;
    $("fakeBtn").textContent = `Fake mode: ${LO.fake ? "on" : "off"}`;
    $("fakeBtn").classList.toggle("active", LO.fake);
    if (LO.fake) {
      if (socket) socket.close();
      socket = null;
      setStatus("fake", "Fake data");
      await refresh();
    } else {
      setStatus("", "Connecting…");
      if (await refresh()) startSocket();
    }
  });

  // ---------- start ----------
  // The socket keeps retrying every 2 s, so the page recovers on its own when the backend starts.
  refresh().then(startSocket);
})();
