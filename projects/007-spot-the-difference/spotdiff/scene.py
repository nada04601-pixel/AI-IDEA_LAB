"""코드로 그린 풍경 그림 + 틀린 곳 만들기.

그림을 '물체 목록'으로 표현하고, 그림 B는 물체 몇 개만 지우거나(remove)
색을 바꾸거나(recolor) 새로 추가(add)해서 다시 그린다. 그래서 두 그림은
바꾼 물체의 영역 안에서만 다르고, 그 영역이 곧 정답 위치가 된다.
"""

from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

W, H = 1000, 700  # 그림 한 장의 크기 (영상에 그대로 붙인다)
SS = 2  # 2배로 그린 뒤 줄여서 테두리를 부드럽게 만든다
GROUND_Y = 470

PALETTE = [
    (230, 57, 70), (255, 159, 28), (255, 214, 10), (46, 196, 182),
    (58, 134, 255), (131, 56, 236), (255, 0, 110), (255, 255, 255),
    (40, 40, 40), (120, 72, 40), (0, 150, 80), (255, 140, 180),
]


@dataclass
class Obj:
    kind: str
    x: float
    y: float
    size: float
    color: tuple
    removable: bool = True
    recolorable: bool = True
    extra: dict = field(default_factory=dict)


@dataclass
class Difference:
    type: str  # remove | recolor | add
    kind: str
    box: tuple  # (x0, y0, x1, y1) 그림 좌표

    def to_dict(self) -> dict:
        return {"type": self.type, "object": self.kind, "box": list(self.box)}


@dataclass
class Puzzle:
    image_a: Image.Image
    image_b: Image.Image
    differences: list


# ---------------------------------------------------------------- 그리기


def _s(v):
    return v * SS


def _ellipse(d, cx, cy, rx, ry, fill, outline=None, width=0):
    d.ellipse([_s(cx - rx), _s(cy - ry), _s(cx + rx), _s(cy + ry)], fill=fill,
              outline=outline, width=_s(width) if width else 0)


def _rect(d, x0, y0, x1, y1, fill, outline=None, width=0):
    d.rectangle([_s(x0), _s(y0), _s(x1), _s(y1)], fill=fill, outline=outline,
                width=_s(width) if width else 0)


def _darker(c, k=0.7):
    return tuple(int(v * k) for v in c)


