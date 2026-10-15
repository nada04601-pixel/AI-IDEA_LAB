"""수정 루프 (M6) — 기획서 Module 6의 수정 예시 4개가 해당 단계만 다시 실행되는지, 버전 보관·되돌리기.

실제 CLI(`ssm run`)를 쓰고, 출력의 '▶ 단계' 줄로 실제로 돈 단계를 확인한다. 음성·OCR만 가짜.
"""

import json
import re
import shutil

import pytest
from typer.testing import CliRunner

from ssm import analyzer, tts_engine
from ssm.cutplan import apply_overrides, check_replacement, PlanError, replacement_candidates
from ssm.main import app
from ssm.schemas import CutOverride, Overrides, Source, Timeline
from ssm.workspace import ORDER, Workspace, import_local_videos

from conftest import PROJECT, make_video, needs_ffmpeg
from test_analyzer import WhiteBoxDetector
from test_cutplan import three_videos, timings
from test_pipeline import FakeTTS

SCRIPT = {
    "version": 1, "preset": "curiosity", "target_duration_sec": 30,
    "product": {"name": "접이식 전기포트", "features": ["접으면 5cm", "프리볼트", "가벼움"]},
    "sentences": [
        {"id": "s1", "section": "hook", "text": "아직도 여행 갈 때 무거운 포트 들고 다니세요?", "emphasis": ["무거운 포트"]},
        {"id": "s2", "section": "problem", "text": "호텔 포트는 늘 찝찝하잖아요.", "emphasis": ["찝찝"]},
        {"id": "s3", "section": "demo", "text": "이건 접으면 두께가 5센티밖에 안 돼요.", "emphasis": ["5센티"]},
        {"id": "s4", "section": "benefit", "text": "프리볼트라 해외에서도 그냥 쓸 수 있어요.", "emphasis": ["프리볼트"]},
        {"id": "s5", "section": "cta", "text": "궁금하시면 댓글에 '링크' 남겨주세요!", "emphasis": ["링크"]},
    ],
    "thumbnail_text": {"top": "여행 필수템", "bottom": "접는 포트"},
}
META = {"version": 1, "category": "travel", "titles": ["여행 갈 때 포트 고민 끝"],
        "thumbnail_texts": [{"top": "여행 필수템", "bottom": "접히는 전기포트"}],
        "summary": ["✔ 접으면 두께 5cm"], "hashtags": ["접이식전기포트"]}


def ran(output: str) -> list[str]:
    """출력에서 실제로 실행된 단계 (▶ 줄)."""
    names = re.findall(r"▶ .*?\((\w+)\)", output)
    return [n for n in ORDER if n in names]


