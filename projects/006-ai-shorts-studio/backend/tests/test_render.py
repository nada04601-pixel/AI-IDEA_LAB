import json
import subprocess

import pytest

from app import config

needs_ffmpeg = pytest.mark.skipif(config.ffmpeg_path() is None, reason="FFmpeg 없음")


def make_project(client, dialogues=("첫 장면 대사입니다.", "둘째 장면!"), durations=(1.5, 2.0), ratio="9:16"):
    pid = client.post("/api/projects", json={"title": "렌더 테스트", "aspect_ratio": ratio}).json()["id"]
    ids = []
    for d, sec in zip(dialogues, durations):
        ids.append(client.post(f"/api/projects/{pid}/scenes", json={"dialogue": d, "image_prompt": "cat", "duration_sec": sec}).json()["id"])
    return pid, ids


def approve_all(client, ids, video_for=()):
    for sid in ids:
        client.post(f"/api/scenes/{sid}/generate-image")
        if sid in video_for:
            client.post(f"/api/scenes/{sid}/generate-video")
        assert client.post(f"/api/scenes/{sid}/approve").status_code == 200


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_audio_does_not_change_review_status(client):
    pid, (sid, _) = make_project(client)
    client.post(f"/api/scenes/{sid}/generate-image")
    client.post(f"/api/scenes/{sid}/approve")
    res = client.post(f"/api/scenes/{sid}/generate-audio")
    assert res.status_code == 202
    assert client.get(f"/api/jobs/{res.json()['id']}").json()["status"] == "succeeded"
    scene = client.get(f"/api/projects/{pid}/scenes").json()[0]
    assert scene["status"] == "approved"
    audio = [a for a in client.get(f"/api/projects/{pid}/assets").json() if a["asset_type"] == "audio"]
    assert len(audio) == 1 and client.get(audio[0]["url"]).headers["content-type"] in ("audio/x-wav", "audio/wav")


def test_audio_only_scene_cannot_be_approved(client):
    pid, (sid, _) = make_project(client)
    client.post(f"/api/scenes/{sid}/generate-audio")
    assert client.post(f"/api/scenes/{sid}/approve").status_code == 409


def test_audio_requires_dialogue(client):
    pid = client.post("/api/projects", json={"title": "x"}).json()["id"]
    sid = client.post(f"/api/projects/{pid}/scenes", json={"image_prompt": "cat"}).json()["id"]
    assert client.post(f"/api/scenes/{sid}/generate-audio").status_code == 422


def test_bulk_audio_and_stale_detection(client):
    pid, ids = make_project(client, dialogues=("하나", "", "셋"), durations=(1, 1, 1))
    jobs = client.post(f"/api/projects/{pid}/generate-audio").json()
    assert len(jobs) == 2  # 대사 없는 장면은 건너뛴다
    check = client.get(f"/api/projects/{pid}/render-check").json()
    assert [s["audio"] for s in check["scenes"]] == ["ready", "no_text", "ready"]
    assert client.post(f"/api/projects/{pid}/generate-audio").json() == []  # 이미 최신

    client.patch(f"/api/scenes/{ids[2]}", json={"dialogue": "바뀐 대사"})
    check = client.get(f"/api/projects/{pid}/render-check").json()
    assert check["scenes"][2]["audio"] == "stale"
    assert any("다시 만들어야" in p for p in check["audio_problems"])
    assert len(client.post(f"/api/projects/{pid}/generate-audio").json()) == 1


def test_render_check_lists_problems(client):
    pid, ids = make_project(client)
    check = client.get(f"/api/projects/{pid}/render-check").json()
    assert not check["ready"]
    assert any("승인되지" in p for p in check["problems"]) and any("음성" in p for p in check["problems"])
    assert check["total_duration"] == 3.5
    quiet = client.get(f"/api/projects/{pid}/render-check?include_audio=false").json()
    assert not any("음성" in p for p in quiet["problems"])
    assert client.post(f"/api/projects/{pid}/render").status_code == 409
    empty = client.post("/api/projects", json={"title": "빈"}).json()["id"]
    assert any("장면이 없습니다" in p for p in client.get(f"/api/projects/{empty}/render-check").json()["problems"])


def test_subtitles_endpoint(client):
    pid, _ = make_project(client)
    subs = client.get(f"/api/projects/{pid}/subtitles").json()
    assert [c["text"] for c in subs["cues"]] == ["첫 장면 대사입니다.", "둘째 장면!"]
    assert subs["cues"][1]["start"] == 1.5 and subs["cues"][1]["end"] == 3.5
    assert subs["srt"].startswith("1\n00:00:00,000 --> 00:00:01,500\n")


