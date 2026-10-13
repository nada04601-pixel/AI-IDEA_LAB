"""자동 품질 검사.

errors   → 실패. 업로드하지 않는다.
warnings → 검수 대상(review). 영상은 만들지만 자동 업로드는 하지 않는다.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

CHANGE_THRESHOLD = 28  # 채널 차이가 이 값보다 크면 '바뀐 픽셀'
MIN_CHANGED_FRACTION = 0.04  # 정답 상자 안에서 바뀐 픽셀 비율 하한 (미만이면 너무 작은 차이)
MIN_CHANGED_PIXELS = 350
MAX_OUTSIDE_FRACTION = 0.0015  # 정답 상자 밖에서 바뀐 픽셀 비율 상한 (정렬·의도치 않은 변화)
MIN_BOX_SIDE = 0.03  # 정답 상자 짧은 변 하한 (이미지 짧은 변 대비)
CIRCLE_SCALE = 1.18  # 영상에 그리는 정답 원은 상자를 이만큼 키운 타원


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        self.errors += other.errors
        self.warnings += other.warnings
        self.metrics.update(other.metrics)
        return self


def circle_box(b: list[float], scale: float = CIRCLE_SCALE) -> tuple[float, float, float, float]:
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    # 상자(이미 여백 포함)를 살짝 키운 타원. 영상의 정답 원과 같은 계산을 쓴다.
    rx, ry = (b[2] - b[0]) / 2 * scale, (b[3] - b[1]) / 2 * scale
    return cx - rx, cy - ry, cx + rx, cy + ry


def _ellipses_overlap(a, b) -> bool:
    ax, ay, arx, ary = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2, (a[2] - a[0]) / 2, (a[3] - a[1]) / 2
    bx, by, brx, bry = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, (b[2] - b[0]) / 2, (b[3] - b[1]) / 2
    # 중심을 잇는 방향으로 두 타원의 반지름 합과 거리 비교 (근사)
    dx, dy = bx - ax, by - ay
    dist = math.hypot(dx, dy)
    if dist == 0:
        return True
    ux, uy = dx / dist, dy / dist
    ra = 1 / math.sqrt((ux / arx) ** 2 + (uy / ary) ** 2)
    rb = 1 / math.sqrt((ux / brx) ** 2 + (uy / bry) ** 2)
    return dist < ra + rb


def validate_puzzle(puzzle: dict, original_path: Path, modified_path: Path) -> ValidationResult:
    r = ValidationResult()
    for p in (original_path, modified_path):
        if not p.exists():
            r.errors.append(f"이미지 파일이 없습니다: {p.name}")
    if r.errors:
        return r
    a = Image.open(original_path).convert("RGB")
    b = Image.open(modified_path).convert("RGB")
    if a.size != b.size:
        r.errors.append(f"원본과 수정본 크기가 다릅니다: {a.size} vs {b.size}")
        return r
    w, h = a.size

    diffs = puzzle.get("differences", [])
    expected = puzzle.get("difference_count")
    if expected != len(diffs):
        r.errors.append(f"difference_count({expected})와 실제 정답 개수({len(diffs)})가 다릅니다")
    ids = [d.get("id") for d in diffs]
    if len(set(ids)) != len(ids):
        r.errors.append("정답 id가 중복됩니다")

    delta = np.abs(np.asarray(a, int) - np.asarray(b, int)).max(axis=2) > CHANGE_THRESHOLD
    covered = np.zeros_like(delta)
    px_boxes = []
    for d in diffs:
        bn = d.get("bbox_normalized")
        if not bn or len(bn) != 4 or not all(0 <= v <= 1 for v in bn) or bn[0] >= bn[2] or bn[1] >= bn[3]:
            r.errors.append(f"정답 {d.get('id')}: 좌표가 올바르지 않습니다 {bn}")
            continue
        x0, y0, x1, y1 = int(bn[0] * w), int(bn[1] * h), int(math.ceil(bn[2] * w)), int(math.ceil(bn[3] * h))
        px_boxes.append((d["id"], (x0, y0, x1, y1)))
        covered[y0:y1, x0:x1] = True
        side = min(x1 - x0, y1 - y0) / min(w, h)
        if side < MIN_BOX_SIDE:
            r.warnings.append(f"정답 {d['id']}({d.get('label')}): 차이 영역이 너무 작습니다")
        region = delta[y0:y1, x0:x1]
        changed = int(region.sum())
        frac = changed / max(1, region.size)
        r.metrics[f"diff{d['id']}_changed_fraction"] = round(frac, 4)
        if changed == 0:
            r.errors.append(f"정답 {d['id']}({d.get('label')}): 두 그림이 이 영역에서 똑같습니다")
        elif frac < MIN_CHANGED_FRACTION or changed < MIN_CHANGED_PIXELS:
            r.warnings.append(f"정답 {d['id']}({d.get('label')}): 바뀐 부분이 작아 찾기 어려울 수 있습니다 ({frac:.1%})")

    outside = delta & ~covered
    out_frac = float(outside.sum()) / delta.size
    r.metrics["outside_changed_fraction"] = round(out_frac, 5)
    if out_frac > MAX_OUTSIDE_FRACTION:
        r.errors.append(f"정답 영역 밖에서 그림이 달라졌습니다 ({out_frac:.3%}) — 정렬 불량 또는 숨은 차이")

    # 정답 원끼리 겹침, 화면 밖으로 나감
    circles = [(i, circle_box(bx)) for i, bx in px_boxes]
    for k in range(len(circles)):
        i, c = circles[k]
        if c[0] < -w * 0.02 or c[1] < -h * 0.02 or c[2] > w * 1.02 or c[3] > h * 1.02:
            r.warnings.append(f"정답 {i}: 표시 원이 그림 밖으로 나갑니다")
        for m in range(k + 1, len(circles)):
            j, c2 = circles[m]
            if _ellipses_overlap(c, c2):
                r.warnings.append(f"정답 {i}과 {j}의 표시 원이 겹칩니다")
    return r


def ffprobe(path: Path) -> dict:
    exe = shutil.which("ffprobe")
    if not exe:
        raise RuntimeError("ffprobe를 찾을 수 없습니다 (FFmpeg 설치 필요)")
    out = subprocess.run([exe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe 실패: {out.stderr.strip()[:300]}")
    return json.loads(out.stdout)


def validate_video(path: Path, expected_duration: float, tolerance: float = 0.6) -> ValidationResult:
    r = ValidationResult()
    if not path.exists():
        r.errors.append("영상 파일이 없습니다")
        return r
    size = path.stat().st_size
    r.metrics["video_bytes"] = size
    if size < 50_000:
        r.errors.append(f"영상 파일이 너무 작습니다 ({size} bytes)")
    if size > 200 * 1024 * 1024:
        r.errors.append("영상 파일이 너무 큽니다 (200MB 초과)")
    try:
        info = ffprobe(path)
    except Exception as e:  # noqa: BLE001
        r.errors.append(str(e))
        return r
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    au = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not v:
        r.errors.append("영상 스트림이 없습니다")
        return r
    if (v.get("width"), v.get("height")) != (1080, 1920):
        r.errors.append(f"해상도가 1080x1920이 아닙니다: {v.get('width')}x{v.get('height')}")
    if v.get("codec_name") != "h264":
        r.errors.append(f"영상 코덱이 h264가 아닙니다: {v.get('codec_name')}")
    if v.get("pix_fmt") != "yuv420p":
        r.warnings.append(f"픽셀 형식이 yuv420p가 아닙니다: {v.get('pix_fmt')}")
    if not au:
        r.warnings.append("오디오 스트림이 없습니다")
    dur = float(info.get("format", {}).get("duration", 0))
    r.metrics["duration"] = round(dur, 2)
    if abs(dur - expected_duration) > tolerance:
        r.errors.append(f"영상 길이가 예상({expected_duration:.1f}s)과 다릅니다: {dur:.2f}s")
    if dur > 60:
        r.errors.append("Shorts 권장 길이(60초)를 넘습니다")
    return r
