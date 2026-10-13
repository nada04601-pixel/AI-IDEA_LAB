"""차이점 만들기.

1) 장면 기반(make_scene_differences): 내장 장면의 소품 데이터를 바꿔 다시 그린다.
   구도가 100% 같고, 정답 좌표는 바뀐 소품의 상자에서 정확히 계산된다. (기본 경로)
2) 래스터 기반(make_raster_differences): ComfyUI·샘플 사진처럼 소품 데이터가 없는 그림.
   디테일이 많은 영역을 골라 색 바꾸기·좌우 반전·무늬 덧입히기·소품 붙이기·지우기를 한다.
   의미 있는 물체를 고른다는 보장이 약하므로 결과에 review 표시를 붙인다.
"""
from __future__ import annotations

import colorsys
import random
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .props import C, PATTERNS, SWAP_COLORS, VARIANTS, Prop, color_distance, render_prop, rgb
from .scenes import COLOR_ATTR, Scene, render_scene

TYPE_LABELS = {
    "object_added": "추가",
    "object_removed": "사라짐",
    "color_changed": "색깔",
    "shape_changed": "모양",
    "pattern_changed": "무늬",
    "direction_changed": "방향",
}
PAD = 8  # 수채화 번짐을 감싸기 위한 여백(px)
MIN_GAP = 0.025  # 정답 상자 사이 최소 간격 (이미지 짧은 변 대비)
MIN_PROP_SIDE = 52  # 이보다 작은 소품은 휴대폰에서 알아보기 어려워 차이 후보에서 뺀다(px, 1200x840 기준)


@dataclass
class Difference:
    id: int
    type: str
    label: str
    bbox: tuple[int, int, int, int]  # 픽셀 x0, y0, x1, y1

    def to_json(self, w: int, h: int) -> dict:
        x0, y0, x1, y1 = self.bbox
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "bbox_normalized": [round(x0 / w, 4), round(y0 / h, 4), round(x1 / w, 4), round(y1 / h, 4)],
            "bbox_px": [int(x0), int(y0), int(x1), int(y1)],
        }


def _pad(b, w, h, pad=PAD):
    return (max(0, b[0] - pad), max(0, b[1] - pad), min(w, b[2] + pad), min(h, b[3] + pad))


def circle_footprint(b, w, h):
    """영상에 그릴 정답 원(validator.circle_box)을 감싸는 사각형."""
    from .validator import CIRCLE_SCALE
    hx, hy = (b[2] - b[0]) / 2 * (CIRCLE_SCALE - 1), (b[3] - b[1]) / 2 * (CIRCLE_SCALE - 1)
    return (b[0] - hx, b[1] - hy, b[2] + hx, b[3] + hy)


def boxes_conflict(a, b, gap: float) -> bool:
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def _covered_by_front(scene: Scene, pr: Prop) -> bool:
    """다른 소품이 이 소품 위에 겹쳐 그려지면 차이가 가려질 수 있으므로 후보에서 뺀다."""
    everything = scene.props + scene.extras  # 렌더링과 같은 순서(같은 층이면 먼저 나온 것이 아래)
    for other in everything:
        if other is pr or not other.visible or other.layer < pr.layer:
            continue
        if other.layer == pr.layer and everything.index(other) < everything.index(pr):
            continue
        if boxes_conflict(pr.bbox(), other.bbox(), 0):
            return True
    return False


def _new_color(pr: Prop, rng: random.Random) -> tuple[str, object]:
    attr = COLOR_ATTR.get(pr.kind, "color")
    cur = rgb(getattr(pr, attr) or "earth")
    if pr.kind == "persimmon":
        choices = ["green", "red", "yellow"]
    else:
        choices = list(SWAP_COLORS)
    rng.shuffle(choices)
    choices.sort(key=lambda n: -color_distance(rgb(n), cur))
    return attr, choices[0]


