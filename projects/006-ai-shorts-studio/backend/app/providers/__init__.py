import os

from app.providers.base import ScriptProvider
from app.providers.mock import MockScriptProvider

_SCRIPT_PROVIDERS: dict[str, type] = {"mock": MockScriptProvider}


def get_script_provider() -> ScriptProvider:
    """AISS_SCRIPT_PROVIDER 환경 변수로 공급자를 고른다 (기본: mock)."""
    name = os.getenv("AISS_SCRIPT_PROVIDER", "mock")
    try:
        return _SCRIPT_PROVIDERS[name]()
    except KeyError:
        raise RuntimeError(f"알 수 없는 대본 공급자입니다: {name} (사용 가능: {', '.join(_SCRIPT_PROVIDERS)})")
