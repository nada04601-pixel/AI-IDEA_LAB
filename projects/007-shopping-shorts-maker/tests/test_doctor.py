import hashlib

import pytest

from ssm import doctor, fonts
from ssm.doctor import Probe


class FakeProbe(Probe):
    def __init__(self, gpu=True, torch_cuda=True, torch=True, nvenc_ok=True, ffmpeg=True, py=(3, 12, 3)):
        self.gpu, self.torch_cuda, self.torch, self.nvenc_ok, self.ffmpeg, self.py = (
            gpu, torch_cuda, torch, nvenc_ok, ffmpeg, py)

    def which(self, name):
        if name == "nvidia-smi":
            return "nvidia-smi" if self.gpu else None
        if name in ("ffmpeg", "ffprobe"):
            return f"/bin/{name}" if self.ffmpeg else None
        return None

    def run(self, cmd, timeout=30):
        if cmd[0] == "nvidia-smi":
            return 0, "NVIDIA GeForce RTX 4060, 560.94, 8188 MiB\n"
        if "-version" in cmd:
            return 0, "ffmpeg version 7.1-full_build Copyright\n"
        if "-encoders" in cmd:
            return 0, " V....D libx264  H.264\n V....D h264_nvenc  NVIDIA NVENC\n"
        return (0, "") if self.nvenc_ok else (1, "Cannot load nvcuda.dll")

    def has_module(self, name):
        return True

    def python_version(self):
        return self.py

    def torch_info(self):
        if not self.torch:
            return None
        return {"version": "2.14.1+cu128" if self.torch_cuda else "2.14.1+cpu", "cuda": self.torch_cuda,
                "cuda_version": "12.8" if self.torch_cuda else None,
                "device": "NVIDIA GeForce RTX 4060" if self.torch_cuda else None}

    def free_gb(self, path):
        return 100.0

    def vc_runtime(self):
        return getattr(self, "vc", (14, 44))


@pytest.fixture
def with_fonts(home, monkeypatch):
    """체크섬이 맞는 가짜 폰트 파일을 만든다."""
    fake = []
    for f in fonts.FONTS:
        data = f"font:{f.filename}".encode()
        fake.append(fonts.Font(f.filename, f.url, hashlib.sha256(data).hexdigest(), f.license))
        (home / "assets/fonts").mkdir(parents=True, exist_ok=True)
        (home / "assets/fonts" / f.filename).write_bytes(data)
    monkeypatch.setattr(fonts, "FONTS", fake)


def by_name(checks):
    return {c.name: c for c in checks}


def failures(checks):
    return [c.name for c in checks if c.status == "fail"]


def test_windows_gpu_pc_passes(with_fonts):
    checks = by_name(doctor.run_checks(FakeProbe()))
    assert failures(checks.values()) == []
    assert "RTX 4060" in checks["PyTorch CUDA"].detail
    assert checks["GPU 인코더(NVENC)"].status == "ok"


def test_gpu_pc_with_cpu_torch_fails(with_fonts):
    checks = doctor.run_checks(FakeProbe(torch_cuda=False))
    assert failures(checks) == ["PyTorch CUDA"]
    assert "ReinstallTorch" in by_name(checks)["PyTorch CUDA"].fix


def test_gpu_pc_without_torch_fails(with_fonts):
    assert failures(doctor.run_checks(FakeProbe(torch=False))) == ["PyTorch"]


def test_cpu_only_pc_passes_with_warnings(with_fonts):
    checks = by_name(doctor.run_checks(FakeProbe(gpu=False, torch_cuda=False, nvenc_ok=False)))
    assert failures(checks.values()) == []
    assert checks["NVIDIA 드라이버"].status == "warn"
    assert "GPU 없음" in checks["GPU 인코더(NVENC)"].detail


def test_device_cuda_without_gpu_fails(with_fonts, home):
    (home / "config.local.yaml").write_text("device: cuda\n", encoding="utf-8")
    assert "설정 device" in failures(doctor.run_checks(FakeProbe(gpu=False, torch_cuda=False)))


def test_missing_ffmpeg_and_fonts_fail(home):
    names = failures(doctor.run_checks(FakeProbe(ffmpeg=False)))
    assert "FFmpeg" in names and "폰트" in names


def test_broken_config_fails(with_fonts, home):
    (home / "config.local.yaml").write_text("video:\n  fps: 25\n", encoding="utf-8")
    checks = by_name(doctor.run_checks(FakeProbe()))
    assert checks["설정 파일"].status == "fail"
    assert "video.fps" in checks["설정 파일"].detail


def test_old_python_fails(with_fonts):
    assert "Python" in failures(doctor.run_checks(FakeProbe(py=(3, 10, 11))))


def test_font_install_verifies_checksum(home, monkeypatch):
    data = b"real font"
    good = fonts.Font("A.otf", "https://x/A.otf", hashlib.sha256(data).hexdigest(), "OFL")
    bad = fonts.Font("B.otf", "https://x/B.otf", "0" * 64, "OFL")
    monkeypatch.setattr(fonts, "FONTS", [good, bad])
    failed = fonts.install_fonts(download=lambda url: data, log=lambda m: None)
    assert failed == ["B.otf"]
    assert fonts.font_status(good) == "ok"
    assert fonts.font_status(bad) == "missing"


class BrokenTorchProbe(FakeProbe):
    def torch_info(self):
        return {"version": None, "error": "[WinError 1114] DLL 초기화 실패", "cuda": False,
                "cuda_version": None, "device": None}


def test_old_vc_runtime_warns(with_fonts):
    probe = FakeProbe()
    probe.vc = (14, 28)
    check = by_name(doctor.run_checks(probe))["Visual C++ 런타임"]
    assert check.status == "warn" and "VCRedist" in check.fix
    assert by_name(doctor.run_checks(FakeProbe()))["Visual C++ 런타임"].status == "ok"


def test_broken_torch_is_not_reported_as_ok(with_fonts):
    checks = by_name(doctor.run_checks(BrokenTorchProbe(gpu=False, nvenc_ok=False)))
    assert checks["PyTorch"].status == "warn" and "DLL" in checks["PyTorch"].detail
    assert "PyTorch" in failures(doctor.run_checks(BrokenTorchProbe(gpu=True)))
