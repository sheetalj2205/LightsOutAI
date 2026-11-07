"""Real weather + migration module for Lights Out AI.
 
Gets tonight's hourly forecast for Buffalo from the National Weather Service
(api.weather.gov, free, no key) and estimates bird migration level and sky danger.
 
Contract: get_conditions() returns a dict with these keys (see models.Conditions):
    time, location, summary, sky_cover (0-100), fog, rain, wind_dir, wind_speed_mph,
    migration_level ("low"/"medium"/"high"), migration_estimated (True), sky_danger (0-1)
 
If the NWS API fails, it returns safe fallback values so the demo never breaks.
"""
import json
import re
import urllib.request
from datetime import datetime, timezone
 
# UB North Campus, Buffalo NY
LAT, LON = 43.0008, -78.7890
 
# NWS asks every client to send a User-Agent
HEADERS = {"User-Agent": "LightsOutAI-UBHacking (student project)",
           "Accept": "application/geo+json"}
 
RAIN_WORDS = ("rain", "drizzle", "showers", "snow", "storm", "sleet")
 
 
def _fallback() -> dict:
    return {
        "time": datetime.now().isoformat(timespec="minutes"),
        "location": "Buffalo, NY",
        "summary": "Weather unavailable, using default night (fallback)",
        "sky_cover": 50,
        "fog": False,
        "rain": False,
        "wind_dir": "NW",
        "wind_speed_mph": 10,
        "migration_level": "medium",
        "migration_estimated": True,
        "sky_danger": 0.5,
    }
 
 
def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())
 
 
def _wind_mph(text: str) -> int:
    """'5 to 10 mph' -> 10, '8 mph' -> 8"""
    nums = [int(n) for n in re.findall(r"\d+", text or "")]
    return max(nums) if nums else 0
 
 
def _sky_cover_map(grid_url: str) -> dict:
    """Sky cover % by start time from the raw grid data. Empty if it fails."""
    try:
        values = _get(grid_url)["properties"]["skyCover"]["values"]
    except Exception:
        return {}
    # validTime looks like "2026-11-07T23:00:00+00:00/PT3H"
    return {datetime.fromisoformat(v["validTime"].split("/")[0]): v["value"] for v in values}
 
 
def _cover_at(cover_map: dict, t: datetime, summary: str) -> int:
    """Sky cover at time t. If the grid data is missing, guess from the summary."""
    starts = [s for s in cover_map if s <= t]
    if starts:
        return int(cover_map[max(starts)])
    s = summary.lower()
    if "fog" in s or "overcast" in s:
        return 95
    if "mostly cloudy" in s or "cloudy" in s or any(w in s for w in RAIN_WORDS):
        return 80
    if "partly" in s:
        return 45
    return 10
 
 
def _migration_score(month: int, wind_dir: str, wind_mph: int, rain: bool) -> float:
    """Estimated migration, 0 to 1.
    Fall: birds fly south, so north winds (tailwinds) push more birds.
    Spring: birds fly north, so south winds push more birds.
    Rain grounds most birds.
    """
    if month in (4, 5, 9, 10):
        season = 1.0          # peak spring / fall
    elif month in (3, 6, 8, 11):
        season = 0.7          # shoulder months
    else:
        season = 0.2          # winter / mid summer
 
    fall = month >= 7
    good = ("N", "NW", "NE", "NNW", "NNE") if fall else ("S", "SW", "SE", "SSW", "SSE")
    wind = 1.0 if wind_dir in good else 0.5
    if wind_mph > 25:
        wind *= 0.6           # very strong winds slow migration
 
    score = season * wind
    if rain:
        score *= 0.3
    return min(score, 1.0)
 
 
def _sky_danger(summary: str, sky_cover: int) -> float:
    """Sky danger, 0 to 1. Fog and low clouds make birds fly lower,
    where lit windows pull them in."""
    s = summary.lower()
    if "fog" in s:
        danger = 0.95
    elif any(w in s for w in RAIN_WORDS):
        danger = 0.7
    elif "overcast" in s or "cloudy" in s:
        danger = 0.6
    elif "partly" in s:
        danger = 0.35
    else:
        danger = 0.15         # clear
    danger = 0.7 * danger + 0.3 * (sky_cover / 100)
    return round(min(danger, 1.0), 2)
 
 
def _level(score: float) -> str:
    if score >= 0.65:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"
 
 
def get_conditions() -> dict:
    try:
        point = _get(f"https://api.weather.gov/points/{LAT},{LON}")["properties"]
        periods = _get(point["forecastHourly"])["properties"]["periods"]
        cover_map = _sky_cover_map(point["forecastGridData"])
    except Exception:
        return _fallback()
 
    now = datetime.now(timezone.utc)
    # Tonight = the next night-time hours (up to 12)
    night = [p for p in periods
             if not p["isDaytime"] and datetime.fromisoformat(p["endTime"]) > now][:12]
    if not night:
        return _fallback()
 
    hours = []
    for p in night:
        t = datetime.fromisoformat(p["startTime"])
        summary = p.get("shortForecast", "")
        rain = any(w in summary.lower() for w in RAIN_WORDS)
        mph = _wind_mph(p.get("windSpeed"))
        cover = _cover_at(cover_map, t, summary)
        hours.append({
            "summary": summary,
            "sky_cover": cover,
            "fog": "fog" in summary.lower(),
            "rain": rain,
            "wind_dir": p.get("windDirection") or "",
            "wind_speed_mph": mph,
            "migration": _migration_score(t.month, p.get("windDirection") or "", mph, rain),
            "danger": _sky_danger(summary, cover),
        })
 
    # Show the riskiest hour of the night; migration is the night's average
    worst = max(hours, key=lambda h: h["migration"] * h["danger"])
    migration = sum(h["migration"] for h in hours) / len(hours)
 
    return {
        "time": datetime.now().isoformat(timespec="minutes"),
        "location": "Buffalo, NY",
        "summary": f"{worst['summary']}, {worst['wind_dir']} wind {worst['wind_speed_mph']} mph",
        "sky_cover": worst["sky_cover"],
        "fog": worst["fog"],
        "rain": worst["rain"],
        "wind_dir": worst["wind_dir"],
        "wind_speed_mph": worst["wind_speed_mph"],
        "migration_level": _level(migration),
        "migration_estimated": True,
        "sky_danger": max(h["danger"] for h in hours),
    }
 
 
if __name__ == "__main__":
    print(json.dumps(get_conditions(), indent=2))
 