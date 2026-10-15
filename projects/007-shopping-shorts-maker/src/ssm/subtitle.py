"""한국어 자막 (기획서 Module 4).

- 화면 나누기: 한 줄 최대 max_chars_per_line자, 최대 2줄, 한 화면 0.6~2.5초. 어절 중간에서 자르지 않는다.
- 렌더링: Pillow로 자막·광고 표시 PNG를 만들고 FFmpeg overlay로 얹는다 (Windows drawtext 폰트 경로 문제 회피).
"""

import math
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

from ssm.config import SubtitleCfg
from ssm.schemas import SentenceTiming, WordTimings

MAX_LINES = 2
MIN_CUE_SEC = 0.6
MAX_CUE_SEC = 2.5
HOLD_GAP_SEC = 1.0  # 문장 사이 무음이 이보다 짧으면 앞 자막을 다음 자막이 나올 때까지 유지
TAIL_SEC = 0.3
PAUSE_MARKS = ",.?!~…"
PAUSE_SPLIT_SEC = 1.0  # 쉼표까지가 이보다 길면 거기서 화면을 넘긴다

# 1080x1920 기준 플랫폼 세이프존: 이 여백 안에는 핵심 텍스트를 두지 않는다
REF_WIDTH = 1080
SAFE_TOP, SAFE_BOTTOM, SAFE_RIGHT, SAFE_LEFT = 250, 400, 150, 48
STROKE_COLOR = (0, 0, 0, 255)


@dataclass
class Token:
    """어절 하나와 그 어절이 읽히는 시간."""
    text: str
    start: float
    end: float


@dataclass
class Cue:
    """자막 한 화면."""
    start: float
    end: float
    lines: list[str]
    emphasis: list[str]


# ---- 시간 맞추기·화면 나누기 ------------------------------------------------------


def _norm(text: str) -> str:
    return re.sub(r"[\W_]", "", text)


def _even(texts: list[str], start: float, end: float) -> list[Token]:
    """글자 수에 비례해 시간을 나눠 준다 (TTS 단어 경계를 맞출 수 없을 때)."""
    weights = [max(len(_norm(t)), 1) for t in texts]
    total, t, tokens = sum(weights), start, []
    for text, w in zip(texts, weights):
        nxt = t + (end - start) * w / total
        tokens.append(Token(text, t, nxt))
        t = nxt
    return tokens


def align_tokens(sentence: SentenceTiming) -> list[Token]:
    """문장 원문(문장부호 포함)의 어절마다 TTS 단어 경계 시간을 붙인다."""
    texts = sentence.text.split()
    words = [w for w in sentence.words if _norm(w.text)]
    span = (words[0].start, words[-1].end) if words else (sentence.start, sentence.end)
    owner: list[int] = []  # 정규화한 글자마다 몇 번째 어절인지
    for i, t in enumerate(texts):
        owner += [i] * len(_norm(t))
    joined = "".join(_norm(t) for t in texts)

    starts: list[float | None] = [None] * len(texts)
    ends: list[float | None] = [None] * len(texts)
    cursor = 0
    for w in words:
        nw = _norm(w.text)
        pos = joined.find(nw, cursor)
        if pos < 0:  # 숫자를 다르게 읽는 등 원문과 어긋나면 비례 배분
            return _even(texts, *span)
        for k in range(pos, pos + len(nw)):
            i = owner[k]
            starts[i] = w.start if starts[i] is None else min(starts[i], w.start)
            ends[i] = w.end if ends[i] is None else max(ends[i], w.end)
        cursor = pos + len(nw)
    if not words or all(s is None for s in starts):
        return _even(texts, *span)

    tokens: list[Token] = []
    i = 0
    while i < len(texts):  # 시간을 못 받은 어절(기호만 있는 어절 등)은 앞뒤 사이를 나눠 준다
        if starts[i] is not None:
            tokens.append(Token(texts[i], starts[i], ends[i]))
            i += 1
            continue
        j = i
        while j < len(texts) and starts[j] is None:
            j += 1
        gap_start = tokens[-1].end if tokens else span[0]
        gap_end = starts[j] if j < len(texts) else span[1]
        tokens += _even(texts[i:j], gap_start, max(gap_end, gap_start))
        i = j
    return tokens