def apply_op(pr: Prop, op: str, rng: random.Random) -> Prop:
    if op == "object_removed":
        return pr.copy(visible=False)
    if op == "object_added":
        return pr.copy(visible=True)
    if op == "color_changed":
        attr, col = _new_color(pr, rng)
        return pr.copy(**{attr: col})
    if op == "shape_changed":
        n = VARIANTS.get(pr.kind, 2)
        return pr.copy(variant=rng.choice([v for v in range(n) if v != pr.variant]))
    if op == "pattern_changed":
        if pr.pattern == "plain":
            return pr.copy(pattern=rng.choice(PATTERNS))
        return pr.copy(pattern=rng.choice(["plain"] + [p for p in PATTERNS if p != pr.pattern]))
    if op == "direction_changed":
        return pr.copy(flipped=not pr.flipped)
    raise ValueError(op)


def make_scene_differences(scene: Scene, count: int, rng: random.Random) -> tuple[Image.Image, Image.Image, list[Difference], Scene]:
    """장면에서 count개의 차이를 골라 원본/수정본 이미지와 정답 목록을 돌려준다."""
    w, h = scene.width, scene.height
    gap = MIN_GAP * min(w, h)

    candidates: list[tuple[Prop, str]] = []
    def big_enough(pr: Prop) -> bool:
        return min(pr.box[2], pr.box[3]) >= MIN_PROP_SIDE

    for pr in scene.props:
        if not pr.visible or not big_enough(pr) or _covered_by_front(scene, pr):
            continue
        for op in pr.ops:
            candidates.append((pr, op))
    for pr in scene.extras:
        if big_enough(pr):
            candidates.append((pr, "object_added"))
    rng.shuffle(candidates)

    # 차이 유형이 골고루 섞이도록: 유형별 사용 횟수가 적은 쪽을 먼저
    chosen: list[tuple[Prop, str]] = []
    used_types: dict[str, int] = {}
    used_ids: set[str] = set()
    pool = list(candidates)
    while len(chosen) < count and pool:
        pool.sort(key=lambda c: used_types.get(c[1], 0))
        picked = None
        for cand in pool:
            pr, op = cand
            if pr.id in used_ids:
                continue
            box = circle_footprint(_pad(pr.bbox(), w, h), w, h)
            if any(boxes_conflict(box, circle_footprint(_pad(c[0].bbox(), w, h), w, h), gap) for c in chosen):
                continue
            picked = cand
            break
        if picked is None:
            break
        pool.remove(picked)
        chosen.append(picked)
        used_ids.add(picked[0].id)
        used_types[picked[1]] = used_types.get(picked[1], 0) + 1
    if len(chosen) < count:
        raise RuntimeError(f"서로 떨어진 차이 후보가 부족합니다 ({len(chosen)}/{count})")

    modified = Scene.from_dict(scene.to_dict())
    by_id = {p.id: p for p in modified.props + modified.extras}
    diffs: list[Difference] = []
    for i, (pr, op) in enumerate(chosen, start=1):
        new = apply_op(by_id[pr.id], op, rng)
        target = modified.props if any(p.id == pr.id for p in modified.props) else modified.extras
        idx = next(k for k, p in enumerate(target) if p.id == pr.id)
        target[idx] = new
        diffs.append(Difference(i, op, pr.label, _pad(pr.bbox(), w, h)))

    # 화면 위→아래, 왼→오 순서로 번호를 다시 매긴다 (정답 공개 순서)
    diffs.sort(key=lambda d: (round(d.bbox[1] / (h / 4)), d.bbox[0]))
    for i, d in enumerate(diffs, start=1):
        d.id = i
    original = render_scene(scene)
    edited = render_scene(modified)
    return original, edited, diffs, modified


# ---------------------------------------------------------------------------
# 래스터 기반 (ComfyUI / 샘플 이미지)
# ---------------------------------------------------------------------------

def _detail_map(img: Image.Image, cell: int) -> np.ndarray:
    g = np.asarray(img.convert("L"), float)
    gx = np.abs(np.diff(g, axis=1, prepend=g[:, :1]))
    gy = np.abs(np.diff(g, axis=0, prepend=g[:1, :]))
    e = gx + gy
    hh, ww = g.shape[0] // cell, g.shape[1] // cell
    e = e[: hh * cell, : ww * cell].reshape(hh, cell, ww, cell).mean(axis=(1, 3))
    return e


def _ellipse_mask(size, feather=6) -> Image.Image:
    w, h = size
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).ellipse([feather, feather, w - feather, h - feather], fill=255)
    return m.filter(ImageFilter.GaussianBlur(feather / 2))


