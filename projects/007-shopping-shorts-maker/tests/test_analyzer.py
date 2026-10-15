import json

import numpy as np
import pytest

from ssm import analyzer
from ssm.analyzer import AnalyzeError, fixed_text_regions, run_analyze, score_shots, split_shots
from ssm.schemas import Analysis, Source
from ssm.workspace import Workspace, import_local_videos

from conftest import make_video, needs_ffmpeg


class WhiteBoxDetector:
    """흰색으로 꽉 찬 띠를 '글자'로 보는 가짜 OCR (테스트 영상의 자막 띠를 찾는다)."""

    def detect(self, image):
        mask = image > 240
        rows = np.where(mask.mean(axis=1) > 0.4)[0]
        if len(rows) == 0:
            return []
        cols = np.where(mask[rows].mean(axis=0) > 0.8)[0]
        if len(cols) == 0:
            return []
        return [(int(cols[0]), int(rows[0]), int(cols[-1] - cols[0] + 1), int(rows[-1] - rows[0] + 1))]


def test_split_shots_merges_short_and_splits_long():
    assert split_shots([3.0, 6.0], 9.0) == [(0.0, 3.0), (3.0, 6.0), (6.0, 9.0)]
    assert split_shots([0.2, 3.0, 3.3, 8.8], 9.0) == [(0.0, 3.0), (3.0, 6.0), (6.0, 9.0)]  # 0.5초 미만 샷은 합침
    assert split_shots([], 10.0) == [(0.0, 3.333), (3.333, 6.667), (6.667, 10.0)]  # 4초 넘는 샷은 쪼갬


def test_score_shots_prefers_sharp_moving_and_long():
    base = {"brightness": 128, "duration": 3.0}
    scores = score_shots([{**base, "sharpness": 10, "motion": 0.01}, {**base, "sharpness": 500, "motion": 0.2},
                          {**base, "sharpness": 500, "motion": 0.2, "duration": 0.6}])
    assert scores[1] > scores[0] and scores[1] > scores[2]
    assert all(0 <= s <= 1 for s in scores)


def test_fixed_text_regions_groups_changing_subtitles():
    # 아래쪽 자막: 글자 내용(폭)이 프레임마다 바뀌지만 같은 자리 → 한 영역. 위쪽 상자는 한 번만 보임 → 제외
    frames = [[(100, 800, 300, 40)], [(80, 805, 360, 38), (10, 10, 50, 20)], [(120, 798, 250, 42)], []]
    regions = fixed_text_regions(frames, (540, 960))
    assert len(regions) == 1
    (x, y, w, h), coverage = regions[0]
    assert coverage == 0.75
    assert x <= 80 and x + w >= 440 and y <= 798 and y + h >= 840  # 모든 자막 위치를 덮는다


@needs_ffmpeg
def test_run_analyze_finds_shots_and_subtitle_box(home, tmp_path):
    ws = Workspace.create(Source(type="local", files=[]))
    import_local_videos(ws, [make_video(tmp_path / "a.mp4", "720x1280", 6, shots=2, box=True),
                             make_video(tmp_path / "b.mp4", "640x360", 3)])
    analysis = run_analyze(ws, detector=WhiteBoxDetector(), log=lambda m: None)
    assert ws.status("analyze") == "done"
    a, b = analysis.videos
    assert (a.width, a.height) == (720, 1280) and a.ocr == "ok"
    assert [round(s.start, 1) for s in a.shots] == [0.0, 3.0]  # 장면 전환을 찾았다
    assert len(a.text_boxes) == 1
    box = a.text_boxes[0]  # 원본 좌표: x=144, y=1024, w=432, h=106
    assert box.x <= 144 and box.x + box.w >= 576 and box.y <= 1024 and box.y + box.h >= 1130 and box.y > 900
    assert b.text_boxes == [] and b.shots[0].id == "02-001"

    # 사용자가 등급을 mood로 바꾸면 다시 분석해도 유지된다. 영상을 추가하면 analyze가 다시 필요해진다
    data = json.loads((ws.path / "analysis.json").read_text(encoding="utf-8"))
    data["videos"][1]["grade"] = "mood"
    (ws.path / "analysis.json").write_text(json.dumps(data), encoding="utf-8")
    import_local_videos(ws, [make_video(tmp_path / "c.mp4", seconds=1)])
    assert ws.status("analyze") == "stale"
    analysis = run_analyze(ws, detector=WhiteBoxDetector(), log=lambda m: None)
    assert [v.grade for v in analysis.videos] == ["same_product", "mood", "same_product"]


@needs_ffmpeg
def test_run_analyze_without_ocr(home, tmp_path):
    ws = Workspace.create(Source(type="local", files=[]))
    with pytest.raises(AnalyzeError, match="ssm add"):
        run_analyze(ws, log=lambda m: None)
    import_local_videos(ws, [make_video(tmp_path / "a.mp4")])
    logs = []
    analysis = run_analyze(ws, load=lambda cfg: (None, "OSError: DLL"), log=logs.append)
    assert analysis.videos[0].ocr == "unavailable"
    assert any("OCR을 쓸 수 없어" in m for m in logs)
    assert Analysis.model_validate_json((ws.path / "analysis.json").read_text(encoding="utf-8")) == analysis
