import pytest

from app import config, scenarios, weather


@pytest.fixture(autouse=True)
def no_external_services(monkeypatch):
    """Tests never call real Gemini, BullsAI, Tiger Data or the weather service, even if .env has keys."""
    for name in ("GEMINI_API_KEY", "BULLSAI_API_KEY", "BULLSAI_BASE_URL", "BULLSAI_MODEL", "DATABASE_URL"):
        monkeypatch.setattr(config, name, "")
    monkeypatch.setattr(weather, "get_conditions", lambda: {
        "location": "Buffalo, NY", "summary": "Mostly Cloudy, NW wind 8 mph", "sky_cover": 80,
        "fog": False, "rain": False, "wind_dir": "NW", "wind_speed_mph": 8,
        "migration_level": "medium", "migration_estimated": True, "sky_danger": 0.6})
    monkeypatch.setattr(scenarios, "_cache", (0.0, {}))
