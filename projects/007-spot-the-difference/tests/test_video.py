import json
import shutil
import subprocess

import pytest

from spotdiff.__main__ import main

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffprobe"), reason="FFmpeg 없음")


def test_cli_without_video(tmp_path):
    assert main(["--out", str(tmp_path), "--seed", "1", "--puzzles", "2", "--no-video"]) == 0
    meta = json.loads((tmp_path / "puzzles.json").read_text(encoding="utf-8"))
    assert [len(p["differences"]) for p in meta["puzzles"]] == [3, 4]
    for n in (1, 2):
        for part in ("a", "b", "answer"):
            assert (tmp_path / f"puzzle{n}_{part}.png").exists()


@needs_ffmpeg
def test_cli_renders_vertical_mp4_with_audio(tmp_path):
    assert main(["--out", str(tmp_path), "--seed", "1", "--puzzles", "1", "--time", "2"]) == 0
    mp4 = tmp_path / "shorts.mp4"
    info = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
         "-of", "json", str(mp4)], capture_output=True, text=True, check=True).stdout)
    kinds = {s["codec_type"] for s in info["streams"]}
    assert kinds == {"video", "audio"}
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1080, 1920)
    # 시작 1초 + 제한 2초 + 정답 3곳(0.6초씩) + 1.6초 + 마무리 2.5초 = 8.9초
    assert abs(float(info["format"]["duration"]) - 8.9) < 0.3