def wrap(words: list[str], max_chars: int) -> list[str] | None:
    """어절들을 최대 2줄로 나눈다 (두 줄 길이를 최대한 비슷하게). 들어가지 않으면 None."""
    one = " ".join(words)
    if len(one) <= max_chars or len(words) == 1:  # 한 어절이 너무 길면 자르지 않고 그대로 둔다
        return [one]
    best: tuple[int, list[str]] | None = None
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        score = max(len(a), len(b)) - (2 if a[-1] in PAUSE_MARKS else 0)  # 쉼표 등 뒤에서 나누는 쪽을 선호
        if len(a) <= max_chars and len(b) <= max_chars and (best is None or score < best[0]):
            best = (score, [a, b])
    return best[1] if best else None


def build_cues(timings: WordTimings, max_chars: int, video_end: float) -> list[Cue]:
    cues: list[Cue] = []
    for sentence in timings.sentences:
        groups: list[list[Token]] = []
        group: list[Token] = []
        for tok in align_tokens(sentence):
            cand = group + [tok]
            too_long = wrap([t.text for t in cand], max_chars) is None
            too_slow = cand[-1].end - cand[0].start > MAX_CUE_SEC
            if group and (too_long or too_slow):
                groups.append(group)
                group = [tok]
            else:
                group = cand
            if tok.text[-1] in PAUSE_MARKS and group[-1].end - group[0].start >= PAUSE_SPLIT_SEC:
                groups.append(group)  # 쉼표에서 쉬는 곳은 화면도 넘긴다
                group = []
        if group:
            groups.append(group)

        merged: list[list[Token]] = []  # 너무 짧게 지나가는 화면은 앞 화면과 합친다
        for g in groups:
            if merged and g[-1].end - g[0].start < MIN_CUE_SEC and \
                    wrap([t.text for t in merged[-1] + g], max_chars) is not None:
                merged[-1] = merged[-1] + g
            else:
                merged.append(g)
        for g in merged:
            cues.append(Cue(g[0].start, g[-1].end, wrap([t.text for t in g], max_chars), sentence.emphasis))

    for i, cue in enumerate(cues):  # 자막이 깜빡이지 않게 다음 화면까지 이어 붙인다
        nxt = cues[i + 1].start if i + 1 < len(cues) else video_end
        if i + 1 == len(cues) or nxt - cue.end <= HOLD_GAP_SEC:
            cue.end = nxt
        else:
            cue.end = min(max(cue.end + TAIL_SEC, cue.start + MIN_CUE_SEC), nxt)
    return cues


def _srt_time(t: float) -> str:
    ms = max(round(t * 1000), 0)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: list[Cue]) -> str:
    blocks = [f"{i}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n" + "\n".join(c.lines)
              for i, c in enumerate(cues, start=1)]
    return "\n\n".join(blocks) + "\n"


# ---- PNG 렌더링 -----------------------------------------------------------------


def emphasis_mask(lines: list[str], emphasis: list[str]) -> list[list[bool]]:
    """줄마다 글자별 강조 여부. 줄바꿈에 걸친 강조어도 찾는다."""
    joined = "\n".join(lines)
    mask = [False] * len(joined)
    for phrase in emphasis:
        parts = phrase.split()
        if not parts:
            continue
        for m in re.finditer(r"\s+".join(map(re.escape, parts)), joined):
            mask[m.start():m.end()] = [True] * (m.end() - m.start())
    out, pos = [], 0
    for line in lines:
        out.append(mask[pos:pos + len(line)])
        pos += len(line) + 1
    return out


def _runs(line: str, mask: list[bool]) -> list[tuple[str, bool]]:
    runs: list[tuple[str, bool]] = []
    for ch, flag in zip(line, mask):
        if runs and runs[-1][1] == flag:
            runs[-1] = (runs[-1][0] + ch, flag)
        else:
            runs.append((ch, flag))
    return runs


