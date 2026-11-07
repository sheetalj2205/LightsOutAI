"""Pick which windows to turn off or dim (Task 6).

Gemini looks at the photo, window list and tonight's conditions and returns JSON.
If Gemini is missing, slow or returns bad JSON, a rule-based fallback takes over,
so the demo never breaks. Essential floors (lobby) always stay on.
"""
import json
import logging
from typing import Optional

from pydantic import BaseModel, ValidationError

from . import config, risk
from .models import Action, Conditions, Window

log = logging.getLogger("lightsout.decide")

# Rough energy model for the "saved" numbers: one lit office window ~ 60 W of lighting.
WATTS_PER_WINDOW = 60
HOURS_PER_NIGHT = 8
USD_PER_KWH = 0.17  # approx. NY commercial rate


class _GeminiAnswer(BaseModel):
    actions: list[Action]
    reason: str


PROMPT = """You are Lights Out AI, protecting migrating birds from building lights at night.
Birds are drawn to lit windows, especially bright white light on foggy, cloudy nights with
strong migration. Choose which windows to turn OFF or DIM tonight to cut collision risk.

Rules:
- Never change windows on these floors (essential lobby/safety lighting): {essential}
- Prefer turning off the highest-risk windows; dim medium-risk ones if useful.
- On a low-risk night, change only a few windows. On a high-risk night, be aggressive.
- Only use window ids from the list.

Tonight's conditions:
{conditions}

Windows (risk is 0-1, higher = more dangerous):
{windows}

Reply with JSON only:
{{"actions": [{{"id": <window id>, "state": "off" or "dim"}}],
  "reason": "<one or two short plain-English sentences for building staff, mentioning the
   weather, migration level, how many windows and which floors>"}}"""


def _floors_text(floors: list[int]) -> str:
    floors = sorted(set(floors))
    if not floors:
        return ""
    if len(floors) == 1:
        return f"floor {floors[0]}"
    if floors == list(range(floors[0], floors[-1] + 1)):
        return f"floors {floors[0]} to {floors[-1]}"
    return "floors " + ", ".join(map(str, floors[:-1])) + f" and {floors[-1]}"


def fallback_decision(windows: list[Window], cond: Conditions) -> tuple[list[Action], str]:
    """Turn off the top-risk windows; how many depends on how dangerous the night is."""
    scored = risk.score_windows(windows, cond)
    candidates = sorted((w for w in scored if w.state != "off" and w.floor not in config.ESSENTIAL_FLOORS),
                        key=lambda w: w.risk, reverse=True)
    night = risk.MIGRATION_FACTOR[cond.migration_level] * risk.sky_factor(cond.sky_danger)
    share_off = 0.15 + 0.65 * night  # 15% on a calm night up to 80% on the worst night
    n_off = round(len(candidates) * share_off)
    off, rest = candidates[:n_off], candidates[n_off:]
    dim = [w for w in rest if w.risk >= 0.25][: max(1, len(rest) // 3)] if rest else []
    actions = [Action(id=w.id, state="off") for w in off] + [Action(id=w.id, state="dim") for w in dim]

    sky = [x for x, on in (("fog", cond.fog), ("rain", cond.rain),
                            ("low clouds", cond.sky_cover >= 70 and not cond.fog)) if on]
    sky_text = " and ".join(sky) if sky else ("clear skies" if cond.sky_cover < 30 else "some clouds")
    city = cond.location.split(",")[0]
    parts = [f"{cond.migration_level.capitalize()} migration and {sky_text} over {city} tonight."]
    if off:
        parts.append(f"I've turned off {len(off)} windows on {_floors_text([w.floor for w in off])}")
        parts[-1] += f" and dimmed {len(dim)} more." if dim else "."
    elif dim:
        parts.append(f"I've dimmed {len(dim)} windows.")
    else:
        parts.append("No changes needed right now.")
    return actions, " ".join(parts)


def _gemini_decision(windows: list[Window], cond: Conditions,
                     photo: Optional[bytes]) -> tuple[list[Action], str]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY,
                          http_options=types.HttpOptions(timeout=20_000))
    scored = risk.score_windows(windows, cond)
    win_rows = [{"id": w.id, "floor": w.floor, "col": w.col, "state": w.state,
                 "brightness": w.brightness, "color": w.color, "risk": w.risk} for w in scored]
    prompt = PROMPT.format(essential=sorted(config.ESSENTIAL_FLOORS),
                           conditions=cond.model_dump_json(indent=1),
                           windows=json.dumps(win_rows))
    contents: list = [prompt]
    if photo:
        contents.insert(0, types.Part.from_bytes(data=photo, mime_type="image/jpeg"))
    resp = client.models.generate_content(
        model=config.GEMINI_MODEL, contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
    )
    answer = _GeminiAnswer.model_validate_json(resp.text)
    return answer.actions, answer.reason.strip()


def _clean(actions: list[Action], windows: list[Window]) -> list[Action]:
    """Drop unknown ids, essential floors, duplicates and no-op changes."""
    by_id = {w.id: w for w in windows}
    seen, out = set(), []
    for a in actions:
        w = by_id.get(a.id)
        if w is None or a.id in seen or w.floor in config.ESSENTIAL_FLOORS or w.state == a.state:
            continue
        seen.add(a.id)
        out.append(a)
    return out


def decide(windows: list[Window], cond: Conditions, photo: Optional[bytes] = None) -> dict:
    source = "fallback"
    actions, reason = [], ""
    if config.GEMINI_API_KEY:
        try:
            actions, reason = _gemini_decision(windows, cond, photo)
            actions = _clean(actions, windows)
            source = "gemini"
        except (ValidationError, ValueError) as exc:
            log.warning("Gemini returned bad JSON, using fallback: %s", exc)
        except Exception as exc:  # network, quota, timeout...
            log.warning("Gemini failed, using fallback: %s", exc)
    if source == "fallback":
        actions, reason = fallback_decision(windows, cond)
        actions = _clean(actions, windows)

    changes = {a.id: a.state for a in actions}
    before, after = risk.risk_before_after(windows, changes, cond)
    new_windows = risk.score_windows(
        [w.model_copy(update={"state": changes.get(w.id, w.state)}) for w in windows], cond)

    watts_saved = sum(WATTS_PER_WINDOW * (1.0 if s == "off" else 0.5) for s in changes.values())
    kwh = round(watts_saved * HOURS_PER_NIGHT / 1000, 2)
    return {
        "actions": actions, "reason": reason, "source": source,
        "risk_before": before, "risk_after": after, "windows": new_windows,
        "energy_saved_kwh": kwh, "money_saved_usd": round(kwh * USD_PER_KWH, 2),
    }
