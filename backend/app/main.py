"""Lights Out AI backend. Run from the backend/ folder:

    .venv/bin/uvicorn app.main:app --reload --port 8000

Then open http://localhost:8000/docs to try every endpoint.
"""
import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from typing import Optional

import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from . import config, db, decide as decider, detection, risk, scenarios, voice
from .demo import make_demo_photo
from .led import LedView
from .models import AlertRequest, DecideRequest, SimulateRequest
from .state import Building, hub, state

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("lightsout")

DEMO_NAME = "Demo Hall"


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "building"


def _analyze(name: str, photo: bytes, threshold: int, corners=None, floors=None, cols=None) -> Building:
    img = detection.load_image(photo)
    if corners:
        windows = detection.detect_grid(img, corners, floors, cols)
        method = "grid"
    else:
        windows = detection.detect_windows(img, threshold)
        method = "detect"
    windows = risk.score_windows(windows, scenarios.current_conditions())

    folder = config.OUTPUT_DIR / _slug(name)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "photo.jpg").write_bytes(photo)
    detection.save_debug_image(img, windows, folder / "debug.jpg")
    base = f"/output/{_slug(name)}"
    b = Building(name=name, windows=windows, photo=photo, image_size=(img.shape[1], img.shape[0]),
                 photo_url=f"{base}/photo.jpg", debug_url=f"{base}/debug.jpg", method=method,
                 original=[w.model_copy() for w in windows])
    state.buildings[name] = b
    state.current = name
    return b


def _load_saved_results() -> None:
    """Load buildings saved by scripts/run_photos.py (Task 8) so the demo starts ready."""
    for f in sorted(config.OUTPUT_DIR.glob("*/result.json")):
        try:
            data = json.loads(f.read_text())
            photo = (f.parent / "photo.jpg").read_bytes()
            _analyze(data["building"], photo, data.get("threshold", config.DETECT_THRESHOLD),
                     data.get("corners"), data.get("floors"), data.get("cols"))
            log.info("loaded saved building %s", data["building"])
        except Exception as exc:
            log.warning("could not load %s: %s", f, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(db.init)
    _analyze(DEMO_NAME, make_demo_photo(), threshold=150)
    _load_saved_results()
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
    return scenarios.current_conditions()


@app.get("/api/buildings")
def buildings():
    return {"current": state.current,
            "buildings": [{"building": b.name, "windows": len(b.windows), "photo_url": b.photo_url,
                           "method": b.method} for b in state.buildings.values()]}


@app.get("/api/windows")
def windows(building: Optional[str] = None):
    """Current window list of a building (default: the current one), for the twin page."""
    b = _get_building(building)
    cond = scenarios.current_conditions()
    return b.summary() | {"risk": risk.building_risk(b.windows, cond)}


@app.post("/api/select")
async def select_building(building: str = Form(...)):
    """Make a building the current one and show it on every twin page."""
    b = _get_building(building)
    state.current = b.name
    await hub.broadcast({"type": "building"} | b.summary())
    return b.summary()


@app.post("/api/analyze")
async def analyze(photo: UploadFile = File(...), building: str = Form("Building"),
                  threshold: int = Form(config.DETECT_THRESHOLD),
                  corners: Optional[str] = Form(None, description='Grid fallback: [[x,y] x4] TL,TR,BR,BL'),
                  floors: Optional[int] = Form(None), cols: Optional[int] = Form(None)):
    """Upload a night photo. Returns every detected window with position, brightness, color and risk.
    Pass corners + floors + cols to use the grid fallback instead of automatic detection."""
    data = await photo.read()
    pts = None
    if corners:
        try:
            pts = json.loads(corners)
        except json.JSONDecodeError:
            raise HTTPException(400, "corners must be JSON like [[10,20],[500,20],[500,700],[10,700]]")
        if not floors or not cols:
            raise HTTPException(400, "Grid fallback needs floors and cols too")
    try:
        b = await asyncio.to_thread(_analyze, building, data, threshold, pts, floors, cols)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await hub.broadcast({"type": "building"} | b.summary())
    cond = scenarios.current_conditions()
    return b.summary() | {"risk": risk.building_risk(b.windows, cond), "conditions": cond.model_dump()}


@app.post("/api/decide")
async def decide(req: DecideRequest):
    """Ask the AI which windows to turn off or dim. Sends the commands to the twin pages."""
    b = _get_building(req.building)
    if req.windows:
        b.windows = req.windows
    cond = scenarios.current_conditions()
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
    cond = scenarios.current_conditions()
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
                scored = risk.score_windows(b.original, scenarios.current_conditions()) if b else []
                r = next((x.risk for x in scored if x.id == wid), 0.0)
                asyncio.create_task(asyncio.to_thread(
                    db.log_rows, state.current, [(wid, r, st)], "confirmed"))
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(ws)
