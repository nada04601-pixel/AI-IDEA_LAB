"""전체 흐름: 주제 → 원본 → 차이 → 정답 JSON → 검사 → 렌더링 → 영상 검사 → 메타데이터 → (업로드)."""
from __future__ import annotations

import json
import logging
import random
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import Settings, difference_count
from .db import JobDB, now
from .difference_editor import make_raster_differences, make_scene_differences
from .fonts import find_font
from .image_generator import ImageSourceError, generate_base
from .metadata_generator import build_metadata
from .topic_picker import load_topics, pick_topic
from .validator import validate_puzzle, validate_video
from .video_renderer import FFmpegError, Timeline, build_preview, render_video

log = logging.getLogger("pipeline")


def setup_logging(settings: Settings, verbose: bool = False) -> None:
    root = logging.getLogger()
    if any(getattr(h, "_nostalgia", False) for h in root.handlers):
        return
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = RotatingFileHandler(settings.path("logs") / "pipeline.log", maxBytes=2_000_000, backupCount=5,
                             encoding="utf-8")
    fh.setFormatter(fmt)
    fh._nostalgia = True  # type: ignore[attr-defined]
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    sh._nostalgia = True  # type: ignore[attr-defined]
    root.addHandler(fh)
    root.addHandler(sh)
    for noisy in ("PIL", "urllib3", "googleapiclient"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


@dataclass
class JobResult:
    job_id: str
    status: str
    video_path: Path | None = None
    preview_path: Path | None = None
    puzzle_path: Path | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    youtube_id: str | None = None


def _job_id(topic_id: str, seed: int) -> str:
    return f"{datetime.now():%Y%m%d-%H%M%S}-{topic_id}-{seed % 10000:04d}"


def make_one(settings: Settings, db: JobDB, *, topic_id: str | None = None, difficulty: str | None = None,
             source: str | None = None, seed: int | None = None, upload: bool = False,
             keep_frames: bool = False, timeline: Timeline | None = None) -> JobResult:
    difficulty = difficulty or settings.difficulty
    count = difference_count(difficulty)
    source = (source or settings.image_source).lower()
    seed = seed if seed is not None else random.SystemRandom().randint(1, 10**9)
    rng = random.Random(seed)

    topics = load_topics(settings.path("topics"))
    topic = pick_topic(topics, db.recent_topic_ids(), db.topic_use_counts(), rng, topic_id)
    job_id = _job_id(topic["id"], seed)
    while db.get_job(job_id):
        job_id += "b"
    db.create_job(job_id, topic_id=topic["id"], topic=topic["title"], difficulty=difficulty, source=source, seed=seed)
    log.info("[%s] 시작: 주제=%s 난이도=%s(%d개) 원본=%s seed=%d", job_id, topic["title"], difficulty, count, source, seed)
    res = JobResult(job_id, "created")

    def fail(msg: str) -> JobResult:
        log.error("[%s] 실패: %s", job_id, msg)
        res.status = "failed"
        res.errors.append(msg)
        db.update_job(job_id, status="failed", error=msg)
        return res

    try:
        font = find_font(settings.font_path, str(settings.path("fonts")))
    except FileNotFoundError as e:
        return fail(str(e))

    img_dir = settings.path("images")
    orig_path, mod_path = img_dir / f"{job_id}_original.png", img_dir / f"{job_id}_modified.png"
    puzzle_path = settings.path("puzzles") / f"{job_id}.json"
    puzzle: dict | None = None
    check = None
    base_meta: dict = {}

    # 원본 생성 + 차이 만들기 + 정답 검사. 실패하면 seed를 바꿔 제한 횟수만큼 재시도
    for attempt in range(1, settings.max_retries + 1):
        db.update_job(job_id, attempts=attempt)
        attempt_seed = seed + (attempt - 1) * 7919
        arng = random.Random(attempt_seed)
        try:
            base = generate_base(settings, topic, attempt_seed, font, source)
            base_meta = base.meta
            if base.is_scene:
                original, modified, diffs, _ = make_scene_differences(base.scene, count, arng)
            else:
                inpainter = None
                if source == "comfyui" and settings.comfyui_inpaint:
                    from .image_generator import ComfyUIClient
                    inpainter = ComfyUIClient(settings).inpaint
                original, modified, diffs = make_raster_differences(base.image, count, arng, font, inpainter)
        except (ImageSourceError, RuntimeError) as e:
            log.warning("[%s] 시도 %d 실패: %s", job_id, attempt, e)
            if attempt == settings.max_retries:
                return fail(f"원본/차이 생성 실패: {e}")
            time.sleep(1 if source == "comfyui" else 0)
            continue

        original.save(orig_path)
        modified.save(mod_path)
        w, h = original.size
        puzzle = {
            "job_id": job_id,
            "topic": topic["title"],
            "topic_id": topic["id"],
            "difficulty": difficulty,
            "difference_count": count,
            "differences": [d.to_json(w, h) for d in diffs],
            "image_size": [w, h],
            "original_image": orig_path.name,
            "modified_image": mod_path.name,
            "source": source,
            "source_meta": base_meta,
            "seed": attempt_seed,
            "created_at": now(),
        }
        if source != "procedural":
            puzzle["needs_human_review"] = True  # 래스터 편집은 의미 있는 물체를 골랐는지 사람이 확인
        puzzle_path.write_text(json.dumps(puzzle, ensure_ascii=False, indent=2), encoding="utf-8")
        check = validate_puzzle(puzzle, orig_path, mod_path)
        if check.ok and (not check.warnings or attempt == settings.max_retries):
            break
        if check.ok:  # 경고만 있으면 다른 seed로 한 번 더 시도해 더 깔끔한 문제를 고른다
            log.info("[%s] 시도 %d 검수 경고, 다시 생성: %s", job_id, attempt, "; ".join(check.warnings))
            continue
        log.warning("[%s] 시도 %d 정답 검사 실패: %s", job_id, attempt, "; ".join(check.errors))
        if attempt == settings.max_retries:
            db.update_job(job_id, puzzle_path=str(puzzle_path))
            return fail("정답 검사 실패: " + "; ".join(check.errors))

    assert puzzle is not None and check is not None
    res.puzzle_path = puzzle_path
    res.warnings += check.warnings
    if puzzle.get("needs_human_review"):
        res.warnings.append("AI/샘플 이미지 기반 차이 — 사람이 정답을 확인해야 합니다")
    db.update_job(job_id, status="validated", puzzle_path=str(puzzle_path))

    # 정답 미리보기 + 영상 렌더링
    preview = build_preview(puzzle, orig_path, mod_path, settings.path("previews") / f"{job_id}_answer.png", font)
    res.preview_path = preview
    work = settings.root / "output" / "work" / job_id
    video_path = settings.path("videos") / f"{job_id}.mp4"
    tl = timeline or Timeline()
    try:
        render_video(puzzle, orig_path, mod_path, work, video_path, font, seed,
                     music_dir=settings.path("music"), music_volume=settings.music_volume, tl=tl)
    except (FFmpegError, OSError, ValueError) as e:
        return fail(f"렌더링 실패: {e}")
    finally:
        if not keep_frames:
            shutil.rmtree(work, ignore_errors=True)
    vcheck = validate_video(video_path, tl.total)
    if not vcheck.ok:
        db.update_job(job_id, video_path=str(video_path))
        return fail("영상 검사 실패: " + "; ".join(vcheck.errors))
    res.warnings += vcheck.warnings
    res.video_path = video_path

    from .youtube_uploader import sha256_of
    meta = build_metadata(topic, puzzle, db.recent_titles(), rng, source)
    status = "needs_review" if res.warnings else "ready"
    db.update_job(job_id, status=status, video_path=str(video_path), video_sha256=sha256_of(video_path),
                  duration=vcheck.metrics.get("duration"), title=meta["title"], description=meta["description"],
                  tags=meta["tags"], review_flags=res.warnings or None)
    (settings.path("videos") / f"{job_id}.txt").write_text(
        f"{meta['title']}\n\n{meta['description']}\n", encoding="utf-8")
    res.status = status
    log.info("[%s] 완료: %s → %s", job_id, status, video_path)
    for w_ in res.warnings:
        log.warning("[%s] 검수 필요: %s", job_id, w_)

    if upload:
        res.youtube_id = try_upload(settings, db, job_id)
        if res.youtube_id:
            res.status = "uploaded"
    return res


def try_upload(settings: Settings, db: JobDB, job_id: str, force_review: bool = False) -> str | None:
    """업로드를 시도한다. 꺼져 있거나 검수 대상이면 건너뛰고 이유를 로그에 남긴다."""
    from .youtube_uploader import UploadError, UploadSkipped, upload_video
    if not settings.upload_enabled:
        log.info("[%s] 업로드 꺼짐 (UPLOAD_ENABLED=false) — 영상만 저장했습니다", job_id)
        return None
    job = db.get_job(job_id)
    if not job:
        log.error("작업을 찾을 수 없습니다: %s", job_id)
        return None
    try:
        vid = upload_video(settings, db, job, force_review=force_review)
    except UploadSkipped as e:
        log.info("[%s] 업로드 건너뜀: %s", job_id, e)
        return None
    except UploadError as e:
        log.error("[%s] 업로드 실패: %s", job_id, e)
        db.update_job(job_id, error=f"upload: {e}")
        return None
    db.update_job(job_id, status="uploaded")
    return vid
