import pytest
from pydantic import ValidationError

from ssm.config import AppConfig, deep_merge, load_config, set_dotted


def test_shipped_config_is_valid(home):
    cfg = load_config()
    assert cfg.project.duration_sec == 30
    assert cfg.video.fps == 30
    assert cfg.audio.original == "mute"
    assert cfg.ad_disclosure.profile is None
    assert cfg.ad_disclosure.text() is None
    assert cfg.path("assets/fonts").is_relative_to(home)


def test_local_config_overrides_defaults(home):
    (home / "config.local.yaml").write_text("collector:\n  cookies_file: D:/쿠키/cookies.txt\n", encoding="utf-8")
    cfg = load_config()
    assert cfg.collector.cookies_file == "D:/쿠키/cookies.txt"
    assert cfg.collector.max_videos == 5  # 나머지는 그대로


@pytest.mark.parametrize("profile, expected", [
    ("coupang", "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."),
    ("aliexpress", "이 영상은 알리익스프레스 어필리에이트 활동의 일환으로, 구매 시 일정액의 수수료를 받을 수 있습니다."),
])
def test_ad_profiles(home, profile, expected):
    cfg = load_config({"ad_disclosure": {"profile": profile}})
    assert cfg.ad_disclosure.text() == expected


def test_custom_ad_requires_text(home):
    with pytest.raises(ValidationError, match="custom_text"):
        load_config({"ad_disclosure": {"profile": "custom"}})
    cfg = load_config({"ad_disclosure": {"profile": "custom", "custom_text": " 유료 광고 포함 "}})
    assert cfg.ad_disclosure.text() == "유료 광고 포함"


@pytest.mark.parametrize("override", [
    {"project": {"duration_sec": 20}},
    {"video": {"fps": 24}},
    {"audio": {"original": "low"}},
    {"subtitle": {"sizee": 80}},  # 오타 키
    {"collector": {"mood_threshold": 0.9, "same_product_threshold": 0.8}},
])
def test_invalid_values_rejected(home, override):
    with pytest.raises(ValidationError):
        load_config(override)


def test_merge_helpers():
    assert deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"b": 3}}) == {"a": {"b": 3, "c": 2}}
    base = {"a": {"b": 1}}
    assert set_dotted(base, "a.c.d", 2) == {"a": {"b": 1, "c": {"d": 2}}}
    assert base == {"a": {"b": 1}}  # 원본은 바뀌지 않는다


def test_defaults_without_file():
    assert AppConfig().subtitle.max_chars_per_line == 14
