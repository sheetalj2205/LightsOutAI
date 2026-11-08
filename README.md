# Lights Out AI

Turns off the building lights that kill migrating birds. Upload a photo of any building and type its address.
It finds every lit window, checks tonight's weather, bird migration and nearby eBird sightings, lets AI choose
which windows to turn off (checked against published Lights Out rules), and switches them off on a 3D model of
the building and a small ESP32 LED building.

```
photo + address ─► window detection (OpenCV) ─► risk per window ◄─ weather (NWS, NOAA GFS) + eBird
                                                       │          + migration (BirdCast method)
                                  Gemini decision (backups: BullsAI, then rules)
                                                       │
                                     checked against tonight's Lights Out rule
                                                       │
                  WebSocket ─► 3D model + ESP32 LED building ─► "ok" ─► Tiger Data log
                                                       │
                     impact (collisions, energy, money) · before/after · ElevenLabs voice alert
```

| Folder | Owner | What |
|--------|-------|------|
| [backend/](backend/) | Sheetal | FastAPI server, detection, risk, Gemini, WebSocket, Tiger Data |
| [frontend/](frontend/) | Sakshi | Upload page, 3D building, dashboard, before/after, voice alert |
| [photos/](photos/) | Sakshi | Sample building photos |
| [deploy/](deploy/) | Sheetal | Vultr setup (planned; we ran on a laptop + Cloudflare Tunnel) |
| [hardware/wokwi/](hardware/wokwi/) | Sheetal | Simulated ESP32 + LED "mini building" ([guide](hardware/README.md)) |

- **Setup, keys and deploy, step by step:** [SETUP.md](SETUP.md)
- **API for the frontend:** [API.md](API.md)
- **Devpost draft:** [DEVPOST.md](DEVPOST.md)

Quick start:
```bash
python3.12 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env            # add keys (optional: everything has a fallback)
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
# open http://localhost:8000/docs
```
