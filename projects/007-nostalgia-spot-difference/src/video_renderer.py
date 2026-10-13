"""1080x1920 세로 영상 렌더링.

Pillow로 장면별 정지 화면(프레임)을 만들고 FFmpeg concat으로 이어 붙인다.
화면 전환은 부드러운 페이드 한 번씩만 쓰고, 번쩍임·빠른 전환은 넣지 않는다.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import audio
from .difference_editor import TYPE_LABELS
from .validator import circle_box

VW, VH = 1080, 1920
PAPER = (244, 234, 212)
INK = (78, 52, 36)
BROWN = (140, 92, 58)
ACCENT = (206, 76, 52)
IMG_W = 960
IMG_X = (VW - IMG_W) // 2


@dataclass
class Timeline:
    opening: float = 3.0
    problem: float = 20.0
    reveal: float = 10.0
    outro: float = 3.0

    @property
    def total(self) -> float:
        return self.opening + self.problem + self.reveal + self.outro


@dataclass
class RenderResult:
    video_path: Path
    preview_path: Path
    duration: float
    frames: list[Path] = field(default_factory=list)


class FFmpegError(RuntimeError):
    pass


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _fit_font(path: str, text: str, size: int, max_w: int) -> ImageFont.FreeTypeFont:
    while size > 20:
        f = _font(path, size)
        if f.getlength(text) <= max_w:
            return f
        size -= 2
    return _font(path, size)


def _text(d: ImageDraw.ImageDraw, xy, text, font, fill=INK, stroke=0, stroke_fill=(255, 250, 238), anchor="mm"):
    d.text(xy, text, font=font, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=stroke_fill)


def _paper(seed: int = 0) -> Image.Image:
    from .scenes import _paper_texture
    import numpy as np
    tex = _paper_texture(VW, VH, seed + 5)
    arr = np.ones((VH, VW, 3)) * np.array(PAPER, float) * tex[..., None]
    return Image.fromarray(arr.clip(0, 255).astype("uint8"), "RGB")


def _framed(img: Image.Image, h: int) -> Image.Image:
    im = img.resize((IMG_W, h), Image.LANCZOS)
    out = Image.new("RGB", (IMG_W + 12, h + 12), BROWN)
    out.paste(im, (6, 6))
    return out


def _draw_answers(canvas: Image.Image, diffs: list[dict], upto: int, origin: tuple[int, int], size: tuple[int, int],
                  font_path: str, highlight_last: bool = True) -> None:
    d = ImageDraw.Draw(canvas)
    ox, oy = origin
    w, h = size
    num_font = _font(font_path, 34)
    for k, diff in enumerate(diffs[:upto]):
        bn = diff["bbox_normalized"]
        c = circle_box([bn[0] * w, bn[1] * h, bn[2] * w, bn[3] * h])
        box = [ox + c[0], oy + c[1], ox + c[2], oy + c[3]]
        d.ellipse(box, outline=(255, 250, 238), width=13)
        d.ellipse(box, outline=ACCENT, width=7)
        # 번호 동그라미
        r = 24
        cx, cy = box[0] + (box[2] - box[0]) * 0.15, box[1] + (box[3] - box[1]) * 0.15
        cx, cy = max(ox + r, min(cx, ox + w - r)), max(oy + r, min(cy, oy + h - r))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ACCENT, outline=(255, 250, 238), width=3)
        _text(d, (cx, cy), str(diff["id"]), num_font, fill=(255, 255, 255))


SENTENCES = {
    "color_changed": "{label}의 색깔이 바뀌었어요",
    "shape_changed": "{label}의 모양이 바뀌었어요",
    "pattern_changed": "{label}의 무늬가 달라졌어요",
    "direction_changed": "{label}의 방향이 바뀌었어요",
}


def josa(word: str, pair: tuple[str, str]) -> str:
    """받침에 따라 이/가, 을/를, 은/는 등을 고른다."""
    if not word:
        return pair[1]
    ch = word[-1]
    if "가" <= ch <= "힣":
        return pair[0] if (ord(ch) - 0xAC00) % 28 else pair[1]
    return pair[1]


def answer_sentence(diff: dict) -> str:
    label = diff.get("label", "")
    t = diff["type"]
    if t == "object_added":
        return f"{label}{josa(label, ('이', '가'))} 새로 생겼어요"
    if t == "object_removed":
        return f"{label}{josa(label, ('이', '가'))} 사라졌어요"
    return SENTENCES[t].format(label=label)


def build_frames(puzzle: dict, original: Path, modified: Path, out_dir: Path, font_path: str,
                 tl: Timeline, seed: int) -> list[tuple[Path, float]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    a = Image.open(original).convert("RGB")
    b = Image.open(modified).convert("RGB")
    img_h = round(IMG_W * a.height / a.width)
    top_y, gap = 300, 28
    if top_y + img_h * 2 + gap > VH - 200:  # 세로로 긴 그림이면 줄인다
        img_h = (VH - 200 - top_y - gap) // 2
    ya, yb = top_y, top_y + img_h + gap
    n = puzzle["difference_count"]
    topic = puzzle["topic"]
    diffs = puzzle["differences"]
    frames: list[tuple[Path, float]] = []

    f_brand = _font(font_path, 46)
    f_topic = _fit_font(font_path, topic, 70, 760)
    f_sub = _font(font_path, 44)
    f_timer = _font(font_path, 66)

    base = _paper(seed)
    fa, fb = _framed(a, img_h), _framed(b, img_h)

    def header(canvas: Image.Image, sub: str):
        d = ImageDraw.Draw(canvas)
        _text(d, (VW // 2 - 70, 70), "그리운 옛날 풍경", f_brand, fill=BROWN)
        _text(d, (VW // 2 - 70, 152), topic, f_topic, fill=INK, stroke=2)
        _text(d, (VW // 2 - 70, 232), sub, f_sub, fill=BROWN)

    def timer(canvas: Image.Image, text: str, frac: float):
        d = ImageDraw.Draw(canvas)
        cx, cy, r = 955, 150, 82
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 250, 238), outline=BROWN, width=6)
        if frac > 0:
            d.pieslice([cx - r + 10, cy - r + 10, cx + r - 10, cy + r - 10], -90, -90 + 360 * frac,
                       fill=(250, 214, 170))
        _text(d, (cx, cy + 2), text, f_timer, fill=ACCENT if text.isdigit() and int(text) <= 5 else INK)

    def boards(canvas: Image.Image):
        canvas.paste(fa, (IMG_X - 6, ya - 6))
        canvas.paste(fb, (IMG_X - 6, yb - 6))

    def save(img: Image.Image, name: str, dur: float):
        p = out_dir / f"{len(frames):03d}_{name}.png"
        img.save(p, compress_level=1)  # 임시 프레임: 압축보다 속도
        frames.append((p, dur))

    # 1) 오프닝: 제목 + 원본 그림 카드 + 안내
    op = base.copy()
    d = ImageDraw.Draw(op)
    _text(d, (VW // 2, 330), "그리운 옛날 풍경", _font(font_path, 96), fill=INK, stroke=4)
    _text(d, (VW // 2, 470), topic, _fit_font(font_path, topic, 84, 900), fill=BROWN, stroke=3)
    card_y = (VH - img_h) // 2
    op.paste(fa, (IMG_X - 6, card_y - 6))
    _text(d, (VW // 2, card_y + img_h + 130), f"다른 그림 {n}개를", _font(font_path, 80), fill=INK, stroke=4)
    _text(d, (VW // 2, card_y + img_h + 240), "찾아보세요!", _font(font_path, 80), fill=ACCENT, stroke=4)
    save(op, "opening", tl.opening)

    # 2) 문제 (1초마다 타이머)
    secs = int(round(tl.problem))
    prob_base = base.copy()
    header(prob_base, f"다른 그림 {n}개를 찾아보세요")
    boards(prob_base)
    for s in range(secs):
        fr = prob_base.copy()
        remain = secs - s
        timer(fr, str(remain), remain / secs)
        d = ImageDraw.Draw(fr)
        bar_w = int((VW - 2 * IMG_X) * remain / secs)
        d.rounded_rectangle([IMG_X, yb + img_h + 30, IMG_X + bar_w, yb + img_h + 50], radius=10, fill=(222, 170, 110))
        save(fr, f"problem{s:02d}", tl.problem / secs)

    # 3) 정답 공개 (하나씩, 앞의 정답은 계속 보이게)
    each = tl.reveal / max(1, len(diffs))
    rev_base = base.copy()
    header(rev_base, "정답을 확인해 보세요")
    boards(rev_base)
    timer(rev_base, "정답", 0)
    for k in range(1, len(diffs) + 1):
        fr = rev_base.copy()
        _draw_answers(fr, diffs, k, (IMG_X, ya), (IMG_W, img_h), font_path)
        _draw_answers(fr, diffs, k, (IMG_X, yb), (IMG_W, img_h), font_path)
        d = ImageDraw.Draw(fr)
        cap = f"{diffs[k - 1]['id']}. {answer_sentence(diffs[k - 1])}"
        _text(d, (VW // 2, yb + img_h + 75), cap, _fit_font(font_path, cap, 50, 980), fill=INK, stroke=3)
        save(fr, f"reveal{k:02d}", each)

    # 4) 마무리: 정답이 표시된 그림 카드 + 인사
    end = base.copy()
    card_y = (VH - img_h) // 2
    end.paste(fb, (IMG_X - 6, card_y - 6))
    _draw_answers(end, diffs, len(diffs), (IMG_X, card_y), (IMG_W, img_h), font_path)
    d = ImageDraw.Draw(end)
    _text(d, (VW // 2, card_y - 150), "몇 개나 찾으셨나요?", _font(font_path, 86), fill=INK, stroke=4)
    _text(d, (VW // 2, card_y + img_h + 130), "다음 추억 여행에서", _font(font_path, 72), fill=BROWN, stroke=3)
    _text(d, (VW // 2, card_y + img_h + 230), "만나요!", _font(font_path, 72), fill=BROWN, stroke=3)
    save(end, "outro", tl.outro)
    return frames


def build_preview(puzzle: dict, original: Path, modified: Path, out_path: Path, font_path: str) -> Path:
    """사람이 정답을 빠르게 확인하는 미리보기: 원본 | 수정본(정답 원 표시)."""
    a = Image.open(original).convert("RGB")
    b = Image.open(modified).convert("RGB")
    w, h = a.size
    sheet = Image.new("RGB", (w * 2 + 30, h + 90), PAPER)
    sheet.paste(a, (10, 80))
    sheet.paste(b, (w + 20, 80))
    _draw_answers(sheet, puzzle["differences"], len(puzzle["differences"]), (w + 20, 80), (w, h), font_path)
    _draw_answers(sheet, puzzle["differences"], len(puzzle["differences"]), (10, 80), (w, h), font_path)
    d = ImageDraw.Draw(sheet)
    title = f"{puzzle['topic']} · 차이 {puzzle['difference_count']}개 · " + ", ".join(
        f"{x['id']}.{x['label']}({TYPE_LABELS.get(x['type'], x['type'])})" for x in puzzle["differences"])
    _text(d, (20, 40), title, _fit_font(font_path, title, 36, w * 2 - 20), anchor="lm")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return out_path


def _run(cmd: list[str], timeout: int = 600) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise FFmpegError(f"FFmpeg 실패 (code {proc.returncode}): {proc.stderr.strip()[-800:]}")


def render_video(puzzle: dict, original: Path, modified: Path, work_dir: Path, out_path: Path, font_path: str,
                 seed: int, music_dir: Path | None = None, music_volume: float = 0.18,
                 tl: Timeline | None = None) -> RenderResult:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FFmpegError("ffmpeg를 찾을 수 없습니다. 설치 후 PATH에 추가하세요 (README 참고).")
    tl = tl or Timeline()
    frames = build_frames(puzzle, original, modified, work_dir / "frames", font_path, tl, seed)

    concat = work_dir / "frames.txt"
    lines = []
    for p, dur in frames:
        lines.append(f"file '{p.resolve().as_posix()}'")
        lines.append(f"duration {dur:.4f}")
    lines.append(f"file '{frames[-1][0].resolve().as_posix()}'")  # concat 마지막 프레임 규칙
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")

    n = max(1, len(puzzle["differences"]))
    reveal_start = tl.opening + tl.problem
    reveal_times = [reveal_start + k * tl.reveal / n for k in range(n)]
    user_music = audio.pick_user_music(music_dir, seed) if music_dir else None
    music_wav, chime_wav = audio.build_audio(tl.total, reveal_times, seed, work_dir, with_music=user_music is None)

    total = tl.total
    vf = (f"fps=30,format=yuv420p,fade=t=in:st=0:d=0.6,fade=t=out:st={total - 0.8:.2f}:d=0.8,"
          f"setsar=1")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat)]
    if user_music:
        cmd += ["-stream_loop", "-1", "-i", str(user_music), "-i", str(chime_wav)]
        af = (f"[1:a]atrim=0:{total:.2f},volume={music_volume},afade=t=in:st=0:d=1,"
              f"afade=t=out:st={total - 1.5:.2f}:d=1.5[m];[2:a]volume=1.0[c];"
              f"[m][c]amix=inputs=2:normalize=0:duration=first[a]")
    else:
        cmd += ["-i", str(music_wav), "-i", str(chime_wav)]
        af = "[1:a][2:a]amix=inputs=2:normalize=0:duration=first[a]"
    cmd += ["-filter_complex", af, "-map", "0:v", "-map", "[a]", "-vf", vf,
            "-c:v", "libx264", "-preset", "faster", "-tune", "stillimage", "-crf", "20", "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-t", f"{total:.2f}", "-movflags", "+faststart",
            str(out_path)]
    _run(cmd)
    return RenderResult(video_path=out_path, preview_path=Path(), duration=total, frames=[p for p, _ in frames])
