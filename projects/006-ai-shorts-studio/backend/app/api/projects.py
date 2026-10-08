from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.asset import Asset
from app.models.job import ACTIVE_JOB_STATUSES, Job
from app.models.project import Project, utcnow
from app.models.scene import Scene
from app.providers import ScriptProvider, get_script_provider
from app.providers.base import ScriptRequest
from app.schemas.project import (
    MAX_SCRIPT_LENGTH,
    ProjectCreate,
    ProjectRead,
    ProjectSummary,
    ProjectUpdate,
    ScriptGenerateRequest,
    StoryboardGenerateRequest,
)
from app.schemas.scene import SceneRead
from app.services import storage
from app.services.jobs import project_has_active_job

router = APIRouter(prefix="/api/projects", tags=["projects"])


def get_project_or_404(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    return project


def _script_request(project: Project) -> ScriptRequest:
    return ScriptRequest(
        title=project.title,
        topic=project.topic,
        target_duration_sec=project.target_duration_sec,
        aspect_ratio=project.aspect_ratio,
        visual_style=project.visual_style,
    )


@router.get("", response_model=list[ProjectSummary])
def list_projects(session: Session = Depends(get_session)):
    projects = session.scalars(select(Project).order_by(Project.updated_at.desc(), Project.id.desc())).all()

    def counts(stmt) -> dict[int, int]:
        return dict(session.execute(stmt).all())

    scene_count = counts(select(Scene.project_id, func.count()).group_by(Scene.project_id))
    approved = counts(select(Scene.project_id, func.count()).where(Scene.status == "approved").group_by(Scene.project_id))
    active = counts(select(Job.project_id, func.count()).where(Job.status.in_(ACTIVE_JOB_STATUSES)).group_by(Job.project_id))
    failed = counts(select(Job.project_id, func.count()).where(Job.status == "failed").group_by(Job.project_id))
    renders = counts(
        select(Asset.project_id, func.max(Asset.version)).where(Asset.asset_type == "render").group_by(Asset.project_id)
    )
    return [
        ProjectSummary.model_validate(p).model_copy(
            update={
                "scene_count": scene_count.get(p.id, 0),
                "approved_count": approved.get(p.id, 0),
                "active_job_count": active.get(p.id, 0),
                "failed_job_count": failed.get(p.id, 0),
                "latest_render_version": renders.get(p.id),
            }
        )
        for p in projects
    ]


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(body: ProjectCreate, session: Session = Depends(get_session)):
    project = Project(**body.model_dump())
    session.add(project)
    session.commit()
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, session: Session = Depends(get_session)):
    return get_project_or_404(session, project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, body: ProjectUpdate, session: Session = Depends(get_session)):
    project = get_project_or_404(session, project_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{key} 값은 비울 수 없습니다.")
        setattr(project, key, value)
    session.commit()
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, session: Session = Depends(get_session)):
    project = get_project_or_404(session, project_id)
    if project_has_active_job(session, project_id):
        raise HTTPException(status_code=409, detail="생성 중인 작업이 있어 삭제할 수 없습니다. 작업이 끝난 뒤 다시 시도하세요.")
    # 장면에 속하지 않는 자산·작업(최종 렌더 등)도 함께 지운다
    session.execute(delete(Asset).where(Asset.project_id == project_id))
    session.execute(delete(Job).where(Job.project_id == project_id))
    session.delete(project)
    session.commit()
    storage.delete_project_dir(project_id)
    return Response(status_code=204)


@router.post("/{project_id}/generate-script", response_model=ProjectRead)
def generate_script(
    project_id: int,
    body: ScriptGenerateRequest | None = None,
    session: Session = Depends(get_session),
    provider: ScriptProvider = Depends(get_script_provider),
):
    """대본 초안을 만들어 프로젝트에 저장한다. 기존 대본은 overwrite=true일 때만 덮어쓴다."""
    project = get_project_or_404(session, project_id)
    if project.script.strip() and not (body and body.overwrite):
        raise HTTPException(status_code=409, detail="이미 대본이 있습니다. 덮어쓰려면 overwrite=true로 요청하세요.")
    project.script = provider.generate_script(_script_request(project))[:MAX_SCRIPT_LENGTH]
    session.commit()
    return project


@router.post("/{project_id}/storyboard", response_model=list[SceneRead])
def generate_storyboard(
    project_id: int,
    body: StoryboardGenerateRequest | None = None,
    session: Session = Depends(get_session),
    provider: ScriptProvider = Depends(get_script_provider),
):
    """저장된 대본을 장면으로 나눈다. 기존 장면은 replace=true일 때만 바꾼다."""
    project = get_project_or_404(session, project_id)
    if not project.script.strip():
        raise HTTPException(status_code=422, detail="대본이 비어 있습니다. 먼저 대본을 작성하거나 생성하세요.")
    if project.scenes and not (body and body.replace):
        raise HTTPException(status_code=409, detail="이미 장면이 있습니다. 바꾸려면 replace=true로 요청하세요.")
    if project_has_active_job(session, project_id):
        raise HTTPException(status_code=409, detail="생성 중인 작업이 있어 장면을 바꿀 수 없습니다. 작업이 끝난 뒤 다시 시도하세요.")
    drafts = provider.generate_storyboard(project.script, _script_request(project))
    old_scene_ids = [s.id for s in project.scenes]
    project.scenes.clear()
    session.flush()
    for number, draft in enumerate(drafts, start=1):
        project.scenes.append(
            Scene(
                scene_number=number,
                dialogue=draft.dialogue,
                visual_description=draft.visual_description,
                image_prompt=draft.image_prompt,
                video_prompt=draft.video_prompt,
                duration_sec=draft.duration_sec,
            )
        )
    project.updated_at = utcnow()
    session.commit()
    for scene_id in old_scene_ids:
        storage.delete_scene_dir(project_id, scene_id)
    return project.scenes
