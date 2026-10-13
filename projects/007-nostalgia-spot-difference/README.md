# 007. 그리운 옛날 풍경 · 다른 그림 찾기 Shorts

한국 1960~80년대 생활 풍경을 동화책풍 그림으로 그리고, **다른 그림 찾기 문제 → 정답 JSON → 자동 검사 → 1080×1920 Shorts 영상 → (선택) 비공개 업로드**까지 한 번에 만드는 저비용 자동화 도구입니다.

- 요청서(기획·기술 명세): [ideas/007-nostalgia-spot-difference/idea.md](../../ideas/007-nostalgia-spot-difference/idea.md)
- 현재 단계: **1·2단계 완료 (MVP + 안정성 검사)**, 3단계(ComfyUI)·4단계(업로드)·5단계(예약 실행) **코드 준비됨 — 실제 연결은 사용자 환경에서 확인 필요**
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

1. ComfyUI 설치: https://github.com/comfyanonymous/ComfyUI (GPL-3.0). 실행하면 기본 주소 `http://127.0.0.1:8188`.
2. 체크포인트(모델)를 `ComfyUI/models/checkpoints/`에 넣습니다. **라이선스를 반드시 확인하세요** → [docs/LICENSES.md](docs/LICENSES.md)
3. `.env`에서 `IMAGE_SOURCE=comfyui`, `COMFYUI_CHECKPOINT=<파일명>`을 설정하고 `main.py doctor`로 연결을 확인합니다.
4. 기본 워크플로는 `workflows/comfyui_workflow.json`(SDXL txt2img, API 형식)입니다. 본인 워크플로를 ComfyUI의 **Save (API Format)**으로 저장해 교체할 수 있고, 문자열 `%PROMPT% %NEGATIVE% %SEED% %CKPT% %WIDTH% %HEIGHT%`가 실행 시 바뀝니다.

권장 사양(대략): SDXL은 VRAM 8GB 이상(12GB 권장), SD 1.5 계열은 4~6GB. GPU가 없거나 VRAM이 부족하면 기본값 `procedural`을 그대로 쓰면 됩니다.

> **알려진 한계**: AI가 만든 그림은 소품 데이터가 없어서, 차이는 디테일이 많은 영역을 골라 자동 편집(색 바꾸기·좌우 반전·무늬·소품 붙이기·옆 영역 복사로 지우기)합니다. 의미 있는 물체를 골랐다는 보장이 약하므로 **항상 `needs_review`**가 되고, 사람이 미리보기를 보고 승인해야 업로드됩니다. 지우기 품질을 높이려면 ComfyUI 인페인팅 워크플로를 추가하는 것이 다음 개선 과제입니다.

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

## 다양성 (반복 콘텐츠 방지)

- 주제 8개(5개 시리즈) — `data/topics.json`에 추가하면 바로 반영됩니다. 새 장면 그림이 필요하면 `src/scenes.py`에 템플릿을 추가합니다.
- 같은 주제라도 seed마다 소품 색·위치·종류·차이 유형이 바뀌고, 차이 유형은 골고루 섞이도록 고릅니다.
- 제목·설명 문구 여러 가지 중 최근에 쓰지 않은 것을 고릅니다.

## 알려진 한계

- 내장 장면은 소품 조합이라 그림체가 단순한 편입니다. 더 풍부한 그림은 3단계(ComfyUI)나 직접 그린 샘플 그림으로 보완합니다.
- 렌더링은 4코어 기준 영상 1개에 약 1분입니다(대부분 FFmpeg 인코딩). 하루 1~3개에는 충분합니다.
- 업로드·ComfyUI 코드는 이 저장소의 자동 테스트에서 실제 Google·ComfyUI 서버에 연결해 보지 않았습니다(가짜 객체로 안전장치만 검증). 처음 연결할 때 `doctor`와 비공개 업로드 1건으로 확인하세요.
- Shorts 화면 아래쪽은 YouTube 앱의 제목·버튼에 일부 가려질 수 있어, 중요한 안내는 위쪽에 둡니다.
