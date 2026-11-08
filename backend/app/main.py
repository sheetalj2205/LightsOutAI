"""Lights Out AI backend. Run from the backend/ folder:

    .venv/bin/uvicorn app.main:app --reload --port 8000

Then open http://localhost:8000/docs to try every endpoint.
"""
import asyncio
import json
import shutil
import logging
import re
from contextlib import asynccontextmanager
from typing import Optional

import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from . import config, db, decide as decider, detection, facade, geo, risk, scenarios, voice
from .demo import make_demo_photo
from .led import LedView
from .models import AlertRequest, DecideRequest, LocationRequest, SimulateRequest
from .state import Building, hub, state

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("lightsout")

DEMO_NAME = "Demo Hall"


MAX_BUILDINGS = 20  # buildings kept in memory at once


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "building"


def _cond_or_none(b: Optional[Building] = None):
    """Tonight's forecast at the building's (default: current) location, or None without an address."""
    if b is None:
        b = state.buildings.get(state.current)
    try:
        return scenarios.current_conditions(b.location if b else None)
    except scenarios.NoLocation:
        return None


def _cond(b: Optional[Building] = None):
    """Like _cond_or_none, but answers HTTP 409 when the building has no address yet."""
    cond = _cond_or_none(b)
    if cond is None:
        raise HTTPException(409, "Add this building's address first, so we can read its local forecast.")
    return cond


FACES = ("front", "right", "back", "left")


def _detect_face(img, photo: bytes, seed: str, threshold: int, corners=None, floors=None, cols=None):
    """Windows on one photo of one side -> (windows, method, lights)."""
    if corners:
        return detection.detect_grid(img, corners, floors, cols), "grid", "detected"
    day = facade.is_daylight(img)
    lights = "simulated" if day else "detected"  # a day photo shows no real night lights
    if not day:
        # Glass facades: windows from the frame grid; separate windows on a wall: bright blobs.
        grid = detection.detect_facade_grid(img)
        if len(grid) >= 12:
            return grid, "detect-grid", lights
    windows = [] if day else detection.detect_windows(img, threshold)
    if len(windows) >= 6:
        return windows, "detect", lights
    # Day photo, or too few lit windows: read the facade with AI (or use a given grid).
    info = None
    try:
        info = facade.read_facade(photo)
    except Exception as exc:
        log.warning("facade reading failed: %s", str(exc)[:200])
    f = (info or {}).get("floors") or floors
    c = (info or {}).get("cols") or cols
    known = bool(f and c)
    auto = [] if known else detection.detect_auto(img)
    if auto:
        return auto, "detect-auto", lights  # no AI: the brightest panes at the best brightness level
    if not known:
        gf, gc = facade.guess_grid(img)  # never ask the user for the grid
        f, c = f or gf, c or gc
    pts = None
    if info and info.get("corners"):
        h, w = img.shape[:2]
        pts = [[x * w, y * h] for x, y in info["corners"]]
    method = "ai-facade" if info and info.get("floors") and info.get("cols") else (
        "manual" if floors and cols else "estimate")
    return facade.simulate_windows(img, f, c, pts, seed=seed), method, "simulated"


