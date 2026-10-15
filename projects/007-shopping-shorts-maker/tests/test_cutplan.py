import pytest

from ssm.cutplan import MAX_CUT_SEC, MIN_SPEED, PlanError, plan_timeline
from ssm.schemas import Analysis, SentenceTiming, Shot, VideoAnalysis, Word, WordTimings


def timings(spec: list[tuple[str, int]], word_sec: float = 0.3, gap: float = 0.15) -> WordTimings:
    """spec: [(section, 어절 수)] → 어절마다 word_sec초인 가짜 음성 타이밍."""
    sentences, t = [], 0.0
    for i, (section, n) in enumerate(spec):
        start = t
        words = [Word(text=f"w{k}", start=round(t + 0.05 + k * word_sec, 3), end=round(t + 0.05 + (k + 1) * word_sec, 3))
                 for k in range(n)]
        t = words[-1].end + 0.05
        sentences.append(SentenceTiming(id=f"s{i + 1}", section=section, text=" ".join(w.text for w in words),
                                        start=start, end=t, words=words))
        t += gap
    return WordTimings(provider="fake", voice="v", rate="+0%", duration=round(t - gap, 3), sentences=sentences)


def video(name: str, shots: list[tuple[float, float, float]], grade: str = "same_product") -> VideoAnalysis:
    return VideoAnalysis(file=f"raw_videos/{name}.mp4", width=1080, height=1920, duration=shots[-1][1], grade=grade,
                         shots=[Shot(id=f"{name}-{i:03d}", start=a, end=b, score=s) for i, (a, b, s) in enumerate(shots, 1)])


def three_videos(mood_second: bool = False) -> Analysis:
    return Analysis(videos=[
        video("01", [(0, 3, 0.5), (3, 6, 0.9), (6, 9, 0.4), (9, 12, 0.3)]),
        video("02", [(0, 3, 0.95), (3, 6, 0.6), (6, 9, 0.2)], grade="mood" if mood_second else "same_product"),
        video("03", [(0, 4, 0.7), (4, 8, 0.65), (8, 12, 0.1)]),
    ])


SCRIPT = [("hook", 6), ("problem", 8), ("demo", 12), ("demo", 7), ("benefit", 9), ("cta", 6)]


def sentence_starts(t: WordTimings) -> list[float]:
    return [0.0] + [s.words[0].start for s in t.sentences[1:]]


def test_cuts_follow_sentence_boundaries_and_rules():
    t = timings(SCRIPT)
    total = t.duration + 0.5
    timeline, warnings = plan_timeline(t, three_videos(), total)
    cuts = timeline.cuts
    assert warnings == []

    # 빈틈없이 이어지고 끝까지 채운다
    assert cuts[0].position == 0.0
    ends = [c.position + c.length for c in cuts]
    assert all(e == pytest.approx(n.position, abs=0.002) for e, n in zip(ends, cuts[1:]))
    assert ends[-1] == pytest.approx(total, abs=0.002)

    # 모든 문장 시작에 컷 전환이 있고, 나머지 전환도 단어 시작에 맞는다
    positions = [c.position for c in cuts]
    word_starts = [w.start for s in t.sentences for w in s.words]
    for b in sentence_starts(t):
        assert min(abs(b - p) for p in positions) <= 0.2
    for p in positions[1:]:
        assert min(abs(p - w) for w in word_starts) <= 0.2

    assert cuts[0].shot_id == "02-001"  # 첫 컷은 하이라이트 1위
    assert len({c.shot_id for c in cuts}) == len(cuts)  # 같은 샷 재사용 없음
    for a, b, c in zip(cuts, cuts[1:], cuts[2:]):  # 같은 원본 연속 2컷 이하
        assert not (a.source == b.source == c.source)
    assert all(c.length <= MAX_CUT_SEC + 1e-6 and c.speed >= MIN_SPEED for c in cuts)


def test_mood_videos_only_in_hook_and_problem():
    t = timings(SCRIPT)
    timeline, _ = plan_timeline(t, three_videos(mood_second=True), t.duration + 0.5)
    for c in timeline.cuts:
        if c.source.endswith("02.mp4"):
            assert c.section in ("hook", "problem")
    assert any(c.source.endswith("02.mp4") for c in timeline.cuts)  # 훅에는 쓸 수 있다

    only_mood = Analysis(videos=[video("01", [(0, 3, 0.5)], grade="mood")])
    with pytest.raises(PlanError, match="same_product"):
        plan_timeline(t, only_mood, t.duration + 0.5)


def test_short_shots_are_slowed_or_split():
    t = timings([("hook", 6), ("cta", 6)])  # 문장마다 약 1.9초
    analysis = Analysis(videos=[video("01", [(0, 1.0, 0.9), (1.0, 2.0, 0.8), (2.0, 3.0, 0.7), (3.0, 4.0, 0.6),
                                             (4.0, 5.0, 0.5)])])
    timeline, _ = plan_timeline(t, analysis, t.duration + 0.5)
    for c in timeline.cuts:
        assert c.duration <= 1.0 + 1e-6 and c.speed >= MIN_SPEED  # 1초 샷은 최대 1.11초만 채운다
    assert len(timeline.cuts) >= 4


def test_reuses_shots_with_warning_when_sources_run_out():
    t = timings(SCRIPT)
    timeline, warnings = plan_timeline(t, Analysis(videos=[video("01", [(0, 3, 0.5), (3, 6, 0.9)])]), t.duration + 0.5)
    assert len(timeline.cuts) > 2 and any("같은 장면을 다시" in w for w in warnings)
    for a, b in zip(timeline.cuts, timeline.cuts[1:]):
        assert a.shot_id != b.shot_id  # 다시 쓰더라도 바로 이어서 같은 샷은 아니다
