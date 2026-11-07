/* Lights Out AI: the 3D building (Three.js).

   createScene(container) -> {
     setBuilding({floors, cols, windows}), setWindows(windows), setWindow(id, state),
     setRiskView(bool), setBirdMode("attracted" | "safe"), thinking(bool), dispose()
   }
   Throws if WebGL is unavailable, so the page can fall back to a flat grid.

   Story: birds swirl around the glowing floors ("attracted") -> the AI scans the facade
   ("thinking") -> windows click off top floor first -> birds regroup into V-formations and
   migrate safely past the dark building ("safe"). */
import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";

const CELL_W = 1.0;        // width of one window column
const CELL_H = 1.3;        // height of one floor
const BASE_Y = 0.35;       // plinth height
const WIN_W = 0.62, WIN_H = 0.84;
const FADE = 0.14;         // seconds (time constant); ~0.4 s to settle

const LIGHT = {            // detected light color -> glow color
  white: 0xfff1d6, yellow: 0xffd27a, orange: 0xffb066, blue: 0xd9e8ff,
  red: 0xff8a70, green: 0xd4ffd4,
};
const OFF_GLASS = new THREE.Color(0x1c2436);
const FLASH = new THREE.Color(2, 2, 2);
const RISK_LOW = new THREE.Color(0x3ccf6e), RISK_MID = new THREE.Color(0xffb020), RISK_HIGH = new THREE.Color(0xff4d4d);
const LEVEL = { on: 1, dim: 0.32, off: 0 };
const UP = new THREE.Vector3(0, 1, 0);

// ------------------------------------------------------------------ textures
function gradientTexture(stops, w = 4, h = 512) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const ctx = c.getContext("2d");
  const g = ctx.createLinearGradient(0, 0, 0, h);
  stops.forEach(([at, col]) => g.addColorStop(at, col));
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function glowTexture(inner = "rgba(255,255,255,1)", outer = "rgba(255,255,255,0)") {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, inner);
  g.addColorStop(0.25, inner);
  g.addColorStop(1, outer);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function riskColor(r) {
  const t = Math.min(Math.max(r / 0.6, 0), 1);
  return t < 0.5 ? RISK_LOW.clone().lerp(RISK_MID, t / 0.5) : RISK_MID.clone().lerp(RISK_HIGH, (t - 0.5) / 0.5);
}

// Seeded random so the trees and skyline look the same on every load.
function rng(seed) {
  return () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
}

function makeBird(mat) {
  const g = new THREE.Group();
  const wing = new THREE.BufferGeometry();
  wing.setAttribute("position", new THREE.Float32BufferAttribute([0, 0, 0.12, 0, 0, -0.1, 0.42, 0, -0.02], 3));
  const left = new THREE.Mesh(wing, mat);
  const right = new THREE.Mesh(wing, mat);
  right.scale.x = -1;
  const body = new THREE.Mesh(new THREE.ConeGeometry(0.05, 0.3, 5), mat);
  body.rotation.x = Math.PI / 2; // nose points +z, so lookAt() aims it along its flight
  g.add(left, right, body);
  g.scale.setScalar(0.85);
  return { mesh: g, left, right };
}

