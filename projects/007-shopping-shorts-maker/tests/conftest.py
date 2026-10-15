import shutil
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    """config.yaml만 복사한 빈 프로젝트 폴더를 SSM_HOME으로 쓴다 (실제 workspace를 건드리지 않게)."""
    root = tmp_path / "작업 폴더"  # 한글·공백 경로도 함께 검증
    root.mkdir()
    shutil.copy(PROJECT / "config.yaml", root / "config.yaml")
    monkeypatch.setenv("SSM_HOME", str(root))
    return root
