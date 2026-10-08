"""외부 API 없이 동작하는 mock 음성(TTS) 공급자.

실제 목소리 대신, 자막이 바뀌는 시점마다 짧은 '삑' 소리가 나는 장면 길이만큼의 WAV를 만든다.
프롬프트(대사)에 [mock-fail] / [mock-fail-once]가 있으면 실패한다.
"""

import hashlib
import math
import struct
import wave

from app.providers.media import MediaRequest, MediaResult
from app.providers.mock_media import _check_fail_trigger
from app.services.subtitles import build_cues

SAMPLE_RATE = 44100
BEEP_SEC = 0.12


def text_hash(text: str) -> str:
    """음성을 만든 대사를 기억해, 대사가 바뀌면 다시 만들어야 함을 알 수 있게 한다."""
    return hashlib.sha256(text.strip().encode()).hexdigest()[:16]


class MockTTSProvider:
    name = "mock"
    kind = "audio"
    is_paid = False
    currency = "USD"

    def estimate_cost(self, duration_sec: float) -> float:
        return 0.0

    def generate(self, req: MediaRequest) -> MediaResult:
        _check_fail_trigger(req)
        total = int(SAMPLE_RATE * req.duration_sec)
        beeps = [round(c.start * SAMPLE_RATE) for c in build_cues([(1, req.prompt, req.duration_sec)])]
        beep_len = int(SAMPLE_RATE * BEEP_SEC)
        samples = bytearray(total * 2)
        for start in beeps:
            for i in range(min(beep_len, total - start)):
                fade = min(1.0, i / 200, (beep_len - i) / 200)  # 딸깍 소리 방지
                value = int(0.25 * 32767 * fade * math.sin(2 * math.pi * 660 * i / SAMPLE_RATE))
                struct.pack_into("<h", samples, (start + i) * 2, value)
        path = req.output_path.with_suffix(".wav")
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(bytes(samples))
        meta = {"duration_sec": req.duration_sec, "text_hash": text_hash(req.prompt), "mock": True}
        return MediaResult(path, 0.0, self.currency, meta)
