"""환경 변수 설정. 비밀값은 코드에 두지 않고 .env 또는 환경 변수로만 받는다."""

import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_env_file(path: Path | None = None) -> None:
    """projects/006-ai-shorts-studio/.env의 KEY=VALUE를 환경 변수로 읽는다.

    이미 설정된 환경 변수는 덮어쓰지 않는다. 값은 로그에 남기지 않는다.
    """
    path = path or PROJECT_ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()  # 줄 끝 주석
        if key and key not in os.environ:
            os.environ[key] = value


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
