"""환경 변수 설정. 비밀값은 코드에 두지 않고 .env 또는 환경 변수로만 받는다."""

import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def storage_dir() -> Path:
    """DB와 생성 자산(이미지·영상)을 저장하는 폴더."""
    path = Path(os.getenv("AISS_STORAGE_DIR", PROJECT_ROOT / "storage")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_url() -> str:
    return os.getenv("AISS_DATABASE_URL") or f"sqlite:///{storage_dir() / 'app.db'}"


def cors_origins() -> list[str]:
    raw = os.getenv("AISS_CORS_ORIGINS", "http://localhost:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


def ffmpeg_path() -> str | None:
    return os.getenv("AISS_FFMPEG_PATH") or shutil.which("ffmpeg")
