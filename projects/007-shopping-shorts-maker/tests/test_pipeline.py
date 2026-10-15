"""analyze → tts → edit 파이프라인. 실제 FFmpeg를 쓰고, 음성 합성·OCR은 네트워크·모델 없이 가짜로 한다."""

import json
import re
import shutil
import subprocess

import pytest
from typer.testing import CliRunner

from ssm import analyzer, tts_engine
from ssm.analyzer import run_analyze
from ssm.main import app
from ssm.schemas import Source, Timeline, Word, WordTimings
from ssm.tts_engine import TTSError, run_tts
from ssm.video_editor import EditError, run_edit
from ssm.workspace import Workspace, import_local_videos

from conftest import FFMPEG, PROJECT, make_video, needs_ffmpeg
from test_analyzer import WhiteBoxDetector

pytestmark = needs_ffmpeg

SCRIPT = {
    "version": 1, "preset": "curiosity", "target_duration_sec": 15,
    "product": {"name": "접이식 전기포트", "features": ["접으면 5cm"]},
    "sentences": [
        {"id": "s1", "section": "hook", "text": "아직도 여행 갈 때 무거운 포트 들고 다니세요?", "emphasis": ["포트"],
         "sfx": "whoosh"},
        {"id": "s2", "section": "demo", "text": "이건 접으면 두께가 5센티밖에 안 돼요.", "emphasis": ["5센티"], "sfx": "pop"},
        {"id": "s3", "section": "benefit", "text": "물 붓고 버튼만 누르면 금방 끓어요.", "sfx": "boom"},
        {"id": "s4", "section": "cta", "text": "댓글에 '링크' 남겨주세요!", "emphasis": ["링크"]},
    ],
    "thumbnail_text": {"top": "여행 필수템", "bottom": "접는 포트"},
}
quiet = lambda m: None  # noqa: E731


class FakeTTS:
    """어절마다 0.3초짜리 소리를 만든다."""

    name = "fake"

    def __init__(self, fail_times=0):
        self.calls, self.fail_times = [], fail_times

    def synthesize(self, text, voice, rate, out):
        self.calls.append(text)
        if len(self.calls) <= self.fail_times:
            raise ConnectionError("연결 끊김")
        words = text.split()
        subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=f=440:d={0.3 * len(words)}",
                        "-af", "volume=-20dB", "-ar", "24000", "-ac", "1", str(out)], check=True)
        return [Word(text=w, start=i * 0.3, end=i * 0.3 + 0.27) for i, w in enumerate(words)]


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,codec_name,width,height,r_frame_rate,channels:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def loudness(path):
    err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    summary = err[err.rfind("Summary:"):]
    return (float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1)),
            float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary).group(1)))


@pytest.fixture
def project(home, tmp_path):
    """같은 상품 영상 3개(하나는 원본 자막 띠 있음) + 대본이 있는 프로젝트. 폰트는 실제 폰트를 복사한다."""
    fonts = PROJECT / "assets/fonts"
    if not (fonts / "Pretendard-ExtraBold.otf").is_file():
        pytest.skip("폰트가 없음 (ssm fonts)")
    shutil.copytree(fonts, home / "assets/fonts")
    videos = [make_video(tmp_path / "원본 1.mp4", "720x1280", 6, shots=2, box=True),
              make_video(tmp_path / "원본 2.mp4", "640x360", 4, shots=2),
              make_video(tmp_path / "원본 3.mp4", "1080x1920", 3)]
    ws = Workspace.create(Source(type="local", files=[str(v) for v in videos]),
                          {"ad_disclosure": {"profile": "coupang"}, "project": {"duration_sec": 15}})
    import_local_videos(ws, videos)
    (ws.path / "script.json").write_text(json.dumps(SCRIPT, ensure_ascii=False), encoding="utf-8")
    return ws


def test_tts_outputs_timings_and_caches_sentences(project):
    fake = FakeTTS()
    timings = run_tts(project, provider=fake, log=quiet)
    assert (project.path / "tts.mp3").is_file()
    saved = WordTimings.model_validate_json((project.path / "word_timings.json").read_text(encoding="utf-8"))
    assert saved == timings
    assert [(s.id, s.section, s.sfx) for s in timings.sentences][:2] == [("s1", "hook", "whoosh"), ("s2", "demo", "pop")]
    s1, s2 = timings.sentences[:2]
    assert s2.start == pytest.approx(s1.end + tts_engine.SENTENCE_GAP_SEC, abs=0.01)  # 문장 사이 무음
    assert s2.words[0].start == pytest.approx(s2.start, abs=0.01)
    assert project.status("tts") == "done"

    # 그대로 다시 돌리면 합성하지 않고, 한 문장만 고치면 그 문장만 다시 합성한다
    run_tts(project, provider=fake, log=quiet)
    assert len(fake.calls) == 4
    script = json.loads(json.dumps(SCRIPT))
    script["sentences"][1]["text"] = "이건 접으면 5센티예요."
    (project.path / "script.json").write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
    assert project.status("tts") == "stale"
    run_tts(project, provider=fake, log=quiet)
    assert fake.calls[4:] == ["이건 접으면 5센티예요."]


