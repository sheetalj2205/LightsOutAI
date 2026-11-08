import pytest

from app import config, decide, ebird, geo, migration, scenarios, weather

TEST_PLACE = {"lat": 41.88, "lon": -87.63, "place": "Testville, IL", "matched": "1 Test St, Testville, IL"}


@pytest.fixture(autouse=True)
def no_external_services(monkeypatch, tmp_path):
    """Tests never call real Gemini, BullsAI, Tiger Data or the weather service, even if .env has keys,
    and write photos to a temp folder (server start-up clears the output folder)."""
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    from app.main import app
    out = next(r.app for r in app.routes if getattr(r, "name", "") == "output")  # /output static files
    monkeypatch.setattr(out, "directory", tmp_path)
    monkeypatch.setattr(out, "all_directories", [tmp_path])
    for name in ("GEMINI_API_KEY", "BULLSAI_API_KEY", "BULLSAI_BASE_URL", "BULLSAI_MODEL", "DATABASE_URL"):
        monkeypatch.setattr(config, name, "")
    monkeypatch.setattr(weather, "get_conditions", lambda *a, **k: {
        "location": "Buffalo, NY", "summary": "Mostly Cloudy, NW wind 8 mph", "sky_cover": 80,
        "fog": False, "rain": False, "wind_dir": "NW", "wind_speed_mph": 8,
        "migration_level": "medium", "migration_estimated": True, "sky_danger": 0.6,
        "source": "Test forecast", "source_url": "https://example.test/forecast", "updated": "2026-11-07T20:00:00+00:00"})
    monkeypatch.setattr(scenarios, "_cache", {})
    decide._answers.clear()
    monkeypatch.setattr(config, "EBIRD_API_KEY", "")
    monkeypatch.setattr(migration, "estimate", lambda lat, lon: {
        "migration_level": "medium", "migration_index": 0.4, "migration_source": "Test migration model",
        "birdcast_url": "https://dashboard.birdcast.org/",
        "migration_factors": [{"label": "NW wind 9 mph · tailwind", "effect": "up"}]})
    monkeypatch.setattr(geo, "geocode", lambda address: TEST_PLACE | {"matched": address})
