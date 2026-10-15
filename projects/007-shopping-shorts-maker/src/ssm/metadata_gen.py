"""썸네일·캡션 (기획서 Module 5) — thumbnail_1~3.png, thumbnails_preview.jpg, caption.txt.

문구(제목·썸네일 문구·요약·상품 해시태그)는 Claude가 meta.json에 쓴다 (A안). 없으면 script.json에서 기본 문구를 만든다.
- 썸네일: 같은 상품 영상의 하이라이트 상위 샷에서 선명도·밝기·중앙 집중도가 높은 프레임 3장 → 원본 자막 영역 블러 →
  1080x1920, 위(노란 강조어)·아래(흰 요약) 2줄을 세이프존 안 위쪽 가운데에.
- 캡션: 광고 문구를 본문 첫 줄에 (공정위 추천·보증 심사지침), 훅·요약·CTA·해시태그. 유튜브 쇼츠는 제목 후보와 요약 태그 따로.
- 스타일 복제: 레퍼런스 썸네일 → 색 팔레트(k-means), (OCR이 되면) 글자 위치·크기 → thumbnail_style.json.
"""

import io
import json
import re
from collections.abc import Callable
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont
from pydantic import ValidationError

from ssm.config import AppConfig
from ssm.media import Media, MediaError
from ssm.schemas import Analysis, MetaText, Script, Shot, TextBox, ThumbnailStyle, ThumbnailText, VideoAnalysis
from ssm.scripter import Banned, ScriptError, find_banned, load_banned, load_script_file
from ssm.subtitle import REF_WIDTH, SAFE_BOTTOM, SAFE_RIGHT, SAFE_TOP
from ssm.workspace import Workspace

THUMB_COUNT = 3
THUMB_SIZE = (1080, 1920)
SHOT_POOL = 6  # 점수 상위 몇 개 샷에서 프레임을 고를지
FRAME_POINTS = (0.3, 0.5, 0.7)  # 샷 안에서 프레임을 볼 위치
TEXT_MAX_WIDTH = REF_WIDTH - 2 * SAFE_RIGHT  # 가운데 정렬해도 오른쪽 세이프존을 넘지 않는 폭
MIN_FONT_RATIO = 0.6  # 이보다 작게 줄여야 하면 두 줄로 나눈다
COVER_TOLERANCE = 0.12
TITLE_MAX = 100
AD_TITLE_PREFIX = "[광고] "
HASHTAGS = (10, 15)
YOUTUBE_TAGS = 5
PRESET_DIR = "presets/hashtags"


class MetaError(Exception):
    """사용자에게 그대로 보여줄 수 있는 썸네일·캡션 단계 오류."""


# ---- 문구 ------------------------------------------------------------------------


def load_meta_text(ws: Workspace) -> MetaText | None:
    path = ws.path / "meta.json"
    if not path.is_file():
        return None
    try:
        return MetaText.model_validate_json(path.read_text(encoding="utf-8-sig"))
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(str(x) for x in first["loc"])
        raise MetaError(f"meta.json 형식이 올바르지 않습니다 — {where}: {first['msg']}") from e


