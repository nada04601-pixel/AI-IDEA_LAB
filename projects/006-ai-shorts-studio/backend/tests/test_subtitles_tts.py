import wave

from app.providers.media import MediaRequest
from app.providers.mock_tts import MockTTSProvider, text_hash
from app.services.subtitles import MAX_CUE_CHARS, build_cues, split_sentences, to_srt, wrap_lines


def test_split_sentences():
    assert split_sentences("안녕하세요. 반가워요!\n다음 줄") == ["안녕하세요.", "반가워요!", "다음 줄"]
    long = "아주 " * 20
    assert all(len(c) <= MAX_CUE_CHARS for c in split_sentences(long))
    assert all(len(c) <= MAX_CUE_CHARS for c in split_sentences("가" * 70))
    assert split_sentences("   ") == []


def test_wrap_lines():
    assert wrap_lines("짧은 문장") == "짧은 문장"
    wrapped = wrap_lines("고양이가 상자를 좋아하는 이유를 알아봐요")
    assert "\n" in wrapped and wrapped.replace("\n", " ") == "고양이가 상자를 좋아하는 이유를 알아봐요"


def test_cue_timing_follows_scenes():
    cues = build_cues([(1, "하나. 둘둘둘.", 4.0), (2, "", 2.0), (3, "셋", 3.0)])
    assert [c.scene_number for c in cues] == [1, 1, 3]
    assert cues[0].start == 0 and cues[1].end == 4.0
    assert cues[0].end == cues[1].start
    assert cues[2].start == 6.0 and cues[2].end == 9.0  # 대사 없는 장면 2는 자막 없이 시간만 지난다


def test_srt_format():
    srt = to_srt(build_cues([(1, "안녕", 61.5)]))
    assert srt == "1\n00:00:00,000 --> 00:01:01,500\n안녕\n"
    assert to_srt([]) == ""


def test_mock_tts_wav(tmp_path):
    req = MediaRequest(kind="audio", prompt="첫 문장. 둘째 문장.", aspect_ratio="9:16", duration_sec=2.5,
                       scene_number=1, version=1, attempt=1, output_path=tmp_path / "audio_v1")
    result = MockTTSProvider().generate(req)
    assert result.file_path.suffix == ".wav"
    assert result.metadata["text_hash"] == text_hash("첫 문장. 둘째 문장.")
    with wave.open(str(result.file_path)) as w:
        assert abs(w.getnframes() / w.getframerate() - 2.5) < 0.01
