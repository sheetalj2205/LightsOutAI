# Add any building (photo + address) — design

Date: 2026-11-07 · Status: approved in brainstorming

## Goal
Anyone can add a building: upload a photo (night or day) with a name and address. The tool finds the
location, reads that place's weather, works out the floors and windows, builds the 3D tower floor by
floor, and runs the usual 3-step story for it.

## Flow
"＋ Add building" (top bar) → pop-up: photo drop zone + preview, name, address, optional
"floors / windows per floor" → progress checklist (📍 address → 🌙 sky → 🪟 floors & windows →
🏗️ 3D) → pop-up closes, the tower rises floor by floor, story resets to step ①.

## Backend
- `app/geo.py`: `geocode(address) -> {lat, lon, place, matched} | None`.
  US Census one-line geocoder first, OpenStreetMap Nominatim second. 8 s timeouts.
- `app/weather.py` (Sakshi's): `get_conditions(lat=LAT, lon=LON, place="Buffalo, NY")`.
- `app/scenarios.py`: `current_conditions(location=None)`; live weather cached per (lat, lon) for 10 min.
- `app/facade.py`:
  - `read_facade(photo) -> {floors, cols, corners | None, is_night}` via Gemini (image input, JSON).
  - `simulate_windows(img, floors, cols, corners=None, seed=…) -> list[Window]`: grid geometry from
    the corners (or the whole photo), ~70 % of windows lit, ground floor always lit.
- `detection.detect_grid` and `simulate_windows` share one grid-geometry helper.
- `/api/analyze` gains `address`. Order: corners given → grid fallback (as now); else night detection;
  if it finds < 6 windows or the photo is bright (day) → Gemini facade reading → simulated lights;
  if Gemini fails → manual `floors`/`cols` if given, else HTTP 422 "need floors and cols".
- `Building` stores `location {address, lat, lon, place}` and `lights: "detected" | "simulated"`.
  Every conditions/risk call uses the current building's location (Buffalo by default).

## Frontend
- Pop-up (`<dialog>`) in `index.html`, logic in `js/addbuilding.js`; uses `fetch` + FormData to
  `/api/analyze` (disabled in fake mode with a toast).
- `scene.setBuilding(b, {rise: true})`: tower grows from the ground over ~1.6 s.
- Step ① eyebrow shows the place ("Tonight's sky · Chicago, IL"); building chip shows name + city.
- Simulated-lights buildings show "Lights simulated · day photo" and the grid overlay photo instead of
  the before/after slider.

## Errors
Address not found → Buffalo weather + notice. Non-US → default night, labelled. Gemini fails → pop-up
asks for floors / windows per floor. HEIC or unreadable image → clear message.

## Testing
pytest with external calls faked: geocode parsing, per-location conditions + cache key, day photo →
simulated grid, 422 when no grid info, address stored on the building. Browser run of the upload flow.

## Out of scope
Photo texture on the 3D facade, map pin, non-US weather.
