# 006. AI Shorts Studio

쇼츠 주제를 입력하면 대본·장면을 만들고, 장면별로 승인한 뒤 세로형 MP4로 내보내는 개인용 웹 애플리케이션.

- 요구사항·작업 지침: [ideas/006-ai-shorts-studio/idea.md](../../ideas/006-ai-shorts-studio/idea.md)
- 현재 단계: **MVP 완료 (5단계 안정화까지)** — 1단계 기본 뼈대·프로젝트 관리, 2단계 대본·스토리보드, 3단계 장면 생성·승인, 4단계 음성·자막·렌더링, 5단계 안정화
- 사용 방법: [docs/user-guide.md](docs/user-guide.md)
- 외부 AI·유료 API 호출: **없음** — 대본·스토리보드·장면 이미지·영상·음성 모두 mock provider로 만들고, 최종 MP4는 로컬 FFmpeg로 렌더링한다

## 구성

| 폴더 | 내용 |
|---|---|
| `backend/` | Python + FastAPI + SQLAlchemy(SQLite). `app/providers/`에 AI 공급자 어댑터 |
| `frontend/` | Next.js(App Router) + TypeScript |
| `storage/` | 실행 시 자동 생성. SQLite DB, 장면 자산 `projects/{프로젝트}/scenes/{장면}/image_v1.png`·`audio_v1.wav` 등, 최종 결과 `projects/{프로젝트}/renders/v1/shorts.mp4`·`subtitles.srt` (Git 제외) |

## 빠른 시작

```bash
cd projects/006-ai-shorts-studio
./start.sh        # 처음 한 번은 패키지 설치 후 실행. 브라우저에서 http://localhost:3000
```

Windows는 탐색기에서 **`start-windows.bat`을 더블클릭**합니다 (필요한 프로그램 확인 → 처음 한 번 패키지 설치 → 서버 두 개를 새 창으로 실행 → 브라우저 열기). 사용 순서와 문제 해결은 [사용 가이드](docs/user-guide.md)를 보세요.

## 실행 방법 (수동)

필요한 도구: Python 3.11 이상, Node.js 20 이상, FFmpeg (mock 영상 생성과 최종 렌더링에 사용. 영상에 자막을 입히려면 libass가 포함된 빌드가 필요하며, 대부분의 배포판에 포함되어 있다. FFmpeg가 없으면 영상 생성과 렌더링만 안 되고 나머지는 동작)

### 백엔드 (http://localhost:8000)

```bash
cd projects/006-ai-shorts-studio/backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

API 문서는 http://localhost:8000/docs 에서 볼 수 있다.

### 프런트엔드 (http://localhost:3000)

```bash
cd projects/006-ai-shorts-studio/frontend
npm install
npm run dev
```

백엔드 주소가 다르면 `frontend/.env.local`에 `NEXT_PUBLIC_API_BASE=...`를 적는다. 설정값 목록은 `.env.example` 참고.

## 테스트

```bash
# 백엔드 (API·mock 공급자·승인 규칙·재시도·유료 확인·음성·자막·렌더링·오류 메시지·이전 DB 업그레이드,
#         tests/test_full_flow.py는 주제 입력부터 MP4 내려받기까지 요구사항 5장 흐름 전체)
cd backend && pytest

# 프런트엔드 단위 테스트, 타입 검사, 빌드
cd frontend && npm test && npm run typecheck && npm run build

