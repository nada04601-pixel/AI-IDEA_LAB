"""편집·렌더링 (기획서 Module 4) — analysis.json + tts 결과 → final_output.mp4.

1. 컷 배치 (cutplan): 문장 경계에 컷 전환, 하이라이트 샷 우선.
2. 컷마다: 원본 자막·워터마크 가리기(blur/crop) → 속도 조절 → 9:16 정규화 → 프레임 수를 정확히 맞춰 이어 붙이기.
3. 한국어 자막·광고 표시 PNG를 overlay. 원본 소리는 쓰지 않고 audio_mix(음성+효과음+BGM, -14 LUFS)를 얹는다.
"""

import shutil
from collections.abc import Callable
from pathlib import Path

from ssm import subtitle
from ssm.audio_mix import AudioError, mix_audio
from ssm.config import AppConfig
from ssm.cutplan import PlanError, plan_timeline
from ssm.media import Media
from ssm.schemas import Analysis, Cut, TextBox, WordTimings
from ssm.workspace import Workspace

TAIL_SEC = 0.5  # 마지막 문장 뒤 여유
COVER_TOLERANCE = 0.12  # 원본 비율이 9:16과 이 정도 이내로 다르면 꽉 채워 자르고, 더 다르면 블러 배경 위에 얹는다
PREVIEW_SIZE = (540, 960)
AD_FONT = "assets/fonts/Pretendard-Bold.otf"
AD_BADGE_FONT = "assets/fonts/Pretendard-ExtraBold.otf"
CROP_BAND = (0.25, 0.70)  # crop 방식: 글자가 위쪽 25% 안이나 아래쪽 30% 안에만 있을 때 잘라낸다
CROP_KEEP_MIN = 0.65  # 잘라낸 뒤 화면 높이가 이 비율보다 작아지면 crop 대신 blur


class EditError(Exception):
    """사용자에게 그대로 보여줄 수 있는 편집 단계 오류."""


# ---- 원본 자막 가리기 -------------------------------------------------------------


