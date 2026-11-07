"""Task 8: run window detection on the real night photos and pick a threshold.

1) Try thresholds on every photo in photos/ (writes debug images to output/tuning/):
       .venv/bin/python scripts/run_photos.py tune
       .venv/bin/python scripts/run_photos.py tune --thresholds 160 180 200 220

2) Save the best photo of a building for the demo (loaded automatically on server start):
       .venv/bin/python scripts/run_photos.py save "Davis Hall" ../photos/davis_1910.jpg --threshold 190

   Grid fallback instead of auto-detection (4 facade corners TL,TR,BR,BL in pixels):
       .venv/bin/python scripts/run_photos.py save "Capen Hall" ../photos/capen.jpg \
           --corners "[[120,340],[2900,300],[2950,2100],[100,2150]]" --floors 6 --cols 14

iPhone HEIC photos: convert first with  sips -s format jpeg in.HEIC --out out.jpg
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config, detection, risk, scenarios  # noqa: E402

EXTS = {".jpg", ".jpeg", ".png"}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def tune(thresholds: list[int]) -> None:
    photos = sorted(p for p in config.PHOTOS_DIR.rglob("*") if p.suffix.lower() in EXTS)
    if not photos:
        print(f"No JPG/PNG photos in {config.PHOTOS_DIR}")
        return
    cond = scenarios.current_conditions()
    print(f"{'photo':40} " + " ".join(f"t={t:<5}" for t in thresholds) + "  (windows found)")
    for p in photos:
        img = detection.load_image(p.read_bytes())
        counts = []
        for t in thresholds:
            wins = risk.score_windows(detection.detect_windows(img, t), cond)
            counts.append(len(wins))
            detection.save_debug_image(img, wins, config.OUTPUT_DIR / "tuning" / f"{p.stem}_t{t}.jpg")
        print(f"{p.name[:40]:40} " + " ".join(f"{c:<7}" for c in counts))
    print(f"\nOpen {config.OUTPUT_DIR / 'tuning'} and pick the threshold whose boxes match the lit windows best.")


def save(name: str, photo: Path, threshold: int, corners, floors, cols) -> None:
    data = photo.read_bytes()
    img = detection.load_image(data)
    if corners:
        wins = detection.detect_grid(img, json.loads(corners), floors, cols)
    else:
        wins = detection.detect_windows(img, threshold)
    wins = risk.score_windows(wins, scenarios.current_conditions())
    folder = config.OUTPUT_DIR / slug(name)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "photo.jpg").write_bytes(data)
    detection.save_debug_image(img, wins, folder / "debug.jpg")
    (folder / "result.json").write_text(json.dumps({
        "building": name, "source_photo": photo.name, "threshold": threshold,
        "corners": json.loads(corners) if corners else None, "floors": floors, "cols": cols,
        "windows": [w.model_dump() for w in wins],
    }, indent=1))
    print(f"Saved {len(wins)} windows for {name} -> {folder}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tune")
    t.add_argument("--thresholds", type=int, nargs="+", default=[160, 180, 200, 220])
    s = sub.add_parser("save")
    s.add_argument("name")
    s.add_argument("photo", type=Path)
    s.add_argument("--threshold", type=int, default=config.DETECT_THRESHOLD)
    s.add_argument("--corners")
    s.add_argument("--floors", type=int)
    s.add_argument("--cols", type=int)
    a = ap.parse_args()
    if a.cmd == "tune":
        tune(a.thresholds)
    else:
        save(a.name, a.photo, a.threshold, a.corners, a.floors, a.cols)
