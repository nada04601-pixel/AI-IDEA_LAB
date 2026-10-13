"""그리운 옛날 풍경 · 다른 그림 찾기 Shorts — 명령줄 진입점.

  python main.py doctor                 환경 점검 (Python, FFmpeg, 한글 글꼴, GPU, ComfyUI)
  python main.py make                   영상 1개 만들기 (업로드는 설정이 켜져 있을 때만)
  python main.py batch --count 10       안정성 점검: 여러 개 만들고 결과 요약
  python main.py daily                  예약 실행용: DAILY_COUNT개 만들고, 켜져 있으면 비공개 업로드
  python main.py jobs                   최근 작업 목록
  python main.py approve JOB_ID         검수 대상 작업을 사람이 확인했다고 표시
  python main.py auth                   YouTube OAuth 로그인 (처음 한 번)
  python main.py upload JOB_ID          작업 하나 업로드 (비공개 기본)
  python main.py status                 업로드 상태·조회수 갱신
  python main.py export                 작업·성과 기록을 CSV로 내보내기
  python main.py comfyui-test           ComfyUI 원본 생성·인페인팅을 1번씩 시험
"""
from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys

from src.config import DIFFICULTY_COUNTS, load_settings
from src.db import JobDB


def _console_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass


def cmd_doctor(settings, args) -> int:
    from src.fonts import find_font
    from src.image_generator import ComfyUIClient
    ok = True
    print(f"운영체제      : {platform.system()} {platform.release()} ({platform.machine()})")
    py = sys.version_info
    print(f"Python        : {platform.python_version()}" + ("" if py >= (3, 10) else "  ← 3.10 이상 필요"))
    ok &= py >= (3, 10)
    for exe in ("ffmpeg", "ffprobe"):
        path = shutil.which(exe)
        print(f"{exe:<14}: {path or '없음 ← 설치 필요 (README 참고)'}")
        ok &= bool(path)
    try:
        print(f"한글 글꼴     : {find_font(settings.font_path, str(settings.path('fonts')))}")
    except FileNotFoundError as e:
        print(f"한글 글꼴     : 없음 ← {e}")
        ok = False
    gpu = "확인 불가 (nvidia-smi 없음)"
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                                 capture_output=True, text=True, timeout=10).stdout.strip()
            gpu = out or gpu
        except Exception:  # noqa: BLE001
            pass
    elif platform.system() == "Darwin":
        gpu = "Apple Silicon/Mac — ComfyUI는 MPS로 동작 가능(느릴 수 있음)"
    print(f"GPU           : {gpu}")
    print(f"이미지 원본   : {settings.image_source}")
    if settings.image_source == "comfyui":
        client = ComfyUIClient(settings)
        alive = client.ping()
        print(f"ComfyUI       : {settings.comfyui_url} {'연결됨' if alive else '연결 안 됨 ← ComfyUI 실행 필요'}")
        if alive:
            for dev in client.system_info().get("devices", []):
                vram = dev.get("vram_total", 0) / 1024**3
                print(f"  장치        : {dev.get('name')} ({vram:.1f}GB)")
        print(f"  모델        : {settings.comfyui_checkpoint} / 인페인팅: "
              f"{'켜짐' if settings.comfyui_inpaint else '꺼짐'}")
        ok &= alive
    print(f"업로드        : {'켜짐' if settings.upload_enabled else '꺼짐'} (공개 상태: {settings.upload_privacy}, "
          f"공개 허용: {settings.allow_public_upload})")
    if settings.upload_enabled:
        try:
            import googleapiclient  # noqa: F401
            print("YouTube 패키지: 설치됨")
        except ImportError:
            print("YouTube 패키지: 없음 ← pip install -r requirements-youtube.txt")
            ok = False
    print("\n결과: " + ("준비 완료" if ok else "위 ← 표시 항목을 해결하세요"))
    return 0 if ok else 1


