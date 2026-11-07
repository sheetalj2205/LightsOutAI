"""In-memory state: analyzed buildings and connected twin pages."""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from fastapi import WebSocket

from .led import LedView
from .models import Window

log = logging.getLogger("lightsout.ws")


@dataclass
class Building:
    name: str
    windows: list[Window]
    photo: Optional[bytes] = None
    image_size: tuple[int, int] = (0, 0)  # (width, height)
    photo_url: str = ""
    debug_url: str = ""
    after_url: str = ""
    method: str = "detect"
    original: list[Window] = field(default_factory=list)  # as detected, for "reset"
    location: Optional[dict] = None  # {address, lat, lon, place}; None until the user gives an address
    lights: str = "detected"         # "detected" (night photo) or "simulated" (day photo)

    def summary(self) -> dict:
        return {
            "building": self.name,
            "floors": max((w.floor for w in self.windows), default=0),
            "cols": max((w.col for w in self.windows), default=0),
            "image_width": self.image_size[0], "image_height": self.image_size[1],
            "photo_url": self.photo_url, "debug_url": self.debug_url, "after_url": self.after_url,
            "method": self.method, "lights": self.lights,
            "location": self.location,
            "windows": [w.model_dump() for w in self.windows],
        }


@dataclass
class AppState:
    buildings: dict[str, Building] = field(default_factory=dict)
    current: str = ""
    last_decision: Optional[dict] = None

    def building(self, name: Optional[str] = None) -> Building:
        key = name or self.current
        if key not in self.buildings:
            raise KeyError(key)
        return self.buildings[key]


class TwinHub:
    """Keeps the list of connected twin/dashboard pages and sends window commands."""

    def __init__(self) -> None:
        self.clients: dict[WebSocket, Optional[LedView]] = {}  # LedView for LED boards, None for pages
        self.confirmed: dict[int, str] = {}  # window id -> state the twin page confirmed

    async def connect(self, ws: WebSocket, led: Optional[LedView] = None) -> None:
        await ws.accept()
        self.clients[ws] = led
        log.info("%s connected (%d total)", "LED board" if led else "twin page", len(self.clients))

    def disconnect(self, ws: WebSocket) -> None:
        if self.clients.pop(ws, None) is not None:
            log.info("LED board left")
        log.info("client left (%d total)", len(self.clients))

    def led_boards(self) -> int:
        return sum(1 for v in self.clients.values() if v is not None)

    async def send_to(self, ws: WebSocket, message: dict) -> None:
        view = self.clients.get(ws)
        out = view.translate(message) if view is not None else [message]
        for m in out:
            await ws.send_text(json.dumps(m))

    async def broadcast(self, message: dict) -> None:
        for ws in list(self.clients):
            try:
                await self.send_to(ws, message)
            except Exception:
                self.disconnect(ws)

    async def send_commands(self, commands: list[dict], delay: float = 0.08) -> None:
        """Send {"id", "state"} one by one with a short gap, so windows go dark in a
        visible wave on the twin page (looks good on stage)."""
        for cmd in commands:
            await self.broadcast(cmd)
            if delay:
                await asyncio.sleep(delay)


state = AppState()
hub = TwinHub()
