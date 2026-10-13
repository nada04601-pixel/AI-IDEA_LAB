# 007. 그리운 옛날 풍경 · 다른 그림 찾기 Shorts

한국 1960~80년대 생활 풍경을 동화책풍 그림으로 그리고, **다른 그림 찾기 문제 → 정답 JSON → 자동 검사 → 1080×1920 Shorts 영상 → (선택) 비공개 업로드**까지 한 번에 만드는 저비용 자동화 도구입니다.

- 요청서(기획·기술 명세): [ideas/007-nostalgia-spot-difference/idea.md](../../ideas/007-nostalgia-spot-difference/idea.md)
- 현재 단계: **1·2단계 완료**, **3단계(ComfyUI + 인페인팅) 구현 완료 — 사용자 PC(Windows, RTX 3060 12GB)에서 실측 필요**, 4단계(업로드)·5단계(예약 실행) 코드 준비됨
- 비용: 기본 경로는 **무료** (GPU·인터넷·유료 API 불필요). YouTube Data API도 무료(일일 할당량 내).

## 어떻게 동작하나요

```
주제 선택 → 원본 장면 → 차이 만들기 → 정답 JSON → 정답 검사 → 정답 미리보기 + 영상 렌더링 → 영상 검사 → 제목·설명 → (업로드)
```

| 단계 | 파일 | 설명 |
|---|---|---|
| 주제 선택 | `src/topic_picker.py`, `data/topics.json` | 최근 주제·같은 시리즈 연속을 피하고 덜 쓴 주제 우선 |
| 원본 장면 | `src/image_generator.py`, `src/scenes.py`, `src/props.py` | 기본은 **내장 손그림 장면**(기와집·장독대·가마솥·구멍가게 등 30여 종 소품). ComfyUI·샘플 그림은 플러그인 |
| 차이 만들기 | `src/difference_editor.py` | 소품 단위로 추가·제거·색·모양·무늬·방향 변경. 같은 장면 데이터를 다시 그리므로 구도가 100% 같음 |
| 정답 검사 | `src/validator.py` | 개수 일치, 크기·정렬, 정답 영역 밖 변화, 차이 크기, 정답 원 겹침 |
| 렌더링 | `src/video_renderer.py`, `src/audio.py` | 오프닝 3초 → 문제 20초(카운트다운) → 정답 공개 10초 → 마무리 3초 = 36초 |
| 영상 검사 | `src/validator.py` | 1080×1920, h264/yuv420p, 길이, 오디오, 파일 크기 (ffprobe) |
| 메타데이터 | `src/metadata_generator.py` | 제목 7가지 틀 중 최근에 안 쓴 것, 설명·해시태그, 과장 표현 없음 |
| 업로드 | `src/youtube_uploader.py` | OAuth, **기본 비공개**, 중복 방지(작업 ID·영상 해시), 재시도 제한 |
| 기록 | `src/db.py` → `data/jobs.sqlite` | 작업 상태, 실패 원인, 업로드 ID, 조회수. CSV 내보내기 |

결과물 (Git에 올라가지 않음):

```
output/videos/<작업ID>.mp4          완성 영상
output/videos/<작업ID>.txt          제목·설명 (수동 업로드용 복사)
output/previews/<작업ID>_answer.png 원본 | 수정본 + 정답 원 (사람 확인용)
output/images/<작업ID>_original.png / _modified.png
data/puzzles/<작업ID>.json          정답 데이터
output/logs/pipeline.log            실행·오류 로그
```

## 설치

필요한 것: **Python 3.10 이상**(3.11+ 권장), **FFmpeg**. GPU는 필요 없습니다.

### Windows (PowerShell)

```powershell
winget install --id Gyan.FFmpeg -e        # FFmpeg 설치 후 PowerShell 창을 새로 여세요
cd projects\007-nostalgia-spot-difference
.\setup-windows.bat                        # 가상환경 + 패키지 + .env 생성 + 환경 점검
```

