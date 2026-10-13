"""주제 선택. 최근에 쓴 주제를 피하고, 덜 쓴 주제를 우선한다."""
from __future__ import annotations

import json
import random
from pathlib import Path


def load_topics(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    topics = data["topics"] if isinstance(data, dict) else data
    if not topics:
        raise ValueError(f"주제 목록이 비어 있습니다: {path}")
    ids = [t["id"] for t in topics]
    if len(ids) != len(set(ids)):
        raise ValueError("topics.json에 중복된 id가 있습니다")
    return topics


def pick_topic(topics: list[dict], recent_ids: list[str], use_counts: dict[str, int],
               rng: random.Random, topic_id: str | None = None) -> dict:
    if topic_id:
        for t in topics:
            if t["id"] == topic_id or t["title"] == topic_id:
                return t
        raise ValueError(f"주제를 찾을 수 없습니다: {topic_id}")

    # 최근 사용한 주제(목록 절반 이내)와 바로 직전 시리즈는 제외
    window = max(1, len(topics) // 2)
    blocked = set(recent_ids[:window])
    last_series = None
    if recent_ids:
        last = next((t for t in topics if t["id"] == recent_ids[0]), None)
        last_series = last.get("series") if last else None
    candidates = [t for t in topics if t["id"] not in blocked and t.get("series") != last_series]
    if not candidates:
        candidates = [t for t in topics if t["id"] not in blocked] or list(topics)

    least = min(use_counts.get(t["id"], 0) for t in candidates)
    candidates = [t for t in candidates if use_counts.get(t["id"], 0) == least]
    return rng.choice(candidates)
