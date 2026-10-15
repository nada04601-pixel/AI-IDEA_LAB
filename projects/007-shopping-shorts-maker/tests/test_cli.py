from typer.testing import CliRunner

from ssm.main import app
from ssm.workspace import Workspace

from conftest import make_video, needs_ffmpeg

runner = CliRunner()


def invoke(*args, input=None):
    return runner.invoke(app, list(args), input=input)


def test_new_with_options_and_status(home):
    r = invoke("new", "https://www.xiaohongshu.com/explore/abc", "--duration", "45", "--fps", "60", "--ad", "coupang")
    assert r.exit_code == 0, r.output
    ws = Workspace.open(None)
    cfg = ws.config()
    assert ws.project().source.type == "url"
    assert (cfg.project.duration_sec, cfg.video.fps, cfg.ad_disclosure.profile) == (45, 60, "coupang")

    r = invoke("status")
    assert r.exit_code == 0
    assert "45초" in r.output and "60fps" in r.output and "coupang" in r.output


def test_new_custom_ad_and_defaults(home):
    r = invoke("new", "전기포트", "--ad", "custom", "--ad-text", "유료 광고 포함", "-y")
    assert r.exit_code == 0, r.output
    cfg = Workspace.open(None).config()
    assert cfg.ad_disclosure.text() == "유료 광고 포함"
    assert cfg.project.duration_sec == 30


def test_new_rejects_bad_values(home):
    r = invoke("new", "전기포트", "--fps", "24", "-y")
    assert r.exit_code == 1
    assert "video.fps" in r.output
    r = invoke("new", "전기포트", "--ad", "custom", "-y")
    assert r.exit_code == 1 and "custom_text" in r.output
    r = invoke("new")
    assert r.exit_code == 1


def test_new_local_files(home, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    r = invoke("new", "--local", str(video), "-y")
    assert r.exit_code == 0, r.output
    ws = Workspace.open(None)
    assert (ws.path / "raw_videos/01.mp4").is_file()
    assert ws.project().source.type == "local"


def test_set_and_list(home):
    invoke("new", "전기포트", "-y")
    r = invoke("set", "subtitle.size", "96")
    assert r.exit_code == 0, r.output
    assert Workspace.open(None).config().subtitle.size == 96
    r = invoke("set", "video.fps", "25")
    assert r.exit_code == 1
    r = invoke("list")
    assert "전기포트" in r.output


def test_unimplemented_stage_exit_code(home):
    invoke("new", "전기포트", "-y")
    r = invoke("meta")
    assert r.exit_code == 2
    assert "M5" in r.output


@needs_ffmpeg
def test_tts_and_run_without_script(home, tmp_path):
    invoke("new", "--local", str(make_video(tmp_path / "a.mp4")), "-y")
    r = invoke("tts")
    assert r.exit_code == 1 and "script.json이 없습니다" in r.output
    r = invoke("run")  # 수집(로컬)·분석까지 하고, 대본 단계에서 요청서를 만들라고 알린다
    assert r.exit_code == 1 and "▶ 영상 분석" in r.output and "script.json이 없습니다" in r.output
    assert "ssm script --preset" in r.output


def test_no_project_message(home):
    r = invoke("status")
    assert r.exit_code == 1
    assert "ssm new" in r.output
