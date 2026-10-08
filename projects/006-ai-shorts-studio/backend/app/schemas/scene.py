from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_SCENE_SEC = 0.5
MAX_SCENE_SEC = 60.0


class SceneFields(BaseModel):
    dialogue: str = Field(default="", max_length=2000)
    visual_description: str = Field(default="", max_length=2000)
    image_prompt: str = Field(default="", max_length=4000)
    video_prompt: str = Field(default="", max_length=4000)
    duration_sec: float = Field(default=3.0, ge=MIN_SCENE_SEC, le=MAX_SCENE_SEC)


class SceneCreate(SceneFields):
    pass


class SceneUpdate(BaseModel):
    dialogue: str | None = Field(default=None, max_length=2000)
    visual_description: str | None = Field(default=None, max_length=2000)
    image_prompt: str | None = Field(default=None, max_length=4000)
    video_prompt: str | None = Field(default=None, max_length=4000)
    duration_sec: float | None = Field(default=None, ge=MIN_SCENE_SEC, le=MAX_SCENE_SEC)


class SceneReorder(BaseModel):
    scene_ids: list[int]


class SceneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    scene_number: int
    dialogue: str
    visual_description: str
    image_prompt: str
    video_prompt: str
    duration_sec: float
    status: str
    rejection_reason: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_validator("approved_at", "created_at", "updated_at")
    @classmethod
    def _assume_utc(cls, value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo:
            return value
        return value.replace(tzinfo=timezone.utc)