def _print_result(r) -> None:
    print(f"\n작업 {r.job_id}: {r.status}")
    if r.video_path:
        print(f"  영상      : {r.video_path}")
    if r.preview_path:
        print(f"  정답 미리보기: {r.preview_path}")
    if r.puzzle_path:
        print(f"  정답 JSON : {r.puzzle_path}")
    if r.youtube_id:
        print(f"  YouTube   : https://youtu.be/{r.youtube_id} (비공개 여부는 status로 확인)")
    for e in r.errors:
        print(f"  [실패] {e}")
    for w in r.warnings:
        print(f"  [검수] {w}")


def cmd_make(settings, args) -> int:
    from src.pipeline import make_one
    db = JobDB(settings.path("db"))
    r = make_one(settings, db, topic_id=args.topic, difficulty=args.difficulty, source=args.source,
                 seed=args.seed, upload=args.upload or settings.upload_enabled, keep_frames=args.keep_frames)
    _print_result(r)
    return 0 if r.status != "failed" else 1


def cmd_batch(settings, args) -> int:
    from src.pipeline import make_one
    db = JobDB(settings.path("db"))
    results = []
    for i in range(args.count):
        print(f"\n=== {i + 1}/{args.count} ===")
        results.append(make_one(settings, db, difficulty=args.difficulty, source=args.source, upload=False))
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    print("\n요약:", ", ".join(f"{k} {v}개" for k, v in counts.items()))
    for r in results:
        line = f"  {r.job_id}: {r.status}"
        if r.errors or r.warnings:
            line += " — " + "; ".join(r.errors + r.warnings)
        print(line)
    print(f"로그: {settings.path('logs') / 'pipeline.log'}")
    return 0 if counts.get("failed", 0) == 0 else 1


def cmd_daily(settings, args) -> int:
    from src.pipeline import make_one
    db = JobDB(settings.path("db"))
    n = args.count or settings.daily_count
    failed = 0
    for _ in range(n):
        r = make_one(settings, db, upload=settings.upload_enabled)
        _print_result(r)
        failed += r.status == "failed"
    return 1 if failed else 0


def cmd_jobs(settings, args) -> int:
    db = JobDB(settings.path("db"))
    for j in db.list_jobs(args.limit):
        up = db.find_upload(j["job_id"])
        extra = f" youtube={up['youtube_id']}({up['privacy']})" if up else ""
        print(f"{j['job_id']}  {j['status']:<12} {j['topic']:<10} {j['difficulty']:<6} {j['title'] or ''}{extra}")
    return 0


def cmd_approve(settings, args) -> int:
    db = JobDB(settings.path("db"))
    job = db.get_job(args.job_id)
    if not job:
        print("작업을 찾을 수 없습니다")
        return 1
    if job["status"] != "needs_review":
        print(f"검수 대상이 아닙니다 (현재 상태: {job['status']})")
        return 1
    db.update_job(args.job_id, status="ready")
    print(f"{args.job_id} → ready (사람 확인 완료)")
    return 0


def cmd_auth(settings, args) -> int:
    from src.youtube_uploader import get_service
    get_service(settings, interactive=True)
    print(f"인증 완료. 토큰 저장: {settings.resolve(settings.youtube_token)} (Git에 올리지 마세요)")
    return 0


def cmd_upload(settings, args) -> int:
    from src.pipeline import setup_logging, try_upload
    setup_logging(settings)
    if not settings.upload_enabled:
        print("업로드가 꺼져 있습니다. .env에서 UPLOAD_ENABLED=true 로 바꾼 뒤 다시 실행하세요.")
        return 1
    db = JobDB(settings.path("db"))
    vid = try_upload(settings, db, args.job_id, force_review=args.force_review)
    print(f"video ID: {vid}" if vid else "업로드하지 않았습니다 (로그 참고)")
    return 0 if vid else 1


def cmd_status(settings, args) -> int:
    from src.youtube_uploader import refresh_status
    db = JobDB(settings.path("db"))
    for r in refresh_status(settings, db):
        print(r)
    return 0


