"""편집·렌더링 (기획서 Module 4) — 원본 영상 + tts.mp3 + word_timings.json → final_output.mp4.

M1 범위: 원본 영상 1개를 음성 길이만큼 이어 쓰고(짧으면 반복), 9:16으로 맞춘 뒤 원본 소리를 빼고
TTS 음성·한국어 자막·광고 표시를 얹는다. 다중 컷 배치·외국어 자막 가리기·BGM은 M2.
"""

import shutil
from collections.abc import Callable
from pathlib import Path

from ssm import subtitle
from ssm.config import AppConfig
from ssm.media import Media, VideoInfo
from ssm.schemas import Cut, Timeline, WordTimings
from ssm.workspace import Workspace

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
TAIL_SEC = 0.5  # 마지막 문장 뒤 여유
COVER_TOLERANCE = 0.12  # 원본 비율이 9:16과 이 정도 이내로 다르면 꽉 채워 자르고, 더 다르면 블러 배경 위에 얹는다
PREVIEW_SIZE = (540, 960)
AD_FONT = "assets/fonts/Pretendard-Bold.otf"
AD_BADGE_FONT = "assets/fonts/Pretendard-ExtraBold.otf"


class EditError(Exception):
    """사용자에게 그대로 보여줄 수 있는 편집 단계 오류."""


def source_videos(ws: Workspace) -> list[Path]:
    folder = ws.path / "raw_videos"
    return sorted(p for p in folder.glob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS)


def plan_cuts(source: str, source_duration: float, total: float) -> list[Cut]:
    """원본 영상 하나로 total초를 채운다. 원본이 짧으면 처음부터 반복한다."""
    if source_duration <= 0.1:
        raise EditError(f"원본 영상({source})의 길이가 너무 짧습니다.")
    cuts, t = [], 0.0
    while total - t > 0.01:
        length = min(source_duration, total - t)
        cuts.append(Cut(source=source, start=0.0, end=round(length, 3)))
        t += length
    return cuts


def _normalize_filter(info: VideoInfo, w: int, h: int, fps: int, label_in: str, label_out: str, i: int) -> str:
    cover = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    tail = f"fps={fps},setsar=1,format=yuv420p,setpts=PTS-STARTPTS[{label_out}]"
    if abs(info.width / info.height - w / h) / (w / h) <= COVER_TOLERANCE:
        return f"[{label_in}]{cover},{tail}"
    return (f"[{label_in}]split[a{i}][b{i}];[a{i}]{cover},boxblur=24:2[bg{i}];"
            f"[b{i}]scale={w}:{h}:force_original_aspect_ratio=decrease[fg{i}];"
            f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,{tail}")


def _encoder_args(media: Media, cfg: AppConfig, preview: bool) -> list[str]:
    if preview:
        return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "28"]
    if media.video_encoder() == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", str(cfg.video.crf), "-b:v", "0",
                "-profile:v", "high"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(cfg.video.crf), "-profile:v", "high"]


