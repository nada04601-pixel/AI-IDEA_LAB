from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.db import get_session
from app.models.project import Project, utcnow
from app.models.scene import Scene
from app.schemas.scene import SceneCreate, SceneRead, SceneReorder, SceneUpdate

router = APIRouter(tags=["scenes"])

MAX_SCENES_PER_PROJECT = 50


def _get_scene_or_404(session: Session, scene_id: int) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="장면을 찾을 수 없습니다.")
    return scene


def _renumber(project: Project) -> None:
    for number, scene in enumerate(sorted(project.scenes, key=lambda s: s.scene_number), start=1):
        scene.scene_number = number


@router.get("/api/projects/{project_id}/scenes", response_model=list[SceneRead])
def list_scenes(project_id: int, session: Session = Depends(get_session)):
    return get_project_or_404(session, project_id).scenes


@router.post("/api/projects/{project_id}/scenes", response_model=SceneRead, status_code=201)
def create_scene(project_id: int, body: SceneCreate, session: Session = Depends(get_session)):
    """장면을 맨 뒤에 추가한다."""
    project = get_project_or_404(session, project_id)
    if len(project.scenes) >= MAX_SCENES_PER_PROJECT:
        raise HTTPException(status_code=422, detail=f"장면은 최대 {MAX_SCENES_PER_PROJECT}개까지 만들 수 있습니다.")
    scene = Scene(scene_number=len(project.scenes) + 1, **body.model_dump())
    project.scenes.append(scene)
    project.updated_at = utcnow()
    session.commit()
    return scene


@router.patch("/api/scenes/{scene_id}", response_model=SceneRead)
def update_scene(scene_id: int, body: SceneUpdate, session: Session = Depends(get_session)):
    scene = _get_scene_or_404(session, scene_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{key} 값은 비울 수 없습니다.")
        setattr(scene, key, value)
    scene.project.updated_at = utcnow()
    session.commit()
    return scene


@router.delete("/api/scenes/{scene_id}", status_code=204)
def delete_scene(scene_id: int, session: Session = Depends(get_session)):
    scene = _get_scene_or_404(session, scene_id)
    project = scene.project
    project.scenes.remove(scene)
    _renumber(project)
    project.updated_at = utcnow()
    session.commit()
    return Response(status_code=204)


@router.post("/api/projects/{project_id}/scenes/reorder", response_model=list[SceneRead])
def reorder_scenes(project_id: int, body: SceneReorder, session: Session = Depends(get_session)):
    """scene_ids 순서대로 장면 번호를 다시 매긴다. 프로젝트의 모든 장면을 한 번씩 포함해야 한다."""
    project = get_project_or_404(session, project_id)
    by_id = {s.id: s for s in project.scenes}
    if len(body.scene_ids) != len(by_id) or set(body.scene_ids) != set(by_id):
        raise HTTPException(status_code=422, detail="장면 목록이 현재 장면과 일치하지 않습니다. 새로고침 후 다시 시도하세요.")
    for number, scene_id in enumerate(body.scene_ids, start=1):
        by_id[scene_id].scene_number = number
    project.updated_at = utcnow()
    session.commit()
    session.refresh(project)
    return project.scenes
