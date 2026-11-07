"""Check every key in .env works:   .venv/bin/python scripts/check_keys.py"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config  # noqa: E402  (loads .env)

ok = True


def report(name: str, good: bool, msg: str) -> None:
    global ok
    ok &= good
    print(f"{'PASS' if good else 'FAIL'}  {name:12} {msg}")


# Gemini
if not config.GEMINI_API_KEY:
    report("Gemini", False, "GEMINI_API_KEY is empty (the app still runs, using the rule-based fallback)")
else:
    try:
        from google import genai
        client = genai.Client(api_key=config.GEMINI_API_KEY)  # keep a reference or the SDK closes it
        r = client.models.generate_content(model=config.GEMINI_MODEL, contents="Reply with the single word: ready")
        report("Gemini", True, f"{config.GEMINI_MODEL} says: {r.text.strip()[:40]}")
    except Exception as e:
        report("Gemini", False, str(e)[:160])

# BullsAI (backup AI)
from app import decide  # noqa: E402
if not decide.bullsai_ready():
    report("BullsAI", False, "BULLSAI_API_KEY / BULLSAI_BASE_URL / BULLSAI_MODEL not all set (optional backup)")
else:
    try:
        reply = decide.bullsai_chat('Reply with this JSON exactly: {"status": "ready"}')
        report("BullsAI", "ready" in reply, f"{config.BULLSAI_MODEL} says: {reply.strip()[:60]}")
    except Exception as e:
        report("BullsAI", False, f"{str(e)[:140]}  (off campus? connect to UB VPN)")

# eBird (Cornell Lab)
from app import ebird  # noqa: E402
if not config.EBIRD_API_KEY:
    report("eBird", False, "EBIRD_API_KEY is empty (optional: live bird sightings are hidden)")
else:
    e = ebird.recent(42.886, -78.878)
    report("eBird", e is not None, f"{e['migrant_species']} night-migrant species reported near Buffalo" if e else "request failed")

# ElevenLabs (Sakshi's voice alert)
key = os.getenv("ELEVENLABS_API_KEY", "")
if not key:
    report("ElevenLabs", False, "ELEVENLABS_API_KEY is empty")
else:
    import httpx
    voice = os.getenv("ELEVENLABS_VOICE_ID", "")
    if not voice:
        report("ElevenLabs", False, "ELEVENLABS_VOICE_ID is empty")
    else:
        # Speak one word with the chosen voice: tests the key, the Text to Speech permission and the voice id.
        r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                       headers={"xi-api-key": key}, timeout=20,
                       json={"text": "Ready.", "model_id": "eleven_flash_v2_5"})
        good = r.status_code == 200 and r.headers.get("content-type", "").startswith("audio")
        report("ElevenLabs", good, f"voice works ({len(r.content)} bytes of audio)" if good else r.text[:200])

# Tiger Data
if not config.DATABASE_URL:
    report("Tiger Data", False, "DATABASE_URL is empty (optional: logging is skipped)")
else:
    from app import db
    report("Tiger Data", db.init(), "connected, window_events table ready" if db.enabled() else "could not connect")

# Weather (no key needed)
try:
    import httpx
    r = httpx.get("https://api.weather.gov/points/42.8864,-78.8784",
                  headers={"User-Agent": "LightsOutAI hackathon project"}, timeout=10)
    report("Weather.gov", r.status_code == 200, "reachable" if r.status_code == 200 else f"HTTP {r.status_code}")
except Exception as e:
    report("Weather.gov", False, str(e)[:160])

sys.exit(0 if ok else 1)
