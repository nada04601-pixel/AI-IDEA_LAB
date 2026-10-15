"""수집·필터 (M3). 네트워크·AI 모델 없이 가짜 다운로더·검색기·검사기로 판정 흐름을 확인한다.

가짜 검사기는 파일 이름이 아니라 영상 내용으로 판단한다:
  - OCR: 화면에 흰 띠가 있으면 한글 자막을 읽은 것으로 본다
  - 음성: 440Hz 소리면 한국어로 본다
  - CLIP: 화면 평균 색 (빨강=기준 상품, 빨강 계열=같은 상품, 노랑=분위기 비슷, 파랑=다른 상품)
"""

import json

import numpy as np
import pytest
from typer.testing import CliRunner

from ssm import collector
from ssm.analyzer import run_analyze
from ssm.collector import CollectError, run_collect, title_keyword
from ssm.downloader import (SEARCH, DownloadError, Fetched, collect_links, load_netscape_cookies, platform_of,
                            xhs_host)
from ssm.filters import Inspectors, grade_for, korean_meta_reason, korean_speech_reason, korean_text_reason
from ssm.main import app
from ssm.schemas import Candidates, Selected, Source
from ssm.workspace import Workspace, import_local_videos

from conftest import make_video, needs_ffmpeg

XHS = "https://www.xiaohongshu.com/explore/{:024x}"


# ---- 판정 규칙 -------------------------------------------------------------------


