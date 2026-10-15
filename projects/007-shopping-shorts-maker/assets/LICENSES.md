# 에셋 라이선스

상업적 이용이 가능한 에셋만 사용한다. 새 에셋을 추가하면 이 표에 출처와 라이선스를 적는다.

## 폰트 (`ssm fonts`가 내려받음, Git에는 올리지 않음)

| 파일 | 출처 | 라이선스 |
|---|---|---|
| Pretendard-ExtraBold/Bold/Black.otf | [orioncactus/pretendard v1.3.9](https://github.com/orioncactus/pretendard) | [SIL Open Font License 1.1](https://github.com/orioncactus/pretendard/blob/v1.3.9/LICENSE) |
| BlackHanSans-Regular.ttf | [google/fonts](https://github.com/google/fonts/tree/main/ofl/blackhansans) | [SIL Open Font License 1.1](https://github.com/google/fonts/blob/main/ofl/blackhansans/OFL.txt) |

OFL 폰트는 영상·이미지에 넣어 상업적으로 쓸 수 있다. 폰트 파일 자체를 판매하는 것만 금지된다.

## 효과음 (`assets/sfx/`)

기본 효과음 `whoosh`·`swish`·`pop`·`ding`은 파일이 아니라 렌더링할 때 FFmpeg로 직접 합성한다
(`src/ssm/audio_mix.py`의 `BUILTIN_SFX`, 노이즈·사인파 수식). 외부 음원이 아니므로 라이선스 제약이 없다.
`assets/sfx/{이름}.wav|mp3|…`를 두면 같은 이름의 기본 효과음 대신 그 파일을 쓴다 — 넣을 때 아래 표에 출처를 적는다.

| 파일 | 출처 | 라이선스 |
|---|---|---|
| (없음) | | |

## BGM (`assets/bgm/`)

번들하지 않는다. 상업 이용 가능한 음원(예: YouTube 오디오 보관함의 '저작자 표시 필요 없음' 음원)을 직접 넣고 아래 표에 출처를 적는다.
`audio.bgm: auto`면 이 폴더에서 프로젝트마다 하나를 고르고, 비어 있으면 BGM 없이 만든다.

| 파일 | 출처 | 라이선스 |
|---|---|---|
| (없음) | | |
