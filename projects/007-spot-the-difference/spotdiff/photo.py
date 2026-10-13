"""가지고 있는 그림(AI로 만든 그림 등) 한 장으로 틀린그림 문제 만들기.

원본을 복사한 뒤 둥근 영역 몇 곳만 고친다: 색 바꾸기(color), 좌우 뒤집기(flip),
다른 곳 조각 붙이기(clone). 고친 결과가 눈에 띄는지 확인해서 안 띄면 다시 고른다.
"""

from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .scene import H, W, Difference, Puzzle, _overlaps

# 난이도별: 고칠 영역 반지름 범위와 틀린 곳 개수
LEVELS = {0: ((60, 80), 3), 1: ((45, 65), 4), 2: ((35, 50), 5)}
MIN_VISIBLE = 28  # 고친 영역의 평균 색 차이가 이보다 작으면 안 보인다고 판단
MIN_DETAIL = 22  # 밋밋한 곳(하늘·잔디)을 고치면 얼룩처럼 보이므로 무늬가 있는 곳만 고른다


def _mask(cx, cy, r) -> np.ndarray:
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse([cx - r * 0.8, cy - r * 0.8, cx + r * 0.8, cy + r * 0.8], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(r * 0.12))
    arr = np.asarray(m, dtype=np.float32) / 255.0
    out = np.zeros_like(arr)  # 정답 상자 밖으로 번지지 않게 자른다
    y0, y1, x0, x1 = max(0, cy - r), min(H, cy + r), max(0, cx - r), min(W, cx + r)
    out[y0:y1, x0:x1] = arr[y0:y1, x0:x1]
    return out[..., None]


def _shift_hue(arr: np.ndarray, amount: float) -> np.ndarray:
    hsv = np.asarray(Image.fromarray(arr.astype(np.uint8)).convert("HSV")).astype(np.int32)
    hsv[..., 0] = (hsv[..., 0] + int(amount * 255)) % 256
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.2 + 20, 0, 255)
    return np.asarray(Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")).astype(np.float32)


def load_image(path) -> Image.Image:
    """영상에 들어갈 크기(1000x700)로 가운데를 잘라 맞춘다."""
    return ImageOps.fit(Image.open(path).convert("RGB"), (W, H), Image.LANCZOS)


def make_puzzle_from_image(img: Image.Image, seed: int, level: int = 0) -> Puzzle:
    rng = random.Random(seed)
    img = ImageOps.fit(img.convert("RGB"), (W, H), Image.LANCZOS)
    a = np.asarray(img).astype(np.float32)
    b = a.copy()
    (rmin, rmax), count = LEVELS[level]
    diffs: list[Difference] = []

    for _ in range(2000):
        if len(diffs) == count:
            break
        r = rng.randint(rmin, rmax)
        cx, cy = rng.randint(r + 10, W - r - 10), rng.randint(r + 10, H - r - 10)
        box = (cx - r, cy - r, cx + r, cy + r)
        if any(_overlaps(box, d.box, 20) for d in diffs):
            continue
        y0, y1, x0, x1 = cy - r, cy + r, cx - r, cx + r
        if a[y0:y1, x0:x1].mean(axis=2).std() < MIN_DETAIL:
            continue
        kind = rng.choice(["color", "flip", "clone"])
        edited = b.copy()
        if kind == "color":
            edited[y0:y1, x0:x1] = _shift_hue(b[y0:y1, x0:x1], rng.uniform(0.3, 0.6))
        elif kind == "flip":
            edited[y0:y1, x0:x1] = b[y0:y1, x0:x1][:, ::-1]
        else:
            sx, sy = rng.randint(r, W - r), rng.randint(r, H - r)
            src = (sx - r, sy - r, sx + r, sy + r)
            if _overlaps(src, box, 0) or any(_overlaps(src, d.box, 0) for d in diffs):
                continue
            edited[y0:y1, x0:x1] = a[sy - r:sy + r, sx - r:sx + r]
        m = _mask(cx, cy, r)
        candidate = b * (1 - m) + edited * m
        core = m[..., 0] > 0.5
        visible = np.abs(candidate - b).sum(axis=2)[core].mean() / 3
        if visible < MIN_VISIBLE:
            continue
        b = candidate
        diffs.append(Difference(kind, "region", box))

    if len(diffs) < count:
        raise RuntimeError("이 그림에서는 눈에 띄는 틀린 곳을 충분히 만들지 못했습니다. 더 알록달록한 그림을 써 보세요.")
    return Puzzle(img, Image.fromarray(np.clip(np.rint(b), 0, 255).astype(np.uint8)), diffs)
