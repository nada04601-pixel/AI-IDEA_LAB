"""대본 (기획서 Module 2) — 프리셋·레퍼런스 화법·분량 규칙·금지 표현.

A안(기본): 대본은 Claude Code가 쓴다. 이 모듈은
  1. `ssm script --preset N` → 작성 요청서(script_prompt.md)를 만든다: 상품 정보 초안, 분량, 프리셋 규칙·예시,
     금지 표현, 레퍼런스 화법, 영상 장면 모음(script_frames.jpg)
  2. `ssm script --check` → Claude가 쓴 script.json을 검사하고, 통과하면 script 단계를 완료로 기록한다.
B안(API)·C안(로컬 LLM)은 LLMProvider로 끼울 수 있게만 열어 둔다 (v1 미구현).
"""

import hashlib
import io
import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yaml
from pydantic import ValidationError

from ssm.audio_mix import AUDIO_EXTS, BUILTIN_SFX
from ssm.config import AppConfig
from ssm.media import Media, MediaError
from ssm.schemas import Analysis, Candidates, Script, StyleProfile
from ssm.tts_engine import SENTENCE_OVERHEAD_SEC, estimate_seconds, speech_rate, syllable_budget, syllables
from ssm.workspace import Workspace

PRESET_DIR = "presets/scripts"
BANNED_FILE = "presets/banned_phrases.txt"
CTA_WORDS = ("댓글", "링크", "프로필", "팔로우", "저장")
HOOK_MAX_SYLLABLES = 20  # 훅은 3초 안에 (말하는 동안 초당 약 6.3음절)
MAX_SFX = 4
TOO_LONG = 1.1  # 예상 길이가 목표의 110%를 넘으면 오류
TOO_SHORT = 0.75  # 75%보다 짧으면 주의
REFERENCE_SECONDS = 90
SHEET_TILES = 12


class ScriptError(Exception):
    """사용자에게 그대로 보여줄 수 있는 대본 단계 오류."""


# ---- 프리셋 ---------------------------------------------------------------------


@dataclass
class Preset:
    id: str
    number: int
    name: str
    description: str
    fits: str = ""
    tone: str = ""
    hook_patterns: list[str] = field(default_factory=list)
    sentence_syllables: tuple[int, int] = (6, 22)
    endings: list[str] = field(default_factory=list)
    structure: dict[str, str] = field(default_factory=dict)
    cta_examples: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    examples: list[dict] = field(default_factory=list)


