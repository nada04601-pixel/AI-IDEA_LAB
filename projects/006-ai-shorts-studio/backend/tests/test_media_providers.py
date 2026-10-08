import json
import subprocess

import pytest
from PIL import Image

from app import config
from app.providers.media import MediaRequest, ProviderError, frame_size
from app.providers.mock_media import MockImageProvider, MockVideoProvider


def req(tmp_path, **kw):
    base = dict(kind="image", prompt="cat in a box", aspect_ratio="9:16", duration_sec=2.0, scene_number=1,
                version=1, attempt=1, output_path=tmp_path / "out" / "image_v1")
    base.update(kw)
    return MediaRequest(**base)


@pytest.mark.parametrize("ratio,expected", [("9:16", (720, 1280)), ("16:9", (1280, 720)), ("1:1", (1280, 1280))])
def test_frame_size(ratio, expected):
    assert frame_size(ratio) == expected


def test_mock_image(tmp_path):
    result = MockImageProvider().generate(req(tmp_path))
    assert result.file_path.suffix == ".png"
    assert result.cost_amount == 0.0
    with Image.open(result.file_path) as img:
        assert img.size == frame_size("9:16", 960)
        # 글자가 가장자리에 닿지 않는다 (좌우 끝 열은 배경색 그대로)
        edge = {img.getpixel((x, y)) for x in (0, img.width - 1) for y in range(0, img.height, 4)}
        assert (255, 255, 255) not in edge


def test_mock_fail_triggers(tmp_path):
    p = MockImageProvider()
    with pytest.raises(ProviderError):
        p.generate(req(tmp_path, prompt="x [mock-fail]", attempt=3))
    with pytest.raises(ProviderError):
        p.generate(req(tmp_path, prompt="x [mock-fail-once]", attempt=1))
    assert p.generate(req(tmp_path, prompt="x [mock-fail-once]", attempt=2)).file_path.exists()


needs_ffmpeg = pytest.mark.skipif(config.ffmpeg_path() is None, reason="FFmpeg 없음")


def probe_duration(path) -> float:
    ffprobe = config.ffmpeg_path().replace("ffmpeg", "ffprobe")
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


@needs_ffmpeg
def test_mock_video_from_color(tmp_path):
    result = MockVideoProvider().generate(req(tmp_path, kind="video", output_path=tmp_path / "video_v1", duration_sec=1.5))
    assert result.file_path.suffix == ".mp4"
    assert abs(probe_duration(result.file_path) - 1.5) < 0.2


@needs_ffmpeg
def test_mock_video_from_image(tmp_path):
    image = MockImageProvider().generate(req(tmp_path)).file_path
    result = MockVideoProvider().generate(req(tmp_path, kind="video", output_path=tmp_path / "video_v1", source_image=image))
    assert abs(probe_duration(result.file_path) - 2.0) < 0.2


def test_mock_video_without_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ffmpeg_path", lambda: None)
    with pytest.raises(ProviderError, match="FFmpeg"):
        MockVideoProvider().generate(req(tmp_path, kind="video"))
