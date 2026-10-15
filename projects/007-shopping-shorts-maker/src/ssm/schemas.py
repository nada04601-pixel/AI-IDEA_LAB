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


# ---- word_timings.json (tts 단계 결과) -----------------------------------------
# 시간은 모두 tts.mp3 처음부터의 초 단위.


class Word(_Model):
    text: str
    start: float
    end: float


class SentenceTiming(_Model):
    id: str
    section: Section = "demo"
    text: str
    emphasis: list[str] = Field(default_factory=list)
    sfx: str | None = None
    start: float  # 이 문장 음성 구간 (앞뒤 무음 포함)
    end: float
    words: list[Word] = Field(default_factory=list)  # TTS 엔진이 알려준 단어 경계 (문장부호 제외)


class WordTimings(_Model):
    version: Literal[1] = 1
    provider: str
    voice: str
    rate: str
    duration: float
    sentences: list[SentenceTiming]


Grade = Literal["same_product", "mood"]


# ---- candidates.json · selected.json (collect 단계 결과) ---------------------------


class Candidate(_Model):
    id: str  # c01, c02 … (c01이 기준 영상)
    url: str | None = None
    platform: str = "other"  # xiaohongshu | douyin | tiktok | local | other
    reference: bool = False  # 사용자가 준 기준 영상
    file: str | None = None  # 프로젝트 폴더 기준 내려받은 파일 (candidates/c01.mp4)
    title: str = ""
    description: str = ""
    author: str = ""
    location: str = ""  # 작성자 IP 표시 지역 등
    similarity: float | None = None  # 기준 영상과의 CLIP 유사도 (검사 못 하면 None)
    grade: Grade | Literal["excluded"] | None = None
    reasons: list[str] = Field(default_factory=list)  # 제외 사유
    notes: list[str] = Field(default_factory=list)  # 검사하지 못한 항목 등 참고 사항
    error: str | None = None  # 내려받기 실패


class Candidates(_Model):
    version: Literal[1] = 1
    source: str | None = None
    keyword: str | None = None
    candidates: list[Candidate]


class SelectedVideo(_Model):
    file: str  # raw_videos/01.mp4
    candidate: str  # candidates.json의 id
    grade: Grade
    similarity: float | None = None
    url: str | None = None


class Selected(_Model):
    version: Literal[1] = 1
    videos: list[SelectedVideo]


# ---- overrides.json (사용자 수정: 컷 교체) -----------------------------------------


class CutOverride(_Model):
    position: float  # 바꿀 컷이 시작하는 시각 (초)
    was: str  # 원래 배치된 장면 (shot id) — 대본·영상이 바뀌어 컷 배치가 달라지면 적용하지 않는다
    shot: str  # 대신 쓸 장면


class Overrides(_Model):
    version: Literal[1] = 1
    cuts: list[CutOverride] = Field(default_factory=list)


# ---- analysis.json (analyze 단계 결과) ------------------------------------------
# 좌표는 원본 영상 화면(회전 반영) 기준 픽셀, 시간은 원본 영상 기준 초.


class Shot(_Model):
    id: str  # 예: 01-003 (영상 01의 세 번째 샷)
    start: float
    end: float
    score: float = Field(ge=0.0, le=1.0)  # 하이라이트 점수 (모든 영상의 샷끼리 비교한 상대값)
    sharpness: float = 0.0
    motion: float = 0.0
    brightness: float = 0.0

    @property
    def duration(self) -> float:
        return self.end - self.start


class TextBox(_Model):
    """여러 프레임에 반복해서 나온 글자 영역 (자막·워터마크). 이 영역을 가린다."""
    x: int
    y: int
    w: int
    h: int
    coverage: float = Field(ge=0.0, le=1.0)  # 검사한 프레임 중 글자가 보인 비율


class VideoAnalysis(_Model):
    file: str  # 프로젝트 폴더 기준 경로 (예: raw_videos/01.mp4)
    width: int
    height: int
    duration: float
    grade: Grade = "same_product"  # mood면 hook·problem 구간에만 쓴다
    shots: list[Shot]
    text_boxes: list[TextBox] = Field(default_factory=list)
    ocr: Literal["ok", "unavailable"] = "ok"


class Analysis(_Model):
    version: Literal[1] = 1
    videos: list[VideoAnalysis] = Field(min_length=1)


# ---- timeline.json (edit 단계 결과) ---------------------------------------------


class Cut(_Model):
    source: str  # 프로젝트 폴더 기준 원본 영상 경로 (예: raw_videos/01.mp4)
    start: float  # 원본 영상 안에서의 구간 (초)
    end: float
    position: float = 0.0  # 최종 영상에서 이 컷이 시작하는 시각 (초)
    speed: float = Field(1.0, ge=0.5, le=2.0)  # 1보다 작으면 느리게 재생해 길이를 채운다
    shot_id: str | None = None
    section: Section | None = None

    @property
    def duration(self) -> float:
        """원본에서 가져오는 길이."""
        return self.end - self.start

    @property
    def length(self) -> float:
        """최종 영상에서 차지하는 길이."""
        return self.duration / self.speed


class Timeline(_Model):
    version: Literal[1] = 1
    duration: float  # 최종 영상 길이 (초)
    cuts: list[Cut] = Field(min_length=1)


# ---- meta.json (Claude 작성: 제목·썸네일 문구·캡션 요약·해시태그) ---------------------------

CATEGORIES = ("kitchen", "living", "travel", "beauty", "digital", "general")


class MetaText(_Model):
    version: Literal[1] = 1
    category: Literal["kitchen", "living", "travel", "beauty", "digital", "general"] = "general"
    titles: list[str] = Field(default_factory=list, max_length=3)  # 쇼츠 제목 후보 ([광고] 포함 100자 이내)
    thumbnail_texts: list[ThumbnailText] = Field(default_factory=list, max_length=3)  # 썸네일 문구 3안
    summary: list[str] = Field(default_factory=list, max_length=3)  # 캡션 상품 요약 2~3줄
    hashtags: list[str] = Field(default_factory=list, max_length=10)  # 상품에 맞춘 해시태그 ('#' 없어도 됨)


# ---- thumbnail_style.json (레퍼런스 썸네일 스타일) -----------------------------------


class ThumbnailStyle(_Model):
    version: Literal[1] = 1
    source: str
    palette: list[str] = Field(default_factory=list)  # 많이 쓰인 색 (#RRGGBB)
    top_color: str | None = None
    bottom_color: str | None = None
    stroke_color: str | None = None
    stroke_width: int | None = None
    top_size: int | None = None
    bottom_size: int | None = None
    position_y_ratio: float | None = None
    gradient: bool | None = None
    notes: list[str] = Field(default_factory=list)


# ---- reference_style.json (레퍼런스 화법 분석) -------------------------------------


class StyleProfile(_Model):
    version: Literal[1] = 1
    source: str  # 링크·파일 경로
    transcript: str
    sentence_count: int
    avg_syllables: float  # 문장 하나의 평균 음절 수
    max_syllables: int
    syllables_per_sec: float | None = None  # 말 속도 (영상에서 받아 적었을 때만)
    question_ratio: float  # 물음표로 끝나는 문장 비율
    endings: list[tuple[str, int]] = Field(default_factory=list)  # 자주 쓰는 어미 (끝 두 글자)와 횟수
    hook: str = ""  # 첫 문장


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
