"""최종 렌더링 작업 실행."""

import json
import logging
import shutil

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.job import Job
from app.models.project import Project, utcnow
from app.providers.media import ProviderError
from app.services import storage
from app.services.jobs import next_project_version
from app.services.render import RenderSettings, output_size, probe_duration, render
from app.services.render_plan import plan_render
from app.services.subtitles import to_srt

log = logging.getLogger(__name__)


def run_render(session: Session, job: Job) -> None:
    project = session.get(Project, job.project_id)
    if project is None:
        return
    settings = RenderSettings.from_json(job.prompt)
    job.status = "running"
    job.attempts += 1
    job.error_message = None
    job.progress = 0
    project.status = "rendering"
    session.commit()

    version = next_project_version(session, project.id, "render")
    work_dir = storage.render_dir(project.id, version)

    def on_progress(percent: int) -> None:
        job.progress = min(percent, 99)
        session.commit()

    try:
        plan = plan_render(session, project, settings.include_audio)
        if plan.problems:
            raise ProviderError("렌더링할 수 없습니다: " + " ".join(plan.problems))
        video, srt = render(plan.segments, to_srt(plan.cues), project.aspect_ratio, settings, work_dir, on_progress)
    except Exception as exc:
        if not isinstance(exc, ProviderError):
            log.exception("render job %s failed", job.id)
        shutil.rmtree(work_dir, ignore_errors=True)
        job.status = "failed"
        job.error_message = str(exc)[:1000] or exc.__class__.__name__
        job.finished_at = utcnow()
        project.status = "in_progress"
        session.commit()
        return

    width, height = output_size(project.aspect_ratio)
    meta = {
        "duration_sec": probe_duration(video) or plan.total_duration,
        "width": width,
        "height": height,
        "scene_count": len(plan.segments),
        "include_audio": settings.include_audio,
        "burn_subtitles": settings.burn_subtitles,
    }
    common = dict(project_id=project.id, scene_id=None, job_id=job.id, version=version, provider="ffmpeg",
                  cost_amount=0.0, cost_currency="USD")
    session.add(Asset(asset_type="render", file_path=storage.to_relative(video),
                      metadata_json=json.dumps(meta, ensure_ascii=False), **common))
    session.add(Asset(asset_type="subtitle", file_path=storage.to_relative(srt),
                      metadata_json=json.dumps({"cue_count": len(plan.cues)}), **common))
    job.status = "succeeded"
    job.progress = 100
    job.finished_at = utcnow()
    project.status = "done"
    project.updated_at = utcnow()
    session.commit()
