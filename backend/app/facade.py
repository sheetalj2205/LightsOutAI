"""Buildings from any photo (night or day).

read_facade(photo)   Gemini counts floors and windows per floor and finds the facade corners.
simulate_windows()   builds the window grid from that, with a typical night's lights (~70 % on).
"""
import hashlib
import json
import logging
import random
from typing import Optional

import cv2
import numpy as np

from . import config
from .detection import grid_cells
from .models import Window

log = logging.getLogger("lightsout.facade")
MAX_FLOORS, MAX_COLS = 60, 40

PROMPT = """Look at this photo of a building. Focus on the main facade facing the camera.
Count its floors (stories above ground) and the number of window columns on one floor of that facade.
Give the facade's 4 corners as fractions (0-1) of the image width and height, in this order:
top-left, top-right, bottom-right, bottom-left. Say whether the photo was taken at night.
Reply with JSON only:
{"floors": <int>, "windows_per_floor": <int>, "corners": [[x,y],[x,y],[x,y],[x,y]], "is_night": <bool>}"""


def is_daylight(img: np.ndarray) -> bool:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(gray.mean()) > 85


def _parse(text: str) -> dict:
    text = text.strip()
    if not text.startswith("{"):
        text = text[text.find("{"): text.rfind("}") + 1]
    data = json.loads(text)
    floors = int(data["floors"])
    cols = int(data.get("windows_per_floor") or data.get("cols"))
    if not (1 <= floors <= 200 and 1 <= cols <= 200):
        raise ValueError(f"implausible grid {floors}x{cols}")
    corners = data.get("corners")
    if corners and (len(corners) != 4 or not all(0 <= float(v) <= 1 for p in corners for v in p)):
        corners = None
    return {"floors": min(floors, MAX_FLOORS), "cols": min(cols, MAX_COLS),
            "corners": corners, "is_night": bool(data.get("is_night", False))}


def read_facade(photo: bytes) -> Optional[dict]:
    """{floors, cols, corners (fractions) | None, is_night} from Gemini, or None if unavailable."""
    if not config.GEMINI_API_KEY:
        return None
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=20_000))
    resp = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=[types.Part.from_bytes(data=photo, mime_type="image/jpeg"), PROMPT],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    )
    info = _parse(resp.text)
    log.info("facade read by Gemini: %s floors x %s cols", info["floors"], info["cols"])
    return info


def simulate_windows(img: np.ndarray, floors: int, cols: int, corners_px=None, seed: str = "") -> list[Window]:
    """Grid of windows over the facade with a typical night: ~70 % lit, lobby always lit."""
    floors, cols = max(1, min(floors, MAX_FLOORS)), max(1, min(cols, MAX_COLS))
    h, w = img.shape[:2]
    if not corners_px:
        mx, my = w * 0.06, h * 0.06
        corners_px = [[mx, my], [w - mx, my], [w - mx, h - my], [mx, h - my]]
    rnd = random.Random(hashlib.sha1(seed.encode()).hexdigest() if seed else 7)
    out = []
    for cell in grid_cells(img, corners_px, floors, cols):
        f = cell["floor"]
        lit = f == 1 or rnd.random() < 0.7
        out.append(Window(
            id=0, floor=f, col=cell["col"], x=cell["x"], y=cell["y"], w=cell["w"], h=cell["h"],
            state="on" if lit else "off",
            brightness=round(rnd.uniform(0.72, 0.95), 3) if lit else 0.1,
            color="white" if rnd.random() < 0.6 else "yellow",
        ))
    out.sort(key=lambda win: (win.floor, win.col))
    return [win.model_copy(update={"id": i}) for i, win in enumerate(out, start=1)]


def guess_grid(img: np.ndarray) -> tuple[int, int]:
    """Rough floors x windows-per-floor from the photo's shape, when nothing else worked."""
    h, w = img.shape[:2]
    floors = max(3, min(12, round(6 * h / w)))  # taller photo -> more floors
    cols = max(3, min(14, round(7 * w / h)))     # wider photo -> more windows per floor
    return floors, cols
