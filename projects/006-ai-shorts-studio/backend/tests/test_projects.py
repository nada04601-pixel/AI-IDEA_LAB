def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_project_crud(client):
    res = client.post("/api/projects", json={"title": "고양이 쇼츠", "topic": "고양이가 상자를 좋아하는 이유"})
    assert res.status_code == 201
    created = res.json()
    assert created["aspect_ratio"] == "9:16"
    assert created["target_duration_sec"] == 30
    assert created["status"] == "draft"
    pid = created["id"]

    assert [p["id"] for p in client.get("/api/projects").json()] == [pid]
    assert client.get(f"/api/projects/{pid}").json()["title"] == "고양이 쇼츠"

    res = client.patch(f"/api/projects/{pid}", json={"visual_style": "수채화", "target_duration_sec": 45})
    assert res.status_code == 200
    assert res.json()["visual_style"] == "수채화"
    assert res.json()["target_duration_sec"] == 45
    assert res.json()["topic"] == "고양이가 상자를 좋아하는 이유"

    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/projects/{pid}").status_code == 404
    assert client.get("/api/projects").json() == []


def test_list_orders_recently_updated_first(client):
    a = client.post("/api/projects", json={"title": "A"}).json()["id"]
    b = client.post("/api/projects", json={"title": "B"}).json()["id"]
    client.patch(f"/api/projects/{a}", json={"topic": "수정"})
    assert [p["id"] for p in client.get("/api/projects").json()] == [a, b]


def test_validation(client):
    assert client.post("/api/projects", json={"title": ""}).status_code == 422
    assert client.post("/api/projects", json={"title": "x", "aspect_ratio": "4:3"}).status_code == 422
    assert client.post("/api/projects", json={"title": "x", "target_duration_sec": 1}).status_code == 422
    pid = client.post("/api/projects", json={"title": "x"}).json()["id"]
    assert client.patch(f"/api/projects/{pid}", json={"title": None}).status_code == 422
    assert client.patch("/api/projects/9999", json={"title": "y"}).status_code == 404


def test_data_persists_across_restart(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("AISS_DATABASE_URL", f"sqlite:///{tmp_path / 'persist.db'}")
    from app.main import app

    with TestClient(app) as c:
        c.post("/api/projects", json={"title": "남는 프로젝트"})
    with TestClient(app) as c:
        assert [p["title"] for p in c.get("/api/projects").json()] == ["남는 프로젝트"]


def test_timestamps_are_utc_aware(client):
    created = client.post("/api/projects", json={"title": "x"}).json()
    assert created["created_at"].endswith(("+00:00", "Z"))
    fetched = client.get(f"/api/projects/{created['id']}").json()
    assert fetched["updated_at"].endswith(("+00:00", "Z"))
