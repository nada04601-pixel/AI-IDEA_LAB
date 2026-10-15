import pytest
from PIL import Image

from ssm import subtitle
from ssm.config import SubtitleCfg
from ssm.schemas import SentenceTiming, Word, WordTimings
from ssm.subtitle import Cue, align_tokens, build_cues, emphasis_mask, to_srt, wrap

from conftest import PROJECT

FONT = PROJECT / "assets/fonts/Pretendard-ExtraBold.otf"
needs_font = pytest.mark.skipif(not FONT.is_file(), reason="폰트가 없음 (ssm fonts)")


def sentence(text, words, start=0.0, end=None, sid="s1", emphasis=()):
    ws = [Word(text=t, start=a, end=b) for t, a, b in words]
    return SentenceTiming(id=sid, text=text, emphasis=list(emphasis), start=start,
                          end=end if end is not None else (ws[-1].end if ws else 1.0), words=ws)


def test_wrap_balances_two_lines_without_splitting_words():
    assert wrap(["짧은", "문장"], 14) == ["짧은 문장"]
    lines = wrap("이건 접으면 두께가 5센티밖에 안 돼요.".split(), 14)
    assert lines == ["이건 접으면 두께가", "5센티밖에 안 돼요."]
    assert all(len(line) <= 14 for line in lines)
    assert wrap("가나다라마바사 아자차카타파하 가나다라마바사".split(), 14) is None  # 2줄에 안 들어감
    assert wrap(["아주아주아주아주아주긴한단어입니다"], 14) == ["아주아주아주아주아주긴한단어입니다"]


def test_wrap_prefers_break_after_comma():
    assert wrap("실리콘이라 가볍고, 프리볼트라".split(), 14) == ["실리콘이라 가볍고,", "프리볼트라"]


def test_align_tokens_keeps_punctuation_and_word_times():
    s = sentence("궁금하시면 댓글에 '링크' 남겨주세요!",
                 [("궁금하시면", 0.1, 0.7), ("댓글에", 0.75, 1.2), ("링크", 1.25, 1.5), ("남겨주세요", 1.6, 2.4)])
    tokens = align_tokens(s)
    assert [t.text for t in tokens] == ["궁금하시면", "댓글에", "'링크'", "남겨주세요!"]
    assert (tokens[2].start, tokens[2].end) == (1.25, 1.5)


def test_align_tokens_falls_back_to_even_split():
    s = sentence("오늘 5개 샀어요", [("오늘", 0.0, 0.4), ("다섯개", 0.4, 1.0), ("샀어요", 1.0, 1.6)])
    tokens = align_tokens(s)  # 숫자를 다르게 읽으면 글자 수 비례로 나눈다
    assert [t.text for t in tokens] == ["오늘", "5개", "샀어요"]
    assert tokens[0].start == 0.0 and tokens[-1].end == pytest.approx(1.6)
    assert all(a.end == pytest.approx(b.start) for a, b in zip(tokens, tokens[1:]))


def test_build_cues_respects_limits_and_is_continuous():
    words = "물 붓고 버튼만 누르면 1분 만에 보글보글 끓어요".split()
    s1 = sentence("물 붓고 버튼만 누르면 1분 만에 보글보글 끓어요.",
                  [(w, i * 0.4, i * 0.4 + 0.35) for i, w in enumerate(words)], emphasis=["1분 만에"])
    s2 = sentence("댓글 주세요!", [("댓글", 4.0, 4.4), ("주세요", 4.4, 5.0)], start=3.8, sid="s2")
    timings = WordTimings(provider="fake", voice="v", rate="+0%", duration=5.0, sentences=[s1, s2])
    cues = build_cues(timings, 14, video_end=5.5)

    assert len(cues) >= 3
    for c in cues:
        assert 1 <= len(c.lines) <= 2 and all(len(line) <= 14 for line in c.lines)
        assert c.end - c.start <= subtitle.MAX_CUE_SEC + 1.0
    assert all(a.end == pytest.approx(b.start) for a, b in zip(cues, cues[1:]))  # 깜빡임 없음
    assert cues[-1].end == 5.5 and cues[-1].lines == ["댓글 주세요!"]
    assert " ".join(" ".join(c.lines) for c in cues[:-1]) == s1.text


def test_build_cues_splits_at_comma():
    s = sentence("호텔 포트는 찝찝하고, 챙기자니 아까워요.",
                 [("호텔", 0.0, 0.3), ("포트는", 0.3, 0.7), ("찝찝하고", 0.7, 1.3), ("챙기자니", 1.5, 2.0),
                  ("아까워요", 2.0, 2.6)])
    timings = WordTimings(provider="fake", voice="v", rate="+0%", duration=2.6, sentences=[s])
    cues = build_cues(timings, 14, video_end=3.0)
    assert [c.lines for c in cues] == [["호텔 포트는 찝찝하고,"], ["챙기자니 아까워요."]]


def test_emphasis_mask_spans_line_break():
    mask = emphasis_mask(["버튼만 누르면 1분", "만에 끓어요"], ["1분 만에", "끓어요"])
    assert "".join("^" if m else "." for m in mask[0]) == "........^^"
    assert "".join("^" if m else "." for m in mask[1]) == "^^.^^^"


def test_srt():
    text = to_srt([Cue(0.095, 2.5, ["첫 줄", "둘째 줄"], []), Cue(62.0, 3725.25, ["끝"], [])])
    assert text == "1\n00:00:00,095 --> 00:00:02,500\n첫 줄\n둘째 줄\n\n2\n00:01:02,000 --> 01:02:05,250\n끝\n"


def test_cue_position_stays_in_safe_zone():
    x, y = subtitle.cue_position((900, 200), (1080, 1920), 0.95)
    assert x + 900 <= 1080 - subtitle.SAFE_RIGHT
    assert y + 200 <= 1920 - subtitle.SAFE_BOTTOM
    _, y = subtitle.cue_position((600, 200), (1080, 1920), 0.0)
    assert y >= subtitle.SAFE_TOP


@needs_font
def test_render_cue_and_ad(tmp_path):
    cue = Cue(0, 1, ["아직도 여행 갈 때", "무거운 포트 들고"], ["무거운 포트"])
    w, h = subtitle.render_cue(cue, SubtitleCfg(), FONT, 1.0, tmp_path / "cue.png")
    img = Image.open(tmp_path / "cue.png")
    assert img.size == (w, h) and img.mode == "RGBA"
    assert w <= 1080 - subtitle.SAFE_LEFT - subtitle.SAFE_RIGHT  # 14자 기본 크기가 세이프존 안에 들어간다
    colors = {px[:3] for _, px in img.getcolors(maxcolors=w * h) if px[3] == 255}
    assert (255, 225, 77) in colors and (255, 255, 255) in colors  # 강조어 노란색 + 기본 흰색

    text = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
    w, h = subtitle.render_ad(text, FONT, FONT, 1080, tmp_path / "ad.png")
    x, y = subtitle.ad_position((w, h), 1080, "top_left")
    assert x + w <= 1080 - subtitle.SAFE_RIGHT and y >= subtitle.SAFE_TOP
    assert h < 130  # 2줄 이내