def test_tts_retries_then_reports(project):
    sleeps = []
    run_tts(project, provider=FakeTTS(fail_times=2), log=quiet, sleep=sleeps.append)
    assert sleeps == [1, 2]
    shutil.rmtree(project.path / "tts_cache")
    with pytest.raises(TTSError, match="3번 실패"):
        run_tts(project, provider=FakeTTS(fail_times=99), log=quiet, sleep=lambda s: None)


def test_tts_script_errors(project):
    (project.path / "script.json").write_text('{"version": 1}', encoding="utf-8")
    with pytest.raises(TTSError, match="형식이 올바르지"):
        run_tts(project, provider=FakeTTS(), log=quiet)
    (project.path / "script.json").unlink()
    with pytest.raises(TTSError, match="script.json이 없습니다"):
        run_tts(project, provider=FakeTTS(), log=quiet)


def test_edit_multi_cut_render(project, home):
    # BGM을 깔아 덕킹·라우드니스까지 확인한다
    (home / "assets/bgm").mkdir(parents=True)
    subprocess.run([FFMPEG, "-v", "error", "-f", "lavfi", "-i", "sine=f=220:d=4", str(home / "assets/bgm/calm.mp3")],
                   check=True)
    run_analyze(project, detector=WhiteBoxDetector(), log=quiet)
    timings = run_tts(project, provider=FakeTTS(), log=quiet)
    logs = []
    out = run_edit(project, log=logs.append)

    info = probe(out)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
    assert (video["width"], video["height"], video["r_frame_rate"]) == (1080, 1920, "30/1")
    assert len(audio) == 1 and audio[0]["codec_name"] == "aac"  # 원본 소리 없이 믹스 하나만
    total = timings.duration + 0.5
    assert float(info["format"]["duration"]) == pytest.approx(total, abs=0.1)

    lufs, peak = loudness(out)
    assert lufs == pytest.approx(-14, abs=1.0)  # M2 완료 기준: -14 LUFS ±1
    assert peak <= -0.5

    timeline = Timeline.model_validate_json((project.path / "timeline.json").read_text(encoding="utf-8"))
    assert len({c.source for c in timeline.cuts}) >= 2  # 여러 영상을 섞어 쓴다
    starts = [0.0] + [s.words[0].start for s in timings.sentences[1:]]
    for b in starts:  # 문장 경계마다 컷 전환
        assert min(abs(b - c.position) for c in timeline.cuts) <= 0.2
    text = "\n".join(logs)
    assert "BGM: calm.mp3" in text and "boom" in text and "원본 자막 블러" in text
    assert project.pending_stages() == ["collect", "script", "meta"]

    # 자막 크기만 바꾸면 edit만 다시 (이전 결과는 versions/에 보관)
    project.set_override("subtitle.size", 90)
    assert project.pending_stages() == ["collect", "script", "edit", "meta"]
    run_edit(project, log=quiet)
    assert project.versions() == [1] and (project.path / "versions/v1/final_output.mp4").is_file()


def test_edit_preview_and_crop_mode(project):
    project.set_override("foreign_sub_removal", "crop")
    run_analyze(project, detector=WhiteBoxDetector(), log=quiet)
    run_tts(project, provider=FakeTTS(), log=quiet)
    logs = []
    out = run_edit(project, preview=True, log=logs.append)
    video = next(s for s in probe(out)["streams"] if s["codec_type"] == "video")
    assert out.name == "preview.mp4" and (video["width"], video["height"]) == (540, 960)
    assert project.statuses()["edit"] == "pending"  # 미리보기는 완료로 치지 않는다
    assert any("잘라냄" in m for m in logs if m.startswith("렌더링"))


def test_edit_requires_previous_stages_and_ad(project):
    with pytest.raises(EditError, match="ssm analyze"):
        run_edit(project, log=quiet)
    run_analyze(project, detector=WhiteBoxDetector(), log=quiet)
    with pytest.raises(EditError, match="ssm tts"):
        run_edit(project, log=quiet)
    run_tts(project, provider=FakeTTS(), log=quiet)
    project.set_override("ad_disclosure.profile", None)
    with pytest.raises(EditError, match="광고 표시"):
        run_edit(project, log=quiet)


def test_cli_run_and_add(project, tmp_path, monkeypatch):
    monkeypatch.setitem(tts_engine.PROVIDERS, "edge", FakeTTS)
    monkeypatch.setattr(analyzer, "load_detector", lambda cfg: (WhiteBoxDetector(), ""))
    runner = CliRunner()
    r = runner.invoke(app, ["run"])
    assert r.exit_code == 0, r.output
    assert (project.path / "final_output.mp4").is_file() and (project.path / "thumbnail_1.png").is_file()
    assert "caption.txt" in [p.name for p in project.path.iterdir()] and project.pending_stages() == []
    r = runner.invoke(app, ["run"])  # 바뀐 게 없으면 아무것도 다시 하지 않는다
    assert "▶" not in r.output

    r = runner.invoke(app, ["add", str(make_video(tmp_path / "추가.mp4", seconds=2))])
    assert r.exit_code == 0 and "04.mp4" in r.output
    r = runner.invoke(app, ["run"])  # 영상이 늘면 분석부터 다시, 음성은 그대로
    assert "▶ 영상 분석" in r.output and "▶ 편집·렌더링" in r.output and "▶ 음성" not in r.output
