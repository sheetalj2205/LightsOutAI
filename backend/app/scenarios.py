"""Demo presets that override live conditions (Task 7)."""
from datetime import datetime

from . import weather
from .models import Conditions

PRESETS = {
    "clear": {
        "summary": "Clear sky, light south wind. Few birds flying.",
        "sky_cover": 5, "fog": False, "rain": False,
        "wind_dir": "S", "wind_speed_mph": 6,
        "migration_level": "low", "sky_danger": 0.15,
    },
    "foggy_migration": {
        "summary": "Fog and low clouds, steady NW wind. Heavy migration night.",
        "sky_cover": 95, "fog": True, "rain": False,
        "wind_dir": "NW", "wind_speed_mph": 14,
        "migration_level": "high", "sky_danger": 0.9,
    },
}

_active = "live"


def set_scenario(name: str) -> None:
    global _active
    if name != "live" and name not in PRESETS:
        raise ValueError(f"unknown scenario: {name}")
    _active = name


def active_scenario() -> str:
    return _active


def current_conditions() -> Conditions:
    """Live conditions from the weather module, unless a demo scenario is active."""
    try:
        live = weather.get_conditions()
    except Exception as exc:  # weather API down -> fall back to a neutral night
        live = {"summary": f"Weather unavailable ({exc.__class__.__name__})"}
    data = {"time": datetime.now().isoformat(timespec="minutes"), **live}
    if _active != "live":
        data.update(PRESETS[_active])
    data["scenario"] = _active
    return Conditions(**data)
