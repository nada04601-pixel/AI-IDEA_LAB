# 007. 쇼핑 쇼츠 메이커

해외 숏폼(샤오홍슈·도우인 등) 링크 하나로 한국어 쇼핑 쇼츠(1080×1920 MP4)와 썸네일·캡션을 만드는 CLI.
Claude Code 안에서 대화하며 쓰도록 설계했다 (대본은 Claude가 쓰고, 영상 처리는 `ssm`이 한다).

- 요구사항: [ideas/007-shopping-shorts-maker/idea.md](../../ideas/007-shopping-shorts-maker/idea.md) (v1.0)
- Claude Code 작업 지침: [CLAUDE.md](CLAUDE.md)
- 현재 단계: **M3 완료** — 샤오홍슈·도우인 링크 → 같은 상품 영상 수집(yt-dlp → 브라우저 대체)·국내 콘텐츠 필터·CLIP 유사도 등급 (`ssm collect`)
  → 영상 분석 → TTS · 문장 경계 다중 컷 편집 · 원본 자막 블러 · 한국어 자막 · 광고 표시 · 효과음·BGM · -14 LUFS (`ssm run`)

## 설치

| OS | 방법 |
|---|---|
| Windows (권장: NVIDIA GPU) | 탐색기에서 **`setup.bat` 더블클릭** |
| Mac / Linux | `./setup.sh` |

setup이 하는 일: Python 3.11~3.12 확인 → `.venv` 생성 → GPU가 있으면 CUDA용 PyTorch, 없으면 CPU용 설치 →
패키지 설치 → FFmpeg 확인(Windows는 없으면 winget 설치 제안) → 폰트 내려받기 → `ssm doctor` 점검.
여러 번 실행해도 안전하다. GPU가 있는데 CPU용 PyTorch가 깔렸다면 `setup.bat -ReinstallTorch`.

설치가 끝나면 `ssm doctor`에 **실패 항목이 없어야** 한다 (주의 항목은 나중 단계에서 필요할 때 준비하면 됨).

## 사용

```text
ssm.bat doctor                      # 설치 점검 (Mac/Linux: ./ssm doctor)
ssm.bat new <URL|키워드> [--local 파일...] [--duration 30] [--fps 30] [--ad coupang|aliexpress|custom] [--ad-text 문구]
ssm.bat list                        # 프로젝트 목록
ssm.bat status [ID]                 # 단계별 진행 상황 (ID 생략 시 최근 프로젝트)
ssm.bat set subtitle.size 90        # 이 프로젝트의 설정 변경 → 영향받는 단계만 다시 실행 대상
ssm.bat versions / rollback 2       # 결과물 버전 보관·되돌리기
ssm.bat collect [--keyword 검색어] [--url 링크]   # 같은 상품 영상 수집·필터 → raw_videos/ (candidates.json에 후보별 사유)
ssm.bat add 영상.mp4 ...             # 같은 상품 영상 추가 (analyze부터 다시)
ssm.bat run                         # 남은 단계 실행 (현재 analyze·tts·edit, 개발 전 단계는 건너뜀)
ssm.bat edit --preview              # 540x960 미리보기
```

Claude Code에서는 이 폴더를 열고 "이 링크로 쇼츠 만들어줘"처럼 말하면 Claude가 위 명령을 실행한다.

## 설정

- `config.yaml`: 기본값 (영상 규격, 자막 스타일, 광고 문구, TTS 목소리, 수집 기준 등)
- `config.local.yaml`: 개인 설정 (Git 제외). 같은 키만 적으면 덮어쓴다. 예:
  ```yaml
  collector:
    cookies_file: secrets/cookies.txt
  ffmpeg_path: C:/ffmpeg/bin/ffmpeg.exe
  ```
- 프로젝트별 설정: `workspace/{id}/project.yaml`의 `overrides` (`ssm set`으로 변경)
- 수집용 부계정 쿠키: [docs/cookies.md](docs/cookies.md)

## 작업 폴더

```text
workspace/{YYYYMMDD-HHMM-이름}/
├── project.yaml       # 원본 정보 + 프로젝트별 설정
├── state.json         # 단계별 완료 기록 (입력 해시)
├── raw_videos/  logs/  versions/v1 …
└── (단계별 결과) candidates.json, analysis.json, script.json, tts.mp3, subtitles.srt, final_output.mp4, thumbnail*.png, caption.txt
```

단계 의존 관계: `collect → analyze → script → tts → edit`, `analyze·script → meta`.
설정이나 앞 단계 파일이 바뀌면 그 영향을 받는 단계만 '다시 실행 필요'가 된다 (예: 자막 크기 → edit만).

## 개발

```bash
./setup.sh                      # 또는 setup.bat
.venv/bin/pytest                # Windows: .venv\Scripts\python -m pytest
```

| 폴더/파일 | 내용 |
|---|---|
| `src/ssm/main.py` | CLI (typer) |
| `src/ssm/config.py` | 설정 읽기·검증 (config.yaml ← config.local.yaml ← 프로젝트 overrides) |
| `src/ssm/workspace.py` | 작업 폴더, 단계 상태·캐시 무효화, 버전 |
| `src/ssm/schemas.py` | `script.json`, `project.yaml` 형식 |
| `src/ssm/doctor.py` | 설치 점검 |
| `src/ssm/fonts.py` | 폰트 내려받기 (SHA256 확인) |

폰트·효과음·BGM 라이선스: [assets/LICENSES.md](assets/LICENSES.md)
