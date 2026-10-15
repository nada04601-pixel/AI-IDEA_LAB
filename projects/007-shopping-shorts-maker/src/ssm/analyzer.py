"""영상 분석 (기획서 Module 1.5) — raw_videos/* → analysis.json.

영상마다 FFmpeg를 한 번만 돌려 장면 전환 시각(scene 점수)과 저해상도 흑백 프레임을 함께 받는다.
(OpenCV·PySceneDetect는 Windows에서 한글 경로 영상을 열지 못해 FFmpeg로 읽는다.)

- 샷: 장면 전환으로 나누고, 긴 샷은 MAX_SHOT_SEC 이하로 쪼갠다 (긴 원본 하나에서도 여러 컷을 뽑을 수 있게).
- 하이라이트 점수: 선명도(Laplacian 분산)·움직임(프레임 차이)·밝기를 모든 샷끼리 비교해 0~1로.
- 고정 글자 영역: 여러 프레임에서 OCR로 글자 위치를 찾고, 자주 반복되는 영역을 자막·워터마크로 본다.
"""

import json
import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import numpy as np

from ssm.config import AppConfig
from ssm.media import Media
from ssm.schemas import Analysis, Shot, TextBox, VideoAnalysis
from ssm.workspace import Workspace

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
SAMPLE_FPS = 4  # 점수 계산용 프레임 간격
FRAME_WIDTH = 540  # 분석용 프레임 가로 크기 (자막 글자를 OCR로 찾을 수 있을 정도)
SCENE_THRESHOLD = 0.3  # FFmpeg scene 점수가 이보다 크면 샷이 바뀐 것으로 본다
MIN_SHOT_SEC = 0.5
MAX_SHOT_SEC = 4.0
SHORT_SHOT_SEC = 1.0  # 이보다 짧은 샷은 점수를 깎는다 (컷으로 쓰기 어렵다)
OCR_FRAMES = 8  # 글자 영역을 찾을 프레임 수 (영상 전체에 고르게)
TEXT_MIN_COVERAGE = 0.4  # 검사 프레임의 이 비율 이상에서 보이면 고정 글자 영역
TEXT_PAD = 0.25  # 가릴 때 글자 높이의 이만큼 여유를 둔다

Box = tuple[int, int, int, int]  # x, y, w, h


class AnalyzeError(Exception):
    """사용자에게 그대로 보여줄 수 있는 분석 단계 오류."""


class TextDetector(Protocol):
    def detect(self, image: np.ndarray) -> list[Box]:
        """흑백 이미지에서 글자 영역 상자 목록."""


class EasyOCRDetector:
    """EasyOCR 글자 위치 검출 (중국어 간체 + 영어). 글자 내용은 읽지 않는다."""

    def __init__(self, gpu: bool):
        import easyocr

        self.reader = easyocr.Reader(["ch_sim", "en"], gpu=gpu, verbose=False)

    def detect(self, image: np.ndarray) -> list[Box]:
        horizontal, free = self.reader.detect(image)
        boxes = [(int(x0), int(y0), int(x1 - x0), int(y1 - y0)) for x0, x1, y0, y1 in horizontal[0]]
        for poly in free[0]:
            xs, ys = [p[0] for p in poly], [p[1] for p in poly]
            boxes.append((int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys))))
        return [b for b in boxes if b[2] > 0 and b[3] > 0]


def load_detector(cfg: AppConfig) -> tuple[TextDetector | None, str]:
    """(검출기, 실패 이유). PyTorch·EasyOCR를 쓸 수 없으면 검출기 없이 진행한다."""
    from ssm.doctor import native_runtime_problem

    if problem := native_runtime_problem():
        return None, problem
    try:
        import torch

        gpu = cfg.device == "cuda" or (cfg.device == "auto" and torch.cuda.is_available())
        return EasyOCRDetector(gpu=gpu), ""
    except Exception as e:  # noqa: BLE001 — DLL 오류·모델 다운로드 실패 등 종류가 다양하다
        return None, f"{type(e).__name__}: {str(e)[:150]}"


def source_videos(ws: Workspace) -> list[Path]:
    folder = ws.path / "raw_videos"
    return sorted(p for p in folder.glob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS)


# ---- 프레임·장면 전환 읽기 ----------------------------------------------------------


def read_frames(media: Media, path: Path, width: int, height: int) -> tuple[list[float], np.ndarray, int, int]:
    """(장면 전환 시각들, 흑백 프레임 배열 [n, h, w], 프레임 가로, 세로)."""
    fw = FRAME_WIDTH
    fh = max(2, int(round(height * fw / width / 2)) * 2)
    # 첫 프레임(eq(n,0))도 항상 내보낸다: 장면 전환이 없는 영상에서도 출력이 비지 않게 (0초는 샷 나누기에서 무시됨)
    graph = (f"[0:v]split[a][b];[a]select='gt(scene,{SCENE_THRESHOLD})+eq(n,0)',showinfo[s];"
             f"[b]fps={SAMPLE_FPS},scale={fw}:{fh},format=gray[f]")
    raw = media.run(["-i", str(path), "-filter_complex", graph, "-map", "[s]", "-f", "null", "-",
                     "-map", "[f]", "-f", "rawvideo", "pipe:1"], what=f"{path.name} 분석")
    cuts = [float(t) for t in re.findall(r"pts_time:\s*([\d.]+)", media.last_stderr)]
    frames = np.frombuffer(raw, dtype=np.uint8)
    n = frames.size // (fw * fh)
    return cuts, frames[: n * fw * fh].reshape(n, fh, fw), fw, fh


