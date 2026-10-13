import base64
import io
import json
import urllib.error

import pytest
from PIL import Image

from app import config
from app.providers import MEDIA_PROVIDERS, get_media_provider
from app.providers import gemini_image
from app.providers.gemini_image import GeminiImageProvider, clean_prompt
from app.providers.media import MediaRequest, ProviderError

KEY = "test-key-should-not-leak"


def png_bytes(size=(90, 160)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 120, 40)).save(buf, "PNG")
    return buf.getvalue()


def ok_response(mime="image/png", camel=True):
    inline = {"mimeType" if camel else "mime_type": mime, "data": base64.b64encode(png_bytes()).decode()}
    part = {"inlineData": inline} if camel else {"inline_data": inline}
    return {"candidates": [{"content": {"parts": [{"text": "here you go"}, part]}, "finishReason": "STOP"}],
            "usageMetadata": {"totalTokenCount": 1300}}


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def calls(monkeypatch):
    """urlopen을 가짜로 바꾸고 보낸 요청을 기록한다."""
    seen = []
    state = {"response": ok_response(), "error": None}

    def fake_urlopen(request, timeout=None):
        seen.append(request)
        if state["error"]:
            raise state["error"]
        return FakeResponse(state["response"])

    monkeypatch.setattr(gemini_image.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    monkeypatch.delenv("AISS_GEMINI_IMAGE_MODEL", raising=False)
    monkeypatch.delenv("AISS_GEMINI_IMAGE_COST", raising=False)
    return seen, state


def req(tmp_path, prompt="old man in a carriage --ar 9:16 --style raw", ratio="9:16"):
    return MediaRequest(kind="image", prompt=prompt, aspect_ratio=ratio, duration_sec=5, scene_number=1,
                        version=1, attempt=1, output_path=tmp_path / "image_v1")


def test_clean_prompt_removes_midjourney_flags():
    assert clean_prompt("a cat --ar 9:16 --style raw") == "a cat"
    assert clean_prompt("a cat, warm light --v 6 --stylize 250 --no text") == "a cat, warm light"
    assert clean_prompt("a well-lit room -- dash") == "a well-lit room -- dash"


def test_generate_sends_expected_request_and_saves_image(tmp_path, calls):
    seen, _ = calls
    result = GeminiImageProvider().generate(req(tmp_path))
    request = seen[0]
    assert request.full_url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image:generateContent"
    assert KEY not in request.full_url  # 키는 헤더로만
    assert request.get_header("X-goog-api-key") == KEY
    body = json.loads(request.data)
    assert body["contents"][0]["parts"][0]["text"] == "old man in a carriage"
    assert body["generationConfig"]["imageConfig"] == {"aspectRatio": "9:16"}
    assert "IMAGE" in body["generationConfig"]["responseModalities"]

    assert result.file_path.suffix == ".png" and result.file_path.exists()
    with Image.open(result.file_path) as img:
        assert img.size == (90, 160)
    assert result.cost_amount == 0.067 and result.cost_currency == "USD"
    assert result.metadata["model"] == "gemini-3.1-flash-image" and result.metadata["estimated"] is True
    assert KEY not in json.dumps(result.metadata)


def test_snake_case_and_jpeg_response(tmp_path, calls):
    _, state = calls
    state["response"] = ok_response(mime="image/jpeg", camel=False)
    assert GeminiImageProvider().generate(req(tmp_path)).file_path.suffix == ".jpg"


def test_model_and_cost_can_be_configured(tmp_path, calls, monkeypatch):
    seen, _ = calls
    monkeypatch.setenv("AISS_GEMINI_IMAGE_MODEL", "gemini-3.1-flash-lite-image")
    p = GeminiImageProvider()
    assert p.estimate_cost(5) == 0.034
    p.generate(req(tmp_path, ratio="16:9"))
    assert "gemini-3.1-flash-lite-image:generateContent" in seen[0].full_url
    assert json.loads(seen[0].data)["generationConfig"]["imageConfig"]["aspectRatio"] == "16:9"
    monkeypatch.setenv("AISS_GEMINI_IMAGE_COST", "0.05")
    assert GeminiImageProvider().estimate_cost(5) == 0.05
    monkeypatch.setenv("AISS_GEMINI_IMAGE_MODEL", "some-future-model")
    monkeypatch.delenv("AISS_GEMINI_IMAGE_COST")
    assert GeminiImageProvider().estimate_cost(5) == 0.07


def test_missing_key(tmp_path, calls, monkeypatch):
    seen, _ = calls
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        GeminiImageProvider().generate(req(tmp_path))
    assert seen == []


@pytest.mark.parametrize("status,needle", [(400, "Gemini API 오류 (400)"), (403, "키가 올바르지"), (404, "찾을 수 없습니다"), (429, "사용량 한도")])
def test_http_errors_become_korean_messages(tmp_path, calls, status, needle):
    _, state = calls
    body = json.dumps({"error": {"message": "Billing required for this model"}}).encode()
    state["error"] = urllib.error.HTTPError("u", status, "err", {}, io.BytesIO(body))
    with pytest.raises(ProviderError) as exc:
        GeminiImageProvider().generate(req(tmp_path))
    assert needle in str(exc.value) and "Billing required" in str(exc.value)
    assert KEY not in str(exc.value)


def test_network_error(tmp_path, calls):
    _, state = calls
    state["error"] = urllib.error.URLError("Name or service not known")
    with pytest.raises(ProviderError, match="연결할 수 없습니다"):
        GeminiImageProvider().generate(req(tmp_path))


def test_blocked_or_textonly_responses(tmp_path, calls):
    _, state = calls
    state["response"] = {"promptFeedback": {"blockReason": "SAFETY"}}
    with pytest.raises(ProviderError, match="거절"):
        GeminiImageProvider().generate(req(tmp_path))
    state["response"] = {"candidates": [{"content": {"parts": []}, "finishReason": "IMAGE_SAFETY"}]}
    with pytest.raises(ProviderError, match="안전 필터"):
        GeminiImageProvider().generate(req(tmp_path))
    state["response"] = {"candidates": [{"content": {"parts": [{"text": "I can't draw that."}]}, "finishReason": "STOP"}]}
    with pytest.raises(ProviderError, match="I can't draw that"):
        GeminiImageProvider().generate(req(tmp_path))


def test_registered_and_selected_by_env(monkeypatch):
    assert MEDIA_PROVIDERS["image"]["gemini"] is GeminiImageProvider
    monkeypatch.setenv("AISS_IMAGE_PROVIDER", "gemini")
    p = get_media_provider("image")
    assert p.name == "gemini" and p.is_paid


def test_api_flow_requires_cost_confirmation(client, calls, monkeypatch):
    """유료 공급자이므로 확인 없이 요청하면 409, 확인하면 생성되고 비용이 기록된다."""
    monkeypatch.setenv("AISS_IMAGE_PROVIDER", "gemini")
    info = {p["kind"]: p for p in client.get("/api/providers").json()}["image"]
    assert info["name"] == "gemini" and info["is_paid"] and info["estimated_cost_per_job"] == 0.067

    pid = client.post("/api/projects", json={"title": "갈릴레오"}).json()["id"]
    sid = client.post(f"/api/projects/{pid}/scenes", json={"image_prompt": "Galileo selfie --ar 9:16"}).json()["id"]
    res = client.post(f"/api/scenes/{sid}/generate-image")
    assert res.status_code == 409 and "0.067" in res.json()["detail"]

    job = client.post(f"/api/scenes/{sid}/generate-image", json={"confirm_paid": True}).json()
    job = client.get(f"/api/jobs/{job['id']}").json()
    assert job["status"] == "succeeded" and job["provider"] == "gemini"
    asset = client.get(f"/api/projects/{pid}/assets").json()[0]
    assert asset["provider"] == "gemini" and asset["cost_amount"] == 0.067
    assert client.get(asset["url"]).headers["content-type"] == "image/png"
    assert client.post(f"/api/scenes/{sid}/approve").status_code == 200


def test_api_failure_is_retryable(client, calls, monkeypatch):
    _, state = calls
    monkeypatch.setenv("AISS_IMAGE_PROVIDER", "gemini")
    pid = client.post("/api/projects", json={"title": "x"}).json()["id"]
    sid = client.post(f"/api/projects/{pid}/scenes", json={"image_prompt": "cat"}).json()["id"]
    state["error"] = urllib.error.HTTPError("u", 429, "err", {}, io.BytesIO(b"{}"))
    job = client.post(f"/api/scenes/{sid}/generate-image", json={"confirm_paid": True}).json()
    job = client.get(f"/api/jobs/{job['id']}").json()
    assert job["status"] == "failed" and "사용량 한도" in job["error_message"]
    assert client.post(f"/api/jobs/{job['id']}/retry").status_code == 409  # 재시도도 비용 확인 필요
    state["error"] = None
    client.post(f"/api/jobs/{job['id']}/retry", json={"confirm_paid": True})
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "succeeded"


def test_env_file_loader(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "﻿# 주석\nAISS_T1=plain\nexport AISS_T2=\"quoted value\"\nAISS_T3='single'\n"
        "AISS_T4=value # trailing comment\nAISS_T5=already\nbroken line\n\n", encoding="utf-8")
    for k in ("AISS_T1", "AISS_T2", "AISS_T3", "AISS_T4"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AISS_T5", "from-shell")
    config.load_env_file(env)
    import os
    assert [os.environ[k] for k in ("AISS_T1", "AISS_T2", "AISS_T3", "AISS_T4", "AISS_T5")] == \
        ["plain", "quoted value", "single", "value", "from-shell"]
    for k in ("AISS_T1", "AISS_T2", "AISS_T3", "AISS_T4"):
        monkeypatch.delenv(k)
    config.load_env_file(tmp_path / "missing.env")  # 없으면 조용히 넘어간다
