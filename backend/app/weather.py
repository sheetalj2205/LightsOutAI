"""PLACEHOLDER — Sakshi replaces this file with the real weather + migration module.

Contract: get_conditions() returns a dict with these keys (see models.Conditions):
    time, location, summary, sky_cover (0-100), fog, rain, wind_dir, wind_speed_mph,
    migration_level ("low"/"medium"/"high"), migration_estimated (True), sky_danger (0-1)

Until then it returns fixed fake values so everything else works.
"""
from datetime import datetime


def get_conditions() -> dict:
    return {
        "time": datetime.now().isoformat(timespec="minutes"),
        "location": "Buffalo, NY",
        "summary": "Partly cloudy, light NW wind (fake data)",
        "sky_cover": 45,
        "fog": False,
        "rain": False,
        "wind_dir": "NW",
        "wind_speed_mph": 9,
        "migration_level": "medium",
        "migration_estimated": True,
        "sky_danger": 0.45,
    }
