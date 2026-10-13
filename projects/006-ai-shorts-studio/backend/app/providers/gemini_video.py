"""Google Veo 영상 생성 공급자 (Gemini API, predictLongRunning).

- API 키: GEMINI_API_KEY (이미지와 같은 키)
- 모델: AISS_GEMINI_VIDEO_MODEL (기본 veo-3.1-lite-generate-preview, 가장 저렴)
- 해상도: AISS_GEMINI_VIDEO_RESOLUTION (기본 720p)
- 장면의 최신 이미지가 있으면 그 이미지를 첫 화면으로 쓴다 (이미지 → 영상).
- Veo 영상 길이는 4·6·8초만 된다. 장면이 8초보다 길면 8초로 만들고, 최종 렌더링에서 마지막 화면을 늘린다.
- 유료다. 초당 요금이라 이미지보다 훨씬 비싸다.
"""

import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request

from app.providers.gemini_image import API_BASE, _http_error_message, clean_prompt
from app.providers.media import MediaRequest, MediaResult, ProviderError

DEFAULT_MODEL = "veo-3.1-lite-generate-preview"
CLIP_SECONDS = (4, 6, 8)

# 초당 참고 가격(USD, 소리 포함). 실제 청구액은 Google Cloud 결제 화면에서 확인한다.
RATES = {
    "veo-3.1-lite": {"720p": 0.05, "1080p": 0.08},
    "veo-3.1-fast": {"720p": 0.10, "1080p": 0.12, "4k": 0.30},
    "veo-3.1": {"720p": 0.40, "1080p": 0.40, "4k": 0.60},
}
FALLBACK_RATE = 0.40  # 모르는 모델은 비싸게 잡아 둔다

ASPECT_RATIOS = {"9:16", "16:9"}  # Veo가 받는 비율. 1:1 프로젝트는 9:16으로 만든다.


def clip_seconds(scene_sec: float) -> int:
    """장면 길이 이상인 가장 짧은 Veo 길이 (최대 8초)."""
    return next((s for s in CLIP_SECONDS if s >= scene_sec), CLIP_SECONDS[-1])


def rate_for(model: str, resolution: str) -> float:
    family = "veo-3.1-lite" if "lite" in model else "veo-3.1-fast" if "fast" in model else "veo-3.1" if model.startswith("veo-3.1") else ""
    return RATES.get(family, {}).get(resolution.lower(), FALLBACK_RATE)


class GeminiVideoProvider:
    name = "gemini"
    kind = "video"
    is_paid = True
    currency = "USD"

    def __init__(self) -> None:
        self.model = os.getenv("AISS_GEMINI_VIDEO_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        self.resolution = os.getenv("AISS_GEMINI_VIDEO_RESOLUTION", "720p").strip() or "720p"

    def estimate_cost(self, duration_sec: float) -> float:
        return round(rate_for(self.model, self.resolution) * clip_seconds(duration_sec), 4)

    # ---- HTTP ----
    def _base(self) -> str:
        return os.getenv("AISS_GEMINI_API_BASE", API_BASE).rstrip("/")

    def _call(self, url: str, api_key: str, body: dict | None = None, raw: bool = False):
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST" if body is not None else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as res:
                data = res.read()
        except urllib.error.HTTPError as exc:
            raise ProviderError(_http_error_message(exc.code, exc.read().decode("utf-8", "replace"), self.model))
        except urllib.error.URLError as exc:
            raise ProviderError(f"Gemini API에 연결할 수 없습니다. 인터넷 연결을 확인하세요. ({exc.reason})")
        except TimeoutError:
            raise ProviderError("Gemini API 응답이 시간 안에 오지 않았습니다. 잠시 뒤 재시도하세요.")
        return data if raw else json.loads(data.decode("utf-8"))

    def _request_body(self, req: MediaRequest) -> dict:
        instance: dict = {"prompt": clean_prompt(req.prompt)}
        if req.source_image and req.source_image.exists():
            mime = mimetypes.guess_type(req.source_image.name)[0] or "image/png"
            instance["image"] = {"bytesBase64Encoded": base64.b64encode(req.source_image.read_bytes()).decode(), "mimeType": mime}
        return {
            "instances": [instance],
            "parameters": {
                "aspectRatio": req.aspect_ratio if req.aspect_ratio in ASPECT_RATIOS else "9:16",
                "durationSeconds": clip_seconds(req.duration_sec),
                "resolution": self.resolution,
            },
        }

    def generate(self, req: MediaRequest) -> MediaResult:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ProviderError("GEMINI_API_KEY가 없습니다. projects/006-ai-shorts-studio/.env에 키를 넣고 백엔드를 다시 시작하세요.")
        base = self._base()
        body = self._request_body(req)
        started = self._call(f"{base}/models/{self.model}:predictLongRunning", api_key, body)
        op_name = started.get("name")
        if not op_name:
            raise ProviderError("Veo 작업을 시작하지 못했습니다 (응답에 작업 이름이 없음).")

        # Veo는 보통 1~6분 걸린다. 끝날 때까지 기다린다.
        poll = float(os.getenv("AISS_GEMINI_POLL_SEC", "10"))
        deadline = time.monotonic() + float(os.getenv("AISS_GEMINI_VIDEO_TIMEOUT_SEC", "1200"))
        op = started
        while not op.get("done"):
            if time.monotonic() > deadline:
                raise ProviderError(
                    f"Veo 영상이 20분 안에 끝나지 않았습니다 (작업 {op_name}). 재시도하면 새로 만들어지고 비용이 다시 듭니다."
                )
            time.sleep(poll)
            op = self._call(f"{base}/{op_name}", api_key)

        if op.get("error"):
            message = str(op["error"].get("message", ""))[:300]
            raise ProviderError(f"Veo 영상 생성 실패: {message or '알 수 없는 오류'}")
        result = (op.get("response") or {}).get("generateVideoResponse") or {}
        samples = result.get("generatedSamples") or []
        uri = ((samples[0] if samples else {}).get("video") or {}).get("uri")
        if not uri:
            reasons = result.get("raiMediaFilteredReasons") or []
            if reasons:
                raise ProviderError(f"Veo 안전 필터로 영상이 만들어지지 않았습니다: {' '.join(map(str, reasons))[:200]}")
            raise ProviderError("Veo 응답에 영상이 없습니다.")

        video = self._call(uri, api_key, raw=True)
        path = req.output_path.with_suffix(".mp4")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(video)
        seconds = clip_seconds(req.duration_sec)
        meta = {"model": self.model, "resolution": self.resolution, "clip_sec": seconds, "scene_sec": req.duration_sec,
                "image_to_video": "image" in body["instances"][0], "estimated": True,
                "prompt": clean_prompt(req.prompt)[:500]}
        return MediaResult(path, self.estimate_cost(req.duration_sec), self.currency, meta)
