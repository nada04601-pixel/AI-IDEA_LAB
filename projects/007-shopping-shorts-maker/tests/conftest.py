import subprocess
import shutil
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    """config.yaml·presets만 복사한 빈 프로젝트 폴더를 SSM_HOME으로 쓴다 (실제 workspace를 건드리지 않게)."""
    root = tmp_path / "작업 폴더"  # 한글·공백 경로도 함께 검증
    root.mkdir()
    shutil.copy(PROJECT / "config.yaml", root / "config.yaml")
    shutil.copytree(PROJECT / "presets", root / "presets")
    monkeypatch.setenv("SSM_HOME", str(root))
    return root


FFMPEG = shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(not FFMPEG or not shutil.which("ffprobe"), reason="FFmpeg가 없음")


def make_video(path: Path, size: str = "320x240", seconds: float = 2, shots: int = 1, box: bool = False,
               color: str | None = None, tone: int = 880) -> Path:
    """테스트용 영상. shots개 장면이 이어지고(장면마다 전혀 다른 그림), box면 아래쪽에 흰 '자막' 띠가 계속 보인다.
    color를 주면 그 단색 화면, tone은 소리 높이(Hz)."""
    sources = ["testsrc2", "mandelbrot", "rgbtestsrc", "smptebars", "cellauto"]
    w, h = (int(v) for v in size.split("x"))
    each = seconds / shots
    args = [FFMPEG, "-v", "error", "-y"]
    for k in range(shots):
        src = f"color=c={color}" if color else sources[k % len(sources)]
        args += ["-f", "lavfi", "-i", f"{src}:s={size}:r=30" if color else f"{src}=s={size}:r=30"]
    args += ["-f", "lavfi", "-i", f"sine=f={tone}:d={seconds}"]
    chains = [f"[{k}:v]trim=duration={each},setpts=PTS-STARTPTS,format=yuv420p[s{k}]" for k in range(shots)]
    graph = ";".join(chains) + ";" + "".join(f"[s{k}]" for k in range(shots)) + f"concat=n={shots}:v=1[cat]"
    graph += (f";[cat]drawbox=x={w // 5}:y={int(h * 0.8)}:w={w * 3 // 5}:h={h // 12}:color=white:t=fill[v]" if box
              else ";[cat]null[v]")
    args += ["-filter_complex", graph, "-map", "[v]", "-map", f"{shots}:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-shortest", str(path)]
    subprocess.run(args, check=True)
    return path


@pytest.fixture(autouse=True)
def no_models(monkeypatch):
    """테스트에서 실제 AI 모델(OCR·음성 인식·CLIP)을 내려받거나 불러오지 않게 한다. 필요한 테스트는 가짜로 바꿔 끼운다."""
    from ssm import analyzer, collector
    from ssm.filters import Inspectors

    monkeypatch.setattr(analyzer, "load_detector", lambda cfg: (None, "테스트: 모델 사용 안 함"))
    monkeypatch.setattr(collector, "load_inspectors",
                        lambda cfg, log=print: Inspectors(ocr_reason="테스트", speech_reason="테스트", clip_reason="테스트"))
