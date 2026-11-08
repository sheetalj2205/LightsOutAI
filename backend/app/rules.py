"""Tonight's lights-out rule and the collision estimate, taken from published sources.

What to turn off, by tonight's migration level:
  high    every non-essential lit window off.
          Lights Out guidance: Audubon, BirdCast and NY State DEC ask buildings to turn off all
          non-essential lights overnight during migration.
  medium  at least half of the lit window area off, highest-risk windows first.
          Van Doren et al. 2021 (PNAS): halving the lit window area cut collisions 11x in spring
          and 6x in fall at McCormick Place, Chicago (21 years of data).
  low     no target; the AI may dim the brightest windows.

How much it helps: the same study's result, used as an estimate for this building.
Halving lit area -> collisions / 6 (fall) or / 11 (spring), i.e. collisions ~ (lit area)^k with
k = log2(6) or log2(11). It was measured on one building, so for others it is an estimate. The study
measured halving, so turning off more than half is reported as "at least" the halving result.
Dimmed windows still count as lit (conservative: the study is about lit vs dark windows).
"""
import math
from datetime import datetime
from typing import Optional

from .models import Window

GUIDANCE = {"name": "Lights Out guidance (Audubon, BirdCast, NY DEC)", "url": "https://birdcast.org/lights-out/"}
VAN_DOREN = {"name": "Van Doren et al. 2021, PNAS", "url": "https://www.pnas.org/doi/10.1073/pnas.2101666118"}

RULES = {
    "high": {"goal": "all", "source": GUIDANCE,
             "text": "Heavy migration: turn off every non-essential lit window (lobby and safety lights stay on)."},
    "medium": {"goal": "half", "source": VAN_DOREN,
               "text": "Moderate migration: turn off at least half of the lit window area, highest-risk windows first."},
    "low": {"goal": "none", "source": None,
            "text": "Light migration: no lights-out target tonight; dimming the brightest windows is optional."},
}

# Collisions fall by this factor when the lit window area is halved (Van Doren et al. 2021).
HALVING_FACTOR = {"spring": 11, "fall": 6}


def rule_for(level: str) -> dict:
    return {"level": level, **RULES.get(level, RULES["medium"])}


def area(w: Window) -> int:
    return max(w.w, 1) * max(w.h, 1)


def lit_area(windows: list[Window]) -> int:
    return sum(area(w) for w in windows if w.state != "off")


def season(month: Optional[int] = None) -> str:
    """Spring migration Feb-Jul, fall Aug-Jan (northern hemisphere)."""
    month = month or datetime.now().month
    return "spring" if 2 <= month <= 7 else "fall"


def rule_met(level: str, candidates: list[Window], windows: list[Window], off_ids: set[int]) -> bool:
    """candidates: lit windows that may change; off_ids: windows the plan turns off."""
    goal = rule_for(level)["goal"]
    if goal == "all":
        return all(w.id in off_ids for w in candidates)
    if goal == "half":
        off_area = sum(area(w) for w in windows if w.id in off_ids and w.state != "off")
        return off_area >= 0.5 * lit_area(windows)
    return True


def minimum_plan(level: str, candidates: list[Window], windows: list[Window]) -> list[int]:
    """Fewest highest-risk windows (candidates sorted by risk) that meet tonight's rule."""
    off: list[int] = []
    for w in candidates:
        if rule_met(level, candidates, windows, set(off)):
            break
        off.append(w.id)
    return off


def collision_estimate(before: list[Window], after: list[Window], month: Optional[int] = None) -> dict:
    """Estimated drop in bird collisions from the change in lit window area."""
    s = season(month)
    a0, a1 = lit_area(before), lit_area(after)
    ratio = a1 / a0 if a0 else 1.0
    k = math.log2(HALVING_FACTOR[s])
    at_least = ratio < 0.5  # beyond what the study measured: claim only the halving result
    reduction = 1 - 1 / HALVING_FACTOR[s] if at_least else 1 - ratio ** k
    return {
        "reduction": round(reduction, 3),           # 0.83 = about 83% fewer collisions
        "at_least": at_least,
        "lit_area_off": round(1 - ratio, 3),        # share of the lit window area turned off
        "season": s, "halving_factor": HALVING_FACTOR[s],
        "source": VAN_DOREN,
    }
