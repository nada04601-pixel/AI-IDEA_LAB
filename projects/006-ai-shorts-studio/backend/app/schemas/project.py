from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AspectRatio = Literal["9:16", "16:9", "1:1"]
ProjectStatus = Literal["draft", "in_progress", "rendering", "done"]


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    topic: str = Field(default="", max_length=2000)
    target_duration_sec: int = Field(default=30, ge=5, le=180)
    aspect_ratio: AspectRatio = "9:16"
    visual_style: str = Field(default="", max_length=200)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    topic: str | None = Field(default=None, max_length=2000)
    target_duration_sec: int | None = Field(default=None, ge=5, le=180)
    aspect_ratio: AspectRatio | None = None
    visual_style: str | None = Field(default=None, max_length=200)
    status: ProjectStatus | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    topic: str
    target_duration_sec: int
    aspect_ratio: str
    visual_style: str
    status: str
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def _assume_utc(cls, value: datetime) -> datetime:
        # SQLite는 시간대를 저장하지 않으므로 UTC로 저장한 값임을 응답에 명시한다.
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
