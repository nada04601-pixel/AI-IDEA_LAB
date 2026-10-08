
import pytest
from fastapi.testclient import TestClient

from app import config
from app.models.job import Job
from app.providers import MEDIA_PROVIDERS
from app.providers.media import MediaResult


def setup_scene(client, **scene):
    pid = client.post("/api/projects", json={"title": "고양이"}).json()["id"]
    sid = client.post(f"/api/projects/{pid}/scenes", json={"image_prompt": "cat", "duration_sec": 1, **scene}).json()["id"]
    return pid, sid


def scene_of(client, pid, sid):
    return next(s for s in client.get(f"/api/projects/{pid}/scenes").json() if s["id"] == sid)


def test_generate_image_review_and_approve(client):
    pid, sid = setup_scene(client)
    res = client.post(f"/api/scenes/{sid}/generate-image")
    assert res.status_code == 202
    job = res.json()
    assert job["status"] == "queued" and job["provider"] == "mock" and job["estimated_cost"] == 0

    # TestClient는 응답 뒤 백그라운드 작업까지 실행한다
    job = client.get(f"/api/jobs/{job['id']}").json()
    assert job["status"] == "succeeded" and job["attempts"] == 1
    assert scene_of(client, pid, sid)["status"] == "review_required"

    assets = client.get(f"/api/projects/{pid}/assets").json()
    assert len(assets) == 1 and assets[0]["version"] == 1 and assets[0]["cost_amount"] == 0
    file = client.get(assets[0]["url"])
    assert file.status_code == 200 and file.headers["content-type"] == "image/png"

    res = client.post(f"/api/scenes/{sid}/approve")
    assert res.status_code == 200
    assert res.json()["status"] == "approved" and res.json()["approved_at"]


def test_regenerate_keeps_history(client):
    pid, sid = setup_scene(client)
    client.post(f"/api/scenes/{sid}/generate-image")
    client.post(f"/api/scenes/{sid}/reject", json={"reason": "너무 어두움"})
    client.patch(f"/api/scenes/{sid}", json={"image_prompt": "bright cat"})
    client.post(f"/api/scenes/{sid}/generate-image")
    assets = client.get(f"/api/projects/{pid}/assets").json()
    assert [a["version"] for a in assets] == [1, 2]
    assert all(client.get(a["url"]).status_code == 200 for a in assets)
    jobs = client.get(f"/api/projects/{pid}/jobs").json()
    assert [j["prompt"] for j in jobs] == ["bright cat", "cat"]  # 최신순, 요청 시점 프롬프트 보존


@pytest.mark.skipif(config.ffmpeg_path() is None, reason="FFmpeg 없음")
def test_generate_video_uses_latest_image(client):
    pid, sid = setup_scene(client, video_prompt="slow zoom")
    client.post(f"/api/scenes/{sid}/generate-image")
    job = client.post(f"/api/scenes/{sid}/generate-video").json()
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "succeeded"
    video = [a for a in client.get(f"/api/projects/{pid}/assets").json() if a["asset_type"] == "video"][0]
    assert client.get(video["url"]).headers["content-type"] == "video/mp4"


def test_reject_rules(client):
    pid, sid = setup_scene(client)
    assert client.post(f"/api/scenes/{sid}/reject", json={"reason": "x"}).status_code == 409  # draft
    assert client.post(f"/api/scenes/{sid}/approve").status_code == 409  # draft
    client.post(f"/api/scenes/{sid}/generate-image")
    assert client.post(f"/api/scenes/{sid}/reject", json={"reason": ""}).status_code == 422
    assert client.post(f"/api/scenes/{sid}/reject", json={"reason": "   "}).status_code == 422
    res = client.post(f"/api/scenes/{sid}/reject", json={"reason": " 고양이가 안 보임 "})
    assert res.json()["status"] == "rejected" and res.json()["rejection_reason"] == "고양이가 안 보임"
    assert client.post(f"/api/scenes/{sid}/approve").status_code == 409  # 반려 후에는 재생성해야 승인 가능


def test_edit_after_approval_requires_review(client):
    pid, sid = setup_scene(client)
    client.post(f"/api/scenes/{sid}/generate-image")
    client.post(f"/api/scenes/{sid}/approve")
    client.patch(f"/api/scenes/{sid}", json={"image_prompt": "cat"})  # 값이 같으면 그대로
    assert scene_of(client, pid, sid)["status"] == "approved"
    client.patch(f"/api/scenes/{sid}", json={"dialogue": "새 대사"})
    scene = scene_of(client, pid, sid)
    assert scene["status"] == "review_required" and scene["approved_at"] is None


