"""환경 변수 설정. 비밀값은 코드에 두지 않고 .env 또는 환경 변수로만 받는다."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def database_url() -> str:
    url = os.getenv("AISS_DATABASE_URL")
    if url:
        return url
    storage = Path(os.getenv("AISS_STORAGE_DIR", PROJECT_ROOT / "storage"))
    storage.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{storage / 'app.db'}"


def cors_origins() -> list[str]:
    raw = os.getenv("AISS_CORS_ORIGINS", "http://localhost:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]
