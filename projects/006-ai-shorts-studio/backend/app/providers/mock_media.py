"""외부 API 없이 동작하는 mock 이미지·영상 공급자.

프롬프트에 [mock-fail]이 있으면 항상, [mock-fail-once]가 있으면 첫 시도만 실패한다 (실패·재시도 확인용).
"""

import hashlib
import subprocess

from PIL import Image, ImageDraw, ImageFont

from app import config
from app.providers.media import MediaRequest, MediaResult, ProviderError, frame_size


def _check_fail_trigger(req: MediaRequest) -> None:
    if "[mock-fail]" in req.prompt:
        raise ProviderError("mock 실패: 프롬프트에 [mock-fail]이 있습니다.")
    if "[mock-fail-once]" in req.prompt and req.attempt == 1:
        raise ProviderError("mock 일시 실패: 재시도하면 성공합니다.")


def _color(prompt: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(prompt.encode()).digest()
    return tuple(60 + b % 140 for b in digest[:3])  # type: ignore[return-value]


class MockImageProvider:
    name = "mock"
    kind = "image"
    is_paid = False
    currency = "USD"

    def estimate_cost(self, duration_sec: float) -> float:
        return 0.0

    def generate(self, req: MediaRequest) -> MediaResult:
        _check_fail_trigger(req)
        width, height = frame_size(req.aspect_ratio, 960)
        top = _color(req.prompt)
        bottom = tuple(c // 3 for c in top)
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)
        for y in range(height):
            t = y / max(height - 1, 1)
            draw.line([(0, y), (width, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
        big = ImageFont.load_default(size=width // 8)  # "MOCK IMAGE"가 가로 폭 안에 들어가는 크기
        small = ImageFont.load_default(size=max(width // 18, 14))
        code = hashlib.sha256(req.prompt.encode()).hexdigest()[:8]
        lines = [("MOCK IMAGE", big), (f"scene {req.scene_number} · v{req.version}", small), (f"#{code} · {req.aspect_ratio}", small)]
        y = height // 2 - max(width, height) // 10
        for text, font in lines:
            box = draw.textbbox((0, 0), text, font=font)
            draw.text(((width - (box[2] - box[0])) // 2, y), text, font=font, fill=(255, 255, 255))
            y += (box[3] - box[1]) + max(width, height) // 30
        path = req.output_path.with_suffix(".png")
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "PNG")
        return MediaResult(path, 0.0, self.currency, {"width": width, "height": height, "mock": True})


class MockVideoProvider:
    """FFmpeg로 장면 이미지(없으면 단색 화면)를 장면 길이만큼의 짧은 MP4로 만든다."""

    name = "mock"
    kind = "video"
    is_paid = False
    currency = "USD"

    def estimate_cost(self, duration_sec: float) -> float:
        return 0.0

    def generate(self, req: MediaRequest) -> MediaResult:
        _check_fail_trigger(req)
        ffmpeg = config.ffmpeg_path()
        if not ffmpeg:
            raise ProviderError("FFmpeg를 찾을 수 없습니다. FFmpeg를 설치하거나 AISS_FFMPEG_PATH를 지정하세요.")
        width, height = frame_size(req.aspect_ratio, 960)
        path = req.output_path.with_suffix(".mp4")
        path.parent.mkdir(parents=True, exist_ok=True)
        duration = f"{req.duration_sec:g}"
        if req.source_image and req.source_image.exists():
            source = ["-loop", "1", "-i", str(req.source_image)]
            zoom = f"zoompan=z='min(zoom+0.0015,1.2)':d=1:s={width}x{height}:fps=24"
            vf = f"scale={width * 2}:{height * 2},{zoom},format=yuv420p"
        else:
            r, g, b = _color(req.prompt)
            source = ["-f", "lavfi", "-i", f"color=c=0x{r:02x}{g:02x}{b:02x}:s={width}x{height}:r=24"]
            vf = "format=yuv420p"
        cmd = [ffmpeg, "-y", "-loglevel", "error", *source, "-t", duration, "-vf", vf, "-r", "24",
               "-c:v", "libx264", "-preset", "veryfast", "-movflags", "+faststart", "-an", str(path)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            raise ProviderError("FFmpeg 영상 생성이 시간 안에 끝나지 않았습니다.")
        if proc.returncode != 0:
            raise ProviderError(f"FFmpeg 영상 생성 실패: {proc.stderr.strip()[-300:]}")
        return MediaResult(path, 0.0, self.currency, {"width": width, "height": height, "duration_sec": req.duration_sec, "mock": True})
