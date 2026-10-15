"""원본 수집·필터 (기획서 Module 1) — candidates.json(전체 후보·점수·제외 사유), selected.json, raw_videos/.

URL 프로젝트: 기준 영상 내려받기 → 검색어(collector.keyword, 없으면 기준 영상 제목)로 같은 상품 후보 검색
  + collector.urls → 후보 내려받기(요청 사이 무작위 대기) → 국내 콘텐츠 필터 → CLIP 유사도 등급 → 상위 max_videos개 채택.
키워드 프로젝트: 검색 결과 중 필터를 통과한 첫 영상을 기준으로 삼는다 (상품이 맞는지 사용자 확인 필요).
로컬 프로젝트: 사용자가 넣은 영상을 그대로 쓴다 (내려받지 않고, 국내 콘텐츠로 보이면 경고만).
"""

import hashlib
import json
import os
import random
import re
import shutil
import time
from collections.abc import Callable
from pathlib import Path

from ssm.analyzer import source_videos
from ssm.config import AppConfig
from ssm.downloader import (SEARCH, Downloader, DownloadError, Fetched, PlaywrightDownloader, PlaywrightSearcher,
                            Searcher, YtDlpDownloader, fetch_any, platform_of)
from ssm.filters import (CLIP_FRAMES, OCR_FRAMES, OCR_WIDTH, SPEECH_SECONDS, Inspectors, cosine, grade_for, korean_meta_reason,
                         korean_speech_reason, korean_text_reason, load_inspectors)
from ssm.media import Media, MediaError
from ssm.schemas import Candidate, Candidates, Selected, SelectedVideo
from ssm.workspace import Workspace

CACHE_DIR = "candidates"
MIN_SAME_PRODUCT = 3  # 이보다 적으면 영상 추가를 권한다 (기획서 Module 1 완료 기준)
SEARCH_PLATFORMS = ("xiaohongshu", "douyin")  # 키워드 프로젝트에서 검색할 순서


class CollectError(Exception):
    """사용자에게 그대로 보여줄 수 있는 수집 단계 오류."""