def _cut(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rstrip()


def default_meta(script: Script) -> MetaText:
    """meta.json이 없을 때 대본에서 만드는 기본 문구."""
    product = script.product
    variants = [script.thumbnail_text]
    emphasis = next((e for s in script.sentences for e in s.emphasis), None)
    if emphasis:
        variants.append(ThumbnailText(top=_cut(emphasis, 10), bottom=_cut(product.name, 14)))
    variants += [ThumbnailText(top=_cut(f, 10), bottom=_cut(product.name, 14)) for f in product.features if f.strip()]
    unique = list({(v.top, v.bottom): v for v in variants}.values())
    titles = [script.sentences[0].text, f"{product.name} 써본 후기"]
    if product.features:
        titles.append(f"{product.name} — {product.features[0]}")
    return MetaText(titles=titles[:3], thumbnail_texts=unique[:3],
                    summary=[f"✔ {f}" for f in product.features[:3]],
                    hashtags=[product.name.replace(" ", "")])


def merge_meta(script: Script, meta: MetaText | None) -> tuple[MetaText, list[str]]:
    """Claude가 쓴 meta.json의 빈 곳을 기본 문구로 채운다. (결과, 채운 항목 이름들)."""
    base = default_meta(script)
    if meta is None:
        return base, ["meta.json 전체"]
    filled = []
    data = meta.model_copy(deep=True)
    for name in ("titles", "thumbnail_texts", "summary", "hashtags"):
        if not getattr(data, name):
            setattr(data, name, getattr(base, name))
            filled.append(name)
    texts = list(data.thumbnail_texts)
    extra = [t for t in base.thumbnail_texts if (t.top, t.bottom) not in {(x.top, x.bottom) for x in texts}]
    while len(texts) < THUMB_COUNT and extra:
        texts.append(extra.pop(0))
    data.thumbnail_texts = texts
    return data, filled


def check_meta_text(meta: MetaText, rules: list[Banned]) -> list[str]:
    errors = []
    pieces = [("titles", t) for t in meta.titles] + [("summary", t) for t in meta.summary] + \
             [("hashtags", t) for t in meta.hashtags] + \
             [("thumbnail_texts", f"{t.top} {t.bottom}") for t in meta.thumbnail_texts]
    for where, text in pieces:
        for rule, hit in find_banned(text, rules):
            errors.append(f"{where}: 금지 표현 '{hit}' ({text})" + (f" → {rule.suggestion}" if rule.suggestion else ""))
    for t in meta.titles:
        if len(AD_TITLE_PREFIX + t) > TITLE_MAX:
            errors.append(f"titles: 제목이 깁니다 ({len(AD_TITLE_PREFIX + t)}자, [광고] 포함 {TITLE_MAX}자 이내): {t}")
    return errors


def normalize_tag(tag: str) -> str | None:
    body = re.sub(r"[^\w]", "", tag.strip().lstrip("#"))
    return f"#{body}" if body else None


def category_tags(cfg: AppConfig, category: str) -> list[str]:
    path = cfg.path(PRESET_DIR) / f"{category}.yaml"
    if not path.is_file():
        path = cfg.path(PRESET_DIR) / "general.yaml"
    if not path.is_file():
        return []
    return list(yaml.safe_load(path.read_text(encoding="utf-8")).get("tags", []))


def build_hashtags(product_tags: list[str], category: list[str], general: list[str]) -> list[str]:
    """#광고를 맨 앞에, 상품 태그 → 카테고리 태그 → (모자라면) 일반 태그 순으로 10~15개."""
    tags: list[str] = []

    def add(raw: str) -> None:
        tag = normalize_tag(raw)
        if tag and len(tags) < HASHTAGS[1] and tag.lower() not in {t.lower() for t in tags}:
            tags.append(tag)

    for raw in ["광고", *product_tags, *category]:
        add(raw)
    for raw in general:  # 일반 태그는 10개를 채울 때까지만
        if len(tags) >= HASHTAGS[0]:
            break
        add(raw)
    return tags


def youtube_tags(product_tags: list[str]) -> list[str]:
    tags = ["#shorts", "#광고"]
    for raw in product_tags:
        tag = normalize_tag(raw)
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:YOUTUBE_TAGS]


def build_titles(titles: list[str]) -> list[str]:
    return [_cut(AD_TITLE_PREFIX + t.strip(), TITLE_MAX) for t in titles if t.strip()]


