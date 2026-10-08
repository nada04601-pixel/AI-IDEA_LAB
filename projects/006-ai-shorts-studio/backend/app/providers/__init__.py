import os

from app.providers.base import ScriptProvider
from app.providers.media import MediaProvider
from app.providers.mock import MockScriptProvider
from app.providers.mock_media import MockImageProvider, MockVideoProvider

_SCRIPT_PROVIDERS: dict[str, type] = {"mock": MockScriptProvider}
MEDIA_PROVIDERS: dict[str, dict[str, type]] = {
    "image": {"mock": MockImageProvider},
    "video": {"mock": MockVideoProvider},
}


def get_script_provider() -> ScriptProvider:
    """AISS_SCRIPT_PROVIDER 환경 변수로 공급자를 고른다 (기본: mock)."""
    name = os.getenv("AISS_SCRIPT_PROVIDER", "mock")
    try:
        return _SCRIPT_PROVIDERS[name]()
    except KeyError:
        raise RuntimeError(f"알 수 없는 대본 공급자입니다: {name} (사용 가능: {', '.join(_SCRIPT_PROVIDERS)})")


def media_provider_name(kind: str) -> str:
    """AISS_IMAGE_PROVIDER / AISS_VIDEO_PROVIDER 환경 변수 (기본: mock)."""
    return os.getenv(f"AISS_{kind.upper()}_PROVIDER", "mock")


def get_media_provider(kind: str, name: str | None = None) -> MediaProvider:
    name = name or media_provider_name(kind)
    try:
        return MEDIA_PROVIDERS[kind][name]()
    except KeyError:
        available = ", ".join(MEDIA_PROVIDERS.get(kind, {}))
        raise RuntimeError(f"알 수 없는 {kind} 공급자입니다: {name} (사용 가능: {available})")