def load_presets(cfg: AppConfig) -> list[Preset]:
    folder = cfg.path(PRESET_DIR)
    presets = []
    for path in sorted(folder.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["sentence_syllables"] = tuple(data.get("sentence_syllables", (6, 22)))
        presets.append(Preset(**data))
    if not presets:
        raise ScriptError(f"대본 프리셋이 없습니다 ({folder}). 프로젝트 파일이 온전한지 확인하세요.")
    return sorted(presets, key=lambda p: p.number)


def find_preset(presets: list[Preset], key: str | int | None) -> Preset | None:
    if key is None:
        return None
    key = str(key).strip()
    return next((p for p in presets if key in (p.id, str(p.number))), None)


# ---- 금지 표현 -------------------------------------------------------------------


@dataclass
class Banned:
    pattern: str
    regex: bool
    suggestion: str = ""


def load_banned(cfg: AppConfig) -> list[Banned]:
    path = cfg.path(BANNED_FILE)
    if not path.is_file():
        return []
    rules = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pattern, _, suggestion = (part.strip() for part in line.partition("=>"))
        regex = pattern.startswith("re:")
        rules.append(Banned(pattern[3:] if regex else pattern, regex, suggestion))
    return rules


def find_banned(text: str, rules: list[Banned]) -> list[tuple[Banned, str]]:
    """(규칙, 찾은 글자) 목록. 일반 표현은 띄어쓰기를 무시하고 찾는다."""
    squeezed = re.sub(r"\s+", "", text)
    found = []
    for rule in rules:
        if rule.regex:
            if m := re.search(rule.pattern, text):
                found.append((rule, m.group()))
        elif re.sub(r"\s+", "", rule.pattern) in squeezed:
            found.append((rule, rule.pattern))
    return found


# ---- 검사 -----------------------------------------------------------------------


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    syllables: int = 0
    seconds: float = 0.0  # 예상 음성 길이
    budget: tuple[int, int] = (0, 0)


def available_sfx(cfg: AppConfig) -> list[str]:
    folder = cfg.path("assets/sfx")
    user = {p.stem for p in folder.glob("*") if p.suffix.lower() in AUDIO_EXTS} if folder.is_dir() else set()
    return sorted(set(BUILTIN_SFX) | user)


def check_script(script: Script, cfg: AppConfig, presets: list[Preset], rules: list[Banned],
                 sfx_names: list[str]) -> Report:
    r = Report()
    preset = find_preset(presets, script.preset)
    chosen = find_preset(presets, cfg.script.preset)
    if preset is None:
        r.errors.append(f"preset '{script.preset}'은 없는 프리셋입니다 (가능: {', '.join(p.id for p in presets)}).")
    elif chosen and preset.id != chosen.id:
        r.errors.append(f"대본 프리셋({preset.id})이 고른 프리셋({chosen.id})과 다릅니다 → 대본을 다시 쓰거나 "
                        f"`ssm script --preset {preset.number}`로 맞추세요.")
    if script.target_duration_sec != cfg.project.duration_sec:
        r.errors.append(f"target_duration_sec({script.target_duration_sec})가 프로젝트 길이({cfg.project.duration_sec}초)와 "
                        "다릅니다.")

    duration = cfg.project.duration_sec
    r.budget = syllable_budget(duration, cfg.tts.rate)[:2]
    r.syllables = sum(syllables(s.text) for s in script.sentences)
    r.seconds = estimate_seconds([s.text for s in script.sentences], cfg.tts.rate)
    if r.seconds > duration * TOO_LONG:
        r.errors.append(f"분량 초과: 예상 {r.seconds:.0f}초 (목표 {duration}초, {r.syllables}음절·문장 {len(script.sentences)}개) "
                        "→ 문장을 줄이세요.")
    elif r.seconds < duration * TOO_SHORT:
        r.warnings.append(f"분량이 적습니다: 예상 {r.seconds:.0f}초 (목표 {duration}초) → 문장을 더 넣으세요.")

    for s in script.sentences:
        for rule, hit in find_banned(s.text, rules):
            tip = f" → {rule.suggestion}" if rule.suggestion else ""
            r.errors.append(f"{s.id}: 금지 표현 '{hit}'{tip}")
    for rule, hit in find_banned(" ".join([script.thumbnail_text.top, script.thumbnail_text.bottom]), rules):
        r.errors.append(f"thumbnail_text: 금지 표현 '{hit}'" + (f" → {rule.suggestion}" if rule.suggestion else ""))

    hook = script.sentences[0]
    if syllables(hook.text) > HOOK_MAX_SYLLABLES:
        r.warnings.append(f"{hook.id}: 훅이 깁니다 ({syllables(hook.text)}음절) → 3초 안에 끝나게 {HOOK_MAX_SYLLABLES}음절 이하로.")
    if preset:
        limit = preset.sentence_syllables[1]
        for s in script.sentences:
            if syllables(s.text) > limit + 4:
                r.warnings.append(f"{s.id}: 문장이 깁니다 ({syllables(s.text)}음절, 이 프리셋 권장 {limit}음절 이하) → 둘로 나누세요.")
    cta = script.sentences[-1]
    if not any(w in cta.text for w in CTA_WORDS):
        r.warnings.append(f"{cta.id}: CTA에 댓글·링크·저장 같은 행동 유도가 없습니다 (예: 댓글에 '링크' 남겨주세요).")
    used_sfx = [s.sfx for s in script.sentences if s.sfx]
    for s in script.sentences:
        if s.sfx and s.sfx not in sfx_names:
            r.warnings.append(f"{s.id}: 효과음 '{s.sfx}'이 없습니다 (가능: {', '.join(sfx_names)}) → 넣지 않고 진행됩니다.")
    if len(used_sfx) > MAX_SFX:
        r.warnings.append(f"효과음이 {len(used_sfx)}개입니다 → {MAX_SFX}개 이하가 덜 시끄러워요.")
    return r


def load_script_file(ws: Workspace) -> Script:
    path = ws.path / "script.json"
    if not path.is_file():
        raise ScriptError("script.json이 없습니다 → `ssm script --preset 1~4`로 작성 요청서(script_prompt.md)를 만들고, "
                          f"Claude가 그 요청서대로 {path}에 대본을 저장해야 합니다.")
    try:
        return Script.model_validate_json(path.read_text(encoding="utf-8-sig"))
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(str(x) for x in first["loc"])
        raise ScriptError(f"script.json 형식이 올바르지 않습니다 — {where}: {first['msg']}") from e


def run_script_check(ws: Workspace, cfg: AppConfig | None = None, log: Callable[[str], None] = print) -> Report:
    cfg = cfg or ws.config()
    script = load_script_file(ws)
    report = check_script(script, cfg, load_presets(cfg), load_banned(cfg), available_sfx(cfg))
    for w in report.warnings:
        log(f"[주의] {w}")
    if report.errors:
        raise ScriptError("대본 검사에서 고칠 곳이 있습니다:\n" + "\n".join(f"  - {e}" for e in report.errors))
    ws.mark_done("script")
    log(f"대본 검사 통과: 문장 {len(script.sentences)}개 · {report.syllables}음절 · 예상 {report.seconds:.0f}초 "
        f"(목표 {cfg.project.duration_sec}초) · 프리셋 {script.preset}")
    return report


# ---- 레퍼런스 화법 -----------------------------------------------------------------


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.?!…~])\s+|\n+", text.strip())
    return [p.strip() for p in parts if syllables(p) > 0]


