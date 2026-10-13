import base64
import io
import json
import urllib.error

import pytest

from app.providers import MEDIA_PROVIDERS, get_media_provider
from app.providers import gemini_video
from app.providers.gemini_video import GeminiVideoProvider, clip_seconds, rate_for
from app.providers.media import MediaRequest, ProviderError

KEY = "test-key-should-not-leak"
OP = "models/veo-3.1-lite-generate-preview/operations/abc123"
VIDEO_URI = "https://example.invalid/files/video-1:download?alt=media"
VIDEO_BYTES = b"\x00\x00\x00\x18ftypmp42fake-mp4"


class FakeResponse:
    def __init__(self, data: bytes):
        self.data = data

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def fake(monkeypatch):
    """predictLongRunning → 작업 조회(진행 중 → 완료) → 영상 다운로드 순서를 흉내 낸다."""
    state = {"requests": [], "polls_until_done": 2, "final": None, "start_error": None}

    def done_payload():
        return state["final"] or {"name": OP, "done": True, "response": {"generateVideoResponse": {
            "generatedSamples": [{"video": {"uri": VIDEO_URI}}]}}}

    def fake_urlopen(request, timeout=None):
        state["requests"].append(request)
        url = request.full_url
        if url.endswith(":predictLongRunning"):
            if state["start_error"]:
                raise state["start_error"]
            return FakeResponse(json.dumps({"name": OP}).encode())
        if url.endswith(OP):
            state["polls_until_done"] -= 1
            payload = done_payload() if state["polls_until_done"] <= 0 else {"name": OP, "done": False}
            return FakeResponse(json.dumps(payload).encode())
        if url == VIDEO_URI:
            return FakeResponse(VIDEO_BYTES)
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(gemini_video.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(gemini_video.time, "sleep", lambda s: None)
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    for k in ("AISS_GEMINI_VIDEO_MODEL", "AISS_GEMINI_VIDEO_RESOLUTION", "AISS_GEMINI_API_BASE"):
        monkeypatch.delenv(k, raising=False)
    return state


def req(tmp_path, duration=5.0, source=None, ratio="9:16"):
    return MediaRequest(kind="video", prompt="old man breathes heavily --ar 9:16", aspect_ratio=ratio, duration_sec=duration,
                        scene_number=1, version=1, attempt=1, output_path=tmp_path / "video_v1", source_image=source)


@pytest.mark.parametrize("sec,expected", [(0.5, 4), (4, 4), (4.5, 6), (6, 6), (7, 8), (8, 8), (15, 8)])
def test_clip_seconds(sec, expected):
    assert clip_seconds(sec) == expected


def test_rates():
    assert rate_for("veo-3.1-lite-generate-preview", "720p") == 0.05
    assert rate_for("veo-3.1-lite-generate-preview", "1080p") == 0.08
    assert rate_for("veo-3.1-fast-generate-preview", "720p") == 0.10
    assert rate_for("veo-3.1-generate-preview", "1080p") == 0.40
    assert rate_for("veo-9-unknown", "720p") == 0.40


def test_estimate_cost(monkeypatch):
    p = GeminiVideoProvider()
    assert p.estimate_cost(15) == 0.40  # 8초 × $0.05
    assert p.estimate_cost(3) == 0.20  # 4초
    monkeypatch.setenv("AISS_GEMINI_VIDEO_RESOLUTION", "1080p")
    assert GeminiVideoProvider().estimate_cost(8) == 0.64


def test_generate_text_to_video(tmp_path, fake):
    result = GeminiVideoProvider().generate(req(tmp_path, duration=5.0))
    start, *polls, download = fake["requests"]
    assert start.full_url.endswith("/models/veo-3.1-lite-generate-preview:predictLongRunning")
    assert KEY not in start.full_url and start.get_header("X-goog-api-key") == KEY
    body = json.loads(start.data)
    assert body["instances"][0] == {"prompt": "old man breathes heavily"}
    assert body["parameters"] == {"aspectRatio": "9:16", "durationSeconds": 6, "resolution": "720p"}
    assert len(polls) == 2 and polls[0].get_method() == "GET"
    assert download.full_url == VIDEO_URI and download.get_header("X-goog-api-key") == KEY

    assert result.file_path.suffix == ".mp4" and result.file_path.read_bytes() == VIDEO_BYTES
    assert result.cost_amount == 0.30 and result.metadata["clip_sec"] == 6
    assert result.metadata["image_to_video"] is False and KEY not in json.dumps(result.metadata)


def test_generate_image_to_video(tmp_path, fake):
    image = tmp_path / "image_v1.png"
    image.write_bytes(b"\x89PNG fake")
    result = GeminiVideoProvider().generate(req(tmp_path, duration=15, source=image, ratio="1:1"))
    body = json.loads(fake["requests"][0].data)
    assert body["instances"][0]["image"] == {"bytesBase64Encoded": base64.b64encode(b"\x89PNG fake").decode(), "mimeType": "image/png"}
    assert body["parameters"]["aspectRatio"] == "9:16"  # Veo는 1:1을 받지 않는다
    assert body["parameters"]["durationSeconds"] == 8
    assert result.metadata["image_to_video"] is True and result.metadata["scene_sec"] == 15


def test_operation_error_and_filters(tmp_path, fake):
    fake["final"] = {"name": OP, "done": True, "error": {"code": 3, "message": "Image is too small"}}
    with pytest.raises(ProviderError, match="Image is too small"):
        GeminiVideoProvider().generate(req(tmp_path))
    fake["polls_until_done"] = 1
    fake["final"] = {"name": OP, "done": True, "response": {"generateVideoResponse": {"raiMediaFilteredReasons": ["person"]}}}
    with pytest.raises(ProviderError, match="안전 필터"):
        GeminiVideoProvider().generate(req(tmp_path))


def test_start_http_error(tmp_path, fake):
    fake["start_error"] = urllib.error.HTTPError("u", 404, "nf", {}, io.BytesIO(b'{"error":{"message":"model not found"}}'))
    with pytest.raises(ProviderError, match="찾을 수 없습니다") as exc:
        GeminiVideoProvider().generate(req(tmp_path))
    assert KEY not in str(exc.value)


def test_timeout(tmp_path, fake, monkeypatch):
    fake["polls_until_done"] = 10**9
    monkeypatch.setenv("AISS_GEMINI_VIDEO_TIMEOUT_SEC", "0")
    with pytest.raises(ProviderError, match="끝나지 않았습니다"):
        GeminiVideoProvider().generate(req(tmp_path))


def test_missing_key(tmp_path, fake, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        GeminiVideoProvider().generate(req(tmp_path))
    assert fake["requests"] == []


def test_api_flow_uses_latest_image_and_confirms_cost(client, fake, monkeypatch):
    monkeypatch.setenv("AISS_VIDEO_PROVIDER", "gemini")
    assert MEDIA_PROVIDERS["video"]["gemini"] is GeminiVideoProvider
    assert get_media_provider("video").is_paid
    info = {p["kind"]: p for p in client.get("/api/providers").json()}["video"]
    assert info["name"] == "gemini" and info["estimated_cost_per_job"] == 0.40  # 8초 기준 안내

    pid = client.post("/api/projects", json={"title": "갈릴레오"}).json()["id"]
    sid = client.post(f"/api/projects/{pid}/scenes", json={"image_prompt": "Galileo", "video_prompt": "breathes heavily", "duration_sec": 10}).json()["id"]
    client.post(f"/api/scenes/{sid}/generate-image")  # 이미지는 mock
    res = client.post(f"/api/scenes/{sid}/generate-video")
    assert res.status_code == 409 and "0.4" in res.json()["detail"]

    job = client.post(f"/api/scenes/{sid}/generate-video", json={"confirm_paid": True}).json()
    job = client.get(f"/api/jobs/{job['id']}").json()
    assert job["status"] == "succeeded" and job["provider"] == "gemini", job["error_message"]
    body = json.loads(fake["requests"][0].data)
    assert "image" in body["instances"][0]  # 최신 이미지로 영상을 만든다
    assert body["instances"][0]["prompt"] == "breathes heavily"
    video = [a for a in client.get(f"/api/projects/{pid}/assets").json() if a["asset_type"] == "video"][0]
    assert video["cost_amount"] == 0.40 and video["metadata"]["clip_sec"] == 8
