import json
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


def _utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo:
        return value
    return value.replace(tzinfo=timezone.utc)


class GenerateRequest(BaseModel):
    confirm_paid: bool = False  # 유료 공급자일 때 사용자가 비용을 확인했다는 표시


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    scene_id: int | None
    job_type: str
    status: str
    progress: int
    provider: str
    prompt: str
    estimated_cost: float | None
    cost_currency: str | None
    attempts: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None

    @field_validator("created_at", "updated_at", "finished_at")
    @classmethod
    def _assume_utc(cls, value: datetime | None) -> datetime | None:
        return _utc(value)


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    scene_id: int | None
    job_id: int | None
    asset_type: str
    version: int
    provider: str | None
    status: str
    cost_amount: float | None
    cost_currency: str | None
    metadata: dict = Field(validation_alias="metadata_json")
    created_at: datetime

    @field_validator("metadata", mode="before")
    @classmethod
    def _parse_metadata(cls, value):
        return json.loads(value) if isinstance(value, str) else value

    @field_validator("created_at")
    @classmethod
    def _assume_utc(cls, value: datetime) -> datetime:
        return _utc(value)

    @computed_field
    @property
    def url(self) -> str:
        return f"/api/assets/{self.id}/file"


class ProviderInfo(BaseModel):
    kind: str
    name: str
    is_paid: bool
    estimated_cost_per_job: float
    currency: str
