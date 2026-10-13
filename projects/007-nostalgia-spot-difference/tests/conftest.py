import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.fonts import find_font  # noqa: E402


@pytest.fixture(scope="session")
def font_path() -> str:
    try:
        return find_font("", str(ROOT / "assets" / "fonts"))
    except FileNotFoundError:
        pytest.skip("한글 글꼴이 없어 건너뜀")


@pytest.fixture
def settings(tmp_path, monkeypatch):
    """임시 폴더를 루트로 쓰는 설정 (실제 output/·data/를 건드리지 않음)."""
    import shutil
    from src.config import load_settings
    (tmp_path / "data").mkdir()
    shutil.copy(ROOT / "data" / "topics.json", tmp_path / "data" / "topics.json")
    for k in ("IMAGE_SOURCE", "UPLOAD_ENABLED", "UPLOAD_PRIVACY", "ALLOW_PUBLIC_UPLOAD", "DIFFICULTY"):
        monkeypatch.delenv(k, raising=False)
    return load_settings(env_file=tmp_path / ".env", root=tmp_path)
