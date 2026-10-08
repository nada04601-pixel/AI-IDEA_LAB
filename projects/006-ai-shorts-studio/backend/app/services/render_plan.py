"""렌더링 전 점검: 장면마다 무엇으로 영상을 만들지, 무엇이 빠졌는지 정리한다."""

import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.project import Project
from app.models.scene import Scene
from app.providers.mock_tts import text_hash
from app.services import storage
from app.services.jobs import latest_asset
from app.services.render import SegmentInput
from app.services.subtitles import Cue, build_cues


def audio_status(session: Session, scene: Scene) -> tuple[str, int | None]:
    """(상태, 음성 자산 id). 상태: no_text(대사 없음) | none | stale(대사가 바뀜) | ready"""
    if not scene.dialogue.strip():
        return "no_text", None
    audio = latest_asset(session, scene.id, "audio")
    if audio is None:
        return "none", None
    meta = json.loads(audio.metadata_json or "{}")
    return ("ready" if meta.get("text_hash") == text_hash(scene.dialogue) else "stale"), audio.id


@dataclass
class SceneCheck:
    id: int
    scene_number: int
    status: str
    duration_sec: float
    visual: str | None  # video | image | None
    visual_asset_id: int | None
    audio: str
    audio_asset_id: int | None


@dataclass
class RenderPlan:
    scenes: list[SceneCheck]
    cues: list[Cue]
    problems: list[str] = field(default_factory=list)
    audio_problems: list[str] = field(default_factory=list)
    segments: list[SegmentInput] = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        return round(sum(s.duration_sec for s in self.scenes), 3)


def plan_render(session: Session, project: Project, include_audio: bool = True) -> RenderPlan:
    scenes = sorted(project.scenes, key=lambda s: s.scene_number)
    plan = RenderPlan(scenes=[], cues=build_cues([(s.scene_number, s.dialogue, s.duration_sec) for s in scenes]))
    if not scenes:
        plan.problems.append("장면이 없습니다. 스토리보드에서 장면을 만드세요.")

    for scene in scenes:
        video = latest_asset(session, scene.id, "video")
        image = latest_asset(session, scene.id, "image")
        visual = video or image
        a_status, a_id = audio_status(session, scene)
        plan.scenes.append(
            SceneCheck(scene.id, scene.scene_number, scene.status, scene.duration_sec,
                       visual.asset_type if visual else None, visual.id if visual else None, a_status, a_id)
        )
        if scene.status != "approved":
            plan.problems.append(f"장면 {scene.scene_number}이(가) 아직 승인되지 않았습니다.")
        if visual is None:
            plan.problems.append(f"장면 {scene.scene_number}에 이미지나 영상이 없습니다.")
        if a_status == "none":
            plan.audio_problems.append(f"장면 {scene.scene_number}의 음성이 없습니다.")
        elif a_status == "stale":
            plan.audio_problems.append(f"장면 {scene.scene_number}의 대사가 바뀌어 음성을 다시 만들어야 합니다.")

        visual_path = storage.resolve(visual.file_path) if visual else None
        if visual is not None and (visual_path is None or not visual_path.is_file()):
            plan.problems.append(f"장면 {scene.scene_number}의 {visual.asset_type} 파일을 찾을 수 없습니다.")
            visual_path = None
        audio_path = None
        if a_status == "ready":
            audio_asset = session.get(Asset, a_id)
            audio_path = storage.resolve(audio_asset.file_path) if audio_asset else None
        if visual_path is not None:
            plan.segments.append(SegmentInput(scene.scene_number, scene.duration_sec, visual_path, visual.asset_type, audio_path))

    if include_audio:
        plan.problems.extend(plan.audio_problems)
    return plan
