"""음성 합성 (기획서 Module 3) — script.json → tts.mp3 + word_timings.json.

문장마다 따로 합성해 tts_cache/에 보관하고, 문장 사이에 짧은 무음을 넣어 이어 붙인다.
대본을 조금 고치면 바뀐 문장만 새로 합성한다.
"""

import asyncio
import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from ssm.config import AppConfig
from ssm.media import Media
from ssm.schemas import Script, SentenceTiming, Word, WordTimings
from ssm.workspace import Workspace

SAMPLE_RATE = 24000  # edge-tts 출력과 같은 값 (다시 샘플링하지 않게)
SENTENCE_GAP_SEC = 0.15  # 문장 사이 무음 (기획서: 120~200ms)
RETRIES = 3
SYLLABLES_PER_SEC = (6, 7)  # 한국어 TTS 기준 분량 (기획서 Module 2)


class TTSError(Exception):
    """사용자에게 그대로 보여줄 수 있는 음성 합성 오류."""


class TTSProvider(Protocol):
    name: str

    def synthesize(self, text: str, voice: str, rate: str, out: Path) -> list[Word]:
        """text를 읽어 out(mp3)에 저장하고 단어별 시간(out 기준 초)을 돌려준다."""


class EdgeTTS:
    """Microsoft Edge 읽어주기 (무료, 비공식 엔드포인트 — 예고 없이 막힐 수 있다)."""

    name = "edge"

    def synthesize(self, text: str, voice: str, rate: str, out: Path) -> list[Word]:
        return asyncio.run(self._synthesize(text, voice, rate, out))

    @staticmethod
    async def _synthesize(text: str, voice: str, rate: str, out: Path) -> list[Word]:
        import edge_tts

        words: list[Word] = []
        audio = bytearray()
        async for chunk in edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary").stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
            elif chunk["type"] == "WordBoundary":  # offset·duration 단위는 100ns
                start = chunk["offset"] / 1e7
                words.append(Word(text=chunk["text"], start=start, end=start + chunk["duration"] / 1e7))
        if not audio:
            raise RuntimeError("음성 데이터를 받지 못했습니다.")
        out.write_bytes(bytes(audio))
        return words


PROVIDERS: dict[str, Callable[[], TTSProvider]] = {"edge": EdgeTTS}


def load_script(ws: Workspace) -> Script:
    path = ws.path / "script.json"
    if not path.is_file():
        raise TTSError("script.json이 없습니다 → Claude에게 대본 작성을 요청하세요 "
                       "(형식: src/ssm/schemas.py의 Script, 저장 위치: " + str(path) + ").")
    try:
        return Script.model_validate_json(path.read_text(encoding="utf-8-sig"))
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(str(x) for x in first["loc"])
        raise TTSError(f"script.json 형식이 올바르지 않습니다 — {where}: {first['msg']}") from e


def syllables(text: str) -> int:
    return sum("가" <= ch <= "힣" or ch.isalnum() for ch in text)


def _synthesize_with_retry(provider: TTSProvider, text: str, voice: str, rate: str, out: Path,
                           sleep: Callable[[float], None]) -> list[Word]:
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            return provider.synthesize(text, voice, rate, out)
        except Exception as e:  # noqa: BLE001 — 네트워크·엔드포인트 오류 종류가 다양하다
            last = e
            if attempt + 1 < RETRIES:
                sleep(2 ** attempt)
    raise TTSError(
        f"음성 합성에 {RETRIES}번 실패했습니다 ({type(last).__name__}: {last}).\n"
        f"→ 인터넷 연결을 확인하고 잠시 후 `ssm tts`를 다시 실행하세요. 목소리 이름(tts.voice={voice})이 "
        "맞는지도 확인하세요. 계속 막히면 edge-tts 엔드포인트가 바뀐 것일 수 있으니 `pip install -U edge-tts`를 해보세요."
    ) from last


def run_tts(ws: Workspace, cfg: AppConfig | None = None, provider: TTSProvider | None = None,
            log: Callable[[str], None] = print, sleep: Callable[[float], None] = time.sleep) -> WordTimings:
    cfg = cfg or ws.config()
    provider = provider or PROVIDERS[cfg.tts.provider]()
    script = load_script(ws)
    media = Media(cfg)
    voice, rate = cfg.tts.voice, cfg.tts.rate

    limit = script.target_duration_sec * SYLLABLES_PER_SEC[1]
    count = sum(syllables(s.text) for s in script.sentences)
    if count > limit:
        log(f"[주의] 대본이 {count}음절로 목표 {script.target_duration_sec}초 분량(약 {limit}음절)보다 깁니다.")

    cache = ws.path / "tts_cache"
    cache.mkdir(exist_ok=True)
    gap = bytes(int(SENTENCE_GAP_SEC * SAMPLE_RATE) * 2)
    pcm = bytearray()
    sentences: list[SentenceTiming] = []
    fresh = 0
    for s in script.sentences:
        key = hashlib.sha256(json.dumps([provider.name, voice, rate, s.text], ensure_ascii=False).encode()).hexdigest()
        mp3, meta = cache / f"{key[:20]}.mp3", cache / f"{key[:20]}.json"
        if mp3.is_file() and meta.is_file():
            words = [Word.model_validate(w) for w in json.loads(meta.read_text(encoding="utf-8"))]
        else:
            log(f"  합성: {s.id} {s.text}")
            words = _synthesize_with_retry(provider, s.text, voice, rate, mp3, sleep)
            meta.write_text(json.dumps([w.model_dump() for w in words], ensure_ascii=False), encoding="utf-8")
            fresh += 1
        audio = media.run(["-i", str(mp3), "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
                          what=f"{s.id} 음성 변환")
        if sentences:
            pcm += gap
        start = len(pcm) / 2 / SAMPLE_RATE
        pcm += audio
        end = len(pcm) / 2 / SAMPLE_RATE
        sentences.append(SentenceTiming(
            id=s.id, text=s.text, emphasis=s.emphasis, start=start, end=end,
            words=[Word(text=w.text, start=round(start + w.start, 3), end=round(min(start + w.end, end), 3))
                   for w in words]))

    duration = len(pcm) / 2 / SAMPLE_RATE
    tmp = ws.path / "tts.tmp.mp3"
    media.run(["-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", "-", "-c:a", "libmp3lame", "-b:a", "128k",
               "-f", "mp3", str(tmp)], stdin=bytes(pcm), log=ws.path / "logs" / "tts.log", what="음성 파일 저장")
    tmp.replace(ws.path / "tts.mp3")
    timings = WordTimings(provider=provider.name, voice=voice, rate=rate, duration=round(duration, 3),
                          sentences=sentences)
    (ws.path / "word_timings.json").write_text(timings.model_dump_json(indent=2), encoding="utf-8")
    ws.mark_done("tts")

    log(f"음성 {duration:.1f}초 (문장 {len(sentences)}개, 새로 합성 {fresh}개, 목소리 {voice} {rate})")
    target = script.target_duration_sec
    if duration > target * 1.1:
        log(f"[주의] 목표 {target}초보다 깁니다 → 대본을 줄이거나 `ssm set tts.rate \"+20%\"`로 빠르게 하세요.")
    elif duration < target * 0.7:
        log(f"[주의] 목표 {target}초보다 많이 짧습니다 → 대본에 문장을 더 넣어 보세요.")
    return timings