def title_keyword(title: str, limit: int = 20) -> str | None:
    """기준 영상 제목에서 검색어를 뽑는다 (해시태그·이모지·기호 제거)."""
    text = re.sub(r"\s*[-|｜]\s*(rednote|xiaohongshu|小红书|抖音|douyin|tiktok)\s*$", "", title or "", flags=re.I)
    text = re.sub(r"#[^#\s]*(?:\[话题\])?#?", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = " ".join(text.split())[:limit].strip()
    return text or None


def _media_id(url: str) -> str:
    """같은 글의 다른 주소(공유 토큰 등)를 같은 것으로 보기 위한 키."""
    for _, pattern in SEARCH.values():
        if m := pattern.search(url):
            return m.group(1)
    return url.split("#")[0]


class _Run:
    """collect 한 번 실행하는 동안의 상태."""

    def __init__(self, ws: Workspace, cfg: AppConfig, media: Media, downloaders: list[Downloader],
                 inspectors: Callable[[], Inspectors], log: Callable[[str], None], sleep: Callable[[float], None],
                 rng: random.Random):
        self.ws, self.cfg, self.media, self.downloaders = ws, cfg, media, downloaders
        self._inspectors, self._loaded = inspectors, None
        self.log, self.sleep, self.rng = log, sleep, rng
        self.cache = ws.path / CACHE_DIR
        self.cache.mkdir(exist_ok=True)
        self.network_used = False

    @property
    def inspectors(self) -> Inspectors:
        if self._loaded is None:
            self._loaded = self._inspectors()
            for kind, reason in (("한글 OCR", self._loaded.ocr_reason), ("한국어 음성 감지", self._loaded.speech_reason),
                                 ("CLIP 유사도", self._loaded.clip_reason)):
                if reason:
                    self.log(f"[주의] {kind}를 쓸 수 없습니다: {reason}")
        return self._loaded

    def wait(self) -> None:
        """요청 사이 무작위 대기 (차단 방지). 첫 요청 전에는 기다리지 않는다."""
        if self.network_used:
            self.sleep(self.rng.uniform(*self.cfg.collector.delay_sec))
        self.network_used = True

    def download(self, cid: str, url: str, reference: bool = False) -> Candidate:
        key = hashlib.sha256(_media_id(url).encode()).hexdigest()[:12]
        meta_file = self.cache / f"{key}.json"
        cand = Candidate(id=cid, url=url, platform=platform_of(url), reference=reference)
        cached = next((p for p in self.cache.glob(f"{key}.*") if p.suffix != ".json"), None)
        if meta_file.is_file() and cached:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            fetched = Fetched(file=cached, **meta)
        else:
            self.wait()
            try:
                fetched, failed = fetch_any(self.downloaders, url, self.cache, key)
            except DownloadError as e:
                cand.error = str(e)
                return cand
            if failed:
                cand.notes.append("yt-dlp 실패 → 브라우저로 받음")
            meta_file.write_text(json.dumps({"title": fetched.title, "description": fetched.description,
                                             "author": fetched.author, "location": fetched.location},
                                            ensure_ascii=False), encoding="utf-8")
        cand.file = fetched.file.relative_to(self.ws.path).as_posix()
        cand.title, cand.description = fetched.title, fetched.description
        cand.author, cand.location = fetched.author, fetched.location
        return cand

    def korean_reasons(self, cand: Candidate) -> list[str]:
        """국내 콘텐츠 판별 (전부). 검사하지 못한 항목은 notes에 남긴다."""
        return self.quick_reasons(cand) or self.ocr_reasons(cand)

    def ocr_reasons(self, cand: Candidate) -> list[str]:
        """한글 자막 (OCR) — 가장 느린 검사라 다른 검사를 통과한 후보에만 한다."""
        ins = self.inspectors
        if not ins.ocr:
            cand.notes.append("한글 자막 검사 못함")
            return []
        frames = self.media.sample_frames(self.ws.path / cand.file, OCR_FRAMES, width=OCR_WIDTH)
        reason = korean_text_reason([ins.ocr.read(f) for f in frames])
        return [reason] if reason else []

    def quick_reasons(self, cand: Candidate) -> list[str]:
        """메타데이터·한국어 음성 (빠른 검사)."""
        path = self.ws.path / cand.file
        reasons = []
        if reason := korean_meta_reason(cand.title, cand.description, cand.author, cand.location):
            reasons.append(reason)
        ins = self.inspectors
        audio = self.media.audio_pcm16k(path, SPEECH_SECONDS)
        if audio.size < 16000:
            cand.notes.append("소리 없음 → 음성 검사 생략")
        elif ins.speech:
            if reason := korean_speech_reason(ins.speech.korean_probability(audio)):
                reasons.append(reason)
        else:
            cand.notes.append("한국어 음성 검사 못함")
        return reasons

    def embedding(self, cand: Candidate):
        ins = self.inspectors
        if not ins.clip:
            return None
        return ins.clip.embed(self.media.sample_frames(self.ws.path / cand.file, CLIP_FRAMES, width=224))


def _publish(ws: Workspace, chosen: list[Candidate], local: bool) -> list[SelectedVideo]:
    """채택한 후보를 raw_videos/로 옮긴다. 이전 collect가 넣은 파일만 지우고, `ssm add`로 넣은 파일은 둔다."""
    raw = ws.path / "raw_videos"
    raw.mkdir(exist_ok=True)
    if local:
        return [SelectedVideo(file=c.file, candidate=c.id, grade=c.grade, similarity=c.similarity) for c in chosen]
    old = ws.path / "selected.json"
    if old.is_file():
        for v in Selected.model_validate_json(old.read_text(encoding="utf-8")).videos:
            (ws.path / v.file).unlink(missing_ok=True)
    used = {int(p.stem) for p in raw.glob("*") if p.stem.isdigit()}
    videos, n = [], 1
    for c in chosen:
        while n in used:
            n += 1
        src = ws.path / c.file
        dest = raw / f"{n:02d}{src.suffix.lower()}"
        try:
            os.link(src, dest)  # 같은 디스크면 복사하지 않고 링크 (용량 절약)
        except OSError:
            shutil.copy2(src, dest)
        used.add(n)
        videos.append(SelectedVideo(file=dest.relative_to(ws.path).as_posix(), candidate=c.id, grade=c.grade,
                                    similarity=c.similarity, url=c.url))
    return videos


def run_collect(ws: Workspace, cfg: AppConfig | None = None, downloaders: list[Downloader] | None = None,
                searcher: Searcher | None = None, inspectors: Callable[[], Inspectors] | None = None,
                log: Callable[[str], None] = print, sleep: Callable[[float], None] = time.sleep,
                rng: random.Random | None = None) -> Selected:
    cfg = cfg or ws.config()
    col = cfg.collector
    media = Media(cfg)
    source = ws.project().source
    cookies = cfg.path(col.cookies_file) if col.cookies_file else None
    if cookies and not cookies.is_file():
        cookies = None
        if source.type != "local":
            log("[참고] 부계정 쿠키(secrets/cookies.txt)가 없어 로그인 없이 시도합니다 — 막히면 docs/cookies.md 참고.")
    downloaders = downloaders if downloaders is not None else [YtDlpDownloader(cookies, media.ffmpeg),
                                                               PlaywrightDownloader(cookies)]
    searcher = searcher if searcher is not None else PlaywrightSearcher(cookies)
    run = _Run(ws, cfg, media, downloaders, inspectors or (lambda: load_inspectors(cfg, log)), log, sleep,
               rng or random.Random())
    try:
        if source.type == "local":
            cands = _collect_local(run)
        else:
            cands = _collect_online(run, source.type, source.value, searcher)
    except MediaError as e:
        raise CollectError(str(e)) from e

    order = {"same_product": 0, "mood": 1}
    ok = [c for c in cands if c.grade in order]
    ok.sort(key=lambda c: (not c.reference, order[c.grade], -(c.similarity or 0)))
    chosen = ok[: col.max_videos]
    same = sum(c.grade == "same_product" for c in chosen)
    if same == 0:
        _write(ws, source.value, col.keyword, cands, None)
        raise CollectError("같은 상품 영상을 하나도 확보하지 못했습니다 (candidates.json에 후보별 사유가 있습니다).\n"
                           "→ 같은 상품 영상 링크를 `ssm collect --url 링크`로 주거나, 직접 받은 영상을 `ssm add 파일`로 넣으세요.")
    selected = Selected(videos=_publish(ws, chosen, source.type == "local"))
    _write(ws, source.value, col.keyword, cands, selected)
    ws.mark_done("collect")

    for c in cands:
        state = c.error and "내려받기 실패" or (c.grade == "excluded" and "제외: " + ", ".join(c.reasons)) or c.grade
        sim = f" 유사도 {c.similarity:.2f}" if c.similarity is not None else ""
        mark = " (기준)" if c.reference else ""
        log(f"  {c.id}{mark} [{c.platform}] {state}{sim} {c.title[:30]}")
    log(f"채택 {len(chosen)}개 (같은 상품 {same}개, 분위기 영상 {len(chosen) - same}개) → raw_videos/")
    if same < MIN_SAME_PRODUCT and source.type != "local":
        log(f"[주의] 같은 상품 영상이 {same}개뿐입니다 (권장 {MIN_SAME_PRODUCT}개 이상) → 같은 상품 링크(`ssm collect --url`)나 "
            "파일(`ssm add`)을 더 주면 컷이 덜 반복됩니다.")
    return selected


def _write(ws: Workspace, source: str | None, keyword: str | None, cands: list[Candidate],
           selected: Selected | None) -> None:
    data = Candidates(source=source, keyword=keyword, candidates=cands)
    (ws.path / "candidates.json").write_text(data.model_dump_json(indent=2), encoding="utf-8")
    if selected is not None:
        (ws.path / "selected.json").write_text(selected.model_dump_json(indent=2), encoding="utf-8")


def _collect_local(run: _Run) -> list[Candidate]:
    previous = run.ws.path / "selected.json"  # 사용자가 selected.json에서 바꾼 등급은 유지
    grades = {}
    if previous.is_file():
        grades = {v.file: v.grade for v in Selected.model_validate_json(previous.read_text(encoding="utf-8")).videos}
    cands = []
    for i, path in enumerate(source_videos(run.ws), start=1):
        rel = path.relative_to(run.ws.path).as_posix()
        cand = Candidate(id=f"c{i:02d}", platform="local", reference=i == 1, file=rel, grade=grades.get(rel, "same_product"))
        if reasons := run.korean_reasons(cand):  # 직접 고른 영상이라 제외하지 않고 알리기만 한다
            cand.notes += [f"국내 콘텐츠로 보임: {r}" for r in reasons]
            run.log(f"[주의] {rel}: 국내 콘텐츠로 보입니다 ({', '.join(reasons)}) — 저작권 분쟁 위험이 있으니 확인하세요.")
        cands.append(cand)
    if not cands:
        raise CollectError("raw_videos/에 영상이 없습니다 → `ssm add 영상.mp4`로 넣으세요.")
    return cands


def _collect_online(run: _Run, kind: str, value: str | None, searcher: Searcher) -> list[Candidate]:
    col = run.cfg.collector
    cands: list[Candidate] = []
    reference: Candidate | None = None
    platforms = list(SEARCH_PLATFORMS)
    if kind == "url":
        reference = run.download("c01", value, reference=True)
        cands.append(reference)
        if reference.error:
            raise CollectError(f"기준 영상을 내려받지 못했습니다: {reference.error}\n"
                               "→ 쿠키가 만료됐을 수 있습니다 (docs/cookies.md). 막히면 영상을 직접 받아 "
                               "`ssm new --local 파일`로 시작하세요.")
        platforms = [reference.platform] if reference.platform in SEARCH else []

    keyword = col.keyword or (value if kind == "keyword" else None) or (reference and title_keyword(reference.title))
    if col.keyword is None and kind == "url" and keyword:
        run.log(f"  검색어(기준 영상 제목에서): {keyword} — 바꾸려면 `ssm collect --keyword 검색어`")

    urls: list[str] = list(col.urls)
    if keyword:
        for platform in platforms:
            run.wait()
            try:
                found = searcher.search(platform, keyword, col.max_candidates * 2)
            except DownloadError as e:
                run.log(f"[주의] {platform} 검색 실패: {e}")
                continue
            run.log(f"  {platform} 검색 '{keyword}': 링크 {len(found)}개")
            urls += found
    elif not urls:
        run.log("[주의] 검색어가 없어 후보를 찾지 않았습니다 → `ssm collect --keyword 중국어검색어`")

    seen = {_media_id(c.url) for c in cands if c.url}
    queue = []
    for u in urls:
        if _media_id(u) not in seen:
            seen.add(_media_id(u))
            queue.append(u)

    attempts = 0
    for url in queue:  # 이미지 글 등으로 실패하는 링크가 있어 최대 2배까지 시도한다
        if sum(1 for c in cands if not c.reference and c.file) >= col.max_candidates or attempts >= col.max_candidates * 2:
            break
        attempts += 1
        cands.append(run.download(f"c{len(cands) + 1:02d}", url))

    # 검사 순서: 메타데이터·음성(빠름) → 유사도 → 한글 자막 OCR(느림). 앞에서 제외된 후보는 OCR을 하지 않는다.
    ref_emb = None
    for cand in cands:
        if not cand.file:
            cand.grade = "excluded"
            continue
        cand.reasons = run.quick_reasons(cand)
        if cand.reasons:
            cand.grade = "excluded"
            continue
        becomes_reference = not cand.reference and (reference is None or reference.grade == "excluded")
        if not cand.reference and not becomes_reference:
            emb = run.embedding(cand) if ref_emb is not None else None
            cand.similarity = round(cosine(ref_emb, emb), 4) if emb is not None else None
            cand.grade, reason = grade_for(cand.similarity, col.same_product_threshold, col.mood_threshold)
            if reason:
                cand.reasons.append(reason)
                continue
            if cand.similarity is None:
                cand.notes.append("유사도 검사 못함 → 안전하게 분위기 영상(mood)으로 분류 (상품 구간에는 쓰지 않음)")
        cand.reasons = run.ocr_reasons(cand)
        if cand.reasons:
            cand.grade = "excluded"
            continue
        if becomes_reference:  # 키워드 프로젝트: 국내 콘텐츠가 아닌 첫 영상을 기준으로
            if reference is not None:
                reference.reference = False
            reference, cand.reference = cand, True
            cand.notes.append("검색 결과에서 기준 영상으로 삼음 — 광고할 상품이 맞는지 확인하세요")
        if cand.reference:
            cand.grade, cand.similarity = "same_product", 1.0
            ref_emb = run.embedding(cand)
    if reference is not None and reference.grade == "excluded" and kind == "url":
        run.log(f"[주의] 기준 영상이 국내 콘텐츠로 보여 제외했습니다 ({', '.join(reference.reasons)}).")
    return cands