def build_caption(script: Script, meta: MetaText, ad_text: str, tags: list[str], yt_tags: list[str]) -> str:
    hook, cta = script.sentences[0].text, script.sentences[-1].text
    body = [ad_text, "", hook, "", *meta.summary, "", cta]
    lines = [
        "========== 공통 (인스타그램 릴스 · 틱톡) ==========",
        *body, "", " ".join(tags), "",
        "========== 유튜브 쇼츠 ==========",
        "[제목 후보 — 하나를 골라 제목에]",
        *[f"{i}. {t}" for i, t in enumerate(build_titles(meta.titles), start=1)],
        "",
        "[설명]",
        *body, "", " ".join(yt_tags), "",
        "========== 참고 ==========",
        "- 광고 문구는 본문 첫 줄에서 지우거나 '더보기' 아래로 옮기지 마세요 (공정위 추천·보증 심사지침).",
        f"- 상품: {script.product.name}" + (f" ({script.product.price_hint})" if script.product.price_hint else ""),
    ]
    return "\n".join(lines) + "\n"


# ---- 프레임 고르기 ------------------------------------------------------------------


def frame_at(media: Media, path: Path, t: float) -> Image.Image:
    png = media.run(["-ss", f"{max(t, 0):.3f}", "-i", str(path), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png",
                     "-"], what=f"{path.name} 썸네일 프레임")
    if not png:
        raise MediaError(f"{path.name}의 {t:.1f}초 프레임을 읽지 못했습니다.")
    return Image.open(io.BytesIO(png)).convert("RGB")


