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
    """ComfyUI HTTP API 클라이언트 (/system_stats, /upload/image, /prompt, /history, /view).

    워크플로 파일은 ComfyUI에서 'Save (API Format)'으로 저장한 JSON이어야 한다.
    문자열 값 %PROMPT% %NEGATIVE% %SEED% %CKPT% %WIDTH% %HEIGHT% %IMAGE% 를 실행 시 바꿔 넣는다.
    """

    poll_interval = 1.5

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

    def system_info(self) -> dict:
        """GPU 이름·VRAM 등 (doctor 표시용). 실패하면 빈 dict."""
        import requests
        try:
            return requests.get(f"{self.base}/system_stats", timeout=5).json()
        except Exception:  # noqa: BLE001
            return {}

    def _load_workflow(self, rel_path: str, values: dict) -> dict:
        path = self.s.resolve(rel_path)
        if not path.exists():
            raise ImageSourceError(f"ComfyUI 워크플로 파일이 없습니다: {path}")
        wf = json.loads(path.read_text(encoding="utf-8"))
        wf.pop("_comment", None)

        def walk(node):
            if isinstance(node, dict):
                return {k: walk(v) for k, v in node.items()}
            if isinstance(node, list):
                return [walk(v) for v in node]
            if isinstance(node, str) and node in values:
                return values[node]  # 숫자 자리(%SEED% 등)는 숫자로 바꾼다
            if isinstance(node, str):
                for k, v in values.items():
                    if isinstance(v, str):
                        node = node.replace(k, v)
            return node

        return walk(copy.deepcopy(wf))

    _started = False

    def _ensure_up(self) -> None:
        if not self.ping() and self.s.comfyui_start_cmd and not ComfyUIClient._started:
            self._start_server()
        if not self.ping():
            raise ImageSourceError(f"ComfyUI 서버에 연결할 수 없습니다: {self.base} "
                                   "(ComfyUI의 run_nvidia_gpu.bat을 먼저 실행하세요)")

    def _start_server(self, wait: int = 180) -> None:
        """COMFYUI_START_CMD로 ComfyUI를 켜고 응답할 때까지 기다린다 (한 번만 시도)."""
        import subprocess
        ComfyUIClient._started = True
        cmd = self.s.comfyui_start_cmd
        log.info("ComfyUI가 꺼져 있어 실행합니다: %s", cmd)
        kwargs: dict = {"cwd": str(Path(cmd.strip('"')).parent) if Path(cmd.strip('"')).exists() else None,
                        "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if hasattr(subprocess, "CREATE_NEW_CONSOLE"):
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE  # Windows: 별도 창
        subprocess.Popen(cmd, shell=True, **kwargs)  # noqa: S602 — 사용자가 .env에 직접 적은 명령
        deadline = time.time() + wait
        while time.time() < deadline:
            if self.ping():
                log.info("ComfyUI 응답 확인")
                return
            time.sleep(3)
        log.error("ComfyUI가 %d초 안에 응답하지 않았습니다", wait)

    def upload_image(self, img: Image.Image, name: str) -> str:
        import requests
        from io import BytesIO
        buf = BytesIO()
        img.save(buf, format="PNG")
        r = requests.post(f"{self.base}/upload/image", files={"image": (name, buf.getvalue(), "image/png")},
                          data={"overwrite": "true", "type": "input"}, timeout=60)
        if not r.ok:
            raise ImageSourceError(f"ComfyUI 이미지 업로드 오류 {r.status_code}: {r.text[:300]}")
        info = r.json()
        return f"{info['subfolder']}/{info['name']}" if info.get("subfolder") else info["name"]

    def _run(self, wf: dict) -> tuple[Image.Image, str]:
        import requests
        from io import BytesIO
        r = requests.post(f"{self.base}/prompt", json={"prompt": wf, "client_id": uuid.uuid4().hex}, timeout=30)
        if not r.ok:
            # 노드 이름·모델 파일명 오류는 여기서 400으로 돌아온다
            raise ImageSourceError(f"ComfyUI /prompt 오류 {r.status_code}: {r.text[:500]}")
        prompt_id = r.json()["prompt_id"]
        deadline = time.time() + self.s.comfyui_timeout
        while time.time() < deadline:
            h = requests.get(f"{self.base}/history/{prompt_id}", timeout=15)
            if h.ok and prompt_id in h.json():
                entry = h.json()[prompt_id]
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise ImageSourceError(f"ComfyUI 실행 오류: {json.dumps(status, ensure_ascii=False)[:500]}")
                for out in entry.get("outputs", {}).values():
                    for im in out.get("images", []):
                        v = requests.get(f"{self.base}/view", params={"filename": im["filename"],
                                         "subfolder": im.get("subfolder", ""), "type": im.get("type", "output")},
                                         timeout=60)
                        v.raise_for_status()
                        return Image.open(BytesIO(v.content)).convert("RGB"), im["filename"]
                if status.get("completed"):
                    raise ImageSourceError("ComfyUI가 끝났지만 출력 이미지가 없습니다 (SaveImage 노드 확인)")
            time.sleep(self.poll_interval)
        raise ImageSourceError(f"ComfyUI 생성이 {self.s.comfyui_timeout}초 안에 끝나지 않았습니다")

    def generate(self, topic: dict, seed: int) -> Image.Image:
        self._ensure_up()
        prompt = f"{topic.get('prompt', topic['title'])}, {STYLE_PROMPT}"
        wf = self._load_workflow(self.s.comfyui_workflow, {
            "%PROMPT%": prompt, "%NEGATIVE%": NEGATIVE_PROMPT, "%SEED%": seed % (2**31),
            "%CKPT%": self.s.comfyui_checkpoint, "%WIDTH%": self.s.comfyui_width, "%HEIGHT%": self.s.comfyui_height})
        t0 = time.time()
        img, fname = self._run(wf)
        self.last_meta = {"generator": "comfyui", "prompt": prompt, "seed": seed,
                          "checkpoint": self.s.comfyui_checkpoint, "file": fname,
                          "size": [self.s.comfyui_width, self.s.comfyui_height], "seconds": round(time.time() - t0, 1)}
        log.info("ComfyUI 원본 생성 %.1f초 (%s)", time.time() - t0, fname)
        return img

    def inpaint(self, image: Image.Image, mask: Image.Image, prompt: str, seed: int) -> Image.Image:
        """mask(L, 255=다시 그릴 곳) 영역을 prompt대로 다시 그린 전체 그림을 돌려준다."""
        self._ensure_up()
        rgba = image.convert("RGBA")
        # ComfyUI LoadImage는 투명한 곳을 MASK=1(다시 그릴 곳)로 읽는다
        rgba.putalpha(Image.eval(mask.convert("L"), lambda v: 255 - v))
        name = self.upload_image(rgba, f"nostalgia_inpaint_{uuid.uuid4().hex[:8]}.png")
        ckpt = self.s.comfyui_inpaint_checkpoint or self.s.comfyui_checkpoint
        wf = self._load_workflow(self.s.comfyui_inpaint_workflow, {
            "%PROMPT%": f"{prompt}, {STYLE_PROMPT}", "%NEGATIVE%": NEGATIVE_PROMPT, "%SEED%": seed % (2**31),
            "%CKPT%": ckpt, "%IMAGE%": name})
        out, _ = self._run(wf)
        if out.size != image.size:
            out = out.resize(image.size, Image.LANCZOS)
        return out
