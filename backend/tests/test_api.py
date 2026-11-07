import json

from fastapi.testclient import TestClient

from app import config
from app.demo import make_demo_photo
from app.main import app


def test_full_loop(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    with TestClient(app) as client:
        assert client.get("/api/health").json()["ok"]
        # No address yet: no forecast, and the AI won't decide.
        assert client.get("/api/conditions").status_code == 409
        assert client.post("/api/decide", json={}).status_code == 409
        loc = client.post("/api/location", json={"address": "1 Test St, Testville"}).json()
        assert loc["location"]["place"] == "Testville, IL"
        cond = client.get("/api/conditions").json()
        assert cond["migration_level"] in ("low", "medium", "high")
        assert cond["source"] == "Test forecast" and cond["source_url"] and cond["location"]

        r = client.post("/api/analyze", files={"photo": ("p.jpg", make_demo_photo(3), "image/jpeg")},
                        data={"building": "Test Hall", "threshold": "150", "address": "2 Test Ave, Testville"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["windows"] and set(body["windows"][0]) >= {
            "id", "floor", "col", "x", "y", "w", "h", "state", "brightness", "color", "risk"}
        assert client.get(body["debug_url"]).status_code == 200

        assert client.post("/api/simulate", json={"scenario": "foggy_migration"}).json()["sky_danger"] == 0.9

        with client.websocket_connect("/ws") as ws:
            hello = json.loads(ws.receive_text())
            assert hello["type"] == "building" and hello["building"] == "Test Hall"
            d = client.post("/api/decide", json={}).json()
            assert d["risk_after"] < d["risk_before"] and d["actions"]
            assert json.loads(ws.receive_text())["type"] == "decision"
            cmd = json.loads(ws.receive_text())
            assert set(cmd) == {"id", "state"}
            ws.send_text(json.dumps(cmd | {"ok": True}))

        assert client.get(d["after_url"]).status_code == 200
        assert all(w["state"] == w0["state"] for w, w0 in
                   zip(client.post("/api/reset").json()["windows"], body["windows"]))
        client.post("/api/simulate", json={"scenario": "live"})