def render_cue(cue: Cue, cfg: SubtitleCfg, font_path: Path, scale: float, out: Path) -> tuple[int, int]:
    """자막 한 화면을 투명 PNG로 저장하고 (가로, 세로)를 돌려준다."""
    size, stroke = round(cfg.size * scale), round(cfg.stroke_width * scale)
    font = ImageFont.truetype(str(font_path), size)
    ascent, descent = font.getmetrics()
    line_h = round((ascent + descent) * 1.08)
    pad = stroke + (round(size * 0.3) if cfg.box else 0) + 2
    widths = [font.getlength(line) for line in cue.lines]
    text_w = math.ceil(max(widths))
    w = text_w + 2 * pad
    h = line_h * (len(cue.lines) - 1) + ascent + descent + 2 * pad

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if cfg.box:
        draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=round(size * 0.25), fill=(0, 0, 0, 150))
    color, emph = ImageColor.getrgb(cfg.color), ImageColor.getrgb(cfg.emphasis_color)
    masks = emphasis_mask(cue.lines, cue.emphasis)
    for outline in (True, False):  # 외곽선을 먼저 모두 그려야 옆 글자의 외곽선이 글자를 덮지 않는다
        for i, (line, mask) in enumerate(zip(cue.lines, masks)):
            x, y = pad + (text_w - widths[i]) / 2, pad + i * line_h
            for text, flag in _runs(line, mask):
                if outline:
                    draw.text((x, y), text, font=font, fill=STROKE_COLOR, stroke_width=stroke, stroke_fill=STROKE_COLOR)
                else:
                    draw.text((x, y), text, font=font, fill=emph if flag else color)
                x += font.getlength(text)
    img.save(out)
    return w, h


def cue_position(size: tuple[int, int], frame: tuple[int, int], y_ratio: float) -> tuple[int, int]:
    """자막 위치: 가운데 정렬, 세로 중심은 y_ratio. 세이프존 밖으로 나가지 않게 당긴다."""
    (w, h), (fw, fh) = size, frame
    s = fw / REF_WIDTH
    x = min((fw - w) / 2, fw - SAFE_RIGHT * s - w)
    y = min(max(fh * y_ratio - h / 2, SAFE_TOP * s), fh - SAFE_BOTTOM * s - h)
    return max(round(x), 0), max(round(y), 0)


def _wrap_pixels(text: str, font: ImageFont.FreeTypeFont, max_w: float) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and font.getlength(lines[-1] + " " + word) <= max_w:
            lines[-1] += " " + word
            continue
        while font.getlength(word) > max_w and len(word) > 1:  # 한 어절이 한 줄보다 길 때만 글자 단위로 자른다
            k = max(i for i in range(1, len(word) + 1) if font.getlength(word[:i]) <= max_w or i == 1)
            lines.append(word[:k])
            word = word[k:]
        lines.append(word)
    return lines


def render_ad(text: str, font_path: Path, badge_font_path: Path, frame_w: int, out: Path) -> tuple[int, int]:
    """'광고' 배지 + 광고 문구(2줄 이내가 되도록 글자 크기 자동 조절)를 투명 PNG로 저장."""
    s = frame_w / REF_WIDTH
    pad, gap = round(14 * s), round(14 * s)
    badge_font = ImageFont.truetype(str(badge_font_path), round(32 * s))
    bx0, by0, bx1, by1 = badge_font.getbbox("광고")
    badge_w, badge_h = bx1 - bx0 + round(24 * s), by1 - by0 + round(18 * s)
    text_max_w = (REF_WIDTH - SAFE_LEFT - SAFE_RIGHT) * s - 2 * pad - badge_w - gap

    for px in range(30, 19, -1):  # 2줄에 들어갈 때까지 줄인다 (끝까지 안 들어가면 가장 작은 크기로 전부 표시)
        font = ImageFont.truetype(str(font_path), round(px * s))
        lines = _wrap_pixels(text, font, text_max_w)
        if len(lines) <= 2:
            break
    ascent, descent = font.getmetrics()
    line_h = round((ascent + descent) * 1.1)
    text_w = math.ceil(max(font.getlength(line) for line in lines))
    text_h = line_h * (len(lines) - 1) + ascent + descent
    w = pad * 2 + badge_w + gap + text_w
    h = pad * 2 + max(badge_h, text_h)

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=round(12 * s), fill=(0, 0, 0, 140))
    by = pad + (h - 2 * pad - badge_h) // 2
    draw.rounded_rectangle((pad, by, pad + badge_w, by + badge_h), radius=round(8 * s), fill=(255, 225, 77, 255))
    draw.text((pad + badge_w / 2, by + badge_h / 2), "광고", font=badge_font, fill=(0, 0, 0, 255), anchor="mm")
    ty = pad + (h - 2 * pad - text_h) // 2
    for i, line in enumerate(lines):
        draw.text((pad + badge_w + gap, ty + i * line_h), line, font=font, fill=(255, 255, 255, 255))
    img.save(out)
    return w, h


def ad_position(size: tuple[int, int], frame_w: int, position: str) -> tuple[int, int]:
    s = frame_w / REF_WIDTH
    x = (frame_w - size[0]) / 2 if position == "top_center" else SAFE_LEFT * s
    return round(x), round(SAFE_TOP * s)