수동으로 하려면:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe main.py doctor
```

### macOS / Linux

```bash
brew install ffmpeg            # macOS   (Ubuntu: sudo apt install ffmpeg)
cd projects/007-nostalgia-spot-difference
./scripts/setup.sh             # 가상환경 + 패키지 + .env 생성 + 환경 점검
```

## 사용법

아래 예시는 macOS/Linux 기준입니다. Windows에서는 `.venv/bin/python` 대신 `.\.venv\Scripts\python.exe`를 쓰세요.

```bash
.venv/bin/python main.py doctor                 # 환경 점검 (Python, FFmpeg, 한글 글꼴, GPU, ComfyUI, 업로드 설정)
.venv/bin/python main.py make                   # 영상 1개 (주제 자동 선택)
.venv/bin/python main.py make --topic old_kitchen --difficulty hard --seed 7
.venv/bin/python main.py batch --count 10       # 2단계 안정성 점검: 10개 만들고 요약
.venv/bin/python main.py jobs                   # 최근 작업 목록과 상태
.venv/bin/python main.py comfyui-test           # (3단계) ComfyUI 원본·인페인팅 1번씩 시험
```

Windows에서는 `make-video-windows.bat`을 더블클릭해도 영상 1개가 만들어집니다.

작업 상태:

| 상태 | 뜻 |
|---|---|
| `ready` | 모든 자동 검사 통과. 업로드가 켜져 있으면 자동으로 비공개 업로드 |
| `needs_review` | 영상은 만들었지만 검수 필요(차이가 작음, 정답 원 겹침, AI/샘플 그림 기반 등). **자동 업로드 안 함**. 미리보기를 확인한 뒤 `main.py approve <작업ID>` |
| `failed` | 검사 실패. 업로드 안 함. 이유는 `jobs`·로그에 기록 |
| `uploaded` | 업로드 완료 (video ID 기록) |

난이도: `easy` 3개, `normal` 5개(기본), `hard` 7개.

## 3단계 — ComfyUI 연결 (GPU가 있을 때)

**Windows + RTX 3060 12GB 기준 설치·설정 안내: [docs/comfyui-windows.md](docs/comfyui-windows.md)**

요약:
1. ComfyUI 휴대용(`ComfyUI_windows_portable_nvidia.7z`) 설치 → `run_nvidia_gpu.bat` 실행
2. `sd_xl_base_1.0.safetensors`(SDXL 1.0, OpenRAIL++-M, 상업적 이용 가능)를 `ComfyUI\models\checkpoints\`에
3. `.env`: `IMAGE_SOURCE=comfyui` → `main.py doctor` → `main.py comfyui-test`로 원본·인페인팅 시험

- 원본: `workflows/comfyui_workflow.json` (SDXL txt2img, 1216×832)
- 차이: 생긴/사라진 물건은 `workflows/comfyui_inpaint.json`(인페인팅)으로 그리고, **마스크 안쪽만** 합성해 정답 밖은 원본과 똑같이 유지합니다. 색·방향·무늬는 영역 편집입니다.
- 두 워크플로 모두 ComfyUI의 **Save (API Format)** JSON으로 교체할 수 있습니다. 문자열 `%PROMPT% %NEGATIVE% %SEED% %CKPT% %WIDTH% %HEIGHT% %IMAGE%`가 실행 시 바뀝니다.
- `COMFYUI_START_CMD`를 적어 두면 예약 실행 때 ComfyUI가 꺼져 있어도 자동으로 켭니다.

> **알려진 한계**: AI 그림은 소품 데이터가 없어서 "어디가 물건인지"를 그림의 복잡도로 추정합니다. 그래서 AI 그림 기반 문제는 **항상 `needs_review`**이고, 정답 미리보기를 보고 `approve`해야 업로드됩니다. 사람 확인 없이 매일 자동으로 돌리려면 `procedural`(내장 그림)을 쓰거나 두 방식을 섞으세요.

## 4단계 — YouTube 비공개 업로드

1. Google Cloud Console에서 프로젝트 생성 → **YouTube Data API v3** 사용 설정.
2. OAuth 동의 화면 설정(외부, 테스트 사용자에 본인 계정 추가) → 사용자 인증 정보 → **OAuth 클라이언트 ID (데스크톱 앱)** 생성 → JSON을 내려받아 이 폴더에 `credentials.json`으로 저장.
3. 패키지 설치: `pip install -r requirements-youtube.txt` (Windows: `scripts\setup-windows.ps1 -YouTube`)
4. `.venv/bin/python main.py auth` — 브라우저에서 로그인. `token.json`이 생깁니다.
5. `.env`에서 `UPLOAD_ENABLED=true`. 이후 `make`/`daily`가 `ready` 작업을 **비공개로** 올립니다. 특정 작업만: `main.py upload <작업ID>`.
6. `main.py status` — 업로드 처리 상태, 거부 사유, 조회수를 갱신합니다. `main.py export` — CSV 보고서.

안전장치:
- `credentials.json`, `token.json`, `.env`는 `.gitignore`에 들어 있습니다. 절대 커밋하지 마세요.
- 공개(`public`)·일부공개(`unlisted`)는 `UPLOAD_PRIVACY`와 함께 **`ALLOW_PUBLIC_UPLOAD=true`를 직접 켠 경우에만** 적용됩니다. 그 외에는 항상 `private`.
- 같은 작업 ID나 같은 영상 파일(SHA-256)은 다시 올리지 않습니다.
- 일시 오류(HTTP 5xx·네트워크)는 `MAX_RETRIES`번까지만 재시도합니다.
- 할당량: 영상 업로드 1회는 API 할당량을 많이 씁니다(기본 일일 할당량 기준 하루 수 건). 최신 수치는 [공식 문서](https://developers.google.com/youtube/v3/determine_quota_cost)와 Cloud Console에서 확인하세요.
- 인증 전 OAuth 앱이 "테스트" 상태면 토큰이 7일마다 만료될 수 있습니다. 그때는 `auth`를 다시 실행하세요.
- AI 생성 이미지(comfyui)로 만든 영상은 `containsSyntheticMedia`(변경되거나 합성된 콘텐츠)를 자동으로 표시합니다(`DECLARE_SYNTHETIC_MEDIA=auto`). 내장 일러스트는 사실적 합성 콘텐츠가 아니라 기본으로 표시하지 않습니다. 정책은 바뀔 수 있으니 YouTube 최신 안내를 확인하세요.

## 5단계 — 예약 실행

`main.py daily`가 `DAILY_COUNT`개(기본 1)를 만들고, 업로드가 켜져 있으면 `ready`인 것만 비공개로 올립니다.

Windows 작업 스케줄러 (매일 07:10):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register-windows-task.ps1 -Time 07:10
# 삭제: Unregister-ScheduledTask -TaskName "NostalgiaSpotDifference" -Confirm:$false
```

