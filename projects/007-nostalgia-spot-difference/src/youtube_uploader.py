"""YouTube Data API v3 업로드 (OAuth, 기본 비공개).

필요 패키지: requirements-youtube.txt (google-api-python-client, google-auth-oauthlib)
credentials.json / token.json 은 절대 Git에 올리지 않는다 (.gitignore에 포함).
"""
from __future__ import annotations

import hashlib
import logging
import random
import time
from pathlib import Path

from .config import Settings
from .db import JobDB

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
RETRIABLE_STATUS = {500, 502, 503, 504}


class UploadError(RuntimeError):
    pass


class UploadSkipped(RuntimeError):
    pass


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_privacy(settings: Settings) -> str:
    """공개(public)·일부공개(unlisted)는 ALLOW_PUBLIC_UPLOAD=true 일 때만 허용. 그 외에는 항상 private."""
    wanted = settings.upload_privacy
    if wanted not in {"private", "unlisted", "public"}:
        log.warning("UPLOAD_PRIVACY=%s 는 알 수 없는 값이라 private로 올립니다", wanted)
        return "private"
    if wanted != "private" and not settings.allow_public_upload:
        log.warning("UPLOAD_PRIVACY=%s 이지만 ALLOW_PUBLIC_UPLOAD가 꺼져 있어 private로 올립니다", wanted)
        return "private"
    return wanted


def declare_synthetic(settings: Settings, source: str) -> bool:
    v = settings.declare_synthetic_media
    if v in {"true", "1", "yes", "on"}:
        return True
    if v in {"false", "0", "no", "off"}:
        return False
    return source == "comfyui"


def _libs():
    try:
        from google.auth.transport.requests import Request  # noqa: F401
        from google.oauth2.credentials import Credentials  # noqa: F401
        from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401
        from googleapiclient.discovery import build  # noqa: F401
    except ImportError as e:
        raise UploadError("YouTube 업로드용 패키지가 없습니다: pip install -r requirements-youtube.txt") from e


def get_service(settings: Settings, interactive: bool = False):
    _libs()
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token_path = settings.resolve(settings.youtube_token)
    secrets_path = settings.resolve(settings.youtube_client_secrets)
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:  # noqa: BLE001
            log.warning("토큰 갱신 실패: %s", e)
            creds = None
    if not creds or not creds.valid:
        if not interactive:
            raise UploadError("YouTube 인증이 필요합니다. 먼저 `python main.py auth`를 실행하세요.")
        if not secrets_path.exists():
            raise UploadError(f"OAuth 클라이언트 파일이 없습니다: {secrets_path} (README의 'YouTube 연결' 참고)")
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
        creds = flow.run_local_server(port=0)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_video(settings: Settings, db: JobDB, job: dict, service=None, force_review: bool = False) -> str:
    """작업 하나를 업로드하고 video ID를 돌려준다. 중복이면 UploadSkipped."""
    video = Path(job["video_path"] or "")
    if not video.exists():
        raise UploadError(f"영상 파일이 없습니다: {video}")
    if job["status"] == "needs_review" and not force_review:
        raise UploadSkipped("검수 대상(needs_review) 작업입니다. 확인 후 `approve` 하거나 --force-review를 쓰세요.")
    if job["status"] not in {"ready", "needs_review"}:
        raise UploadSkipped(f"업로드할 수 없는 상태입니다: {job['status']}")
    digest = sha256_of(video)
    dup = db.find_upload(job["job_id"], digest)
    if dup:
        raise UploadSkipped(f"이미 업로드된 작업/영상입니다 (video ID {dup['youtube_id']})")

    privacy = resolve_privacy(settings)
    import json
    tags = json.loads(job["tags"]) if job.get("tags") else []
    body = {
        "snippet": {
            "title": job["title"],
            "description": job["description"],
            "tags": tags,
            "categoryId": settings.youtube_category_id,
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": settings.made_for_kids,
            "containsSyntheticMedia": declare_synthetic(settings, job.get("source") or ""),
        },
    }

    service = service or get_service(settings)
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    attempt = 0
    while response is None:
        try:
            _, response = request.next_chunk()
        except HttpError as e:
            status = getattr(e.resp, "status", None)
            if status in RETRIABLE_STATUS and attempt < settings.max_retries:
                attempt += 1
                wait = 2 ** attempt + random.random()
                log.warning("업로드 일시 오류 %s, %.1f초 후 재시도 (%d/%d)", status, wait, attempt, settings.max_retries)
                time.sleep(wait)
                continue
            raise UploadError(f"업로드 실패 (HTTP {status}): {e}") from e
        except (ConnectionError, TimeoutError, OSError) as e:
            if attempt < settings.max_retries:
                attempt += 1
                wait = 2 ** attempt + random.random()
                log.warning("네트워크 오류 %s, %.1f초 후 재시도 (%d/%d)", e, wait, attempt, settings.max_retries)
                time.sleep(wait)
                continue
            raise UploadError(f"업로드 실패 (네트워크): {e}") from e
    video_id = response.get("id")
    if not video_id:
        raise UploadError(f"업로드 응답에 video ID가 없습니다: {response}")
    st = response.get("status", {})
    db.record_upload(job["job_id"], digest, video_id, privacy, st.get("uploadStatus", "unknown"))
    log.info("업로드 완료: %s (privacy=%s, uploadStatus=%s)", video_id, privacy, st.get("uploadStatus"))
    return video_id


def refresh_status(settings: Settings, db: JobDB, service=None) -> list[dict]:
    """업로드한 영상의 처리 상태와 공개 통계를 갱신한다. (API 성공 ≠ 공개 게시 완료)"""
    uploads = db.list_uploads()
    if not uploads:
        return []
    service = service or get_service(settings)
    results = []
    ids = [u["youtube_id"] for u in uploads if u["youtube_id"]]
    for i in range(0, len(ids), 50):
        resp = service.videos().list(part="status,processingDetails,statistics", id=",".join(ids[i:i + 50])).execute()
        found = {it["id"]: it for it in resp.get("items", [])}
        for vid in ids[i:i + 50]:
            it = found.get(vid)
            if not it:
                db.update_upload_status(vid, "not_found", None)
                results.append({"youtube_id": vid, "upload_status": "not_found"})
                continue
            st = it.get("status", {})
            proc = it.get("processingDetails", {}).get("processingStatus")
            db.update_upload_status(vid, st.get("uploadStatus", "unknown"), proc)
            stats = it.get("statistics", {})
            to_int = lambda k: int(stats[k]) if k in stats else None  # noqa: E731
            db.add_stats(vid, to_int("viewCount"), to_int("likeCount"), to_int("commentCount"))
            results.append({"youtube_id": vid, "upload_status": st.get("uploadStatus"),
                            "privacy": st.get("privacyStatus"), "rejection": st.get("rejectionReason"),
                            "processing": proc, "views": to_int("viewCount")})
    return results
