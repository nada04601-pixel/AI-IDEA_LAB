"""문제들을 1080x1920 세로 쇼츠 MP4로 만든다.

문제 하나의 흐름:
  1) 시작 (INTRO_SEC)   : 문제 번호 + "틀린 곳 N개를 찾아보세요!" (띠링)
  2) 카운트다운 (time_sec): 하단 타이머 바가 줄어든다 (매초 째깍, 마지막 3초는 빨간색)
  3) 정답 공개           : 틀린 곳에 빨간 원이 하나씩 나타난다 (띵)
마지막에 "몇 개 찾으셨나요? 댓글로!" 화면을 붙인다.
프레임은 Pillow로 그리고 FFmpeg에 바로 넘겨 인코딩한다.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .scene import H as IMG_H, W as IMG_W, Puzzle

VW, VH, FPS = 1080, 1920, 30
SR = 44100

# 화면 배치 (세로 1920)
IMG_X = (VW - IMG_W) // 2
IMG_A_Y = 200
IMG_B_Y = IMG_A_Y + IMG_H + 24
BAR_Y = IMG_B_Y + IMG_H + 44
BAR_H = 56
BAR_X0, BAR_X1 = 150, VW - 50

INTRO_SEC = 1.0
REVEAL_STEP_SEC = 0.6
REVEAL_HOLD_SEC = 1.6
OUTRO_SEC = 2.5

BG = (22, 30, 60)
YELLOW = (255, 214, 10)
RED = (255, 59, 48)
WHITE = (255, 255, 255)

FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]


def find_font(path: str | None = None) -> str | None:
    for p in [path, os.environ.get("SPOTDIFF_FONT"), *FONT_CANDIDATES]:
        if p and Path(p).exists():
            return p
    return None


class Fonts:
    def __init__(self, path: str | None):
        if path is None:
            print("경고: 한글 글꼴을 찾지 못해 글자가 깨질 수 있습니다. --font 로 .ttf 경로를 지정하세요.", file=sys.stderr)
        self.path = path
        self._cache: dict[int, ImageFont.FreeTypeFont] = {}

    def __call__(self, size: int):
        if size not in self._cache:
            self._cache[size] = ImageFont.truetype(self.path, size) if self.path else ImageFont.load_default(size)
        return self._cache[size]


def _text_center(d, cx, cy, text, font, fill, stroke=0, stroke_fill=(0, 0, 0)):
    d.text((cx, cy), text, font=font, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=stroke_fill)


# ---------------------------------------------------------------- 화면 조각


def _base_frame(p: Puzzle) -> Image.Image:
    f = Image.new("RGB", (VW, VH), BG)
    d = ImageDraw.Draw(f)
    for y in (IMG_A_Y, IMG_B_Y):
        d.rounded_rectangle([IMG_X - 8, y - 8, IMG_X + IMG_W + 8, y + IMG_H + 8], 18, fill=WHITE)
    f.paste(p.image_a, (IMG_X, IMG_A_Y))
    f.paste(p.image_b, (IMG_X, IMG_B_Y))
    return f


def _header(d, fonts, idx, total, text, color=WHITE):
    pill = f"문제 {idx + 1} / {total}"
    d.rounded_rectangle([VW / 2 - 130, 24, VW / 2 + 130, 82], 29, fill=YELLOW)
    _text_center(d, VW / 2, 53, pill, fonts(36), BG)
    _text_center(d, VW / 2, 145, text, fonts(64), color, stroke=4, stroke_fill=(0, 0, 0))


def _bar_color(frac_left: float):
    # 초록 → 노랑 → 빨강
    g, y, r = (52, 199, 89), YELLOW, RED
    if frac_left > 0.5:
        t = (1 - frac_left) / 0.5
        a, b = g, y
    else:
        t = (0.5 - frac_left) / 0.5
        a, b = y, r
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _timer_bar(d, fonts, frac_left: float, secs_left: int, pulse: float = 0.0):
    d.rounded_rectangle([BAR_X0, BAR_Y, BAR_X1, BAR_Y + BAR_H], BAR_H // 2, fill=(60, 66, 95))
    w = (BAR_X1 - BAR_X0) * max(0.0, min(1.0, frac_left))
    if w >= BAR_H:
        d.rounded_rectangle([BAR_X0, BAR_Y, BAR_X0 + w, BAR_Y + BAR_H], BAR_H // 2, fill=_bar_color(frac_left))
    elif w > 0:
        d.ellipse([BAR_X0, BAR_Y, BAR_X0 + BAR_H, BAR_Y + BAR_H], fill=_bar_color(frac_left))
    r = 46 + 8 * pulse
    cx, cy = 85, BAR_Y + BAR_H / 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_bar_color(frac_left) if secs_left <= 3 else WHITE)
    _text_center(d, cx, cy + 2, str(secs_left), fonts(int(54 + 10 * pulse)), BG)


def _ease_out_back(t: float) -> float:
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    return 1 + (c1 + 1) * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _answer_circle(d, box, scale: float):
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2 + IMG_X, (y0 + y1) / 2
    r = max(32, max(x1 - x0, y1 - y0) / 2 + 10) * scale
    if r <= 2:
        return
    for oy in (IMG_A_Y, IMG_B_Y):
        y = cy + oy
        d.ellipse([cx - r - 4, y - r - 4, cx + r + 4, y + r + 4], outline=WHITE, width=14)
        d.ellipse([cx - r, y - r, cx + r, y + r], outline=RED, width=8)


# ---------------------------------------------------------------- 소리


def _tone(freqs, dur, vol, decay):
    t = np.arange(int(SR * dur)) / SR
    wave_ = sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs)
    return (wave_ * np.exp(-t * decay) * vol).astype(np.float32)


SOUNDS = {
    "tick": _tone([1800], 0.05, 0.35, 90),
    "tick_hot": _tone([2400, 1200], 0.09, 0.6, 50),
    "start": np.concatenate([_tone([523], 0.09, 0.4, 20), _tone([659], 0.09, 0.4, 20), _tone([784], 0.3, 0.45, 9)]),
    "buzzer": _tone([220, 233], 0.35, 0.5, 6),
    "ding": _tone([1319, 1760], 0.5, 0.5, 7),
    "outro": np.concatenate([_tone([784], 0.12, 0.4, 15), _tone([1047], 0.5, 0.45, 6)]),
}


def _write_audio(path: Path, events: list[tuple[float, str]], total_sec: float) -> None:
    buf = np.zeros(int(SR * total_sec) + SR, dtype=np.float32)
    for t, name in events:
        s = SOUNDS[name]
        i = int(t * SR)
        buf[i:i + len(s)] += s[: len(buf) - i]
    pcm = (np.clip(buf[: int(SR * total_sec)], -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- 영상


@dataclass
class VideoConfig:
    time_sec: float = 8.0
    font: str | None = None
    outro_text: str = "몇 개 찾으셨나요?"
    outro_sub: str = "댓글로 알려주세요!"


def _frames(puzzles: list[Puzzle], cfg: VideoConfig, fonts: Fonts, events: list):
    n = len(puzzles)
    t0 = 0.0
    for idx, p in enumerate(puzzles):
        base = _base_frame(p)
        k = len(p.differences)
        ask = f"틀린 곳 {k}개를 찾아보세요!"
        reveal_sec = REVEAL_STEP_SEC * k + REVEAL_HOLD_SEC
        dur = INTRO_SEC + cfg.time_sec + reveal_sec
        events.append((t0, "start"))
        for s in range(int(math.ceil(cfg.time_sec))):
            left = cfg.time_sec - s
            events.append((t0 + INTRO_SEC + s, "tick_hot" if left <= 3 else "tick"))
        events.append((t0 + INTRO_SEC + cfg.time_sec, "buzzer"))
        for j in range(k):
            events.append((t0 + INTRO_SEC + cfg.time_sec + 0.3 + j * REVEAL_STEP_SEC, "ding"))

        for fi in range(int(round(dur * FPS))):
            t = fi / FPS
            f = base.copy()
            d = ImageDraw.Draw(f)
            if t < INTRO_SEC + cfg.time_sec:
                tc = max(0.0, t - INTRO_SEC)
                left = cfg.time_sec - tc
                secs_left = int(math.ceil(left - 1e-6))
                pulse = 0.0
                if secs_left <= 3 and t >= INTRO_SEC:
                    pulse = max(0.0, 1 - (tc % 1.0) / 0.35)
                _header(d, fonts, idx, n, ask)
                _timer_bar(d, fonts, left / cfg.time_sec, secs_left, pulse)
            else:
                tr = t - INTRO_SEC - cfg.time_sec
                _header(d, fonts, idx, n, "정답 공개!", YELLOW)
                _timer_bar(d, fonts, 0.0, 0)
                for j, diff in enumerate(p.differences):
                    local = tr - 0.3 - j * REVEAL_STEP_SEC
                    if local > 0:
                        _answer_circle(d, diff.box, _ease_out_back(local / 0.25))
            yield f
        t0 += dur

    # 마무리 화면: 마지막 문제 정답 위에 어둡게 덮고 문구
    last = f.copy()
    overlay = Image.new("RGB", (VW, VH), BG)
    events.append((t0, "outro"))
    for fi in range(int(OUTRO_SEC * FPS)):
        a = min(1.0, fi / (0.3 * FPS)) * 0.82
        frame = Image.blend(last, overlay, a)
        d = ImageDraw.Draw(frame)
        pop = _ease_out_back(fi / (0.35 * FPS))
        _text_center(d, VW / 2, VH / 2 - 70, cfg.outro_text, fonts(max(10, int(86 * pop))), YELLOW,
                     stroke=5, stroke_fill=(0, 0, 0))
        _text_center(d, VW / 2, VH / 2 + 60, cfg.outro_sub, fonts(56), WHITE)
        yield frame
    t0 += OUTRO_SEC
    events.append((t0, "end"))


def render_video(puzzles: list[Puzzle], out_path, cfg: VideoConfig | None = None) -> Path:
    cfg = cfg or VideoConfig()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg를 찾지 못했습니다. FFmpeg를 설치하고 PATH에 추가하세요.")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fonts = Fonts(find_font(cfg.font))
    events: list = []

    with tempfile.TemporaryDirectory() as tmp:
        silent = Path(tmp) / "video.mp4"
        proc = subprocess.Popen(
            [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}",
             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-pix_fmt", "yuv420p", str(silent)],
            stdin=subprocess.PIPE,
        )
        try:
            for frame in _frames(puzzles, cfg, fonts, events):
                proc.stdin.write(frame.tobytes())
        finally:
            proc.stdin.close()
            proc.wait()
        if proc.returncode != 0:
            raise RuntimeError("FFmpeg 영상 인코딩에 실패했습니다.")

        total = events[-1][0]
        audio = Path(tmp) / "audio.wav"
        _write_audio(audio, [e for e in events if e[1] != "end"], total)
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", str(silent), "-i", str(audio), "-c:v", "copy",
             "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out_path)],
            check=True,
        )
    return out_path


def answer_image(p: Puzzle) -> Image.Image:
    """정답 원을 그린 확인용 이미지 (위: 원본, 아래: 바뀐 그림)."""
    f = _base_frame(p)
    d = ImageDraw.Draw(f)
    for diff in p.differences:
        _answer_circle(d, diff.box, 1.0)
    return f.crop((0, IMG_A_Y - 20, VW, IMG_B_Y + IMG_H + 20))
