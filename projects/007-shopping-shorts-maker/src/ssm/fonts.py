"""자막·썸네일용 폰트 내려받기. 상업적 이용이 가능한 OFL 폰트만, 고정 주소 + SHA256 확인."""

import hashlib
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ssm.config import app_root

PRETENDARD = "https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9/packages/pretendard/dist/public/static"


@dataclass(frozen=True)
class Font:
    filename: str
    url: str
    sha256: str
    license: str


FONTS = [
    Font("Pretendard-ExtraBold.otf", f"{PRETENDARD}/Pretendard-ExtraBold.otf",
         "c35fe941b7568d52a96010561540e47f9d3948dfde66ba25bc1908233e0a40cd", "SIL OFL 1.1"),
    Font("Pretendard-Bold.otf", f"{PRETENDARD}/Pretendard-Bold.otf",
         "2e91915fab54df71cc9598ebf608b2bdb54c6fe3c066ac61dff0bc44fca71cc7", "SIL OFL 1.1"),
    Font("Pretendard-Black.otf", f"{PRETENDARD}/Pretendard-Black.otf",
         "94628b0bcea8936b6e5c30d98d685eb9bbaffb0fe2ed255542ecc656c248e021", "SIL OFL 1.1"),
    Font("BlackHanSans-Regular.ttf",
         "https://raw.githubusercontent.com/google/fonts/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
         "31960809284026681774a8e52dc19ebcad26cf69b0ad9d560f288296fbb52739", "SIL OFL 1.1"),
]


def fonts_dir() -> Path:
    return app_root() / "assets" / "fonts"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font_status(font: Font) -> str:
    """ok | missing | mismatch"""
    path = fonts_dir() / font.filename
    if not path.is_file():
        return "missing"
    return "ok" if sha256_of(path) == font.sha256 else "mismatch"


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "shopping-shorts-maker"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def install_fonts(force: bool = False, download: Callable[[str], bytes] = _download,
                  log: Callable[[str], None] = print) -> list[str]:
    """빠진 폰트를 받는다. 실패한 폰트 이름 목록을 돌려준다 (전부 성공하면 빈 목록)."""
    target = fonts_dir()
    target.mkdir(parents=True, exist_ok=True)
    failed = []
    for font in FONTS:
        if not force and font_status(font) == "ok":
            log(f"  [있음] {font.filename}")
            continue
        try:
            data = download(font.url)
        except OSError as e:
            log(f"  [실패] {font.filename}: 내려받지 못했습니다 ({e})")
            failed.append(font.filename)
            continue
        if hashlib.sha256(data).hexdigest() != font.sha256:
            log(f"  [실패] {font.filename}: 파일 내용이 예상과 다릅니다 (체크섬 불일치)")
            failed.append(font.filename)
            continue
        tmp = target / (font.filename + ".part")
        tmp.write_bytes(data)
        tmp.replace(target / font.filename)
        log(f"  [받음] {font.filename} ({len(data) // 1024} KB, {font.license})")
    return failed
