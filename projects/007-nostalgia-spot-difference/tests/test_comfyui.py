"""ComfyUI 연동 테스트. 실제 GPU 대신 같은 HTTP API를 흉내 내는 가짜 서버를 띄운다."""
import email
import email.policy
import json
import random
import shutil
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest
from PIL import Image, ImageDraw

from src.image_generator import ComfyUIClient, ImageSourceError


class FakeComfy:
    def __init__(self):
        self.uploads: dict[str, Image.Image] = {}
        self.prompts: dict[str, dict] = {}
        self.fail_upload = False


def _handler(state: FakeComfy):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            data = json.dumps(body).encode() if ctype == "application/json" else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/system_stats":
                return self._send(200, {"devices": [{"name": "FAKE RTX 3060", "vram_total": 12 * 1024**3}]})
            if u.path.startswith("/history/"):
                pid = u.path.split("/")[-1]
                if pid not in state.prompts:
                    return self._send(200, {})
                return self._send(200, {pid: {"status": {"status_str": "success", "completed": True},
                                              "outputs": {"9": {"images": [{"filename": f"{pid}.png",
                                                                            "subfolder": "", "type": "output"}]}}}})
            if u.path == "/view":
                pid = parse_qs(u.query)["filename"][0][:-4]
                img = self._render(state.prompts[pid])
                buf = BytesIO()
                img.save(buf, format="PNG")
                return self._send(200, buf.getvalue(), "image/png")
            self._send(404, {})

        def _render(self, wf):
            load = next((n for n in wf.values() if n["class_type"] == "LoadImage"), None)
            if load:  # 인페인팅 흉내: 투명한(마스크) 곳에 갈색 항아리 모양을 그린다
                src = state.uploads[load["inputs"]["image"]]
                rgb = src.convert("RGB")
                alpha = np.asarray(src.getchannel("A"))
                ys, xs = np.where(alpha < 128)
                d = ImageDraw.Draw(rgb)
                d.ellipse([xs.min() + 10, ys.min() + 10, xs.max() - 10, ys.max() - 10], fill=(120, 70, 40))
                return rgb
            lat = next(n for n in wf.values() if n["class_type"] == "EmptyLatentImage")["inputs"]
            seed = next(n for n in wf.values() if n["class_type"] == "KSampler")["inputs"]["seed"]
            from src.scenes import build_scene, render_scene
            scene = render_scene(build_scene("village", seed % 1000, None, None))
            return scene.resize((lat["width"], lat["height"]))

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            if self.path == "/prompt":
                pid = uuid.uuid4().hex
                state.prompts[pid] = json.loads(body)["prompt"]
                return self._send(200, {"prompt_id": pid, "number": 1})
            if self.path == "/upload/image":
                if state.fail_upload:
                    return self._send(500, {"error": "boom"})
                msg = email.message_from_bytes(
                    b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + body,
                    policy=email.policy.default)
                for part in msg.iter_parts():
                    if part.get_param("name", header="content-disposition") == "image":
                        name = part.get_filename()
                        state.uploads[name] = Image.open(BytesIO(part.get_payload(decode=True)))
                        return self._send(200, {"name": name, "subfolder": "", "type": "input"})
                return self._send(400, {})
            self._send(404, {})

    return H


@pytest.fixture
def comfy(settings, monkeypatch):
    state = FakeComfy()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    settings.comfyui_url = f"http://127.0.0.1:{server.server_address[1]}"
    settings.image_source = "comfyui"
    # 테스트용 임시 루트에 워크플로 복사
    from tests.conftest import ROOT
    (settings.root / "workflows").mkdir(exist_ok=True)
    for f in ("comfyui_workflow.json", "comfyui_inpaint.json"):
        shutil.copy(ROOT / "workflows" / f, settings.root / "workflows" / f)
    monkeypatch.setattr(ComfyUIClient, "poll_interval", 0.01)
    yield state
    server.shutdown()


def test_generate_fills_placeholders(settings, comfy):
    c = ComfyUIClient(settings)
    assert c.ping()
    assert c.system_info()["devices"][0]["name"] == "FAKE RTX 3060"
    img = c.generate({"id": "x", "title": "고향 마을", "prompt": "korean village"}, 1234)
    assert img.size == (1216, 832)
    wf = next(iter(comfy.prompts.values()))
    assert wf["3"]["inputs"]["seed"] == 1234  # 숫자 자리는 숫자로
    assert wf["4"]["inputs"]["ckpt_name"] == settings.comfyui_checkpoint
    assert "korean village" in wf["6"]["inputs"]["text"] and "storybook" in wf["6"]["inputs"]["text"]
    assert "%" not in json.dumps(wf)


def test_inpaint_changes_only_mask(settings, comfy):
    c = ComfyUIClient(settings)
    base = Image.new("RGB", (400, 300), (230, 220, 200))
    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).rectangle([150, 100, 250, 200], fill=255)
    out = c.inpaint(base, mask, "a jar", 5)
    a, b = np.asarray(base, int), np.asarray(out, int)
    changed = np.abs(a - b).max(axis=2) > 20
    assert changed[100:200, 150:250].mean() > 0.3
    assert changed[:90].sum() == 0
    wf = next(iter(comfy.prompts.values()))
    assert wf["1"]["inputs"]["image"] in comfy.uploads


def test_unreachable_server(settings):
    settings.comfyui_url = "http://127.0.0.1:9"
    with pytest.raises(ImageSourceError):
        ComfyUIClient(settings).generate({"id": "x", "title": "t"}, 1)


def test_raster_inpaint_fallback_on_error(settings, comfy, font_path):
    from src.difference_editor import make_raster_differences
    from src.scenes import build_scene, render_scene
    comfy.fail_upload = True
    base = render_scene(build_scene("market", 3, None, font_path))
    a, b, diffs = make_raster_differences(base, 5, random.Random(3), font_path, ComfyUIClient(settings).inpaint)
    assert len(diffs) == 5  # 업로드가 실패해도 내장 방식으로 채운다


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
def test_pipeline_with_comfyui(settings, comfy):
    from src.db import JobDB
    from src.pipeline import make_one
    from src.video_renderer import Timeline
    db = JobDB(settings.path("db"))
    r = make_one(settings, db, topic_id="old_kitchen", seed=77, timeline=Timeline(1, 2, 2.5, 1))
    assert r.status == "needs_review", r.errors  # AI 그림 기반은 항상 사람 확인
    puzzle = json.loads(r.puzzle_path.read_text(encoding="utf-8"))
    assert puzzle["source_meta"]["generator"] == "comfyui"
    assert puzzle["image_size"] == [1200, 840]
    types = [d["type"] for d in puzzle["differences"]]
    assert "object_added" in types or "object_removed" in types
    assert any(p["1"]["class_type"] == "LoadImage" for p in comfy.prompts.values() if "1" in p), "인페인팅 호출"
