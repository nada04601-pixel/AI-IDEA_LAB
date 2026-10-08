"""장면 대사와 길이로 자막 타이밍을 만든다."""

import re
from dataclasses import dataclass

MAX_CUE_CHARS = 28  # 자막 한 개(최대 2줄)에 넣을 글자 수
LINE_CHARS = 16  # 한 줄 글자 수 (세로 화면 기준)


@dataclass(frozen=True)
class Cue:
    index: int
    start: float
    end: float
    text: str
    scene_number: int


def split_sentences(text: str) -> list[str]:
    """문장 부호·줄바꿈으로 나눈 뒤, 긴 문장은 띄어쓰기 기준으로 MAX_CUE_CHARS 이하로 자른다."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?。！？])\s+|\n+", text) if p.strip()]
    chunks: list[str] = []
    for part in parts:
        current = ""
        for word in part.split():
            while len(word) > MAX_CUE_CHARS:  # 띄어쓰기 없이 긴 단어
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(word[:MAX_CUE_CHARS])
                word = word[MAX_CUE_CHARS:]
            candidate = f"{current} {word}".strip()
            if len(candidate) > MAX_CUE_CHARS and current:
                chunks.append(current)
                current = word
            else:
                current = candidate
        if current:
            chunks.append(current)
    return chunks


def wrap_lines(text: str) -> str:
    """한 줄이 LINE_CHARS를 넘으면 가운데 가까운 띄어쓰기에서 두 줄로 나눈다."""
    if len(text) <= LINE_CHARS or " " not in text:
        return text
    mid = len(text) // 2
    spaces = [i for i, ch in enumerate(text) if ch == " "]
    cut = min(spaces, key=lambda i: abs(i - mid))
    return text[:cut] + "\n" + text[cut + 1 :]


def build_cues(scenes: list[tuple[int, str, float]]) -> list[Cue]:
    """scenes: (장면 번호, 대사, 길이) 순서 목록. 장면 안에서는 글자 수에 비례해 시간을 나눈다."""
    cues: list[Cue] = []
    offset = 0.0
    for number, dialogue, duration in scenes:
        chunks = split_sentences(dialogue)
        total = sum(len(c) for c in chunks)
        t = offset
        for i, chunk in enumerate(chunks):
            end = offset + duration if i == len(chunks) - 1 else t + duration * len(chunk) / total
            cues.append(Cue(len(cues) + 1, round(t, 3), round(end, 3), wrap_lines(chunk), number))
            t = end
        offset += duration
    return cues


def _srt_time(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: list[Cue]) -> str:
    blocks = [f"{c.index}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n{c.text}\n" for c in cues]
    return "\n".join(blocks)
