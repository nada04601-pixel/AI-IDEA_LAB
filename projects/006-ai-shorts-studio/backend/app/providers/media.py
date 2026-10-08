"""이미지·영상 생성 공급자 인터페이스."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class ProviderError(Exception):
    """공급자가 생성에 실패했을 때. 메시지는 사용자에게 그대로 보여준다."""


@dataclass(frozen=True)
class MediaRequest:
    kind: str  # image | video
    prompt: str
    aspect_ratio: str
    duration_sec: float
    scene_number: int
    version: int
    attempt: int
    output_path: Path  # 확장자 없이 받는다. 공급자가 확장자를 붙여 저장한다.
    source_image: Path | None = None


@dataclass(frozen=True)
class MediaResult:
    file_path: Path
    cost_amount: float
    cost_currency: str
    metadata: dict = field(default_factory=dict)


class MediaProvider(Protocol):
    name: str
    kind: str
    is_paid: bool
    currency: str

    def estimate_cost(self, duration_sec: float) -> float:
        """작업 1건의 예상 비용."""
        ...

    def generate(self, req: MediaRequest) -> MediaResult: ...


def frame_size(aspect_ratio: str, long_side: int = 1280) -> tuple[int, int]:
    """화면 비율에 맞는 (가로, 세로) 픽셀. 짝수로 맞춘다 (H.264 요구사항)."""
    w, h = (int(x) for x in aspect_ratio.split(":"))
    if w >= h:
        width, height = long_side, round(long_side * h / w)
    else:
        width, height = round(long_side * w / h), long_side
    return width - width % 2, height - height % 2