def write(ws, name, data):
    (ws.path / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def cuts(ws) -> list[dict]:
    return [c.model_dump() for c in Timeline.model_validate_json((ws.path / "timeline.json").read_text(encoding="utf-8")).cuts]


@pytest.fixture
def project(home, tmp_path, monkeypatch):
    if not (PROJECT / "assets/fonts/Pretendard-ExtraBold.otf").is_file():
        pytest.skip("폰트가 없음 (ssm fonts)")
    shutil.copytree(PROJECT / "assets/fonts", home / "assets/fonts")
    fake = FakeTTS()
    monkeypatch.setitem(tts_engine.PROVIDERS, "edge", lambda: fake)
    monkeypatch.setattr(analyzer, "load_detector", lambda cfg: (WhiteBoxDetector(), ""))
    videos = [make_video(tmp_path / "a.mp4", "720x1280", 6, shots=3, box=True),
              make_video(tmp_path / "b.mp4", "720x1280", 6, shots=3),
              make_video(tmp_path / "c.mp4", "640x360", 6, shots=2)]
    ws = Workspace.create(Source(type="local", files=[str(v) for v in videos]),
                          {"ad_disclosure": {"profile": "coupang"}, "project": {"duration_sec": 30}})
    import_local_videos(ws, videos)
    write(ws, "script.json", SCRIPT)
    write(ws, "meta.json", META)
    ws.fake_tts = fake
    return ws


@needs_ffmpeg
def test_module6_examples_rerun_only_what_changed(project):
    runner = CliRunner()
    invoke = lambda *a: runner.invoke(app, list(a))  # noqa: E731

    r = invoke("run")
    assert r.exit_code == 0, r.output
    assert ran(r.output) == ["collect", "analyze", "script", "tts", "edit", "meta"]
    assert invoke("run").output.strip() == "모든 단계가 완료되어 있습니다."

    # 예시 3) "자막 폰트 크기 좀 키우고 위치 살짝 올려줘" → edit만, 컷 배치는 그대로
    before = cuts(project)
    invoke("set", "subtitle.size", "96")
    invoke("set", "subtitle.position_y_ratio", "0.6")
    r = invoke("run")
    assert ran(r.output) == ["edit"], r.output
    assert cuts(project) == before

    # 예시 4) "세 번째 컷 다른 장면으로 바꿔줘" → edit만, 그 컷만 바뀐다
    r = invoke("cut", "3")
    assert r.exit_code == 0 and "3번 컷" in r.output, r.output
    r = invoke("run")
    assert ran(r.output) == ["edit"] and "컷 교체 1개 적용" in r.output, r.output
    after = cuts(project)
    assert [i for i, (a, b) in enumerate(zip(before, after)) if a != b] == [2]
    assert after[2]["position"] == before[2]["position"] and after[2]["shot_id"] != before[2]["shot_id"]
    assert "(교체)" in invoke("cuts").output

    # 예시 2) "썸네일 문구를 '자취생 필수템'으로 수정해줘" → meta만
    thumb = (project.path / "thumbnail_1.png").read_bytes()
    write(project, "meta.json", {**META, "thumbnail_texts": [{"top": "자취생 필수템", "bottom": "접히는 전기포트"}]})
    r = invoke("run")
    assert ran(r.output) == ["meta"] and "자취생 필수템" in r.output, r.output
    assert (project.path / "thumbnail_1.png").read_bytes() != thumb

    # 예시 1) "대본 결을 조금 더 친근하게 바꿔서 다시 만들어줘" → script(검사) → tts → edit → meta(캡션)
    friendly = json.loads(json.dumps(SCRIPT))
    friendly["sentences"][1]["text"] = "호텔 포트, 솔직히 좀 찝찝하잖아요."
    write(project, "script.json", friendly)
    calls = len(project.fake_tts.calls)
    r = invoke("run")
    assert ran(r.output) == ["script", "tts", "edit", "meta"], r.output
    assert project.fake_tts.calls[calls:] == ["호텔 포트, 솔직히 좀 찝찝하잖아요."]  # 바뀐 문장만 다시 합성
    caption = (project.path / "caption.txt").read_text(encoding="utf-8")
    assert caption.splitlines()[1].startswith("이 포스팅은 쿠팡 파트너스")

    # 고친 대본도 다시 검사한다 (금지 표현은 막힌다)
    friendly["sentences"][3]["text"] = "최저가라 해외에서도 그냥 쓸 수 있어요."
    friendly["sentences"][3]["emphasis"] = []
    write(project, "script.json", friendly)
    r = invoke("run")
    assert r.exit_code == 1 and "최저가" in r.output and ran(r.output) == ["script"]

    # 버전: 실행이 성공할 때마다 결과가 보관되고(실패한 실행은 보관 안 함), 되돌리면 대본·영상·설정이 함께 돌아간다
    versions = project.versions()
    notes = [project.version_info(v)["note"] for v in versions]
    assert notes == ["collect → analyze → script → tts → edit → meta 실행 후", "edit 실행 후", "edit 실행 후",
                     "meta 실행 후", "script → tts → edit → meta 실행 후"]
    before_friendly = versions[notes.index("meta 실행 후")]
    r = invoke("rollback", str(before_friendly))
    assert r.exit_code == 0, r.output
    assert json.loads((project.path / "script.json").read_text(encoding="utf-8")) == SCRIPT
    assert project.config().subtitle.size == 96  # 그 시점의 설정
    assert project.pending_stages() == []  # 되돌린 결과물과 상태 기록이 맞는다
    assert "v" in invoke("versions").output


def test_overrides_follow_cut_position():
    t = timings([("hook", 6), ("problem", 8), ("demo", 12), ("benefit", 9), ("cta", 6)])
    from ssm.cutplan import plan_timeline
    timeline, _ = plan_timeline(t, three_videos(), t.duration + 0.5)
    options = replacement_candidates(timeline, three_videos(), 2)
    assert options and all(s.id not in {c.shot_id for c in timeline.cuts} for _, s in options)
    new_shot = options[0][1].id
    o = Overrides(cuts=[CutOverride(position=timeline.cuts[2].position, was=timeline.cuts[2].shot_id, shot=new_shot),
                        CutOverride(position=99.0, was="01-001", shot="01-002")])
    updated, applied, dropped = apply_overrides(timeline, three_videos(), o)
    assert applied == 1 and len(dropped) == 1  # 없는 자리의 설정은 버리고 알린다
    assert updated.cuts[2].shot_id == new_shot and updated.cuts[2].position == timeline.cuts[2].position
    assert updated.cuts[2].length == pytest.approx(timeline.cuts[2].length, abs=0.01)
    assert [c.shot_id for i, c in enumerate(updated.cuts) if i != 2] == [c.shot_id for i, c in enumerate(timeline.cuts) if i != 2]

    with pytest.raises(PlanError, match="없습니다"):
        check_replacement(timeline, three_videos(), 2, "99-999")
    mood = three_videos(mood_second=True)
    demo = next(i for i, c in enumerate(timeline.cuts) if c.section == "demo")
    with pytest.raises(PlanError, match="mood"):
        check_replacement(timeline, mood, demo, "02-001")
