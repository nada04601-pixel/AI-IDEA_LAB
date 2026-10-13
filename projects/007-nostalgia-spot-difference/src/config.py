"""설정 로딩. `.env` 파일과 환경 변수를 읽어 Settings 하나로 모은다.

외부 패키지(python-dotenv)를 쓰지 않으려고 아주 단순한 .env 파서를 직접 둔다.
환경 변수가 .env보다 우선한다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


@dataclass
class Settings:
    root: Path = ROOT
    # 이미지 원본: procedural(내장 손그림 장면, GPU 불필요) | sample(assets/sample_images) | comfyui
    image_source: str = "procedural"
    difficulty: str = "normal"
    font_path: str = ""
    # ComfyUI
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_workflow: str = "workflows/comfyui_workflow.json"
    comfyui_checkpoint: str = "sd_xl_base_1.0.safetensors"
    comfyui_timeout: int = 300
    # 업로드 (기본: 꺼짐, 비공개)
    upload_enabled: bool = False
    upload_privacy: str = "private"
    allow_public_upload: bool = False
    youtube_client_secrets: str = "credentials.json"
    youtube_token: str = "token.json"
    youtube_category_id: str = "24"
    made_for_kids: bool = False
    # auto: AI 생성 이미지(comfyui)일 때만 YouTube의 "변경되거나 합성된 콘텐츠" 표시를 켬
    declare_synthetic_media: str = "auto"
    # 예약 실행
    daily_count: int = 1
    max_retries: int = 3
    # 렌더링
    music_volume: float = 0.18
    paths: dict[str, Path] = field(default_factory=dict)

    def path(self, key: str) -> Path:
        return self.paths[key]

    def resolve(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else self.root / p


def load_settings(env_file: Path | None = None, root: Path | None = None) -> Settings:
    root = root or ROOT
    file_values = _read_env_file(env_file or root / ".env")

    def get(key: str, default: str = "") -> str:
        return os.environ.get(key, file_values.get(key, default))

    s = Settings(root=root)
    s.image_source = get("IMAGE_SOURCE", s.image_source).lower()
    s.difficulty = get("DIFFICULTY", s.difficulty).lower()
    s.font_path = get("FONT_PATH", "")
    s.comfyui_url = get("COMFYUI_URL", s.comfyui_url).rstrip("/")
    s.comfyui_workflow = get("COMFYUI_WORKFLOW", s.comfyui_workflow)
    s.comfyui_checkpoint = get("COMFYUI_CHECKPOINT", s.comfyui_checkpoint)
    s.comfyui_timeout = _int(get("COMFYUI_TIMEOUT"), s.comfyui_timeout)
    s.upload_enabled = _bool(get("UPLOAD_ENABLED"), False)
    s.upload_privacy = get("UPLOAD_PRIVACY", "private").lower()
    s.allow_public_upload = _bool(get("ALLOW_PUBLIC_UPLOAD"), False)
    s.youtube_client_secrets = get("YOUTUBE_CLIENT_SECRETS", s.youtube_client_secrets)
    s.youtube_token = get("YOUTUBE_TOKEN", s.youtube_token)
    s.youtube_category_id = get("YOUTUBE_CATEGORY_ID", s.youtube_category_id)
    s.made_for_kids = _bool(get("MADE_FOR_KIDS"), False)
    s.declare_synthetic_media = get("DECLARE_SYNTHETIC_MEDIA", "auto").lower()
    s.daily_count = max(1, _int(get("DAILY_COUNT"), 1))
    s.max_retries = max(1, _int(get("MAX_RETRIES"), 3))
    try:
        s.music_volume = float(get("MUSIC_VOLUME", "0.18"))
    except ValueError:
        pass

    s.paths = {
        "data": root / "data",
        "puzzles": root / "data" / "puzzles",
        "db": root / "data" / "jobs.sqlite",
        "topics": root / "data" / "topics.json",
        "images": root / "output" / "images",
        "previews": root / "output" / "previews",
        "videos": root / "output" / "videos",
        "logs": root / "output" / "logs",
        "fonts": root / "assets" / "fonts",
        "music": root / "assets" / "music",
        "samples": root / "assets" / "sample_images",
    }
    for key in ("puzzles", "images", "previews", "videos", "logs"):
        s.paths[key].mkdir(parents=True, exist_ok=True)
    return s


DIFFICULTY_COUNTS = {"easy": 3, "normal": 5, "hard": 7}


def difference_count(difficulty: str) -> int:
    if difficulty not in DIFFICULTY_COUNTS:
        raise ValueError(f"알 수 없는 난이도: {difficulty} (easy/normal/hard 중 하나)")
    return DIFFICULTY_COUNTS[difficulty]
