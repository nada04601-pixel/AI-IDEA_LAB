from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.generation import create_job
from app.api.projects import get_project_or_404
from app.db import get_session
from app.models.job import Job
from app.schemas.generation import GenerateRequest, JobRead
from app.schemas.render import FfmpegInfo, RenderCheck, RenderRequest, SubtitlesRead
from app.services import jobs as job_service
from app.services.render import RenderSettings, ffmpeg_info
from app.services.render_plan import audio_status, plan_render
from app.services.subtitles import to_srt

router = APIRouter(tags=["render"])


@router.get("/api/system/ffmpeg", response_model=FfmpegInfo)
def get_ffmpeg():
    return ffmpeg_info()


@router.post("/api/projects/{project_id}/generate-audio", response_model=list[JobRead], status_code=202)
def generate_project_audio(
    project_id: int,
    background: BackgroundTasks,
    body: GenerateRequest | None = None,
    session: Session = Depends(get_session),
):
    """대사가 있고 음성이 없거나 대사가 바뀐 장면의 음성을 한 번에 만든다. 생성 중인 장면은 건너뛴다."""
    project = get_project_or_404(session, project_id)
    created: list[Job] = []
    for scene in sorted(project.scenes, key=lambda s: s.scene_number):
        status, _ = audio_status(session, scene)
        if status not in ("none", "stale") or job_service.scene_has_active_job(session, scene.id):
            continue
        created.append(create_job("audio", scene, bool(body and body.confirm_paid), session))
    session.commit()
    for job in created:
        background.add_task(job_service.run_job, job.id)
    return created


@router.get("/api/projects/{project_id}/render-check", response_model=RenderCheck)
def render_check(project_id: int, include_audio: bool = True, session: Session = Depends(get_session)):
    project = get_project_or_404(session, project_id)
    plan = plan_render(session, project, include_audio)
    info = ffmpeg_info()
    problems = list(plan.problems)
    if not info["available"]:
        problems.insert(0, "FFmpeg를 찾을 수 없습니다. 설치하거나 AISS_FFMPEG_PATH를 지정하세요.")
    return RenderCheck(
        ffmpeg=info,
        ready=not problems,
        problems=problems,
        audio_problems=plan.audio_problems,
        total_duration=plan.total_duration,
        scenes=[asdict(s) for s in plan.scenes],
    )


@router.get("/api/projects/{project_id}/subtitles", response_model=SubtitlesRead)
def get_subtitles(project_id: int, session: Session = Depends(get_session)):
    """현재 장면 대사·길이로 계산한 자막. 렌더링할 때 이 내용이 SRT로 저장된다."""
    project = get_project_or_404(session, project_id)
    plan = plan_render(session, project)
    return SubtitlesRead(cues=[asdict(c) for c in plan.cues], srt=to_srt(plan.cues))


@router.post("/api/projects/{project_id}/render", response_model=JobRead, status_code=202)
def start_render(
    project_id: int,
    background: BackgroundTasks,
    body: RenderRequest | None = None,
    session: Session = Depends(get_session),
):
    """모든 장면이 승인되었을 때만 최종 MP4 렌더링 작업을 시작한다."""
    project = get_project_or_404(session, project_id)
    settings = RenderSettings(**(body or RenderRequest()).model_dump())
    if job_service.project_has_active_job(session, project_id):
        raise HTTPException(status_code=409, detail="진행 중인 작업이 있습니다. 끝난 뒤 다시 렌더링하세요.")
    if not ffmpeg_info()["available"]:
        raise HTTPException(status_code=409, detail="FFmpeg를 찾을 수 없습니다. 설치하거나 AISS_FFMPEG_PATH를 지정하세요.")
    plan = plan_render(session, project, settings.include_audio)
    if plan.problems:
        raise HTTPException(status_code=409, detail="렌더링할 수 없습니다: " + " ".join(plan.problems))
    job = Job(
        project_id=project_id,
        scene_id=None,
        job_type="render",
        provider="ffmpeg",
        prompt=settings.to_json(),
        estimated_cost=0.0,
        cost_currency="USD",
    )
    session.add(job)
    session.commit()
    background.add_task(job_service.run_job, job.id)
    return job
