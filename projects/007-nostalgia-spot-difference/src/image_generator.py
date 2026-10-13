"""원본 장면 만들기 (플러그인 방식).

- procedural : 내장 손그림 장면. GPU·인터넷·유료 API 불필요. 기본값.
- sample     : assets/sample_images/ 의 그림을 사용 (직접 그렸거나 이용 권한이 있는 그림만).
- comfyui    : 로컬 ComfyUI 서버(HTTP API)에 워크플로를 보내 생성.

procedural은 소품 데이터(Scene)를 돌려주고, 나머지는 그림(raster)만 돌려준다.
"""
from __future__ import annotations

import copy
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps

from .config import Settings
from .scenes import H, W, Scene, build_scene

log = logging.getLogger(__name__)

STYLE_PROMPT = (
    "warm nostalgic Korean storybook illustration, hand-drawn watercolor, soft outlines, paper texture, "
    "warm beige, earthy brown, soft green and light orange palette, calm afternoon light, "
    "clear separate objects, wide shot, no people, no text"
)
NEGATIVE_PROMPT = (
    "photo, photorealistic, 3d render, text, letters, watermark, logo, signature, people, faces, "
    "chinese architecture, japanese architecture, pagoda, torii, modern buildings, cars, neon, "
    "blurry, cluttered, dark, horror"
)


class ImageSourceError(RuntimeError):
    pass


@dataclass
class BaseImage:
    source: str
    scene: Scene | None = None
    image: Image.Image | None = None
    meta: dict = field(default_factory=dict)

    @property
    def is_scene(self) -> bool:
        return self.scene is not None


def fit_canvas(img: Image.Image, size=(W, H)) -> Image.Image:
    """비율을 유지한 채 가운데를 잘라 장면 크기(10:7)에 맞춘다."""
    return ImageOps.fit(img.convert("RGB"), size, Image.LANCZOS, centering=(0.5, 0.5))


def generate_base(settings: Settings, topic: dict, seed: int, font_path: str | None,
                  source: str | None = None) -> BaseImage:
    source = (source or settings.image_source).lower()
    if source == "procedural":
        scene = build_scene(topic["scene"], seed, topic.get("variant"), font_path)
        return BaseImage("procedural", scene=scene, meta={"template": topic["scene"], "generator": "built-in"})
    if source == "sample":
        return _from_samples(settings.path("samples"), topic, seed)
    if source == "comfyui":
        client = ComfyUIClient(settings)
        img = client.generate(topic, seed)
        return BaseImage("comfyui", image=fit_canvas(img), meta=client.last_meta)
    raise ImageSourceError(f"알 수 없는 IMAGE_SOURCE: {source} (procedural | sample | comfyui)")


def _from_samples(folder: Path, topic: dict, seed: int) -> BaseImage:
    files = sorted(p for p in folder.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
    if not files:
        raise ImageSourceError(f"샘플 이미지가 없습니다: {folder} (README.md 참고)")
    matching = [p for p in files if p.stem.startswith(topic["id"])] or files
    path = random.Random(seed).choice(matching)
    return BaseImage("sample", image=fit_canvas(Image.open(path)), meta={"file": path.name})


class ComfyUIClient:
    """ComfyUI HTTP API 클라이언트 (/prompt, /history, /view).

    워크플로 파일은 ComfyUI에서 'Save (API Format)'으로 저장한 JSON이어야 한다.
    문자열 값 중 %PROMPT% %NEGATIVE% %SEED% %CKPT% %WIDTH% %HEIGHT% 를 바꿔 넣는다.
    """

    def __init__(self, settings: Settings):
        self.s = settings
        self.base = settings.comfyui_url
        self.last_meta: dict = {}

    def ping(self) -> bool:
        import requests
        try:
            return requests.get(f"{self.base}/system_stats", timeout=5).ok
        except requests.RequestException:
            return False

    def _workflow(self, prompt: str, seed: int) -> dict:
        path = self.s.resolve(self.s.comfyui_workflow)
        if not path.exists():
            raise ImageSourceError(f"ComfyUI 워크플로 파일이 없습니다: {path}")
        wf = json.loads(path.read_text(encoding="utf-8"))
        wf.pop("_comment", None)
        values = {"%PROMPT%": prompt, "%NEGATIVE%": NEGATIVE_PROMPT, "%SEED%": seed,
                  "%CKPT%": self.s.comfyui_checkpoint, "%WIDTH%": 1344, "%HEIGHT%": 944}

        def walk(node):
            if isinstance(node, dict):
                return {k: walk(v) for k, v in node.items()}
            if isinstance(node, list):
                return [walk(v) for v in node]
            if isinstance(node, str) and node in values:
                return values[node]
            if isinstance(node, str):
                for k, v in values.items():
                    if isinstance(v, str):
                        node = node.replace(k, v)
            return node

        return walk(copy.deepcopy(wf))

    def generate(self, topic: dict, seed: int) -> Image.Image:
        import requests
        if not self.ping():
            raise ImageSourceError(f"ComfyUI 서버에 연결할 수 없습니다: {self.base} (ComfyUI를 먼저 실행하세요)")
        prompt = f"{topic.get('prompt', topic['title'])}, {STYLE_PROMPT}"
        wf = self._workflow(prompt, seed % (2**31))
        client_id = uuid.uuid4().hex
        r = requests.post(f"{self.base}/prompt", json={"prompt": wf, "client_id": client_id}, timeout=30)
        if not r.ok:
            raise ImageSourceError(f"ComfyUI /prompt 오류 {r.status_code}: {r.text[:300]}")
        prompt_id = r.json()["prompt_id"]
        deadline = time.time() + self.s.comfyui_timeout
        while time.time() < deadline:
            h = requests.get(f"{self.base}/history/{prompt_id}", timeout=15)
            if h.ok and prompt_id in h.json():
                entry = h.json()[prompt_id]
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise ImageSourceError(f"ComfyUI 실행 오류: {json.dumps(status)[:300]}")
                for out in entry.get("outputs", {}).values():
                    for im in out.get("images", []):
                        v = requests.get(f"{self.base}/view", params={"filename": im["filename"],
                                         "subfolder": im.get("subfolder", ""), "type": im.get("type", "output")},
                                         timeout=60)
                        v.raise_for_status()
                        from io import BytesIO
                        self.last_meta = {"generator": "comfyui", "prompt": prompt, "seed": seed,
                                          "checkpoint": self.s.comfyui_checkpoint, "file": im["filename"]}
                        return Image.open(BytesIO(v.content)).convert("RGB")
            time.sleep(2)
        raise ImageSourceError(f"ComfyUI 생성이 {self.s.comfyui_timeout}초 안에 끝나지 않았습니다")
