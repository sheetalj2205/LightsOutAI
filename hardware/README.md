# Wokwi "mini building" (simulated ESP32 + LEDs)

A simulated ESP32 drives a 5 × 6 NeoPixel grid: one LED per window block of the real building.
When the AI decides, the LEDs switch off top floor first, in sync with the twin page.

Files (all go into one Wokwi project):

| File | What |
|------|------|
| `sketch.ino` | Firmware |
| `config.h` | Server address + grid size — **edit `SERVER_HOST`** |
| `diagram.json` | ESP32 + 5×6 LED matrix + blue Demo button |
| `libraries.txt` | WebSockets, ArduinoJson, Adafruit NeoPixel |

## Setup (once, ~5 minutes)

1. Open **https://wokwi.com** and sign in (free account, so you can save the project).
2. **New Project → ESP32** (Arduino template).
3. Replace the contents of the default tabs:
   - `sketch.ino` ← this folder's `sketch.ino`
   - `diagram.json` ← this folder's `diagram.json`
   - `libraries.txt` ← this folder's `libraries.txt`
     (if there is no `libraries.txt` tab: **Library Manager** tab → **+** → add `WebSockets`,
     `ArduinoJson`, `Adafruit NeoPixel`)
4. Add a new file: the tab menu **▾ → New file… → `config.h`**, paste this folder's `config.h`.
5. In `config.h` set the server (free Wokwi only reaches the **public internet**, never `localhost`):

   | Backend runs on | `SERVER_HOST` | `SERVER_PORT` | `USE_SSL` |
   |-----------------|---------------|---------------|-----------|
   | Vultr, by IP | `"45.x.x.x"` | `80` | `false` |
   | Domain with HTTPS | `"yourdomain.xyz"` | `443` | `true` |

   No `http://` and no `/` at the end.
6. **Save** (top bar) → **Share** to copy the project link for the Devpost page.

## Run

1. Press the green **▶ Play** button. First build takes ~30–60 s.
2. Serial monitor should show:
   ```
   Joining Wi-Fi Wokwi-GUEST ...
   Wi-Fi OK, IP 10.10.0.2
   Connected to Lights Out AI
   Building received: OOOOOO...
   ```
   The bottom-left LED pulses **blue** while joining Wi-Fi, **amber** while looking for the server.
3. On the dashboard click **Foggy migration** → **Decide**: the LEDs turn off top floor first,
   the ground floor (lobby) stays lit.
4. Check the backend sees it: `http://<server>/api/health` → `"led_boards": 1`.

**No server / Wi-Fi trouble?** Click the blue **Demo** button in the simulation: 1st press lights the
building, 2nd press runs "lights out" by itself, 3rd press turns everything back on.

## Changing the grid size

Keep three places in sync: `config.h` (`FLOORS`, `COLS`) and `diagram.json` (`"rows"`, `"cols"`).
The backend maps any real building onto whatever grid the board reports.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Amber pulse forever | Wrong `SERVER_HOST`/port, or server down: open `http://<server>/api/health` in a browser |
| `Disconnected, retrying...` loop with a domain | Set `USE_SSL true` and port `443` |
| Library not found when building | Check `libraries.txt` has the 3 names exactly |
| LEDs mirrored / upside down | Toggle `START_AT_TOP` or `SERPENTINE` in `config.h` |
