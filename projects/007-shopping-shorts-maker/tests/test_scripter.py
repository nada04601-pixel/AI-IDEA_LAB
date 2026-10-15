import json

import pytest
from typer.testing import CliRunner

from ssm import scripter
from ssm.analyzer import run_analyze
from ssm.config import load_config
from ssm.main import app
from ssm.schemas import Candidate, Candidates, Script, Source
from ssm.scripter import (ScriptError, analyze_style, available_sfx, check_script, find_banned, find_preset,
                          load_banned, load_presets, prepare_request, reference_style, run_script_check)
from ssm.tts_engine import estimate_seconds, speech_rate, syllable_budget
from ssm.workspace import Workspace, import_local_videos

from conftest import make_video, needs_ffmpeg


def example_script(preset, index=0, duration=30, **changes) -> Script:
    ex = preset.examples[index]
    data = {"version": 1, "preset": preset.id, "target_duration_sec": duration,
            "product": {"name": ex["product"], "features": ["a", "b", "c"]},
            "sentences": [{"id": f"s{i}", **s} for i, s in enumerate(ex["sentences"], start=1)],
            "thumbnail_text": {"top": "여행 필수템", "bottom": "접으면 5cm"}}
    data.update(changes)
    return Script.model_validate(data)


@pytest.fixture
def cfg(home):
    return load_config()


def test_presets_load_and_find(cfg):
    presets = load_presets(cfg)
    assert [p.number for p in presets] == [1, 2, 3, 4]
    assert [p.id for p in presets] == ["curiosity", "honest_review", "value_deal", "info_curation"]
    assert find_preset(presets, 2).id == "honest_review" and find_preset(presets, "value_deal").number == 3
    assert find_preset(presets, "9") is None and find_preset(presets, None) is None
    for p in presets:
        assert len(p.examples) == 2 and p.hook_patterns and p.cta_examples
        assert set(p.structure) == {"hook", "problem", "demo", "benefit", "cta"}


def test_preset_examples_pass_their_own_checks(cfg):
    """예시 대본은 Claude가 따라 쓰는 기준이므로 검사를 그대로 통과해야 한다 (금지 표현·분량)."""
    presets, rules, sfx = load_presets(cfg), load_banned(cfg), available_sfx(cfg)
    for p in presets:
        for i in range(2):
            report = check_script(example_script(p, i), cfg.model_copy(update={"script": cfg.script.model_copy(
                update={"preset": p.id})}), presets, rules, sfx)
            assert report.errors == [], (p.id, i, report.errors)
            assert 20 <= report.seconds <= 33, (p.id, i, report.seconds)  # 30초 예시는 30초 안팎


@pytest.mark.parametrize("text, hit", [
    ("이건 100 % 효과 있어요", "100% 효과"),
    ("만족도 100%보장해요", "100%보장"),
    ("세균 99.9% 제거", "99.9% 제거"),
    ("지금 최저가예요", "최저가"),
    ("판매 1위 상품", "판매 1위"),
    ("면역력 강화에 좋아요", "면역력 강화"),
    ("뱃살이 쭉 빠져요", "뱃살이 쭉 빠져"),
    ("의사들이 추천하는 제품", "의사들이 추천"),
])
def test_banned_phrases_found(cfg, text, hit):
    found = find_banned(text, load_banned(cfg))
    assert found and found[0][1].replace(" ", "") == hit.replace(" ", "")


def test_banned_phrases_no_false_positive(cfg):
    rules = load_banned(cfg)
    for text in ["면 100% 소재라 부드러워요", "가격 대비 괜찮아요", "1분 만에 끓어요", "살짝 눌러 주세요"]:
        assert find_banned(text, rules) == [], text


