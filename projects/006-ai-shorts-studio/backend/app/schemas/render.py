from pydantic import BaseModel


class RenderRequest(BaseModel):
    include_audio: bool = True
    burn_subtitles: bool = True


class FfmpegInfo(BaseModel):
    available: bool
    path: str | None
    version: str | None


class SceneCheckRead(BaseModel):
    id: int
    scene_number: int
    status: str
    duration_sec: float
    visual: str | None
    visual_asset_id: int | None
    audio: str
    audio_asset_id: int | None


class CueRead(BaseModel):
    index: int
    start: float
    end: float
    text: str
    scene_number: int


class RenderCheck(BaseModel):
    ffmpeg: FfmpegInfo
    ready: bool
    problems: list[str]
    audio_problems: list[str]
    total_duration: float
    scenes: list[SceneCheckRead]


class SubtitlesRead(BaseModel):
    cues: list[CueRead]
    srt: str