def test_korean_text_reason():
    assert korean_text_reason([["这个水壶"], ["好用"]]) is None
    assert "한글" in korean_text_reason([["这个"], ["진짜좋아요"]])  # 4자 연속
    assert "비율" in korean_text_reason([["가 나 다 abc"], ["라 마 바"]])  # 한글 6자, 2프레임, 6/9
    assert korean_text_reason([["ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 3 + "가나다"], ["라마바"]]) is None  # 6/84 = 7% < 10%
    # 실측 오탐: 중국어 자막 영상에서 한국어 OCR이 한자를 '제' 한 글자로 잘못 읽음 → 제외하면 안 된다
    assert korean_text_reason([["제"], [], ["IIp"], []]) is None
    assert korean_text_reason([["가 나 다 라 마 바"]]) is None  # 한 프레임에서만 보이면 비율 규칙 적용 안 함


def test_korean_speech_and_meta():
    assert korean_speech_reason(0.82) and korean_speech_reason(0.2) is None and korean_speech_reason(None) is None
    assert korean_meta_reason(title="折叠水壶 추천") == "제목에 한글 포함"
    assert "한국" in korean_meta_reason(location="韩国")
    assert korean_meta_reason(title="折叠水壶", author="小红", location="广东") is None


def test_grade_for():
    assert grade_for(0.9, 0.8, 0.6) == ("same_product", None)
    assert grade_for(0.7, 0.8, 0.6) == ("mood", None)
    assert grade_for(0.3, 0.8, 0.6)[0] == "excluded"
    assert grade_for(None, 0.8, 0.6) == ("mood", None)  # 모르면 상품 구간에 쓰지 않는 쪽으로


def test_helpers(tmp_path):
    assert platform_of("https://www.xiaohongshu.com/explore/abc") == "xiaohongshu"
    assert platform_of("http://xhslink.com/a/xyz") == "xiaohongshu"
    assert platform_of("https://v.douyin.com/abc/") == "douyin"
    assert platform_of("https://example.com/v.mp4") == "other"
    assert title_keyword("折叠电热水壶🔥出差必备 #好物分享[话题]# #旅行#") == "折叠电热水壶 出差必备"
    assert title_keyword("免打孔的罗马帘买一套这个上梁就搞定了👍 - rednote") == "免打孔的罗马帘买一套这个上梁就搞定了"
    assert collector._media_id(XHS.format(5) + "?xsec_token=a") == collector._media_id(XHS.format(5) + "?xsec_token=b")

    assert platform_of("https://www.rednote.com/explore/abc") == "xiaohongshu"  # 샤오홍슈 국제판

    found = {}
    base = "https://www.rednote.com/search_result/" + "a" * 24
    collect_links([base, base + "?xsec_token=T&xsec_source=", "https://www.rednote.com/user/profile/" + "b" * 24,
                   base + "?other=1"], SEARCH["xiaohongshu"][1], found)
    assert found == {"a" * 24: base + "?xsec_token=T&xsec_source="}  # 토큰 붙은 링크를 고른다

    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n.xiaohongshu.com\tTRUE\t/\tTRUE\t1893456000\tweb_session\tabc\n"
                       "#HttpOnly_.douyin.com\tTRUE\t/\tFALSE\t0\tsid\txyz\n", encoding="utf-8")
    parsed = load_netscape_cookies(cookies)
    assert parsed[0] == {"name": "web_session", "value": "abc", "domain": ".xiaohongshu.com", "path": "/",
                         "secure": True, "httpOnly": False, "expires": 1893456000}
    assert parsed[1]["httpOnly"] is True and "expires" not in parsed[1]
    assert xhs_host(cookies) == "www.xiaohongshu.com" and xhs_host(None) == "www.xiaohongshu.com"
    rednote = tmp_path / "rednote.txt"
    rednote.write_text(".rednote.com\tTRUE\t/\tTRUE\t0\tweb_session\tabc\n", encoding="utf-8")
    assert xhs_host(rednote) == "www.rednote.com"  # 국제판 쿠키뿐이면 국제판에서 검색


# ---- 가짜 도구 -------------------------------------------------------------------


class FakeOCR:
    def read(self, image):
        white = (image.min(axis=2) > 240).mean(axis=1)  # 줄마다 흰 픽셀 비율
        return ["한국어자막입니다"] if (white > 0.4).any() else ["产品展示"]


class FakeSpeech:
    def korean_probability(self, audio):
        freqs = np.fft.rfftfreq(len(audio), 1 / 16000)
        peak = freqs[np.argmax(np.abs(np.fft.rfft(audio)))]
        return 0.9 if abs(peak - 440) < 20 else 0.01


class FakeClip:
    def embed(self, frames):
        v = frames.reshape(-1, 3).mean(axis=0)
        return v / np.linalg.norm(v)


def fake_inspectors(ocr=True, speech=True, clip=True):
    return lambda: Inspectors(FakeOCR() if ocr else None, FakeSpeech() if speech else None,
                              FakeClip() if clip else None, "" if ocr else "모델 없음", "" if speech else "모델 없음",
                              "" if clip else "모델 없음")


class FakeDownloader:
    """url → (영상 파일, 메타데이터). 없는 url은 실패 (이미지 글처럼)."""

    name = "fake"

    def __init__(self, library: dict):
        self.library, self.calls = library, []

    def fetch(self, url, out_dir, stem):
        self.calls.append(url)
        key = url.split("?")[0]  # 검색 결과 링크에는 공유 토큰이 붙는다
        if key not in self.library:
            raise DownloadError("fake: 영상이 없는 글")
        video, meta = self.library[key]
        dest = out_dir / f"{stem}.mp4"
        dest.write_bytes(video.read_bytes())
        return Fetched(file=dest, **meta)


class FakeSearcher:
    def __init__(self, results):
        self.results, self.calls = results, []

    def search(self, platform, keyword, limit):
        self.calls.append((platform, keyword))
        return self.results[:limit]


@pytest.fixture
def library(tmp_path):
    v = lambda name, **kw: make_video(tmp_path / f"{name}.mp4", "160x288", 1.5, **kw)  # noqa: E731
    return {
        XHS.format(1): (v("ref", color="0xC81010"), {"title": "折叠电热水壶 #好物#", "author": "小红"}),
        XHS.format(2): (v("same", color="0xD01818"), {"title": "同款水壶"}),
        XHS.format(3): (v("mood", color="0xC8C810"), {"title": "旅行好物"}),
        XHS.format(4): (v("other", color="0x1010C8"), {"title": "别的东西"}),
        XHS.format(5): (v("ko_sub", color="0xC81010", box=True), {"title": "水壶"}),
        XHS.format(6): (v("ko_voice", color="0xC81010", tone=440), {"title": "水壶"}),
        XHS.format(8): (v("ko_meta", color="0xC81010"), {"title": "접이식 포트 추천"}),
    }


def url_project(home, url=XHS.format(1)) -> Workspace:
    return Workspace.create(Source(type="url", value=url), {"ad_disclosure": {"profile": "coupang"}})


# ---- 수집 흐름 -------------------------------------------------------------------


@needs_ffmpeg
def test_collect_filters_and_grades(home, library):
    ws = url_project(home)
    dl = FakeDownloader(library)
    search = FakeSearcher([XHS.format(i) + "?xsec_token=t" for i in (2, 3, 4, 5, 6, 7, 8)])
    sleeps, logs = [], []
    selected = run_collect(ws, downloaders=[dl], searcher=search, inspectors=fake_inspectors(),
                           log=logs.append, sleep=sleeps.append)

    assert search.calls == [("xiaohongshu", "折叠电热水壶")]  # 기준 영상 제목에서 검색어
    cands = {c.url.split("?")[0][-1]: c for c in Candidates.model_validate_json(
        (ws.path / "candidates.json").read_text(encoding="utf-8")).candidates}
    assert cands["1"].reference and cands["1"].grade == "same_product"
    assert cands["2"].grade == "same_product" and cands["2"].similarity > 0.99
    assert cands["3"].grade == "mood" and 0.6 <= cands["3"].similarity < 0.8
    assert cands["4"].grade == "excluded" and "유사도 낮음" in cands["4"].reasons[0]
    assert cands["7"].error and cands["7"].grade == "excluded"  # 이미지 글 → 내려받기 실패

    # 완료 기준: 국내 콘텐츠(한글 자막·한국어 음성·한글 메타데이터)는 100% 제외
    assert "한글 자막" in cands["5"].reasons[0]
    assert "한국어 음성" in cands["6"].reasons[0]
    assert "제목에 한글" in cands["8"].reasons[0]
    assert {c.grade for k, c in cands.items() if k in "568"} == {"excluded"}

    assert [(v.file, v.grade) for v in selected.videos] == [
        ("raw_videos/01.mp4", "same_product"), ("raw_videos/02.mp4", "same_product"), ("raw_videos/03.mp4", "mood")]
    assert all((ws.path / v.file).is_file() for v in selected.videos)
    assert ws.status("collect") == "done"
    assert any("같은 상품 영상이 2개뿐" in m for m in logs)
    assert len(sleeps) == len(dl.calls) and all(2 <= s <= 5 for s in sleeps)  # 검색 1번 + 내려받기 8번, 첫 요청만 대기 없음

    # 분석은 selected.json의 등급을 쓴다 → mood 영상은 hook·problem 구간에만
    analysis = run_analyze(ws, load=lambda cfg: (None, "테스트"), log=lambda m: None)
    assert [v.grade for v in analysis.videos] == ["same_product", "same_product", "mood"]

    # 기준값만 바꿔 다시 돌리면 받아 둔 영상은 다시 받지 않고(캐시) 다시 판정한다. 실패했던 링크만 다시 시도
    ws.set_override("collector.same_product_threshold", 0.6)
    assert ws.status("collect") == "stale"
    calls = len(dl.calls)
    selected = run_collect(ws, downloaders=[dl], searcher=search, inspectors=fake_inspectors(), log=lambda m: None,
                           sleep=lambda s: None)
    assert dl.calls[calls:] == [XHS.format(7) + "?xsec_token=t"]
    assert [v.grade for v in selected.videos] == ["same_product"] * 3
    assert sorted(p.name for p in (ws.path / "raw_videos").iterdir()) == ["01.mp4", "02.mp4", "03.mp4"]


@needs_ffmpeg
def test_collect_without_models_is_conservative(home, library):
    ws = url_project(home)
    logs = []
    run_collect(ws, downloaders=[FakeDownloader(library)], searcher=FakeSearcher([XHS.format(2), XHS.format(5)]),
                inspectors=fake_inspectors(ocr=False, speech=False, clip=False), log=logs.append, sleep=lambda s: None)
    cands = Candidates.model_validate_json((ws.path / "candidates.json").read_text(encoding="utf-8")).candidates
    assert cands[1].grade == "mood" and cands[1].similarity is None  # 유사도를 모르면 상품 구간에 쓰지 않는다
    assert "한글 자막 검사 못함" in cands[2].notes  # 검사 못한 것은 꾸며내지 않고 기록
    assert any("한글 OCR를 쓸 수 없습니다" in m for m in logs)


@needs_ffmpeg
def test_collect_keyword_project_and_extra_urls(home, library):
    ws = Workspace.create(Source(type="keyword", value="折叠电热水壶"))
    ws.set_override("collector.urls", [XHS.format(2)])
    search = FakeSearcher([XHS.format(5), XHS.format(1), XHS.format(4)])
    run_collect(ws, downloaders=[FakeDownloader(library)], searcher=search, inspectors=fake_inspectors(),
                log=lambda m: None, sleep=lambda s: None)
    assert [c[0] for c in search.calls] == ["xiaohongshu", "douyin"]
    cands = Candidates.model_validate_json((ws.path / "candidates.json").read_text(encoding="utf-8")).candidates
    ref = next(c for c in cands if c.reference)
    assert ref.url == XHS.format(2)  # 직접 준 링크가 먼저, 국내 콘텐츠가 아닌 첫 영상이 기준
    assert any("기준 영상으로 삼음" in n for n in ref.notes)


@needs_ffmpeg
def test_collect_errors(home, library):
    ws = url_project(home, XHS.format(9))
    with pytest.raises(CollectError, match="기준 영상을 내려받지 못했습니다"):
        run_collect(ws, downloaders=[FakeDownloader(library)], searcher=FakeSearcher([]),
                    inspectors=fake_inspectors(), log=lambda m: None, sleep=lambda s: None)
    ws = url_project(home, XHS.format(5))  # 기준 영상부터 국내 콘텐츠, 다른 후보도 없음
    with pytest.raises(CollectError, match="같은 상품 영상을 하나도"):
        run_collect(ws, downloaders=[FakeDownloader(library)], searcher=FakeSearcher([]),
                    inspectors=fake_inspectors(), log=lambda m: None, sleep=lambda s: None)
    assert (ws.path / "candidates.json").is_file()  # 왜 실패했는지 볼 수 있게 후보 기록은 남긴다


@needs_ffmpeg
def test_collect_local_project_only_warns(home, tmp_path):
    files = [make_video(tmp_path / "a.mp4", color="red"), make_video(tmp_path / "b.mp4", color="red", box=True)]
    ws = Workspace.create(Source(type="local", files=[str(f) for f in files]))
    import_local_videos(ws, files)
    logs = []
    selected = run_collect(ws, downloaders=[], searcher=FakeSearcher([]), inspectors=fake_inspectors(),
                           log=logs.append, sleep=lambda s: None)
    assert [v.file for v in selected.videos] == ["raw_videos/01.mp4", "raw_videos/02.mp4"]  # 그대로, 제외하지 않음
    assert any("02.mp4: 국내 콘텐츠로 보입니다" in m for m in logs)

    # 사용자가 selected.json에서 등급을 바꾸면 다시 수집해도 유지되고, 분석에도 반영된다
    data = json.loads((ws.path / "selected.json").read_text(encoding="utf-8"))
    data["videos"][1]["grade"] = "mood"
    (ws.path / "selected.json").write_text(json.dumps(data), encoding="utf-8")
    selected = run_collect(ws, downloaders=[], searcher=FakeSearcher([]), inspectors=fake_inspectors(),
                           log=lambda m: None, sleep=lambda s: None)
    assert selected.videos[1].grade == "mood"
    assert run_analyze(ws, load=lambda cfg: (None, ""), log=lambda m: None).videos[1].grade == "mood"


@needs_ffmpeg
def test_cli_collect_saves_options(home, library, monkeypatch):
    dl, search = FakeDownloader(library), FakeSearcher([XHS.format(2)])
    monkeypatch.setattr(collector, "YtDlpDownloader", lambda *a: dl)
    monkeypatch.setattr(collector, "PlaywrightDownloader", lambda *a: FakeDownloader({}))
    monkeypatch.setattr(collector, "PlaywrightSearcher", lambda *a: search)
    monkeypatch.setattr(collector, "load_inspectors", lambda cfg, log: fake_inspectors()())
    monkeypatch.setattr(collector.random, "Random", lambda: type("R", (), {"uniform": lambda self, a, b: 0})())
    monkeypatch.setattr(collector.time, "sleep", lambda s: None)
    ws = url_project(home)
    r = CliRunner().invoke(app, ["collect", "--keyword", "水壶", "--url", XHS.format(3), "--max", "4"])
    assert r.exit_code == 0, r.output
    cfg = ws.config().collector
    assert (cfg.keyword, cfg.urls, cfg.max_videos) == ("水壶", [XHS.format(3)], 4)
    assert search.calls == [("xiaohongshu", "水壶")]
    assert "채택 3개" in r.output
    assert len(Selected.model_validate_json((ws.path / "selected.json").read_text(encoding="utf-8")).videos) == 3
