"""승인된 장면을 이어 붙여 최종 MP4를 만든다 (FFmpeg).

1) 장면마다 같은 크기·프레임·오디오 형식의 조각(segment)을 만든다. 영상이 있으면 영상, 없으면 이미지를 쓴다.
2) 조각을 이어 붙인다.
3) 자막(SRT)을 영상에 입히고(선택), 켜고 끌 수 있는 자막 트랙도 함께 넣는다.
"""

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app import config
from app.providers.media import ProviderError, frame_size

FPS = 30
AUDIO_ARGS = ["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]
VIDEO_ARGS = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-r", str(FPS)]


@dataclass(frozen=True)
class SegmentInput:
    scene_number: int
    duration_sec: float
    visual_path: Path
    visual_kind: str  # image | video
    audio_path: Path | None


@dataclass(frozen=True)
class RenderSettings:
    include_audio: bool = True
    burn_subtitles: bool = True

    def to_json(self) -> str:
        return json.dumps({"include_audio": self.include_audio, "burn_subtitles": self.burn_subtitles})

    @classmethod
    def from_json(cls, raw: str) -> "RenderSettings":
        data = json.loads(raw or "{}")
        return cls(bool(data.get("include_audio", True)), bool(data.get("burn_subtitles", True)))


def output_size(aspect_ratio: str) -> tuple[int, int]:
    """최종 출력 크기. 9:16 → 1080×1920, 16:9 → 1920×1080, 1:1 → 1080×1080."""
    return frame_size(aspect_ratio, 1080 if aspect_ratio == "1:1" else 1920)


def ffmpeg_info() -> dict:
    path = config.ffmpeg_path()
    if not path:
        return {"available": False, "path": None, "version": None}
    try:
        out = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=10).stdout
        version = out.split("\n", 1)[0].removeprefix("ffmpeg version ").split(" ")[0]
        return {"available": True, "path": path, "version": version}
    except (OSError, subprocess.SubprocessError):
        return {"available": False, "path": path, "version": None}


def _run(cmd: list[str], cwd: Path, what: str) -> None:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        raise ProviderError(f"{what}: FFmpeg가 시간 안에 끝나지 않았습니다.")
    if proc.returncode != 0:
        raise ProviderError(f"{what} 실패: {proc.stderr.strip()[-400:]}")


def _subtitle_style() -> str:
    """libass 자막 스타일. 글꼴은 AISS_SUBTITLE_FONT로 바꿀 수 있다 (없으면 시스템이 한글 글꼴로 대체)."""
    font = os.getenv("AISS_SUBTITLE_FONT", "")
    style = "FontSize=13,Outline=2,Shadow=0,MarginV=40,Alignment=2,BorderStyle=1"
    return f"FontName={font},{style}" if font else style


def render(
    segments: list[SegmentInput],
    srt_text: str,
    aspect_ratio: str,
    settings: RenderSettings,
    work_dir: Path,
    on_progress: Callable[[int], None] = lambda _p: None,
) -> tuple[Path, Path]:
    """최종 MP4와 SRT 경로를 돌려준다. 실패하면 ProviderError."""
    ffmpeg = config.ffmpeg_path()
    if not ffmpeg:
        raise ProviderError("FFmpeg를 찾을 수 없습니다. FFmpeg를 설치하거나 AISS_FFMPEG_PATH를 지정하세요.")
    if not segments:
        raise ProviderError("렌더링할 장면이 없습니다.")
    width, height = output_size(aspect_ratio)
    work_dir.mkdir(parents=True, exist_ok=True)
    fit = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    total_steps = len(segments) + 2

    names = []
    for i, seg in enumerate(segments, start=1):
        d = f"{seg.duration_sec:g}"
        if seg.visual_kind == "video":
            visual = ["-i", str(seg.visual_path)]
            vf = f"{fit},fps={FPS},tpad=stop_mode=clone:stop_duration={d}"  # 영상이 짧으면 마지막 장면을 늘린다
        else:
            visual = ["-loop", "1", "-framerate", str(FPS), "-i", str(seg.visual_path)]
            vf = f"{fit},fps={FPS}"
        if settings.include_audio and seg.audio_path:
            audio = ["-i", str(seg.audio_path)]
            af = ["-af", "apad"]  # 음성이 짧으면 무음으로 채우고, 길면 -t에서 자른다
        else:
            audio = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
            af = []
        name = f"seg_{i:03d}.mp4"
        cmd = [ffmpeg, "-y", "-loglevel", "error", *visual, *audio, "-map", "0:v:0", "-map", "1:a:0",
               "-vf", vf, *af, "-t", d, *VIDEO_ARGS, *AUDIO_ARGS, name]
        _run(cmd, work_dir, f"장면 {seg.scene_number} 조각 만들기")
        names.append(name)
        on_progress(round(i / total_steps * 100))

    (work_dir / "list.txt").write_text("".join(f"file '{n}'\n" for n in names), encoding="utf-8")
    _run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "joined.mp4"],
         work_dir, "장면 이어 붙이기")
    on_progress(round((len(segments) + 1) / total_steps * 100))

    srt = work_dir / "subtitles.srt"
    srt.write_text(srt_text, encoding="utf-8")
    has_subs = bool(srt_text.strip())
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", "joined.mp4"]
    if has_subs:
        cmd += ["-i", "subtitles.srt", "-map", "0:v", "-map", "0:a", "-map", "1:s",
                "-c:s", "mov_text", "-metadata:s:s:0", "language=kor"]
    else:
        cmd += ["-map", "0:v", "-map", "0:a"]
    if has_subs and settings.burn_subtitles:
        # 작업 폴더 안의 상대 경로를 써서 Windows 경로 이스케이프 문제를 피한다
        cmd += ["-vf", f"subtitles=subtitles.srt:charenc=UTF-8:force_style='{_subtitle_style()}'", *VIDEO_ARGS]
    else:
        cmd += ["-c:v", "copy"]
    cmd += ["-c:a", "copy", "-movflags", "+faststart", "shorts.mp4"]
    _run(cmd, work_dir, "자막 입히기·최종 파일 만들기")

    for leftover in [*names, "list.txt", "joined.mp4"]:
        (work_dir / leftover).unlink(missing_ok=True)
    on_progress(100)
    return work_dir / "shorts.mp4", srt


def probe_duration(path: Path) -> float | None:
    ffmpeg = config.ffmpeg_path()
    if not ffmpeg:
        return None
    ffprobe = shutil.which("ffprobe") or re.sub(r"ffmpeg(\.exe)?$", r"ffprobe\1", ffmpeg)
    try:
        out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                             capture_output=True, text=True, timeout=30).stdout
        return round(float(json.loads(out)["format"]["duration"]), 3)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return None