def run_edit(ws: Workspace, cfg: AppConfig | None = None, preview: bool = False,
             log: Callable[[str], None] = print) -> Path:
    cfg = cfg or ws.config()
    ad_text = cfg.ad_disclosure.text()
    if not ad_text:
        raise EditError("광고 표시 프로필이 정해지지 않아 렌더링을 멈췄습니다 (법적 의무 표시).\n"
                        "→ `ssm set ad_disclosure.profile coupang` (또는 aliexpress / custom) 으로 고른 뒤 다시 실행하세요.")
    if ws.status("tts", cfg) != "done":
        raise EditError("음성(tts) 단계가 완료되지 않았거나 대본·목소리가 바뀌었습니다 → 먼저 `ssm tts`를 실행하세요.")
    videos = source_videos(ws)
    if not videos:
        raise EditError("raw_videos/에 원본 영상이 없습니다 → `ssm new --local 영상.mp4`로 영상을 넣어 프로젝트를 만드세요.")
    fonts = {"sub": cfg.path(cfg.subtitle.font), "ad": cfg.path(AD_FONT), "badge": cfg.path(AD_BADGE_FONT)}
    missing = [p.name for p in fonts.values() if not p.is_file()]
    if missing:
        raise EditError(f"폰트 파일이 없습니다: {', '.join(missing)} → `ssm fonts`를 실행하세요.")

    media = Media(cfg)
    timings = WordTimings.model_validate_json((ws.path / "word_timings.json").read_text(encoding="utf-8"))
    total = round(timings.duration + TAIL_SEC, 3)
    source = videos[0]
    rel = source.relative_to(ws.path).as_posix()
    info = media.probe_video(source)
    timeline = Timeline(duration=total, cuts=plan_cuts(rel, info.duration, total))
    if len(videos) > 1:
        log(f"[참고] 영상이 {len(videos)}개지만 M1에서는 첫 번째({source.name})만 씁니다 (여러 영상 컷 편집은 M2).")

    w, h, fps = cfg.video.width, cfg.video.height, cfg.video.fps
    cues = subtitle.build_cues(timings, cfg.subtitle.max_chars_per_line, total)

    out_name = "preview.mp4" if preview else "final_output.mp4"
    if not preview and (ws.path / "final_output.mp4").is_file():
        n = ws.snapshot()
        log(f"이전 결과를 versions/v{n}에 보관했습니다.")

    render_dir = ws.path / "render"
    shutil.rmtree(render_dir, ignore_errors=True)
    render_dir.mkdir()
    scale = w / subtitle.REF_WIDTH
    ad_png = render_dir / "ad.png"
    ad_size = subtitle.render_ad(ad_text, fonts["ad"], fonts["badge"], w, ad_png)
    ad_xy = subtitle.ad_position(ad_size, w, cfg.ad_disclosure.position)
    overlays = []
    for i, cue in enumerate(cues):
        png = render_dir / f"cue_{i:03d}.png"
        size = subtitle.render_cue(cue, cfg.subtitle, fonts["sub"], scale, png)
        overlays.append((png, subtitle.cue_position(size, (w, h), cfg.subtitle.position_y_ratio), cue))

    # 입력: 컷들 → 음성 → 광고 표시 → 자막 화면들. 원본 영상의 소리는 쓰지 않는다 (항상 음소거).
    args: list[str] = []
    for cut in timeline.cuts:
        args += ["-ss", f"{cut.start:.3f}", "-t", f"{cut.duration:.3f}", "-i", str(ws.path / cut.source)]
    audio_idx = len(timeline.cuts)
    args += ["-i", str(ws.path / "tts.mp3"), "-i", str(ad_png)]
    for png, _, _ in overlays:
        args += ["-i", str(png)]

    graph = []
    for i, cut in enumerate(timeline.cuts):
        cut_info = info if ws.path / cut.source == source else media.probe_video(ws.path / cut.source)
        graph.append(_normalize_filter(cut_info, w, h, fps, f"{i}:v", f"c{i}", i))
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
    graph.append(f"[{audio_idx}:a]aresample=48000,apad[aout]")

    tmp = ws.path / f"{Path(out_name).stem}.tmp.mp4"
    args += ["-filter_complex", ";".join(graph), "-map", f"[{last}]", "-map", "[aout]", "-t", f"{total:.3f}",
             *_encoder_args(media, cfg, preview), "-pix_fmt", "yuv420p", "-r", str(fps),
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)]
    (ws.path / "timeline.json").write_text(timeline.model_dump_json(indent=2), encoding="utf-8")
    (ws.path / "subtitles.srt").write_text(subtitle.to_srt(cues), encoding="utf-8")
    size_label = f"{PREVIEW_SIZE[0]}x{PREVIEW_SIZE[1]} 미리보기" if preview else f"{w}x{h}"
    log(f"렌더링: {total:.1f}초 · {size_label} · {fps}fps · 자막 {len(cues)}개 · 광고 표시 '{cfg.ad_disclosure.profile}'")
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
