"""Tonight's bird-migration estimate for a location, following the factors in the BirdCast
forecast model (Van Doren & Horton, Science 2018): season, tailwind, temperature change,
pressure change and precipitation. Weather comes from NOAA's GFS model (the model BirdCast
forecasts use), served by Open-Meteo (free, no key).

This is an estimate from weather, not a radar measurement. BirdCast is linked for comparison.
"""
import json
import logging
import math
import urllib.request
from datetime import datetime, timezone

log = logging.getLogger("lightsout.migration")

SOURCE = "Weather-based estimate (BirdCast method) · NOAA GFS via Open-Meteo"
BIRDCAST_URL = "https://dashboard.birdcast.org/"
UA = {"User-Agent": "LightsOutAI-UBHacking (student project)"}

FALL_PEAK, FALL_SD = 280, 28      # day of year ~ Oct 7 (northern hemisphere)
SPRING_PEAK, SPRING_SD = 128, 20  # ~ May 8


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def _sig(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _gauss(x: float, mu: float, sd: float) -> float:
    return math.exp(-0.5 * ((x - mu) / sd) ** 2)


def season_strength(day: int, lat: float) -> tuple[float, str]:
    """0-1 how deep into a migration season this date is, and which season."""
    if lat < 0:  # southern hemisphere: seasons flip
        day = (day + 182) % 365
    fall, spring = _gauss(day, FALL_PEAK, FALL_SD), _gauss(day, SPRING_PEAK, SPRING_SD)
    return (fall, "fall") if fall >= spring else (spring, "spring")


def score(day: int, lat: float, wind_from_deg: float, wind_mph: float,
          temp_change_c: float, pressure_change_hpa: float, rain_mm: float) -> dict:
    """Combine the factors into a 0-1 migration index, a level and readable 'why' chips."""
    season, which = season_strength(day, lat)
    toward_south = math.cos(math.radians(wind_from_deg))  # wind FROM north blows birds south
    tail_mph = (toward_south if which == "fall" else -toward_south) * wind_mph
    if lat < 0:
        tail_mph = -tail_mph
    tail = _sig(tail_mph / 6)
    temp = _sig((-temp_change_c if which == "fall" else temp_change_c) / 2.5)
    press = _sig((pressure_change_hpa if which == "fall" else -pressure_change_hpa) / 2.5)
    rain = 0.25 if rain_mm >= 1 else 0.6 if rain_mm >= 0.2 else 1.0

    weather = 0.45 * tail + 0.3 * temp + 0.25 * press
    index = max(0.0, min(1.0, (0.15 + 0.85 * season) * weather * rain * 1.5))
    level = "high" if index >= 0.5 else "medium" if index >= 0.25 else "low"

    compass = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((wind_from_deg + 22.5) // 45) % 8]
    up, down = "up", "down"
    factors = [
        {"label": f"{'Peak' if season > 0.7 else 'Mid' if season > 0.35 else 'Late/early'} {which} season",
         "effect": up if season > 0.5 else down},
        {"label": f"{compass} wind {round(wind_mph)} mph · " + ("tailwind" if tail_mph > 2 else "headwind" if tail_mph < -2 else "light wind"),
         "effect": up if tail_mph > 2 else down if tail_mph < -2 else "neutral"},
        {"label": "Temperature steady" if abs(temp_change_c) < 1 else
                  f"Temperature {'falling' if temp_change_c < 0 else 'rising'} {abs(temp_change_c):.0f}°C in 24 h",
         "effect": up if temp > 0.6 else down if temp < 0.4 else "neutral"},
        {"label": "Pressure steady" if abs(pressure_change_hpa) < 1 else
                  f"Pressure {'rising' if pressure_change_hpa > 0 else 'falling'} {abs(pressure_change_hpa):.0f} hPa",
         "effect": up if press > 0.6 else down if press < 0.4 else "neutral"},
        {"label": "Rain tonight" if rain < 1 else "No rain tonight", "effect": down if rain < 1 else up},
    ]
    return {"migration_level": level, "migration_index": round(index, 2), "migration_factors": factors}


def estimate(lat: float, lon: float) -> dict:
    """Tonight's migration for a location; raises if the weather model can't be reached."""
    q = (f"https://api.open-meteo.com/v1/forecast?latitude={lat:.4f}&longitude={lon:.4f}"
         "&hourly=temperature_2m,pressure_msl,wind_speed_10m,wind_direction_10m,precipitation,is_day"
         "&wind_speed_unit=mph&past_days=1&forecast_days=2&timezone=UTC&models=gfs_seamless")
    h = _get(q)["hourly"]
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in h["time"]]
    # Tonight's first dark hour, then ~3 h after sunset (when BirdCast's forecasts apply).
    dark = [i for i, t in enumerate(times) if t >= now and not h["is_day"][i]]
    if not dark:
        raise ValueError("no night hours in the forecast")
    i = min(dark[0] + 3, len(times) - 1)
    j = max(0, i - 24)
    rain = sum((h["precipitation"][k] or 0) for k in range(dark[0], min(dark[0] + 8, len(times))))
    out = score(
        day=times[i].timetuple().tm_yday, lat=lat,
        wind_from_deg=h["wind_direction_10m"][i] or 0, wind_mph=h["wind_speed_10m"][i] or 0,
        temp_change_c=(h["temperature_2m"][i] or 0) - (h["temperature_2m"][j] or 0),
        pressure_change_hpa=(h["pressure_msl"][i] or 0) - (h["pressure_msl"][j] or 0),
        rain_mm=rain,
    )
    return out | {"migration_source": SOURCE, "birdcast_url": BIRDCAST_URL}
