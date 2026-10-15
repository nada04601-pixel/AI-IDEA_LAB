"""후보 영상 검사 (기획서 Module 1) — 국내 콘텐츠 필터와 같은 상품 유사도.

국내 콘텐츠(하나라도 해당하면 제외):
  1. 한글 텍스트: 균등 8프레임 OCR → 한글 음절 비율 10% 이상 또는 한글 4자 이상 연속
  2. 한국어 음성: 앞 30초 faster-whisper 언어 감지 → ko 확률 0.5 이상
  3. 작성자 메타데이터: 제목·설명·작성자 이름에 한글, 또는 IP 표시 지역이 한국
  ('얼굴로 국적 판별'은 신뢰할 수 없고 차별 소지가 있어 쓰지 않는다 — 기획서 결정)
같은 상품 유사도: 기준 영상과 후보 영상 프레임의 CLIP 임베딩 코사인 유사도.

모델은 모두 바꿔 끼울 수 있는 인터페이스 뒤에 두고, 쓸 수 없으면 '검사 못함'으로 기록한다 (꾸며내지 않는다).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from ssm.config import AppConfig

OCR_FRAMES = 8
OCR_WIDTH = 480  # CPU에서 720px의 절반 시간, 자막 크기 한글은 그대로 읽힌다 (360px부터는 놓침 — 실측)
HANGUL_RATIO = 0.10
HANGUL_RUN = re.compile(r"[가-힣]{4,}")
OCR_MIN_CONFIDENCE = 0.4  # 이보다 확신이 낮은 글자는 버린다 (중국어를 한글로 잘못 읽는 경우 줄이기)
KO_SPEECH_PROB = 0.5
SPEECH_SECONDS = 30
CLIP_FRAMES = 6
KOREA_PLACES = ("韩国", "韓國", "korea", "대한민국", "한국")


# ---- 판정 규칙 (모델과 무관한 순수 함수) ------------------------------------------------


def is_hangul(ch: str) -> bool:
    return "가" <= ch <= "힣"


def korean_text_reason(frame_texts: list[list[str]]) -> str | None:
    """프레임별 OCR 결과 → 제외 사유 (없으면 None)."""
    chars = [ch for texts in frame_texts for t in texts for ch in t if ch.isalnum()]
    hangul = sum(is_hangul(ch) for ch in chars)
    run = next((m.group() for texts in frame_texts for t in texts if (m := HANGUL_RUN.search(t))), None)
    if run:
        return f"한글 자막/텍스트 검출 ('{run}')"
    if chars and hangul / len(chars) >= HANGUL_RATIO:
        return f"한글 텍스트 비율 {hangul / len(chars):.0%}"
    return None


def korean_speech_reason(ko_prob: float | None) -> str | None:
    if ko_prob is not None and ko_prob >= KO_SPEECH_PROB:
        return f"한국어 음성 (확률 {ko_prob:.2f})"
    return None


def korean_meta_reason(title: str = "", description: str = "", author: str = "", location: str = "") -> str | None:
    for label, text in (("제목", title), ("설명", description), ("작성자", author)):
        if any(is_hangul(ch) for ch in text or ""):
            return f"{label}에 한글 포함"
    if any(p in (location or "").lower() for p in KOREA_PLACES):
        return f"작성자 지역이 한국 ({location})"
    return None


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def grade_for(similarity: float | None, same: float, mood: float) -> tuple[str, str | None]:
    """(등급, 제외 사유). 유사도를 모르면 안전하게 mood (상품이 보이는 구간에는 쓰지 않음)."""
    if similarity is None:
        return "mood", None
    if similarity >= same:
        return "same_product", None
    if similarity >= mood:
        return "mood", None
    return "excluded", f"기준 영상과 유사도 낮음 ({similarity:.2f})"


# ---- 모델 인터페이스 --------------------------------------------------------------


class TextReader(Protocol):
    def read(self, image: np.ndarray) -> list[str]:
        """RGB 이미지에서 읽은 글자들."""


class LanguageDetector(Protocol):
    def korean_probability(self, audio16k: np.ndarray) -> float:
        """16kHz 모노 오디오가 한국어일 확률."""


class Embedder(Protocol):
    def embed(self, frames: np.ndarray) -> np.ndarray:
        """RGB 프레임들 → 하나의 정규화된 임베딩 벡터."""


class EasyOCRReader:
    def __init__(self, gpu: bool):
        import easyocr

        self.reader = easyocr.Reader(["ko", "en"], gpu=gpu, verbose=False)

    def read(self, image: np.ndarray) -> list[str]:
        return [text for _, text, conf in self.reader.readtext(image) if conf >= OCR_MIN_CONFIDENCE]


class WhisperLanguage:
    def __init__(self, cuda: bool):
        from faster_whisper import WhisperModel

        self.model = WhisperModel("tiny", device="cuda" if cuda else "cpu", compute_type="int8")

    def korean_probability(self, audio16k: np.ndarray) -> float:
        _, info = self.model.transcribe(audio16k, beam_size=1)  # 언어 감지만 하고 전사는 하지 않는다
        return float(dict(info.all_language_probs or []).get("ko", 0.0))


class ClipEmbedder:
    def __init__(self, device: str):
        import open_clip
        import torch

        self.torch = torch
        self.device = device
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k", device=device)
        self.model.eval()

    def embed(self, frames: np.ndarray) -> np.ndarray:
        from PIL import Image

        batch = self.torch.stack([self.preprocess(Image.fromarray(f)) for f in frames]).to(self.device)
        with self.torch.no_grad():
            feats = self.model.encode_image(batch).float()
        feats = feats / feats.norm(dim=-1, keepdim=True)
        mean = feats.mean(dim=0)
        return (mean / mean.norm()).cpu().numpy()


@dataclass
class Inspectors:
    """쓸 수 있는 검사기들. 없으면 None과 그 이유."""
    ocr: TextReader | None = None
    speech: LanguageDetector | None = None
    clip: Embedder | None = None
    ocr_reason: str = ""
    speech_reason: str = ""
    clip_reason: str = ""


def _try(factory: Callable[[], object]) -> tuple[object | None, str]:
    try:
        return factory(), ""
    except Exception as e:  # noqa: BLE001 — 모델 다운로드 실패·DLL 오류 등
        return None, f"{type(e).__name__}: {str(e)[:150]}"


def load_inspectors(cfg: AppConfig, log: Callable[[str], None] = print) -> Inspectors:
    from ssm.doctor import native_runtime_problem

    if problem := native_runtime_problem():
        return Inspectors(ocr_reason=problem, speech_reason=problem, clip_reason=problem)
    log("  검사 모델 준비 중… (처음에는 OCR·음성 인식·CLIP 모델을 내려받아 몇 분 걸립니다)")
    try:
        import torch

        cuda = cfg.device == "cuda" or (cfg.device == "auto" and torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        cuda = False
    ocr, ocr_reason = _try(lambda: EasyOCRReader(gpu=cuda))
    speech, speech_reason = _try(lambda: WhisperLanguage(cuda=cuda))
    clip, clip_reason = _try(lambda: ClipEmbedder("cuda" if cuda else "cpu"))
    return Inspectors(ocr, speech, clip, ocr_reason, speech_reason, clip_reason)
