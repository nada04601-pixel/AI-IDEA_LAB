"""작업 파일 형식 (기획서 6장). 모듈끼리는 이 형식의 파일로만 주고받는다."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Section = Literal["hook", "problem", "demo", "benefit", "cta"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- script.json -------------------------------------------------------------


class Product(_Model):
    name: str = Field(min_length=1)
    features: list[str] = Field(default_factory=list)
    price_hint: str | None = None


class Sentence(_Model):
    id: str = Field(min_length=1)
    section: Section
    text: str = Field(min_length=1)
    emphasis: list[str] = Field(default_factory=list)
    sfx: str | None = None
    scene_hint: str | None = None

    @model_validator(mode="after")
    def _emphasis_in_text(self) -> "Sentence":
        missing = [w for w in self.emphasis if w not in self.text]
        if missing:
            raise ValueError(f"{self.id}: 강조어 {missing}가 문장에 없습니다.")
        return self


class ThumbnailText(_Model):
    top: str = Field(min_length=1)
    bottom: str = Field(min_length=1)


class Script(_Model):
    version: Literal[1] = 1
    preset: str
    target_duration_sec: int
    product: Product
    sentences: list[Sentence] = Field(min_length=2)
    thumbnail_text: ThumbnailText

    @model_validator(mode="after")
    def _structure(self) -> "Script":
        ids = [s.id for s in self.sentences]
        if len(ids) != len(set(ids)):
            raise ValueError("문장 id가 중복되었습니다.")
        if self.sentences[0].section != "hook":
            raise ValueError("첫 문장은 hook 구간이어야 합니다.")
        if self.sentences[-1].section != "cta":
            raise ValueError("마지막 문장은 cta 구간이어야 합니다.")
        return self


# ---- workspace/{id}/project.yaml --------------------------------------------


class Source(_Model):
    type: Literal["url", "keyword", "local"]
    value: str | None = None
    files: list[str] = Field(default_factory=list)


class ProjectFile(_Model):
    id: str
    created_at: datetime
    source: Source
    overrides: dict = Field(default_factory=dict)