def frame_metrics(img: Image.Image) -> tuple[float, float, float]:
    """(선명도, 밝기 점수 0~1, 중앙 집중도 0~1). 중앙 집중도 = 가장자리보다 가운데에 윤곽이 몰린 정도."""
    import cv2

    small = np.asarray(img.convert("L").resize((270, max(2, int(270 * img.height / img.width)))), dtype=np.float32)
    sharp = float(cv2.Laplacian(small, cv2.CV_32F).var())
    bright = 1 - min(abs(float(small.mean()) - 130) / 130, 1)
    gy, gx = np.gradient(small)
    edges = np.hypot(gx, gy)
    h, w = edges.shape
    center = edges[h // 4: 3 * h // 4, w // 4: 3 * w // 4].sum()
    central = min(float(center / (edges.sum() + 1e-6)) / 0.5, 1.0)  # 고르면 0.25 → 0.5, 가운데에 몰리면 1
    return sharp, bright, central


def pick_frames(ws: Workspace, media: Media, analysis: Analysis, count: int = THUMB_COUNT
                ) -> list[tuple[Image.Image, VideoAnalysis, Shot]]:
    videos = [v for v in analysis.videos if v.grade == "same_product"] or analysis.videos  # 썸네일엔 같은 상품만
    shots = sorted(((v, s) for v in videos for s in v.shots), key=lambda vs: -vs[1].score)[:SHOT_POOL]
    scored = []
    for video, shot in shots:
        best = None
        for p in FRAME_POINTS:
            img = frame_at(media, ws.path / video.file, shot.start + shot.duration * p)
            metrics = frame_metrics(img)
            if best is None or metrics[0] > best[1][0]:
                best = (img, metrics)
        scored.append((best[0], best[1], video, shot))
    if not scored:
        raise MetaError("썸네일로 쓸 장면이 없습니다 → `ssm analyze`를 먼저 실행하세요.")
    sharp_rank = {id(x): r / len(scored) for r, x in enumerate(sorted(scored, key=lambda x: x[1][0]), start=1)}
    ranked = sorted(scored, key=lambda x: -(0.45 * sharp_rank[id(x)] + 0.25 * x[1][1] + 0.30 * x[1][2]))
    picks = [(img, v, s) for img, _, v, s in ranked[:count]]
    while len(picks) < count:  # 샷이 모자라면 좋은 프레임을 다시 쓴다
        picks.append(picks[len(picks) % len(ranked)])
    return picks


# ---- 썸네일 그리기 -----------------------------------------------------------------


def hide_text(img: Image.Image, boxes: list[TextBox]) -> Image.Image:
    """원본 자막·워터마크 영역을 블러로 가린다 (편집 단계와 같은 방식)."""
    img = img.copy()
    for b in boxes:
        box = (max(0, b.x), max(0, b.y), min(img.width, b.x + b.w), min(img.height, b.y + b.h))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        region = img.crop(box).filter(ImageFilter.GaussianBlur(max(8, b.h // 4)))
        region = Image.blend(region, Image.new("RGB", region.size, "black"), 0.3)
        img.paste(region, box[:2])
    return img


def fit_vertical(img: Image.Image, size: tuple[int, int] = THUMB_SIZE) -> Image.Image:
    w, h = size
    cover_scale = max(w / img.width, h / img.height)
    cover = img.resize((round(img.width * cover_scale), round(img.height * cover_scale)), Image.LANCZOS)
    left, top = (cover.width - w) // 2, (cover.height - h) // 2
    cover = cover.crop((left, top, left + w, top + h))
    if abs(img.width / img.height - w / h) / (w / h) <= COVER_TOLERANCE:
        return cover
    canvas = cover.filter(ImageFilter.GaussianBlur(30))  # 비율이 많이 다르면 블러 배경 위에 원본을 통째로
    fit_scale = min(w / img.width, h / img.height)
    fg = img.resize((round(img.width * fit_scale), round(img.height * fit_scale)), Image.LANCZOS)
    canvas.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
    return canvas


def _fit_lines(text: str, font_path: Path, size: int, max_w: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """한 줄로 넣되, 너무 줄여야 하면 어절 단위로 두 줄로 나눈다."""
    for px in range(size, int(size * MIN_FONT_RATIO) - 1, -2):
        font = ImageFont.truetype(str(font_path), px)
        if font.getlength(text) <= max_w:
            return font, [text]
    words = text.split()
    if len(words) > 1:
        splits = [(" ".join(words[:k]), " ".join(words[k:])) for k in range(1, len(words))]
        for px in range(size, int(size * 0.4) - 1, -2):
            font = ImageFont.truetype(str(font_path), px)
            fitting = [s for s in splits if max(font.getlength(s[0]), font.getlength(s[1])) <= max_w]
            if fitting:
                best = min(fitting, key=lambda s: abs(len(s[0]) - len(s[1])))
                return font, list(best)
    for px in range(int(size * MIN_FONT_RATIO), 19, -2):  # 띄어쓰기 없는 긴 글자는 끝까지 줄인다
        font = ImageFont.truetype(str(font_path), px)
        if font.getlength(text) <= max_w:
            break
    return font, [text]


def render_thumbnail(frame: Image.Image, boxes: list[TextBox], text: ThumbnailText, style: dict,
                     font_path: Path) -> Image.Image:
    canvas = fit_vertical(hide_text(frame, boxes)).convert("RGBA")
    W, H = canvas.size
    stroke = style["stroke_width"]
    blocks = []
    for value, size_key, color_key in ((text.top, "top_size", "top_color"), (text.bottom, "bottom_size", "bottom_color")):
        font, lines = _fit_lines(value, font_path, style[size_key], TEXT_MAX_WIDTH)
        blocks.append((font, lines, ImageColor.getrgb(style[color_key])))

    y = max(int(H * style["position_y_ratio"]), SAFE_TOP)
    layout, cursor = [], y
    for font, lines, color in blocks:
        ascent, descent = font.getmetrics()
        for line in lines:
            layout.append((line, font, color, cursor))
            cursor += int((ascent + descent) * 1.05)
        cursor += int(font.size * 0.15)
    shift = max(0, cursor - (H - SAFE_BOTTOM))  # 아래 세이프존을 넘으면 위로 당긴다
    layout = [(t, f, c, max(SAFE_TOP, yy - shift)) for t, f, c, yy in layout]

    if style["gradient"]:
        bottom = min(H, cursor - shift + 220)
        alpha = np.zeros((H, 1), dtype=np.uint8)
        alpha[:bottom, 0] = np.linspace(170, 0, bottom).astype(np.uint8)
        shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        shade.putalpha(Image.fromarray(np.repeat(alpha, W, axis=1)))
        canvas = Image.alpha_composite(canvas, shade)
    draw = ImageDraw.Draw(canvas)
    stroke_color = ImageColor.getrgb(style["stroke_color"])
    for line, font, color, yy in layout:
        x = (W - font.getlength(line)) / 2
        draw.text((x, yy), line, font=font, fill=color, stroke_width=stroke, stroke_fill=stroke_color)
    return canvas.convert("RGB")


def preview_sheet(paths: list[Path], out: Path) -> Path:
    tiles = [Image.open(p).convert("RGB").resize((360, 640)) for p in paths]
    sheet = Image.new("RGB", (len(tiles) * 370 - 10, 690), "white")
    draw = ImageDraw.Draw(sheet)
    for i, tile in enumerate(tiles):
        sheet.paste(tile, (i * 370, 0))
        draw.text((i * 370 + 170, 655), str(i + 1), fill="black", font=ImageFont.load_default(28))
    sheet.save(out, quality=88)
    return out


# ---- 스타일 -----------------------------------------------------------------------


def kmeans_palette(img: Image.Image, k: int = 6, iterations: int = 15) -> list[tuple[str, float]]:
    """많이 쓰인 색 k개 [(#RRGGBB, 비율)] — 비율이 큰 순서."""
    small = np.asarray(img.convert("RGB").resize((96, max(1, int(96 * img.height / img.width)))), dtype=np.float32)
    pixels = small.reshape(-1, 3)
    order = np.argsort(pixels.sum(axis=1))
    centers = pixels[order[np.linspace(0, len(order) - 1, k).astype(int)]].copy()  # 어두운 색~밝은 색으로 시작
    for _ in range(iterations):
        labels = np.argmin(((pixels[:, None, :] - centers[None]) ** 2).sum(axis=2), axis=1)
        for j in range(k):
            if (labels == j).any():
                centers[j] = pixels[labels == j].mean(axis=0)
    labels = np.argmin(((pixels[:, None, :] - centers[None]) ** 2).sum(axis=2), axis=1)
    counts = np.bincount(labels, minlength=k) / len(labels)
    result = [("#%02X%02X%02X" % tuple(int(round(v)) for v in centers[j]), float(counts[j])) for j in range(k)
              if counts[j] > 0]
    return sorted(result, key=lambda c: -c[1])


def _hsv(hex_color: str) -> tuple[float, float, float]:
    import colorsys

    r, g, b = (c / 255 for c in ImageColor.getrgb(hex_color))
    return colorsys.rgb_to_hsv(r, g, b)


def analyze_style_image(path: Path, detector=None) -> ThumbnailStyle:
    img = Image.open(path).convert("RGB")
    palette = kmeans_palette(img)
    colors = [c for c, ratio in palette if ratio >= 0.01]
    accent = max(colors, key=lambda c: _hsv(c)[1] * _hsv(c)[2])  # 가장 쨍한 색 → 강조어
    light = [c for c in colors if _hsv(c)[1] < 0.25 and _hsv(c)[2] > 0.8]
    style = ThumbnailStyle(source=str(path), palette=[c for c, _ in palette], top_color=accent,
                           bottom_color=light[0] if light else "#FFFFFF")
    if detector is None:
        style.notes.append("OCR을 쓸 수 없어 글자 위치·크기는 읽지 못함 — Claude가 이미지를 보고 채울 수 있음")
        return style
    gray = np.asarray(img.convert("L"))
    boxes = sorted(detector.detect(gray), key=lambda b: b[1])
    if not boxes:
        style.notes.append("글자를 찾지 못함")
        return style
    scale = THUMB_SIZE[1] / img.height
    style.position_y_ratio = round(min(max(boxes[0][1] / img.height, 0.13), 0.75), 3)
    style.top_size = int(min(max(boxes[0][3] * scale * 1.05, 40), 300))
    if len(boxes) > 1:
        style.bottom_size = int(min(max(boxes[1][3] * scale * 1.05, 30), 250))
    return style


def effective_style(cfg: AppConfig, ws: Workspace) -> dict:
    style = cfg.thumbnail.model_dump()
    path = ws.path / "thumbnail_style.json"
    if path.is_file():
        ref = ThumbnailStyle.model_validate_json(path.read_text(encoding="utf-8"))
        style.update({k: v for k, v in ref.model_dump().items() if k in style and v is not None})
    return style


def save_style(ws: Workspace, source: str | None, detector_loader: Callable | None = None) -> ThumbnailStyle | None:
    """레퍼런스 썸네일 스타일을 thumbnail_style.json으로. source가 None이면 지운다."""
    out = ws.path / "thumbnail_style.json"
    if source is None:
        out.unlink(missing_ok=True)
        return None
    path = Path(source).expanduser()
    if not path.is_file():
        raise MetaError(f"레퍼런스 썸네일 이미지를 찾을 수 없습니다: {source}")
    from ssm.analyzer import load_detector

    detector, _ = (detector_loader or load_detector)(ws.config())
    style = analyze_style_image(path, detector)
    out.write_text(style.model_dump_json(indent=2), encoding="utf-8")
    return style


# ---- 단계 실행 ------------------------------------------------------------------


def run_meta(ws: Workspace, cfg: AppConfig | None = None, log: Callable[[str], None] = print) -> list[Path]:
    cfg = cfg or ws.config()
    ad_text = cfg.ad_disclosure.text()
    if not ad_text:
        raise MetaError("광고 표시 프로필이 정해지지 않았습니다 (캡션 첫 줄에 넣어야 함) → `ssm set ad_disclosure.profile coupang`")
    try:
        script = load_script_file(ws)
    except ScriptError as e:
        raise MetaError(str(e)) from e
    analysis_file = ws.path / "analysis.json"
    if not analysis_file.is_file():
        raise MetaError("analysis.json이 없습니다 → 먼저 `ssm analyze`를 실행하세요.")
    font = cfg.path(cfg.thumbnail.font)
    if not font.is_file():
        raise MetaError(f"썸네일 폰트가 없습니다: {font.name} → `ssm fonts`를 실행하세요.")

    meta, filled = merge_meta(script, load_meta_text(ws))
    if filled:
        log(f"[참고] meta.json에 없는 항목({', '.join(filled)})은 대본에서 기본 문구로 만들었습니다 — "
            "Claude가 meta.json을 쓰면 더 좋은 제목·썸네일 문구가 됩니다.")
    errors = check_meta_text(meta, load_banned(cfg))
    if errors:
        raise MetaError("제목·썸네일·캡션 문구에서 고칠 곳이 있습니다 (meta.json):\n" + "\n".join(f"  - {e}" for e in errors))

    media = Media(cfg)
    analysis = Analysis.model_validate_json(analysis_file.read_text(encoding="utf-8"))
    style = effective_style(cfg, ws)
    try:
        frames = pick_frames(ws, media, analysis)
    except MediaError as e:
        raise MetaError(str(e)) from e
    for old in ws.path.glob("thumbnail*.png"):
        old.unlink()
    paths = []
    for i, ((frame, video, shot), text) in enumerate(zip(frames, meta.thumbnail_texts * THUMB_COUNT), start=1):
        out = ws.path / f"thumbnail_{i}.png"
        render_thumbnail(frame, video.text_boxes, text, style, font).save(out)
        paths.append(out)
        log(f"  thumbnail_{i}.png: '{text.top}' / '{text.bottom}' (장면 {shot.id})")
    preview = preview_sheet(paths, ws.path / "thumbnails_preview.jpg")

    general = category_tags(cfg, "general")
    tags = build_hashtags(meta.hashtags, category_tags(cfg, meta.category), general)
    caption = build_caption(script, meta, ad_text, tags, youtube_tags(meta.hashtags))
    (ws.path / "caption.txt").write_text(caption, encoding="utf-8")
    ws.mark_done("meta")
    log(f"썸네일 {len(paths)}안 (비교: {preview.name}) · 캡션 caption.txt (해시태그 {len(tags)}개, 제목 후보 "
        f"{len(meta.titles)}개)")
    return paths
