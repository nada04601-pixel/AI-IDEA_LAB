"""생성 자산 파일 경로 관리. DB에는 storage 폴더 기준 상대 경로만 저장한다."""

import shutil
from pathlib import Path

from app import config


def scene_asset_base(project_id: int, scene_id: int, kind: str, version: int) -> Path:
    """확장자 없는 절대 경로. 예: storage/projects/3/scenes/12/image_v2"""
    return config.storage_dir() / "projects" / str(project_id) / "scenes" / str(scene_id) / f"{kind}_v{version}"


def to_relative(path: Path) -> str:
    return path.resolve().relative_to(config.storage_dir()).as_posix()


def resolve(relative: str) -> Path | None:
    """상대 경로를 절대 경로로 바꾼다. storage 밖을 가리키면 None."""
    root = config.storage_dir()
    path = (root / relative).resolve()
    return path if path.is_relative_to(root) else None


def delete_files(relatives: list[str]) -> None:
    for rel in relatives:
        path = resolve(rel)
        if path and path.is_file():
            path.unlink()


def delete_scene_dir(project_id: int, scene_id: int) -> None:
    shutil.rmtree(config.storage_dir() / "projects" / str(project_id) / "scenes" / str(scene_id), ignore_errors=True)


def delete_project_dir(project_id: int) -> None:
    shutil.rmtree(config.storage_dir() / "projects" / str(project_id), ignore_errors=True)
