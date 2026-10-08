def test_validation_errors_are_korean_sentences(client):
    res = client.post("/api/projects", json={"title": ""})
    assert res.status_code == 422
    assert res.json()["detail"] == "제목을 입력하세요."
    assert res.json()["errors"][0]["type"] == "string_too_short"

    res = client.post("/api/projects", json={"title": "x", "target_duration_sec": 999, "aspect_ratio": "4:3"})
    detail = res.json()["detail"]
    assert "목표 길이는 180 이하여야 합니다." in detail and "화면 비율 값은" in detail

    assert client.post("/api/projects", json={}).json()["detail"] == "제목 값이 필요합니다."
    assert client.get("/api/projects/abc").json()["detail"] == "프로젝트 번호는 정수여야 합니다."
    res = client.post("/api/projects", content="not json", headers={"Content-Type": "application/json"})
    assert res.json()["detail"] == "요청 본문이 올바른 JSON이 아닙니다."


def test_scene_validation_message(client):
    pid = client.post("/api/projects", json={"title": "x"}).json()["id"]
    res = client.post(f"/api/projects/{pid}/scenes", json={"duration_sec": 100})
    assert res.json()["detail"] == "장면 길이는 60.0 이하여야 합니다."


def test_unexpected_error_is_hidden_behind_message(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("AISS_DATABASE_URL", f"sqlite:///{tmp_path / 'e.db'}")
    monkeypatch.setenv("AISS_STORAGE_DIR", str(tmp_path / "storage"))
    from app.api import generation
    from app.main import app


    monkeypatch.setattr(generation, "MEDIA_PROVIDERS", None)  # /api/providers에서 예외 발생
    with TestClient(app, raise_server_exceptions=False) as c:
        res = c.get("/api/providers")
    assert res.status_code == 500
    assert "예상하지 못한 오류" in res.json()["detail"] and "secret" not in res.text


def test_foreign_keys_are_enforced(client):
    from sqlalchemy.exc import IntegrityError

    from app.db import SessionLocal
    from app.models.scene import Scene

    import pytest

    with SessionLocal() as s:
        s.add(Scene(project_id=9999, scene_number=1))
        with pytest.raises(IntegrityError):
            s.commit()


def test_project_summary(client):
    pid = client.post("/api/projects", json={"title": "요약"}).json()["id"]
    a = client.post(f"/api/projects/{pid}/scenes", json={"image_prompt": "cat"}).json()["id"]
    client.post(f"/api/projects/{pid}/scenes", json={"image_prompt": "dog [mock-fail]"})
    b = client.get(f"/api/projects/{pid}/scenes").json()[1]["id"]
    client.post(f"/api/scenes/{a}/generate-image")
    client.post(f"/api/scenes/{a}/approve")
    client.post(f"/api/scenes/{b}/generate-image")
    other = client.post("/api/projects", json={"title": "빈 프로젝트"}).json()["id"]

    summary = {p["id"]: p for p in client.get("/api/projects").json()}
    s = summary[pid]
    assert (s["scene_count"], s["approved_count"], s["active_job_count"], s["failed_job_count"]) == (2, 1, 0, 1)
    assert s["latest_render_version"] is None
    assert summary[other]["scene_count"] == 0 and summary[other]["failed_job_count"] == 0


def test_josa():
    from app.errors import josa

    assert josa("제목", "을", "를") == "제목을"
    assert josa("대사", "을", "를") == "대사를"
    assert josa("장면 길이", "은", "는") == "장면 길이는"
    assert josa("반려 사유", "은", "는") == "반려 사유는"
