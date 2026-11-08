"""Shared data formats. These match "How our parts connect" in the team plan."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

State = Literal["on", "dim", "off"]
MigrationLevel = Literal["low", "medium", "high"]


class Window(BaseModel):
    """{"id": 12, "floor": 3, "col": 5, "x": 410, "y": 220, "w": 38, "h": 52,
        "state": "on", "brightness": 0.82, "color": "white", "risk": 0.74}"""
    id: int
    floor: int
    col: int
    x: int
    y: int
    w: int
    h: int
    state: State = "on"
    brightness: float = Field(ge=0, le=1)
    color: str = "white"
    risk: float = Field(default=0.0, ge=0, le=1)
    face: str = "front"  # which side of the building: front, right, back or left


class Conditions(BaseModel):
    time: str
    location: str = ""
    summary: str = ""
    sky_cover: int = Field(default=0, ge=0, le=100)  # percent
    fog: bool = False
    rain: bool = False
    wind_dir: str = ""  # e.g. "NW"
    wind_speed_mph: float = 0
    migration_level: MigrationLevel = "medium"
    migration_estimated: bool = True
    sky_danger: float = Field(default=0.5, ge=0, le=1)
    scenario: str = "live"  # "live", "clear" or "foggy_migration"
    source: str = ""        # where the forecast came from, e.g. "U.S. National Weather Service"
    source_url: str = ""    # human-readable forecast page for that location
    updated: str = ""       # when the source last updated the forecast (ISO time)
    # Migration estimate details (BirdCast method on NOAA GFS) and live eBird evidence
    migration_index: Optional[float] = None
    migration_factors: list[dict] = []
    migration_source: str = ""
    birdcast_url: str = ""
    ebird: Optional[dict] = None


class Command(BaseModel):
    """Backend -> twin page: {"id": 12, "state": "off"}"""
    id: int
    state: State


class Action(BaseModel):
    id: int
    state: State


class DecideRequest(BaseModel):
    building: Optional[str] = None
    windows: Optional[list[Window]] = None  # defaults to the last analyzed building
    apply: bool = True  # send the commands to connected twin pages


class Decision(BaseModel):
    building: str
    actions: list[Action]
    risk_before: float
    risk_after: float
    reason: str
    source: Literal["gemini", "bullsai", "fallback"]
    conditions: Conditions
    windows: list[Window]
    energy_saved_kwh: float
    money_saved_usd: float


class SimulateRequest(BaseModel):
    scenario: Literal["live", "clear", "foggy_migration"]


class LocationRequest(BaseModel):
    address: str
    building: Optional[str] = None  # default: the current building


class AlertRequest(BaseModel):
    text: str