macOS / Linux (cron):

```bash
crontab -e
10 7 * * * /절대경로/projects/007-nostalgia-spot-difference/scripts/run-daily.sh
```

처음 1주일은 하루 1개로 돌리며 `output/previews/`와 `jobs`, `output/logs/`를 확인한 뒤 수량을 늘리세요.

## 테스트

```bash
.venv/bin/python -m pytest
```

- 모든 장면 템플릿 × 난이도에서 차이 생성·정답 검사 통과, 여러 seed 반복
- 검사기가 개수 불일치·정답 밖 변화·크기 불일치·변화 없는 정답을 잡아내는지
- 공개 설정 가드(기본 private), 중복 업로드 거부, 검수 대상 업로드 거부, 업로드 기본 꺼짐
- 짧은 타임라인으로 **실제 FFmpeg 렌더링까지 전체 흐름** 실행 후 ffprobe로 1080×1920·오디오 확인
- 가짜 ComfyUI 서버로 원본 생성·인페인팅·실패 시 대체·comfyui 원본 전체 흐름 확인

## 다양성 (반복 콘텐츠 방지)

- 주제 8개(5개 시리즈) — `data/topics.json`에 추가하면 바로 반영됩니다. 새 장면 그림이 필요하면 `src/scenes.py`에 템플릿을 추가합니다.
- 같은 주제라도 seed마다 소품 색·위치·종류·차이 유형이 바뀌고, 차이 유형은 골고루 섞이도록 고릅니다.
- 제목·설명 문구 여러 가지 중 최근에 쓰지 않은 것을 고릅니다.

## 알려진 한계

- 내장 장면은 소품 조합이라 그림체가 단순한 편입니다. 더 풍부한 그림은 3단계(ComfyUI)나 직접 그린 샘플 그림으로 보완합니다.
- 렌더링은 4코어 기준 영상 1개에 약 1분입니다(대부분 FFmpeg 인코딩). 하루 1~3개에는 충분합니다.
- ComfyUI 연동은 같은 HTTP API를 흉내 내는 가짜 서버로 테스트했습니다(업로드·프롬프트·결과 조회·인페인팅·실패 시 대체). 실제 GPU에서의 그림 품질과 속도는 `comfyui-test`로 확인하세요.
- YouTube 업로드 코드는 실제 Google 서버에 연결해 보지 않았습니다(가짜 객체로 안전장치만 검증). 처음 연결할 때 비공개 업로드 1건으로 확인하세요.
- Shorts 화면 아래쪽은 YouTube 앱의 제목·버튼에 일부 가려질 수 있어, 중요한 안내는 위쪽에 둡니다.
