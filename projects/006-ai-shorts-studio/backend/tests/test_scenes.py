import sqlite3

from fastapi.testclient import TestClient


def make_project(client, **kw):
    return client.post("/api/projects", json={"title": "고양이", "topic": "상자", **kw}).json()["id"]


def numbers(client, pid):
    return [(s["id"], s["scene_number"]) for s in client.get(f"/api/projects/{pid}/scenes").json()]


def test_generate_script_and_overwrite_guard(client):
    pid = make_project(client)
    res = client.post(f"/api/projects/{pid}/generate-script")
    assert res.status_code == 200
    assert res.json()["script"].startswith("[mock]")

    client.patch(f"/api/projects/{pid}", json={"script": "내가 쓴 대본"})
    assert client.post(f"/api/projects/{pid}/generate-script").status_code == 409
    assert client.get(f"/api/projects/{pid}").json()["script"] == "내가 쓴 대본"
    res = client.post(f"/api/projects/{pid}/generate-script", json={"overwrite": True})
    assert res.json()["script"].startswith("[mock]")


def test_script_length_limit(client):
    pid = make_project(client)
    assert client.patch(f"/api/projects/{pid}", json={"script": "가" * 20001}).status_code == 422


def test_storyboard_generation(client):
    pid = make_project(client, target_duration_sec=20)
    assert client.post(f"/api/projects/{pid}/storyboard").status_code == 422  # 대본 없음

    client.patch(f"/api/projects/{pid}", json={"script": "하나\n\n둘\n\n셋"})
    res = client.post(f"/api/projects/{pid}/storyboard")
    assert res.status_code == 200
    scenes = res.json()
    assert [s["dialogue"] for s in scenes] == ["하나", "둘", "셋"]
    assert [s["scene_number"] for s in scenes] == [1, 2, 3]
    assert all(s["status"] == "draft" for s in scenes)
    assert sum(s["duration_sec"] for s in scenes) == 20

    assert client.post(f"/api/projects/{pid}/storyboard").status_code == 409
    client.patch(f"/api/projects/{pid}", json={"script": "새 대본"})
    res = client.post(f"/api/projects/{pid}/storyboard", json={"replace": True})
    assert [s["dialogue"] for s in res.json()] == ["새 대본"]
    assert len(client.get(f"/api/projects/{pid}/scenes").json()) == 1


def test_scene_crud_and_renumber(client):
    pid = make_project(client)
    ids = [client.post(f"/api/projects/{pid}/scenes", json={"dialogue": d}).json()["id"] for d in "abc"]
    assert numbers(client, pid) == [(ids[0], 1), (ids[1], 2), (ids[2], 3)]

    res = client.patch(f"/api/scenes/{ids[1]}", json={"image_prompt": "cat in box", "duration_sec": 4.5})
    assert res.status_code == 200
    assert res.json()["image_prompt"] == "cat in box"
    assert res.json()["duration_sec"] == 4.5
    assert res.json()["dialogue"] == "b"

    assert client.delete(f"/api/scenes/{ids[0]}").status_code == 204
    assert numbers(client, pid) == [(ids[1], 1), (ids[2], 2)]
    assert client.patch(f"/api/scenes/{ids[0]}", json={"dialogue": "x"}).status_code == 404


def test_scene_validation(client):
    pid = make_project(client)
    assert client.post(f"/api/projects/{pid}/scenes", json={"duration_sec": 0.1}).status_code == 422
    assert client.post(f"/api/projects/{pid}/scenes", json={"duration_sec": 61}).status_code == 422
    sid = client.post(f"/api/projects/{pid}/scenes", json={}).json()["id"]
    assert client.patch(f"/api/scenes/{sid}", json={"dialogue": None}).status_code == 422
    assert client.patch(f"/api/scenes/{sid}", json={"status": "approved"}).json()["status"] == "draft"
    assert client.post("/api/projects/9999/scenes", json={}).status_code == 404


def test_reorder(client):
    pid = make_project(client)
    ids = [client.post(f"/api/projects/{pid}/scenes", json={"dialogue": d}).json()["id"] for d in "abc"]
    res = client.post(f"/api/projects/{pid}/scenes/reorder", json={"scene_ids": [ids[2], ids[0], ids[1]]})
    assert res.status_code == 200
    assert [s["dialogue"] for s in res.json()] == ["c", "a", "b"]
    assert [s["dialogue"] for s in client.get(f"/api/projects/{pid}/scenes").json()] == ["c", "a", "b"]

    bad = [[ids[0], ids[1]], [ids[0], ids[0], ids[1]], [ids[0], ids[1], 9999]]
    for scene_ids in bad:
        assert client.post(f"/api/projects/{pid}/scenes/reorder", json={"scene_ids": scene_ids}).status_code == 422

    other = make_project(client)
    oid = client.post(f"/api/projects/{other}/scenes", json={}).json()["id"]
    assert client.post(f"/api/projects/{pid}/scenes/reorder", json={"scene_ids": [ids[0], ids[1], oid]}).status_code == 422


def test_deleting_project_deletes_scenes(client):
    pid = make_project(client)
    sid = client.post(f"/api/projects/{pid}/scenes", json={}).json()["id"]
    client.delete(f"/api/projects/{pid}")
    assert client.patch(f"/api/scenes/{sid}", json={"dialogue": "x"}).status_code == 404


def test_scene_change_bumps_project_order(client):
    a = make_project(client)
    b = make_project(client)
    assert [p["id"] for p in client.get("/api/projects").json()][0] == b
    client.post(f"/api/projects/{a}/scenes", json={})
    assert [p["id"] for p in client.get("/api/projects").json()][0] == a


def test_stage1_database_is_upgraded(tmp_path, monkeypatch):
    """1단계에서 만든 DB(script 열, scenes 테이블 없음)를 열면 빠진 부분이 추가되고 데이터는 유지된다."""
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE projects (id INTEGER PRIMARY KEY, title VARCHAR(200) NOT NULL, topic TEXT NOT NULL,"
        " target_duration_sec INTEGER NOT NULL, aspect_ratio VARCHAR(10) NOT NULL, visual_style VARCHAR(200) NOT NULL,"
        " status VARCHAR(30) NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
    )
    conn.execute(
        "INSERT INTO projects VALUES (1, '예전 프로젝트', '', 30, '9:16', '', 'draft',"
        " '2026-10-08 00:00:00', '2026-10-08 00:00:00')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("AISS_DATABASE_URL", f"sqlite:///{db}")
    from app.main import app

    with TestClient(app) as c:
        project = c.get("/api/projects/1").json()
        assert project["title"] == "예전 프로젝트"
        assert project["script"] == ""
        assert c.post("/api/projects/1/scenes", json={"dialogue": "새 장면"}).status_code == 201
