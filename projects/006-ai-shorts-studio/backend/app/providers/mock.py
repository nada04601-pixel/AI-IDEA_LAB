"""외부 API 없이 동작하는 mock 공급자. 같은 입력에는 항상 같은 결과를 낸다."""

import re

from app.providers.base import SceneDraft, ScriptRequest

MAX_SCENES = 30
MIN_SCENE_SEC = 0.5


def scene_count_for(duration_sec: int) -> int:
    """목표 길이에 맞는 장면 수 (대략 장면당 6~7초, 3~8개)."""
    return max(3, min(8, round(duration_sec / 7)))


def split_paragraphs(script: str) -> list[str]:
    """빈 줄을 기준으로 장면 문단을 나눈다."""
    parts = [p.strip() for p in re.split(r"\n\s*\n", script.replace("\r\n", "\n"))]
    return [p for p in parts if p]


def distribute_duration(lengths: list[int], total_sec: float) -> list[float]:
    """글자 수에 비례해 전체 길이를 나눈다. 0.5초 단위, 장면당 최소 0.5초, 합계는 total_sec."""
    n = len(lengths)
    if n == 0:
        return []
    units = max(int(round(total_sec / MIN_SCENE_SEC)), n)  # 0.5초 단위 개수
    weights = [max(length, 1) for length in lengths]
    spare = units - n  # 최소 1단위씩 준 뒤 남는 단위
    raw = [spare * w / sum(weights) for w in weights]
    alloc = [int(r) for r in raw]
    # 최대 나머지 방식으로 남은 단위를 배분한다 (동률이면 앞 장면 우선)
    order = sorted(range(n), key=lambda i: (-(raw[i] - alloc[i]), i))
    for i in order[: spare - sum(alloc)]:
        alloc[i] += 1
    return [(a + 1) * MIN_SCENE_SEC for a in alloc]


def _summary(text: str, limit: int = 40) -> str:
    """프롬프트용 한 줄 요약. mock 표시와 줄바꿈을 빼고 길면 자른다."""
    one_line = " ".join(text.removeprefix("[mock]").split())
    return one_line if len(one_line) <= limit else one_line[:limit] + "…"


class MockScriptProvider:
    name = "mock"
    is_paid = False

    def generate_script(self, req: ScriptRequest) -> str:
        topic = req.topic.strip() or req.title.strip()
        n = scene_count_for(req.target_duration_sec)
        paragraphs = [f"[mock] 잠깐! {topic}, 알고 계셨나요?"]
        for i in range(1, n - 1):
            paragraphs.append(f"[mock] 포인트 {i}. {topic}에 대해 꼭 알아야 할 내용을 한 문장으로 설명합니다.")
        paragraphs.append("[mock] 도움이 됐다면 저장하고, 다음 쇼츠도 확인하세요!")
        return "\n\n".join(paragraphs)

    def generate_storyboard(self, script: str, req: ScriptRequest) -> list[SceneDraft]:
        paragraphs = split_paragraphs(script)[:MAX_SCENES]
        durations = distribute_duration([len(p) for p in paragraphs], req.target_duration_sec)
        style = req.visual_style.strip() or "깔끔한 실사 스타일"
        drafts = []
        orientation = {"9:16": "vertical", "16:9": "horizontal", "1:1": "square"}.get(req.aspect_ratio, "vertical")
        for text, sec in zip(paragraphs, durations):
            summary = _summary(text)
            drafts.append(
                SceneDraft(
                    dialogue=text,
                    visual_description=f"[mock] '{summary}' 내용을 보여주는 화면",
                    image_prompt=f"{style}, {summary}, {req.aspect_ratio} {orientation} composition",
                    video_prompt=f"{style}, {summary}, slow camera push-in",
                    duration_sec=sec,
                )
            )
        return drafts