def test_check_script_errors_and_warnings(cfg):
    presets, rules, sfx = load_presets(cfg), load_banned(cfg), available_sfx(cfg)
    p = presets[0]
    s = example_script(p, duration=45)
    assert any("프로젝트 길이" in e for e in check_script(s, cfg, presets, rules, sfx).errors)

    chosen = cfg.model_copy(update={"script": cfg.script.model_copy(update={"preset": "value_deal"})})
    assert any("고른 프리셋" in e for e in check_script(example_script(p), chosen, presets, rules, sfx).errors)

    data = example_script(p).model_dump()
    data["sentences"][2]["text"] = "이건 최저가 보장이고 효과 보장이에요."
    data["sentences"][2]["emphasis"] = []
    data["sentences"][0]["text"] = "여행 갈 때마다 무거운 포트를 캐리어에 넣고 다니느라 정말 힘드셨죠?"
    data["sentences"][0]["emphasis"] = []
    data["sentences"][-1]["text"] = "오늘도 좋은 하루 보내세요."
    data["sentences"][-1]["emphasis"] = []
    for sent in data["sentences"]:
        sent["sfx"] = "boom" if sent["id"] == "s2" else "pop"
    report = check_script(Script.model_validate(data), cfg, presets, rules, sfx)
    assert any("s3: 금지 표현 '최저가'" in e for e in report.errors) and any("효과 보장" in e for e in report.errors)
    text = "\n".join(report.warnings)
    assert "훅이 깁니다" in text and "행동 유도가 없습니다" in text and "'boom'" in text and "효과음이 6개" in text

    long = example_script(p).model_dump()
    long["sentences"][2]["text"] = "이건 접으면 두께가 정말 얇아져요. " * 30
    long["sentences"][2]["emphasis"] = []
    assert any("분량 초과" in e for e in check_script(Script.model_validate(long), cfg, presets, rules, sfx).errors)


