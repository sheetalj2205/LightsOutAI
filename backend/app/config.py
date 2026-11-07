"""Settings loaded from the .env file in the repo root (or real env vars)."""
import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
OUTPUT_DIR = BACKEND_DIR / "output"
PHOTOS_DIR = REPO_ROOT / "photos"

load_dotenv(REPO_ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ElevenLabs voice alert. Default voice = "Rachel" (calm, clear) if none is set.
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "") or "21m00Tcm4TlvDq8Ikt00"
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
DETECT_THRESHOLD = int(os.getenv("DETECT_THRESHOLD", "200"))

# Floors whose lights always stay on (lobby / safety lighting).
ESSENTIAL_FLOORS = {1}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
