"""한글 글꼴 찾기. FONT_PATH → assets/fonts → 운영체제 기본 한글 글꼴 순서."""
from __future__ import annotations

import platform
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

SYSTEM_CANDIDATES = [
    # Windows (맑은 고딕)
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    # macOS
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/NanumGothicBold.ttf",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    # Linux
    "/usr/share/fonts/truetype/nanum/NanumSquareRoundEB.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


def supports_hangul(path: str) -> bool:
    try:
        f = ImageFont.truetype(path, 40)
        ga = f.getmask("가")
        missing = f.getmask("\U000F0000")  # 거의 모든 글꼴에 없는 문자 → '두부' 글리프
        return ga.getbbox() is not None and bytes(ga) != bytes(missing)
    except Exception:  # noqa: BLE001
        return False


@lru_cache(maxsize=8)
def find_font(preferred: str = "", fonts_dir: str = "") -> str:
    tried: list[str] = []
    candidates: list[str] = []
    if preferred:
        candidates.append(preferred)
    if fonts_dir and Path(fonts_dir).is_dir():
        files = sorted(p for p in Path(fonts_dir).iterdir() if p.suffix.lower() in {".ttf", ".otf", ".ttc"})
        # 굵은 글꼴 우선
        files.sort(key=lambda p: 0 if any(k in p.name.lower() for k in ("bold", "eb", "heavy", "black")) else 1)
        candidates += [str(p) for p in files]
    candidates += SYSTEM_CANDIDATES
    for c in candidates:
        tried.append(c)
        if Path(c).exists() and supports_hangul(c):
            return c
    raise FileNotFoundError(
        "한글 글꼴을 찾지 못했습니다. assets/fonts/ 에 한글 .ttf 파일(예: 나눔스퀘어라운드, Noto Sans KR — "
        "무료·상업적 이용 가능한 OFL 글꼴)을 넣거나 .env의 FONT_PATH를 지정하세요. "
        f"(운영체제: {platform.system()})"
    )


def load(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)
