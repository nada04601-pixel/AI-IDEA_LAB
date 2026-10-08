"""생성 작업 실행. 요청 API는 작업을 queued로 만들고 바로 응답하며, 실제 생성은 백그라운드에서 한다."""

import json
import logging

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.asset import Asset
from app.models.job import ACTIVE_JOB_STATUSES, Job
from app.models.project import Project, utcnow
from app.models.scene import Scene
from app.providers import get_media_provider
from app.providers.media import MediaRequest, ProviderError
from app.services import storage

log = logging.getLogger(__name__)

REVIEWABLE_KINDS = ("image", "video")  # 결과를 사용자가 검토·승인하는 작업 종류


def scene_has_active_job(session: Session, scene_id: int) -> bool:
    stmt = select(Job.id).where(Job.scene_id == scene_id, Job.status.in_(ACTIVE_JOB_STATUSES)).limit(1)
    return session.scalar(stmt) is not None


def project_has_active_job(session: Session, project_id: int) -> bool:
    stmt = select(Job.id).where(Job.project_id == project_id, Job.status.in_(ACTIVE_JOB_STATUSES)).limit(1)
    return session.scalar(stmt) is not None


def latest_asset(session: Session, scene_id: int, kind: str) -> Asset | None:
    stmt = select(Asset).where(Asset.scene_id == scene_id, Asset.asset_type == kind).order_by(Asset.version.desc()).limit(1)
    return session.scalar(stmt)


def _next_version(session: Session, scene_id: int, kind: str) -> int:
    stmt = select(func.max(Asset.version)).where(Asset.scene_id == scene_id, Asset.asset_type == kind)
    return (session.scalar(stmt) or 0) + 1


def next_project_version(session: Session, project_id: int, kind: str) -> int:
    """장면에 속하지 않는 프로젝트 단위 자산(최종 렌더 등)의 다음 버전."""
    stmt = select(func.max(Asset.version)).where(
        Asset.project_id == project_id, Asset.scene_id.is_(None), Asset.asset_type == kind
    )
    return (session.scalar(stmt) or 0) + 1


def latest_project_asset(session: Session, project_id: int, kind: str) -> Asset | None:
    stmt = (
        select(Asset)
        .where(Asset.project_id == project_id, Asset.scene_id.is_(None), Asset.asset_type == kind)
        .order_by(Asset.version.desc())
        .limit(1)
    )
    return session.scalar(stmt)


def project_render_active(session: Session, project_id: int) -> bool:
    stmt = select(Job.id).where(
        Job.project_id == project_id, Job.job_type == "render", Job.status.in_(ACTIVE_JOB_STATUSES)
    ).limit(1)
    return session.scalar(stmt) is not None


def run_job(job_id: int) -> None:
    """queued 작업 하나를 실행한다. 결과는 Asset으로 저장하고 장면 상태를 바꾼다."""
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None or job.status != "queued":
            return
        if job.job_type == "render":
            from app.services.render_job import run_render  # 순환 import 방지

            return run_render(session, job)
        scene = session.get(Scene, job.scene_id)
        if scene is None:
            return
        # 이미지·영상은 검토 대상이라 장면 상태를 바꾸고, 음성은 장면 상태를 건드리지 않는다
        reviewable = job.job_type in REVIEWABLE_KINDS
        job.status = "running"
        job.attempts += 1
        job.error_message = None
        if reviewable:
            scene.status = "generating"
        session.commit()

        try:
            provider = get_media_provider(job.job_type, job.provider)
            version = _next_version(session, scene.id, job.job_type)
            source = None
            if job.job_type == "video":
                image = latest_asset(session, scene.id, "image")
                source = storage.resolve(image.file_path) if image else None
            req = MediaRequest(
                kind=job.job_type,
                prompt=job.prompt,
                aspect_ratio=scene.project.aspect_ratio,
                duration_sec=scene.duration_sec,
                scene_number=scene.scene_number,
                version=version,
                attempt=job.attempts,
                output_path=storage.scene_asset_base(scene.project_id, scene.id, job.job_type, version),
                source_image=source,
            )
            result = provider.generate(req)
        except Exception as exc:  # 공급자 오류는 작업 실패로 기록하고 재시도할 수 있게 한다
            if not isinstance(exc, ProviderError):
                log.exception("job %s failed", job_id)
            job.status = "failed"
            job.error_message = str(exc)[:1000] or exc.__class__.__name__
            job.finished_at = utcnow()
            if reviewable:
                scene.status = "failed"
            session.commit()
            return

        session.add(
            Asset(
                project_id=scene.project_id,
                scene_id=scene.id,
                job_id=job.id,
                asset_type=job.job_type,
                version=version,
                file_path=storage.to_relative(result.file_path),
                provider=provider.name,
                cost_amount=result.cost_amount,
                cost_currency=result.cost_currency,
                metadata_json=json.dumps(result.metadata, ensure_ascii=False),
            )
        )
        job.status = "succeeded"
        job.progress = 100
        job.finished_at = utcnow()
        if reviewable:
            scene.status = "review_required"
            scene.approved_at = None
        scene.project.updated_at = utcnow()
        session.commit()


def recover_interrupted_jobs() -> None:
    """서버가 작업 도중 꺼졌다면 남은 작업을 실패로 표시해 사용자가 재시도할 수 있게 한다."""
    with SessionLocal() as session:
        active = session.scalars(select(Job).where(Job.status.in_(ACTIVE_JOB_STATUSES))).all()
        for job in active:
            job.status = "failed"
            job.error_message = "서버가 다시 시작되어 작업이 중단되었습니다. 재시도하세요."
            job.finished_at = utcnow()
        session.execute(
            update(Scene).where(Scene.status.in_(("queued", "generating"))).values(status="failed")
        )
        session.execute(update(Project).where(Project.status == "rendering").values(status="in_progress"))
        session.commit()
