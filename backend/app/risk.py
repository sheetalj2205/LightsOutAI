"""Bird-collision risk per window and per building (Task 3).

risk = migration x sky danger x window attractiveness, scaled 0 to 1.
"""
from .models import Conditions, Window

MIGRATION_FACTOR = {"low": 0.3, "medium": 0.6, "high": 1.0}

# Cool / white light draws birds in more than warm or red light.
COLOR_FACTOR = {"white": 1.0, "blue": 1.0, "cool": 1.0, "yellow": 0.75, "warm": 0.75,
                "orange": 0.7, "red": 0.5, "green": 0.8}

STATE_FACTOR = {"on": 1.0, "dim": 0.35, "off": 0.0}


def sky_factor(sky_danger: float) -> float:
    # Even a clear night carries some risk, so never multiply by zero.
    return 0.3 + 0.7 * sky_danger


def attractiveness(win: Window, max_floor: int) -> float:
    color = COLOR_FACTOR.get(win.color, 0.85)
    height = 0.6 + 0.4 * (win.floor / max(max_floor, 1))  # higher floors are seen from farther
    return win.brightness * color * height * STATE_FACTOR[win.state]


def window_risk(win: Window, cond: Conditions, max_floor: int) -> float:
    r = MIGRATION_FACTOR[cond.migration_level] * sky_factor(cond.sky_danger) * attractiveness(win, max_floor)
    return round(min(max(r, 0.0), 1.0), 3)


def score_windows(windows: list[Window], cond: Conditions) -> list[Window]:
    """Return copies of the windows with .risk filled in for their current state."""
    max_floor = max((w.floor for w in windows), default=1)
    return [w.model_copy(update={"risk": window_risk(w, cond, max_floor)}) for w in windows]


def building_risk(windows: list[Window], cond: Conditions) -> float:
    """Average window risk, 0 to 1. Turning windows off or dim lowers it."""
    if not windows:
        return 0.0
    scored = score_windows(windows, cond)
    return round(sum(w.risk for w in scored) / len(scored), 3)


def risk_before_after(windows: list[Window], changes: dict[int, str], cond: Conditions) -> tuple[float, float]:
    """Total risk now, and after applying {window_id: new_state}."""
    after = [w.model_copy(update={"state": changes.get(w.id, w.state)}) for w in windows]
    return building_risk(windows, cond), building_risk(after, cond)
