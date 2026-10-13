"""내장 손그림 장면(GPU 불필요).

장면 = 배경 + 소품 레이어 목록 + (추가 차이용) 숨은 소품 목록.
같은 장면 데이터에서 소품 하나만 바꿔 다시 그리므로 두 그림의 구도가 항상 같다.
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .props import C, DRAWERS, OUTLINE, Painter, Prop, rgb, render_prop, shade

W, H = 1200, 840

DEFAULT_OPS: dict[str, tuple[str, ...]] = {
    "jar": ("object_removed", "color_changed", "shape_changed", "pattern_changed"),
    "persimmon": ("object_removed", "color_changed"),
    "bucket": ("object_removed", "color_changed", "shape_changed"),
    "broom": ("object_removed", "direction_changed", "color_changed"),
    "shoes": ("object_removed", "color_changed", "direction_changed"),
    "pot": ("object_removed", "color_changed", "shape_changed", "pattern_changed"),
    "bowl": ("object_removed", "color_changed", "shape_changed"),
    "basket": ("object_removed", "color_changed", "shape_changed", "pattern_changed"),
    "bicycle": ("object_removed", "direction_changed", "color_changed"),
    "scale": ("object_removed", "color_changed", "shape_changed"),
    "sign": ("color_changed", "shape_changed"),
    "flowerpot": ("object_removed", "color_changed", "shape_changed"),
    "umbrella": ("object_removed", "color_changed", "pattern_changed", "direction_changed"),
    "clothes": ("object_removed", "color_changed", "pattern_changed", "shape_changed"),
    "chicken": ("object_removed", "direction_changed", "color_changed"),
    "bird": ("object_removed", "direction_changed"),
    "cloud": ("object_removed", "shape_changed"),
    "mailbox": ("object_removed", "color_changed"),
    "kettle": ("object_removed", "direction_changed", "color_changed"),
    "cauldron": ("shape_changed",),
    "fire": ("object_removed",),
    "cabbage": ("object_removed", "color_changed"),
    "sack": ("object_removed", "color_changed", "pattern_changed"),
    "kite": ("object_removed", "color_changed", "pattern_changed"),
    "puddle": ("object_removed",),
    "basin": ("object_removed", "color_changed", "pattern_changed"),
    "crate": ("object_removed", "color_changed"),
    "radio": ("object_removed", "color_changed", "pattern_changed"),
}

# 색상 변경 시 바꿀 속성 (화분은 꽃 색)
COLOR_ATTR = {"flowerpot": "color2"}


# ---------------------------------------------------------------------------
# 구조물(배경 쪽 큰 물체) 그리기 — 차이 대상이 아님
# ---------------------------------------------------------------------------

def draw_giwa_house(P: Painter, pr: Prop):
    P.rect(0.08, 0.42, 0.92, 1.0, "cream")  # 벽
    for x in (0.08, 0.3, 0.5, 0.7, 0.92):
        P.line([(x, 0.42), (x, 1.0)], fill="wood", width=P.lw + 3)
    P.rect(0.33, 0.55, 0.47, 0.92, "light_wood")  # 문
    P.rect(0.53, 0.55, 0.67, 0.92, "light_wood")
    for x in (0.4, 0.6):
        P.line([(x, 0.55), (x, 0.92)], fill="wood", width=2)
    for y in (0.65, 0.75, 0.85):
        P.line([(0.33, y), (0.67, y)], fill="wood", width=2)
    P.rect(0.03, 0.92, 0.97, 1.0, "gray")  # 기단
    roof = rgb(pr.color or "dark_gray")
    P.poly([(-0.02, 0.36), (0.1, 0.18), (0.3, 0.06), (0.7, 0.06), (0.9, 0.18), (1.02, 0.36), (0.92, 0.46),
            (0.08, 0.46)], roof)
    for i in range(1, 12):
        x = 0.08 + i * 0.07
        P.line([(x, 0.1), (x - 0.02, 0.44)], fill=shade(roof, 0.75), width=2)
    P.line([(0.3, 0.06), (0.7, 0.06)], fill=shade(roof, 0.6), width=P.lw + 4)


def draw_choga_house(P: Painter, pr: Prop):
    P.rect(0.1, 0.45, 0.9, 1.0, (226, 204, 160))
    P.rect(0.4, 0.58, 0.6, 0.95, "light_wood")
    P.rect(0.15, 0.58, 0.32, 0.78, "cream")
    P.line([(0.235, 0.58), (0.235, 0.78)], fill="wood", width=2)
    P.chord(-0.05, 0.0, 1.05, 0.9, 180, 360, "straw")
    P.rect(-0.05, 0.42, 1.05, 0.5, shade("straw", 0.85), outline=None, width=0)
    for i in range(1, 6):
        P.arc(0.0 + i * 0.03, 0.05 + i * 0.05, 1.0 - i * 0.03, 0.9, 200, 340, fill=shade("straw", 0.8), width=2)


def draw_stone_wall(P: Painter, pr: Prop):
    P.rect(0.0, 0.25, 1.0, 1.0, (190, 178, 160))
    rng = random.Random(pr.extra.get("seed", 7))
    rows = 4
    for r in range(rows):
        y0 = 0.25 + r * 0.75 / rows
        x = -rng.random() * 0.05
        while x < 1.0:
            w = 0.05 + rng.random() * 0.06
            c = (170 + rng.randint(-18, 18), 160 + rng.randint(-15, 15), 145 + rng.randint(-15, 15))
            P.ellipse(x, y0, x + w, y0 + 0.75 / rows, c, width=2)
            x += w
    P.rect(-0.01, 0.1, 1.01, 0.28, "dark_gray")  # 담 위 기와


def draw_platform(P: Painter, pr: Prop):  # 장독대 돌 단
    P.rect(0.0, 0.0, 1.0, 1.0, (186, 172, 150), radius=0.1)
    for x in (0.2, 0.45, 0.7):
        P.line([(x, 0.1), (x + 0.05, 0.9)], fill=(150, 138, 120), width=2)


def draw_tent(P: Painter, pr: Prop):  # 장터 천막
    col = pr.color
    P.line([(0.03, 0.3), (0.03, 1.0)], fill="dark_earth", width=P.lw + 3)
    P.line([(0.97, 0.3), (0.97, 1.0)], fill="dark_earth", width=P.lw + 3)
    P.poly([(0.0, 0.32), (0.08, 0.0), (0.92, 0.0), (1.0, 0.32)], col, primary=True)
    n = 8
    for i in range(n):
        x0 = i / n
        P.chord(x0, 0.22, x0 + 1 / n, 0.42, 0, 180, shade(col, 0.9))


def draw_table(P: Painter, pr: Prop):
    P.rect(0.0, 0.0, 1.0, 0.3, pr.color)
    for x in (0.04, 0.92):
        P.rect(x, 0.3, x + 0.04, 1.0, shade(pr.color, 0.8))


def draw_pole(P: Painter, pr: Prop):  # 전봇대
    P.rect(0.3, 0.0, 0.7, 1.0, pr.color, width=2)
    P.rect(-1.5, 0.08, 2.5, 0.11, shade(pr.color, 0.8), width=2)


def draw_bench(P: Painter, pr: Prop):  # 평상
    P.rect(0.0, 0.0, 1.0, 0.3, pr.color)
    for i in range(1, 8):
        P.line([(i / 8, 0.0), (i / 8, 0.3)], fill=shade(pr.color, 0.75), width=2)
    for x in (0.03, 0.48, 0.92):
        P.rect(x, 0.3, x + 0.05, 1.0, shade(pr.color, 0.75))


def draw_storefront(P: Painter, pr: Prop):  # 구멍가게 건물
    P.rect(0.0, 0.0, 1.0, 1.0, (222, 206, 176))
    P.rect(0.0, 0.0, 1.0, 0.08, "dark_gray")
    P.rect(0.05, 0.38, 0.95, 1.0, "light_wood")
    for i in range(4):
        x0 = 0.07 + i * 0.22
        P.rect(x0, 0.42, x0 + 0.2, 0.98, (196, 214, 214))
        for j in range(1, 4):
            P.line([(x0, 0.42 + j * 0.14), (x0 + 0.2, 0.42 + j * 0.14)], fill="wood", width=3)
        P.line([(x0 + 0.1, 0.42), (x0 + 0.1, 0.98)], fill="wood", width=3)


def draw_buttumak(P: Painter, pr: Prop):  # 부뚜막
    P.rect(0.0, 0.0, 1.0, 1.0, pr.color, radius=0.05)
    P.rect(0.0, 0.0, 1.0, 0.12, shade(pr.color, 0.85))
    for cx in (0.25, 0.68):
        P.chord(cx - 0.12, 0.5, cx + 0.12, 1.4, 180, 360, (50, 40, 36))


def draw_cupboard(P: Painter, pr: Prop):  # 찬장
    P.rect(0.0, 0.0, 1.0, 1.0, pr.color)
    for y in (0.3, 0.55):
        P.rect(0.04, y, 0.96, y + 0.03, shade(pr.color, 0.8))
    P.rect(0.04, 0.6, 0.96, 0.97, shade(pr.color, 0.9))
    P.line([(0.5, 0.6), (0.5, 0.97)], fill=OUTLINE, width=3)
    P.ellipse(0.43, 0.76, 0.47, 0.8, "brass")
    P.ellipse(0.53, 0.76, 0.57, 0.8, "brass")


def draw_window(P: Painter, pr: Prop):  # 창살 창문
    P.rect(0.0, 0.0, 1.0, 1.0, "wood")
    P.rect(0.06, 0.08, 0.94, 0.92, (250, 240, 214))
    for i in range(1, 6):
        P.line([(0.06 + i * 0.88 / 6, 0.08), (0.06 + i * 0.88 / 6, 0.92)], fill="wood", width=3)
    for i in range(1, 4):
        P.line([(0.06, 0.08 + i * 0.84 / 4), (0.94, 0.08 + i * 0.84 / 4)], fill="wood", width=3)


def draw_clothesline(P: Painter, pr: Prop):
    P.line([(0.01, 0.05), (0.01, 1.0)], fill="dark_earth", width=P.lw + 3)
    P.line([(0.99, 0.05), (0.99, 1.0)], fill="dark_earth", width=P.lw + 3)
    P.line([(0.01, 0.08), (0.5, 0.1), (0.99, 0.08)], fill="dark_earth", width=3)


DRAWERS.update({
    "giwa_house": draw_giwa_house, "choga_house": draw_choga_house, "stone_wall": draw_stone_wall,
    "platform": draw_platform, "tent": draw_tent, "table": draw_table, "pole": draw_pole, "bench": draw_bench,
    "storefront": draw_storefront, "buttumak": draw_buttumak, "cupboard": draw_cupboard, "window": draw_window,
    "clothesline": draw_clothesline,
})


# ---------------------------------------------------------------------------
# 장면 데이터
# ---------------------------------------------------------------------------

@dataclass
class Scene:
    template: str
    seed: int
    background: dict
    props: list[Prop]
    extras: list[Prop] = field(default_factory=list)  # 수정본에서만 나타날 수 있는 소품
    width: int = W
    height: int = H

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @staticmethod
    def from_dict(d: dict) -> "Scene":
        def mk(p):
            p = dict(p)
            p["box"] = tuple(p["box"])
            p["ops"] = tuple(p.get("ops", ()))
            for k in ("color", "color2"):
                if isinstance(p.get(k), list):
                    p[k] = tuple(p[k])
            return Prop(**p)
        return Scene(template=d["template"], seed=d["seed"], background=d["background"],
                     props=[mk(p) for p in d["props"]], extras=[mk(p) for p in d.get("extras", [])],
                     width=d.get("width", W), height=d.get("height", H))


class SceneBuilder:
    def __init__(self, rng: random.Random, font_path: str | None):
        self.rng = rng
        self.font = font_path
        self.props: list[Prop] = []
        self.extras: list[Prop] = []
        self._n = 0

    def j(self, v: int, amount: int = 12) -> int:
        return v + self.rng.randint(-amount, amount)

    def add(self, kind: str, label: str, x: int, y: int, w: int, h: int, color=None, *, layer: int = 5,
            ops=None, jitter: int = 10, hidden: bool = False, **kw) -> Prop:
        self._n += 1
        if jitter:
            x, y = self.j(x, jitter), self.j(y, max(2, jitter // 2))
        pr = Prop(id=f"{kind}{self._n}", kind=kind, label=label, box=(x, y, w, h),
                  color=color if color is not None else "earth", layer=layer,
                  ops=tuple(DEFAULT_OPS.get(kind, ())) if ops is None else tuple(ops), **kw)
        if kind == "sign":
            pr.extra.setdefault("font", self.font)
        if hidden:
            pr.visible = False
            self.extras.append(pr)
        else:
            self.props.append(pr)
        return pr

    def structure(self, kind: str, x, y, w, h, color=None, layer: int = 1, **kw) -> Prop:
        return self.add(kind, kind, x, y, w, h, color, layer=layer, ops=(), jitter=0, **kw)

    def pick(self, *names):
        return self.rng.choice(names)


def build_scene(template: str, seed: int, variant: str | None = None, font_path: str | None = None) -> Scene:
    rng = random.Random(seed)
    b = SceneBuilder(rng, font_path)
    builders = {"village": _village, "kitchen": _kitchen, "market": _market, "rainy_road": _rainy_road,
                "corner_store": _corner_store}
    if template not in builders:
        raise ValueError(f"알 수 없는 장면 템플릿: {template}")
    bg = builders[template](b, variant)
    bg["template"] = template
    return Scene(template=template, seed=seed, background=bg, props=b.props, extras=b.extras)


def _sky_items(b: SceneBuilder, rainy=False, kite=False, bird_y=(110, 150)):
    if not rainy:
        b.add("cloud", "구름", b.rng.randint(240, 420), b.rng.randint(30, 60), 200, 90, "white", layer=0, jitter=0)
        b.add("bird", "새", b.rng.randint(560, 680), b.rng.randint(*bird_y), 100, 58, "dark_gray", layer=0,
              flipped=b.rng.random() < 0.5, jitter=0)
        b.add("bird", "새", 470, 40, 96, 56, "dark_gray", layer=0, hidden=True)
        if kite:  # 건물이 없는 오른쪽 하늘
            b.add("kite", "방패연", 950, 20, 90, 110, b.pick("red", "blue"), layer=0, jitter=0)


def _village(b: SceneBuilder, variant):
    r = b.rng
    b.structure("giwa_house", 30, 170, 560, 390, color="dark_gray")
    b.structure("tree", 880, 110, 310, 470, color="green", layer=1)
    b.structure("stone_wall", 580, 430, 630, 150, layer=2, extra={"seed": r.randint(0, 999)})
    b.structure("platform", 600, 640, 420, 70, layer=3)
    b.structure("well", 1050, 590, 140, 170, color=(180, 170, 152), layer=3)
    _sky_items(b)
    for i, (x, y) in enumerate([(915, 250), (1015, 195), (1095, 305)]):
        b.add("persimmon", "감", x, y, 64, 68, "persimmon", layer=2, jitter=8)
    b.add("persimmon", "감", 965, 330, 62, 66, "persimmon", layer=2, jitter=0, hidden=True)
    b.add("jar", "큰 장독", 612, 494, 158, 156, "onggi", layer=4, jitter=4, ops=("color_changed", "shape_changed", "pattern_changed"))
    b.add("jar", "장독", 778, 538, 118, 114, "onggi", layer=4, jitter=4, variant=r.choice([0, 2]))
    b.add("jar", "작은 항아리", 905, 560, 92, 92, "onggi", layer=4, jitter=3, variant=1)
    b.add("bucket", "두레박", 960, 735, 78, 80, "wood", layer=6, variant=1, jitter=6)
    if variant == "laundry":
        b.structure("clothesline", 50, 440, 540, 160, layer=4)
        cols = r.sample(["white", "sky", "pink", "yellow", "green"], 4)
        for i, x in enumerate((80, 200, 330, 450)):
            b.add("clothes", r.choice(["셔츠", "빨래"]), x, 450, 100, 112, cols[i], layer=5, jitter=6,
                  variant=r.choice([0, 1]), pattern=r.choice(["plain", "plain", "stripes"]))
        b.add("chicken", "닭", 180, 660, 110, 100, r.choice(["white", "orange"]), layer=6, flipped=r.random() < 0.5)
        b.add("chicken", "병아리 닭", 420, 700, 96, 88, "white", layer=6, hidden=True)
        b.add("basin", "빨간 대야", 380, 610, 140, 78, "red", layer=6)
        b.add("shoes", "고무신", 70, 740, 110, 68, "white", layer=6, flipped=r.random() < 0.5)
    else:
        b.add("broom", "빗자루", 470, 400, 92, 160, "straw", layer=5, flipped=r.random() < 0.5)
        b.add("flowerpot", "화분", 60, 440, 84, 112, "earth", color2=r.choice(["red", "pink"]), layer=5)
        b.add("shoes", "고무신", 250, 580, 110, 68, r.choice(["white", "black"]), layer=6, flipped=r.random() < 0.5)
        b.add("basin", "대야", 360, 640, 140, 78, r.choice(["red", "blue"]), layer=6)
        b.add("chicken", "닭", 120, 680, 110, 100, r.choice(["white", "orange"]), layer=6, flipped=r.random() < 0.5)
        b.add("chicken", "닭", 520, 700, 100, 92, "white", layer=6, hidden=True)
    b.add("kite", "방패연", 150, 30, 90, 110, "blue", layer=0, hidden=True)
    return {"kind": "outdoor", "sky": ((172, 202, 214), (242, 230, 204)), "ground_y": 560,
            "ground": (226, 202, 162), "hills": True, "path": True}


def _kitchen(b: SceneBuilder, variant):
    r = b.rng
    b.structure("window", 470, 60, 270, 200, layer=0)
    b.structure("buttumak", 60, 430, 560, 180, color=(196, 156, 116), layer=1)
    b.structure("cupboard", 860, 170, 300, 470, color="wood", layer=1)
    b.add("cauldron", "큰 가마솥", 110, 330, 220, 140, "black", layer=2, jitter=0, variant=r.choice([0, 1]))
    b.add("cauldron", "작은 가마솥", 360, 350, 190, 120, "black", layer=2, jitter=0, variant=r.choice([0, 1]))
    b.add("fire", "아궁이 불", 145, 530, 100, 72, "orange", layer=2, jitter=0)
    if variant != "morning":
        b.add("fire", "아궁이 불", 390, 530, 90, 70, "orange", layer=2, jitter=0)
    b.add("pot", "양은 냄비", 640, 380, 130, 105, "yellow", layer=3, jitter=8, variant=r.choice([0, 1]))
    b.add("radio", "라디오", 930, 90, 120, 80, "red", layer=2, jitter=6)
    b.add("bowl", "놋그릇", 890, 330, 100, 52, "brass", layer=2, jitter=4, variant=r.choice([0, 2]))
    b.add("bowl", "놋주발", 1020, 318, 100, 64, "brass", layer=2, jitter=4, variant=1)
    b.add("jar", "단지", 900, 412, 82, 82, "onggi", layer=2, jitter=4, variant=2)
    b.add("bowl", "사발", 1030, 440, 90, 50, "white", layer=2, jitter=4)
    b.add("kettle", "양은 주전자", 690, 650, 130, 112, "yellow", layer=5, flipped=r.random() < 0.5)
    b.add("basket", "대바구니", 60, 660, 160, 110, "straw", color2=r.choice(["persimmon", "red", "green"]), layer=5)
    b.add("bucket", "양동이", 290, 670, 96, 96, r.choice(["blue", "dark_gray"]), layer=5)
    b.add("broom", "빗자루", 770, 440, 80, 150, "straw", layer=4, flipped=r.random() < 0.5)
    b.add("jar", "항아리", 460, 640, 110, 115, "onggi", layer=5, variant=1)
    b.add("basin", "고무 대야", 900, 700, 150, 82, "red", layer=5, hidden=True)
    b.add("bowl", "그릇", 590, 720, 90, 48, "brass", layer=5, hidden=True)
    b.add("bucket", "두레박", 1050, 700, 84, 86, "wood", variant=1, layer=6, hidden=True, jitter=0)
    return {"kind": "indoor", "wall": (232, 214, 182), "floor_y": 600, "floor": (176, 138, 98)}


def _market(b: SceneBuilder, variant):
    r = b.rng
    b.structure("tent", 30, 110, 540, 330, color=r.choice(["blue", "red", "green"]), layer=1,
                pattern="hstripes")
    b.structure("table", 50, 430, 500, 130, color="wood", layer=2)
    b.structure("tent", 620, 150, 360, 280, color=r.choice(["orange", "sky", "yellow"]), layer=1)
    b.structure("table", 640, 420, 320, 130, color="light_wood", layer=2)
    _sky_items(b)
    fruits = ["persimmon", "red", "green", "yellow"]
    for i, x in enumerate((70, 225, 380)):
        b.add("basket", "과일 바구니", x, 335, 140, 100, "straw", color2=r.choice(fruits), layer=3, jitter=6,
              variant=r.choice([0, 1]))
    b.add("scale", "저울", 690, 318, 120, 105, r.choice(["green", "blue"]), layer=3, jitter=6)
    b.add("bowl", "놋그릇", 840, 370, 90, 50, "brass", layer=3, jitter=4, variant=2)
    b.add("sign", "간판", 1000, 160, 170, 72, r.choice(["navy", "red"]),
          extra={"text": "과일" if variant == "fruit" else "장터"}, layer=2, jitter=4)
    b.add("cabbage", "배추", 650, 590, 180, 120, "green", layer=5)
    b.add("sack", "쌀가마니", 60, 590, 120, 140, "straw", layer=5, jitter=6)
    b.add("sack", "쌀가마니", 195, 610, 110, 120, "straw", layer=5, jitter=6, extra={"label": True})
    b.add("umbrella", "파라솔", 360, 560, 170, 160, r.choice(["red", "blue"]), layer=6,
          flipped=r.random() < 0.5, pattern=r.choice(["plain", "stripes"]))
    b.add("bicycle", "자전거", 900, 580, 260, 170, r.choice(["navy", "red", "dark_gray"]), layer=6,
          flipped=r.random() < 0.5)
    b.add("basket", "바구니", 520, 700, 120, 92, "straw", color2="red", layer=7, hidden=True)
    b.add("chicken", "닭", 860, 450, 90, 84, "white", layer=7, hidden=True, jitter=0)
    b.add("kite", "방패연", 150, 20, 80, 96, "red", layer=0, hidden=True)
    return {"kind": "outdoor", "sky": ((176, 204, 216), (244, 232, 206)), "ground_y": 470,
            "ground": (222, 198, 156), "hills": True, "path": False}


def _rainy_road(b: SceneBuilder, variant):
    r = b.rng
    b.structure("choga_house", 20, 250, 430, 280, layer=1)
    b.structure("choga_house", 830, 290, 330, 210, layer=1)
    b.structure("pole", 500, 70, 34, 470, color="wood", layer=1)
    b.structure("pole", 1150, 110, 26, 420, color="wood", layer=1)
    b.add("jar", "장독", 70, 470, 96, 96, "onggi", layer=3, jitter=4)
    b.add("shoes", "고무신", 240, 560, 110, 66, r.choice(["white", "black"]), layer=4, flipped=r.random() < 0.5)
    b.add("chicken", "닭", 330, 470, 90, 86, "orange", layer=3, flipped=r.random() < 0.5)
    b.add("sign", "간판", 880, 400, 160, 56, r.choice(["red", "navy"]), extra={"text": "이발소"}, layer=2, jitter=0)
    b.add("mailbox", "우체통", 1060, 440, 74, 120, "red", layer=3, jitter=4)
    b.add("umbrella", "우산", 590, 420, 170, 180, r.choice(["blue", "yellow", "red"]), layer=4,
          flipped=r.random() < 0.5)
    b.add("bicycle", "자전거", 860, 570, 240, 160, r.choice(["navy", "dark_gray"]), layer=5,
          flipped=r.random() < 0.5)
    b.add("puddle", "물웅덩이", 400, 640, 210, 80, (150, 170, 182), layer=2)
    b.add("puddle", "물웅덩이", 560, 740, 230, 80, (150, 170, 182), layer=2)
    b.add("bucket", "양동이", 120, 690, 90, 90, r.choice(["blue", "dark_gray"]), layer=5)
    b.add("basin", "대야", 300, 740, 140, 70, "red", layer=5, hidden=True)
    b.add("puddle", "물웅덩이", 860, 760, 200, 64, (150, 170, 182), layer=2, hidden=True)
    b.add("flowerpot", "화분", 20, 560, 80, 110, "earth", color2="red", layer=5, hidden=True)
    return {"kind": "outdoor", "sky": ((150, 164, 176), (206, 204, 192)), "ground_y": 520,
            "ground": (186, 160, 124), "hills": True, "path": True, "rain": True}


def _corner_store(b: SceneBuilder, variant):
    r = b.rng
    b.structure("storefront", 30, 130, 800, 450, layer=1)
    b.structure("bench", 110, 580, 580, 120, color="light_wood", layer=3)
    _sky_items(b, kite=True, bird_y=(30, 60))
    b.add("sign", "가게 간판", 120, 160, 520, 100, r.choice(["navy", "blue", "red"]),
          extra={"text": r.choice(["행복상회", "우리상회", "한마을상회"])}, layer=2, jitter=0,
          ops=("color_changed",))
    b.add("sign", "담배 간판", 680, 150, 110, 110, "red", variant=1, extra={"text": "담배"}, layer=2, jitter=0)
    b.add("kettle", "주전자", 180, 500, 100, 88, "yellow", layer=4, flipped=r.random() < 0.5, jitter=6)
    b.add("bowl", "사발", 320, 540, 90, 44, "white", layer=4, jitter=6)
    b.add("radio", "라디오", 450, 512, 110, 74, r.choice(["red", "sky"]), layer=4, jitter=6)
    b.add("mailbox", "빨간 우체통", 870, 420, 100, 180, "red", layer=4)
    b.add("bicycle", "자전거", 900, 610, 270, 180, r.choice(["navy", "red"]), layer=5, flipped=r.random() < 0.5)
    b.add("crate", "병 상자", 40, 700, 140, 100, "red", color2="green", layer=5)
    b.add("shoes", "고무신", 300, 730, 110, 66, r.choice(["white", "black"]), layer=5, flipped=r.random() < 0.5)
    b.add("flowerpot", "화분", 740, 640, 80, 110, "earth", color2=r.choice(["red", "pink"]), layer=5)
    b.add("chicken", "닭", 560, 720, 100, 92, "white", layer=6, hidden=True)
    b.add("bucket", "양동이", 470, 730, 80, 80, "blue", layer=6, hidden=True)
    b.add("cloud", "구름", 900, 160, 180, 80, "white", layer=0, hidden=True)
    return {"kind": "outdoor", "sky": ((168, 200, 218), (240, 230, 206)), "ground_y": 580,
            "ground": (214, 196, 160), "hills": False, "path": False}


# ---------------------------------------------------------------------------
# 렌더링
# ---------------------------------------------------------------------------

def _gradient(w, h, top, bottom) -> Image.Image:
    t = np.linspace(0, 1, h)[:, None]
    top, bottom = np.array(top, float), np.array(bottom, float)
    arr = (top[None, :] * (1 - t[..., None]) + bottom[None, :] * t[..., None])
    arr = np.repeat(arr, w, axis=1)
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def render_background(bg: dict, seed: int, w: int = W, h: int = H) -> Image.Image:
    rng = random.Random(seed * 31 + 7)
    bg = {k: tuple(v) if isinstance(v, list) else v for k, v in bg.items()}  # JSON 왕복 시 list → tuple
    if bg["kind"] == "indoor":
        img = Image.new("RGB", (w, h), bg["wall"])
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, w, 40], fill=shade("wood", 0.8))
        for x in range(0, w, 300):
            d.rectangle([x + 140, 0, x + 165, bg["floor_y"]], fill=shade("wood", 0.9))
        d.rectangle([0, bg["floor_y"], w, h], fill=bg["floor"])
        for _ in range(60):
            x, y = rng.randint(0, w), rng.randint(bg["floor_y"] + 10, h)
            d.ellipse([x, y, x + rng.randint(6, 18), y + rng.randint(3, 7)], fill=shade(bg["floor"], 0.9))
        return img
    img = _gradient(w, h, *bg["sky"])
    d = ImageDraw.Draw(img)
    gy = bg["ground_y"]
    if not bg.get("rain"):
        d.ellipse([60, 40, 160, 140], fill=(250, 226, 170))
    if bg.get("hills"):
        for k, (base, col) in enumerate([(gy - 170, (178, 200, 160)), (gy - 100, (150, 180, 128))]):
            if bg.get("rain"):
                col = tuple(int(c * 0.6 + 170 * 0.4) for c in col)
            ph, amp, fr = rng.random() * 6, 35 + k * 10, 0.004 + rng.random() * 0.003
            pts = [(x, base + amp * math.sin(x * fr + ph) + 15 * math.sin(x * fr * 3.1)) for x in range(0, w + 20, 20)]
            d.polygon(pts + [(w, h), (0, h)], fill=col)
    d.rectangle([0, gy, w, h], fill=bg["ground"])
    if bg.get("path"):
        d.polygon([(w * 0.42, gy), (w * 0.58, gy), (w * 0.8, h), (w * 0.2, h)], fill=shade(bg["ground"], 1.06))
    for _ in range(80):
        x, y = rng.randint(0, w), rng.randint(gy + 6, h)
        d.ellipse([x, y, x + rng.randint(4, 12), y + rng.randint(2, 5)], fill=shade(bg["ground"], 0.9))
    return img


def _paper_texture(w: int, h: int, seed: int) -> np.ndarray:
    gen = np.random.default_rng(seed)
    small = gen.normal(0, 1, (h // 6 + 1, w // 6 + 1))
    tex = Image.fromarray(((small - small.min()) / (np.ptp(small) + 1e-6) * 255).astype(np.uint8))
    tex = tex.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(2))
    fine = gen.normal(0, 1, (h, w))
    arr = np.asarray(tex, float) / 255.0
    return 0.93 + 0.07 * arr + 0.012 * fine


def _watercolor(img: Image.Image, seed: int) -> Image.Image:
    """동화책 질감: 살짝 번진 선 + 종이 결 + 따뜻한 톤 + 은은한 비네팅. 두 그림에 똑같이 적용."""
    w, h = img.size
    soft = img.filter(ImageFilter.GaussianBlur(0.9))
    arr = np.asarray(soft, float)
    arr = arr * _paper_texture(w, h, seed)[..., None]
    warm = np.array([1.03, 1.0, 0.94])
    arr = arr * warm
    yy, xx = np.mgrid[0:h, 0:w]
    vig = 1 - 0.12 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    arr = arr * vig[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _rain(img: Image.Image, seed: int) -> None:
    rng = random.Random(seed + 99)
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    for _ in range(260):
        x, y = rng.randint(-50, img.width), rng.randint(-20, img.height)
        d.line([(x, y), (x + 10, y + 34)], fill=(235, 240, 246, 120), width=2)
    img.alpha_composite(over)


def render_scene(scene: Scene) -> Image.Image:
    base = render_background(scene.background, scene.seed, scene.width, scene.height).convert("RGBA")
    layers = sorted([p for p in scene.props + scene.extras if p.visible], key=lambda p: p.layer)
    for pr in layers:
        tile = render_prop(pr)
        base.alpha_composite(tile, (pr.box[0], pr.box[1])) if pr.box[0] >= 0 and pr.box[1] >= 0 else \
            base.paste(tile, (pr.box[0], pr.box[1]), tile)
    if scene.background.get("rain"):
        _rain(base, scene.seed)
    return _watercolor(base.convert("RGB"), scene.seed)
