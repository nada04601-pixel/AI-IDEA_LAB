"""tts → edit 파이프라인 (M1). 실제 FFmpeg를 쓰고, 음성 합성은 네트워크 없이 가짜 엔진으로 한다."""

import json
import shutil
import subprocess

import pytest
from typer.testing import CliRunner

from ssm import tts_engine
from ssm.main import app
from ssm.schemas import Source, Word, WordTimings
from ssm.tts_engine import TTSError, run_tts
from ssm.video_editor import EditError, plan_cuts, run_edit
from ssm.workspace import Workspace, import_local_videos

from conftest import PROJECT

FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(not FFMPEG or not shutil.which("ffprobe"), reason="FFmpeg가 없음")

SCRIPT = {
    "version": 1, "preset": "curiosity", "target_duration_sec": 15,
    "product": {"name": "접이식 전기포트", "features": ["접으면 5cm"]},
    "sentences": [
        {"id": "s1", "section": "hook", "text": "아직도 포트 들고 다니세요?", "emphasis": ["포트"]},
        {"id": "s2", "section": "demo", "text": "이건 접으면 5센티예요.", "emphasis": ["5센티"]},
        {"id": "s3", "section": "cta", "text": "댓글에 '링크' 남겨주세요!", "emphasis": ["링크"]},
    ],
    "thumbnail_text": {"top": "여행 필수템", "bottom": "접는 포트"},
}


class FakeTTS:
    """어절마다 0.25초짜리 소리를 만든다."""

    name = "fake"

    def __init__(self, fail_times=0):
        self.calls, self.fail_times = [], fail_times

    def synthesize(self, text, voice, rate, out):
        self.calls.append(text)
        if len(self.calls) <= self.fail_times:
            raise ConnectionError("연결 끊김")
        words = text.split()
        subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=f=440:d={0.25 * len(words)}",
                        "-ar", "24000", "-ac", "1", str(out)], check=True)
        return [Word(text=w, start=i * 0.25, end=i * 0.25 + 0.22) for i, w in enumerate(words)]


def make_video(path, size="320x240", seconds=2):
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s={size}:r=30:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=f=880:d={seconds}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.fixture
def project(home, tmp_path):
    """로컬 영상 1개 + 대본이 있는 프로젝트. 폰트는 실제 폰트를 복사한다."""
    fonts = PROJECT / "assets/fonts"
    if not (fonts / "Pretendard-ExtraBold.otf").is_file():
        pytest.skip("폰트가 없음 (ssm fonts)")
    shutil.copytree(fonts, home / "assets/fonts")
    video = make_video(tmp_path / "원본 영상.mp4")
    ws = Workspace.create(Source(type="local", files=[str(video)]), {"ad_disclosure": {"profile": "coupang"}})
    import_local_videos(ws, [video])
    (ws.path / "script.json").write_text(json.dumps(SCRIPT, ensure_ascii=False), encoding="utf-8")
    return ws


def test_tts_outputs_timings_and_caches_sentences(project):
    fake = FakeTTS()
    timings = run_tts(project, provider=fake, log=lambda m: None)
    assert (project.path / "tts.mp3").is_file()
    saved = WordTimings.model_validate_json((project.path / "word_timings.json").read_text(encoding="utf-8"))
    assert saved == timings
    assert [s.id for s in timings.sentences] == ["s1", "s2", "s3"]
    s1, s2 = timings.sentences[:2]
    assert s2.start == pytest.approx(s1.end + tts_engine.SENTENCE_GAP_SEC, abs=0.01)  # 문장 사이 무음
    assert s2.words[0].start == pytest.approx(s2.start, abs=0.01)
    assert timings.sentences[0].emphasis == ["포트"]
    assert project.status("tts") == "done"

    # 그대로 다시 돌리면 합성하지 않고, 한 문장만 고치면 그 문장만 다시 합성한다
    run_tts(project, provider=fake, log=lambda m: None)
    assert len(fake.calls) == 3
    script = json.loads(json.dumps(SCRIPT))
    script["sentences"][1]["text"] = "이건 접으면 5센티밖에 안 돼요."
    (project.path / "script.json").write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
    assert project.status("tts") == "stale"
    run_tts(project, provider=fake, log=lambda m: None)
    assert fake.calls[3:] == ["이건 접으면 5센티밖에 안 돼요."]


