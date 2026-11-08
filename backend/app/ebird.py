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

# Species that migrate at night through the Great Lakes / Northeast and are known building-collision
# victims. Year-round residents with similar names (Carolina Wren, House Sparrow, Song Sparrow,
# White-breasted Nuthatch, American Robin) are left out on purpose.
# Every wood-warbler, vireo and flycatcher here migrates at night, so those are matched by family name.
NIGHT_MIGRANT_FAMILIES = ("Warbler", "Vireo", "Flycatcher")
NIGHT_MIGRANTS = frozenset({
    # thrushes
    "Hermit Thrush", "Swainson's Thrush", "Gray-cheeked Thrush", "Bicknell's Thrush", "Wood Thrush", "Veery",
    # wood-warblers without "Warbler" in the name
    "Ovenbird", "Northern Waterthrush", "Louisiana Waterthrush", "Common Yellowthroat", "American Redstart",
    "Northern Parula", "Yellow-breasted Chat",
    # sparrows and relatives that migrate (not the resident ones)
    "White-throated Sparrow", "White-crowned Sparrow", "Fox Sparrow", "Lincoln's Sparrow", "Swamp Sparrow",
    "Chipping Sparrow", "Field Sparrow", "Savannah Sparrow", "Vesper Sparrow", "Grasshopper Sparrow",
    "American Tree Sparrow", "Dark-eyed Junco", "Eastern Towhee",
    # wrens, kinglets, creepers, nuthatches that migrate
    "Winter Wren", "House Wren", "Marsh Wren", "Sedge Wren", "Golden-crowned Kinglet", "Ruby-crowned Kinglet",
    "Brown Creeper", "Red-breasted Nuthatch",
    # others
    "Gray Catbird", "Brown Thrasher", "Scarlet Tanager", "Rose-breasted Grosbeak", "Indigo Bunting",
    "Baltimore Oriole", "Orchard Oriole", "Bobolink", "Eastern Wood-Pewee", "Eastern Phoebe",
    "Yellow-billed Cuckoo", "Black-billed Cuckoo", "Yellow-bellied Sapsucker", "Sora", "Virginia Rail",
    "American Woodcock", "Wilson's Snipe",
})


def _is_night_migrant(name: str) -> bool:
    name = name.split(" (")[0]  # "Yellow-rumped Warbler (Myrtle)" -> "Yellow-rumped Warbler"
    return name in NIGHT_MIGRANTS or name.endswith(NIGHT_MIGRANT_FAMILIES)


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
