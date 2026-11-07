"""Find lit windows in a night photo of a building.

detect_windows()  - Task 4: bright-blob detection with OpenCV.
detect_grid()     - Task 5: fallback when you give the 4 facade corners + floors/columns.
"""
from pathlib import Path

import cv2
import numpy as np

from .models import Window

MAX_SIDE = 1600  # resize big phone photos before processing (coords are scaled back)


def load_image(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not read the image (expected JPG or PNG)")
    return img


def _main_color(bgr_pixels: np.ndarray) -> str:
    if bgr_pixels.size == 0:
        return "white"
    mean = bgr_pixels.reshape(-1, 3).mean(axis=0).astype(np.uint8).reshape(1, 1, 3)
    h, s, _ = cv2.cvtColor(mean, cv2.COLOR_BGR2HSV)[0, 0]
    if s < 60:
        return "white"
    if h < 10 or h > 160:
        return "red"
    if h < 20:
        return "orange"
    if h < 35:
        return "yellow"
    if h < 85:
        return "green"
    return "blue"


def _cluster(values: list[float], tol: float) -> list[int]:
    """Group 1-D positions into rows/columns. Returns a group index per value (sorted ascending)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    labels = [0] * len(values)
    group, last = 0, None
    for i in order:
        if last is not None and values[i] - last > tol:
            group += 1
        labels[i] = group
        last = values[i]
    return labels


def _assign_floors_cols(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int]]:
    """Floor 1 = bottom row, col 1 = leftmost."""
    if not boxes:
        return []
    med_w = float(np.median([b[2] for b in boxes]))
    med_h = float(np.median([b[3] for b in boxes]))
    rows = _cluster([b[1] + b[3] / 2 for b in boxes], tol=0.6 * med_h)
    cols = _cluster([b[0] + b[2] / 2 for b in boxes], tol=0.6 * med_w)
    n_rows = max(rows) + 1
    return [(n_rows - r, c + 1) for r, c in zip(rows, cols)]


def detect_windows(img: np.ndarray, threshold: int = 200) -> list[Window]:
    """Bright-pixel detection: grayscale -> keep bright pixels -> window-sized rectangles."""
    h0, w0 = img.shape[:2]
    scale = min(1.0, MAX_SIDE / max(h0, w0))
    small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else img
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_img = small.shape[0] * small.shape[1]
    boxes, stats = [], []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area < max(30, area_img * 0.00005) or area > area_img * 0.05:
            continue  # noise or a huge glare blob, not a window
        if not 0.2 <= w / h <= 5:
            continue  # streetlight streaks, edges
        if cv2.contourArea(c) / area < 0.4:
            continue  # irregular shape
        roi_gray = gray[y:y + h, x:x + w]
        roi_mask = mask[y:y + h, x:x + w] > 0
        brightness = float(roi_gray.mean()) / 255
        color = _main_color(small[y:y + h, x:x + w][roi_mask])
        boxes.append((x, y, w, h))
        stats.append((brightness, color))

    floors_cols = _assign_floors_cols(boxes)
    inv = 1 / scale
    windows = []
    # Number windows bottom-to-top, left-to-right so ids read like the building.
    order = sorted(range(len(boxes)), key=lambda i: (floors_cols[i][0], floors_cols[i][1], boxes[i][0]))
    for new_id, i in enumerate(order, start=1):
        x, y, w, h = boxes[i]
        floor, col = floors_cols[i]
        brightness, color = stats[i]
        windows.append(Window(
            id=new_id, floor=floor, col=col,
            x=round(x * inv), y=round(y * inv), w=round(w * inv), h=round(h * inv),
            state="on", brightness=round(min(brightness, 1.0), 3), color=color,
        ))
    return windows


def detect_grid(img: np.ndarray, corners: list[list[float]], floors: int, cols: int,
                lit_threshold: int = 110) -> list[Window]:
    """Fallback: straighten the facade from 4 corners (top-left, top-right, bottom-right,
    bottom-left, in image pixels) and check each floors x cols cell for light."""
    if len(corners) != 4:
        raise ValueError("corners must be 4 points: top-left, top-right, bottom-right, bottom-left")
    cell_w, cell_h = 60, 80
    W, H = cols * cell_w, floors * cell_h
    src = np.array(corners, dtype=np.float32)
    dst = np.array([[0, 0], [W, 0], [W, H], [0, H]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    M_inv = np.linalg.inv(M)
    flat = cv2.warpPerspective(img, M, (W, H))
    gray = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)

    windows = []
    wid = 0
    for f in range(floors):  # f=0 is the top row in the straightened image
        floor = floors - f
        for c in range(cols):
            x0, y0 = c * cell_w, f * cell_h
            mx, my = int(cell_w * 0.2), int(cell_h * 0.2)  # ignore frames/mullions
            inner = gray[y0 + my:y0 + cell_h - my, x0 + mx:x0 + cell_w - mx]
            level = float(inner.mean())
            cell_px = np.array([[[x0, y0]], [[x0 + cell_w, y0]], [[x0 + cell_w, y0 + cell_h]],
                                [[x0, y0 + cell_h]]], dtype=np.float32)
            back = cv2.perspectiveTransform(cell_px, M_inv)
            bx, by, bw, bh = cv2.boundingRect(back.astype(np.int32))
            color_px = flat[y0 + my:y0 + cell_h - my, x0 + mx:x0 + cell_w - mx]
            wid += 1
            windows.append(Window(
                id=wid, floor=floor, col=c + 1, x=bx, y=by, w=bw, h=bh,
                state="on" if level >= lit_threshold else "off",
                brightness=round(level / 255, 3),
                color=_main_color(color_px) if level >= lit_threshold else "white",
            ))
    # Re-number bottom-to-top, left-to-right to match detect_windows.
    windows.sort(key=lambda w: (w.floor, w.col))
    return [w.model_copy(update={"id": i}) for i, w in enumerate(windows, start=1)]


def _risk_color(r: float) -> tuple[int, int, int]:
    """Green (safe) -> amber -> red (dangerous), in BGR."""
    t = min(max(r / 0.7, 0.0), 1.0)
    green, amber, red = np.array([90, 200, 60]), np.array([0, 190, 255]), np.array([50, 50, 235])
    c = green + (amber - green) * (t / 0.5) if t < 0.5 else amber + (red - amber) * ((t - 0.5) / 0.5)
    return tuple(int(v) for v in c)


def save_debug_image(img: np.ndarray, windows: list[Window], path: Path) -> Path:
    """Draw a box + id on every window, colored by risk, plus a small legend."""
    out = img.copy()
    side = max(img.shape[:2])
    thick = max(2, round(side / 600))
    font = 0.35 * max(1, side / 900)
    pad = thick + 1
    for w in windows:
        color = _risk_color(w.risk) if w.state != "off" else (130, 130, 130)
        cv2.rectangle(out, (w.x - pad, w.y - pad), (w.x + w.w + pad, w.y + w.h + pad), color, thick)
        cv2.putText(out, str(w.id), (w.x - pad, max(w.y - pad - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX,
                    font, color, max(1, thick // 2), cv2.LINE_AA)
    # Legend: "LIGHTS OUT AI  low risk [====] high risk  N windows"
    lh = int(28 * max(1, side / 900))
    cv2.rectangle(out, (0, 0), (out.shape[1], lh + 12), (20, 14, 10), -1)
    y = lh // 2 + 10
    cv2.putText(out, "LIGHTS OUT AI", (12, y), cv2.FONT_HERSHEY_SIMPLEX, font * 1.4, (240, 240, 240),
                max(1, thick // 2 + 1), cv2.LINE_AA)
    x0 = int(out.shape[1] * 0.35)
    bar_w = int(out.shape[1] * 0.25)
    cv2.putText(out, "low risk", (x0 - int(70 * font / 0.35), y), cv2.FONT_HERSHEY_SIMPLEX, font,
                (200, 200, 200), 1, cv2.LINE_AA)
    for i in range(bar_w):
        cv2.line(out, (x0 + i, y - lh // 3), (x0 + i, y + lh // 6), _risk_color(0.7 * i / bar_w), 1)
    cv2.putText(out, "high risk", (x0 + bar_w + 8, y), cv2.FONT_HERSHEY_SIMPLEX, font, (200, 200, 200), 1,
                cv2.LINE_AA)
    lit = sum(1 for w in windows if w.state != "off")
    cv2.putText(out, f"{lit} lit windows", (int(out.shape[1] * 0.78), y), cv2.FONT_HERSHEY_SIMPLEX, font,
                (200, 200, 200), 1, cv2.LINE_AA)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), out)
    return path


def save_after_image(img: np.ndarray, windows: list[Window], path: Path) -> Path:
    """The same photo with the windows that are off darkened and dimmed ones toned down
    (for the before/after view)."""
    out = img.copy()
    H, W = out.shape[:2]
    for w in windows:
        if w.state == "on":
            continue
        p = max(3, round(min(w.w, w.h) * 0.12))  # also cover the glow around the window
        x0, y0, x1, y1 = max(w.x - p, 0), max(w.y - p, 0), min(w.x + w.w + p, W), min(w.y + w.h + p, H)
        factor = 0.1 if w.state == "off" else 0.45
        roi = out[y0:y1, x0:x1].astype(np.float32)
        gray = cv2.cvtColor(out[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)
        # Window itself: darken fully. Ring around it: darken only the glow (pixels brighter
        # than the facade around it), so no black frame appears.
        ring_level = np.median(np.concatenate([gray[0], gray[-1], gray[:, 0], gray[:, -1]]))
        glow = np.clip((gray - ring_level) / 40.0, 0, 1)
        inside = np.zeros_like(gray)
        inside[w.y - y0:w.y - y0 + w.h, w.x - x0:w.x - x0 + w.w] = 1
        amount = np.maximum(inside, glow)[..., None]  # 1 = fully darkened
        dark = np.minimum(roi * factor, ring_level) if w.state == "off" else roi * factor
        out[y0:y1, x0:x1] = (roi * (1 - amount) + dark * amount).astype(np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), out)
    return path
