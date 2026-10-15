import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from ssm.schemas import Source
from ssm.workspace import Workspace, WorkspaceError, import_local_videos, list_projects, slugify

NOW = datetime(2026, 10, 15, 9, 30)


def make(home, value="접이식 전기포트", **kw) -> Workspace:
    return Workspace.create(Source(type="keyword", value=value), now=NOW, **kw)


def fake_outputs(ws: Workspace, *stages: str) -> None:
    """단계 결과 파일을 흉내 낸다."""
    files = {
        "collect": ["raw_videos/01.mp4", "candidates.json", "selected.json"],
        "analyze": ["analysis.json"],
        "script": ["script.json"],
        "tts": ["tts.mp3", "word_timings.json", "subtitles.srt"],
        "edit": ["timeline.json", "final_output.mp4"],
        "meta": ["thumbnail.png", "caption.txt"],
    }
    for stage in stages:
        for name in files[stage]:
            (ws.path / name).write_text(f"{stage}:{name}", encoding="utf-8")
        ws.mark_done(stage)


def test_slugify():
    assert slugify("https://www.xiaohongshu.com/explore/66f1a2b3?xsec=1") == "xiaohongshu-66f1a2b3"
    assert slugify("https://v.douyin.com/iAbCd12/") == "douyin-iabcd12"
    assert slugify("자취생 필수템!!") == "자취생-필수템"
    assert slugify("???") == "project"


def test_create_layout_and_unique_ids(home):
    a = make(home)
    b = make(home)
    assert a.id == "20261015-0930-접이식-전기포트"
    assert b.id == a.id + "-2"
    for sub in ("raw_videos", "logs", "versions"):
        assert (a.path / sub).is_dir()
    assert a.project().source.value == "접이식 전기포트"
    assert [w.id for w in list_projects()] == [a.id, b.id]
    assert Workspace.open(None).id == b.id  # 생략하면 최근 프로젝트
    with pytest.raises(WorkspaceError):
        Workspace.open("없는-프로젝트")


def test_project_overrides(home):
    ws = make(home, overrides={"project": {"duration_sec": 45}, "video": {"fps": 60}})
    cfg = ws.config()
    assert (cfg.project.duration_sec, cfg.video.fps) == (45, 60)
    with pytest.raises(ValidationError):
        make(home, overrides={"video": {"fps": 25}})


def test_all_pending_initially(home):
    ws = make(home)
    assert set(ws.statuses().values()) == {"pending"}
    assert ws.pending_stages() == ["collect", "analyze", "script", "tts", "edit", "meta"]
    with pytest.raises(WorkspaceError):
        ws.mark_done("collect")  # 결과 파일 없이 완료 기록 불가


def test_done_and_invalidation_by_upstream_file(home):
    ws = make(home)
    fake_outputs(ws, "collect", "analyze", "script", "tts", "edit", "meta")
    assert ws.pending_stages() == []

    # Claude가 대본을 고치면: 대본은 그대로 완료, tts → edit 와 캡션(meta)이 다시 실행 대상
    (ws.path / "script.json").write_text("새 대본", encoding="utf-8")
    statuses = ws.statuses()
    assert statuses["script"] == "done"
    assert statuses["tts"] == "stale" and statuses["meta"] == "stale"
    assert statuses["edit"] == "done"  # edit 자체 입력(tts 결과)은 아직 그대로
    assert ws.pending_stages() == ["tts", "edit", "meta"]  # 하지만 tts가 다시 돌면 edit도 다시


def test_subtitle_style_change_only_reruns_edit(home):
    ws = make(home)
    fake_outputs(ws, "collect", "analyze", "script", "tts", "edit", "meta")
    ws.set_override("subtitle.size", 92)
    assert ws.pending_stages() == ["edit"]
    assert ws.config().subtitle.size == 92


def test_thumbnail_change_only_reruns_meta(home):
    ws = make(home)
    fake_outputs(ws, "collect", "analyze", "script", "tts", "edit", "meta")
    ws.set_override("thumbnail.top_color", "#FF0000")
    assert ws.pending_stages() == ["meta"]


def test_set_override_validates_before_saving(home):
    ws = make(home)
    with pytest.raises(ValidationError):
        ws.set_override("video.fps", 25)
    with pytest.raises(WorkspaceError):
        ws.set_override("nothing.here", 1)
    assert ws.project().overrides == {}


def test_deleted_output_is_pending(home):
    ws = make(home)
    fake_outputs(ws, "collect", "analyze")
    (ws.path / "analysis.json").unlink()
    assert ws.statuses()["analyze"] == "pending"


def test_snapshot_and_rollback(home):
    ws = make(home)
    fake_outputs(ws, "collect", "analyze", "script")
    (ws.path / "final_output.mp4").write_text("v1 영상", encoding="utf-8")
    assert ws.snapshot() == 1

    (ws.path / "script.json").write_text("v2 대본", encoding="utf-8")
    (ws.path / "final_output.mp4").write_text("v2 영상", encoding="utf-8")
    (ws.path / "caption.txt").write_text("v2에서 처음 생긴 캡션", encoding="utf-8")
    ws.set_override("subtitle.size", 100)

    ws.rollback(1)
    assert (ws.path / "final_output.mp4").read_text(encoding="utf-8") == "v1 영상"
    assert (ws.path / "script.json").read_text(encoding="utf-8") == "script:script.json"
    assert not (ws.path / "caption.txt").exists()
    assert ws.config().subtitle.size == 78  # project.yaml도 되돌아감
    assert ws.versions() == [1, 2]  # 되돌리기 전 상태는 v2로 남는다
    assert (ws.path / "versions/v2/final_output.mp4").read_text(encoding="utf-8") == "v2 영상"
    assert json.loads((ws.path / "state.json").read_text(encoding="utf-8"))["script"]
    with pytest.raises(WorkspaceError):
        ws.rollback(9)


def test_import_local_videos(home, tmp_path):
    ws = make(home)
    a = tmp_path / "원본 A.MP4"
    a.write_bytes(b"a")
    b = tmp_path / "b.mov"
    b.write_bytes(b"b")
    copied = import_local_videos(ws, [a, b])
    assert [p.name for p in copied] == ["01.mp4", "02.mov"]
    with pytest.raises(WorkspaceError):
        import_local_videos(ws, [tmp_path / "없음.mp4"])
