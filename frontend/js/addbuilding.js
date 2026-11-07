/* Lights Out AI: "Add a building" pop-up.
   Photo (night or day) + name + address -> POST /api/analyze -> onAdded(building summary). */
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

export function initAddBuilding({ onAdded, toast }) {
  const dlg = $("addDialog");
  let file = null;
  let timers = [];

  function showError(msg) {
    const e = $("addError");
    e.textContent = msg;
    e.hidden = !msg;
  }

  function setPhase(phase) {
    $("addFields").hidden = phase !== "form";
    $("addProgress").hidden = phase !== "progress";
  }

  function progress(stepIndex) {
    [...$("addProgress").children].forEach((li, i) => {
      li.className = i < stepIndex ? "done" : i === stepIndex ? "doing" : "";
    });
  }

  function setFile(f) {
    if (!f) return;
    if (/\.hei[cf]$/i.test(f.name) || /hei[cf]/i.test(f.type)) {
      showError("iPhone HEIC photos aren't supported by browsers. Please export it as JPG first.");
      return;
    }
    if (!/^image\//.test(f.type)) { showError("Please choose a JPG or PNG photo."); return; }
    file = f;
    showError("");
    const img = $("addPreview");
    img.src = URL.createObjectURL(f);
    img.hidden = false;
    $("dropHint").hidden = true;
    if (!$("addName").value) {
      $("addName").value = f.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").replace(/\b\w/g, (m) => m.toUpperCase()).slice(0, 60);
    }
  }

  function open() {
    if (LO.fake) { toast("Turn off fake mode (⋯ menu) to add a building."); return; }
    file = null;
    $("addForm").reset();
    $("addPreview").hidden = true;
    $("dropHint").hidden = false;
    $("addManual").open = false;
    showError("");
    setPhase("form");
    dlg.showModal();
  }

  function close() {
    timers.forEach(clearTimeout);
    dlg.close();
  }

  async function submit(ev) {
    ev.preventDefault();
    if (!file) { showError("Add a photo of the building first."); return; }
    const name = $("addName").value.trim();
    if (!name) { showError("Give the building a name."); $("addName").focus(); return; }

    let blob;
    try { blob = await shrink(file); } catch (e) { showError("Couldn't read that image. Please use a JPG or PNG."); return; }

    const fd = new FormData();
    fd.append("photo", blob, "building.jpg");
    fd.append("building", name);
    const address = $("addAddress").value.trim();
    if (address) fd.append("address", address);
    if ($("addFloors").value) fd.append("floors", $("addFloors").value);
    if ($("addCols").value) fd.append("cols", $("addCols").value);

    setPhase("progress");
    progress(0);
    timers = [1, 2, 3].map((k) => setTimeout(() => progress(k), k * STEP_MS));
    const started = performance.now();
    try {
      const r = await fetch(LO.url("/api/analyze"), { method: "POST", body: fd });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) {
        timers.forEach(clearTimeout);
        setPhase("form");
        if (r.status === 422) $("addManual").open = true;
        showError(body.detail || `Something went wrong (HTTP ${r.status}).`);
        return;
      }
      // Let the checklist finish its little story before the building appears.
      const wait = Math.max(0, 3 * STEP_MS - (performance.now() - started));
      setTimeout(() => {
        progress(4);
        setTimeout(() => { close(); onAdded(body); }, 450);
      }, wait);
    } catch (e) {
      timers.forEach(clearTimeout);
      setPhase("form");
      showError("Couldn't reach the server. Is the backend running?");
    }
  }

  $("addBtn").addEventListener("click", open);
  $("addClose").addEventListener("click", close);
  $("addCancel").addEventListener("click", close);
  $("addForm").addEventListener("submit", submit);
  $("addPhoto").addEventListener("change", (e) => setFile(e.target.files[0]));
  const drop = $("drop");
  ["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((t) => drop.addEventListener(t, () => drop.classList.remove("over")));
  drop.addEventListener("drop", (e) => { e.preventDefault(); setFile(e.dataTransfer.files[0]); });
}
