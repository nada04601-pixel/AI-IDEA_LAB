import json
import shutil

import numpy as np
import pytest
from PIL import Image, ImageDraw
from typer.testing import CliRunner

from ssm.analyzer import run_analyze
from ssm.config import load_config
from ssm.main import app
from ssm.metadata_gen import (HASHTAGS, MetaError, analyze_style_image, build_caption, build_hashtags, check_meta_text,
                              default_meta, effective_style, fit_vertical, hide_text, kmeans_palette, merge_meta,
                              normalize_tag, render_thumbnail, run_meta, youtube_tags)
from ssm.schemas import MetaText, Script, Source, TextBox, ThumbnailText
from ssm.scripter import load_banned
from ssm.subtitle import SAFE_BOTTOM, SAFE_RIGHT, SAFE_TOP
from ssm.workspace import Workspace, import_local_videos

from conftest import PROJECT, make_video, needs_ffmpeg
from test_analyzer import WhiteBoxDetector

FONT = PROJECT / "assets/fonts/BlackHanSans-Regular.ttf"
needs_font = pytest.mark.skipif(not FONT.is_file(), reason="폰트가 없음 (ssm fonts)")

SCRIPT = {
    "version": 1, "preset": "curiosity", "target_duration_sec": 15,
    "product": {"name": "접이식 실리콘 전기포트", "features": ["접으면 5cm", "프리볼트", "가벼움"], "price_hint": "2만원대"},
    "sentences": [
        {"id": "s1", "section": "hook", "text": "아직도 무거운 포트 들고 다니세요?", "emphasis": ["무거운 포트"]},
        {"id": "s2", "section": "demo", "text": "이건 접으면 5센티예요.", "emphasis": ["5센티"]},
        {"id": "s3", "section": "cta", "text": "궁금하시면 댓글에 '링크' 남겨주세요!", "emphasis": ["링크"]},
    ],
    "thumbnail_text": {"top": "여행 필수템", "bottom": "접히는 전기포트"},
}
META = {"version": 1, "category": "travel", "titles": ["출장 갈 때 포트 고민 끝", "접히는 전기포트 후기"],
        "thumbnail_texts": [{"top": "두께 5cm", "bottom": "접으면 이만큼"}],
        "summary": ["✔ 접으면 두께 5cm", "✔ 프리볼트"], "hashtags": ["접이식전기포트", "#여행 포트", "출장템"]}
AD = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."


def close(hex_color: str, rgb: tuple[int, int, int], tol: int = 24) -> bool:
    value = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return sum(abs(x - y) for x, y in zip(value, rgb)) <= tol


def script() -> Script:
    return Script.model_validate(SCRIPT)


# ---- 문구 ------------------------------------------------------------------------


def test_default_and_merged_meta():
    base = default_meta(script())
    assert len(base.thumbnail_texts) == 3 and base.thumbnail_texts[0].top == "여행 필수템"
    assert base.thumbnail_texts[1].top == "무거운 포트"  # 첫 강조어
    assert base.titles[0] == "아직도 무거운 포트 들고 다니세요?" and base.summary[0] == "✔ 접으면 5cm"

    merged, filled = merge_meta(script(), MetaText.model_validate(META))
    assert filled == []
    assert merged.titles == META["titles"]  # Claude가 쓴 건 그대로
    assert [t.top for t in merged.thumbnail_texts] == ["두께 5cm", "여행 필수템", "무거운 포트"]  # 모자란 안만 채움
    assert merge_meta(script(), None)[1] == ["meta.json 전체"]


def test_check_meta_text(home):
    rules = load_banned(load_config())
    bad = MetaText(titles=["역대 최저가 포트", "가" * 99], hashtags=["다이어트효과"],
                   thumbnail_texts=[ThumbnailText(top="100% 효과", bottom="포트")])
    errors = "\n".join(check_meta_text(bad, rules))
    assert "titles: 금지 표현 '최저가'" in errors and "100자" in errors
    assert "hashtags: 금지 표현" in errors and "thumbnail_texts: 금지 표현" in errors
    assert check_meta_text(MetaText.model_validate(META), rules) == []


