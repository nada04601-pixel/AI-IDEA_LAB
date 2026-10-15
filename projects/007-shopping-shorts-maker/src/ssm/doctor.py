"""설치 점검 (`ssm doctor`).

결과는 ok(통과) / warn(지금은 괜찮지만 나중 단계에 필요) / fail(지금 고쳐야 함) 세 가지.
fail이 하나라도 있으면 M0 완료 기준을 통과하지 못한 것이다.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from ssm import fonts
from ssm.config import AppConfig, app_root, load_config

CORE_PACKAGES = {  # import 이름: pip 패키지 이름
    "typer": "typer", "rich": "rich", "yaml": "PyYAML", "pydantic": "pydantic", "PIL": "pillow",
    "numpy": "numpy", "cv2": "opencv-python-headless", "scenedetect": "scenedetect",
    "edge_tts": "edge-tts", "yt_dlp": "yt-dlp",
}
ML_PACKAGES = {"easyocr": "easyocr", "faster_whisper": "faster-whisper", "open_clip": "open-clip-torch"}
MIN_FREE_GB = 15
MIN_VC_RUNTIME = (14, 40)  # PyTorch·onnxruntime 최신 휠이 요구하는 Visual C++ 런타임 (2022, 17.10 이후)
VC_FIX = "winget install Microsoft.VCRedist.2015+.x64 로 Visual C++ 재배포 패키지를 최신으로 설치하세요 (관리자 권한)."
SETUP_HINT = "setup.bat(Windows) 또는 ./setup.sh를 다시 실행하세요."


@dataclass(frozen=True)
class Check:
    group: str
    name: str
    status: str  # ok | warn | fail
    detail: str
    fix: str = ""


class Probe:
    """외부 환경 조회. 테스트에서 바꿔 끼울 수 있게 한곳에 모았다."""

    def which(self, name: str) -> str | None:
        return shutil.which(name)

    def run(self, cmd: list[str], timeout: int = 30) -> tuple[int, str]:
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               encoding="utf-8", errors="replace")
            return p.returncode, (p.stdout or "") + (p.stderr or "")
        except (OSError, subprocess.SubprocessError) as e:
            return -1, str(e)

    def has_module(self, name: str) -> bool:
        return importlib.util.find_spec(name) is not None

    def python_version(self) -> tuple[int, int, int]:
        return sys.version_info[:3]

    def torch_info(self) -> dict | None:
        """torch가 없으면 None. 있으면 {'version', 'cuda'(bool), 'cuda_version', 'device'}."""
        if not self.has_module("torch"):
            return None
        try:
            import torch
        except Exception as e:  # noqa: BLE001 — 깨진 설치도 사용자에게 보여준다
            return {"version": None, "error": str(e), "cuda": False, "cuda_version": None, "device": None}
        cuda = bool(torch.cuda.is_available())
        return {
            "version": torch.__version__,
            "cuda": cuda,
            "cuda_version": torch.version.cuda,
            "device": torch.cuda.get_device_name(0) if cuda else None,
        }

    def free_gb(self, path: Path) -> float:
        return shutil.disk_usage(path).free / 1024**3

    def vc_runtime(self) -> tuple[int, int] | None:
        """Windows의 Visual C++ 런타임(msvcp140.dll) 버전. Windows가 아니면 None, 없으면 (0, 0)."""
        if sys.platform != "win32":
            return None
        dll = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "msvcp140.dll"
        if not dll.is_file():
            return (0, 0)
        code, out = self.run(["powershell", "-NoProfile", "-Command",
                              f"$v=(Get-Item '{dll}').VersionInfo; '{{0}}.{{1}}' -f $v.FileMajorPart,$v.FileMinorPart"])
        try:
            major, minor = out.strip().split(".")[:2]
            return int(major), int(minor)
        except ValueError:
            return None


def ffmpeg_binary(cfg: AppConfig, probe: Probe) -> str | None:
    if cfg.ffmpeg_path:
        p = cfg.path(cfg.ffmpeg_path)
        return str(p) if p.is_file() else None
    return probe.which("ffmpeg")


def _check_python(probe: Probe) -> Check:
    v = probe.python_version()
    text = ".".join(map(str, v))
    if v < (3, 11):
        return Check("기본", "Python", "fail", f"{text} (3.11 이상 필요)", "Python 3.12를 설치한 뒤 " + SETUP_HINT)
    if v >= (3, 13):
        return Check("기본", "Python", "warn", f"{text} (3.11~3.12 권장: GPU용 PyTorch 호환성)")
    return Check("기본", "Python", "ok", text)


def _check_config() -> tuple[Check, AppConfig | None]:
    try:
        cfg = load_config()
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(str(x) for x in first["loc"])
        return Check("기본", "설정 파일", "fail", f"{where}: {first['msg']}",
                     "config.yaml(또는 config.local.yaml)의 해당 항목을 고치세요."), None
    except (OSError, ValueError) as e:
        return Check("기본", "설정 파일", "fail", str(e), "config.yaml 형식을 확인하세요."), None
    return Check("기본", "설정 파일", "ok", "config.yaml 정상"), cfg


def _check_packages(probe: Probe) -> list[Check]:
    missing = [pip for mod, pip in CORE_PACKAGES.items() if not probe.has_module(mod)]
    checks = [Check("기본", "필수 패키지", "fail", "없음: " + ", ".join(missing), SETUP_HINT) if missing
              else Check("기본", "필수 패키지", "ok", f"{len(CORE_PACKAGES)}개 설치됨")]
    ml_missing = [pip for mod, pip in ML_PACKAGES.items() if not probe.has_module(mod)]
    checks.append(Check("AI 모델", "OCR·음성인식·유사도 패키지", "warn", "없음: " + ", ".join(ml_missing) +
                        " (M3 수집·필터부터 필요)", SETUP_HINT) if ml_missing
                  else Check("AI 모델", "OCR·음성인식·유사도 패키지", "ok", ", ".join(ML_PACKAGES.values())))
    return checks


def nvidia_gpu(probe: Probe) -> str | None:
    """NVIDIA GPU 정보 한 줄. 없으면 None."""
    if not probe.which("nvidia-smi"):
        return None
    code, out = probe.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"])
    return out.strip().splitlines()[0] if code == 0 and out.strip() else None


def _check_gpu(cfg: AppConfig, probe: Probe, gpu: str | None) -> list[Check]:
    has_nvidia = gpu is not None
    checks = []
    if has_nvidia:
        checks.append(Check("GPU", "NVIDIA 드라이버", "ok", gpu))
    else:
        checks.append(Check("GPU", "NVIDIA 드라이버", "warn", "NVIDIA GPU를 찾지 못함 → CPU 모드 (느림)",
                            "GPU가 있다면 NVIDIA 드라이버를 설치·업데이트하세요."))

    torch = probe.torch_info()
    if torch is None:
        status = "fail" if has_nvidia else "warn"
        checks.append(Check("GPU", "PyTorch", status, "설치되지 않음", SETUP_HINT))
    elif torch.get("error"):  # 설치는 됐지만 import가 안 됨 (DLL 오류 등) — M3의 OCR·음성 인식이 동작하지 않는다
        status = "fail" if has_nvidia else "warn"
        checks.append(Check("GPU", "PyTorch", status, f"불러오기 실패: {torch['error'][:120]}",
                            "먼저 " + VC_FIX + " 그래도 안 되면 setup.bat -ReinstallTorch 로 PyTorch를 다시 설치하세요."))
    elif torch["cuda"]:
        checks.append(Check("GPU", "PyTorch CUDA", "ok",
                            f"torch {torch['version']} / CUDA {torch['cuda_version']} / {torch['device']}"))
    elif has_nvidia:
        checks.append(Check("GPU", "PyTorch CUDA", "fail", f"torch {torch['version']}가 GPU를 쓰지 못함 (CPU용 설치)",
                            "setup.bat -ReinstallTorch 로 GPU용 PyTorch를 다시 설치하세요."))
    else:
        checks.append(Check("GPU", "PyTorch", "ok", f"torch {torch['version']} (CPU 모드)"))

    if cfg.device == "cuda" and not (torch and torch["cuda"]):
        checks.append(Check("GPU", "설정 device", "fail", "device: cuda인데 GPU를 쓸 수 없음",
                            "config의 device를 auto로 바꾸거나 GPU용 PyTorch를 설치하세요."))
    return checks


def _check_vc_runtime(probe: Probe) -> list[Check]:
    version = probe.vc_runtime()
    if version is None:
        return []
    text = ".".join(map(str, version))
    if version < MIN_VC_RUNTIME:
        return [Check("기본", "Visual C++ 런타임", "warn",
                      f"{text} (14.40 이상 필요 — 낮으면 PyTorch·OCR이 DLL 오류로 멈춤)", VC_FIX)]
    return [Check("기본", "Visual C++ 런타임", "ok", text)]


def _check_ffmpeg(cfg: AppConfig, probe: Probe, has_nvidia: bool) -> list[Check]:
    ffmpeg = ffmpeg_binary(cfg, probe)
    if not ffmpeg:
        fix = "winget install Gyan.FFmpeg (Windows) / brew install ffmpeg (Mac) 후 창을 새로 여세요."
        if cfg.ffmpeg_path:
            fix = f"config의 ffmpeg_path({cfg.ffmpeg_path}) 경로를 확인하세요."
        return [Check("FFmpeg", "FFmpeg", "fail", "찾을 수 없음", fix)]
    code, out = probe.run([ffmpeg, "-hide_banner", "-version"])
    version = out.split("\n", 1)[0].removeprefix("ffmpeg version ").split(" ")[0] if code == 0 else "?"
    checks = [Check("FFmpeg", "FFmpeg", "ok", f"{version} ({ffmpeg})")]

    ffprobe_name = Path(ffmpeg).name.replace("ffmpeg", "ffprobe")
    ffprobe = str(Path(ffmpeg).with_name(ffprobe_name)) if cfg.ffmpeg_path else probe.which("ffprobe")
    if not ffprobe or (cfg.ffmpeg_path and not Path(ffprobe).is_file()):
        checks.append(Check("FFmpeg", "ffprobe", "fail", "찾을 수 없음", "FFmpeg 전체 패키지(ffprobe 포함)를 설치하세요."))
    else:
        checks.append(Check("FFmpeg", "ffprobe", "ok", ffprobe))

    _, encoders = probe.run([ffmpeg, "-hide_banner", "-encoders"])
    if "libx264" not in encoders:
        checks.append(Check("FFmpeg", "H.264 인코더(libx264)", "fail", "없음",
                            "libx264가 포함된 FFmpeg(예: Gyan.FFmpeg)로 바꾸세요."))
    else:
        checks.append(Check("FFmpeg", "H.264 인코더(libx264)", "ok", "사용 가능"))

    if "h264_nvenc" in encoders:
        code, out = probe.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                               "color=c=black:s=256x256:d=0.2", "-c:v", "h264_nvenc", "-f", "null", "-"])
        if code == 0:
            checks.append(Check("FFmpeg", "GPU 인코더(NVENC)", "ok", "사용 가능 → encoder: auto 시 GPU로 인코딩"))
        elif not has_nvidia:
            checks.append(Check("FFmpeg", "GPU 인코더(NVENC)", "warn", "NVIDIA GPU 없음 → libx264(CPU) 인코딩"))
        else:
            checks.append(Check("FFmpeg", "GPU 인코더(NVENC)", "warn", "목록에는 있으나 실행 실패 → libx264 사용",
                                "NVIDIA 드라이버를 업데이트하면 쓸 수 있습니다."))
    else:
        status = "fail" if cfg.video.encoder == "h264_nvenc" else "warn"
        checks.append(Check("FFmpeg", "GPU 인코더(NVENC)", status, "없음 → libx264(CPU) 인코딩"))
    return checks


def _check_fonts() -> Check:
    bad = [f"{f.filename}({s})" for f in fonts.FONTS if (s := fonts.font_status(f)) != "ok"]
    if bad:
        return Check("에셋", "폰트", "fail", "문제: " + ", ".join(bad), "ssm fonts 를 실행해 다시 받으세요.")
    return Check("에셋", "폰트", "ok", f"{len(fonts.FONTS)}개 (Pretendard, Black Han Sans)")


def _check_storage(cfg: AppConfig, probe: Probe) -> list[Check]:
    root = cfg.path(cfg.workspace_dir)
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=root, prefix=".write-test-", delete=True) as f:
            f.write("한글 테스트".encode())
    except OSError as e:
        return [Check("작업 폴더", "쓰기 권한", "fail", f"{root}: {e}", "workspace_dir 경로를 확인하세요.")]
    checks = [Check("작업 폴더", "쓰기 권한", "ok", str(root))]
    free = probe.free_gb(root)
    if free < MIN_FREE_GB:
        checks.append(Check("작업 폴더", "여유 공간", "warn", f"{free:.1f}GB (권장 {MIN_FREE_GB}GB 이상)"))
    else:
        checks.append(Check("작업 폴더", "여유 공간", "ok", f"{free:.0f}GB"))
    return checks


def _check_cookies(cfg: AppConfig) -> Check:
    if not cfg.collector.cookies_file:
        return Check("수집", "부계정 쿠키", "warn", "설정 안 됨 (M3 수집부터 필요)", "docs/cookies.md 참고")
    path = cfg.path(cfg.collector.cookies_file)
    if not path.is_file():
        return Check("수집", "부계정 쿠키", "warn", f"{cfg.collector.cookies_file} 없음 (M3 수집부터 필요)",
                     "docs/cookies.md를 보고 부계정 쿠키를 저장하세요.")
    return Check("수집", "부계정 쿠키", "ok", cfg.collector.cookies_file)


def run_checks(probe: Probe | None = None) -> list[Check]:
    probe = probe or Probe()
    checks = [_check_python(probe)]
    config_check, cfg = _check_config()
    checks.append(config_check)
    checks += _check_packages(probe)
    checks += _check_vc_runtime(probe)
    if cfg is None:  # 설정이 깨지면 나머지는 기본값으로라도 점검한다
        cfg = AppConfig()
    gpu = nvidia_gpu(probe)
    checks += _check_gpu(cfg, probe, gpu)
    checks += _check_ffmpeg(cfg, probe, gpu is not None)
    checks.append(_check_fonts())
    checks += _check_storage(cfg, probe)
    checks.append(_check_cookies(cfg))
    return checks


def environment_summary() -> dict:
    return {"root": str(app_root()), "python": sys.executable, "venv": os.getenv("VIRTUAL_ENV") or ""}