# 브라우저 흐름 테스트 (1~4단계 화면을 실제로 조작). 백엔드 가상환경이 있어야 한다.
# 포트 8100·3100과 임시 저장 폴더를 쓰므로 개발 중인 데이터에는 영향이 없다.
cd frontend
npx playwright install chromium    # 처음 한 번
npm run test:e2e
```

- FFmpeg가 없으면 영상·렌더링 관련 테스트는 건너뛴다(skip).
- Playwright가 받은 Chromium은 H.264를 재생하지 못하므로, 브라우저 테스트에서는 영상 파일을 ffprobe로 검사한다 (ffprobe가 없으면 그 검사만 건너뛴다).
- 다른 브라우저를 쓰려면 `PLAYWRIGHT_CHROMIUM_PATH`로 실행 파일 경로를 지정한다. Windows에서 Python 경로가 다르면 `AISS_PYTHON`으로 지정한다.

### 수동 확인 체크리스트 (1단계)

- [ ] 대시보드에서 제목 없이 만들기를 누르면 "제목을 입력하세요."가 보인다
- [ ] 프로젝트를 만들면 목록 맨 위에 나타난다
- [ ] 목록에서 프로젝트를 눌러 상세 화면으로 이동한다
- [ ] 설정을 바꾸고 저장한 뒤 새로고침해도 값이 유지된다
- [ ] 백엔드를 껐다 켜도 프로젝트가 남아 있다
- [ ] 삭제하면 확인창이 뜨고, 확인 후 목록에서 사라진다
- [ ] 백엔드를 끈 상태에서 대시보드를 열면 연결 오류 안내와 "다시 시도" 버튼이 보인다

### 수동 확인 체크리스트 (2단계)

- [ ] 프로젝트 화면 위쪽 탭으로 설정·대본·스토리보드를 오갈 수 있다
- [ ] 대본이 비어 있으면 "스토리보드로 나누기"가 꺼져 있다
- [ ] "대본 초안 생성 (mock)"을 누르면 `[mock]`으로 시작하는 예시 대본이 채워진다
- [ ] 대본이 있을 때 다시 생성하면 덮어쓰기 확인창이 뜬다
- [ ] 대본을 고치면 "저장 안 됨"이 보이고, 저장 후 새로고침해도 유지된다
- [ ] 저장하지 않고 새로고침하면 브라우저가 경고한다
- [ ] 글자 수·예상 장면 수·읽기 시간이 입력에 따라 바뀐다
- [ ] "스토리보드로 나누기"를 누르면 빈 줄 기준으로 장면이 만들어지고, 장면 길이 합계가 목표 길이와 같다
- [ ] 장면이 있을 때 다시 나누면 교체 확인창이 뜬다
- [ ] 장면의 대사·화면 설명·프롬프트·길이를 고치고 "장면 저장"하면 유지된다
- [ ] ↑/↓로 순서를 바꾸고, ✕로 삭제하고, "+ 장면 추가"로 맨 뒤에 추가할 수 있다
- [ ] 합계 길이가 목표와 다르면 차이(+/−초)가 표시된다

### 수동 확인 체크리스트 (3단계)

- [ ] "검토" 탭에 승인 진행률(승인 n/전체)과 공급자(mock, 무료)가 보인다
- [ ] 생성 전에는 "승인"이 꺼져 있다
- [ ] "이미지 생성"을 누르면 "생성 중…"이 보였다가 MOCK IMAGE 미리보기와 "검토 필요" 상태가 된다
- [ ] "승인"하면 상태가 "승인"으로 바뀌고 진행률이 올라간다
- [ ] 이미지 프롬프트에 `[mock-fail-once]`를 넣고 생성하면 실패 메시지와 "재시도" 버튼이 보이고, 재시도하면 성공한다
- [ ] "반려"는 사유 없이 확정할 수 없고, 사유를 넣으면 반려 사유가 카드에 표시된다
- [ ] "영상 생성"을 누르면 장면 길이만큼의 MP4가 만들어지고 재생된다 (이미지가 있으면 그 이미지로 만든다)
- [ ] 재생성하면 이전 버전(v1)이 남고 v2가 추가되며, 승인했던 장면은 다시 "검토 필요"가 된다
- [ ] 승인한 장면의 대사·프롬프트를 스토리보드에서 고치면 다시 "검토 필요"가 된다
- [ ] 생성 중인 장면은 다시 생성하거나 삭제할 수 없다
- [ ] "작업" 탭에 작업별 상태·시도 횟수·예상 비용·오류가 보이고, 실패한 작업은 여기서도 재시도할 수 있다
- [ ] 생성 도중 백엔드를 껐다 켜면 그 작업은 "실패(서버 재시작)"로 표시되고 재시도할 수 있다

### 수동 확인 체크리스트 (4단계)

- [ ] "렌더링" 탭 위쪽에 FFmpeg 버전과 "렌더링 준비" 상태가 보인다
- [ ] 승인 안 된 장면, 이미지·영상이 없는 장면, 음성이 없는 장면이 목록으로 보이고 "MP4 렌더링"이 꺼져 있다
- [ ] "음성 만들기 (n개 장면)"을 누르면 장면별 음성이 "준비됨"이 되고 재생 버튼이 생긴다 (대사 없는 장면은 무음)
- [ ] 자막 목록에 시간과 문장이 보이고 "SRT 내려받기"로 받을 수 있다
- [ ] 모든 장면이 승인되고 음성이 준비되면 "MP4 렌더링"이 켜지고, 누르면 진행률이 보인 뒤 결과 영상이 나타난다
- [ ] 결과 영상에 자막이 입혀져 있고 mock 음성(짧은 소리)이 들린다
- [ ] "MP4 내려받기"로 `프로젝트명_v1.mp4` 파일을 받을 수 있다
- [ ] "다시 렌더링"하면 v2가 생기고 v1은 "이전 버전"에서 받을 수 있다
- [ ] 장면 대사를 바꾸면 그 장면 음성이 "대사 바뀜"이 되고, 다시 승인하고 음성을 만들 때까지 렌더링이 막힌다
- [ ] "음성 넣기"를 끄면 음성 관련 문제가 목록에서 빠지고 무음 영상으로 렌더링된다
- [ ] "자막을 영상에 입히기"를 끄면 영상에는 자막이 없고, 플레이어에서 켤 수 있는 자막 트랙만 들어간다

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/health` | 상태 확인 |
| GET | `/api/projects` | 프로젝트 목록 (최근 수정순). 장면 수·승인 수·진행 중/실패 작업 수·최신 렌더 버전 포함 |
| POST | `/api/projects` | 프로젝트 생성 |
| GET | `/api/projects/{id}` | 프로젝트 상세 |
| PATCH | `/api/projects/{id}` | 프로젝트 수정 (보낸 필드만) |
| DELETE | `/api/projects/{id}` | 프로젝트 삭제 (장면·작업·자산 파일도 함께 삭제. 생성 중이면 409) |
| POST | `/api/projects/{id}/generate-script` | 대본 초안 생성·저장. 기존 대본이 있으면 `{"overwrite": true}` 필요 (없으면 409) |
| POST | `/api/projects/{id}/storyboard` | 저장된 대본을 빈 줄 기준으로 장면 생성. 기존 장면이 있으면 `{"replace": true}` 필요 (없으면 409). 생성 중이면 409 |
| GET | `/api/projects/{id}/scenes` | 장면 목록 (순서대로) |
| POST | `/api/projects/{id}/scenes` | 장면을 맨 뒤에 추가 (프로젝트당 최대 50개) |
| POST | `/api/projects/{id}/scenes/reorder` | `{"scene_ids": [...]}` 순서로 장면 번호를 다시 매김. 모든 장면을 한 번씩 포함해야 함 |
| PATCH | `/api/scenes/{scene_id}` | 장면 수정 (대사·화면 설명·이미지/영상 프롬프트·길이). 승인된 장면을 바꾸면 `review_required`로 되돌림 |
| DELETE | `/api/scenes/{scene_id}` | 장면 삭제 후 번호를 1부터 다시 매김 (생성 중이면 409) |
| GET | `/api/providers` | 대본·이미지·영상 공급자와 유료 여부, 1건 예상 비용 |
| POST | `/api/scenes/{scene_id}/generate-image` | 이미지 생성 작업 요청 → 202와 작업(Job). 유료 공급자면 `{"confirm_paid": true}` 필요 |
| POST | `/api/scenes/{scene_id}/generate-video` | 영상 생성 작업 요청 (최신 이미지가 있으면 그것으로 만듦) |
| POST | `/api/scenes/{scene_id}/approve` | 승인 (`review_required` 상태이고 결과가 있을 때만) |
| POST | `/api/scenes/{scene_id}/reject` | `{"reason": "..."}`로 반려 (`review_required`·`approved` 상태에서, 사유 필수) |
| GET | `/api/projects/{id}/jobs` | 작업 목록 (최신순) |
| GET | `/api/jobs/{job_id}` | 작업 상태 조회 |
| POST | `/api/jobs/{job_id}/retry` | 실패한 작업을 같은 프롬프트·공급자로 다시 실행 |
| GET | `/api/projects/{id}/assets` | 생성 자산 목록 (버전·비용·파일 주소) |
| GET | `/api/assets/{asset_id}/file` | 자산 파일 (Range 요청 지원). `?download=true`면 `프로젝트명_v1.mp4` 이름으로 내려받기 |
| POST | `/api/scenes/{scene_id}/generate-audio` | 장면 대사로 음성 생성 (장면의 검토·승인 상태는 바뀌지 않음) |
| POST | `/api/projects/{id}/generate-audio` | 음성이 없거나 대사가 바뀐 장면의 음성을 한 번에 생성 |
| GET | `/api/projects/{id}/render-check` | 렌더링 전 점검: FFmpeg, 장면별 승인·화면·음성 상태, 문제 목록 (`?include_audio=false`면 음성 문제 제외) |
| GET | `/api/projects/{id}/subtitles` | 장면 대사·길이로 계산한 자막 (cue 목록과 SRT 텍스트) |
| POST | `/api/projects/{id}/render` | `{"include_audio": true, "burn_subtitles": true}`로 최종 MP4 렌더링 작업 시작. 점검에 문제가 있으면 409 |
| GET | `/api/system/ffmpeg` | FFmpeg 사용 가능 여부와 버전 |