def test_hashtags_and_caption():
    assert normalize_tag("#여행 포트") == "#여행포트" and normalize_tag("  ") is None and normalize_tag("#!!") is None
    general = ["쇼핑", "추천템", "꿀템", "살림템", "생활꿀팁", "쇼핑하울", "아이디어상품", "신박한물건", "가성비템", "내돈내산"]
    tags = build_hashtags(["접이식전기포트", "#여행 포트"], ["여행필수템", "여행용품", "꿀템"], general)
    assert tags[:3] == ["#광고", "#접이식전기포트", "#여행포트"]
    assert HASHTAGS[0] <= len(tags) <= HASHTAGS[1] and len(set(tags)) == len(tags)
    many = build_hashtags([f"상품{i}" for i in range(10)], [f"분류{i}" for i in range(10)], general)
    assert len(many) == HASHTAGS[1]
    assert youtube_tags(["a", "b", "c", "d"]) == ["#shorts", "#광고", "#a", "#b", "#c"]

    meta = MetaText.model_validate(META)
    caption = build_caption(script(), meta, AD, tags, youtube_tags(meta.hashtags))
    common, youtube = caption.split("========== 유튜브 쇼츠 ==========")
    assert common.splitlines()[1] == AD  # 광고 문구가 본문 첫 줄
    assert youtube.split("[설명]\n")[1].splitlines()[0] == AD
    assert "1. [광고] 출장 갈 때 포트 고민 끝" in youtube and "#shorts" in youtube
    assert "아직도 무거운 포트 들고 다니세요?" in common and "궁금하시면 댓글에" in common
    assert "2만원대" in caption


# ---- 이미지 -----------------------------------------------------------------------


def test_fit_vertical_and_hide_text():
    land = Image.new("RGB", (1280, 720), (200, 20, 20))
    assert fit_vertical(land).size == (1080, 1920) and fit_vertical(Image.new("RGB", (720, 1280))).size == (1080, 1920)

    img = Image.new("RGB", (400, 400), (200, 20, 20))
    ImageDraw.Draw(img).rectangle((100, 300, 300, 340), fill="white")
    for x in range(100, 300, 20):  # 글자처럼 촘촘한 무늬
        ImageDraw.Draw(img).line((x, 300, x, 340), fill="black", width=3)
    out = np.asarray(hide_text(img, [TextBox(x=90, y=290, w=220, h=60, coverage=1.0)]), dtype=float)
    assert out[300:340, 100:300].std() < np.asarray(img, dtype=float)[300:340, 100:300].std() / 3  # 뭉개짐
    assert np.array_equal(out[:200], np.asarray(img, dtype=float)[:200])  # 다른 곳은 그대로


@needs_font
def test_render_thumbnail_layout(home):
    style = load_config().thumbnail.model_dump()
    frame = Image.new("RGB", (720, 1280), (40, 90, 160))
    thumb = render_thumbnail(frame, [], ThumbnailText(top="두께 5cm", bottom="접으면 이만큼"), style, FONT)
    assert thumb.size == (1080, 1920)
    px = np.asarray(thumb).astype(int)
    yellow = (np.abs(px - np.array([255, 225, 77])).sum(axis=2) < 40)
    rows, cols = np.where(yellow)
    assert rows.min() >= SAFE_TOP and rows.max() <= 1920 - SAFE_BOTTOM  # 세이프존 안
    assert cols.max() <= 1080 - SAFE_RIGHT + 10
    assert abs((cols.min() + cols.max()) / 2 - 540) < 20  # 가운데 정렬

    long = render_thumbnail(frame, [], ThumbnailText(top="아주 길고 긴 강조 문구 입니다", bottom="접으면"), style, FONT)
    rows = np.where((np.abs(np.asarray(long).astype(int) - np.array([255, 225, 77])).sum(axis=2) < 40).any(axis=1))[0]
    assert rows.max() - rows.min() > 150  # 너무 길면 두 줄로


def test_kmeans_palette_and_style(tmp_path):
    img = Image.new("RGB", (400, 600), (20, 40, 120))
    draw = ImageDraw.Draw(img)
    draw.rectangle((40, 100, 360, 160), fill=(255, 40, 40))  # 강조 글자색 (빨강)
    draw.rectangle((60, 200, 340, 240), fill=(250, 250, 250))  # 요약 글자색 (흰색)
    path = tmp_path / "ref.png"
    img.save(path)
    palette = kmeans_palette(img)
    assert close(palette[0][0], (20, 40, 120)) and palette[0][1] > 0.8  # 배경이 가장 많이
    style = analyze_style_image(path)
    assert close(style.top_color, (255, 40, 40)) and close(style.bottom_color, (250, 250, 250))
    assert style.position_y_ratio is None and "OCR" in style.notes[0]

    class Boxes:
        def detect(self, gray):
            return [(60, 200, 280, 40), (40, 100, 320, 60)]
    style = analyze_style_image(path, Boxes())
    assert style.position_y_ratio == pytest.approx(100 / 600, abs=0.01)
    assert style.top_size == int(60 * 1920 / 600 * 1.05) and style.bottom_size is not None


