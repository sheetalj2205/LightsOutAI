"""A generated night photo of a 7-floor glass building, so the whole pipeline can be
shown before (or without) the real UB photos."""
import cv2
import numpy as np

FLOORS, COLS = 7, 10


def make_demo_photo(seed: int = 7) -> bytes:
    rng = np.random.default_rng(seed)
    H, W = 900, 1200
    img = np.zeros((H, W, 3), np.uint8)
    for y in range(H):  # night sky gradient
        img[y, :] = (40 - y * 25 // H, 22 - y * 12 // H, 14 - y * 8 // H)
    bx0, bx1, by0, by1 = 220, 980, 150, 860
    cv2.rectangle(img, (bx0, by0), (bx1, by1), (38, 34, 32), -1)  # facade
    cv2.rectangle(img, (0, by1), (W, H), (18, 18, 18), -1)  # ground
    cell_w, cell_h = (bx1 - bx0) / COLS, (by1 - by0) / FLOORS
    palette = [(235, 245, 255), (170, 225, 255), (120, 200, 255), (255, 230, 200)]  # BGR
    for f in range(FLOORS):
        for c in range(COLS):
            x = int(bx0 + c * cell_w + cell_w * 0.18)
            y = int(by0 + f * cell_h + cell_h * 0.2)
            w, h = int(cell_w * 0.64), int(cell_h * 0.6)
            floor = FLOORS - f
            lit = floor == 1 or rng.random() < 0.72
            if lit:
                color = np.array(palette[rng.integers(len(palette))], float) * rng.uniform(0.85, 1.0)
                cv2.rectangle(img, (x, y), (x + w, y + h), tuple(int(v) for v in color), -1)
            else:
                cv2.rectangle(img, (x, y), (x + w, y + h), (24, 22, 20), -1)
    img = cv2.GaussianBlur(img, (3, 3), 0)
    noise = rng.normal(0, 3, img.shape)
    img = np.clip(img.astype(float) + noise, 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return buf.tobytes()