오류 응답은 항상 `{"detail": "화면에 보여줄 한국어 문장"}` 형식이다. 입력 검증 오류(422)는 `errors`에 필드 위치와 종류도 담는다. 예상하지 못한 오류(500)는 내부 내용을 숨기고 안내 문장만 돌려주며, 자세한 내용은 백엔드 로그에 남긴다.

입력 규칙
- 프로젝트: 제목 1~200자, 주제 2000자 이하, 목표 길이 5~180초, 화면 비율 `9:16`(기본)·`16:9`·`1:1`, 스타일 200자 이하, 대본 20,000자 이하
- 장면: 대사·화면 설명 2000자 이하, 이미지·영상 프롬프트 4000자 이하, 길이 0.5~60초
- 장면 상태: `draft`(초안) → `queued`(생성 대기) → `generating`(생성 중) → `review_required`(검토 필요) → `approved`(승인) / `rejected`(반려), 실패 시 `failed`
- 한 장면에는 동시에 하나의 작업만 실행된다 (중복 클릭으로 같은 작업이 두 번 실행되지 않게 409로 막는다).
- 재생성해도 이전 결과는 지우지 않고 버전(v1, v2, …)으로 남긴다.

## AI 공급자 (provider)

`app/providers/base.py`의 `ScriptProvider` 인터페이스(`generate_script`, `generate_storyboard`)를 구현하면 공급자를 바꿀 수 있다. `AISS_SCRIPT_PROVIDER` 환경 변수로 고르며 기본값이자 현재 유일한 값은 `mock`이다.