def _analyze(name: str, photo: bytes, threshold: int, corners=None, floors=None, cols=None,
             location: Optional[dict] = None, sides: Optional[dict] = None) -> Building:
    """Front photo plus optional photos of the other sides ({"right": bytes, "back": ..., "left": ...})."""
    folder = config.OUTPUT_DIR / _slug(name)
    folder.mkdir(parents=True, exist_ok=True)
    base = f"/output/{_slug(name)}"
    photos = {"front": photo} | {k: v for k, v in (sides or {}).items() if k in FACES and k != "front" and v}
    windows, faces, method, lights, front_img = [], {}, "detect", "detected", None
    for face in FACES:
        if face not in photos:
            continue
        img = detection.load_image(photos[face])
        is_front = face == "front"
        found, m, li = _detect_face(img, photos[face], f"{name}:{face}", threshold,
                                    corners if is_front else None, floors if is_front else None,
                                    cols if is_front else None)
        if not is_front and not found:
            continue
        if is_front:
            front_img, method, lights = img, m, li
        found = [w.model_copy(update={"face": face, "id": len(windows) + i})
                 for i, w in enumerate(found, start=1)]
        windows += found
        stem = "photo" if is_front else face
        (folder / f"{stem}.jpg").write_bytes(photos[face])
        detection.save_debug_image(img, found, folder / f"{stem}_debug.jpg" if not is_front else folder / "debug.jpg")
        faces[face] = {"photo_url": f"{base}/{stem}.jpg",
                       "debug_url": f"{base}/{'debug' if is_front else stem + '_debug'}.jpg",
                       "image_width": img.shape[1], "image_height": img.shape[0], "lights": li}
    if location:
        windows = risk.score_windows(windows, scenarios.current_conditions(location))

    b = Building(name=name, windows=windows, photo=photo, image_size=(front_img.shape[1], front_img.shape[0]),
                 photo_url=faces["front"]["photo_url"], debug_url=faces["front"]["debug_url"], method=method,
                 original=[w.model_copy() for w in windows], location=location, lights=lights, faces=faces)
    # Keep only the most recent buildings (enough for a few people at once); the page never lists them.
    state.buildings.pop(name, None)
    state.buildings[name] = b
    while len(state.buildings) > MAX_BUILDINGS:
        old = next(iter(state.buildings))
        state.buildings.pop(old)
        shutil.rmtree(config.OUTPUT_DIR / _slug(old), ignore_errors=True)
    state.current = name
    state.last_decision = None
    return b


def _clear_old_uploads() -> None:
    """Delete photos and results left from earlier runs; every server start begins fresh."""
    for d in config.OUTPUT_DIR.iterdir():
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(db.init)
    await asyncio.to_thread(_clear_old_uploads)
    _analyze(DEMO_NAME, make_demo_photo(), threshold=150)
    yield


app = FastAPI(title="Lights Out AI", version="1.0", lifespan=lifespan,
              description="Turns off the building lights that kill migrating birds.")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=False)
app.mount("/output", StaticFiles(directory=config.OUTPUT_DIR), name="output")


def _get_building(name: Optional[str]) -> Building:
    try:
        return state.building(name)
    except KeyError:
        raise HTTPException(404, f"Unknown building: {name}. Call /api/analyze first.")


@app.get("/api/health")
def health():
    return {"ok": True, "gemini": bool(config.GEMINI_API_KEY), "bullsai": decider.bullsai_ready(),
            "tiger_data": db.enabled(),
            "twin_pages": len(hub.clients) - hub.led_boards(), "led_boards": hub.led_boards(),
            "scenario": scenarios.active_scenario(),
            "current_building": state.current}


@app.get("/api/conditions")
def conditions():
    """Tonight's weather, migration level (low/medium/high, estimated) and sky danger."""
    return _cond()


@app.get("/api/buildings")
def buildings():
    return {"current": state.current,
            "buildings": [{"building": b.name, "windows": len(b.windows), "photo_url": b.photo_url,
                           "method": b.method} for b in state.buildings.values()]}


@app.get("/api/windows")
def windows(building: Optional[str] = None):
    """Current window list of a building (default: the current one), for the twin page."""
    b = _get_building(building)
    cond = _cond_or_none(b)
    return b.summary() | {"risk": risk.building_risk(b.windows, cond) if cond else None}


@app.post("/api/select")
async def select_building(building: str = Form(...)):
    """Make a building the current one and show it on every twin page."""
    b = _get_building(building)
    state.current = b.name
    await hub.broadcast({"type": "building"} | b.summary())
    return b.summary()