def test_tts_retries_then_reports(project):
    sleeps = []
    run_tts(project, provider=FakeTTS(fail_times=2), log=lambda m: None, sleep=sleeps.append)
    assert sleeps == [1, 2]

    shutil.rmtree(project.path / "tts_cache")
    with pytest.raises(TTSError, match="3번 실패"):
        run_tts(project, provider=FakeTTS(fail_times=99), log=lambda m: None, sleep=lambda s: None)


def test_tts_script_errors(project):
    (project.path / "script.json").write_text('{"version": 1}', encoding="utf-8")
    with pytest.raises(TTSError, match="형식이 올바르지"):
        run_tts(project, provider=FakeTTS(), log=lambda m: None)
    (project.path / "script.json").unlink()
    with pytest.raises(TTSError, match="script.json이 없습니다"):
        run_tts(project, provider=FakeTTS(), log=lambda m: None)


def test_plan_cuts_repeats_short_source():
    cuts = plan_cuts("raw_videos/01.mp4", 4.0, 10.0)
    assert [(c.start, c.end) for c in cuts] == [(0, 4.0), (0, 4.0), (0, 2.0)]
    assert len(plan_cuts("raw_videos/01.mp4", 30.0, 10.0)) == 1


def test_edit_renders_vertical_video(project):
    run_tts(project, provider=FakeTTS(), log=lambda m: None)
    out = run_edit(project, log=lambda m: None)
    assert out.name == "final_output.mp4"
    info = probe(out)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
    assert (video["width"], video["height"], video["r_frame_rate"]) == (1080, 1920, "30/1")
    assert len(audio) == 1 and audio[0]["codec_name"] == "aac"  # TTS 음성 하나만 (원본 소리 없음)
    timings = WordTimings.model_validate_json((project.path / "word_timings.json").read_text(encoding="utf-8"))
    assert float(info["format"]["duration"]) == pytest.approx(timings.duration + 0.5, abs=0.15)
    assert "링크" in (project.path / "subtitles.srt").read_text(encoding="utf-8")
    assert json.loads((project.path / "timeline.json").read_text(encoding="utf-8"))["cuts"]  # 원본 2초 → 반복
    assert project.pending_stages() == ["collect", "analyze", "script", "meta"]  # tts·edit 완료

    # 자막 크기만 바꾸면 edit만 다시 (이전 결과는 versions/에 보관)
    project.set_override("subtitle.size", 90)
    assert project.statuses()["tts"] == "done" and project.statuses()["edit"] == "stale"
    assert "tts" not in project.pending_stages()
    run_edit(project, log=lambda m: None)
    assert project.versions() == [1] and (project.path / "versions/v1/final_output.mp4").is_file()


def test_edit_preview(project):
    run_tts(project, provider=FakeTTS(), log=lambda m: None)
    out = run_edit(project, preview=True, log=lambda m: None)
    video = next(s for s in probe(out)["streams"] if s["codec_type"] == "video")
    assert out.name == "preview.mp4" and (video["width"], video["height"]) == (540, 960)
    assert project.statuses()["edit"] == "pending"  # 미리보기는 완료로 치지 않는다


def test_edit_requires_ad_profile_and_tts(project):
    with pytest.raises(EditError, match="ssm tts"):
        run_edit(project, log=lambda m: None)
    run_tts(project, provider=FakeTTS(), log=lambda m: None)
    project.set_override("ad_disclosure.profile", None)
    with pytest.raises(EditError, match="광고 표시"):
        run_edit(project, log=lambda m: None)


def test_cli_run_skips_unimplemented_stages(project, monkeypatch):
    monkeypatch.setitem(tts_engine.PROVIDERS, "edge", FakeTTS)
    r = CliRunner().invoke(app, ["run"])
    assert r.exit_code == 0, r.output
    assert "건너뜁니다" in r.output and (project.path / "final_output.mp4").is_file()
    r = CliRunner().invoke(app, ["run"])  # 바뀐 게 없으면 아무것도 다시 하지 않는다
    assert "음성·자막 타이밍" not in r.output and "편집·렌더링" not in r.output
