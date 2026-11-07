# Backend API (for Sakshi's pages)

Base URL: `http://localhost:8000` (laptop) or `http://<vultr-ip>` (deployed). Try everything live at `/docs`.
The server starts with a built-in **Demo Hall** building, so every call below works right away.

## Window format (same everywhere)
```json
{"id": 12, "floor": 3, "col": 5, "x": 410, "y": 220, "w": 38, "h": 52,
 "state": "on", "brightness": 0.82, "color": "white", "risk": 0.74}
```
`floor` 1 = ground floor (always kept on). `col` 1 = leftmost. `x, y, w, h` are pixels in the building photo
(use them for risk overlays and the before/after view). `state` is `on`, `dim` or `off`.

## Endpoints

| Call | What you get |
|------|-------------|
| `GET /api/conditions` | Tonight's forecast **at the current building's address**: `{time, location, summary, sky_cover, fog, rain, wind_dir, wind_speed_mph, migration_level, migration_estimated, sky_danger, scenario, source, source_url, updated}`. **409** if the building has no address yet |
| `POST /api/location` (JSON `{"address": "...", "building": optional}`) | Sets/changes a building's address → `{location, conditions, risk}`. **422** if the address can't be found |
| `GET /api/windows` | Current building: `{building, floors, cols, image_width, image_height, photo_url, debug_url, after_url, windows: [...], risk}` |
| `GET /api/buildings` | List of analyzed buildings + which one is current |
| `POST /api/select` (form: `building`) | Switch the current building (twin pages redraw) |
| `POST /api/analyze` (form: `photo` file, `building`, `address`, optional `floors`, `cols`, `threshold`) | Night photo: detects lit windows. Day photo: AI counts floors/windows, lights simulated (`lights: "simulated"`). Returns `/api/windows` shape + `location` + `conditions`. 422 if the address or the floors can't be found |
| `POST /api/decide` (JSON `{}`) | `{building, actions:[{id,state}], risk_before, risk_after, reason, source, conditions, windows, energy_saved_kwh, money_saved_usd, photo_url, after_url}` and sends the commands to twin pages |
| `POST /api/simulate` (JSON `{"scenario": "clear" \| "foggy_migration" \| "live"}`) | The new conditions |
| `POST /api/reset` | All windows back to how they were in the photo (to run the demo again) |
| `GET /api/decision` | The last decision (or `{}`) |
| `POST /api/alert` (JSON `{"text": "..."}`) | ElevenLabs voice: returns an mp3 clip. 503 if no key (the page then uses the browser voice) |

Image URLs (`photo_url`, `debug_url`, `after_url`) are paths: prefix them with the base URL.
`after_url` is the real photo with the chosen windows darkened — ready for the before/after view.

**Demo flow:** building has an address (else `POST /api/location`) → `POST /api/decide {}` (409 without an address) → show
`reason`, `risk_before → risk_after`, savings, and play the voice alert for `reason`.

## WebSocket `/ws`

```js
const ws = new WebSocket(BASE.replace(/^http/, "ws") + "/ws");
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === "building")   drawBuilding(msg);          // full window list: draw the grid
  else if (msg.type === "decision")   showDecision(msg);     // reason, risk before/after (dashboard)
  else if (msg.type === "conditions") showConditions(msg);   // after /api/simulate
  else if ("id" in msg) {                                    // a command: {"id": 12, "state": "off"}
    setWindow(msg.id, msg.state);
    ws.send(JSON.stringify({ ...msg, ok: true }));           // reply: {"id": 12, "state": "off", "ok": true}
  }
};
```
- Right after connecting you receive a `building` message with every window.
- Commands arrive ~80 ms apart, top floor first, so windows go dark in a visible wave.
- Reconnect after 2 s if the socket closes (the server may restart during the hackathon).

## LED boards (Wokwi ESP32)
Connect to `/ws?device=led&floors=5&cols=6`. The building is mapped onto that grid and the board gets
`{"type":"frame","states":"OODF…","colors":[…]}` then `{"led": 7, "state": "off"}`, and replies with `"ok": true`.
Twin pages are not affected. `GET /api/health` shows `led_boards`. See [hardware/README.md](hardware/README.md).

## Migration estimate
`migration_level`, `migration_index` (0-1) and `migration_factors` (`[{label, effect: up|down|neutral}]`) come from
`backend/app/migration.py`: the factors of the BirdCast forecast model (Van Doren & Horton, Science 2018) — season,
tailwind, 24 h temperature and pressure change, rain — on NOAA GFS weather via Open-Meteo. `birdcast_url` links to
BirdCast's radar dashboard for comparison. `ebird` (when `EBIRD_API_KEY` is set) lists night-migrant species reported
within 25 km in the last 3 days (eBird, Cornell Lab of Ornithology).

## Weather sources
No location is hardcoded. The forecast always comes from the building's address:
U.S. National Weather Service (api.weather.gov) for US addresses, Open-Meteo (open-meteo.com) elsewhere.
`source`, `source_url` (the human-readable forecast page) and `updated` say which one, so the page can cite it.
Addresses are found with the US Census geocoder, then OpenStreetMap Nominatim.
