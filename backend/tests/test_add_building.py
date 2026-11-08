import cv2
import numpy as np
from fastapi.testclient import TestClient

from app import facade, geo, main
from app.main import app


def day_photo() -> bytes:
    img = np.full((600, 800, 3), 190, np.uint8)  # bright daytime facade
    cv2.rectangle(img, (150, 80), (650, 560), (150, 150, 160), -1)
    return cv2.imencode(".jpg", img)[1].tobytes()


def post(client, **data):
    return client.post("/api/analyze", files={"photo": ("b.jpg", day_photo(), "image/jpeg")}, data=data)


def test_day_photo_without_ai_never_asks_for_grid(monkeypatch):
    monkeypatch.setattr(facade, "read_facade", lambda photo: None)
    with TestClient(app) as client:
        r = post(client, building="Mystery Tower")
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["method"] in ("detect-auto", "estimate") and b["floors"] >= 2 and b["windows"]


def test_day_photo_with_manual_grid(monkeypatch):
    monkeypatch.setattr(geo, "geocode", lambda a: {"lat": 41.88, "lon": -87.63, "place": "Chicago, IL", "matched": a})
    with TestClient(app) as client:
        r = post(client, building="Manual Tower", address="233 S Wacker Dr, Chicago", floors="12", cols="8")
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["lights"] == "simulated" and b["method"] == "manual"
        assert b["floors"] == 12 and b["cols"] == 8 and len(b["windows"]) == 96
        assert all(w["state"] == "on" for w in b["windows"] if w["floor"] == 1)  # lobby always lit
        assert b["location"]["place"] == "Chicago, IL"
        assert client.get("/api/windows").json()["building"] == "Manual Tower"


def test_day_photo_read_by_ai(monkeypatch):
    monkeypatch.setattr(facade, "read_facade", lambda photo: {
        "floors": 9, "cols": 6, "corners": [[0.2, 0.1], [0.8, 0.1], [0.8, 0.9], [0.2, 0.9]], "is_night": False})
    with TestClient(app) as client:
        b = post(client, building="AI Tower", address="1 Test St, Testville").json()
        assert b["method"] == "ai-facade" and b["floors"] == 9 and b["cols"] == 6
        assert b["location"]["place"] == "Testville, IL"
        assert b["conditions"]["source"] == "Test forecast"
        xs = [w["x"] for w in b["windows"]]
        assert min(xs) >= 0.18 * 800 - 5 and max(xs) <= 0.8 * 800  # inside the facade corners


def test_parse_facade_answer():
    info = facade._parse('```json\n{"floors": 120, "windows_per_floor": 7, "corners": [[0,0],[1,0],[1,1]], "is_night": true}\n```')
    assert info["floors"] == facade.MAX_FLOORS and info["cols"] == 7 and info["corners"] is None and info["is_night"]


def test_unknown_address_is_rejected(monkeypatch):
    monkeypatch.setattr(geo, "geocode", lambda a: None)
    with TestClient(app) as client:
        r = post(client, building="Lost Tower", address="nowhere 123", floors="5", cols="5")
        assert r.status_code == 422 and "Couldn't find" in r.json()["detail"]


def test_two_people_at_once_keep_their_own_building():
    with TestClient(app) as client:
        assert post(client, building="Tower A", floors="4", cols="4").status_code == 200
        assert post(client, building="Tower B", floors="5", cols="3").status_code == 200
        r = client.post("/api/location", json={"address": "1 Test St", "building": "Tower A"})
        assert r.status_code == 200, r.text
        d = client.post("/api/decide", json={"building": "Tower A"}).json()
        assert d["building"] == "Tower A"


def test_photos_of_more_sides():
    with TestClient(app) as client:
        r = client.post("/api/analyze", data={"building": "Four Sides", "floors": "4", "cols": "5"},
                        files={"photo": ("f.jpg", day_photo(), "image/jpeg"),
                               "photo_right": ("r.jpg", day_photo(), "image/jpeg")})
        assert r.status_code == 200, r.text
        b = r.json()
        assert set(b["faces"]) == {"front", "right"}
        sides = {w["face"] for w in b["windows"]}
        assert sides == {"front", "right"}
        ids = [w["id"] for w in b["windows"]]
        assert len(ids) == len(set(ids))  # unique across sides
        assert b["cols"] == 5  # front only
        assert client.get(b["faces"]["right"]["photo_url"]).status_code == 200