def draw_obj(d: ImageDraw.ImageDraw, o: Obj) -> None:
    x, y, s, c = o.x, o.y, o.size, o.color
    if o.kind == "sun":
        for i in range(8):
            a = i * math.pi / 4
            d.line([_s(x + math.cos(a) * s * 1.2), _s(y + math.sin(a) * s * 1.2),
                    _s(x + math.cos(a) * s * 1.55), _s(y + math.sin(a) * s * 1.55)],
                   fill=c, width=_s(5))
        _ellipse(d, x, y, s, s, c)
    elif o.kind == "cloud":
        for dx, dy, r in ((-0.9, 0.15, 0.55), (0, -0.2, 0.75), (0.9, 0.15, 0.55), (0.35, 0.25, 0.6), (-0.35, 0.25, 0.6)):
            _ellipse(d, x + dx * s, y + dy * s, r * s, r * s * 0.85, c)
    elif o.kind == "house_body":
        _rect(d, x, y, x + s, y + s * 0.8, c, outline=_darker(c), width=3)
    elif o.kind == "roof":
        w = o.extra["w"]
        d.polygon([(_s(x - 20), _s(y)), (_s(x + w / 2), _s(y - s)), (_s(x + w + 20), _s(y))], fill=c)
    elif o.kind == "chimney":
        _rect(d, x, y, x + s * 0.5, y + s, c, outline=_darker(c), width=2)
    elif o.kind == "door":
        _rect(d, x, y, x + s * 0.6, y + s, c, outline=_darker(c), width=3)
        _ellipse(d, x + s * 0.48, y + s * 0.55, 4, 4, (255, 214, 10))
    elif o.kind == "window":
        _rect(d, x, y, x + s, y + s, c, outline=(255, 255, 255), width=5)
        d.line([_s(x + s / 2), _s(y), _s(x + s / 2), _s(y + s)], fill=(255, 255, 255), width=_s(4))
        d.line([_s(x), _s(y + s / 2), _s(x + s), _s(y + s / 2)], fill=(255, 255, 255), width=_s(4))
    elif o.kind == "trunk":
        _rect(d, x - s * 0.18, y - s, x + s * 0.18, y, c)
    elif o.kind == "crown":
        for dx, dy, r in ((0, -0.35, 0.6), (-0.45, 0.05, 0.5), (0.45, 0.05, 0.5), (0, 0.2, 0.55)):
            _ellipse(d, x + dx * s, y + dy * s, r * s, r * s, c)
    elif o.kind == "apple":
        _ellipse(d, x, y, s, s, c)
        d.line([_s(x), _s(y - s), _s(x + 2), _s(y - s - 6)], fill=(90, 50, 20), width=_s(3))
    elif o.kind == "flower":
        d.line([_s(x), _s(y), _s(x), _s(y + s * 2.2)], fill=(30, 120, 50), width=_s(4))
        for i in range(5):
            a = i * 2 * math.pi / 5
            _ellipse(d, x + math.cos(a) * s * 0.6, y + math.sin(a) * s * 0.6, s * 0.5, s * 0.5, c)
        _ellipse(d, x, y, s * 0.38, s * 0.38, (255, 214, 10) if c != (255, 214, 10) else (230, 57, 70))
    elif o.kind == "bird":
        d.arc([_s(x - s), _s(y - s * 0.5), _s(x), _s(y + s * 0.5)], 200, 340, fill=c, width=_s(5))
        d.arc([_s(x), _s(y - s * 0.5), _s(x + s), _s(y + s * 0.5)], 200, 340, fill=c, width=_s(5))
    elif o.kind == "balloon":
        d.line([_s(x), _s(y + s * 1.2), _s(x + 6), _s(y + s * 3)], fill=(80, 80, 80), width=_s(2))
        _ellipse(d, x, y, s, s * 1.2, c)
        _ellipse(d, x - s * 0.35, y - s * 0.45, s * 0.18, s * 0.25, (255, 255, 255))
    elif o.kind == "mushroom":
        _rect(d, x - s * 0.25, y - s * 0.6, x + s * 0.25, y, (245, 235, 215))
        d.pieslice([_s(x - s), _s(y - s * 1.4), _s(x + s), _s(y - s * 0.2)], 180, 360, fill=c)
        for dx in (-0.5, 0, 0.5):
            _ellipse(d, x + dx * s, y - s * 0.95 + abs(dx) * s * 0.3, s * 0.14, s * 0.14, (255, 255, 255))
    elif o.kind == "butterfly":
        for sx in (-1, 1):
            _ellipse(d, x + sx * s * 0.5, y - s * 0.3, s * 0.5, s * 0.4, c)
            _ellipse(d, x + sx * s * 0.4, y + s * 0.3, s * 0.35, s * 0.3, _darker(c, 0.8))
        _rect(d, x - 3, y - s * 0.6, x + 3, y + s * 0.6, (40, 40, 40))
    elif o.kind == "star":
        pts = []
        for i in range(10):
            r = s if i % 2 == 0 else s * 0.45
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((_s(x + math.cos(a) * r), _s(y + math.sin(a) * r)))
        d.polygon(pts, fill=c)
    else:
        raise ValueError(o.kind)


def bbox(o: Obj) -> tuple:
    """물체가 칠하는 영역 (여유 4px 포함)."""
    x, y, s = o.x, o.y, o.size
    k = o.kind
    if k == "sun":
        b = (x - s * 1.6, y - s * 1.6, x + s * 1.6, y + s * 1.6)
    elif k == "cloud":
        b = (x - 1.45 * s, y - 0.95 * s, x + 1.45 * s, y + 0.8 * s)
    elif k == "house_body":
        b = (x, y, x + s, y + s * 0.8)
    elif k == "roof":
        b = (x - 20, y - s, x + o.extra["w"] + 20, y)
    elif k == "chimney":
        b = (x, y, x + s * 0.5, y + s)
    elif k == "door":
        b = (x, y, x + s * 0.6, y + s)
    elif k == "window":
        b = (x, y, x + s, y + s)
    elif k == "trunk":
        b = (x - s * 0.18, y - s, x + s * 0.18, y)
    elif k == "crown":
        b = (x - 0.95 * s, y - 0.95 * s, x + 0.95 * s, y + 0.75 * s)
    elif k == "apple":
        b = (x - s, y - s - 7, x + s + 3, y + s)
    elif k == "flower":
        b = (x - 1.1 * s, y - 1.1 * s, x + 1.1 * s, y + 2.2 * s)
    elif k == "bird":
        b = (x - s, y - s * 0.5, x + s, y + s * 0.5)
    elif k == "balloon":
        b = (x - s, y - s * 1.2, x + s, y + s * 3)
    elif k == "mushroom":
        b = (x - s, y - s * 1.4, x + s, y)
    elif k == "butterfly":
        b = (x - s, y - s * 0.7, x + s, y + s * 0.6)
    elif k == "star":
        b = (x - s, y - s, x + s, y + s)
    else:
        raise ValueError(k)
    p = 4
    return (max(0, int(b[0] - p)), max(0, int(b[1] - p)), min(W, int(b[2] + p + 1)), min(H, int(b[3] + p + 1)))


