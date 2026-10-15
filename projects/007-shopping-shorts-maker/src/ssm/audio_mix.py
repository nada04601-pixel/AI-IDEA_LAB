"""오디오 믹스 (기획서 Module 3) — TTS 음성 + 효과음 + BGM(덕킹) → 라우드니스 정규화.

- 원본 영상 소리는 쓰지 않는다 (audio.original: mute 고정).
- 효과음: script.json 문장의 sfx 큐 위치(문장 첫 단어 직전)에 넣는다. assets/sfx/{이름}.wav|mp3|… 가 있으면 그것을,
  없으면 기본 효과음(whoosh·swish·pop·ding)을 FFmpeg로 직접 합성해 쓴다 (외부 음원이 아니라 라이선스 문제 없음).
- BGM: assets/bgm/의 음원을 반복해 깔고, 말하는 동안 sidechaincompress로 낮춘다.
- 라우드니스: 측정 → 게인+리미터 → 다시 측정 → 미세 보정으로 target_lufs(기본 -14 LUFS), True Peak -1 dBTP 이하.
  (loudnorm linear 모드는 피크 여유가 없으면 dynamic으로 바뀌어 짧은 영상에서 목표에 못 미치므로 리미터로 직접 맞춘다)
"""

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path

from ssm.config import AppConfig
from ssm.media import Media, MediaError
from ssm.schemas import WordTimings
from ssm.workspace import Workspace

AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac")
SAMPLE_RATE = 48000
TRUE_PEAK = -1.0
LIMIT = 10 ** (-1.6 / 20)  # 리미터 상한 (샘플 피크 -1.6dBFS → 트루 피크 -1dBTP 이하 여유)
LOUDNESS_PASSES = 3
LOUDNESS_TOLERANCE = 0.3  # dB
SFX_GAIN_DB = -4.0
SFX_LEAD_SEC = 0.08  # 효과음을 첫 단어보다 살짝 먼저
BGM_PAUSE_ABOVE_DUCK_DB = 8.0  # 말이 없는 동안 BGM은 덕킹 수준보다 이만큼 크다
BGM_FADE_OUT_SEC = 1.5

BUILTIN_SFX = {  # 이름: FFmpeg lavfi 합성식
    "whoosh": "anoisesrc=d=0.6:c=pink:a=0.6:r=48000,bandpass=f=1800:width_type=h:w=2400,"
              "afade=t=in:d=0.3:curve=exp,afade=t=out:st=0.3:d=0.3,volume=10dB",
    "swish": "anoisesrc=d=0.35:c=white:a=0.4:r=48000,highpass=f=2500,afade=t=in:d=0.12,afade=t=out:st=0.12:d=0.23",
    "pop": "aevalsrc='0.7*sin(2*PI*(500+1500*exp(-60*t))*t)*exp(-30*t)':s=48000:d=0.18",
    "ding": "aevalsrc='0.45*sin(2*PI*1568*t)*exp(-5*t)+0.2*sin(2*PI*3136*t)*exp(-8*t)':s=48000:d=0.9",
}
NO_BGM = {"", "none", "off", "false"}


class AudioError(Exception):
    """사용자에게 그대로 보여줄 수 있는 오디오 오류."""


def _assets(cfg: AppConfig, kind: str) -> Path:
    return cfg.path(f"assets/{kind}")


def sfx_file(name: str, cfg: AppConfig, media: Media, workdir: Path) -> Path | None:
    for ext in AUDIO_EXTS:
        user = _assets(cfg, "sfx") / f"{name}{ext}"
        if user.is_file():
            return user
    if name not in BUILTIN_SFX:
        return None
    out = workdir / f"sfx_{name}.wav"
    if not out.is_file():
        media.run(["-f", "lavfi", "-i", BUILTIN_SFX[name], "-ar", str(SAMPLE_RATE), str(out)], what=f"효과음 {name} 만들기")
    return out


def bgm_file(cfg: AppConfig, project_id: str) -> Path | None:
    """audio.bgm: auto(assets/bgm/에서 프로젝트마다 하나 고름) | none | 파일 경로."""
    choice = str(cfg.audio.bgm).strip()
    if choice.lower() in NO_BGM:
        return None
    if choice.lower() == "auto":
        folder = _assets(cfg, "bgm")
        files = sorted(p for p in folder.glob("*") if p.suffix.lower() in AUDIO_EXTS) if folder.is_dir() else []
        if not files:
            return None
        return files[int(hashlib.sha256(project_id.encode()).hexdigest(), 16) % len(files)]
    path = cfg.path(choice)
    if not path.is_file():
        raise AudioError(f"BGM 파일을 찾을 수 없습니다: {choice} → `ssm set audio.bgm auto`(assets/bgm에서 자동 선택) "
                         "또는 `ssm set audio.bgm none`(BGM 없음)으로 바꾸세요.")
    return path


def _loudnorm_stats(stderr: str) -> dict:
    blocks = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr)
    if not blocks:
        raise MediaError("라우드니스 측정 결과를 읽지 못했습니다.")
    return json.loads(blocks[-1])


