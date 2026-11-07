import json

from fastapi.testclient import TestClient

from app.led import LedView
from app.main import app


def building(states):
    # 4 floors x 4 cols building, ids 1..16 bottom-to-top
    return {"type": "building", "windows": [
        {"id": (f - 1) * 4 + c, "floor": f, "col": c, "state": states, "color": "white"}
        for f in range(1, 5) for c in range(1, 5)]}


def test_maps_big_building_onto_small_grid():
    v = LedView(floors=2, cols=2)
    frame = v.load_building(building("on"))
    assert frame["states"] == "OOOO" and len(frame["colors"]) == 4
    # Top-right LED (index 3) covers windows on floors 3-4, cols 3-4: ids 11, 12, 15, 16.
    assert v.translate({"id": 16, "state": "off"}) == []  # others still on
    for wid in (11, 12, 15):
        out = v.translate({"id": wid, "state": "off"})
    assert out == [{"led": 3, "state": "off"}]
    assert v.translate({"type": "decision", "reason": "x"}) == []


def test_led_board_over_websocket():
    with TestClient(app) as client:
        with client.websocket_connect("/ws?device=led&floors=3&cols=4") as board, \
             client.websocket_connect("/ws") as page:
            frame = json.loads(board.receive_text())
            assert frame["type"] == "frame" and len(frame["states"]) == 12
            assert json.loads(page.receive_text())["type"] == "building"  # pages unchanged
            assert client.get("/api/health").json()["led_boards"] == 1
            client.post("/api/simulate", json={"scenario": "foggy_migration"})
            client.post("/api/decide", json={})
            msg = json.loads(board.receive_text())
            assert set(msg) == {"led", "state"} and 0 <= msg["led"] < 12
            board.send_text(json.dumps(msg | {"ok": True}))
        client.post("/api/reset")
        client.post("/api/simulate", json={"scenario": "live"})