def render(objs: list[Obj], sky: tuple, ground: tuple) -> Image.Image:
    img = Image.new("RGB", (_s(W), _s(H)), sky)
    d = ImageDraw.Draw(img)
    top = tuple(min(255, v + 60) for v in sky)
    for yy in range(_s(GROUND_Y)):  # 하늘 그라데이션
        t = yy / _s(GROUND_Y)
        d.line([(0, yy), (_s(W), yy)], fill=tuple(int(top[i] * (1 - t) + sky[i] * t) for i in range(3)))
    _ellipse(d, 250, GROUND_Y + 40, 420, 120, _darker(ground, 0.9))
    _ellipse(d, 820, GROUND_Y + 50, 380, 100, _darker(ground, 0.85))
    _rect(d, 0, GROUND_Y, W, H, ground)
    for o in objs:
        draw_obj(d, o)
    return img.resize((W, H), Image.LANCZOS)


# ---------------------------------------------------------------- 풍경 만들기


def build_scene(rng: random.Random) -> tuple[list[Obj], tuple, tuple]:
    sky = rng.choice([(110, 180, 240), (120, 200, 235), (150, 170, 240)])
    ground = rng.choice([(110, 190, 90), (130, 200, 100), (95, 175, 105)])
    objs: list[Obj] = []

    sun_left = rng.random() < 0.5
    objs.append(Obj("sun", rng.uniform(90, 150) if sun_left else rng.uniform(850, 910), rng.uniform(85, 110), 45,
                    (255, 205, 40)))
    cloud_xs = [rng.uniform(300, 420), rng.uniform(560, 700)]
    for cx in cloud_xs:
        objs.append(Obj("cloud", cx, rng.uniform(80, 150), rng.uniform(40, 55), (255, 255, 255)))

    # 집 (왼쪽 또는 오른쪽)
    house_left = rng.random() < 0.5
    hx = rng.uniform(80, 140) if house_left else rng.uniform(600, 660)
    hw = 260
    hy = GROUND_Y + 40 - hw * 0.8
    body_c = rng.choice([(245, 222, 179), (255, 228, 196), (210, 230, 250), (250, 240, 200)])
    roof_c = rng.choice([(200, 60, 50), (120, 70, 50), (60, 90, 160)])
    objs.append(Obj("chimney", hx + hw * 0.7, hy - 95, 70, (150, 80, 60)))
    objs.append(Obj("house_body", hx, hy, hw, body_c, removable=False))
    objs.append(Obj("roof", hx, hy, 110, roof_c, removable=False, extra={"w": hw}))
    objs.append(Obj("door", hx + hw * 0.42, hy + hw * 0.8 - 100, 100, (140, 85, 50)))
    objs.append(Obj("window", hx + 25, hy + 35, 62, (150, 210, 250)))
    objs.append(Obj("window", hx + hw - 87, hy + 35, 62, (150, 210, 250)))

    # 나무와 사과
    tree_x = rng.uniform(560, 620) if house_left else rng.uniform(330, 400)
    objs.append(Obj("trunk", tree_x, GROUND_Y + 50, 150, (120, 80, 45), removable=False, recolorable=False))
    objs.append(Obj("crown", tree_x, GROUND_Y - 150, 110, (40, 150, 70), removable=False))
    for dx, dy in rng.sample([(-50, -170), (40, -200), (60, -120), (-60, -110), (0, -230), (5, -140)], 3):
        objs.append(Obj("apple", tree_x + dx, GROUND_Y + dy, 13, (220, 40, 40)))

    # 풍선
    bx = rng.uniform(470, 520)
    objs.append(Obj("balloon", bx, rng.uniform(300, 330), 32, rng.choice(PALETTE[:7])))

    # 새 두 마리: 집·나무·풍선·구름에 가리지 않는 하늘 위치에
    birds = 0
    while birds < 2:
        bird = Obj("bird", rng.uniform(200, 800), rng.uniform(170, 270), rng.uniform(14, 20), (50, 50, 60))
        if not any(_overlaps(bbox(bird), bbox(o), 6) for o in objs):
            objs.append(bird)
            birds += 1

    # 땅 위 소품 (집·나무를 피해 아래쪽에)
    for i in range(5):
        fx = 60 + i * 200 + rng.uniform(-30, 30)
        objs.append(Obj("flower", fx, rng.uniform(600, 625), rng.uniform(17, 22), rng.choice(PALETTE[:7])))
    objs.append(Obj("mushroom", rng.uniform(150, 850), 690, 30, (220, 50, 50)))
    objs.append(Obj("butterfly", rng.uniform(150, 850), rng.uniform(540, 560), 24, rng.choice(PALETTE[:7])))
    return objs, sky, ground


