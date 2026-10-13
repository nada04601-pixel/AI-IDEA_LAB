"""동화책풍 손그림 소품 라이브러리.

각 소품은 자기 상자(box) 안에 투명 레이어로 그려진다. 그래서
- 좌우 반전(방향 변경), 숨기기(제거), 추가가 레이어 단위로 정확하고
- 차이 영역의 좌표를 그림에서 바로 계산할 수 있다.

좌표는 상자 크기 기준 비율(0~1)로 적고 Painter가 픽셀로 바꾼다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Callable

from PIL import Image, ImageDraw

OUTLINE = (88, 60, 42)

# 따뜻한 동화책 팔레트
C = {
    "beige": (238, 224, 194),
    "cream": (247, 238, 214),
    "earth": (150, 106, 70),
    "dark_earth": (112, 78, 52),
    "wood": (170, 120, 76),
    "light_wood": (204, 160, 108),
    "green": (164, 192, 120),
    "dark_green": (104, 140, 84),
    "orange": (238, 160, 92),
    "persimmon": (232, 118, 52),
    "red": (204, 72, 60),
    "pink": (232, 150, 150),
    "blue": (92, 132, 176),
    "sky": (150, 186, 210),
    "navy": (60, 78, 120),
    "yellow": (232, 196, 92),
    "brass": (204, 162, 72),
    "white": (246, 242, 230),
    "gray": (150, 148, 140),
    "dark_gray": (92, 96, 102),
    "black": (58, 52, 50),
    "purple": (150, 110, 170),
    "onggi": (122, 74, 48),
    "straw": (214, 184, 112),
}

# 색상 변경 차이에 쓸 후보. 원래 색과 충분히 다른 색을 고른다.
SWAP_COLORS = ["red", "blue", "green", "yellow", "white", "navy", "purple", "pink", "orange", "black"]


def color_distance(a: tuple, b: tuple) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a[:3], b[:3])))


def rgb(name_or_rgb) -> tuple:
    if isinstance(name_or_rgb, str):
        return C[name_or_rgb]
    return tuple(name_or_rgb)


def shade(color, k: float) -> tuple:
    c = rgb(color)
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def pattern_tile(size: tuple[int, int], base, pattern: str, accent=None) -> Image.Image:
    w, h = size
    base = rgb(base)
    img = Image.new("RGBA", (w, h), base + (255,))
    d = ImageDraw.Draw(img)
    acc = rgb(accent) if accent else (shade(base, 0.62) if sum(base) > 360 else shade(base, 1.6))
    if pattern == "stripes":
        step = max(10, min(w, h) // 5)
        for x in range(-h, w + h, step):
            d.line([(x, 0), (x + h, h)], fill=acc, width=max(3, step // 3))
    elif pattern == "hstripes":
        step = max(10, h // 5)
        for y in range(0, h, step):
            d.rectangle([0, y, w, y + step // 2], fill=acc)
    elif pattern == "dots":
        step = max(12, min(w, h) // 5)
        r = max(3, step // 4)
        for yi, y in enumerate(range(step // 2, h, step)):
            off = step // 2 if yi % 2 else 0
            for x in range(step // 2 + off, w, step):
                d.ellipse([x - r, y - r, x + r, y + r], fill=acc)
    elif pattern == "checks":
        step = max(12, min(w, h) // 4)
        for yi, y in enumerate(range(0, h, step)):
            for xi, x in enumerate(range(0, w, step)):
                if (xi + yi) % 2 == 0:
                    d.rectangle([x, y, x + step, y + step], fill=acc)
    return img


class Painter:
    """비율 좌표로 그리는 작은 도우미. primary=True인 도형에는 무늬(pattern)를 입힌다."""

    def __init__(self, w: int, h: int, prop: "Prop"):
        self.w, self.h = w, h
        self.prop = prop
        self.img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.lw = max(2, int(min(w, h) * 0.025) + 1)

    def p(self, pts):
        return [(x * self.w, y * self.h) for x, y in pts]

    def box(self, x0, y0, x1, y1):
        return [x0 * self.w, y0 * self.h, x1 * self.w, y1 * self.h]

    def _shape(self, kind: str, xy, fill, outline=OUTLINE, width=None, primary=False, **kw):
        width = self.lw if width is None else width
        fill = rgb(fill) if fill is not None else None
        pat = self.prop.pattern if primary else "plain"
        if fill is not None and pat != "plain":
            mask = Image.new("L", (self.w, self.h), 0)
            getattr(ImageDraw.Draw(mask), kind)(xy, fill=255, **kw)
            self.img.paste(pattern_tile((self.w, self.h), fill, pat), (0, 0), mask)
            if outline is not None and width:
                getattr(self.d, kind)(xy, outline=outline, width=width, **kw)
        else:
            getattr(self.d, kind)(xy, fill=fill, outline=outline if width else None, width=width or 0, **kw)

    def poly(self, pts, fill, primary=False, outline=OUTLINE, width=None):
        self._shape("polygon", self.p(pts), fill, outline, width, primary)

    def ellipse(self, x0, y0, x1, y1, fill, primary=False, outline=OUTLINE, width=None):
        self._shape("ellipse", self.box(x0, y0, x1, y1), fill, outline, width, primary)

    def rect(self, x0, y0, x1, y1, fill, primary=False, outline=OUTLINE, width=None, radius=0):
        if radius:
            self._shape("rounded_rectangle", self.box(x0, y0, x1, y1), fill, outline, width, primary,
                        radius=radius * min(self.w, self.h))
        else:
            self._shape("rectangle", self.box(x0, y0, x1, y1), fill, outline, width, primary)

    def chord(self, x0, y0, x1, y1, start, end, fill, primary=False, outline=OUTLINE, width=None):
        self._shape("chord", self.box(x0, y0, x1, y1), fill, outline, width, primary, start=start, end=end)

    def line(self, pts, fill=OUTLINE, width=None):
        self.d.line(self.p(pts), fill=rgb(fill), width=width or self.lw, joint="curve")

    def arc(self, x0, y0, x1, y1, start, end, fill=OUTLINE, width=None):
        self.d.arc(self.box(x0, y0, x1, y1), start, end, fill=rgb(fill), width=width or self.lw)


@dataclass
class Prop:
    id: str
    kind: str
    label: str
    box: tuple[int, int, int, int]  # x, y, w, h (장면 픽셀)
    color: str | tuple = "earth"
    color2: str | tuple | None = None
    pattern: str = "plain"
    variant: int = 0
    flipped: bool = False
    visible: bool = True
    layer: int = 5
    ops: tuple[str, ...] = ()  # 이 소품에 허용된 차이 유형
    extra: dict = field(default_factory=dict)

    def bbox(self) -> tuple[int, int, int, int]:
        x, y, w, h = self.box
        return (x, y, x + w, y + h)

    def copy(self, **changes) -> "Prop":
        return replace(self, **changes)


# ---------------------------------------------------------------------------
# 소품 그리기 함수들
# ---------------------------------------------------------------------------

def draw_jar(P: Painter, pr: Prop):  # 장독(옹기)
    col = pr.color
    if pr.variant == 1:  # 키 큰 항아리
        P.poly([(0.2, 0.18), (0.8, 0.18), (0.95, 0.5), (0.82, 0.95), (0.18, 0.95), (0.05, 0.5)], col, primary=True)
        P.ellipse(0.25, 0.1, 0.75, 0.24, shade(col, 0.8))
    else:
        P.poly([(0.18, 0.3), (0.82, 0.3), (1.0, 0.58), (0.84, 0.97), (0.16, 0.97), (0.0, 0.58)], col, primary=True)
        if pr.variant == 2:  # 납작한 뚜껑
            P.rect(0.12, 0.2, 0.88, 0.32, shade(col, 0.85), radius=0.04)
        else:  # 둥근 뚜껑
            P.chord(0.12, 0.08, 0.88, 0.5, 180, 360, shade(col, 0.85))
            P.ellipse(0.44, 0.04, 0.56, 0.14, shade(col, 0.7))
    P.arc(0.22, 0.4, 0.5, 0.9, 120, 200, fill=shade(col, 1.6), width=max(2, P.lw))


def draw_persimmon(P: Painter, pr: Prop):
    P.ellipse(0.06, 0.2, 0.94, 0.98, pr.color, primary=True)
    P.poly([(0.5, 0.12), (0.78, 0.3), (0.5, 0.36), (0.22, 0.3)], "dark_green")
    P.line([(0.5, 0.0), (0.5, 0.2)], width=max(2, P.lw))
    P.ellipse(0.24, 0.36, 0.4, 0.52, shade(pr.color, 1.3), outline=None, width=0)


def draw_tree(P: Painter, pr: Prop):  # 감나무
    P.poly([(0.44, 1.0), (0.47, 0.45), (0.3, 0.3), (0.35, 0.27), (0.5, 0.38), (0.62, 0.22), (0.66, 0.25),
            (0.55, 0.45), (0.57, 1.0)], "dark_earth")
    for (x0, y0, x1, y1) in [(0.0, 0.08, 0.55, 0.55), (0.35, 0.0, 1.0, 0.5), (0.12, 0.25, 0.9, 0.62)]:
        P.ellipse(x0, y0, x1, y1, pr.color)
    P.ellipse(0.2, 0.15, 0.4, 0.3, shade(pr.color, 1.15), outline=None, width=0)


def draw_well(P: Painter, pr: Prop):  # 우물
    P.line([(0.12, 0.45), (0.12, 0.02)], fill="dark_earth", width=P.lw * 2)
    P.line([(0.88, 0.45), (0.88, 0.02)], fill="dark_earth", width=P.lw * 2)
    P.poly([(0.0, 0.08), (0.5, -0.02), (1.0, 0.08), (0.96, 0.14), (0.04, 0.14)], "dark_gray")
    P.line([(0.5, 0.14), (0.5, 0.4)], width=max(2, P.lw // 2))
    P.rect(0.05, 0.5, 0.95, 1.0, pr.color, radius=0.05)
    for y in (0.62, 0.75, 0.88):
        P.line([(0.06, y), (0.94, y)], fill=shade(pr.color, 0.75), width=max(2, P.lw // 2))
    for x in (0.25, 0.5, 0.75):
        P.line([(x, 0.5), (x, 0.62)], fill=shade(pr.color, 0.75), width=max(2, P.lw // 2))
    P.ellipse(0.02, 0.42, 0.98, 0.58, shade(pr.color, 0.85))
    P.ellipse(0.12, 0.45, 0.88, 0.55, (60, 70, 80))


def draw_bucket(P: Painter, pr: Prop):  # 양동이/두레박
    if pr.variant == 1:  # 나무 두레박
        P.poly([(0.12, 0.3), (0.88, 0.3), (0.8, 1.0), (0.2, 1.0)], pr.color, primary=True)
        for x in (0.35, 0.5, 0.65):
            P.line([(x, 0.3), (x * 0.95 + 0.025, 1.0)], width=max(2, P.lw // 2))
    else:
        P.poly([(0.1, 0.3), (0.9, 0.3), (0.78, 1.0), (0.22, 1.0)], pr.color, primary=True)
        P.line([(0.14, 0.5), (0.86, 0.5)], fill=shade(pr.color, 0.75))
    P.ellipse(0.08, 0.22, 0.92, 0.38, shade(pr.color, 0.8))
    P.arc(0.12, 0.0, 0.88, 0.6, 180, 360)


def draw_broom(P: Painter, pr: Prop):  # 빗자루 (기울어진 방향이 있음)
    P.line([(0.75, 0.0), (0.42, 0.6)], fill="dark_earth", width=P.lw + 2)
    P.poly([(0.36, 0.55), (0.52, 0.62), (0.62, 1.0), (0.05, 0.92)], pr.color, primary=True)
    for t in (0.25, 0.45, 0.65):
        P.line([(0.38 + t * 0.12, 0.6), (0.12 + t * 0.5, 0.95)], fill=shade(pr.color, 0.7), width=max(2, P.lw // 2))
    P.line([(0.37, 0.6), (0.53, 0.66)], fill="red", width=P.lw)


def draw_shoes(P: Painter, pr: Prop):  # 고무신 한 켤레 (코가 한쪽을 향함)
    for y0 in (0.05, 0.5):
        P.poly([(0.0, y0 + 0.25), (0.15, y0 + 0.05), (0.55, y0 + 0.1), (1.0, y0 - 0.02), (0.9, y0 + 0.3),
                (0.75, y0 + 0.42), (0.1, y0 + 0.42)], pr.color, primary=True)
        P.ellipse(0.18, y0 + 0.1, 0.62, y0 + 0.28, shade(pr.color, 0.6))


def draw_pot(P: Painter, pr: Prop):  # 양은 냄비
    col = pr.color
    P.rect(0.12, 0.38, 0.88, 0.95, col, primary=True, radius=0.06)
    P.rect(0.0, 0.46, 0.14, 0.56, shade(col, 0.8), radius=0.03)
    P.rect(0.86, 0.46, 1.0, 0.56, shade(col, 0.8), radius=0.03)
    P.chord(0.08, 0.2, 0.92, 0.52, 180, 360, shade(col, 0.92))
    if pr.variant == 1:
        P.rect(0.42, 0.12, 0.58, 0.24, "black", radius=0.03)
    elif pr.variant == 2:
        P.ellipse(0.4, 0.08, 0.6, 0.26, "red")
    else:
        P.ellipse(0.44, 0.15, 0.56, 0.25, shade(col, 0.7))
    P.line([(0.2, 0.6), (0.2, 0.86)], fill=shade(col, 1.25), width=P.lw)


def draw_bowl(P: Painter, pr: Prop):  # 놋그릇
    col = pr.color
    P.chord(0.0, 0.0, 1.0, 1.0, 0, 180, col, primary=True)
    P.rect(0.32, 0.92, 0.68, 1.0, shade(col, 0.8))
    if pr.variant == 1:  # 뚜껑 덮인 주발
        P.chord(0.04, 0.0, 0.96, 0.95, 180, 360, shade(col, 0.95))
        P.ellipse(0.44, 0.12, 0.56, 0.26, shade(col, 0.75))
    else:
        P.ellipse(0.0, 0.38, 1.0, 0.62, shade(col, 0.85))
        if pr.variant == 2:  # 밥이 담긴 그릇
            P.chord(0.06, 0.15, 0.94, 0.75, 180, 360, "white")
    P.arc(0.12, 0.45, 0.6, 0.95, 120, 160, fill=shade(col, 1.4))


def draw_basket(P: Painter, pr: Prop):  # 대바구니 (+과일)
    fruit = pr.color2 or "persimmon"
    if pr.variant != 1:
        P.arc(0.12, -0.05, 0.88, 0.85, 180, 360, fill="dark_earth", width=P.lw + 2)
    if pr.extra.get("fruit", True):
        for i, x in enumerate((0.16, 0.38, 0.6)):
            P.ellipse(x, 0.24 - (i % 2) * 0.06, x + 0.26, 0.56, fruit)
    P.poly([(0.0, 0.42), (1.0, 0.42), (0.86, 1.0), (0.14, 1.0)], pr.color, primary=True)
    for t in (0.58, 0.74, 0.88):
        P.line([(0.04 + (t - 0.42) * 0.2, t), (0.96 - (t - 0.42) * 0.2, t)], fill=shade(pr.color, 0.7),
               width=max(2, P.lw // 2))


def draw_bicycle(P: Painter, pr: Prop):  # 자전거 (앞이 한쪽을 향함)
    col = pr.color
    for cx in (0.2, 0.8):
        P.ellipse(cx - 0.19, 0.42, cx + 0.19, 0.98, None, width=P.lw + 2)
        P.ellipse(cx - 0.03, 0.66, cx + 0.03, 0.74, OUTLINE)
    P.line([(0.2, 0.7), (0.45, 0.7), (0.62, 0.38), (0.36, 0.38), (0.2, 0.7)], fill=col, width=P.lw + 3)
    P.line([(0.45, 0.7), (0.33, 0.28)], fill=col, width=P.lw + 3)
    P.line([(0.62, 0.38), (0.8, 0.7)], fill=col, width=P.lw + 3)
    P.line([(0.62, 0.38), (0.66, 0.14), (0.78, 0.12)], fill="dark_gray", width=P.lw + 1)
    P.rect(0.24, 0.22, 0.42, 0.3, "black", radius=0.04)
    P.rect(0.02, 0.4, 0.24, 0.46, "dark_gray")  # 짐받이


def draw_scale(P: Painter, pr: Prop):  # 앉은뱅이 저울
    col = pr.color
    P.rect(0.05, 0.55, 0.95, 1.0, col, primary=True, radius=0.05)
    P.rect(0.0, 0.48, 1.0, 0.58, "dark_gray", radius=0.03)
    if pr.variant == 1:
        P.rect(0.22, 0.0, 0.78, 0.46, "white", radius=0.05)
    else:
        P.ellipse(0.2, 0.0, 0.8, 0.48, "white")
    P.line([(0.5, 0.24), (0.66, 0.1)], fill="red")
    P.ellipse(0.46, 0.2, 0.54, 0.28, OUTLINE)


def draw_sign(P: Painter, pr: Prop):  # 옛 간판
    text = pr.extra.get("text", "상회")
    font = pr.extra.get("font")
    if pr.variant == 1:
        P.ellipse(0.0, 0.0, 1.0, 1.0, pr.color, primary=True)
    else:
        P.rect(0.0, 0.0, 1.0, 1.0, pr.color, primary=True, radius=0.08)
    P.rect(0.06, 0.12, 0.94, 0.88, None, width=max(2, P.lw // 2))
    if font is not None:
        from PIL import ImageFont
        size = int(min(P.h * 0.62, P.w * 0.8 / max(1, len(text))))
        f = ImageFont.truetype(font, size)
        tc = "white" if sum(rgb(pr.color)) < 380 else "black"
        P.d.text((P.w / 2, P.h / 2), text, font=f, fill=rgb(tc), anchor="mm")


def draw_flowerpot(P: Painter, pr: Prop):  # 화분
    P.line([(0.5, 0.62), (0.5, 0.3)], fill="dark_green", width=P.lw + 1)
    P.ellipse(0.2, 0.36, 0.48, 0.5, "green")
    P.ellipse(0.52, 0.42, 0.8, 0.56, "green")
    fl = pr.color2 or "red"
    if pr.variant == 1:  # 해바라기형
        P.ellipse(0.22, 0.0, 0.78, 0.4, "yellow")
        P.ellipse(0.38, 0.1, 0.62, 0.3, "dark_earth")
    else:
        for (x, y) in [(0.5, 0.06), (0.36, 0.16), (0.64, 0.16), (0.42, 0.28), (0.58, 0.28)]:
            P.ellipse(x - 0.12, y - 0.08, x + 0.12, y + 0.1, fl)
        P.ellipse(0.43, 0.12, 0.57, 0.24, "yellow")
    P.poly([(0.18, 0.6), (0.82, 0.6), (0.72, 1.0), (0.28, 1.0)], pr.color, primary=True)


def draw_umbrella(P: Painter, pr: Prop):  # 우산 (기울어짐 = 방향)
    col = pr.color
    P.line([(0.52, 0.32), (0.66, 0.95)], fill="dark_earth", width=P.lw + 1)
    P.arc(0.6, 0.85, 0.78, 1.0, 0, 180, fill="dark_earth", width=P.lw + 1)
    P.poly([(0.0, 0.5), (0.1, 0.24), (0.32, 0.07), (0.52, 0.02), (0.74, 0.08), (0.92, 0.24), (1.0, 0.42),
            (0.8, 0.4), (0.62, 0.48), (0.4, 0.46), (0.2, 0.52)], col, primary=True)
    for x, y in ((0.2, 0.5), (0.4, 0.46), (0.62, 0.47), (0.82, 0.4)):
        P.line([(0.52, 0.03), (x, y)], fill=shade(col, 0.7), width=max(2, P.lw // 2))


def draw_clothes(P: Painter, pr: Prop):  # 빨래 (셔츠/수건)
    col = pr.color
    if pr.variant == 1:  # 수건
        P.rect(0.12, 0.05, 0.88, 0.9, col, primary=True)
        P.line([(0.12, 0.78), (0.88, 0.78)], fill=shade(col, 0.7))
    else:  # 반팔 셔츠
        P.poly([(0.3, 0.05), (0.42, 0.05), (0.5, 0.14), (0.58, 0.05), (0.7, 0.05), (1.0, 0.25), (0.88, 0.42),
                (0.78, 0.36), (0.78, 1.0), (0.22, 1.0), (0.22, 0.36), (0.12, 0.42), (0.0, 0.25)], col, primary=True)
    P.rect(0.26, 0.0, 0.34, 0.1, "light_wood", width=2)
    P.rect(0.66, 0.0, 0.74, 0.1, "light_wood", width=2)


def draw_chicken(P: Painter, pr: Prop):  # 닭 (머리가 한쪽을 향함)
    col = pr.color
    P.poly([(0.05, 0.25), (0.25, 0.4), (0.12, 0.55)], shade(col, 0.8))  # 꼬리
    P.ellipse(0.1, 0.3, 0.8, 0.85, col, primary=True)
    P.ellipse(0.56, 0.08, 0.9, 0.42, col)
    P.poly([(0.6, 0.12), (0.66, 0.0), (0.72, 0.08), (0.78, -0.01), (0.84, 0.1)], "red")
    P.poly([(0.88, 0.22), (1.0, 0.27), (0.88, 0.31)], "yellow")
    P.ellipse(0.74, 0.18, 0.8, 0.24, OUTLINE)
    P.ellipse(0.82, 0.3, 0.9, 0.42, "red", width=1)
    P.line([(0.38, 0.85), (0.36, 1.0)], fill="orange")
    P.line([(0.55, 0.85), (0.57, 1.0)], fill="orange")


def draw_bird(P: Painter, pr: Prop):  # 날아가는 새
    P.poly([(0.0, 0.5), (0.3, 0.3), (0.55, 0.45), (0.8, 0.35), (1.0, 0.45), (0.8, 0.5), (0.55, 0.62),
            (0.3, 0.5)], pr.color)
    P.poly([(0.3, 0.45), (0.45, 0.0), (0.55, 0.45)], shade(pr.color, 0.85))
    P.poly([(1.0, 0.45), (1.0, 0.45), (0.94, 0.5)], "yellow")


def draw_cloud(P: Painter, pr: Prop):
    blobs = [(0.0, 0.4, 0.4, 1.0), (0.22, 0.1, 0.62, 0.9), (0.5, 0.25, 0.95, 1.0)]
    if pr.variant == 1:
        blobs = [(0.0, 0.45, 0.5, 1.0), (0.3, 0.2, 0.75, 1.0), (0.6, 0.45, 1.0, 1.0)]
    for b in blobs:
        P.ellipse(*b, pr.color, outline=shade(pr.color, 0.86), width=max(2, P.lw // 2))
    P.rect(0.1, 0.7, 0.9, 0.98, pr.color, outline=None, width=0)


def draw_mailbox(P: Painter, pr: Prop):  # 빨간 우체통
    col = pr.color
    P.rect(0.3, 0.8, 0.7, 1.0, "dark_gray")
    P.rect(0.08, 0.15, 0.92, 0.82, col, primary=True, radius=0.04)
    P.chord(0.08, 0.0, 0.92, 0.3, 180, 360, col)
    P.rect(0.2, 0.3, 0.8, 0.38, "black")
    P.ellipse(0.38, 0.5, 0.62, 0.68, "white")


def draw_kettle(P: Painter, pr: Prop):  # 양은 주전자 (주둥이 방향)
    col = pr.color
    P.poly([(0.72, 0.62), (1.0, 0.22), (0.92, 0.2), (0.7, 0.48)], col)  # 주둥이
    P.ellipse(0.1, 0.3, 0.8, 1.0, col, primary=True)
    P.ellipse(0.3, 0.24, 0.6, 0.38, shade(col, 0.85))
    P.arc(0.15, 0.02, 0.75, 0.62, 200, 340, fill="dark_gray", width=P.lw + 1)
    P.ellipse(0.4, 0.18, 0.5, 0.28, shade(col, 0.7))


def draw_cauldron(P: Painter, pr: Prop):  # 가마솥
    col = pr.color
    P.ellipse(0.0, 0.32, 1.0, 0.52, shade(col, 0.9))  # 테
    P.chord(0.08, 0.0, 0.92, 1.0, 0, 180, col, primary=True)
    if pr.variant == 1:  # 높은 뚜껑
        P.chord(0.1, 0.0, 0.9, 0.84, 180, 360, shade(col, 1.25))
        P.ellipse(0.42, 0.0, 0.58, 0.14, "dark_earth")
    else:
        P.chord(0.12, 0.16, 0.88, 0.72, 180, 360, shade(col, 1.25))
        P.ellipse(0.42, 0.12, 0.58, 0.26, "dark_earth")


def draw_fire(P: Painter, pr: Prop):  # 아궁이 불
    P.poly([(0.1, 1.0), (0.2, 0.4), (0.35, 0.65), (0.5, 0.05), (0.65, 0.6), (0.8, 0.35), (0.9, 1.0)],
           pr.color, outline=shade(pr.color, 0.75))
    P.poly([(0.3, 1.0), (0.4, 0.6), (0.5, 0.75), (0.6, 0.5), (0.7, 1.0)], "yellow", outline=None, width=0)


def draw_cabbage(P: Painter, pr: Prop):  # 배추 더미
    for x0 in (0.0, 0.34, 0.17):
        y0 = 0.0 if x0 == 0.17 else 0.3
        P.ellipse(x0, y0, x0 + 0.66, y0 + 0.7, pr.color, primary=True)
        P.ellipse(x0 + 0.18, y0 + 0.3, x0 + 0.48, y0 + 0.7, "cream")


def draw_sack(P: Painter, pr: Prop):  # 쌀가마니
    P.poly([(0.1, 0.18), (0.9, 0.18), (1.0, 0.9), (0.0, 0.9)], pr.color, primary=True)
    P.ellipse(0.0, 0.8, 1.0, 1.0, shade(pr.color, 0.9))
    P.poly([(0.25, 0.18), (0.5, 0.0), (0.75, 0.18)], shade(pr.color, 0.9))
    for y in (0.4, 0.6):
        P.line([(0.06, y), (0.94, y)], fill=shade(pr.color, 0.7), width=max(2, P.lw // 2))
    if pr.extra.get("label"):
        P.ellipse(0.3, 0.42, 0.7, 0.75, "white", width=2)


def draw_kite(P: Painter, pr: Prop):  # 방패연
    col = pr.color
    P.line([(0.5, 1.0), (0.2, 1.4)], fill=OUTLINE, width=2)
    P.rect(0.1, 0.0, 0.9, 0.85, "white", width=P.lw)
    P.ellipse(0.38, 0.28, 0.62, 0.56, "white")
    P.rect(0.1, 0.0, 0.9, 0.16, col, primary=True)
    P.poly([(0.1, 0.85), (0.3, 0.85), (0.24, 1.0), (0.16, 1.0)], col)
    P.poly([(0.7, 0.85), (0.9, 0.85), (0.84, 1.0), (0.76, 1.0)], col)
    P.line([(0.1, 0.0), (0.9, 0.85)], fill=shade(col, 0.8), width=2)
    P.line([(0.9, 0.0), (0.1, 0.85)], fill=shade(col, 0.8), width=2)


def draw_puddle(P: Painter, pr: Prop):
    P.ellipse(0.0, 0.2, 1.0, 1.0, pr.color, outline=shade(pr.color, 0.8), width=2)
    P.arc(0.2, 0.4, 0.7, 0.8, 200, 300, fill="white", width=2)


def draw_basin(P: Painter, pr: Prop):  # 고무 대야
    P.poly([(0.0, 0.25), (1.0, 0.25), (0.86, 1.0), (0.14, 1.0)], pr.color, primary=True)
    P.ellipse(0.0, 0.1, 1.0, 0.42, shade(pr.color, 0.85))
    P.ellipse(0.08, 0.16, 0.92, 0.38, shade(pr.color, 0.65))


def draw_crate(P: Painter, pr: Prop):  # 병 상자
    for x in (0.12, 0.37, 0.62):
        P.rect(x, 0.0, x + 0.2, 0.5, pr.color2 or "green", radius=0.06)
        P.rect(x + 0.06, -0.08, x + 0.14, 0.06, "dark_gray")
    P.rect(0.0, 0.35, 1.0, 1.0, pr.color, primary=True)
    P.line([(0.02, 0.6), (0.98, 0.6)], fill=shade(pr.color, 0.7))


def draw_radio(P: Painter, pr: Prop):  # 트랜지스터 라디오
    P.arc(0.2, -0.3, 0.8, 0.4, 200, 340, fill="dark_gray", width=P.lw)
    P.rect(0.0, 0.1, 1.0, 1.0, pr.color, primary=True, radius=0.08)
    P.rect(0.08, 0.2, 0.56, 0.88, "cream", radius=0.04)
    for y in (0.34, 0.5, 0.66, 0.8):
        P.line([(0.12, y), (0.52, y)], fill="dark_earth", width=2)
    P.ellipse(0.66, 0.26, 0.9, 0.5, "dark_gray")
    P.ellipse(0.66, 0.6, 0.9, 0.84, "dark_gray")


DRAWERS: dict[str, Callable[[Painter, Prop], None]] = {
    "jar": draw_jar, "persimmon": draw_persimmon, "tree": draw_tree, "well": draw_well,
    "bucket": draw_bucket, "broom": draw_broom, "shoes": draw_shoes, "pot": draw_pot, "bowl": draw_bowl,
    "basket": draw_basket, "bicycle": draw_bicycle, "scale": draw_scale, "sign": draw_sign,
    "flowerpot": draw_flowerpot, "umbrella": draw_umbrella, "clothes": draw_clothes, "chicken": draw_chicken,
    "bird": draw_bird, "cloud": draw_cloud, "mailbox": draw_mailbox, "kettle": draw_kettle,
    "cauldron": draw_cauldron, "fire": draw_fire, "cabbage": draw_cabbage, "sack": draw_sack,
    "kite": draw_kite, "puddle": draw_puddle, "basin": draw_basin, "crate": draw_crate, "radio": draw_radio,
}

# 모양 변경에 쓸 수 있는 변형 개수
VARIANTS = {"jar": 3, "pot": 3, "bowl": 3, "basket": 2, "scale": 2, "sign": 2, "flowerpot": 2, "clothes": 2,
            "cloud": 2, "cauldron": 2, "bucket": 2}

PATTERNS = ["stripes", "dots", "checks", "hstripes"]


def render_prop(pr: Prop) -> Image.Image:
    x, y, w, h = pr.box
    P = Painter(w, h, pr)
    DRAWERS[pr.kind](P, pr)
    img = P.img
    if pr.flipped:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return img
