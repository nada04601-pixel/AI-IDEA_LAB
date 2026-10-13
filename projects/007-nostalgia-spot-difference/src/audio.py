"""배경음악.

assets/music/ 에 이용 권한이 확인된 음악 파일이 있으면 그것을 쓰고,
없으면 저작권 걱정 없는 잔잔한 오르골 풍 음악을 코드로 직접 만든다.
정답 공개 때마다 작은 종소리를 넣는다. 음량 변화는 작게 유지한다.
"""
from __future__ import annotations

import random
import wave
from pathlib import Path

import numpy as np

SR = 44100
PENTATONIC = [0, 2, 4, 7, 9]  # 도 레 미 솔 라


def _note(freq: float, dur: float, amp: float, decay: float = 3.0) -> np.ndarray:
    t = np.arange(int(SR * dur)) / SR
    env = np.exp(-decay * t) * np.minimum(1, t * 80)
    wave_ = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t) + 0.08 * np.sin(6 * np.pi * freq * t)
    return amp * env * wave_


def _midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def synth_music(duration: float, seed: int) -> np.ndarray:
    rng = random.Random(seed)
    total = int(SR * duration)
    out = np.zeros(total + SR * 3)
    beat = 60 / 76  # 느린 템포
    root = rng.choice([60, 62, 65])  # 도/레/파 장조
    chords = [[0, 4, 7], [5, 9, 12], [7, 11, 14], [0, 4, 7], [9, 12, 16], [5, 9, 12], [7, 11, 14], [0, 4, 7]]
    t = 0.0
    bar = 0
    while t < duration:
        ch = chords[bar % len(chords)]
        # 부드러운 화음(패드)
        for n in ch:
            seg = _note(_midi(root - 12 + n), beat * 4, 0.035, decay=0.6)
            i = int(t * SR)
            out[i:i + len(seg)] += seg[: len(out) - i]
        # 오르골 선율
        for k in range(4):
            if rng.random() < 0.82:
                deg = rng.choice(PENTATONIC) + rng.choice([12, 12, 24])
                seg = _note(_midi(root + deg - 12), beat * 1.6, 0.07, decay=2.6)
                i = int((t + k * beat) * SR)
                out[i:i + len(seg)] += seg[: len(out) - i]
        t += beat * 4
        bar += 1
    return out[:total]


def chimes(duration: float, times: list[float]) -> np.ndarray:
    out = np.zeros(int(SR * duration))
    for tt in times:
        for n, a in ((88, 0.09), (95, 0.05)):
            seg = _note(_midi(n), 1.2, a, decay=4.0)
            i = int(tt * SR)
            if i < len(out):
                out[i:i + len(seg)] += seg[: len(out) - i]
    return out


def _fade(x: np.ndarray, fade_in: float = 0.8, fade_out: float = 1.5) -> np.ndarray:
    n_in, n_out = int(SR * fade_in), int(SR * fade_out)
    x = x.copy()
    x[:n_in] *= np.linspace(0, 1, n_in)
    x[-n_out:] *= np.linspace(1, 0, n_out)
    return x


def write_wav(path: Path, mono: np.ndarray) -> None:
    peak = np.max(np.abs(mono)) or 1.0
    if peak > 0.89:  # 클리핑 방지 (보통은 여기까지 커지지 않음)
        mono = mono / peak * 0.89
    stereo = np.repeat((mono * 32767).astype(np.int16)[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())


def build_audio(duration: float, reveal_times: list[float], seed: int, out_dir: Path,
                with_music: bool = True) -> tuple[Path, Path]:
    """(음악 wav, 종소리 wav) 경로를 돌려준다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    music_path = out_dir / "music.wav"
    chime_path = out_dir / "chimes.wav"
    music = synth_music(duration, seed) if with_music else np.zeros(int(SR * duration))
    write_wav(music_path, _fade(music))
    write_wav(chime_path, chimes(duration, reveal_times))
    return music_path, chime_path


def pick_user_music(music_dir: Path, seed: int) -> Path | None:
    if not music_dir.is_dir():
        return None
    files = sorted(p for p in music_dir.iterdir() if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg", ".flac"})
    if not files:
        return None
    return random.Random(seed).choice(files)
