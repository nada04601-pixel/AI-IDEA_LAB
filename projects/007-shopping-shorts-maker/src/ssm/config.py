"""설정 읽기.

config.yaml(기본값) ← config.local.yaml(개인 설정) ← 프로젝트별 overrides 순서로 덮어쓴 뒤 검증한다.
"""

import copy
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

ADS = ("coupang", "aliexpress", "custom")
DURATIONS = (15, 30, 45, 60)
FPS_CHOICES = (30, 60)


def app_root() -> Path:
    """config.yaml이 있는 프로젝트 폴더. 테스트나 다른 위치에서 쓰려면 SSM_HOME을 지정한다."""
    env = os.getenv("SSM_HOME")
    return Path(env).resolve() if env else Path(__file__).resolve().parents[2]


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")  # 오타 난 키를 조용히 무시하지 않는다


class ProjectCfg(_Section):
    duration_sec: Literal[15, 30, 45, 60] = 30


class VideoCfg(_Section):
    width: int = 1080
    height: int = 1920
    fps: Literal[30, 60] = 30
    crf: int = Field(20, ge=0, le=51)
    encoder: Literal["auto", "libx264", "h264_nvenc"] = "auto"


class SubtitleCfg(_Section):
    font: str = "assets/fonts/Pretendard-ExtraBold.otf"
    size: int = Field(78, ge=10, le=300)
    max_chars_per_line: int = Field(14, ge=4, le=40)
    position_y_ratio: float = Field(0.66, ge=0.0, le=1.0)
    color: str = "#FFFFFF"
    emphasis_color: str = "#FFE14D"
    stroke_width: int = Field(7, ge=0, le=30)
    box: bool = False


class ThumbnailCfg(_Section):
    font: str = "assets/fonts/BlackHanSans-Regular.ttf"
    top_color: str = "#FFE14D"
    bottom_color: str = "#FFFFFF"


class AdDisclosureCfg(_Section):
    profile: Literal["coupang", "aliexpress", "custom"] | None = None
    custom_text: str = ""
    profiles: dict[str, str] = Field(default_factory=dict)
    position: Literal["top_left", "top_center"] = "top_left"

    @model_validator(mode="after")
    def _check(self) -> "AdDisclosureCfg":
        if self.profile == "custom" and not self.custom_text.strip():
            raise ValueError("광고 프로필이 custom이면 custom_text(직접 입력 문구)가 필요합니다.")
        if self.profile in ("coupang", "aliexpress") and not self.profiles.get(self.profile, "").strip():
            raise ValueError(f"광고 프로필 '{self.profile}'의 문구가 profiles에 없습니다.")
        return self

    def text(self) -> str | None:
        """영상·캡션에 넣을 광고 문구. 프로필을 아직 고르지 않았으면 None."""
        if self.profile is None:
            return None
        return self.custom_text.strip() if self.profile == "custom" else self.profiles[self.profile].strip()


class TTSCfg(_Section):
    provider: Literal["edge"] = "edge"
    voice: str = "ko-KR-SunHiNeural"
    rate: str = "+10%"


class AudioCfg(_Section):
    original: Literal["mute"] = "mute"
    bgm: str = "auto"
    bgm_duck_db: float = -18
    target_lufs: float = -14


class CollectorCfg(_Section):
    max_videos: int = Field(5, ge=1, le=10)
    same_product_threshold: float = Field(0.80, ge=0.0, le=1.0)
    mood_threshold: float = Field(0.60, ge=0.0, le=1.0)
    cookies_file: str | None = "secrets/cookies.txt"

    @model_validator(mode="after")
    def _check(self) -> "CollectorCfg":
        if self.mood_threshold > self.same_product_threshold:
            raise ValueError("mood_threshold는 same_product_threshold보다 클 수 없습니다.")
        return self


class LLMCfg(_Section):
    provider: Literal["claude_code"] = "claude_code"


class AppConfig(_Section):
    project: ProjectCfg = ProjectCfg()
    video: VideoCfg = VideoCfg()
    subtitle: SubtitleCfg = SubtitleCfg()
    thumbnail: ThumbnailCfg = ThumbnailCfg()
    foreign_sub_removal: Literal["auto", "crop", "blur", "inpaint"] = "auto"
    ad_disclosure: AdDisclosureCfg = AdDisclosureCfg()
    tts: TTSCfg = TTSCfg()
    audio: AudioCfg = AudioCfg()
    collector: CollectorCfg = CollectorCfg()
    device: Literal["auto", "cuda", "cpu"] = "auto"
    ffmpeg_path: str | None = None
    workspace_dir: str = "workspace"
    llm: LLMCfg = LLMCfg()

    def path(self, relative: str) -> Path:
        """설정에 적힌 경로를 실제 경로로 바꾼다 (상대 경로는 app_root 기준)."""
        p = Path(relative).expanduser()
        return p if p.is_absolute() else app_root() / p


def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _read_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}의 최상위는 '키: 값' 형식이어야 합니다.")
    return data


def raw_config(overrides: dict | None = None) -> dict:
    root = app_root()
    data = deep_merge(_read_yaml(root / "config.yaml"), _read_yaml(root / "config.local.yaml"))
    return deep_merge(data, overrides or {})


def load_config(overrides: dict | None = None) -> AppConfig:
    return AppConfig.model_validate(raw_config(overrides))


def set_dotted(data: dict, dotted_key: str, value: Any) -> dict:
    """{'a': {'b': 1}}에 'a.c'=2를 넣은 새 dict를 돌려준다."""
    out = copy.deepcopy(data)
    node = out
    *parents, last = dotted_key.split(".")
    for part in parents:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[last] = value
    return out