# ---- 단계 -------------------------------------------------------------------------


@pytest.fixture
def project(home, tmp_path):
    if not FONT.is_file():
        pytest.skip("폰트가 없음 (ssm fonts)")
    shutil.copytree(PROJECT / "assets/fonts", home / "assets/fonts")
    videos = [make_video(tmp_path / "a.mp4", "720x1280", 6, shots=2, box=True), make_video(tmp_path / "b.mp4", "640x360", 3)]
    ws = Workspace.create(Source(type="local", files=[str(v) for v in videos]),
                          {"ad_disclosure": {"profile": "coupang"}, "project": {"duration_sec": 15}})
    import_local_videos(ws, videos)
    run_analyze(ws, detector=WhiteBoxDetector(), log=lambda m: None)
    (ws.path / "script.json").write_text(json.dumps(SCRIPT, ensure_ascii=False), encoding="utf-8")
    return ws


@needs_ffmpeg
def test_run_meta(project):
    (project.path / "meta.json").write_text(json.dumps(META, ensure_ascii=False), encoding="utf-8")
    logs = []
    paths = run_meta(project, log=logs.append)
    assert [p.name for p in paths] == ["thumbnail_1.png", "thumbnail_2.png", "thumbnail_3.png"]
    assert all(Image.open(p).size == (1080, 1920) for p in paths)
    assert (project.path / "thumbnails_preview.jpg").is_file()
    caption = (project.path / "caption.txt").read_text(encoding="utf-8")
    assert caption.splitlines()[1] == AD and "#여행필수템" in caption  # travel 카테고리 태그
    assert project.status("meta") == "done" and not any("meta.json에 없는" in m for m in logs)

    # 썸네일 프레임의 원본 자막(흰 띠, 720x1280의 y 1024~1130 → 1.5배)은 가려진다
    for p in paths:
        band = np.asarray(Image.open(p))[1545:1685, 330:750].astype(int)
        assert (band > 250).all(axis=2).mean() < 0.2, p.name

    # 문구만 바꾸면 meta만 다시 (음성·영상은 그대로)
    data = dict(META, titles=["새 제목"])
    (project.path / "meta.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert project.status("meta") == "stale" and project.status("analyze") == "done"

    data["titles"] = ["최저가 포트"]
    (project.path / "meta.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(MetaError, match="최저가"):
        run_meta(project, log=lambda m: None)


@needs_ffmpeg
def test_run_meta_requirements(project):
    project.set_override("ad_disclosure.profile", None)
    with pytest.raises(MetaError, match="광고 표시"):
        run_meta(project, log=lambda m: None)
    project.set_override("ad_disclosure.profile", "coupang")
    (project.path / "meta.json").write_text('{"titles": "하나"}', encoding="utf-8")
    with pytest.raises(MetaError, match="meta.json 형식"):
        run_meta(project, log=lambda m: None)


@needs_ffmpeg
def test_cli_meta_style(project, tmp_path):
    ref = tmp_path / "ref.png"
    img = Image.new("RGB", (400, 600), (20, 40, 120))
    ImageDraw.Draw(img).rectangle((40, 100, 360, 160), fill=(255, 40, 40))
    img.save(ref)
    runner = CliRunner()
    r = runner.invoke(app, ["meta", "--style", str(ref)])
    assert r.exit_code == 0, r.output
    saved = json.loads((project.path / "thumbnail_style.json").read_text(encoding="utf-8"))
    assert close(saved["top_color"], (255, 40, 40)) and saved["top_color"] in r.output
    assert effective_style(project.config(), project)["top_color"] == saved["top_color"]
    assert project.status("meta") == "done"
    r = runner.invoke(app, ["meta", "--style", "none"])
    assert r.exit_code == 0 and not (project.path / "thumbnail_style.json").exists()
    assert effective_style(project.config(), project)["top_color"] == "#FFE14D"
