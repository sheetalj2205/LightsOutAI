"""Make the frozen demo shown on the landing page (frontend/demo/davis-hall/).

Runs Davis Hall through window detection and the AI once, on the "Foggy migration" scenario,
and saves the photo plus every result the landing page needs as demo.json. The landing page
only reads these files, so it never touches the live server.

    .venv/bin/python scripts/make_demo.py [photo.jpg]
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config, decide, detection, geo, risk, scenarios  # noqa: E402

NAME = "Davis Hall"
ADDRESS = "Davis Hall, University at Buffalo, Buffalo, NY"
THRESHOLD = 190
# Bright patches on the white wall that detection mistakes for windows in this photo.
NOT_WINDOWS = {1, 24, 32, 40, 43, 45, 50}

OUT = config.REPO_ROOT / "frontend" / "demo" / "davis-hall"


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "photo.jpg"
    photo = src.read_bytes()
    img = detection.load_image(photo)
    windows = [w for w in detection.detect_windows(img, THRESHOLD) if w.id not in NOT_WINDOWS]

    location = geo.geocode(ADDRESS) or {"lat": 43.0027, "lon": -78.7873, "place": "Buffalo, NY"}
    location["address"] = ADDRESS
    scenarios.set_scenario("foggy_migration")
    cond = scenarios.current_conditions(location)
    windows = risk.score_windows(windows, cond)

    result = decide.decide(windows, cond, photo)
    by_id = {w.id: w for w in windows}
    actions = sorted(result["actions"], key=lambda a: (-by_id[a.id].floor, by_id[a.id].col))

    OUT.mkdir(parents=True, exist_ok=True)
    if src.resolve() != (OUT / "photo.jpg").resolve():
        shutil.copyfile(src, OUT / "photo.jpg")
    c = cond.model_dump()
    data = {
        "building": NAME,
        "place": location.get("place") or "Buffalo, NY",
        "photo": "demo/davis-hall/photo.jpg",
        "image_width": img.shape[1], "image_height": img.shape[0],
        "floors": max(w.floor for w in windows), "cols": max(w.col for w in windows),
        "windows": [w.model_dump() for w in windows],          # before the AI acts
        "actions": [a.model_dump() for a in actions],            # what the AI changed, top floor first
        "risk_before": result["risk_before"], "risk_after": result["risk_after"],
        "reason": result["reason"], "source": result["source"],
        "rule": result["rule"], "estimate": result["estimate"],
        "energy_saved_kwh": result["energy_saved_kwh"], "money_saved_usd": result["money_saved_usd"],
        "conditions": {k: c.get(k) for k in ("summary", "migration_level", "sky_danger", "sky_cover",
                                             "fog", "wind_dir", "wind_speed_mph")},
    }
    (OUT / "demo.json").write_text(json.dumps(data, indent=1))
    offs = sum(a.state == "off" for a in actions)
    print(f"{len(windows)} windows, {offs} off, {len(actions) - offs} dimmed, by {result['source']}")
    print(f"risk {result['risk_before']:.2f} -> {result['risk_after']:.2f}")
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
