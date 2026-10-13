import numpy as np
import pytest
from PIL import Image

from spotdiff.photo import make_puzzle_from_image
from spotdiff.scene import H, LEVELS, W, _overlaps, make_puzzle


def _check(p, count):
    assert len(p.differences) == count
    a = np.asarray(p.image_a).astype(int)
    b = np.asarray(p.image_b).astype(int)
    assert a.shape == b.shape == (H, W, 3)
    changed = np.abs(a - b).sum(axis=2) > 0
    inside = np.zeros_like(changed)
    for i, d in enumerate(p.differences):
        x0, y0, x1, y1 = d.box
        assert 0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H
        inside[y0:y1, x0:x1] = True
        # 틀린 곳마다 눈에 띌 만큼 바뀐 픽셀이 있어야 한다
        assert (np.abs(a[y0:y1, x0:x1] - b[y0:y1, x0:x1]).sum(axis=2) > 60).sum() >= 40, d
        for other in p.differences[i + 1:]:
            assert not _overlaps(d.box, other.box, 0)
    # 정답 상자 밖은 한 픽셀도 다르면 안 된다
    assert not (changed & ~inside).any()


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("level", [0, 1, 2])
def test_scene_puzzle_differs_only_in_answer_boxes(seed, level):
    _check(make_puzzle(seed, level), LEVELS[level][1])


def test_scene_is_reproducible():
    a, b = make_puzzle(3, 1), make_puzzle(3, 1)
    assert [d.box for d in a.differences] == [d.box for d in b.differences]
    assert a.image_b.tobytes() == b.image_b.tobytes()


def _colorful_image(seed):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:500, 0:800]
    img = np.stack([(x * 0.3) % 255, (y * 0.5) % 255, ((x + y) * 0.2) % 255], axis=2)
    for _ in range(60):  # 알록달록한 사각형들
        cx, cy, s = rng.integers(0, 800), rng.integers(0, 500), rng.integers(20, 90)
        img[cy:cy + s, cx:cx + s] = rng.integers(0, 255, 3)
    return Image.fromarray(img.astype(np.uint8))


@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("level", [0, 1, 2])
def test_photo_puzzle_differs_only_in_answer_boxes(seed, level):
    from spotdiff.photo import LEVELS as PL
    _check(make_puzzle_from_image(_colorful_image(seed), seed, level), PL[level][1])


def test_photo_rejects_flat_image():
    with pytest.raises(RuntimeError):
        make_puzzle_from_image(Image.new("RGB", (800, 600), (120, 120, 120)), 0, 0)