def _ending(sentence: str) -> str:
    hangul = re.sub(r"[^가-힣]", "", sentence)
    return hangul[-2:]


def analyze_style(text: str, source: str, duration: float | None = None) -> StyleProfile:
    sentences = split_sentences(text)
    if not sentences:
        raise ScriptError(f"레퍼런스에서 문장을 찾지 못했습니다 ({source}).")
    counts = [syllables(s) for s in sentences]
    endings = Counter(e for e in map(_ending, sentences) if e)
    return StyleProfile(
        source=source, transcript=text.strip(), sentence_count=len(sentences),
        avg_syllables=round(sum(counts) / len(counts), 1), max_syllables=max(counts),
        syllables_per_sec=round(sum(counts) / duration, 1) if duration else None,
        question_ratio=round(sum(s.rstrip().endswith("?") for s in sentences) / len(sentences), 2),
        endings=endings.most_common(5), hook=sentences[0])


class Transcriber(Protocol):
    def transcribe(self, audio16k) -> str:
        """16kHz 모노 오디오 → 받아 적은 한국어 문장들."""


class WhisperTranscriber:
    def __init__(self, cuda: bool):
        from faster_whisper import WhisperModel

        self.model = WhisperModel("small", device="cuda" if cuda else "cpu", compute_type="int8")

    def transcribe(self, audio16k) -> str:
        segments, _ = self.model.transcribe(audio16k, language="ko", beam_size=1)
        return "\n".join(seg.text.strip() for seg in segments)


def load_transcriber(cfg: AppConfig) -> tuple[Transcriber | None, str]:
    from ssm.doctor import native_runtime_problem

    if problem := native_runtime_problem():
        return None, problem
    try:
        import ctranslate2

        return WhisperTranscriber(cuda=cfg.device != "cpu" and ctranslate2.get_cuda_device_count() > 0), ""
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {str(e)[:150]}"