def test_duration_estimate_matches_measured_tts():
    # edge-tts SunHi +10% 실측: 117음절·6문장 → 24.6초
    assert estimate_seconds(["가" * n for n in (18, 24, 16, 20, 24, 15)]) == pytest.approx(24.6, abs=0.1)
    assert speech_rate("+20%") > speech_rate("+10%") > speech_rate("-10%")
    assert speech_rate("이상한 값") == speech_rate("+10%")
    lo, hi, n = syllable_budget(30)
    assert estimate_seconds(["가" * (hi // n)] * n) == pytest.approx(30, abs=1)  # 상한만큼 쓰면 30초


def test_analyze_style():
    text = "솔직히 이거 반신반의하면서 샀거든요. 근데 생각보다 좋더라고요!\n이거 왜 이제 샀을까요? 진짜 편하거든요."
    style = analyze_style(text, "ref.txt", duration=10.0)
    assert style.sentence_count == 4 and style.hook == "솔직히 이거 반신반의하면서 샀거든요."
    assert style.endings[0] == ("든요", 2)
    assert style.question_ratio == 0.25 and style.syllables_per_sec == 4.3  # 43음절 / 10초
    with pytest.raises(ScriptError):
        analyze_style("...", "empty.txt")


class FakeTranscriber:
    def __init__(self):
        self.calls = 0

    def transcribe(self, audio):
        self.calls += 1
        return "이거 진짜 편하더라고요. 아직도 손으로 하세요?"


@needs_ffmpeg
def test_reference_style_sources(home, tmp_path):
    ws = Workspace.create(Source(type="keyword", value="포트"))
    cfg = ws.config()
    from ssm.media import Media
    media = Media(cfg)

    txt = tmp_path / "레퍼런스.txt"
    txt.write_text("아직도 이렇게 하세요? 이거 하나면 끝나요.", encoding="utf-8")
    assert reference_style(ws, cfg, str(txt), media, log=lambda m: None).sentence_count == 2
    assert (ws.path / "reference_style.json").is_file()

    video = make_video(tmp_path / "bench.mp4", seconds=2)
    fake = FakeTranscriber()
    style = reference_style(ws, cfg, str(video), media, transcriber=lambda c: (fake, ""), log=lambda m: None)
    assert style.hook == "이거 진짜 편하더라고요." and style.syllables_per_sec is not None
    reference_style(ws, cfg, str(video), media, transcriber=lambda c: (fake, ""), log=lambda m: None)
    assert fake.calls == 1  # 같은 레퍼런스는 다시 받아 적지 않는다

    (ws.path / "reference_style.json").unlink()
    with pytest.raises(ScriptError, match=r"\.txt"):  # 음성 인식을 못 쓰면 텍스트로 달라고 안내
        reference_style(ws, cfg, str(video), media, transcriber=lambda c: (None, "DLL"), log=lambda m: None)


@needs_ffmpeg
def test_prepare_request_and_check(home, tmp_path):
    files = [make_video(tmp_path / "a.mp4", "320x568", 4, shots=2), make_video(tmp_path / "b.mp4", "320x568", 3)]
    ws = Workspace.create(Source(type="url", value="https://www.xiaohongshu.com/explore/abc"))
    import_local_videos(ws, files)
    cands = Candidates(source="https://www.xiaohongshu.com/explore/abc", candidates=[
        Candidate(id="c01", reference=True, title="折叠电热水壶 出差必备", description="可折叠 双电压", grade="same_product"),
        Candidate(id="c02", grade="mood")])
    (ws.path / "candidates.json").write_text(cands.model_dump_json(), encoding="utf-8")
    run_analyze(ws, log=lambda m: None)

    with pytest.raises(ScriptError, match="프리셋을 골라야"):
        prepare_request(ws, log=lambda m: None)
    ws.set_override("script.preset", "honest_review")
    out = prepare_request(ws, log=lambda m: None)
    prompt = out.read_text(encoding="utf-8")
    assert "내돈내산 찐리뷰형" in prompt and "약 112~132음절, 문장 9개 안팎" in prompt
    assert "## 5. 금지 표현" in prompt  # 레퍼런스 절이 없어도 번호가 이어진다
    assert "折叠电热水壶 出差必备" in prompt and "같은 상품 영상 1개, 분위기 영상(mood) 1개" in prompt
    assert "script_frames.jpg" in prompt and (ws.path / "script_frames.jpg").is_file()
    assert "최저가" in prompt  # 금지 표현 목록
    example = json.loads(prompt.split("```json\n")[1].split("```")[0])
    assert Script.model_validate(example).preset == "honest_review"

    with pytest.raises(ScriptError, match="script.json이 없습니다"):
        run_script_check(ws, log=lambda m: None)
    presets = load_presets(ws.config())
    bad = example_script(find_preset(presets, "curiosity"))
    (ws.path / "script.json").write_text(bad.model_dump_json(), encoding="utf-8")
    with pytest.raises(ScriptError, match="고른 프리셋"):
        run_script_check(ws, log=lambda m: None)
    good = example_script(find_preset(presets, "honest_review"))
    (ws.path / "script.json").write_text(good.model_dump_json(), encoding="utf-8")
    run_script_check(ws, log=lambda m: None)
    assert ws.status("script") == "done"

    ws.set_override("script.preset", "value_deal")  # 프리셋을 바꾸면 대본을 다시 써야 한다
    assert ws.status("script") == "stale"


@needs_ffmpeg
def test_cli_presets_and_script(home, tmp_path):
    runner = CliRunner()
    r = runner.invoke(app, ["presets"])
    assert r.exit_code == 0 and "호기심" in r.output and "정보성 큐레이션" in r.output

    runner.invoke(app, ["new", "--local", str(make_video(tmp_path / "a.mp4")), "-y"])
    ws = Workspace.open(None)
    r = runner.invoke(app, ["script"])
    assert r.exit_code == 1 and "프리셋을 골라야" in r.output
    r = runner.invoke(app, ["script", "--preset", "9"])
    assert r.exit_code == 1 and "ssm presets" in r.output
    r = runner.invoke(app, ["script", "--preset", "1"])
    assert r.exit_code == 0, r.output
    assert ws.config().script.preset == "curiosity" and (ws.path / "script_prompt.md").is_file()

    good = example_script(find_preset(load_presets(ws.config()), "curiosity"))
    (ws.path / "script.json").write_text(good.model_dump_json(), encoding="utf-8")
    r = runner.invoke(app, ["script", "--check"])
    assert r.exit_code == 0 and "대본 검사 통과" in r.output
