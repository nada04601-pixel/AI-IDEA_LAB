import copy

import pytest
from pydantic import ValidationError

from ssm.schemas import Script

VALID = {
    "version": 1,
    "preset": "curiosity",
    "target_duration_sec": 30,
    "product": {"name": "접이식 실리콘 전기포트", "features": ["접으면 5cm"], "price_hint": "2만원대"},
    "sentences": [
        {"id": "s1", "section": "hook", "text": "아직도 여행 갈 때 포트 못 챙기세요?", "emphasis": ["포트"], "sfx": "whoosh"},
        {"id": "s2", "section": "demo", "text": "접으면 두께가 5센티밖에 안 돼요.", "emphasis": ["5센티"],
         "scene_hint": "접는 장면"},
        {"id": "s3", "section": "cta", "text": "궁금하시면 댓글에 '링크' 남겨주세요!", "emphasis": ["링크"], "sfx": None},
    ],
    "thumbnail_text": {"top": "여행 필수템", "bottom": "접으면 5cm 전기포트"},
}


def test_spec_example_is_valid():
    assert Script.model_validate(VALID).sentences[1].scene_hint == "접는 장면"


def mutate(fn):
    data = copy.deepcopy(VALID)
    fn(data)
    return data


@pytest.mark.parametrize("data, message", [
    (mutate(lambda d: d["sentences"][1].update(id="s1")), "중복"),
    (mutate(lambda d: d["sentences"][0].update(section="demo")), "hook"),
    (mutate(lambda d: d["sentences"][2].update(section="benefit")), "cta"),
    (mutate(lambda d: d["sentences"][1].update(emphasis=["없는말"])), "강조어"),
    (mutate(lambda d: d["sentences"][1].update(section="intro")), "section"),
    (mutate(lambda d: d.update(extra=1)), "extra"),
])
def test_invalid_scripts(data, message):
    with pytest.raises(ValidationError, match=message):
        Script.model_validate(data)