mock 공급자 규칙 (외부 호출·비용 없음, 같은 입력이면 항상 같은 결과)
- 대본: 목표 길이에 맞춰 3~8개 문단(장면당 약 7초)을 만든다. 모든 문단은 `[mock]`으로 시작한다.
- 스토리보드: 빈 줄로 문단을 나눠 장면으로 만든다(최대 30개). 장면 길이는 글자 수에 비례해 0.5초 단위로 나누고, 합계는 목표 길이와 같다. 화면 설명·프롬프트는 프로젝트 스타일과 문단 요약으로 채운다.

이미지·영상은 `app/providers/media.py`의 `MediaProvider` 인터페이스(`estimate_cost`, `generate`)를 구현한다. `AISS_IMAGE_PROVIDER`, `AISS_VIDEO_PROVIDER`로 고르며 현재는 `mock`만 있다.
- mock 이미지: Pillow로 프롬프트에 따라 색이 다른 "MOCK IMAGE" 그림을 만든다 (9:16이면 540×960).
- mock 영상: FFmpeg로 최신 이미지(없으면 단색 화면)를 장면 길이만큼의 H.264 MP4로 만든다. 일반 Chrome·Edge·Safari에서 재생된다. (Playwright 테스트용 Chromium은 H.264를 재생하지 못해 자동 테스트에서는 ffprobe로 파일을 확인한다.)
- 실패 확인용: 프롬프트에 `[mock-fail]`이 있으면 항상, `[mock-fail-once]`가 있으면 첫 시도만 실패한다.