def _hue_shift(region: Image.Image, shift: float) -> Image.Image:
    hsv = np.asarray(region.convert("HSV"), float)
    hsv[..., 0] = (hsv[..., 0] + shift * 255) % 255
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.25 + 25, 0, 255)
    return Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")


def make_raster_differences(base: Image.Image, count: int, rng: random.Random,
                            font_path: str | None = None) -> tuple[Image.Image, Image.Image, list[Difference]]:
    img = base.convert("RGB")
    w, h = img.size
    cell = max(24, min(w, h) // 14)
    det = _detail_map(img, cell)
    size = int(min(w, h) * 0.16)
    gap = MIN_GAP * min(w, h)
    margin = int(min(w, h) * 0.04)

    # 디테일 높은 칸(물체일 가능성) 후보와 낮은 칸(소품을 놓을 빈 곳) 후보
    order = np.dstack(np.unravel_index(np.argsort(-det, axis=None), det.shape))[0]
    busy = [(int(c * cell + cell / 2), int(r * cell + cell / 2)) for r, c in order[: len(order) // 3]]
    calm = [(int(c * cell + cell / 2), int(r * cell + cell / 2)) for r, c in order[-len(order) // 3:]]
    rng.shuffle(busy)
    rng.shuffle(calm)

    ops_cycle = ["color_changed", "direction_changed", "object_added", "pattern_changed", "object_removed",
                 "color_changed", "object_added"]
    rng.shuffle(ops_cycle)
    edited = img.copy()
    diffs: list[Difference] = []
    for op in (ops_cycle * 3):
        if len(diffs) >= count:
            break
        pool = calm if op == "object_added" else busy
        while pool:
            cx, cy = pool.pop()
            x0 = int(min(max(margin, cx - size / 2), w - margin - size))
            y0 = int(min(max(margin, cy - size / 2), h - margin - size))
            box = (x0, y0, x0 + size, y0 + size)
            if any(boxes_conflict(box, d.bbox, gap) for d in diffs):
                continue
            break
        else:
            continue
        region = edited.crop(box)
        mask = _ellipse_mask(region.size)
        label = "그림 일부"
        if op == "color_changed":
            new = _hue_shift(region, rng.choice([0.33, 0.5, 0.66]))
            label = "색이 바뀐 부분"
        elif op == "direction_changed":
            new = region.transpose(Image.FLIP_LEFT_RIGHT)
            label = "좌우가 뒤집힌 부분"
        elif op == "pattern_changed":
            from .props import pattern_tile
            tex = pattern_tile(region.size, (255, 255, 255), "stripes", accent=(120, 70, 50)).convert("RGB")
            new = Image.blend(region, tex, 0.35)
            label = "무늬가 생긴 부분"
        elif op == "object_removed":
            # 바로 옆(위쪽) 칸을 복사해 덮는다. 단순한 방식이라 결과를 사람이 확인해야 한다.
            sy = max(0, y0 - size) if y0 - size >= 0 else min(h - size, y0 + size)
            new = edited.crop((x0, sy, x0 + size, sy + size))
            label = "사라진 부분"
        else:  # object_added
            kind = rng.choice(["jar", "basket", "pot", "kettle", "flowerpot", "bucket"])
            pr = Prop(id="added", kind=kind, label="", box=(0, 0, int(size * 0.8), int(size * 0.8)),
                      color=rng.choice(["red", "blue", "yellow", "onggi"]), color2="persimmon")
            tile = render_prop(pr)
            new = region.copy()
            new.paste(tile, (int(size * 0.1), int(size * 0.1)), tile)
            mask = Image.new("L", region.size, 255)
            label = {"jar": "장독", "basket": "바구니", "pot": "냄비", "kettle": "주전자", "flowerpot": "화분",
                     "bucket": "양동이"}[kind]
        edited.paste(new, box[:2], mask)
        diffs.append(Difference(len(diffs) + 1, op, label, box))
    if len(diffs) < count:
        raise RuntimeError(f"래스터 차이를 {count}개 만들지 못했습니다 ({len(diffs)}개)")
    diffs.sort(key=lambda d: (round(d.bbox[1] / (h / 4)), d.bbox[0]))
    for i, d in enumerate(diffs, start=1):
        d.id = i
    return img, edited, diffs
