"""요구사항 문서 5장 사용자 흐름과 12장 완료 기준을 API로 처음부터 끝까지 따라간다."""

import json
import subprocess

import pytest
from fastapi.testclient import TestClient

from app import config

pytestmark = pytest.mark.skipif(config.ffmpeg_path() is None, reason="FFmpeg 없음")


def wait_ok(client, job):
    job = client.get(f"/api/jobs/{job['id']}").json()
    assert job["status"] == "succeeded", job["error_message"]
    return job


def test_topic_to_mp4(tmp_path, monkeypatch):
    monkeypatch.setenv("AISS_DATABASE_URL", f"sqlite:///{tmp_path / 'flow.db'}")
    monkeypatch.setenv("AISS_STORAGE_DIR", str(tmp_path / "storage"))
    from app.main import app

    with TestClient(app) as c:
        # 1~2. 프로젝트 생성: 주제, 길이, 비율(기본 9:16), 스타일
        pid = c.post("/api/projects", json={"title": "고양이 상자", "topic": "고양이가 상자를 좋아하는 이유",
                                            "target_duration_sec": 12, "visual_style": "수채화"}).json()["id"]
        # 3. 대본 초안 생성 후 편집
        script = c.post(f"/api/projects/{pid}/generate-script").json()["script"]
        assert script.startswith("[mock]")
        c.patch(f"/api/projects/{pid}", json={"script": "고양이는 상자를 좋아해요.\n\n좁은 곳이 안전하게 느껴지거든요.\n\n오늘 상자 하나 놓아 주세요!"})
        # 4. 장면별 스토리보드로 분리
        scenes = c.post(f"/api/projects/{pid}/storyboard").json()
        assert len(scenes) == 3 and sum(s["duration_sec"] for s in scenes) == 12
        # 5. 장면 검토·수정, 순서 변경
        c.patch(f"/api/scenes/{scenes[2]['id']}", json={"image_prompt": "cat sitting in a box [mock-fail-once]"})
        c.post(f"/api/projects/{pid}/scenes/reorder", json={"scene_ids": [s["id"] for s in scenes]})
    # 데이터는 서버를 다시 켜도 유지된다 (완료 기준 2)
    with TestClient(app) as c:
        scenes = c.get(f"/api/projects/{pid}/scenes").json()
        assert [s["scene_number"] for s in scenes] == [1, 2, 3]
        # 6. 장면별 이미지·영상 생성 (실패하면 재시도)
        for s in scenes:
            job = c.post(f"/api/scenes/{s['id']}/generate-image").json()
            job = c.get(f"/api/jobs/{job['id']}").json()
            if job["status"] == "failed":
                wait_ok(c, c.post(f"/api/jobs/{job['id']}/retry").json())
        wait_ok(c, c.post(f"/api/scenes/{scenes[0]['id']}/generate-video").json())
        # 7~8. 승인·반려 후 수정·재생성
        c.post(f"/api/scenes/{scenes[1]['id']}/reject", json={"reason": "더 밝게"})
        c.patch(f"/api/scenes/{scenes[1]['id']}", json={"image_prompt": "bright cat"})
        wait_ok(c, c.post(f"/api/scenes/{scenes[1]['id']}/generate-image").json())
        for s in scenes:
            assert c.post(f"/api/scenes/{s['id']}/approve").status_code == 200
        # 9. 음성·자막
        for job in c.post(f"/api/projects/{pid}/generate-audio").json():
            wait_ok(c, job)
        assert len(c.get(f"/api/projects/{pid}/subtitles").json()["cues"]) == 3
        check = c.get(f"/api/projects/{pid}/render-check").json()
        assert check["ready"], check["problems"]
        # 10. FFmpeg로 세로형 MP4 렌더링
        wait_ok(c, c.post(f"/api/projects/{pid}/render").json())
        # 11. 미리보기·내보내기
        render = next(a for a in c.get(f"/api/projects/{pid}/assets").json() if a["asset_type"] == "render")
        res = c.get(render["url"] + "?download=true")
        assert res.status_code == 200 and "attachment" in res.headers["content-disposition"]
        out = tmp_path / "final.mp4"
        out.write_bytes(res.content)

        summary = next(p for p in c.get("/api/projects").json() if p["id"] == pid)
        assert summary["status"] == "done" and summary["approved_count"] == 3 and summary["latest_render_version"] == 1

    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", str(out)],
        capture_output=True, text=True, check=True).stdout)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1080, 1920)
    assert abs(float(probe["format"]["duration"]) - 12) < 0.15
    assert {s["codec_type"] for s in probe["streams"]} == {"video", "audio", "subtitle"}
