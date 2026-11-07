import numpy as np

from app import config, decide, detection, risk
from app.demo import COLS, FLOORS, make_demo_photo
from app.models import Conditions, Window

FOGGY = Conditions(time="t", migration_level="high", sky_danger=0.9)
CLEAR = Conditions(time="t", migration_level="low", sky_danger=0.1)


def three_windows():
    return [
        Window(id=1, floor=1, col=1, x=0, y=0, w=10, h=10, brightness=0.9, color="white"),
        Window(id=2, floor=5, col=1, x=0, y=0, w=10, h=10, brightness=0.9, color="white"),
        Window(id=3, floor=5, col=2, x=0, y=0, w=10, h=10, brightness=0.4, color="yellow"),
    ]


def test_risk_three_windows():
    s = {w.id: w.risk for w in risk.score_windows(three_windows(), FOGGY)}
    assert all(0 <= r <= 1 for r in s.values())
    assert s[2] > s[1]  # higher floor, same light
    assert s[2] > s[3]  # brighter, cooler light
    assert risk.building_risk(three_windows(), FOGGY) > risk.building_risk(three_windows(), CLEAR)


def test_risk_drops_when_windows_off():
    before, after = risk.risk_before_after(three_windows(), {2: "off", 3: "dim"}, FOGGY)
    assert after < before


def test_detects_demo_building():
    img = detection.load_image(make_demo_photo())
    wins = detection.detect_windows(img, threshold=150)
    assert 0.5 * FLOORS * COLS <= len(wins) <= FLOORS * COLS
    assert max(w.floor for w in wins) == FLOORS
    assert sum(1 for w in wins if w.floor == 1) == COLS  # ground floor all lit
    path = detection.save_debug_image(img, wins, config.OUTPUT_DIR / "test" / "debug.jpg")
    assert path.exists()


def test_grid_fallback():
    img = detection.load_image(make_demo_photo())
    wins = detection.detect_grid(img, [[220, 150], [980, 150], [980, 860], [220, 860]], FLOORS, COLS)
    assert len(wins) == FLOORS * COLS
    auto = detection.detect_windows(img, threshold=150)
    lit = sum(1 for w in wins if w.state == "on")
    assert abs(lit - len(auto)) <= 3


def test_fallback_never_touches_lobby(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    img = detection.load_image(make_demo_photo())
    wins = detection.detect_windows(img, threshold=150)
    out = decide.decide(wins, FOGGY)
    by_id = {w.id: w for w in wins}
    assert out["source"] == "fallback"
    assert out["actions"] and all(by_id[a.id].floor != 1 for a in out["actions"])
    assert out["risk_after"] < out["risk_before"]
    assert "turned off" in out["reason"]
    # A clear night changes fewer windows than a foggy migration night.
    assert len(decide.decide(wins, CLEAR)["actions"]) < len(out["actions"])


def test_bad_gemini_falls_back(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake")
    def broken(*a, **k):
        raise ValueError("not json")
    monkeypatch.setattr(decide, "_gemini_decision", broken)
    out = decide.decide(three_windows(), FOGGY)
    assert out["source"] == "fallback"


def test_bullsai_used_when_gemini_fails(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake")
    monkeypatch.setattr(config, "BULLSAI_API_KEY", "k")
    monkeypatch.setattr(config, "BULLSAI_BASE_URL", "http://x/v1")
    monkeypatch.setattr(config, "BULLSAI_MODEL", "m")
    def gemini_down(*a, **k):
        raise RuntimeError("503 UNAVAILABLE")
    monkeypatch.setattr(decide, "_gemini_decision", gemini_down)
    # BullsAI answers with JSON wrapped in a code fence; lobby (id 1) must be ignored.
    monkeypatch.setattr(decide, "bullsai_chat", lambda prompt: '```json\n{"actions": [{"id": 2, "state": "off"},'
                        ' {"id": 1, "state": "off"}], "reason": "Fog tonight."}\n```')
    out = decide.decide(three_windows(), FOGGY)
    assert out["source"] == "bullsai"
    assert [a.id for a in out["actions"]] == [2]


def test_weather_is_cached(monkeypatch):
    from app import scenarios, weather
    calls = []
    monkeypatch.setattr(weather, "get_conditions", lambda *a, **k: calls.append(1) or {"summary": "Clear", "sky_danger": 0.1})
    for _ in range(5):
        scenarios.current_conditions()
    assert len(calls) == 1
