"""컷 배치 (기획서 Module 4 '자동 컷 편집 및 싱크 매칭').

1. 문장마다 한 구간을 만든다 → 컷 전환이 문장 경계(다음 문장 첫 단어 시작)에 맞는다.
2. MAX_CUT_SEC보다 긴 구간은 단어 경계에서 나눈다. MIN_CUT_SEC보다 짧은 구간은 앞 구간에 붙인다.
3. 구간마다 샷을 고른다: 첫 컷은 하이라이트 1위, 같은 샷 재사용 금지, 같은 원본 연속 2컷까지,
   mood 등급 영상은 hook·problem 구간에만. 샷이 짧으면 0.9배속까지 늦추고, 그래도 모자라면 구간을 나눈다.
"""

import math
from dataclasses import dataclass, field

from ssm.schemas import Analysis, Cut, Shot, Timeline, VideoAnalysis, WordTimings

MAX_CUT_SEC = 3.0
MIN_CUT_SEC = 1.0
MIN_SPEED = 0.9
MOOD_SECTIONS = {"hook", "problem"}  # 분위기만 비슷한 영상(mood)을 쓸 수 있는 구간
MAX_SAME_SOURCE_IN_ROW = 2


class PlanError(Exception):
    """사용자에게 그대로 보여줄 수 있는 컷 배치 오류."""


@dataclass
class Piece:
    start: float
    end: float
    sections: set[str] = field(default_factory=set)

    @property
    def length(self) -> float:
        return self.end - self.start


def sentence_pieces(timings: WordTimings, total: float) -> tuple[list[Piece], list[float]]:
    """문장 단위 구간들과 단어 시작 시각 목록 (나눌 때 맞출 지점)."""
    starts = []
    for i, s in enumerate(timings.sentences):
        starts.append(0.0 if i == 0 else (s.words[0].start if s.words else s.start))
    pieces = []
    for i, s in enumerate(timings.sentences):
        end = starts[i + 1] if i + 1 < len(starts) else total
        if end - starts[i] > 1e-6:
            pieces.append(Piece(starts[i], end, {s.section}))
    merged: list[Piece] = []
    for p in pieces:  # 짧은 문장은 앞 구간에 붙인다 (첫 구간이면 다음 구간과 합친다)
        if merged and (p.length < MIN_CUT_SEC or merged[-1].length < MIN_CUT_SEC):
            merged[-1] = Piece(merged[-1].start, p.end, merged[-1].sections | p.sections)
        else:
            merged.append(p)
    word_starts = sorted(w.start for s in timings.sentences for w in s.words)
    return merged, word_starts


def _snap(t: float, lo: float, hi: float, word_starts: list[float]) -> float:
    """lo~hi 안에서 t와 가장 가까운 단어 시작 시각. 없으면 t 그대로."""
    near = [w for w in word_starts if lo <= w <= hi]
    return min(near, key=lambda w: abs(w - t)) if near else t


def split_long(pieces: list[Piece], word_starts: list[float]) -> list[Piece]:
    out = []
    for p in pieces:
        n = math.ceil(p.length / MAX_CUT_SEC - 1e-9)
        if n <= 1:
            out.append(p)
            continue
        cursor = p.start
        for k in range(1, n):
            ideal = p.start + p.length * k / n
            t = _snap(ideal, cursor + MIN_CUT_SEC, p.end - MIN_CUT_SEC, word_starts)
            if t - cursor >= MIN_CUT_SEC and p.end - t >= MIN_CUT_SEC:
                out.append(Piece(cursor, t, set(p.sections)))
                cursor = t
        out.append(Piece(cursor, p.end, set(p.sections)))
    return out


def _source_ok(history: list[str], source: str) -> bool:
    recent = history[-MAX_SAME_SOURCE_IN_ROW:]
    return not (len(recent) == MAX_SAME_SOURCE_IN_ROW and all(h == source for h in recent))


