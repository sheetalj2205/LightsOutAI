/* Lights Out AI: step 1, the building photo.
   Photo (night or day) + name -> POST /api/analyze -> onAnalyzed(building summary). */
const LO = window.LO;
const $ = (id) => document.getElementById(id);
const STEP_MS = 900;
const MAX_SIDE = 2000;

async function shrink(file) {
  // Big phone photos upload slowly; send at most 2000 px as JPEG.
  const bmp = await createImageBitmap(file);
  const scale = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height));
  const c = document.createElement("canvas");
  c.width = Math.round(bmp.width * scale);
  c.height = Math.round(bmp.height * scale);
  c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
  return new Promise((res) => c.toBlob(res, "image/jpeg", 0.9));
}

export function initPhotoStep({ onAnalyzed, toast }) {
  let file = null;
  let timers = [];

  const showError = (msg) => { $("photoError").textContent = msg; $("photoError").hidden = !msg; };
  const phase = (p) => {
    $("photoForm").hidden = p !== "form";
    $("photoProgress").hidden = p !== "progress";
    $("photoResult").hidden = p !== "result";
  };
  const progress = (k) => [...$("photoProgress").children].forEach((li, i) => {
    li.className = i < k ? "done" : i === k ? "doing" : "";
  });

  function setFile(f) {
    if (!f) return;
    if (/\.hei[cf]$/i.test(f.name) || /hei[cf]/i.test(f.type)) {
      showError("iPhone HEIC photos aren't supported by browsers. Please export it as JPG first.");
      return;
    }
    if (!/^image\//.test(f.type)) { showError("Please choose a JPG or PNG photo."); return; }
    file = f;
    showError("");
    $("photoPreview").src = URL.createObjectURL(f);
    $("photoPreview").hidden = false;
    $("dropHint").hidden = true;
    if (!$("photoName").value) {
      $("photoName").value = f.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ")
        .replace(/\b\w/g, (m) => m.toUpperCase()).slice(0, 60);
    }
  }

  function reset() {
    file = null;
    timers.forEach(clearTimeout);
    $("photoForm").reset();
    $("photoPreview").hidden = true;
    $("dropHint").hidden = false;
    $("photoManual").open = false;
    showError("");
    phase("form");
  }

  function showResult(b) {
    const lit = b.windows.filter((w) => w.state !== "off").length;
    $("resultImg").src = b.debug_url ? `${LO.url(b.debug_url)}?t=${Date.now()}` : "";
    $("resultName").textContent = b.building;
    $("resultFacts").textContent = `${b.floors} floors · ${b.floors * b.cols} windows · ${lit} lit`;
    const pill = $("resultLights");
    const simulated = b.lights === "simulated";
    pill.textContent = simulated ? "Day photo · tonight's lights simulated" : "Night photo · lit windows detected";
    pill.className = `pill${simulated ? " sim" : ""}`;
    phase("result");
  }

  async function submit(ev) {
    ev.preventDefault();
    if (LO.fake) { toast("Offline demo data is on (⋯ menu). Turn it off to analyze a photo."); return; }
    if (!file) { showError("Add a photo of the building first."); return; }
    const name = $("photoName").value.trim();
    if (!name) { showError("Give the building a name."); $("photoName").focus(); return; }

    let blob;
    try { blob = await shrink(file); } catch (e) { showError("Couldn't read that image. Please use a JPG or PNG."); return; }
    const fd = new FormData();
    fd.append("photo", blob, "building.jpg");
    fd.append("building", name);
    if ($("photoFloors").value) fd.append("floors", $("photoFloors").value);
    if ($("photoCols").value) fd.append("cols", $("photoCols").value);

    phase("progress");
    progress(0);
    timers = [1, 2].map((k) => setTimeout(() => progress(k), k * STEP_MS));
    const started = performance.now();
    try {
      const r = await fetch(LO.url("/api/analyze"), { method: "POST", body: fd });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) {
        timers.forEach(clearTimeout);
        phase("form");
        if (r.status === 422) $("photoManual").open = true;
        showError(body.detail || `Something went wrong (HTTP ${r.status}).`);
        return;
      }
      // Let the checklist finish its story, then the building rises.
      const wait = Math.max(0, 2 * STEP_MS - (performance.now() - started));
      setTimeout(() => {
        progress(3);
        onAnalyzed(body);
        setTimeout(() => showResult(body), 500);
      }, wait);
    } catch (e) {
      timers.forEach(clearTimeout);
      phase("form");
      showError("Couldn't reach the server. Is the backend running?");
    }
  }

  $("photoForm").addEventListener("submit", submit);
  $("photoInput").addEventListener("change", (e) => setFile(e.target.files[0]));
  const drop = $("drop");
  ["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((t) => drop.addEventListener(t, () => drop.classList.remove("over")));
  drop.addEventListener("drop", (e) => { e.preventDefault(); setFile(e.dataTransfer.files[0]); });

  return { reset, showResult, pick: () => $("photoInput").click() };
}
