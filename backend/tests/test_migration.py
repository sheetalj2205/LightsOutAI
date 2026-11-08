import httpx

from app import config, ebird, migration, scenarios


def test_textbook_fall_cold_front_is_high():
    r = migration.score(day=278, lat=43, wind_from_deg=315, wind_mph=15, temp_change_c=-6,
                        pressure_change_hpa=5, rain_mm=0)
    assert r["migration_level"] == "high"
    effects = {f["label"].split()[0]: f["effect"] for f in r["migration_factors"]}
    assert effects["NW"] == "up" and effects["Temperature"] == "up" and effects["Pressure"] == "up"


def test_rain_and_headwind_keep_birds_down():
    r = migration.score(day=278, lat=43, wind_from_deg=180, wind_mph=12, temp_change_c=3,
                        pressure_change_hpa=-4, rain_mm=3)
    assert r["migration_level"] == "low"
    assert any(f["label"] == "Rain tonight" and f["effect"] == "down" for f in r["migration_factors"])


def test_spring_wants_south_winds():
    south = migration.score(day=128, lat=43, wind_from_deg=190, wind_mph=15, temp_change_c=4,
                            pressure_change_hpa=-3, rain_mm=0)
    north = migration.score(day=128, lat=43, wind_from_deg=0, wind_mph=15, temp_change_c=-4,
                            pressure_change_hpa=3, rain_mm=0)
    assert south["migration_index"] > north["migration_index"]


def test_ebird_counts_night_migrants():
    obs = [{"comName": "Yellow-rumped Warbler"}, {"comName": "Hermit Thrush"}, {"comName": "Rock Pigeon"},
           {"comName": "White-throated Sparrow"}, {"comName": "Hermit Thrush"}]
    s = ebird.summarize(obs)
    assert s["species_total"] == 4 and s["migrant_species"] == 3 and "Rock Pigeon" not in s["examples"]


def test_ebird_skips_year_round_residents():
    # Same name words as migrants ("wren", "sparrow", "nuthatch"), but these stay in Buffalo all year.
    residents = ["Carolina Wren", "House Sparrow", "Song Sparrow", "White-breasted Nuthatch", "American Robin"]
    migrants = ["Winter Wren", "White-throated Sparrow", "Red-breasted Nuthatch", "Brown Creeper",
                "Dark-eyed Junco", "Black-throated Blue Warbler", "Red-eyed Vireo", "Least Flycatcher"]
    s = ebird.summarize([{"comName": n} for n in residents + migrants])
    assert s["migrant_species"] == len(migrants)
    assert not set(residents) & set(s["examples"])


def test_conditions_carry_migration_and_ebird(monkeypatch):
    monkeypatch.setattr(config, "EBIRD_API_KEY", "k")

    class Resp:
        def raise_for_status(self): pass
        def json(self): return [{"comName": "Swainson's Thrush"}, {"comName": "American Crow"}]

    monkeypatch.setattr(httpx, "get", lambda *a, **k: Resp())
    ebird._cache.clear()
    c = scenarios.current_conditions({"lat": 42.9, "lon": -78.9, "place": "Buffalo, NY"})
    assert c.migration_source == "Test migration model" and c.migration_factors
    assert c.birdcast_url and c.ebird["migrant_species"] == 1
