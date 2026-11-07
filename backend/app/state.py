"""In-memory state: analyzed buildings and connected twin pages."""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from fastapi import WebSocket

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

    def summary(self) -> dict:
        return {
            "building": self.name,
            "floors": max((w.floor for w in self.windows), default=0),
            "cols": max((w.col for w in self.windows), default=0),
            "image_width": self.image_size[0], "image_height": self.image_size[1],
            "photo_url": self.photo_url, "debug_url": self.debug_url, "after_url": self.after_url,
            "method": self.method,
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
        self.clients: set[WebSocket] = set()
        self.confirmed: dict[int, str] = {}  # window id -> state the twin page confirmed

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)
        log.info("twin page connected (%d total)", len(self.clients))

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)
        log.info("twin page left (%d total)", len(self.clients))

    async def broadcast(self, message: dict) -> None:
        text = json.dumps(message)
        for ws in list(self.clients):
            try:
                await ws.send_text(text)
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
