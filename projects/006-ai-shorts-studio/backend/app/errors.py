"""오류 응답을 화면에 그대로 보여줄 수 있는 한국어 문장(detail)으로 통일한다."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

FIELD_LABELS = {
    "title": "제목",
    "topic": "주제",
    "target_duration_sec": "목표 길이",
    "aspect_ratio": "화면 비율",
    "visual_style": "스타일",
    "script": "대본",
    "status": "상태",
    "dialogue": "대사",
    "visual_description": "화면 설명",
    "image_prompt": "이미지 프롬프트",
    "video_prompt": "영상 프롬프트",
    "duration_sec": "장면 길이",
    "scene_ids": "장면 목록",
    "reason": "반려 사유",
    "project_id": "프로젝트 번호",
    "scene_id": "장면 번호",
    "job_id": "작업 번호",
    "asset_id": "자산 번호",
}


def josa(word: str, with_batchim: str, without: str) -> str:
    """단어 끝 글자의 받침에 맞는 조사를 붙인다. 예: josa("제목", "을", "를") → "제목을" """
    last = word[-1] if word else ""
    if "가" <= last <= "힣":
        has_batchim = (ord(last) - ord("가")) % 28 != 0
    else:
        has_batchim = last.isdigit() and last in "013678"  # 영, 일, 삼, 육, 칠, 팔
    return word + (with_batchim if has_batchim else without)


def _describe(error: dict) -> str:
    loc = [str(p) for p in error.get("loc", []) if p not in ("body", "path", "query")]
    field = FIELD_LABELS.get(loc[-1], loc[-1]) if loc else "요청"
    kind = error.get("type", "")
    ctx = error.get("ctx") or {}
    topic = josa(field, "은", "는")
    if kind == "json_invalid":
        return "요청 본문이 올바른 JSON이 아닙니다."
    if kind == "missing":
        return f"{field} 값이 필요합니다."
    if kind == "string_too_short":
        return f"{josa(field, '을', '를')} 입력하세요." if ctx.get("min_length") == 1 else f"{topic} {ctx.get('min_length')}자 이상이어야 합니다."
    if kind == "string_too_long":
        return f"{topic} {ctx.get('max_length')}자 이하로 입력하세요."
    if kind in ("greater_than_equal", "greater_than"):
        return f"{topic} {ctx.get('ge', ctx.get('gt'))} 이상이어야 합니다."
    if kind in ("less_than_equal", "less_than"):
        return f"{topic} {ctx.get('le', ctx.get('lt'))} 이하여야 합니다."
    if kind == "literal_error":
        return f"{field} 값은 {ctx.get('expected', '정해진 값')} 중 하나여야 합니다."
    if kind in ("int_parsing", "int_type", "int_from_float"):
        return f"{topic} 정수여야 합니다."
    if kind in ("float_parsing", "float_type"):
        return f"{topic} 숫자여야 합니다."
    if kind in ("bool_parsing", "bool_type"):
        return f"{topic} true 또는 false여야 합니다."
    return f"{field} 값이 올바르지 않습니다."


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError):
        errors = exc.errors()
        messages = list(dict.fromkeys(_describe(e) for e in errors))  # 중복 제거, 순서 유지
        return JSONResponse(
            status_code=422,
            content={"detail": " ".join(messages), "errors": [{"loc": e.get("loc"), "type": e.get("type")} for e in errors]},
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "서버에서 예상하지 못한 오류가 났습니다. 백엔드 터미널의 로그를 확인하세요."},
        )
