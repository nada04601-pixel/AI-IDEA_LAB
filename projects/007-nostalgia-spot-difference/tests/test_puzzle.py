import json
import random

import numpy as np
import pytest
from PIL import Image

from src.config import difference_count
from src.difference_editor import boxes_conflict, make_raster_differences, make_scene_differences
from src.scenes import Scene, build_scene, render_scene
from src.validator import validate_puzzle

TEMPLATES = [("village", None), ("village", "laundry"), ("kitchen", None), ("kitchen", "morning"),
             ("market", None), ("rainy_road", None), ("corner_store", None)]


def _puzzle(diffs, w, h, n):
    return {"topic": "테스트", "difficulty": "normal", "difference_count": n,
            "differences": [d.to_json(w, h) for d in diffs]}


def test_scene_render_is_deterministic(font_path):
    a = render_scene(build_scene("village", 5, None, font_path))
    b = render_scene(build_scene("village", 5, None, font_path))
    assert np.array_equal(np.asarray(a), np.asarray(b))


def test_scene_roundtrip_dict(font_path):
    s = build_scene("market", 3, None, font_path)
    s2 = Scene.from_dict(json.loads(json.dumps(s.to_dict())))
    assert np.array_equal(np.asarray(render_scene(s)), np.asarray(render_scene(s2)))


@pytest.mark.parametrize("template,variant", TEMPLATES)
@pytest.mark.parametrize("difficulty", ["easy", "normal", "hard"])
def test_scene_differences_pass_validation(tmp_path, font_path, template, variant, difficulty):
    n = difference_count(difficulty)
    scene = build_scene(template, 11, variant, font_path)
    a, b, diffs, _ = make_scene_differences(scene, n, random.Random(11))
    assert len(diffs) == n
    assert sorted(d.id for d in diffs) == list(range(1, n + 1))
    assert a.size == b.size == (1200, 840)
    for i, d in enumerate(diffs):
        for e in diffs[i + 1:]:
            assert not boxes_conflict(d.bbox, e.bbox, 0), "정답끼리 겹치면 안 됨"
    pa, pb = tmp_path / "a.png", tmp_path / "b.png"
    a.save(pa)
    b.save(pb)
    res = validate_puzzle(_puzzle(diffs, *a.size, n), pa, pb)
    assert res.ok, res.errors


@pytest.mark.parametrize("seed", range(12))
def test_many_seeds_have_no_errors(tmp_path, font_path, seed):
    template, variant = TEMPLATES[seed % len(TEMPLATES)]
    scene = build_scene(template, seed, variant, font_path)
    a, b, diffs, _ = make_scene_differences(scene, 5, random.Random(seed))
    a.save(tmp_path / "a.png")
    b.save(tmp_path / "b.png")
    res = validate_puzzle(_puzzle(diffs, *a.size, 5), tmp_path / "a.png", tmp_path / "b.png")
    assert res.ok, res.errors


def test_diff_types_are_varied(font_path):
    scene = build_scene("corner_store", 2, None, font_path)
    _, _, diffs, _ = make_scene_differences(scene, 5, random.Random(2))
    assert len({d.type for d in diffs}) >= 3


def test_validator_catches_count_mismatch(tmp_path, font_path):
    scene = build_scene("kitchen", 1, None, font_path)
    a, b, diffs, _ = make_scene_differences(scene, 5, random.Random(1))
    a.save(tmp_path / "a.png")
    b.save(tmp_path / "b.png")
    p = _puzzle(diffs[:4], *a.size, 5)
    assert any("difference_count" in e for e in validate_puzzle(p, tmp_path / "a.png", tmp_path / "b.png").errors)


def test_validator_catches_hidden_change_and_size_mismatch(tmp_path, font_path):
    scene = build_scene("kitchen", 1, None, font_path)
    a, b, diffs, _ = make_scene_differences(scene, 3, random.Random(1))
    # 정답에 없는 곳을 바꾸면 실패해야 함
    b2 = b.copy()
    b2.paste((255, 0, 255), (0, 0, 120, 120))
    a.save(tmp_path / "a.png")
    b2.save(tmp_path / "b.png")
    res = validate_puzzle(_puzzle(diffs, *a.size, 3), tmp_path / "a.png", tmp_path / "b.png")
    assert any("정답 영역 밖" in e for e in res.errors)
    # 크기가 다르면 실패
    b.resize((1000, 700)).save(tmp_path / "c.png")
    res = validate_puzzle(_puzzle(diffs, *a.size, 3), tmp_path / "a.png", tmp_path / "c.png")
    assert any("크기" in e for e in res.errors)


def test_validator_catches_unchanged_answer(tmp_path, font_path):
    scene = build_scene("village", 4, None, font_path)
    a, _, diffs, _ = make_scene_differences(scene, 3, random.Random(4))
    a.save(tmp_path / "a.png")
    a.save(tmp_path / "b.png")
    res = validate_puzzle(_puzzle(diffs, *a.size, 3), tmp_path / "a.png", tmp_path / "b.png")
    assert any("똑같습니다" in e for e in res.errors)


def test_raster_differences(tmp_path, font_path):
    base = render_scene(build_scene("market", 9, None, font_path))
    a, b, diffs = make_raster_differences(base, 5, random.Random(9))
    assert len(diffs) == 5
    a.save(tmp_path / "a.png")
    b.save(tmp_path / "b.png")
    res = validate_puzzle(_puzzle(diffs, *a.size, 5), tmp_path / "a.png", tmp_path / "b.png")
    assert res.ok, res.errors


def test_raster_handles_other_aspect(font_path):
    img = Image.new("RGB", (800, 1200), (200, 180, 150))
    rng = np.random.default_rng(0)
    arr = (rng.random((1200, 800, 3)) * 255).astype("uint8")
    img = Image.fromarray(arr)
    a, b, diffs = make_raster_differences(img, 3, random.Random(0))
    assert a.size == b.size == (800, 1200)
    assert len(diffs) == 3