def measure(media: Media, inputs: list[str], target: float, what: str, graph: str | None = None,
            post: str = "") -> dict:
    """loudnorm 측정값. graph가 있으면 그 필터 그래프의 [mix] 출력(+post 필터)을, 없으면 첫 입력을 잰다."""
    ln = f"{post}," if post else ""
    ln += f"loudnorm=I={target}:TP={TRUE_PEAK}:LRA=11:print_format=json"
    filters = ["-filter_complex", f"{graph};[mix]{ln}"] if graph else ["-af", ln]
    media.run([*inputs, *filters, "-f", "null", "-"], what=what)
    return _loudnorm_stats(media.last_stderr)


def _lufs(stats: dict) -> float | None:
    try:
        value = float(stats["input_i"])
    except (KeyError, ValueError):
        return None
    return value if value > -70 else None  # 무음이면 -inf


def mix_audio(ws: Workspace, cfg: AppConfig, timings: WordTimings, total: float, workdir: Path, media: Media,
              log: Callable[[str], None] = print) -> Path:
    """render 폴더에 audio_mix.wav(48kHz 스테레오, 라우드니스 정규화)를 만든다."""
    target = cfg.audio.target_lufs
    voice = ws.path / "tts.mp3"
    inputs = ["-i", str(voice)]
    graph = [f"[0:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,apad=whole_dur={total:.3f}[voice]"]
    mix = []

    # 효과음
    missing = set()
    n_in = 1
    for s in timings.sentences:
        if not s.sfx:
            continue
        path = sfx_file(s.sfx, cfg, media, workdir)
        if path is None:
            missing.add(s.sfx)
            continue
        at = max(0.0, (s.words[0].start if s.words else s.start) - SFX_LEAD_SEC)
        inputs += ["-i", str(path)]
        ms = int(at * 1000)
        graph.append(f"[{n_in}:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,volume={SFX_GAIN_DB}dB,"
                     f"adelay={ms}:all=1[sfx{n_in}]")
        mix.append(f"[sfx{n_in}]")
        n_in += 1
    if missing:
        log(f"[주의] 효과음 {', '.join(sorted(missing))}을(를) 찾지 못해 넣지 않았습니다 "
            f"(assets/sfx/에 같은 이름의 파일을 두거나 기본 효과음 {', '.join(BUILTIN_SFX)} 중에서 쓰세요).")

    # BGM (말하는 동안 덕킹)
    bgm = bgm_file(cfg, ws.id)
    if bgm is None:
        graph.append("[voice]anull[v1]")
        if str(cfg.audio.bgm).strip().lower() == "auto":
            log("[참고] assets/bgm/에 음원이 없어 BGM 없이 만듭니다 (저작권 프리 음원을 넣으면 자동으로 깔립니다).")
    else:
        voice_lufs = _lufs(measure(media, ["-i", str(voice)], target, "음성 크기 측정"))
        bgm_lufs = _lufs(measure(media, ["-t", "60", "-i", str(bgm)], target, "BGM 크기 측정"))
        gain = 0.0
        if voice_lufs is not None and bgm_lufs is not None:
            gain = voice_lufs + cfg.audio.bgm_duck_db + BGM_PAUSE_ABOVE_DUCK_DB - bgm_lufs
        inputs += ["-stream_loop", "-1", "-i", str(bgm)]
        fade_at = max(0.0, total - BGM_FADE_OUT_SEC)
        graph += [
            "[voice]asplit[v1][sc]",
            f"[{n_in}:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,atrim=0:{total:.3f},"
            f"volume={gain:.2f}dB,afade=t=out:st={fade_at:.3f}:d={BGM_FADE_OUT_SEC}[bgm]",
            "[bgm][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[ducked]",
        ]
        mix.append("[ducked]")
        log(f"  BGM: {bgm.name} (말하는 동안 약 {cfg.audio.bgm_duck_db:.0f}dB로 낮춤)")

    graph.append(f"[v1]{''.join(mix)}amix=inputs={1 + len(mix)}:normalize=0:duration=first,"
                 f"atrim=0:{total:.3f}[mix]")
    base = ";".join(graph)

    # 라우드니스: 측정 → 게인+리미터 → 다시 측정 → 미세 보정 (+리미터)
    first = _lufs(measure(media, inputs, target, "라우드니스 측정", graph=base))
    if first is None:
        raise AudioError("음성이 비어 있습니다 (무음) → `ssm tts`를 다시 실행하세요.")
    limiter = f"alimiter=limit={LIMIT:.4f}:attack=5:release=50:level=false"
    chain, current = "", first
    for _ in range(LOUDNESS_PASSES):  # 리미터가 깎은 만큼 다시 올린다 (보통 2번이면 0.3dB 이내)
        chain += ("," if chain else "") + f"volume={target - current:.2f}dB,{limiter}"
        current = _lufs(measure(media, inputs, target, "라우드니스 보정", graph=base, post=chain)) or target
        if abs(target - current) <= LOUDNESS_TOLERANCE:
            break
    out = workdir / "audio_mix.wav"
    media.run([*inputs, "-filter_complex", f"{base};[mix]{chain},aresample={SAMPLE_RATE}[out]", "-map", "[out]",
               "-c:a", "pcm_s16le", str(out)], log=ws.path / "logs" / "audio.log", what="오디오 믹스")
    return out