def removal_method(cfg_mode: str, boxes: list[TextBox], width: int, height: int) -> tuple[str, tuple[int, int] | None]:
    """('none'|'blur'|'crop', crop이면 남길 세로 구간 (y0, y1))."""
    if not boxes:
        return "none", None
    if cfg_mode == "crop":
        top = [b for b in boxes if b.y + b.h <= height * CROP_BAND[0]]
        bottom = [b for b in boxes if b.y >= height * CROP_BAND[1]]
        if len(top) + len(bottom) == len(boxes):
            y0 = max((b.y + b.h for b in top), default=0)
            y1 = min((b.y for b in bottom), default=height)
            if y1 - y0 >= height * CROP_KEEP_MIN:
                return "crop", (y0 // 2 * 2, y1 // 2 * 2)
    return "blur", None  # auto·inpaint도 지금은 blur (LaMa 인페인팅은 GPU 환경에서 추후 추가)


def _blur_chain(label: str, boxes: list[TextBox], width: int, height: int, tag: str) -> tuple[list[str], str]:
    parts = []
    for k, b in enumerate(boxes):
        x, y = max(0, b.x), max(0, b.y)
        w, h = max(2, min(b.w, width - x)), max(2, min(b.h, height - y))
        sigma = max(8, h // 4)
        out = f"r{tag}_{k}"
        parts.append(f"[{label}]split[m{tag}_{k}][b{tag}_{k}];"
                     f"[b{tag}_{k}]crop={w}:{h}:{x}:{y},gblur=sigma={sigma},"
                     f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.3:t=fill[o{tag}_{k}];"
                     f"[m{tag}_{k}][o{tag}_{k}]overlay={x}:{y}[{out}]")
        label = out
    return parts, label


def cut_filter(i: int, cut: Cut, src_w: int, src_h: int, boxes: list[TextBox], mode: str,
               w: int, h: int, fps: int, frames: int) -> tuple[str, str]:
    """입력 i번(이 컷의 원본)을 w×h·fps, 정확히 frames 프레임으로 만드는 필터와 실제 쓴 가리기 방식."""
    method, keep = removal_method(mode, boxes, src_w, src_h)
    parts: list[str] = []
    label = f"{i}:v"
    if method == "blur":
        parts, label = _blur_chain(label, boxes, src_w, src_h, str(i))
    elif method == "crop":
        parts.append(f"[{label}]crop=iw:{keep[1] - keep[0]}:0:{keep[0]}[k{i}]")
        label, src_h = f"k{i}", keep[1] - keep[0]

    speed = f"setpts=(PTS-STARTPTS)/{cut.speed:.4f}"
    cover = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    tail = (f"fps={fps},tpad=stop_mode=clone:stop_duration=3,trim=end_frame={frames},"
            f"setpts=PTS-STARTPTS,setsar=1,format=yuv420p[c{i}]")
    if abs(src_w / src_h - w / h) / (w / h) <= COVER_TOLERANCE:
        parts.append(f"[{label}]{speed},{cover},{tail}")
    else:
        parts.append(f"[{label}]{speed},split[a{i}][b{i}];[a{i}]{cover},boxblur=24:2[bg{i}];"
                     f"[b{i}]scale={w}:{h}:force_original_aspect_ratio=decrease[fg{i}];"
                     f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,{tail}")
    return ";".join(parts), method


def frame_counts(cuts: list[Cut], total: float, fps: int) -> list[int]:
    """컷 경계를 프레임 단위로 반올림해 누적 오차 없이 나눈다."""
    marks = [round(c.position * fps) for c in cuts] + [round(total * fps)]
    return [max(1, b - a) for a, b in zip(marks, marks[1:])]


def _encoder_args(media: Media, cfg: AppConfig, preview: bool) -> list[str]:
    if preview:
        return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "28"]
    if media.video_encoder() == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", str(cfg.video.crf), "-b:v", "0",
                "-profile:v", "high"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(cfg.video.crf), "-profile:v", "high"]


# ---- 단계 실행 ------------------------------------------------------------------


def run_edit(ws: Workspace, cfg: AppConfig | None = None, preview: bool = False,
             log: Callable[[str], None] = print) -> Path:
    cfg = cfg or ws.config()
    ad_text = cfg.ad_disclosure.text()
    if not ad_text:
        raise EditError("광고 표시 프로필이 정해지지 않아 렌더링을 멈췄습니다 (법적 의무 표시).\n"
                        "→ `ssm set ad_disclosure.profile coupang` (또는 aliexpress / custom) 으로 고른 뒤 다시 실행하세요.")
    if ws.status("analyze", cfg) != "done":
        raise EditError("영상 분석(analyze)이 완료되지 않았거나 원본 영상이 바뀌었습니다 → 먼저 `ssm analyze`를 실행하세요.")
    if ws.status("tts", cfg) != "done":
        raise EditError("음성(tts) 단계가 완료되지 않았거나 대본·목소리가 바뀌었습니다 → 먼저 `ssm tts`를 실행하세요.")
    fonts = {"sub": cfg.path(cfg.subtitle.font), "ad": cfg.path(AD_FONT), "badge": cfg.path(AD_BADGE_FONT)}
    missing = [p.name for p in fonts.values() if not p.is_file()]
    if missing:
        raise EditError(f"폰트 파일이 없습니다: {', '.join(missing)} → `ssm fonts`를 실행하세요.")

    media = Media(cfg)
    timings = WordTimings.model_validate_json((ws.path / "word_timings.json").read_text(encoding="utf-8"))
    analysis = Analysis.model_validate_json((ws.path / "analysis.json").read_text(encoding="utf-8"))
    videos = {v.file: v for v in analysis.videos}
    for v in analysis.videos:
        if not (ws.path / v.file).is_file():
            raise EditError(f"분석했던 영상 {v.file}이 없습니다 → `ssm analyze`를 다시 실행하세요.")
    total = round(timings.duration + TAIL_SEC, 3)
    try:
        timeline, warnings = plan_timeline(timings, analysis, total)
    except PlanError as e:
        raise EditError(str(e)) from e
    for msg in warnings:
        log(f"[주의] {msg}")

    mode = cfg.foreign_sub_removal
    if mode == "inpaint" and any(v.text_boxes for v in analysis.videos):
        log("[참고] inpaint(인페인팅)는 아직 지원 전이라 blur로 원본 자막을 가립니다.")
    if any(v.ocr == "unavailable" for v in analysis.videos):
        log("[주의] 분석 때 OCR을 쓸 수 없어 원본 자막을 가리지 못합니다 (`ssm doctor`로 PyTorch 확인 후 `ssm analyze` 다시).")

    w, h, fps = cfg.video.width, cfg.video.height, cfg.video.fps
    cues = subtitle.build_cues(timings, cfg.subtitle.max_chars_per_line, total)

    out_name = "preview.mp4" if preview else "final_output.mp4"
    if not preview and (ws.path / "final_output.mp4").is_file():
        n = ws.snapshot()
        log(f"이전 결과를 versions/v{n}에 보관했습니다.")

    render_dir = ws.path / "render"
    shutil.rmtree(render_dir, ignore_errors=True)
    render_dir.mkdir()
    try:
        audio = mix_audio(ws, cfg, timings, total, render_dir, media, log=log)
    except AudioError as e:
        raise EditError(str(e)) from e

    scale = w / subtitle.REF_WIDTH
    ad_png = render_dir / "ad.png"
    ad_size = subtitle.render_ad(ad_text, fonts["ad"], fonts["badge"], w, ad_png)
    ad_xy = subtitle.ad_position(ad_size, w, cfg.ad_disclosure.position)
    overlays = []
    for i, cue in enumerate(cues):
        png = render_dir / f"cue_{i:03d}.png"
        size = subtitle.render_cue(cue, cfg.subtitle, fonts["sub"], scale, png)
        overlays.append((png, subtitle.cue_position(size, (w, h), cfg.subtitle.position_y_ratio), cue))

    # 입력: 컷들 → 오디오 믹스 → 광고 표시 → 자막 화면들. 원본 영상의 소리는 쓰지 않는다 (항상 음소거).
    args: list[str] = []
    for cut in timeline.cuts:
        args += ["-ss", f"{cut.start:.3f}", "-t", f"{cut.duration + 0.5:.3f}", "-i", str(ws.path / cut.source)]
    audio_idx = len(timeline.cuts)
    args += ["-i", str(audio), "-i", str(ad_png)]
    for png, _, _ in overlays:
        args += ["-i", str(png)]

    graph, methods = [], set()
    for i, (cut, frames) in enumerate(zip(timeline.cuts, frame_counts(timeline.cuts, total, fps))):
        v = videos[cut.source]
        chain, method = cut_filter(i, cut, v.width, v.height, v.text_boxes, mode, w, h, fps, frames)
        graph.append(chain)
        methods.add(method)
    n = len(timeline.cuts)
    graph.append("".join(f"[c{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[base]")
    graph.append(f"[base][{audio_idx + 1}:v]overlay={ad_xy[0]}:{ad_xy[1]}[v0]")
    for k, (_, (x, y), cue) in enumerate(overlays):
        graph.append(f"[v{k}][{audio_idx + 2 + k}:v]overlay={x}:{y}:"
                     f"enable='between(t,{cue.start:.3f},{cue.end:.3f})'[v{k + 1}]")
    last = f"v{len(overlays)}"
    if preview:
        graph.append(f"[{last}]scale={PREVIEW_SIZE[0]}:{PREVIEW_SIZE[1]}[vout]")
        last = "vout"

    tmp = ws.path / f"{Path(out_name).stem}.tmp.mp4"
    args += ["-filter_complex", ";".join(graph), "-map", f"[{last}]", "-map", f"{audio_idx}:a", "-t", f"{total:.3f}",
             *_encoder_args(media, cfg, preview), "-pix_fmt", "yuv420p", "-r", str(fps),
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)]
    (ws.path / "timeline.json").write_text(timeline.model_dump_json(indent=2), encoding="utf-8")
    (ws.path / "subtitles.srt").write_text(subtitle.to_srt(cues), encoding="utf-8")
    size_label = f"{PREVIEW_SIZE[0]}x{PREVIEW_SIZE[1]} 미리보기" if preview else f"{w}x{h}"
    sources = len({c.source for c in timeline.cuts})
    labels = {"blur": "원본 자막 블러", "crop": "원본 자막 잘라냄"}
    hidden = ", ".join(labels[m] for m in sorted(methods - {"none"})) or "가릴 원본 자막 없음"
    log(f"렌더링: {total:.1f}초 · {size_label} · {fps}fps · 컷 {n}개(영상 {sources}개) · 자막 {len(cues)}개 · "
        f"{hidden} · 광고 표시 '{cfg.ad_disclosure.profile}'")
    try:
        media.run(args, log=ws.path / "logs" / "edit.log", what="영상 렌더링")
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    out = ws.path / out_name
    tmp.replace(out)
    shutil.rmtree(render_dir, ignore_errors=True)
    if not preview:
        ws.mark_done("edit")
    return out
