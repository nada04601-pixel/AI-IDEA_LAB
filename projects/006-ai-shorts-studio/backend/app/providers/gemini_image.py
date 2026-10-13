"""Google Gemini 이미지 생성 공급자 (Gemini API, generateContent).

- API 키: GEMINI_API_KEY (.env에만 넣는다. 코드·로그에 남기지 않는다)
- 모델: AISS_GEMINI_IMAGE_MODEL (기본 gemini-3.1-flash-image)
- 유료다. Google AI Pro 요금제의 월 Google Cloud 크레딧이 연결된 프로젝트의 키라면 크레딧에서 차감된다.
"""

import base64
import json
import os
import re
import urllib.error
import urllib.request

from app.providers.media import MediaRequest, MediaResult, ProviderError

API_BASE = "https://generativelanguage.googleapis.com/v1beta"  # 테스트에서만 AISS_GEMINI_API_BASE로 바꾼다
DEFAULT_MODEL = "gemini-3.1-flash-image"

# 1K 해상도 1장 기준 참고 가격(USD). 실제 청구액은 Google Cloud 결제 화면에서 확인한다.
KNOWN_COSTS = {
    "gemini-3.1-flash-lite-image": 0.034,
    "gemini-3.1-flash-image": 0.067,
    "gemini-3.1-flash-image-preview": 0.067,
    "gemini-2.5-flash-image": 0.039,
    "gemini-3-pro-image-preview": 0.134,
}
FALLBACK_COST = 0.07

# Gemini 이미지 모델이 받는 화면 비율
ASPECT_RATIOS = {"9:16", "16:9", "1:1", "3:4", "4:3"}

BLOCK_REASONS = {"SAFETY", "IMAGE_SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}


def clean_prompt(prompt: str) -> str:
    """Midjourney 전용 옵션(--ar 9:16, --style raw 등)을 지운다. 비율은 API 설정으로 따로 보낸다."""
    cleaned = re.sub(r"\s--[a-zA-Z]+(?:\s+(?!--)[^\s]+)?", "", " " + prompt)
    return " ".join(cleaned.split())


class GeminiImageProvider:
    name = "gemini"
    kind = "image"
    is_paid = True
    currency = "USD"

    def __init__(self) -> None:
        self.model = os.getenv("AISS_GEMINI_IMAGE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

    def estimate_cost(self, duration_sec: float) -> float:
        override = os.getenv("AISS_GEMINI_IMAGE_COST")
        if override:
            try:
                return float(override)
            except ValueError:
                pass
        return KNOWN_COSTS.get(self.model, FALLBACK_COST)

    def _request_body(self, req: MediaRequest) -> dict:
        prompt = clean_prompt(req.prompt)
        ratio = req.aspect_ratio if req.aspect_ratio in ASPECT_RATIOS else "9:16"
        return {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {"aspectRatio": ratio},
            },
        }

    def _post(self, body: dict, api_key: str) -> dict:
        base = os.getenv("AISS_GEMINI_API_BASE", API_BASE).rstrip("/")
        url = f"{base}/models/{self.model}:generateContent"
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},  # 키는 URL에 넣지 않는다
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderError(_http_error_message(exc.code, exc.read().decode("utf-8", "replace"), self.model))
        except urllib.error.URLError as exc:
            raise ProviderError(f"Gemini API에 연결할 수 없습니다. 인터넷 연결을 확인하세요. ({exc.reason})")
        except TimeoutError:
            raise ProviderError("Gemini API 응답이 시간 안에 오지 않았습니다. 잠시 뒤 재시도하세요.")

    def generate(self, req: MediaRequest) -> MediaResult:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ProviderError("GEMINI_API_KEY가 없습니다. projects/006-ai-shorts-studio/.env에 키를 넣고 백엔드를 다시 시작하세요.")
        data = self._post(self._request_body(req), api_key)
        mime, image = _extract_image(data)
        ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, ".png")
        path = req.output_path.with_suffix(ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image)
        usage = data.get("usageMetadata") or {}
        meta = {"model": self.model, "mime_type": mime, "estimated": True,
                "prompt": clean_prompt(req.prompt)[:500], "usage": usage}
        return MediaResult(path, self.estimate_cost(req.duration_sec), self.currency, meta)


def _extract_image(data: dict) -> tuple[str, bytes]:
    feedback = data.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        raise ProviderError(f"Gemini가 프롬프트를 거절했습니다 ({feedback['blockReason']}). 프롬프트를 바꿔 다시 시도하세요.")
    texts = []
    for cand in data.get("candidates") or []:
        for part in (cand.get("content") or {}).get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                return mime, base64.b64decode(inline["data"])
            if part.get("text"):
                texts.append(part["text"].strip())
        reason = cand.get("finishReason")
        if reason in BLOCK_REASONS:
            raise ProviderError(f"Gemini 안전 필터로 이미지가 만들어지지 않았습니다 ({reason}). 프롬프트를 바꿔 다시 시도하세요.")
    hint = f" 응답 메시지: {' '.join(texts)[:200]}" if texts else ""
    raise ProviderError("Gemini 응답에 이미지가 없습니다." + hint)


def _http_error_message(status: int, body: str, model: str) -> str:
    try:
        message = json.loads(body).get("error", {}).get("message", "")
    except (ValueError, AttributeError):
        message = ""
    message = message[:300]
    if status in (401, 403):
        return f"Gemini API 키가 올바르지 않거나 권한이 없습니다 ({status}). 키와 결제 설정을 확인하세요. {message}".strip()
    if status == 404:
        return f"Gemini 모델 '{model}'을(를) 찾을 수 없습니다. AISS_GEMINI_IMAGE_MODEL을 확인하세요. {message}".strip()
    if status == 429:
        return f"Gemini 사용량 한도를 넘었습니다 (429). 잠시 뒤 재시도하거나 결제·한도 설정을 확인하세요. {message}".strip()
    return f"Gemini API 오류 ({status}): {message or '알 수 없는 오류'}"
