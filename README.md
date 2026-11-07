# Lights Out AI

Turns off the building lights that kill migrating birds. It finds every lit window in a real night photo of a
UB building, scores each window's bird-collision risk from tonight's Buffalo weather, lets Gemini choose which
windows to turn off, and switches them on a live digital twin of the building.

```
night photo ─► window detection (OpenCV) ─► risk per window ◄─ weather + migration (NWS)
                                                   │
                                     Gemini decision (+ safe fallback)
                                                   │
                     WebSocket ─► digital twin ─► "ok" ─► Tiger Data log
                                                   │
                           dashboard · before/after · ElevenLabs voice alert
```

| Folder | Owner | What |
|--------|-------|------|
| [backend/](backend/) | Sheetal | FastAPI server, detection, risk, Gemini, WebSocket, Tiger Data |
| [frontend/](frontend/) | Sakshi | Twin building page, dashboard, voice alert |
| [photos/](photos/) | Sakshi | Night photos of UB buildings |
| [deploy/](deploy/) | Sheetal | Vultr setup |
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
