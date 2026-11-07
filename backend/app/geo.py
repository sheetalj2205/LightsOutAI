"""Address -> coordinates. US Census geocoder first (free, no key), OpenStreetMap second."""
import logging
from typing import Optional

import httpx

log = logging.getLogger("lightsout.geo")
UA = {"User-Agent": "LightsOutAI-UBHacking (student project)"}


def _census(address: str) -> Optional[dict]:
    r = httpx.get("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",
                  params={"address": address, "benchmark": "Public_AR_Current", "format": "json"},
                  headers=UA, timeout=8)
    r.raise_for_status()
    matches = r.json()["result"]["addressMatches"]
    if not matches:
        return None
    m = matches[0]
    comp = m.get("addressComponents", {})
    place = ", ".join(x for x in (comp.get("city", "").title(), comp.get("state", "")) if x)
    return {"lat": m["coordinates"]["y"], "lon": m["coordinates"]["x"],
            "place": place or m["matchedAddress"], "matched": m["matchedAddress"]}


def _nominatim(address: str) -> Optional[dict]:
    r = httpx.get("https://nominatim.openstreetmap.org/search",
                  params={"q": address, "format": "json", "limit": 1, "addressdetails": 1},
                  headers=UA, timeout=8)
    r.raise_for_status()
    hits = r.json()
    if not hits:
        return None
    h = hits[0]
    a = h.get("address", {})
    city = a.get("city") or a.get("town") or a.get("village") or a.get("county") or ""
    state = a.get("state", "")
    place = ", ".join(x for x in (city, state) if x) or h["display_name"].split(",")[0]
    return {"lat": float(h["lat"]), "lon": float(h["lon"]), "place": place, "matched": h["display_name"]}


def geocode(address: str) -> Optional[dict]:
    """{lat, lon, place, matched} or None if nobody could find the address."""
    address = (address or "").strip()
    if not address:
        return None
    # Full address first; then drop leading parts ("12 Capen Hall, Buffalo, NY" -> "Buffalo, NY")
    # so campus building names still land in the right city.
    parts = [p.strip() for p in address.split(",") if p.strip()]
    tries = [("census", _census, address), ("nominatim", _nominatim, address)]
    tries += [("nominatim", _nominatim, ", ".join(parts[i:])) for i in range(1, len(parts))]
    for name, fn, query in tries:
        try:
            hit = fn(query)
            if hit:
                log.info("geocoded %r via %s (%r) -> %s", address, name, query, hit["place"])
                return hit
        except Exception as exc:
            log.warning("%s geocoder failed: %s", name, str(exc)[:160])
    return None
