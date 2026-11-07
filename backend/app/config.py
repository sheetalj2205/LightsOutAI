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

# BullsAI Model Hub (UB-hosted models, OpenAI-compatible API). Used when Gemini fails.
BULLSAI_API_KEY = os.getenv("BULLSAI_API_KEY", "")
BULLSAI_BASE_URL = os.getenv("BULLSAI_BASE_URL", "").rstrip("/")
BULLSAI_MODEL = os.getenv("BULLSAI_MODEL", "")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
DETECT_THRESHOLD = int(os.getenv("DETECT_THRESHOLD", "200"))

# Floors whose lights always stay on (lobby / safety lighting).
ESSENTIAL_FLOORS = {1}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