비용 처리
- 작업마다 예상 비용(`estimated_cost`)을, 자산마다 실제 비용(`cost_amount`)을 기록하고 "작업" 탭에 합계를 보여준다. mock은 0(무료).
- 유료 공급자(`is_paid`)는 `confirm_paid: true` 없이 요청하면 작업을 만들지 않고 409와 예상 비용을 돌려준다. 화면에서는 예상 비용을 보여주는 확인창을 거친다.
- 실제(유료) AI 공급자는 아직 연결하지 않았다. 연결할 때는 사용자 승인을 먼저 받는다.

음성(TTS)도 같은 `MediaProvider` 인터페이스를 쓰며(`AISS_AUDIO_PROVIDER`, 프롬프트 자리에 읽을 대사를 넣는다), 결과 메타데이터에 대사 해시를 남겨 대사가 바뀌면 "대사 바뀜"으로 표시한다.
- mock 음성: 실제 목소리 대신 자막이 바뀌는 시점마다 짧은 소리가 나는, 장면 길이만큼의 WAV를 만든다.
- 음성은 검토·승인 대상이 아니다. 음성만 있는 장면은 승인할 수 없다 (이미지나 영상이 있어야 한다).

## 자막과 렌더링

자막
- 장면 순서대로 대사를 문장 부호·줄바꿈 기준으로 나누고, 28자가 넘으면 띄어쓰기에서 자른다. 한 줄이 16자를 넘으면 두 줄로 나눈다.
- 장면 안에서는 글자 수에 비례해 시간을 나눈다. 대사가 없는 장면은 자막 없이 시간만 지난다.

렌더링 (`app/services/render.py`, FFmpeg)
1. 모든 장면이 승인되어야 시작한다 (요구사항 9장). 음성을 넣는다면 대사가 있는 모든 장면의 음성이 최신이어야 한다.
2. 장면마다 최신 영상(없으면 최신 이미지)을 출력 크기에 맞추고(남는 부분은 검은 여백), 30fps로 장면 길이만큼 자른다. 영상이 짧으면 마지막 화면을 늘린다. 음성은 짧으면 무음으로 채우고 길면 자른다.
3. 장면 조각을 이어 붙이고, 자막을 영상에 입힌다(선택). 켜고 끌 수 있는 자막 트랙(mov_text)은 항상 넣는다.
4. 출력: H.264 + AAC MP4. 9:16은 1080×1920, 16:9는 1920×1080, 1:1은 1080×1080.
- 렌더링할 때마다 v1, v2…로 남고, SRT도 같은 버전으로 저장된다. 실패하면 만들던 파일을 지우고 작업 탭·렌더링 탭에서 재시도할 수 있다.
- 렌더링 중에는 장면 생성·음성 생성을 막는다.
- 자막 글꼴은 `AISS_SUBTITLE_FONT`로 바꿀 수 있다. 비워 두면 시스템이 한글을 표시할 수 있는 글꼴로 대체한다.