def reference_style(ws: Workspace, cfg: AppConfig, source: str, media: Media,
                    transcriber: Callable[[AppConfig], tuple[Transcriber | None, str]] | None = None,
                    log: Callable[[str], None] = print) -> StyleProfile:
    """레퍼런스(대본 .txt / 영상·음성 파일 / 링크)의 화법을 분석해 reference_style.json에 저장한다."""
    out = ws.path / "reference_style.json"
    if out.is_file():
        cached = StyleProfile.model_validate_json(out.read_text(encoding="utf-8"))
        if cached.source == source:
            return cached
    path = Path(source).expanduser()
    if path.suffix.lower() in (".txt", ".md") and path.is_file():
        profile = analyze_style(path.read_text(encoding="utf-8-sig"), source)
    else:
        if not path.is_file():
            path = _download_reference(ws, cfg, source, media)
        audio = media.audio_pcm16k(path, REFERENCE_SECONDS)
        if audio.size < 16000:
            raise ScriptError(f"레퍼런스에 소리가 없습니다 ({source}) → 대본을 .txt로 붙여 넣어 `--reference 파일.txt`로 주세요.")
        model, reason = (transcriber or load_transcriber)(cfg)
        if model is None:
            raise ScriptError(f"레퍼런스 음성을 받아 적을 수 없습니다 ({reason}).\n"
                              "→ 레퍼런스 대본을 텍스트로 붙여 넣어 .txt로 저장한 뒤 `ssm script --reference 파일.txt`로 주세요.")
        log("  레퍼런스 음성 받아 적는 중… (처음에는 음성 인식 모델을 내려받습니다)")
        profile = analyze_style(model.transcribe(audio), source, duration=audio.size / 16000)
    out.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return profile


def _download_reference(ws: Workspace, cfg: AppConfig, url: str, media: Media) -> Path:
    from ssm.downloader import DownloadError, PlaywrightDownloader, YtDlpDownloader, fetch_any

    if not url.startswith(("http://", "https://")):
        raise ScriptError(f"레퍼런스 파일을 찾을 수 없습니다: {url}")
    folder = ws.path / "reference"
    folder.mkdir(exist_ok=True)
    cookies = cfg.path(cfg.collector.cookies_file) if cfg.collector.cookies_file else None
    cookies = cookies if cookies and cookies.is_file() else None
    try:
        fetched, _ = fetch_any([YtDlpDownloader(cookies, media.ffmpeg), PlaywrightDownloader(cookies)], url, folder,
                               hashlib.sha256(url.encode()).hexdigest()[:12])
    except DownloadError as e:
        raise ScriptError(f"레퍼런스 영상을 내려받지 못했습니다: {e}\n→ 대본을 .txt로 붙여 넣어 주세요.") from e
    return fetched.file


# ---- 작성 요청서 -----------------------------------------------------------------


def product_draft(ws: Workspace) -> dict:
    """원본 영상 정보 (중국어일 수 있음) — Claude가 번역·요약해 상품 정보 초안을 만든다."""
    info = {"source": ws.project().source.value or "", "title": "", "description": "", "author": "",
            "same_product": 0, "mood": 0}
    path = ws.path / "candidates.json"
    if path.is_file():
        cands = Candidates.model_validate_json(path.read_text(encoding="utf-8")).candidates
        ref = next((c for c in cands if c.reference), None)
        if ref:
            info.update(title=ref.title, description=ref.description[:500], author=ref.author)
        info["same_product"] = sum(c.grade == "same_product" for c in cands)
        info["mood"] = sum(c.grade == "mood" for c in cands)
    return info


