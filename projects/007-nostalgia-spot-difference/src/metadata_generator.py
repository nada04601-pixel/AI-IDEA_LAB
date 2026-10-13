"""한국어 제목·설명·해시태그. 과장 표현 없이, 최근 제목과 겹치지 않게 고른다."""
from __future__ import annotations

import random

TITLE_TEMPLATES = [
    "{topic} 다른 그림 찾기 | {n}개를 찾아보세요",
    "추억의 다른 그림 찾기 · {topic}",
    "그리운 옛날 풍경 · {topic} 다른 그림 {n}개",
    "{topic}, 기억나시나요? 다른 그림 {n}개 찾기",
    "옛날 {short} 풍경 속 다른 그림 {n}개",
    "{topic} 그림에서 달라진 곳 {n}군데",
    "20초 안에 찾아보세요 · {topic} 다른 그림 찾기",
]

LEVEL = {"easy": "쉬움", "normal": "보통", "hard": "어려움"}

DESC_OPENERS = [
    "{topic} 풍경, 기억나시나요?",
    "오늘의 추억 여행지는 '{topic}'입니다.",
    "정겨운 {topic} 그림 두 장을 준비했어요.",
    "그 시절 {topic}의 모습을 그림으로 담았습니다.",
]


def _short(topic: str) -> str:
    return topic.replace("옛날 ", "").replace("동네 ", "")


def build_metadata(topic: dict, puzzle: dict, recent_titles: list[str], rng: random.Random,
                   source: str = "procedural") -> dict:
    t = topic["title"]
    n = puzzle["difference_count"]
    recent = set(recent_titles)
    templates = list(TITLE_TEMPLATES)
    rng.shuffle(templates)
    title = None
    for tpl in templates:
        cand = tpl.format(topic=t, n=n, short=_short(t))
        if cand not in recent:
            title = cand
            break
    if title is None:  # 모든 조합이 최근에 쓰였으면 난이도를 덧붙여 구분
        title = f"{templates[0].format(topic=t, n=n, short=_short(t))} ({LEVEL.get(puzzle['difficulty'], '')})"
    title = title[:95]  # YouTube 제목 100자 제한

    kinds = sorted({d["type"] for d in puzzle["differences"]})
    kind_ko = {"object_added": "생긴 물건", "object_removed": "사라진 물건", "color_changed": "바뀐 색",
               "shape_changed": "바뀐 모양", "pattern_changed": "바뀐 무늬", "direction_changed": "바뀐 방향"}
    lines = [
        rng.choice(DESC_OPENERS).format(topic=t),
        f"위아래 두 그림에서 다른 곳 {n}개를 20초 안에 찾아보세요. (난이도: {LEVEL.get(puzzle['difficulty'], '보통')})",
        "힌트: " + ", ".join(kind_ko[k] for k in kinds),
        "",
        "몇 개나 찾으셨는지 댓글로 알려 주세요.",
        "",
    ]
    if source == "comfyui":
        lines.append("※ 이 영상의 그림은 AI 이미지 생성 도구로 만든 뒤 편집했습니다.")
    else:
        lines.append("※ 이 영상의 그림은 프로그램으로 직접 그린 일러스트입니다.")
    keywords = topic.get("keywords", [])
    tags = ["다른그림찾기", "추억", "옛날풍경", "그리운옛날", t.replace(" ", "")] + [k.replace(" ", "") for k in keywords[:3]]
    seen = set()
    tags = [x for x in tags if not (x in seen or seen.add(x))]
    hashtags = " ".join(f"#{x}" for x in tags[:5]) + " #Shorts"
    lines += ["", hashtags]
    return {"title": title, "description": "\n".join(lines), "tags": tags + ["Shorts", "spot the difference"]}