작업 실행
- 생성 요청은 작업을 `queued`로 만들고 바로 응답한다. 실제 생성은 같은 서버 프로세스의 백그라운드에서 실행되고, 화면은 작업이 끝날 때까지 1.5초마다 상태를 새로 고친다.
- 서버가 작업 도중 꺼지면, 다시 켤 때 남은 작업을 실패로 표시해 재시도할 수 있게 한다.

## 데이터베이스 초기화

SQLite는 외래 키 검사(`foreign_keys=ON`)와 WAL 모드, 30초 잠금 대기로 연다 (백그라운드 작업과 요청이 동시에 써도 덜 막히게). MVP 단계에서는 서버 시작 시 테이블이 없으면 자동으로 만든다 (`app/db.py`의 `init_db`). 이전 단계에서 만든 DB를 열면 나중에 추가된 열을 자동으로 붙인다 (`ADDED_COLUMNS`, 예: 2단계의 `projects.script`). 기존 데이터는 그대로 남는다. 3단계의 `jobs`·`assets` 테이블은 없으면 새로 만든다. 열 추가보다 복잡한 변경(이름 변경·삭제·타입 변경)이 필요해지면 Alembic으로 옮긴다. 데이터를 처음부터 다시 시작하려면 서버를 끄고 `storage/app.db`를 지운다.

## 완료 기준 점검 (요구사항 12장)

| 완료 기준 | 상태 | 확인 방법 |
|---|---|---|
| 로컬에서 프런트엔드와 백엔드를 실행할 수 있다 | ✅ | `./start.sh` 또는 수동 실행, 브라우저 테스트가 두 서버를 띄워 확인 |
| 프로젝트를 만들고 다시 열어도 데이터가 유지된다 | ✅ | `test_data_persists_across_restart`, `test_full_flow` (서버 재시작 후 이어서 진행) |
| 프로젝트의 장면을 생성/수정/정렬할 수 있다 | ✅ | `test_scenes.py`, `e2e/02-script-storyboard.spec.ts` |
| 장면을 승인·반려하고 반려 사유를 확인할 수 있다 | ✅ | `test_generation.py`, `e2e/03-review.spec.ts` |
| AI 키 없이 mock provider로 주요 흐름을 테스트할 수 있다 | ✅ | 모든 공급자 기본값이 mock, `test_full_flow.py` |
| 실제 외부 AI는 공급자 설정·비용을 알린 뒤 사용할 수 있다 | ✅ (구조) | 유료 공급자는 `confirm_paid` 없이는 작업을 만들지 않음 (`test_paid_provider_requires_confirmation`), 화면에서 예상 비용 확인창. 실제 공급자는 아직 연결하지 않음 |
| 승인 장면으로 최종 MP4를 생성하고 로컬로 내보낼 수 있다 | ✅ | `test_render.py`, `e2e/04-render.spec.ts` (내려받은 파일을 ffprobe로 확인) |
| 설치·실행·테스트 방법이 README에 기록되어 있다 | ✅ | 이 문서와 [사용 가이드](docs/user-guide.md) |

## 이후 할 수 있는 일

- 실제 AI 공급자 연결 (대본·이미지·영상·음성). `app/providers/`에 어댑터를 추가하고 환경 변수로 고른다. 비용이 들므로 공급자와 요금을 먼저 정한 뒤 진행한다.
- 자막 직접 편집, 효과음·배경음악, 장면 전환 효과
- 작업이 많아지면 별도 작업 큐(지금은 같은 서버 프로세스의 백그라운드에서 실행)
- 스키마 변경이 복잡해지면 Alembic 마이그레이션
