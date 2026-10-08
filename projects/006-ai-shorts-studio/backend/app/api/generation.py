from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.db import get_session
from app.models.asset import Asset
from app.models.job import Job
from app.models.project import utcnow
from app.models.scene import Scene
from app.providers import MEDIA_PROVIDERS, get_media_provider, get_script_provider, media_provider_name
from app.providers.base import ScriptProvider
from app.schemas.generation import AssetRead, GenerateRequest, JobRead, ProviderInfo, RejectRequest
from app.schemas.scene import SceneRead
from app.services import jobs as job_service
from app.services import storage

router = APIRouter(tags=["generation"])

REVIEWABLE = ("review_required", "approved")


def _scene_or_404(session: Session, scene_id: int) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="장면을 찾을 수 없습니다.")
    return scene


def _prompt_for(scene: Scene, kind: str) -> str:
    if kind == "image":
        candidates = (scene.image_prompt, scene.visual_description, scene.dialogue)
    else:
        candidates = (scene.video_prompt, scene.image_prompt, scene.visual_description, scene.dialogue)
    return next((c.strip() for c in candidates if c.strip()), "")


def _check_paid(provider, confirm_paid: bool, duration_sec: float) -> float:
    estimate = provider.estimate_cost(duration_sec)
    if provider.is_paid and not confirm_paid:
        raise HTTPException(
            status_code=409,
            detail=f"유료 작업입니다 ({provider.name}, 예상 {estimate:g} {provider.currency}). "
            "비용을 확인했다면 confirm_paid=true로 다시 요청하세요.",
        )
    return estimate


@router.get("/api/providers", response_model=list[ProviderInfo])
def list_providers(script: ScriptProvider = Depends(get_script_provider)):
    infos = [ProviderInfo(kind="script", name=script.name, is_paid=script.is_paid, estimated_cost_per_job=0.0, currency="USD")]
    for kind in MEDIA_PROVIDERS:
        p = get_media_provider(kind, media_provider_name(kind))
        infos.append(ProviderInfo(kind=kind, name=p.name, is_paid=p.is_paid, estimated_cost_per_job=p.estimate_cost(5.0), currency=p.currency))
    return infos


def _start(kind: str, scene_id: int, body: GenerateRequest | None, background: BackgroundTasks, session: Session) -> Job:
    scene = _scene_or_404(session, scene_id)
    if job_service.scene_has_active_job(session, scene.id):
        raise HTTPException(status_code=409, detail="이 장면은 이미 생성 중입니다. 끝난 뒤 다시 시도하세요.")
    prompt = _prompt_for(scene, kind)
    if not prompt:
        raise HTTPException(status_code=422, detail="프롬프트가 비어 있습니다. 스토리보드에서 프롬프트나 대사를 입력하세요.")
    try:
        provider = get_media_provider(kind)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    estimate = _check_paid(provider, bool(body and body.confirm_paid), scene.duration_sec)
    job = Job(
        project_id=scene.project_id,
        scene_id=scene.id,
        job_type=kind,
        provider=provider.name,
        prompt=prompt,
        estimated_cost=estimate,
        cost_currency=provider.currency,
    )
    session.add(job)
    scene.status = "queued"
    scene.approved_at = None
    session.commit()
    background.add_task(job_service.run_job, job.id)
    return job


@router.post("/api/scenes/{scene_id}/generate-image", response_model=JobRead, status_code=202)
def generate_image(scene_id: int, background: BackgroundTasks, body: GenerateRequest | None = None, session: Session = Depends(get_session)):
    return _start("image", scene_id, body, background, session)


@router.post("/api/scenes/{scene_id}/generate-video", response_model=JobRead, status_code=202)
def generate_video(scene_id: int, background: BackgroundTasks, body: GenerateRequest | None = None, session: Session = Depends(get_session)):
    return _start("video", scene_id, body, background, session)


@router.post("/api/scenes/{scene_id}/approve", response_model=SceneRead)
def approve_scene(scene_id: int, session: Session = Depends(get_session)):
    scene = _scene_or_404(session, scene_id)
    if scene.status != "review_required":
        raise HTTPException(status_code=409, detail="검토 필요 상태인 장면만 승인할 수 있습니다.")
    if not scene.assets:
        raise HTTPException(status_code=409, detail="생성된 결과가 없는 장면은 승인할 수 없습니다.")
    scene.status = "approved"
    scene.approved_at = utcnow()
    scene.rejection_reason = None
    scene.project.updated_at = utcnow()
    session.commit()
    return scene


@router.post("/api/scenes/{scene_id}/reject", response_model=SceneRead)
def reject_scene(scene_id: int, body: RejectRequest, session: Session = Depends(get_session)):
    scene = _scene_or_404(session, scene_id)
    if scene.status not in REVIEWABLE:
        raise HTTPException(status_code=409, detail="검토 필요 또는 승인 상태인 장면만 반려할 수 있습니다.")
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="반려 사유를 입력하세요.")
    scene.status = "rejected"
    scene.rejection_reason = reason
    scene.approved_at = None
    scene.project.updated_at = utcnow()
    session.commit()
    return scene


@router.get("/api/projects/{project_id}/jobs", response_model=list[JobRead])
def list_jobs(project_id: int, session: Session = Depends(get_session)):
    get_project_or_404(session, project_id)
    return session.scalars(select(Job).where(Job.project_id == project_id).order_by(Job.id.desc())).all()


@router.get("/api/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return job


@router.post("/api/jobs/{job_id}/retry", response_model=JobRead, status_code=202)
def retry_job(job_id: int, background: BackgroundTasks, body: GenerateRequest | None = None, session: Session = Depends(get_session)):
    """실패한 작업을 같은 프롬프트·공급자로 다시 실행한다."""
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    if job.status != "failed":
        raise HTTPException(status_code=409, detail="실패한 작업만 재시도할 수 있습니다.")
    scene = _scene_or_404(session, job.scene_id)
    if job_service.scene_has_active_job(session, scene.id):
        raise HTTPException(status_code=409, detail="이 장면은 이미 생성 중입니다. 끝난 뒤 다시 시도하세요.")
    try:
        provider = get_media_provider(job.job_type, job.provider)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    _check_paid(provider, bool(body and body.confirm_paid), scene.duration_sec)
    job.status = "queued"
    job.progress = 0
    job.error_message = None
    job.finished_at = None
    scene.status = "queued"
    scene.approved_at = None
    session.commit()
    background.add_task(job_service.run_job, job.id)
    return job


@router.get("/api/projects/{project_id}/assets", response_model=list[AssetRead])
def list_assets(project_id: int, session: Session = Depends(get_session)):
    get_project_or_404(session, project_id)
    return session.scalars(select(Asset).where(Asset.project_id == project_id).order_by(Asset.id)).all()


@router.get("/api/assets/{asset_id}/file")
def asset_file(asset_id: int, session: Session = Depends(get_session)):
    asset = session.get(Asset, asset_id)
    path = storage.resolve(asset.file_path) if asset else None
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(path)