// ------------------------------------------------------------------ scene
export function createScene(container) {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = gradientTexture([[0, "#0f1738"], [0.42, "#353a78"], [0.72, "#86699c"], [1, "#e9a98d"]]);
  scene.fog = new THREE.Fog(0x6f5d92, 45, 120);

  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 500);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.enablePan = false;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.5;
  controls.maxPolarAngle = 1.45;
  controls.minPolarAngle = 0.35;
  let idleTimer = null, userDragging = false;
  controls.addEventListener("start", () => { userDragging = true; controls.autoRotate = false; clearTimeout(idleTimer); });
  controls.addEventListener("end", () => {
    userDragging = false;
    idleTimer = setTimeout(() => { if (!camTween && !busyFocus) controls.autoRotate = true; }, 4000);
  });

  // --- lights ---
  scene.add(new THREE.HemisphereLight(0xb7b2ff, 0x262a40, 1.05));
  const moonLight = new THREE.DirectionalLight(0xc9d6ff, 0.9);
  moonLight.position.set(-20, 26, -10);
  scene.add(moonLight);
  const sun = new THREE.DirectionalLight(0xffc4a3, 0.75); // last glow of the sunset
  sun.position.set(18, 14, 20);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  Object.assign(sun.shadow.camera, { left: -30, right: 30, top: 30, bottom: -30 });
  scene.add(sun);

  // --- static world: ground, moon, stars, skyline ---
  const ground = new THREE.Mesh(new THREE.CircleGeometry(160, 64),
    new THREE.MeshStandardMaterial({ color: 0x2c3149, roughness: 1 }));
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  const moon = new THREE.Sprite(new THREE.SpriteMaterial({
    map: glowTexture("rgba(255,248,230,1)", "rgba(255,240,220,0)"), fog: false, depthWrite: false,
  }));
  moon.scale.setScalar(14);
  moon.position.set(-60, 55, -90);
  scene.add(moon);

  const starPos = [];
  const r0 = rng(11);
  for (let i = 0; i < 260; i++) {
    const a = r0() * Math.PI * 2, e = 0.3 + r0() * 1.1, r = 180;
    starPos.push(Math.cos(a) * Math.cos(e) * r, Math.sin(e) * r, Math.sin(a) * Math.cos(e) * r);
  }
  const starMat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.7, transparent: true, opacity: 0.75, fog: false });
  scene.add(new THREE.Points(new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(starPos, 3)), starMat));

  // Distant city skyline: dark towers with a few lit windows.
  (function skyline() {
    const r = rng(42);
    const n = 70;
    const towers = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1),
      new THREE.MeshBasicMaterial({ color: 0x1b2042, fog: false }), n);
    const litDots = [];
    const m = new THREE.Matrix4();
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + r() * 0.05;
      const dist = 95 + r() * 30;
      const w = 4 + r() * 6, h = 3 + Math.pow(r(), 2) * 16, d = 3 + r() * 4;
      const x = Math.cos(a) * dist, z = Math.sin(a) * dist;
      m.compose(new THREE.Vector3(x, h / 2, z), new THREE.Quaternion().setFromAxisAngle(UP, -a), new THREE.Vector3(w, h, d));
      towers.setMatrixAt(i, m);
      const dots = Math.floor(h / 3);
      for (let k = 0; k < dots; k++) {
        if (r() > 0.45) continue;
        const off = (r() - 0.5) * w * 0.8;
        litDots.push(x - Math.cos(a) * (d / 2 + 0.1) + -Math.sin(a) * off, 1 + r() * (h - 2), z - Math.sin(a) * (d / 2 + 0.1) + Math.cos(a) * off);
      }
    }
    scene.add(towers);
    scene.add(new THREE.Points(new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(litDots, 3)),
      new THREE.PointsMaterial({ color: 0xffd38a, size: 0.9, transparent: true, opacity: 0.85, fog: false })));
  })();

  // --- birds ---
  const birdMat = new THREE.MeshBasicMaterial({ color: 0xf4f1ff, side: THREE.DoubleSide, fog: false });
  const birds = [];
  const rb = rng(7);
  for (let i = 0; i < 26; i++) {
    const { mesh, left, right } = makeBird(birdMat);
    const a = rb() * Math.PI * 2;
    const b = {
      mesh, left, right,
      pos: new THREE.Vector3(Math.cos(a) * 60, 12 + rb() * 10, Math.sin(a) * 60), // fly in from afar
      vel: new THREE.Vector3(),
      theta: rb() * Math.PI * 2,
      speed: (0.55 + rb() * 0.45) * (rb() < 0.5 ? 1 : -1),
      ring: rb(), bob: rb() * 6, flap: rb() * 10,
      floorY: 3, repick: 0,
      flock: i % 2, slot: Math.floor(i / 2),
    };
    mesh.position.copy(b.pos);
    scene.add(mesh);
    birds.push(b);
  }
  let birdMode = "attracted";
  const lastPhase = [0, 0];

  // --- building state ---
  let building = null;        // THREE.Group, rebuilt per building
  let winMesh = null, haloMesh = null, scanMeshes = [], aviation = null, lampGlows = [];
  let dims = { w: 8, h: 8, d: 4, floors: 6, cols: 8 };
  const slots = new Map();    // window id -> { idx: [front, back], data, state, y }
  let cur = [], tgt = [];
  let riskView = false;
  let scanning = false;

  function targetFor(slot) {
    let level = LEVEL[slot.state] ?? 1;
    if (level === 0) return OFF_GLASS.clone();
    if (riskView) level = Math.max(level, 0.7);
    const base = riskView ? riskColor(slot.data.risk || 0) : new THREE.Color(LIGHT[slot.data.color] ?? LIGHT.white);
    return OFF_GLASS.clone().lerp(base, level);
  }

  function refreshTargets() {
    for (const slot of slots.values()) {
      const c = targetFor(slot);
      for (const i of slot.idx) tgt[i].copy(c);
    }
  }

  function fitCamera() {
    // Fit the whole building plus some sky above it (where the flocks fly) in both directions.
    const vHalf = (camera.fov * Math.PI) / 360;
    const hHalf = Math.atan(Math.tan(vHalf) * camera.aspect);
    const needH = (dims.h + 7) * 0.62, needW = Math.max(dims.w, dims.d) * 1.15;
    const dist = Math.max(needH / Math.tan(vHalf), needW / Math.tan(hHalf), 14) + dims.d * 0.5;
    controls.target.set(0, dims.h * 0.62, 0);
    const dirV = new THREE.Vector3(0.6, 0.2, 0.78).normalize();
    camera.position.copy(controls.target).addScaledVector(dirV, dist);
    controls.minDistance = dist * 0.5;
    controls.maxDistance = dist * 1.6;
    controls.update();
  }

  function box(w, h, d, mat, x, y, z, shadow = true) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
    m.position.set(x, y, z);
    m.castShadow = shadow;
    m.receiveShadow = true;
    return m;
  }

  let rise = null; // {start, ms} while a new building grows out of the ground

  // Plaza, trees and street lamps around a building footprint of w x d.
  function addGrounds(group, w, d) {
    const m = new THREE.Matrix4();
    const plaza = new THREE.Mesh(new THREE.CircleGeometry(Math.max(w, d) * 0.6 + 2.6, 48),
      new THREE.MeshStandardMaterial({ color: 0x3a4060, roughness: 0.95 }));
    plaza.rotation.x = -Math.PI / 2;
    plaza.position.y = 0.01;
    plaza.receiveShadow = true;
    group.add(plaza);
    const rt = rng(3);
    const trunkGeo = new THREE.CylinderGeometry(0.08, 0.12, 0.8, 6);
    const crownGeo = new THREE.ConeGeometry(0.75, 1.9, 7);
    const trunkMat = new THREE.MeshStandardMaterial({ color: 0x3a2f2a });
    const crownMat = new THREE.MeshStandardMaterial({ color: 0x24493f, roughness: 0.9 });
    const nTrees = 26;
    const trunks = new THREE.InstancedMesh(trunkGeo, trunkMat, nTrees);
    const crowns = new THREE.InstancedMesh(crownGeo, crownMat, nTrees);
    const ringR = Math.max(w, d) * 0.9 + 4;
    for (let t = 0; t < nTrees; t++) {
      let a = (t / nTrees) * Math.PI * 2 + rt() * 0.2;
      if (Math.abs(Math.atan2(Math.sin(a - Math.PI / 2), Math.cos(a - Math.PI / 2))) < 0.35) a += 0.7; // keep the entrance path clear
      const r = ringR + rt() * 6;
      const sc = 0.8 + rt() * 0.6;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      trunks.setMatrixAt(t, m.compose(new THREE.Vector3(x, 0.4 * sc, z), new THREE.Quaternion(), new THREE.Vector3(sc, sc, sc)));
      crowns.setMatrixAt(t, m.compose(new THREE.Vector3(x, (0.8 + 0.95) * sc, z), new THREE.Quaternion(), new THREE.Vector3(sc, sc, sc)));
    }
    trunks.castShadow = crowns.castShadow = true;
    group.add(trunks, crowns);

    lampGlows = [];
    const lampMat = new THREE.MeshStandardMaterial({ color: 0x2b2f40 });
    const glowMap = glowTexture("rgba(255,214,150,1)", "rgba(255,200,120,0)");
    const lampR = Math.max(w, d) * 0.6 + 2.2;
    for (let l = 0; l < 6; l++) {
      const a = (l / 6) * Math.PI * 2 + Math.PI / 6;
      const x = Math.cos(a) * lampR, z = Math.sin(a) * lampR;
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.05, 1.8, 6), lampMat);
      pole.position.set(x, 0.9, z);
      group.add(pole);
      const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowMap, depthWrite: false, blending: THREE.AdditiveBlending }));
      glow.position.set(x, 1.85, z);
      glow.scale.setScalar(0.75);
      group.add(glow);
      lampGlows.push(glow);
    }

  }

  function disposeBuilding() {
    if (!building) return;
    scene.remove(building);
    building.traverse((o) => { o.geometry?.dispose(); if (o.material && o.material !== birdMat) o.material.dispose?.(); });
    building = null;
    winMesh = haloMesh = aviation = null;
    scanMeshes = [];
    lampGlows = [];
    slots.clear();
    cur = []; tgt = [];
  }

  // Empty plot waiting for a building: dashed outline, trees, lamps; birds pass by safely.
  function setEmpty() {
    disposeBuilding();
    rise = null;
    building = new THREE.Group();
    const w = 8, d = 4.2;
    dims = { w, h: 7, d, floors: 5, cols: 7 };
    const pts = [[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2], [-w / 2, -d / 2]]
      .map(([x, z]) => new THREE.Vector3(x, 0.06, z));
    const outline = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineDashedMaterial({ color: 0xc9ccff, dashSize: 0.45, gapSize: 0.3 }));
    outline.computeLineDistances();
    building.add(outline);
    const post = new THREE.ConeGeometry(0.12, 0.5, 8);
    const postMat = new THREE.MeshStandardMaterial({ color: 0xffb648, emissive: 0x7a4a00 });
    for (const p of pts.slice(0, 4)) {
      const c = new THREE.Mesh(post, postMat);
      c.position.set(p.x, 0.25, p.z);
      building.add(c);
    }
    addGrounds(building, w, d);
    scene.add(building);
    fitCamera();
    birdMode = "safe";
    busyFocus = false;
    if (!userDragging) controls.autoRotate = true;
  }


  function setBuilding({ floors, cols, windows }, opts = {}) {
    floors = Math.max(1, floors || Math.max(1, ...windows.map((w) => w.floor)));
    cols = Math.max(1, cols || Math.max(1, ...windows.map((w) => w.col)));
    disposeBuilding();
    building = new THREE.Group();
    const w = cols * CELL_W + 0.9, h = floors * CELL_H + 0.45, d = Math.max(3.4, cols * 0.45);
    dims = { w, h, d, floors, cols };
    const top = BASE_Y + h;

    const stone = new THREE.MeshStandardMaterial({ color: 0xeef0f6, roughness: 0.8 });
    const trim = new THREE.MeshStandardMaterial({ color: 0xf6f4ef, roughness: 0.55 });
    const dark = new THREE.MeshStandardMaterial({ color: 0x3a4058, roughness: 0.6, metalness: 0.3 });

    // Plinth, body, corner pillars, crown.
    building.add(box(w + 1.2, BASE_Y, d + 1.2, dark, 0, BASE_Y / 2, 0));
    building.add(box(w, h, d, stone, 0, BASE_Y + h / 2, 0));
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
      building.add(box(0.32, h + 0.1, 0.32, trim, sx * (w / 2 + 0.06), BASE_Y + h / 2, sz * (d / 2 + 0.06)));
    }
    building.add(box(w + 0.5, 0.35, d + 0.5, trim, 0, top + 0.17, 0));

    // Rooftop: penthouse, mechanical units, antenna with a blinking aviation light.
    const ph = box(w * 0.42, 1.1, d * 0.55, stone, -w * 0.12, top + 0.35 + 0.55, 0);
    building.add(ph);
    building.add(box(0.9, 0.5, 0.7, dark, w * 0.3, top + 0.6, d * 0.15));
    building.add(box(0.6, 0.4, 0.6, dark, w * 0.3, top + 0.55, -d * 0.2));
    const mastH = 2.6;
    const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.07, mastH, 6), dark);
    mast.position.set(-w * 0.12, top + 0.35 + 1.1 + mastH / 2, 0);
    building.add(mast);
    aviation = new THREE.Mesh(new THREE.SphereGeometry(0.12, 12, 8), new THREE.MeshBasicMaterial({ color: 0xff2a2a, toneMapped: false }));
    aviation.position.set(-w * 0.12, top + 0.35 + 1.1 + mastH + 0.05, 0);
    const avGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture("rgba(255,60,60,1)", "rgba(255,40,40,0)"), depthWrite: false, blending: THREE.AdditiveBlending }));
    avGlow.scale.setScalar(1.6);
    aviation.add(avGlow);
    building.add(aviation);

    // Fins between columns and ledges at each floor, front + back.
    const fin = new THREE.BoxGeometry(0.08, h - 0.1, 0.2);
    const ledge = new THREE.BoxGeometry(w, 0.07, 0.18);
    const fins = new THREE.InstancedMesh(fin, trim, (cols + 1) * 2);
    const ledges = new THREE.InstancedMesh(ledge, trim, (floors + 1) * 2);
    const m = new THREE.Matrix4();
    let k = 0;
    for (const side of [1, -1]) for (let c = 0; c <= cols; c++) {
      fins.setMatrixAt(k++, m.makeTranslation((c - cols / 2) * CELL_W, BASE_Y + h / 2, side * (d / 2 + 0.08)));
    }
    k = 0;
    for (const side of [1, -1]) for (let f = 0; f <= floors; f++) {
      ledges.setMatrixAt(k++, m.makeTranslation(0, BASE_Y + 0.2 + f * CELL_H, side * (d / 2 + 0.07)));
    }
    fins.castShadow = true;
    building.add(fins, ledges);

    // Side faces: ribbons of dark glass.
    const sideGlass = new THREE.MeshStandardMaterial({ color: 0x29324a, roughness: 0.25, metalness: 0.5 });
    for (const side of [1, -1]) for (let f = 0; f < floors; f++) {
      const strip = new THREE.Mesh(new THREE.PlaneGeometry(d - 0.9, WIN_H * 0.8), sideGlass);
      strip.position.set(side * (w / 2 + 0.01), BASE_Y + 0.2 + (f + 0.5) * CELL_H, 0);
      strip.rotation.y = side * Math.PI / 2;
      building.add(strip);
    }

    // Lobby canopy over the front entrance, lit from below.
    const canopyY = BASE_Y + CELL_H * 0.9;
    building.add(box(Math.min(4, w * 0.45), 0.12, 1.4, trim, 0, canopyY, d / 2 + 0.75));
    for (const sx of [-1, 1]) building.add(box(0.08, canopyY - BASE_Y, 0.08, dark, sx * Math.min(1.8, w * 0.2), BASE_Y + (canopyY - BASE_Y) / 2, d / 2 + 1.35));
    const under = new THREE.Mesh(new THREE.PlaneGeometry(Math.min(3.6, w * 0.4), 1.1), new THREE.MeshBasicMaterial({ color: 0xffe2a8, toneMapped: false }));
    under.rotation.x = Math.PI / 2;
    under.position.set(0, canopyY - 0.07, d / 2 + 0.75);
    building.add(under);

    // Windows: every grid cell gets a pane (front + back). Undetected cells stay dark glass.
    const byCell = new Map(windows.map((win) => [`${win.floor}:${win.col}`, win]));
    const n = floors * cols * 2;
    winMesh = new THREE.InstancedMesh(new THREE.PlaneGeometry(WIN_W, WIN_H), new THREE.MeshBasicMaterial({ toneMapped: false }), n);
    haloMesh = new THREE.InstancedMesh(new THREE.PlaneGeometry(WIN_W * 1.8, WIN_H * 1.55), new THREE.MeshBasicMaterial({
      transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false,
    }), n);
    slots.clear();
    cur = []; tgt = [];
    let i = 0;
    const q = new THREE.Quaternion(), s = new THREE.Vector3(1, 1, 1), p = new THREE.Vector3();
    for (let f = 1; f <= floors; f++) {
      for (let c = 1; c <= cols; c++) {
        const win = byCell.get(`${f}:${c}`);
        const idx = [];
        const y = BASE_Y + 0.2 + (f - 0.5) * CELL_H;
        for (const side of [1, -1]) {
          p.set((c - (cols + 1) / 2) * CELL_W * side, y, side * (d / 2 + 0.015));
          q.setFromAxisAngle(UP, side === 1 ? 0 : Math.PI);
          winMesh.setMatrixAt(i, m.compose(p, q, s));
          p.z += side * 0.005;
          haloMesh.setMatrixAt(i, m.compose(p, q, s));
          cur.push(OFF_GLASS.clone()); tgt.push(OFF_GLASS.clone());
          winMesh.setColorAt(i, OFF_GLASS);
          haloMesh.setColorAt(i, new THREE.Color(0, 0, 0));
          idx.push(i++);
        }
        if (win) slots.set(win.id, { idx, data: win, state: win.state || "on", y });
      }
    }
    building.add(winMesh, haloMesh);

    // AI scan line that sweeps the facade while the AI is thinking.
    scanMeshes = [];
    const scanMat = new THREE.MeshBasicMaterial({ color: 0x7df9ff, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false });
    for (const side of [1, -1]) {
      const sm = new THREE.Mesh(new THREE.PlaneGeometry(w + 0.6, 0.16), scanMat);
      sm.position.set(0, BASE_Y, side * (d / 2 + 0.2));
      sm.rotation.y = side === 1 ? 0 : Math.PI;
      sm.visible = false;
      building.add(sm);
      scanMeshes.push(sm);
    }

    addGrounds(building, w, d);

    scene.add(building);
    refreshTargets();
    fitCamera();
    if (opts.rise) {
      building.scale.y = 0.001;
      rise = { start: performance.now(), ms: 1800 };
    } else {
      rise = null;
    }
  }

  function setWindow(id, state) {
    const slot = slots.get(id);
    if (!slot || !(state in LEVEL)) return;
    const wasLit = slot.state !== "off";
    slot.state = state;
    slot.data = { ...slot.data, state };
    const c = targetFor(slot);
    for (const i of slot.idx) {
      if (state === "off" && wasLit) cur[i].copy(FLASH); // a quick "click" flash, then dark
      tgt[i].copy(c);
    }
  }

  function setWindows(windows) {
    for (const w of windows) {
      const slot = slots.get(w.id);
      if (!slot) continue;
      slot.data = { ...slot.data, ...w };
      slot.state = w.state || slot.state;
    }
    refreshTargets();
  }

  function setRiskView(on) {
    riskView = !!on;
    refreshTargets();
  }

  function litSlots() {
    return [...slots.values()].filter((s) => s.state !== "off");
  }

  // --- camera moves ---
  let camTween = null, busyFocus = false;
  function focusFront() {
    const t = controls.target.clone();
    const dist = camera.position.distanceTo(t);
    const az = 0.32, el = 0.16;
    const to = new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el)).multiplyScalar(dist).add(t);
    camTween = { from: camera.position.clone(), to, start: performance.now(), ms: 1400 };
    controls.autoRotate = false;
    controls.enabled = false;
  }

  function thinking(on) {
    scanning = !!on;
    scanMeshes.forEach((sm) => { sm.visible = scanning; });
    if (on) { busyFocus = true; focusFront(); }
  }

  function setBirdMode(mode) {
    birdMode = mode === "safe" ? "safe" : "attracted";
    if (birdMode === "safe") {
      // Let the new dark building sink in, then let the camera turn again.
      clearTimeout(idleTimer);
      idleTimer = setTimeout(() => { busyFocus = false; if (!userDragging) controls.autoRotate = true; }, 3500);
    } else {
      busyFocus = false;
      if (!userDragging && !camTween) controls.autoRotate = true;
    }
  }

  // --- resize ---
  const resize = () => {
    const { clientWidth: cw, clientHeight: ch } = container;
    if (!cw || !ch) return;
    renderer.setSize(cw, ch, false);
    camera.aspect = cw / ch;
    camera.updateProjectionMatrix();
    if (building && !camTween && !userDragging) fitCamera();
  };
  const ro = new ResizeObserver(resize);
  ro.observe(container);
  resize();

  // --- birds ---
  const tmpT = new THREE.Vector3(), tmpA = new THREE.Vector3(), look = new THREE.Vector3();
  const pathA = new THREE.Vector3(), pathB = new THREE.Vector3(), dir = new THREE.Vector3(), right = new THREE.Vector3();
  const PERIOD = 15;

  function birdTarget(b, t, dt, out) {
    if (birdMode === "attracted") {
      // Trapped by the light: tight loops around the glowing floors.
      b.repick -= dt;
      if (b.repick <= 0) {
        const lit = litSlots();
        b.floorY = lit.length ? lit[Math.floor(Math.random() * lit.length)].y : dims.h + 3;
        b.repick = 2.5 + Math.random() * 3;
      }
      b.theta += b.speed * dt;
      const rx = dims.w / 2 + 0.9 + b.ring * 1.6, rz = dims.d / 2 + 0.9 + b.ring * 1.6;
      return out.set(Math.cos(b.theta) * rx, b.floorY + Math.sin(t * 2.2 + b.bob) * 0.35, Math.sin(b.theta) * rz);
    }
    // Safe: two V-formations migrating past the dark building, looping.
    const phase = ((t / PERIOD) + b.flock * 0.5) % 1;
    const lift = dims.h + 2.2 + b.flock * 2.2;
    pathA.set(-45, lift, 14 - b.flock * 8);
    pathB.set(45, lift + 2, -16 - b.flock * 8);
    dir.subVectors(pathB, pathA).normalize();
    right.crossVectors(dir, UP).normalize();
    const k = Math.floor(b.slot / 2) + (b.slot % 2 ? 1 : 0);
    const side = b.slot === 0 ? 0 : (b.slot % 2 ? 1 : -1);
    out.lerpVectors(pathA, pathB, phase).addScaledVector(right, side * k * 0.9).addScaledVector(dir, -k * 1.0);
    return out;
  }

  // --- loop ---
  const clock = new THREE.Clock();
  const glow = new THREE.Color();
  let raf = 0;
  function frame() {
    raf = requestAnimationFrame(frame);
    if (document.hidden) return;
    const dt = Math.min(clock.getDelta(), 0.05);
    const t = clock.elapsedTime;

    if (camTween) {
      const p = Math.min((performance.now() - camTween.start) / camTween.ms, 1);
      const e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
      camera.position.lerpVectors(camTween.from, camTween.to, e);
      camera.lookAt(controls.target);
      if (p >= 1) { camTween = null; controls.enabled = true; }
    } else {
      controls.update();
    }

    // New building grows out of the ground with a little overshoot.
    if (rise && building) {
      const p = Math.min((performance.now() - rise.start) / rise.ms, 1);
      const c1 = 1.4, c3 = c1 + 1;
      building.scale.y = Math.max(0.001, 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2));
      if (p >= 1) { building.scale.y = 1; rise = null; }
    }

    // Window fades.
    if (winMesh) {
      const k = 1 - Math.exp(-dt / FADE);
      let changed = false;
      for (let i = 0; i < cur.length; i++) {
        const c = cur[i], g = tgt[i];
        if (Math.abs(c.r - g.r) + Math.abs(c.g - g.g) + Math.abs(c.b - g.b) < 0.002) continue;
        c.lerp(g, k);
        winMesh.setColorAt(i, c);
        glow.copy(c).sub(OFF_GLASS);
        glow.r = Math.max(glow.r, 0); glow.g = Math.max(glow.g, 0); glow.b = Math.max(glow.b, 0);
        haloMesh.setColorAt(i, glow);
        changed = true;
      }
      if (changed) { winMesh.instanceColor.needsUpdate = true; haloMesh.instanceColor.needsUpdate = true; }
    }

    // Scan line sweeps up and down the facade.
    if (scanning) {
      const y = BASE_Y + (0.5 - 0.5 * Math.cos(t * 2.4)) * dims.h;
      scanMeshes.forEach((sm) => { sm.position.y = y; sm.material.opacity = 0.55 + 0.35 * Math.sin(t * 12); });
    }

    // Aviation light blinks; street lamps flicker very slightly.
    if (aviation) aviation.visible = Math.sin(t * 3.2) > -0.2;
    lampGlows.forEach((g, i) => g.scale.setScalar(0.72 + Math.sin(t * 3 + i) * 0.03));

    // Birds: spring toward their target, face their flight direction, flap.
    for (const b of birds) {
      const T = birdTarget(b, t, dt, tmpT);
      if (birdMode === "safe" && b.slot === 0) {
        const phase = ((t / PERIOD) + b.flock * 0.5) % 1;
        if (phase < lastPhase[b.flock]) {
          // Formation wrapped around: jump the whole flock back to the start.
          for (const o of birds) if (o.flock === b.flock) { birdTarget(o, t, 0, o.pos); o.vel.set(0, 0, 0); }
        }
        lastPhase[b.flock] = phase;
      }
      tmpA.subVectors(T, b.pos).multiplyScalar(3.0).addScaledVector(b.vel, -2.6);
      b.vel.addScaledVector(tmpA, dt);
      b.pos.addScaledVector(b.vel, dt);
      b.mesh.position.copy(b.pos);
      if (b.vel.lengthSq() > 1e-4) b.mesh.lookAt(look.copy(b.pos).add(b.vel));
      const flap = Math.sin(t * (birdMode === "attracted" ? 13 : 8) + b.flap) * 0.6;
      b.left.rotation.z = flap;
      b.right.rotation.z = -flap;
    }

    renderer.render(scene, camera);
  }
  frame();

  return {
    setBuilding, setEmpty, setWindow, setWindows, setRiskView, setBirdMode, thinking,
    dispose() {
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
