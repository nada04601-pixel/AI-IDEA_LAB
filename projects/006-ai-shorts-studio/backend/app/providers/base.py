"""대본·스토리보드 생성 공급자 인터페이스.

실제 AI 공급자는 이 인터페이스를 구현하는 어댑터로 추가한다.
유료 공급자는 사용자 승인과 비용 표시가 갖춰진 뒤(3단계)에만 연결한다.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ScriptRequest:
    title: str
    topic: str
    target_duration_sec: int
    aspect_ratio: str
    visual_style: str


@dataclass(frozen=True)
class SceneDraft:
    dialogue: str
    visual_description: str
    image_prompt: str
    video_prompt: str
    duration_sec: float


class ScriptProvider(Protocol):
    name: str
    is_paid: bool

    def generate_script(self, req: ScriptRequest) -> str:
        """주제와 설정으로 대본 초안을 만든다. 장면 구분은 빈 줄로 한다."""
        ...

    def generate_storyboard(self, script: str, req: ScriptRequest) -> list[SceneDraft]:
        """대본을 장면 목록으로 나눈다."""
        ...