def plan_timeline(timings: WordTimings, analysis: Analysis, total: float) -> tuple[Timeline, list[str]]:
    """(타임라인, 사용자에게 알릴 주의 사항들)."""
    pieces, word_starts = sentence_pieces(timings, total)
    queue = split_long(pieces, word_starts)
    shots: list[tuple[VideoAnalysis, Shot]] = [(v, s) for v in analysis.videos for s in v.shots]
    if not any(v.grade == "same_product" for v in analysis.videos):
        raise PlanError("같은 상품 영상(same_product)이 하나도 없습니다 — 분위기 영상(mood)은 상품이 보이는 구간에 쓸 수 없습니다.\n"
                        "→ `ssm add 영상.mp4`로 같은 상품 영상을 추가하거나, analysis.json의 grade를 확인하세요.")

    used: dict[str, int] = {}
    history: list[str] = []
    cuts: list[Cut] = []
    warnings: list[str] = []
    i = 0
    while i < len(queue):
        piece = queue[i]
        allow_mood = piece.sections <= MOOD_SECTIONS
        eligible = [(v, s) for v, s in shots if allow_mood or v.grade == "same_product"]
        fits = lambda s: s.duration >= piece.length * MIN_SPEED  # noqa: E731
        fresh = [(v, s) for v, s in eligible if s.id not in used]
        by_score = lambda vs: (vs[1].score, vs[1].duration)  # noqa: E731

        if not cuts:  # 첫 컷(훅)은 하이라이트 점수 1위
            pick = max(eligible, key=by_score)
        else:
            tiers = [
                [vs for vs in fresh if _source_ok(history, vs[0].file) and fits(vs[1])],
                [vs for vs in fresh if fits(vs[1])],
            ]
            pick = next((max(t, key=by_score) for t in tiers if t), None)
            if pick is None and fresh:  # 길이가 맞는 샷이 없으면 가장 긴 새 샷을 쓰고 구간을 나눈다
                pick = max(fresh, key=lambda vs: (_source_ok(history, vs[0].file), vs[1].duration, vs[1].score))
            if pick is None:  # 새 샷이 다 떨어지면 덜 쓴 샷을 다시 쓴다
                prev = cuts[-1].shot_id
                again = [vs for vs in eligible if vs[1].id != prev] or eligible
                pick = min(again, key=lambda vs: (used[vs[1].id], -vs[1].duration, -vs[1].score))
                msg = "영상 소스가 부족해 같은 장면을 다시 썼습니다 → 같은 상품 영상을 추가하면 더 자연스러워집니다 (`ssm add`)."
                if msg not in warnings:
                    warnings.append(msg)

        video, shot = pick
        usable = shot.duration / MIN_SPEED
        if usable + 1e-6 < piece.length:  # 샷이 짧다 → 이 샷이 채울 수 있는 만큼만 쓰고 나머지는 다음 컷으로
            lo = piece.start + MIN_CUT_SEC / 2
            hi = min(piece.start + usable, piece.end - MIN_CUT_SEC)  # 남는 컷도 MIN_CUT_SEC 이상이 되게
            target = hi
            if hi < lo:  # 그럴 여유가 없으면 남는 컷을 MIN_CUT_SEC/2까지 허용하고 반으로 나눈다
                hi = min(piece.start + usable, piece.end - MIN_CUT_SEC / 2)
                target = min(hi, (piece.start + piece.end) / 2)
            if hi >= lo:
                cut_at = _snap(target, lo, hi, word_starts)
                queue.insert(i + 1, Piece(cut_at, piece.end, set(piece.sections)))
                piece = Piece(piece.start, cut_at, piece.sections)
            # 나눌 여유도 없으면 느리게 재생해 채운다 (아주 드문 경우)

        speed = max(0.5, min(1.0, shot.duration / piece.length))
        src_len = min(piece.length * speed, shot.duration)
        src_start = shot.start + (shot.duration - src_len) / 2  # 샷 가운데 부분을 쓴다
        cuts.append(Cut(source=video.file, start=round(src_start, 3), end=round(src_start + src_len, 3),
                        position=round(piece.start, 3), speed=round(speed, 4), shot_id=shot.id,
                        section=_main_section(piece.sections)))
        used[shot.id] = used.get(shot.id, 0) + 1
        history.append(video.file)
        i += 1
    return Timeline(duration=total, cuts=cuts), warnings


def _main_section(sections: set[str]) -> str:
    order = ["hook", "problem", "demo", "benefit", "cta"]
    return next(s for s in order if s in sections)
