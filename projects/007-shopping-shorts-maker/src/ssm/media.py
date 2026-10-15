"""FFmpeg·ffprobe 실행 (tts·edit 공용). subprocess로 직접 호출한다 (기획서 5장)."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ssm.config import AppConfig
from ssm.doctor import Probe, ffmpeg_binary

FFMPEG_HINT = "`ssm doctor`로 FFmpeg 설치를 확인하세요."


class MediaError(Exception):
    """사용자에게 그대로 보여줄 수 있는 FFmpeg 관련 오류."""


@dataclass(frozen=True)
class VideoInfo:
    width: int  # 회전(세로 촬영 메타데이터)을 반영한 화면 크기
    height: int
    duration: float


class Media:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        ff = ffmpeg_binary(cfg, Probe())
        if not ff:
            raise MediaError("FFmpeg를 찾을 수 없습니다. " + FFMPEG_HINT)
        self.ffmpeg = ff
        self.ffprobe = str(Path(ff).with_name(Path(ff).name.replace("ffmpeg", "ffprobe")))
        self._encoder: str | None = None

    def run(self, args: list[str], *, stdin: bytes | None = None, log: Path | None = None,
            what: str = "FFmpeg 작업") -> bytes:
        """ffmpeg를 실행하고 stdout을 돌려준다. 실패하면 마지막 오류 줄과 함께 MediaError."""
        cmd = [self.ffmpeg, "-hide_banner", "-y", *(["-nostdin"] if stdin is None else []), *args]
        try:
            p = subprocess.run(cmd, input=stdin, capture_output=True)
        except OSError as e:
            raise MediaError(f"{what}을(를) 시작하지 못했습니다 ({e}). " + FFMPEG_HINT) from e
        err = p.stderr.decode("utf-8", errors="replace")
        if log:
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(subprocess.list2cmdline(cmd) + "\n\n" + err, encoding="utf-8")
        if p.returncode != 0:
            tail = "\n".join(err.strip().splitlines()[-5:])
            where = f" (전체 로그: {log})" if log else ""
            raise MediaError(f"{what}에 실패했습니다{where}.\n{tail}")
        return p.stdout

    def probe_video(self, path: Path) -> VideoInfo:
        cmd = [self.ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=width,height:stream_side_data=rotation:stream_tags=rotate:format=duration",
               "-of", "json", str(path)]
        try:
            p = subprocess.run(cmd, capture_output=True)
        except OSError as e:
            raise MediaError(f"ffprobe를 실행하지 못했습니다 ({e}). " + FFMPEG_HINT) from e
        data = json.loads(p.stdout or b"{}")
        streams = data.get("streams") or []
        if p.returncode != 0 or not streams:
            raise MediaError(f"영상 파일을 읽을 수 없습니다: {path.name} — 손상됐거나 영상이 아닌 파일입니다.")
        s = streams[0]
        rotation = int(float(s.get("tags", {}).get("rotate", 0)))
        for side in s.get("side_data_list", []):
            rotation = int(float(side.get("rotation", rotation)))
        w, h = int(s["width"]), int(s["height"])
        if abs(rotation) % 180 == 90:
            w, h = h, w
        return VideoInfo(w, h, float(data.get("format", {}).get("duration") or 0))

    def audio_duration(self, path: Path) -> float:
        p = subprocess.run([self.ffprobe, "-v", "error", "-show_entries", "format=duration", "-of",
                            "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
        try:
            return float(p.stdout.strip())
        except ValueError as e:
            raise MediaError(f"오디오 길이를 읽지 못했습니다: {path.name}") from e

    def video_encoder(self) -> str:
        """config의 video.encoder. auto면 NVENC가 실제로 동작할 때만 GPU 인코딩."""
        if self._encoder:
            return self._encoder
        choice = self.cfg.video.encoder
        if choice == "auto":
            choice = "libx264"
            try:
                self.run(["-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
                          "-c:v", "h264_nvenc", "-f", "null", "-"], what="NVENC 확인")
                choice = "h264_nvenc"
            except MediaError:
                pass
        self._encoder = choice
        return choice