@app.post("/api/analyze")
async def analyze(photo: UploadFile = File(...), building: str = Form("Building"),
                  address: Optional[str] = Form(None, description="Street address; its weather is used"),
                  threshold: int = Form(config.DETECT_THRESHOLD),
                  corners: Optional[str] = Form(None, description='Grid fallback: [[x,y] x4] TL,TR,BR,BL'),
                  floors: Optional[int] = Form(None), cols: Optional[int] = Form(None),
                  photo_right: Optional[UploadFile] = File(None, description="Optional photo of the right side"),
                  photo_back: Optional[UploadFile] = File(None, description="Optional photo of the back"),
                  photo_left: Optional[UploadFile] = File(None, description="Optional photo of the left side")):
    """Upload a building photo (night or day) and its address. Photos of the other sides are optional. Night photo: lit windows are detected.
    Day photo: the AI counts floors and windows and a typical night is simulated.
    Pass corners + floors + cols to use the grid fallback instead of automatic detection."""
    data = await photo.read()
    building = (building or "Building").strip()[:80] or "Building"
    location = None
    if address and address.strip():
        location = await _locate(address)
    pts = None
    if corners:
        try:
            pts = json.loads(corners)
        except json.JSONDecodeError:
            raise HTTPException(400, "corners must be JSON like [[10,20],[500,20],[500,700],[10,700]]")
        if not floors or not cols:
            raise HTTPException(400, "Grid fallback needs floors and cols too")
    try:
        sides = {face: await f.read() for face, f in
                 (("right", photo_right), ("back", photo_back), ("left", photo_left)) if f is not None}
        b = await asyncio.to_thread(_analyze, building, data, threshold, pts, floors, cols, location, sides)
    except ValueError as exc:
        raise HTTPException(400, f"{exc}. Please use a JPG or PNG photo.")
    await hub.broadcast({"type": "building"} | b.summary())
    cond = _cond_or_none(b)
    return b.summary() | {"risk": risk.building_risk(b.windows, cond) if cond else None,
                          "conditions": cond.model_dump() if cond else None}


async def _locate(address: str) -> dict:
    """Address -> {address, lat, lon, place, matched}, or HTTP 422 if nobody can find it."""
    hit = await asyncio.to_thread(geo.geocode, address)
    if not hit:
        raise HTTPException(422, f"Couldn't find \"{address.strip()}\". Try adding the city and state or country.")
    return {"address": address.strip()} | hit


@app.post("/api/location")
async def set_location(req: LocationRequest):
    """Set (or change) a building's address. Its local forecast is used from then on."""
    b = _get_building(req.building)
    b.location = await _locate(req.address)
    cond = _cond(b)
    b.windows = risk.score_windows(b.windows, cond)
    b.original = risk.score_windows(b.original, cond)
    await hub.broadcast({"type": "building"} | b.summary())
    await hub.broadcast({"type": "conditions"} | cond.model_dump())
    return {"location": b.location, "conditions": cond.model_dump(), "risk": risk.building_risk(b.windows, cond)}


@app.post("/api/decide")
async def decide(req: DecideRequest):
    """Ask the AI which windows to turn off or dim. Sends the commands to the twin pages."""
    b = _get_building(req.building)
    if req.windows:
        b.windows = req.windows
    cond = _cond(b)
    risk_now = {w.id: w.risk for w in risk.score_windows(b.windows, cond)}  # risk before the change
    result = await asyncio.to_thread(decider.decide, b.windows, cond, b.photo)
    b.windows = result["windows"]

    if b.photo:
        img = detection.load_image(b.photo)
        folder = config.OUTPUT_DIR / _slug(b.name)
        await asyncio.to_thread(detection.save_after_image, img, b.windows, folder / "after.jpg")
        await asyncio.to_thread(detection.save_debug_image, img, b.windows, folder / "debug_after.jpg")
        b.after_url = f"/output/{_slug(b.name)}/after.jpg"

    by_id = {w.id: w for w in b.windows}
    actions = sorted(result["actions"], key=lambda a: (-by_id[a.id].floor, by_id[a.id].col))
    asyncio.create_task(asyncio.to_thread(
        db.log_rows, b.name, [(a.id, risk_now.get(a.id, 0.0), a.state) for a in actions], "decision"))

    payload = {
        "building": b.name, "actions": [a.model_dump() for a in actions],
        "risk_before": result["risk_before"], "risk_after": result["risk_after"],
        "reason": result["reason"], "source": result["source"], "conditions": cond.model_dump(),
        "windows": [w.model_dump() for w in b.windows],
        "energy_saved_kwh": result["energy_saved_kwh"], "money_saved_usd": result["money_saved_usd"],
        "rule": result["rule"], "estimate": result["estimate"],
        "photo_url": b.photo_url, "after_url": b.after_url,
    }
    state.last_decision = payload
    await hub.broadcast({"type": "decision"} | {k: v for k, v in payload.items() if k != "windows"})
    if req.apply:
        asyncio.create_task(hub.send_commands([a.model_dump() for a in actions]))
    return payload