def test_failure_and_retry(client):
    pid, sid = setup_scene(client, image_prompt="cat [mock-fail-once]")
    job = client.post(f"/api/scenes/{sid}/generate-image").json()
    job = client.get(f"/api/jobs/{job['id']}").json()
    assert job["status"] == "failed" and "재시도" in job["error_message"]
    assert scene_of(client, pid, sid)["status"] == "failed"
    assert client.post(f"/api/scenes/{sid}/approve").status_code == 409

    res = client.post(f"/api/jobs/{job['id']}/retry")
    assert res.status_code == 202
    job = client.get(f"/api/jobs/{job['id']}").json()
    assert job["status"] == "succeeded" and job["attempts"] == 2 and job["error_message"] is None
    assert scene_of(client, pid, sid)["status"] == "review_required"
    assert client.post(f"/api/jobs/{job['id']}/retry").status_code == 409  # 성공한 작업은 재시도 불가


def test_empty_prompt_is_rejected(client):
    pid = client.post("/api/projects", json={"title": "x"}).json()["id"]
    sid = client.post(f"/api/projects/{pid}/scenes", json={}).json()["id"]
    assert client.post(f"/api/scenes/{sid}/generate-image").status_code == 422
    client.patch(f"/api/scenes/{sid}", json={"dialogue": "대사만 있음"})
    assert client.post(f"/api/scenes/{sid}/generate-image").status_code == 202


def _add_active_job(pid, sid):
    from app.db import SessionLocal

    with SessionLocal() as s:
        s.add(Job(project_id=pid, scene_id=sid, job_type="image", provider="mock", prompt="cat", status="running"))
        s.commit()


def test_active_job_blocks_duplicates_and_deletes(client):
    pid, sid = setup_scene(client)
    client.patch(f"/api/projects/{pid}", json={"script": "a"})
    _add_active_job(pid, sid)
    assert client.post(f"/api/scenes/{sid}/generate-image").status_code == 409
    assert client.post(f"/api/scenes/{sid}/generate-video").status_code == 409
    assert client.delete(f"/api/scenes/{sid}").status_code == 409
    assert client.delete(f"/api/projects/{pid}").status_code == 409
    assert client.post(f"/api/projects/{pid}/storyboard", json={"replace": True}).status_code == 409


def test_interrupted_jobs_fail_on_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("AISS_DATABASE_URL", f"sqlite:///{tmp_path / 'r.db'}")
    monkeypatch.setenv("AISS_STORAGE_DIR", str(tmp_path / "storage"))
    from app.main import app

    with TestClient(app) as c:
        pid, sid = setup_scene(c)
        _add_active_job(pid, sid)
    with TestClient(app) as c:
        job = c.get(f"/api/projects/{pid}/jobs").json()[0]
        assert job["status"] == "failed" and "다시 시작" in job["error_message"]
        assert c.post(f"/api/jobs/{job['id']}/retry").status_code == 202


def test_deleting_removes_files(client):
    pid, sid = setup_scene(client)
    client.post(f"/api/scenes/{sid}/generate-image")
    scene_dir = config.storage_dir() / "projects" / str(pid) / "scenes" / str(sid)
    assert any(scene_dir.iterdir())
    client.delete(f"/api/scenes/{sid}")
    assert not scene_dir.exists()

    sid2 = client.post(f"/api/projects/{pid}/scenes", json={"image_prompt": "dog"}).json()["id"]
    client.post(f"/api/scenes/{sid2}/generate-image")
    client.delete(f"/api/projects/{pid}")
    assert not (config.storage_dir() / "projects" / str(pid)).exists()


class FakePaidProvider:
    name = "fakepaid"
    kind = "image"
    is_paid = True
    currency = "USD"

    def estimate_cost(self, duration_sec):
        return 0.04

    def generate(self, req):
        path = req.output_path.with_suffix(".png")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG fake")
        return MediaResult(path, 0.04, "USD", {})


def test_paid_provider_requires_confirmation(client, monkeypatch):
    monkeypatch.setitem(MEDIA_PROVIDERS["image"], "fakepaid", FakePaidProvider)
    monkeypatch.setenv("AISS_IMAGE_PROVIDER", "fakepaid")
    info = {p["kind"]: p for p in client.get("/api/providers").json()}
    assert info["image"]["is_paid"] and info["image"]["estimated_cost_per_job"] == 0.04
    assert info["video"]["name"] == "mock" and not info["video"]["is_paid"]

    pid, sid = setup_scene(client)
    res = client.post(f"/api/scenes/{sid}/generate-image")
    assert res.status_code == 409 and "0.04" in res.json()["detail"]
    assert client.get(f"/api/projects/{pid}/jobs").json() == []  # 확인 전에는 작업을 만들지 않는다

    res = client.post(f"/api/scenes/{sid}/generate-image", json={"confirm_paid": True})
    assert res.status_code == 202 and res.json()["estimated_cost"] == 0.04
    asset = client.get(f"/api/projects/{pid}/assets").json()[0]
    assert asset["cost_amount"] == 0.04 and asset["provider"] == "fakepaid"


def test_asset_file_path_cannot_escape_storage(client):
    from app.db import SessionLocal
    from app.models.asset import Asset

    pid, sid = setup_scene(client)
    with SessionLocal() as s:
        a = Asset(project_id=pid, scene_id=sid, asset_type="image", file_path="../../etc/passwd")
        s.add(a)
        s.commit()
        aid = a.id
    assert client.get(f"/api/assets/{aid}/file").status_code == 404
