import random
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config import load_settings
from src.db import JobDB
from src.metadata_generator import build_metadata
from src.topic_picker import load_topics, pick_topic
from src.video_renderer import Timeline, answer_sentence, josa
from src.youtube_uploader import UploadSkipped, declare_synthetic, resolve_privacy, upload_video

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")


def test_env_file_parsing(tmp_path, monkeypatch):
    monkeypatch.delenv("UPLOAD_ENABLED", raising=False)
    (tmp_path / ".env").write_text("UPLOAD_ENABLED=true\nUPLOAD_PRIVACY='public'\n# comment\n", encoding="utf-8")
    s = load_settings(env_file=tmp_path / ".env", root=tmp_path)
    assert s.upload_enabled is True
    assert s.upload_privacy == "public"
    assert s.allow_public_upload is False


def test_privacy_defaults_to_private(settings):
    assert resolve_privacy(settings) == "private"
    settings.upload_privacy = "public"
    assert resolve_privacy(settings) == "private", "공개 허용 없이는 public 불가"
    settings.upload_privacy = "unlisted"
    assert resolve_privacy(settings) == "private"
    settings.allow_public_upload = True
    settings.upload_privacy = "public"
    assert resolve_privacy(settings) == "public"
    settings.upload_privacy = "weird"
    assert resolve_privacy(settings) == "private"


def test_synthetic_declaration(settings):
    assert declare_synthetic(settings, "comfyui") is True
    assert declare_synthetic(settings, "procedural") is False
    settings.declare_synthetic_media = "true"
    assert declare_synthetic(settings, "procedural") is True


def test_topic_picker_avoids_recent(settings):
    topics = load_topics(settings.path("topics"))
    rng = random.Random(0)
    recent = [topics[0]["id"], topics[1]["id"]]
    for _ in range(30):
        t = pick_topic(topics, recent, {}, rng)
        assert t["id"] not in recent
        assert t["series"] != topics[0]["series"]


def test_topic_picker_prefers_unused(settings):
    topics = load_topics(settings.path("topics"))
    counts = {t["id"]: 3 for t in topics}
    counts[topics[-1]["id"]] = 0
    assert pick_topic(topics, [], counts, random.Random(1))["id"] == topics[-1]["id"]


def test_josa():
    assert josa("빗자루", ("이", "가")) == "가"
    assert josa("냄비", ("이", "가")) == "가"
    assert josa("감", ("이", "가")) == "이"
    assert answer_sentence({"type": "object_removed", "label": "감"}) == "감이 사라졌어요"
    assert answer_sentence({"type": "object_added", "label": "닭"}) == "닭이 새로 생겼어요"


def test_metadata_avoids_recent_titles(settings):
    topics = load_topics(settings.path("topics"))
    puzzle = {"difference_count": 5, "difficulty": "normal",
              "differences": [{"type": "color_changed"}, {"type": "object_removed"}]}
    seen = []
    for i in range(7):
        m = build_metadata(topics[0], puzzle, seen, random.Random(i))
        assert m["title"] not in seen
        assert len(m["title"]) <= 100
        assert "#Shorts" in m["description"]
        seen.append(m["title"])


def test_db_duplicate_detection(tmp_path):
    db = JobDB(tmp_path / "j.sqlite")
    db.create_job("a", topic_id="t", topic="t")
    db.record_upload("a", "hash1", "vid1", "private", "uploaded")
    assert db.find_upload("a")["youtube_id"] == "vid1"
    assert db.find_upload("other", "hash1")["youtube_id"] == "vid1"
    assert db.find_upload("other", "hash2") is None
    assert db.export_csv(tmp_path / "r.csv") == 1


def test_upload_refuses_duplicates_and_review(settings, tmp_path):
    db = JobDB(settings.path("db"))
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x" * 1000)
    db.create_job("j1", topic_id="t", topic="t")
    db.update_job("j1", status="needs_review", video_path=str(video), title="t", description="d", tags=[])
    with pytest.raises(UploadSkipped):
        upload_video(settings, db, db.get_job("j1"), service=object())
    db.update_job("j1", status="ready")
    from src.youtube_uploader import sha256_of
    db.record_upload("old", sha256_of(video), "vid0", "private", "uploaded")
    with pytest.raises(UploadSkipped):
        upload_video(settings, db, db.get_job("j1"), service=object())


def test_upload_disabled_by_default(settings):
    from src.pipeline import try_upload
    db = JobDB(settings.path("db"))
    assert settings.upload_enabled is False
    assert try_upload(settings, db, "anything") is None


@needs_ffmpeg
def test_full_pipeline_short(settings):
    """짧은 타임라인으로 전체 흐름(이미지→정답→검사→렌더→영상 검사→메타데이터)을 실제로 실행."""
    from src.pipeline import make_one
    db = JobDB(settings.path("db"))
    tl = Timeline(opening=1, problem=3, reveal=2.5, outro=1)
    r = make_one(settings, db, topic_id="corner_store", seed=123, timeline=tl)
    assert r.status in {"ready", "needs_review"}, r.errors
    assert r.video_path.exists() and r.preview_path.exists() and r.puzzle_path.exists()
    from src.validator import ffprobe
    info = ffprobe(r.video_path)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert any(s["codec_type"] == "audio" for s in info["streams"])
    job = db.get_job(r.job_id)
    assert job["title"] and job["video_sha256"]
    assert not (settings.root / "output" / "work" / r.job_id).exists(), "작업 프레임은 정리돼야 함"