def split_shots(cuts: list[float], duration: float) -> list[tuple[float, float]]:
    """장면 전환 시각으로 샷을 나누고, 너무 짧은 샷은 합치고 긴 샷은 쪼갠다."""
    bounds = [0.0]
    for t in sorted(cuts):
        if t - bounds[-1] >= MIN_SHOT_SEC and duration - t >= MIN_SHOT_SEC:
            bounds.append(t)
    bounds.append(duration)
    shots = []
    for a, b in zip(bounds, bounds[1:]):
        n = max(1, math.ceil((b - a) / MAX_SHOT_SEC - 1e-9))
        step = (b - a) / n
        shots += [(round(a + i * step, 3), round(a + (i + 1) * step, 3)) for i in range(n)]
    return shots


# ---- 점수 ---------------------------------------------------------------------


def frame_metrics(frames: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """프레임마다 (선명도, 움직임 0~1, 밝기 0~255)."""
    import cv2

    sharp = np.array([cv2.Laplacian(f, cv2.CV_64F).var() for f in frames])
    diff = np.abs(np.diff(frames.astype(np.int16), axis=0)).mean(axis=(1, 2)) / 255 if len(frames) > 1 else np.zeros(0)
    motion = np.concatenate([diff[:1], diff]) if len(diff) else np.zeros(len(frames))
    return sharp, motion, frames.mean(axis=(1, 2))


def _rank(values: list[float]) -> list[float]:
    """작은 값부터 1/n … 1 (모든 영상의 샷끼리 상대 비교)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    for r, i in enumerate(order, start=1):
        ranks[i] = r / len(values)
    return ranks


def score_shots(raw: list[dict]) -> list[float]:
    """raw: [{'sharpness','motion','brightness','duration'}] → 하이라이트 점수 0~1."""
    if not raw:
        return []
    sharp, motion = _rank([r["sharpness"] for r in raw]), _rank([r["motion"] for r in raw])
    scores = []
    for r, s, m in zip(raw, sharp, motion):
        bright = 1 - min(abs(r["brightness"] - 128) / 128, 1)
        score = 0.45 * s + 0.35 * m + 0.20 * bright
        if r["duration"] < SHORT_SHOT_SEC:
            score *= 0.6
        scores.append(round(min(max(score, 0.0), 1.0), 4))
    return scores


# ---- 고정 글자 영역 -----------------------------------------------------------------


def _same_line(a: Box, b: Box) -> bool:
    """두 상자가 같은 자리의 글자 줄인지 (세로로 절반 이상 겹치고 가로로 겹치거나 가깝다)."""
    (ax, ay, aw, ah), (bx, by, bw, bh) = a, b
    v_overlap = min(ay + ah, by + bh) - max(ay, by)
    gap = max(ax, bx) - min(ax + aw, bx + bw)  # 음수면 가로로 겹침
    return v_overlap >= 0.5 * min(ah, bh) and gap <= 0.5 * max(ah, bh)


def fixed_text_regions(frame_boxes: list[list[Box]], size: tuple[int, int],
                       min_coverage: float = TEXT_MIN_COVERAGE) -> list[tuple[Box, float]]:
    """프레임별 글자 상자 → 여러 프레임에 반복된 영역 [(상자, 등장 비율)]. 글자 내용이 바뀌는 자막도 같은 자리면 묶는다."""
    items = [(i, box) for i, boxes in enumerate(frame_boxes) for box in boxes]
    parent = list(range(len(items)))

    def find(k: int) -> int:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for p in range(len(items)):
        for q in range(p + 1, len(items)):
            if _same_line(items[p][1], items[q][1]):
                parent[find(p)] = find(q)
    groups: dict[int, list[int]] = {}
    for k in range(len(items)):
        groups.setdefault(find(k), []).append(k)

    w_max, h_max = size
    regions = []
    for members in groups.values():
        coverage = len({items[k][0] for k in members}) / max(len(frame_boxes), 1)
        if coverage < min_coverage:
            continue
        x0 = min(items[k][1][0] for k in members)
        y0 = min(items[k][1][1] for k in members)
        x1 = max(items[k][1][0] + items[k][1][2] for k in members)
        y1 = max(items[k][1][1] + items[k][1][3] for k in members)
        pad = TEXT_PAD * max(items[k][1][3] for k in members)
        x0, y0 = max(0, int(x0 - pad)), max(0, int(y0 - pad))
        x1, y1 = min(w_max, int(math.ceil(x1 + pad))), min(h_max, int(math.ceil(y1 + pad)))
        regions.append(((x0, y0, x1 - x0, y1 - y0), round(coverage, 3)))
    return sorted(regions, key=lambda r: (r[0][1], r[0][0]))


# ---- 단계 실행 ------------------------------------------------------------------


def analyze_video(media: Media, ws: Workspace, path: Path, detector: TextDetector | None) -> tuple[VideoAnalysis, list[dict]]:
    info = media.probe_video(path)
    cuts, frames, fw, fh = read_frames(media, path, info.width, info.height)
    if len(frames) == 0:
        raise AnalyzeError(f"{path.name}에서 프레임을 읽지 못했습니다 — 영상 파일이 손상됐는지 확인하세요.")
    duration = info.duration or len(frames) / SAMPLE_FPS
    sharp, motion, bright = frame_metrics(frames)

    raw = []
    for a, b in split_shots(cuts, duration):
        idx = [i for i in range(len(frames)) if a <= i / SAMPLE_FPS < b] or \
              [min(int(a * SAMPLE_FPS), len(frames) - 1)]
        raw.append({"start": a, "end": b, "duration": b - a, "sharpness": float(sharp[idx].mean()),
                    "motion": float(motion[idx].mean()), "brightness": float(bright[idx].mean())})

    boxes: list[TextBox] = []
    if detector is not None:
        picks = np.linspace(0, len(frames) - 1, num=min(OCR_FRAMES, len(frames))).round().astype(int)
        found = [detector.detect(frames[i]) for i in picks]
        sx, sy = info.width / fw, info.height / fh  # 분석 프레임 → 원본 좌표
        for (x, y, w, h), coverage in fixed_text_regions(found, (fw, fh)):
            boxes.append(TextBox(x=int(x * sx), y=int(y * sy), w=int(math.ceil(w * sx)), h=int(math.ceil(h * sy)),
                                 coverage=coverage))
    video = VideoAnalysis(file=path.relative_to(ws.path).as_posix(), width=info.width, height=info.height,
                          duration=round(duration, 3), shots=[], text_boxes=boxes,
                          ocr="ok" if detector is not None else "unavailable")
    return video, raw


def run_analyze(ws: Workspace, cfg: AppConfig | None = None, detector: TextDetector | None = None,
                load: Callable[[AppConfig], tuple[TextDetector | None, str]] | None = None,
                log: Callable[[str], None] = print) -> Analysis:
    cfg = cfg or ws.config()
    videos = source_videos(ws)
    if not videos:
        raise AnalyzeError("raw_videos/에 원본 영상이 없습니다 → `ssm add 영상.mp4`로 영상을 넣으세요.")
    media = Media(cfg)

    previous: dict[str, str] = {}  # 사용자가 analysis.json에서 바꾼 등급(mood 등)은 다시 분석해도 유지한다
    out = ws.path / "analysis.json"
    if out.is_file():
        try:
            previous = {v["file"]: v.get("grade", "same_product")
                        for v in json.loads(out.read_text(encoding="utf-8"))["videos"]}
        except (ValueError, KeyError, TypeError):
            previous = {}
    selected = ws.path / "selected.json"  # 수집 단계가 정한 등급이 우선 (사용자는 selected.json에서 바꾼다)
    if selected.is_file():
        try:
            previous.update({v["file"]: v["grade"]
                             for v in json.loads(selected.read_text(encoding="utf-8"))["videos"]})
        except (ValueError, KeyError, TypeError):
            pass

    if detector is None:
        log("  글자 영역 검출기(OCR) 준비 중… (처음에는 모델을 내려받아 시간이 걸립니다)")
        detector, reason = (load or load_detector)(cfg)
        if detector is None:
            log(f"[주의] OCR을 쓸 수 없어 원본 자막 위치를 찾지 못했습니다 ({reason}).\n"
                "  → 원본 자막이 가려지지 않고 보일 수 있습니다. `ssm doctor`로 PyTorch 상태를 확인하세요.")

    results, raws = [], []
    for path in videos:
        video, raw = analyze_video(media, ws, path, detector)
        video.grade = previous.get(video.file, "same_product")
        results.append(video)
        raws.append(raw)

    scores = score_shots([r for raw in raws for r in raw])
    k = 0
    for video, raw in zip(results, raws):
        stem = Path(video.file).stem
        for i, r in enumerate(raw, start=1):
            video.shots.append(Shot(id=f"{stem}-{i:03d}", start=r["start"], end=r["end"], score=scores[k],
                                    sharpness=round(r["sharpness"], 2), motion=round(r["motion"], 4),
                                    brightness=round(r["brightness"], 1)))
            k += 1
        log(f"  {video.file}: {video.duration:.1f}초 · 샷 {len(video.shots)}개 · 고정 글자 영역 {len(video.text_boxes)}개"
            f" · 등급 {video.grade}")

    analysis = Analysis(videos=results)
    out.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
    ws.mark_done("analyze")
    return analysis
