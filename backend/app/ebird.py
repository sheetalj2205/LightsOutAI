"""Live evidence from eBird (Cornell Lab of Ornithology): which night-migrating birds people
reported near the building in the last few days. Free API key: https://ebird.org/api/keygen"""
import logging
import time
from typing import Optional

import httpx

from . import config

log = logging.getLogger("lightsout.ebird")
SOURCE = "eBird (Cornell Lab of Ornithology)"
RADIUS_KM, DAYS = 25, 3
CACHE_SECONDS = 3600
_cache: dict[tuple, tuple[float, dict]] = {}

# Groups that mostly migrate at night (and hit lit buildings): matched on the common name.
NIGHT_MIGRANTS = ("warbler", "thrush", "veery", "vireo", "sparrow", "tanager", "grosbeak", "bunting",
                  "flycatcher", "pewee", "kinglet", "wren", "catbird", "oriole", "bobolink", "cuckoo",
                  "rail", "sora", "sandpiper", "yellowlegs", "dowitcher", "plover", "woodcock", "snipe",
                  "junco", "redstart", "ovenbird", "waterthrush", "yellowthroat", "chat", "creeper",
                  "nuthatch", "brown thrasher", "towhee", "dickcissel", "nighthawk", "whip-poor-will")


def _is_night_migrant(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in NIGHT_MIGRANTS)


def summarize(observations: list[dict]) -> dict:
    species = {o.get("comName", "") for o in observations if o.get("comName")}
    migrants = sorted(s for s in species if _is_night_migrant(s))
    return {"species_total": len(species), "migrant_species": len(migrants), "examples": migrants[:5],
            "radius_km": RADIUS_KM, "days": DAYS, "source": SOURCE, "url": "https://ebird.org/explore"}


def recent(lat: float, lon: float) -> Optional[dict]:
    """Night-migrant species reported nearby, or None without a key / if eBird is unreachable."""
    if not config.EBIRD_API_KEY:
        return None
    key = (round(lat, 2), round(lon, 2))
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    try:
        r = httpx.get("https://api.ebird.org/v2/data/obs/geo/recent",
                      params={"lat": f"{lat:.4f}", "lng": f"{lon:.4f}", "dist": RADIUS_KM, "back": DAYS},
                      headers={"X-eBirdApiToken": config.EBIRD_API_KEY}, timeout=8)
        r.raise_for_status()
        out = summarize(r.json())
    except Exception as exc:
        log.warning("eBird unavailable: %s", str(exc)[:160])
        return None
    _cache[key] = (time.monotonic(), out)
    return out
