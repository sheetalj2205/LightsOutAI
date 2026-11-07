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
        r = genai.Client(api_key=config.GEMINI_API_KEY).models.generate_content(
            model=config.GEMINI_MODEL, contents="Reply with the single word: ready")
        report("Gemini", True, f"{config.GEMINI_MODEL} says: {r.text.strip()[:40]}")
    except Exception as e:
        report("Gemini", False, str(e)[:160])

# ElevenLabs (Sakshi's voice alert)
key = os.getenv("ELEVENLABS_API_KEY", "")
if not key:
    report("ElevenLabs", False, "ELEVENLABS_API_KEY is empty")
else:
    import httpx
    r = httpx.get("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": key}, timeout=10)
    report("ElevenLabs", r.status_code == 200,
           f"{len(r.json().get('voices', []))} voices available" if r.status_code == 200 else r.text[:160])

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