@app.post("/api/reset")
async def reset(building: Optional[str] = Form(None)):
    """Turn every window back to how it was in the photo (to run the demo again)."""
    b = _get_building(building)
    b.windows = [w.model_copy() for w in b.original]
    b.after_url = ""
    state.last_decision = None
    await hub.broadcast({"type": "building"} | b.summary())
    return b.summary()


@app.post("/api/simulate")
async def simulate(req: SimulateRequest):
    """Switch the scenario: clear, foggy_migration, or live (real weather)."""
    scenarios.set_scenario(req.scenario)
    cond = _cond()
    if state.current:
        b = state.building()
        b.windows = risk.score_windows(b.windows, cond)
    await hub.broadcast({"type": "conditions"} | cond.model_dump())
    return cond


@app.post("/api/alert", response_class=Response,
          responses={200: {"content": {"audio/mpeg": {}}}})
async def alert(req: AlertRequest):
    """Turns the AI's reason into speech with ElevenLabs. Returns an mp3 clip.
    503 if ElevenLabs is not set up or fails (the page then uses the browser's voice)."""
    try:
        audio = await asyncio.to_thread(voice.text_to_speech, req.text)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except voice.VoiceUnavailable as exc:
        raise HTTPException(503, str(exc))
    return Response(content=audio, media_type="audio/mpeg")


@app.get("/api/decision")
def last_decision():
    return state.last_decision or {}


@app.get("/api/log")
def event_log(limit: int = 50):
    """Latest rows from Tiger Data (empty if logging is off)."""
    return {"enabled": db.enabled(), "rows": db.recent(limit)}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """Twin pages connect here.
    Server -> page:  {"type": "building", ...windows}  then commands {"id": 12, "state": "off"}
    Page -> server:  {"id": 12, "state": "off", "ok": true}
    LED boards connect to /ws?device=led&floors=5&cols=6 and get compact LED messages (see led.py)."""
    q = ws.query_params
    led = None
    if q.get("device") == "led":
        try:
            led = LedView(floors=int(q.get("floors", 5)), cols=int(q.get("cols", 6)))
        except ValueError:
            led = LedView(floors=5, cols=6)
    await hub.connect(ws, led)
    try:
        if state.current:
            await hub.send_to(ws, {"type": "building"} | state.building().summary())
        while True:
            try:
                msg = json.loads(await ws.receive_text())
            except json.JSONDecodeError:
                continue
            if isinstance(msg, dict) and "id" in msg and (msg.get("ok") or msg.get("done")):
                wid, st = int(msg["id"]), msg.get("state")
                hub.confirmed[wid] = st
                b = state.buildings.get(state.current)
                cond = _cond_or_none(b) if b else None
                scored = risk.score_windows(b.original, cond) if cond else []
                r = next((x.risk for x in scored if x.id == wid), 0.0)
                asyncio.create_task(asyncio.to_thread(
                    db.log_rows, state.current, [(wid, r, st)], "confirmed"))
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(ws)


# Serve Sakshi's pages at http://localhost:8000/ for local testing (on Vultr, Caddy serves them).
# Mounted last so every /api, /ws, /output and /docs route above wins.
FRONTEND_DIR = config.REPO_ROOT / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