@needs_ffmpeg
def test_render_full_pipeline(client):
    pid, ids = make_project(client)
    approve_all(client, ids, video_for=(ids[1],))
    client.post(f"/api/projects/{pid}/generate-audio")
    check = client.get(f"/api/projects/{pid}/render-check").json()
    assert check["ready"], check["problems"]
    assert [s["visual"] for s in check["scenes"]] == ["image", "video"]

    res = client.post(f"/api/projects/{pid}/render", json={"include_audio": True, "burn_subtitles": True})
    assert res.status_code == 202
    job = client.get(f"/api/jobs/{res.json()['id']}").json()
    assert job["status"] == "succeeded", job["error_message"]
    assert job["progress"] == 100

    assets = client.get(f"/api/projects/{pid}/assets").json()
    render = next(a for a in assets if a["asset_type"] == "render")
    srt = next(a for a in assets if a["asset_type"] == "subtitle")
    assert render["scene_id"] is None and render["version"] == 1
    assert render["metadata"]["width"] == 1080 and render["metadata"]["height"] == 1920
    assert abs(render["metadata"]["duration_sec"] - 3.5) < 0.15
    assert client.get(f"/api/projects/{pid}").json()["status"] == "done"

    data = client.get(render["url"]).content
    out = config.storage_dir() / "check.mp4"
    out.write_bytes(data)
    info = probe(out)
    kinds = {s["codec_type"]: s for s in info["streams"]}
    assert kinds["video"]["codec_name"] == "h264" and kinds["video"]["width"] == 1080 and kinds["video"]["height"] == 1920
    assert kinds["audio"]["codec_name"] == "aac"
    assert kinds["subtitle"]["codec_name"] == "mov_text"
    assert client.get(srt["url"]).text.startswith("1\n00:00:00,000")

    dl = client.get(render["url"] + "?download=true")
    assert "attachment" in dl.headers["content-disposition"]
    assert "_v1.mp4" in dl.headers["content-disposition"]

    # 다시 렌더링하면 v2가 생기고 v1은 남는다
    client.post(f"/api/projects/{pid}/render", json={"include_audio": False, "burn_subtitles": False})
    versions = sorted(a["version"] for a in client.get(f"/api/projects/{pid}/assets").json() if a["asset_type"] == "render")
    assert versions == [1, 2]


@needs_ffmpeg
def test_render_square_without_audio(client):
    pid, ids = make_project(client, dialogues=("", "대사"), durations=(1, 1), ratio="1:1")
    approve_all(client, ids)
    res = client.post(f"/api/projects/{pid}/render", json={"include_audio": False, "burn_subtitles": False})
    assert client.get(f"/api/jobs/{res.json()['id']}").json()["status"] == "succeeded"
    render = next(a for a in client.get(f"/api/projects/{pid}/assets").json() if a["asset_type"] == "render")
    assert (render["metadata"]["width"], render["metadata"]["height"]) == (1080, 1080)


@needs_ffmpeg
def test_render_failure_can_be_retried(client, monkeypatch):
    pid, ids = make_project(client)
    approve_all(client, ids)
    client.post(f"/api/projects/{pid}/generate-audio")
    from app.providers.media import ProviderError
    from app.services import render_job

    real = render_job.render

    def broken(*args, **kwargs):
        args[4].mkdir(parents=True, exist_ok=True)  # 작업 폴더를 만든 뒤 실패
        raise ProviderError("장면 1 조각 만들기 실패: 테스트")

    monkeypatch.setattr(render_job, "render", broken)
    res = client.post(f"/api/projects/{pid}/render")
    job = client.get(f"/api/jobs/{res.json()['id']}").json()
    assert job["status"] == "failed" and "테스트" in job["error_message"]
    assert client.get(f"/api/projects/{pid}").json()["status"] == "in_progress"
    assert not (config.storage_dir() / "projects" / str(pid) / "renders" / "v1").exists()  # 실패한 작업 폴더 정리

    monkeypatch.setattr(render_job, "render", real)
    assert client.post(f"/api/jobs/{job['id']}/retry").status_code == 202
    job = client.get(f"/api/jobs/{job['id']}").json()
    assert job["status"] == "succeeded" and job["attempts"] == 2


def test_render_refused_without_ffmpeg(client, monkeypatch):
    pid, ids = make_project(client)
    approve_all(client, ids)
    monkeypatch.setattr(config, "ffmpeg_path", lambda: None)
    check = client.get(f"/api/projects/{pid}/render-check?include_audio=false").json()
    assert not check["ffmpeg"]["available"] and "FFmpeg" in check["problems"][0]
    res = client.post(f"/api/projects/{pid}/render", json={"include_audio": False})
    assert res.status_code == 409 and "FFmpeg" in res.json()["detail"]


def test_render_blocks_other_jobs(client):
    from app.db import SessionLocal
    from app.models.job import Job

    pid, ids = make_project(client)
    with SessionLocal() as s:
        s.add(Job(project_id=pid, scene_id=None, job_type="render", provider="ffmpeg", prompt="{}", status="running"))
        s.commit()
    assert client.post(f"/api/scenes/{ids[0]}/generate-image").status_code == 409
    assert client.post(f"/api/scenes/{ids[0]}/generate-audio").status_code == 409
    assert client.post(f"/api/projects/{pid}/render").status_code == 409


def test_delete_project_removes_render_rows(client):
    from app.db import SessionLocal
    from app.models.asset import Asset
    from app.models.job import Job

    pid, ids = make_project(client)
    with SessionLocal() as s:
        s.add(Job(project_id=pid, scene_id=None, job_type="render", provider="ffmpeg", prompt="{}", status="succeeded"))
        s.add(Asset(project_id=pid, scene_id=None, asset_type="render", file_path="x.mp4"))
        s.commit()
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    with SessionLocal() as s:
        assert s.query(Job).filter_by(project_id=pid).count() == 0
        assert s.query(Asset).filter_by(project_id=pid).count() == 0
