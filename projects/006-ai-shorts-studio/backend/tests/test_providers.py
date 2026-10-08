import pytest

from app.providers import get_script_provider
from app.providers.base import ScriptRequest
from app.providers.mock import MockScriptProvider, distribute_duration, scene_count_for, split_paragraphs

REQ = ScriptRequest(title="고양이", topic="고양이가 상자를 좋아하는 이유", target_duration_sec=30, aspect_ratio="9:16", visual_style="수채화")


def test_mock_script_is_deterministic_and_marked():
    p = MockScriptProvider()
    script = p.generate_script(REQ)
    assert script == p.generate_script(REQ)
    paragraphs = split_paragraphs(script)
    assert len(paragraphs) == scene_count_for(30)
    assert all(par.startswith("[mock]") for par in paragraphs)
    assert "고양이가 상자를 좋아하는 이유" in paragraphs[0]


def test_mock_script_falls_back_to_title():
    script = MockScriptProvider().generate_script(ScriptRequest("제목만", "  ", 30, "9:16", ""))
    assert "제목만" in script


@pytest.mark.parametrize("duration,expected", [(5, 3), (30, 4), (60, 8), (180, 8)])
def test_scene_count(duration, expected):
    assert scene_count_for(duration) == expected


def test_split_paragraphs():
    assert split_paragraphs("a\n\n\nb\r\n\r\nc\n  \n") == ["a", "b", "c"]
    assert split_paragraphs("한 줄\n다음 줄") == ["한 줄\n다음 줄"]
    assert split_paragraphs("   \n\n ") == []


def test_distribute_duration_sums_to_target():
    secs = distribute_duration([10, 30, 20], 30)
    assert sum(secs) == 30
    assert all(s >= 0.5 and (s * 2).is_integer() for s in secs)
    assert secs[1] > secs[2] > secs[0]
    assert distribute_duration([], 30) == []
    assert distribute_duration([1] * 4, 1) == [0.5] * 4  # 장면이 너무 많으면 최소 길이


def test_storyboard_from_script():
    scenes = MockScriptProvider().generate_storyboard("첫 장면\n\n두 번째 장면", REQ)
    assert [s.dialogue for s in scenes] == ["첫 장면", "두 번째 장면"]
    assert sum(s.duration_sec for s in scenes) == 30
    assert "수채화" in scenes[0].image_prompt


def test_unknown_provider(monkeypatch):
    monkeypatch.setenv("AISS_SCRIPT_PROVIDER", "nope")
    with pytest.raises(RuntimeError):
        get_script_provider()


def test_storyboard_prompts_are_clean():
    script = MockScriptProvider().generate_script(REQ)
    scene = MockScriptProvider().generate_storyboard(script, REQ)[0]
    assert scene.dialogue.startswith("[mock]")
    assert scene.visual_description.count("[mock]") == 1
    assert "[mock]" not in scene.image_prompt and "[mock]" not in scene.video_prompt
    assert "vertical" in scene.image_prompt
    multi = MockScriptProvider().generate_storyboard("첫 줄\n둘째 줄", REQ)[0]
    assert "\n" not in multi.image_prompt