def _overlaps(a, b, margin=12) -> bool:
    return not (a[2] + margin <= b[0] or b[2] + margin <= a[0] or a[3] + margin <= b[1] or b[3] + margin <= a[1])


def _area(b) -> int:
    return (b[2] - b[0]) * (b[3] - b[1])


def _far_color(rng, c):
    choices = [p for p in PALETTE if sum((p[i] - c[i]) ** 2 for i in range(3)) ** 0.5 > 150]
    return rng.choice(choices)


def _add_candidates(rng, objs) -> list[Obj]:
    """새로 넣을 수 있는 물체 후보."""
    cands = [Obj("star", rng.uniform(220, 780), rng.uniform(40, 200), 18, (255, 230, 80))]
    crown = next(o for o in objs if o.kind == "crown")
    cands.append(Obj("apple", crown.x + rng.uniform(-70, 70), crown.y + rng.uniform(-60, 30), 13, (220, 40, 40)))
    cands.append(Obj("bird", rng.uniform(220, 780), rng.uniform(170, 280), 17, (50, 50, 60)))
    cands.append(Obj("flower", rng.uniform(60, 940), rng.uniform(560, 640), 18, rng.choice(PALETTE[:7])))
    cands.append(Obj("mushroom", rng.uniform(60, 940), rng.uniform(640, 690), 24, (180, 110, 60)))
    return cands


# 난이도별: 고를 수 있는 최소 크기(작을수록 어렵다)와 틀린 곳 개수
LEVELS = {0: (3200, 3), 1: (1500, 4), 2: (0, 5)}


def make_puzzle(seed: int, level: int = 0) -> Puzzle:
    """seed와 난이도로 틀린그림 문제 하나를 만든다."""
    rng = random.Random(seed)
    objs, sky, ground = build_scene(rng)
    min_area, count = LEVELS[level]

    for _attempt in range(200):
        b_objs = copy.deepcopy(objs)
        diffs: list[Difference] = []
        options = []
        for i, o in enumerate(objs):
            if _area(bbox(o)) < min_area:
                continue
            if o.removable:
                options.append(("remove", i))
            if o.recolorable:
                options.append(("recolor", i))
        for c in _add_candidates(rng, objs):
            if _area(bbox(c)) >= min_area or level >= 1:
                options.append(("add", c))
        rng.shuffle(options)
        used: set[int] = set()
        removed: set[int] = set()
        for typ, target in options:
            if len(diffs) == count:
                break
            if typ == "add":
                box = bbox(target)
            else:
                if target in used:
                    continue
                box = bbox(objs[target])
            if any(_overlaps(box, d.box) for d in diffs):
                continue
            # 추가하는 물체는 다른 물체와 겹치지 않을 때만 (가려지면 안 보이니까)
            if typ == "add" and any(_overlaps(box, bbox(o), 2) for o in objs
                                    if not (target.kind == "apple" and o.kind == "crown")):
                continue
            if typ == "remove":
                removed.add(target)
            elif typ == "recolor":
                b_objs[target].color = _far_color(rng, objs[target].color)
            else:
                b_objs.append(target)
            if typ != "add":
                used.add(target)
            diffs.append(Difference(typ, target.kind if typ == "add" else objs[target].kind, box))
        if len(diffs) == count:
            b_objs = [o for i, o in enumerate(b_objs) if i not in removed]
            img_a = render(objs, sky, ground)
            img_b = render(b_objs, sky, ground)
            return Puzzle(img_a, img_b, diffs)
    raise RuntimeError("틀린 곳을 충분히 만들지 못했습니다. 다른 seed를 써 보세요.")
