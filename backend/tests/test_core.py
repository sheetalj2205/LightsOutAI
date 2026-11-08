import cv2
import numpy as np

from app import config, decide, detection, risk
from app.demo import COLS, FLOORS, make_demo_photo
from app.models import Conditions, Window

FOGGY = Conditions(time="t", migration_level="high", sky_danger=0.9)
CLEAR = Conditions(time="t", migration_level="low", sky_danger=0.1)
MEDIUM = Conditions(time="t", migration_level="medium", sky_danger=0.5)


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
    out = decide.decide(three_windows(), CLEAR)  # low migration: no target, the AI's choice stands
    assert out["source"] == "bullsai"
    assert [a.id for a in out["actions"]] == [2]


def test_weather_is_cached(monkeypatch):
    from app import scenarios, weather
    calls = []
    monkeypatch.setattr(weather, "get_conditions", lambda *a, **k: calls.append(1) or {"summary": "Clear", "sky_danger": 0.1})
    loc = {"lat": 1.0, "lon": 2.0, "place": "X"}
    for _ in range(5):
        scenarios.current_conditions(loc)
    assert len(calls) == 1


def test_no_location_means_no_forecast():
    import pytest
    from app import scenarios
    with pytest.raises(scenarios.NoLocation):
        scenarios.current_conditions(None)


def test_same_question_same_answer(monkeypatch):
    """Two runs on the same building and forecast give the identical AI decision."""
    decide._answers.clear()
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake")
    answers = iter([([decide.Action(id=2, state="off")], "First answer."),
                    ([decide.Action(id=2, state="off"), decide.Action(id=3, state="dim")], "Different answer.")])
    calls = []
    monkeypatch.setattr(decide, "_gemini_decision", lambda *a: calls.append(1) or next(answers))
    first = decide.decide(three_windows(), CLEAR)
    second = decide.decide(three_windows(), CLEAR)
    assert len(calls) == 1
    assert [a.id for a in second["actions"]] == [a.id for a in first["actions"]] == [2]
    assert second["reason"] == "First answer." and second["source"] == "gemini"
    # A different night is a different question.
    decide.decide(three_windows(), MEDIUM)
    assert len(calls) == 2


def test_fallback_is_not_cached(monkeypatch):
    decide._answers.clear()
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake")
    monkeypatch.setattr(decide, "_gemini_decision", lambda *a: (_ for _ in ()).throw(RuntimeError("503")))
    assert decide.decide(three_windows(), FOGGY)["source"] == "fallback"
    assert not decide._answers


def forty_windows():
    return [Window(id=i, floor=2 + i % 8, col=1 + i // 8, x=0, y=0, w=10, h=10, brightness=0.9, color="white")
            for i in range(1, 41)]


def ai_turns_off_two(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(decide, "_gemini_decision",
                        lambda *a: ([decide.Action(id=1, state="off"), decide.Action(id=2, state="dim")], "Two."))


def test_heavy_migration_turns_off_every_non_essential_light(monkeypatch):
    ai_turns_off_two(monkeypatch)
    out = decide.decide(forty_windows(), FOGGY)
    assert {a.id for a in out["actions"] if a.state == "off"} == set(range(1, 41))  # the dim is upgraded too
    assert out["rule"]["goal"] == "all" and "Lights Out" in out["rule"]["source"]["name"]


def test_medium_migration_turns_off_half_the_lit_area(monkeypatch):
    ai_turns_off_two(monkeypatch)
    out = decide.decide(forty_windows(), MEDIUM)
    offs = [a for a in out["actions"] if a.state == "off"]
    assert len(offs) == 20 and out["rule"]["goal"] == "half"
    assert out["estimate"]["lit_area_off"] == 0.5


def test_low_migration_keeps_the_ai_choice(monkeypatch):
    ai_turns_off_two(monkeypatch)
    out = decide.decide(forty_windows(), CLEAR)
    assert [(a.id, a.state) for a in out["actions"]] == [(1, "off"), (2, "dim")]


def test_collision_estimate_follows_van_doren():
    from app import rules
    before = forty_windows()
    after = [w.model_copy(update={"state": "off"}) if w.id <= 20 else w for w in before]
    fall = rules.collision_estimate(before, after, month=10)
    spring = rules.collision_estimate(before, after, month=5)
    assert abs(fall["reduction"] - (1 - 1 / 6)) < 0.001       # halving -> 6x fewer in fall
    assert abs(spring["reduction"] - (1 - 1 / 11)) < 0.001    # 11x fewer in spring
    assert "PNAS" in fall["source"]["name"] and not fall["at_least"]
    # Turning off more than half: only claim the measured halving result, as "at least".
    most = [w.model_copy(update={"state": "off"}) if w.id <= 35 else w for w in before]
    capped = rules.collision_estimate(before, most, month=10)
    assert capped["at_least"] and abs(capped["reduction"] - (1 - 1 / 6)) < 0.001


def test_prompt_states_the_rule():
    wins = forty_windows()
    p = decide._build_prompt(wins, FOGGY)
    assert "every non-essential lit window" in p and "40" in p


def test_glass_facade_grid_ignores_lamps_and_puddles():
    img = np.full((900, 1200, 3), 25, np.uint8)                        # night sky / dark wall
    x0, y0, cols, rows, cw, ch = 200, 250, 10, 5, 70, 80
    cv2.rectangle(img, (x0, y0), (x0 + cols * cw, y0 + rows * ch), (215, 225, 230), -1)  # lit glass
    for c in range(cols + 1):                                          # vertical frames
        cv2.line(img, (x0 + c * cw, y0), (x0 + c * cw, y0 + rows * ch), (30, 30, 30), 6)
    for r in range(rows + 1):                                          # horizontal frames
        cv2.line(img, (x0, y0 + r * ch), (x0 + cols * cw, y0 + r * ch), (30, 30, 30), 6)
    cv2.circle(img, (1050, 300), 25, (255, 255, 255), -1)              # street lamp
    cv2.ellipse(img, (600, 820), (160, 25), 0, 0, 360, (200, 200, 200), -1)  # puddle reflection
    wins = detection.detect_facade_grid(img)
    assert 40 <= len(wins) <= 60                                       # ~50 panes
    assert all(y0 - 10 <= w.y and w.y + w.h <= y0 + rows * ch + 10 for w in wins)  # all on the facade
    assert max(w.floor for w in wins) == rows
    assert len({(w.floor, w.col) for w in wins}) == len(wins)