def contact_sheet(ws: Workspace, media: Media, font: Path | None = None) -> Path | None:
    """하이라이트 상위 샷의 가운데 프레임을 한 장에 모은 이미지 (Claude가 상품·장면을 보고 대본을 쓰게)."""
    from PIL import Image, ImageDraw, ImageFont

    path = ws.path / "analysis.json"
    if not path.is_file():
        return None
    analysis = Analysis.model_validate_json(path.read_text(encoding="utf-8"))
    shots = sorted(((v, s) for v in analysis.videos for s in v.shots), key=lambda vs: -vs[1].score)[:SHEET_TILES]
    tiles = []
    for video, shot in sorted(shots, key=lambda vs: vs[1].id):
        try:
            png = media.run(["-ss", f"{(shot.start + shot.end) / 2:.2f}", "-i", str(ws.path / video.file),
                             "-frames:v", "1", "-vf", "scale=240:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                            what="장면 모음")
        except MediaError:
            continue
        tiles.append((Image.open(io.BytesIO(png)).convert("RGB"), f"{shot.id} {video.grade}"))
    if not tiles:
        return None
    cols = min(4, len(tiles))
    rows = -(-len(tiles) // cols)
    tw, th = 240, max(t.height for t, _ in tiles)
    sheet = Image.new("RGB", (cols * tw, rows * (th + 28)), "black")
    draw = ImageDraw.Draw(sheet)
    label_font = ImageFont.truetype(str(font), 18) if font and font.is_file() else ImageFont.load_default()
    for i, (tile, label) in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (th + 28)
        sheet.paste(tile, (x, y))
        draw.text((x + 6, y + th + 4), label, fill="white", font=label_font)
    out = ws.path / "script_frames.jpg"
    sheet.save(out, quality=85)
    return out


def _example_json(preset: Preset, duration: int) -> str:
    ex = preset.examples[0]
    data = {"version": 1, "preset": preset.id, "target_duration_sec": duration,
            "product": {"name": ex["product"], "features": ["특징 1", "특징 2", "특징 3"], "price_hint": None},
            "sentences": [{"id": f"s{i}", **s} for i, s in enumerate(ex["sentences"], start=1)],
            "thumbnail_text": {"top": "위 강조 문구", "bottom": "아래 요약 문구"}}
    return json.dumps(data, ensure_ascii=False, indent=2)


def build_prompt(ws: Workspace, cfg: AppConfig, preset: Preset, rules: list[Banned], draft: dict,
                 style: StyleProfile | None, sheet: Path | None, sfx_names: list[str]) -> str:
    duration = cfg.project.duration_sec
    lo, hi, n = syllable_budget(duration, cfg.tts.rate)
    lines = [
        f"# 대본 작성 요청서 — {ws.id}",
        "",
        "> 이 파일은 Claude Code가 읽고 대본(script.json)을 쓰기 위한 요청서다. 사람이 읽어도 된다.",
        "",
        "## 1. 목표",
        f"- 길이 **{duration}초** → 대본 **약 {lo}~{hi}음절, 문장 {n}개 안팎**. 예상 길이 = 음절 ÷ {speech_rate(cfg.tts.rate):.1f}"
        f"(말 속도) + 문장 수 × {SENTENCE_OVERHEAD_SEC:.0f}초(쉬는 시간). 목표의 {TOO_LONG:.0%}를 넘으면 검사에서 막힌다.",
        f"- 프리셋: **{preset.number}. {preset.name}** (`{preset.id}`) — {preset.description}",
        "",
        "## 2. 상품 정보 (대본 쓰기 전에 사용자에게 확인)",
        "원본 영상 정보 (중국어일 수 있음 → 번역·요약해 상품명·핵심 특징 3개·가격대 초안을 만든다):",
        f"- 원본: {draft['source'] or '(로컬 파일)'}",
        f"- 제목: {draft['title'] or '(없음)'}",
        f"- 설명: {draft['description'] or '(없음)'}",
        "",
        "규칙: 상품명·특징은 영상과 원본 설명에서 확인되는 것만. **가격대는 사용자가 알려준 것만** 쓴다 (모르면 null).",
        "",
        "## 3. 영상 장면",
    ]
    if sheet:
        lines.append(f"- 장면 모음 이미지: `{sheet}` — **먼저 이 이미지를 열어 상품이 무엇이고 어떤 동작이 보이는지 확인**한다.")
    lines += [
        f"- 같은 상품 영상 {draft['same_product']}개, 분위기 영상(mood) {draft['mood']}개.",
        "- mood 영상은 hook·problem 구간에만 쓰인다. demo·benefit 문장은 같은 상품 영상에 실제로 보이는 동작만 설명한다.",
        "- demo 문장에는 어울리는 장면을 `scene_hint`로 적어 두면 좋다 (예: \"접는 장면\").",
        "",
        "## 4. 프리셋 규칙",
        f"- 어울리는 상품: {preset.fits}",
        f"- 톤: {preset.tone}",
        f"- 훅 패턴: " + " / ".join(f"\"{h}\"" for h in preset.hook_patterns),
        f"- 문장 길이: {preset.sentence_syllables[0]}~{preset.sentence_syllables[1]}음절, 어미: {', '.join(preset.endings)}",
        "- 구간별:",
        *[f"  - **{k}**: {v}" for k, v in preset.structure.items()],
        f"- CTA 예시: " + " / ".join(f"\"{c}\"" for c in preset.cta_examples),
        "- 피할 것:",
        *[f"  - {a}" for a in preset.avoid],
        "",
        "### 예시 대본",
    ]
    for ex in preset.examples:
        lines.append(f"- {ex['product']}:")
        lines += [f"  - ({s['section']}) {s['text']}" for s in ex["sentences"]]
    if style:
        lines += [
            "",
            "## 5. 레퍼런스 화법 (말투만 따라 하고 문장은 베끼지 않는다)",
            f"- 출처: {style.source}",
            f"- 문장 {style.sentence_count}개, 평균 {style.avg_syllables}음절 (최대 {style.max_syllables})"
            + (f", 말 속도 초당 {style.syllables_per_sec}음절" if style.syllables_per_sec else ""),
            f"- 질문으로 끝나는 문장 비율 {style.question_ratio:.0%}",
            f"- 자주 쓰는 어미: " + ", ".join(f"'{e}'({n})" for e, n in style.endings),
            f"- 훅: \"{style.hook}\"",
            "- 원문 앞부분:",
            "",
            "```text",
            style.transcript[:400],
            "```",
        ]
    lines += [
        "",
        "## 6. 금지 표현 (과장·허위 광고 소지 — 검사에서 오류)",
        "확인할 수 없는 효과·최상급·가격·의학적 효능은 쓰지 않는다. 목록:",
        ", ".join(r.pattern if not r.regex else f"/{r.pattern}/" for r in rules),
        "",
        "## 7. 형식",
        f"- 저장 위치: `{ws.path / 'script.json'}` (UTF-8)",
        "- 첫 문장 `hook`, 마지막 문장 `cta`(댓글·링크·저장 등 행동 유도). 구간: hook → problem → demo → benefit → cta.",
        f"- 훅은 3초 안에 ({HOOK_MAX_SYLLABLES}음절 이하). 상품명으로 시작하지 않는다.",
        "- `emphasis`: 문장마다 강조어 0~2개 (문장에 그대로 들어 있는 글자). 노란 자막으로 표시된다.",
        f"- `sfx`: {', '.join(sfx_names)} 중에서 2~3개만 (훅=whoosh, 강조=pop·ding, 전환=swish). 없으면 null.",
        "- `thumbnail_text`: 썸네일 위(노란 강조어, 8자 이내)·아래(흰 요약, 12자 이내).",
        "- 예시:",
        "",
        "```json",
        _example_json(preset, duration),
        "```",
        "",
        "## 8. 제목·썸네일·캡션 문구 (meta.json)",
        f"대본과 함께 `{ws.path / 'meta.json'}`도 쓴다 (없으면 대본에서 기본 문구를 만들지만 밋밋하다).",
        "- `category`: kitchen(주방) · living(생활·수납) · travel(여행) · beauty(뷰티) · digital(디지털·가전) · general",
        "- `titles`: 쇼츠 제목 후보 3개. 앞에 '[광고] '가 자동으로 붙고 합쳐서 100자 이내. 궁금증을 주되 과장하지 않는다.",
        "- `thumbnail_texts`: 썸네일 문구 3안 — 위(노란 강조어, 8자 이내)·아래(흰 요약, 12자 이내). 문제·결과·특징처럼 각도를 달리한다.",
        "- `summary`: 캡션 상품 요약 2~3줄 (예: \"✔ 접으면 두께 5cm\"). 확인된 사실만.",
        "- `hashtags`: 상품에 맞춘 해시태그 3~8개. #광고·카테고리 태그는 자동으로 붙는다.",
        "- 금지 표현 검사가 여기에도 적용된다.",
        "",
        "```json",
        json.dumps({"version": 1, "category": "travel",
                    "titles": ["출장 갈 때 포트 고민 끝", "접히는 전기포트 써본 후기", "캐리어 자리 아끼는 여행템"],
                    "thumbnail_texts": [{"top": "출장 필수템", "bottom": "접히는 전기포트"},
                                        {"top": "두께 5cm", "bottom": "접으면 이만큼"},
                                        {"top": "호텔 포트 대신", "bottom": "내 포트 챙기기"}],
                    "summary": ["✔ 접으면 두께 5cm", "✔ 프리볼트라 해외에서도", "✔ 실리콘이라 가벼움"],
                    "hashtags": ["접이식전기포트", "여행포트", "출장템"]}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 9. 저장한 뒤",
        "`ssm script --check` 로 검사한다. 오류가 있으면 고쳐서 다시 검사하고, 통과하면 `ssm run` (tts → edit → meta).",
        "",
    ]
    number = iter(range(1, 20))  # 레퍼런스 절이 없을 때도 번호가 이어지게
    return "\n".join(re.sub(r"^## \d+\.", lambda m: f"## {next(number)}.", line) for line in lines)


class LLMProvider(Protocol):
    name: str

    def write_script(self, prompt: str, ws: Workspace) -> Script | None:
        """대본을 써서 돌려준다. None이면 사람(또는 Claude Code)이 요청서를 보고 직접 쓴다."""


class ClaudeCodeProvider:
    """A안: Claude Code가 script_prompt.md를 읽고 script.json을 직접 쓴다 (추가 비용 0원)."""

    name = "claude_code"

    def write_script(self, prompt: str, ws: Workspace) -> Script | None:
        return None


PROVIDERS: dict[str, Callable[[], LLMProvider]] = {"claude_code": ClaudeCodeProvider}


def prepare_request(ws: Workspace, cfg: AppConfig | None = None,
                    transcriber: Callable[[AppConfig], tuple[Transcriber | None, str]] | None = None,
                    log: Callable[[str], None] = print) -> Path:
    """설정된 프리셋·레퍼런스로 script_prompt.md(+ script_frames.jpg)를 만든다."""
    cfg = cfg or ws.config()
    presets = load_presets(cfg)
    preset = find_preset(presets, cfg.script.preset)
    if preset is None:
        listing = "\n".join(f"  {p.number}. {p.name} — {p.description}" for p in presets)
        raise ScriptError(f"대본 프리셋을 골라야 합니다 → `ssm script --preset 1~4`\n{listing}")
    media = Media(cfg)
    style = reference_style(ws, cfg, cfg.script.reference, media, transcriber, log) if cfg.script.reference else None
    sheet = contact_sheet(ws, media, cfg.path(cfg.subtitle.font))
    prompt = build_prompt(ws, cfg, preset, load_banned(cfg), product_draft(ws), style, sheet, available_sfx(cfg))
    out = ws.path / "script_prompt.md"
    out.write_text(prompt, encoding="utf-8")
    script = PROVIDERS[cfg.llm.provider]().write_script(prompt, ws)
    if script is not None:  # B안·C안이 생기면 여기서 바로 저장한다
        (ws.path / "script.json").write_text(script.model_dump_json(indent=2), encoding="utf-8")
    log(f"대본 작성 요청서: {out}")
    if sheet:
        log(f"장면 모음 이미지: {sheet}")
    lo, hi, n = syllable_budget(cfg.project.duration_sec, cfg.tts.rate)
    log(f"프리셋 {preset.number}. {preset.name} · {cfg.project.duration_sec}초 → 약 {lo}~{hi}음절·문장 {n}개 안팎"
        + (f" · 레퍼런스 화법 반영 ({style.source})" if style else ""))
    return out