def cmd_comfyui_test(settings, args) -> int:
    """ComfyUI로 원본 1장 + 인페인팅 1번을 실제로 돌려 보고 시간을 잰다."""
    import random
    import time
    from PIL import Image, ImageDraw
    from src.image_generator import ComfyUIClient, fit_canvas
    from src.topic_picker import load_topics
    client = ComfyUIClient(settings)
    if not client.ping():
        print(f"ComfyUI 서버에 연결할 수 없습니다: {settings.comfyui_url}")
        return 1
    topics = load_topics(settings.path("topics"))
    topic = next((t for t in topics if t["id"] == args.topic), topics[0])
    seed = args.seed or random.randint(1, 10**9)
    out = settings.path("images")
    t0 = time.time()
    img = fit_canvas(client.generate(topic, seed))
    img.save(out / "comfyui_test_base.png")
    print(f"원본 생성 {time.time() - t0:.1f}초 → {out / 'comfyui_test_base.png'}")
    if settings.comfyui_inpaint:
        w, h = img.size
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).ellipse([w * 0.4, h * 0.6, w * 0.6, h * 0.9], fill=255)
        t1 = time.time()
        painted = client.inpaint(img, mask, "a single brown onggi earthenware jar", seed + 1)
        Image.composite(painted, img, mask).save(out / "comfyui_test_inpaint.png")
        print(f"인페인팅 {time.time() - t1:.1f}초 → {out / 'comfyui_test_inpaint.png'} (아래 가운데에 장독이 생겼는지 확인)")
    return 0


def cmd_export(settings, args) -> int:
    db = JobDB(settings.path("db"))
    out = settings.root / args.out
    n = db.export_csv(out)
    print(f"{n}행 저장: {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _console_utf8()
    p = argparse.ArgumentParser(description="그리운 옛날 풍경 · 다른 그림 찾기 Shorts")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    m = sub.add_parser("make")
    m.add_argument("--topic", help="topics.json의 id 또는 제목")
    m.add_argument("--difficulty", choices=list(DIFFICULTY_COUNTS))
    m.add_argument("--source", choices=["procedural", "sample", "comfyui"])
    m.add_argument("--seed", type=int)
    m.add_argument("--upload", action="store_true", help="UPLOAD_ENABLED=true 일 때만 실제 업로드")
    m.add_argument("--keep-frames", action="store_true")
    b = sub.add_parser("batch")
    b.add_argument("--count", type=int, default=10)
    b.add_argument("--difficulty", choices=list(DIFFICULTY_COUNTS))
    b.add_argument("--source", choices=["procedural", "sample", "comfyui"])
    d = sub.add_parser("daily")
    d.add_argument("--count", type=int)
    j = sub.add_parser("jobs")
    j.add_argument("--limit", type=int, default=30)
    a = sub.add_parser("approve")
    a.add_argument("job_id")
    sub.add_parser("auth")
    u = sub.add_parser("upload")
    u.add_argument("job_id")
    u.add_argument("--force-review", action="store_true", help="검수 대상도 업로드 (직접 확인한 경우)")
    sub.add_parser("status")
    ct = sub.add_parser("comfyui-test")
    ct.add_argument("--topic", default="hometown_village")
    ct.add_argument("--seed", type=int)
    e = sub.add_parser("export")
    e.add_argument("--out", default="output/report.csv")
    args = p.parse_args(argv)

    settings = load_settings()
    from src.pipeline import setup_logging
    setup_logging(settings, args.verbose)
    handlers = {"doctor": cmd_doctor, "make": cmd_make, "batch": cmd_batch, "daily": cmd_daily, "jobs": cmd_jobs,
                "approve": cmd_approve, "auth": cmd_auth, "upload": cmd_upload, "status": cmd_status,
                "export": cmd_export, "comfyui-test": cmd_comfyui_test}
    try:
        return handlers[args.cmd](settings, args)
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger("main").exception("처리하지 못한 오류: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
