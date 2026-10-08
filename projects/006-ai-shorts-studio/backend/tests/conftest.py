import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AISS_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    from app.main import app

    with TestClient(app) as c:
        yield c
