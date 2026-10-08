# 006. AI Shorts Studio

쇼츠 주제를 입력하면 대본·장면을 만들고, 장면별로 승인한 뒤 세로형 MP4로 내보내는 개인용 웹 애플리케이션.

- 요구사항·작업 지침: [ideas/006-ai-shorts-studio/idea.md](../../ideas/006-ai-shorts-studio/idea.md)
- 현재 단계: **2단계 완료 — 대본과 스토리보드** (1단계: 기본 뼈대·프로젝트 관리)
- 외부 AI·유료 API 호출: **없음** — 대본·스토리보드는 mock provider로 만든다

## 구성

| 폴더 | 내용 |
|---|---|
| `backend/` | Python + FastAPI + SQLAlchemy(SQLite). `app/providers/`에 AI 공급자 어댑터 |
| `frontend/` | Next.js(App Router) + TypeScript |
| `storage/` | 실행 시 자동 생성. SQLite DB와 생성 자산 (Git 제외) |

## 실행 방법

필요한 도구: Python 3.11 이상, Node.js 20 이상. (FFmpeg는 4단계 렌더링부터 필요)

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
# 백엔드 (프로젝트·장면 API, mock provider, 입력 검증, 재시작 후 데이터 유지, 1단계 DB 업그레이드)
cd backend && pytest

# 프런트엔드 (입력 검증·장면 도우미 단위 테스트, 타입 검사, 빌드)
cd frontend && npm test && npm run typecheck && npm run build
```

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

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/health` | 상태 확인 |
| GET | `/api/projects` | 프로젝트 목록 (최근 수정순) |
| POST | `/api/projects` | 프로젝트 생성 |
| GET | `/api/projects/{id}` | 프로젝트 상세 |
| PATCH | `/api/projects/{id}` | 프로젝트 수정 (보낸 필드만) |
| DELETE | `/api/projects/{id}` | 프로젝트 삭제 (장면도 함께 삭제) |
| POST | `/api/projects/{id}/generate-script` | 대본 초안 생성·저장. 기존 대본이 있으면 `{"overwrite": true}` 필요 (없으면 409) |
| POST | `/api/projects/{id}/storyboard` | 저장된 대본을 빈 줄 기준으로 장면 생성. 기존 장면이 있으면 `{"replace": true}` 필요 (없으면 409) |
| GET | `/api/projects/{id}/scenes` | 장면 목록 (순서대로) |
| POST | `/api/projects/{id}/scenes` | 장면을 맨 뒤에 추가 (프로젝트당 최대 50개) |
| POST | `/api/projects/{id}/scenes/reorder` | `{"scene_ids": [...]}` 순서로 장면 번호를 다시 매김. 모든 장면을 한 번씩 포함해야 함 |
| PATCH | `/api/scenes/{scene_id}` | 장면 수정 (대사·화면 설명·이미지/영상 프롬프트·길이) |
| DELETE | `/api/scenes/{scene_id}` | 장면 삭제 후 번호를 1부터 다시 매김 |

입력 규칙
- 프로젝트: 제목 1~200자, 주제 2000자 이하, 목표 길이 5~180초, 화면 비율 `9:16`(기본)·`16:9`·`1:1`, 스타일 200자 이하, 대본 20,000자 이하
- 장면: 대사·화면 설명 2000자 이하, 이미지·영상 프롬프트 4000자 이하, 길이 0.5~60초
- 장면 상태는 2단계에서 항상 `draft`. 승인·반려는 3단계에서 추가한다.

## AI 공급자 (provider)

`app/providers/base.py`의 `ScriptProvider` 인터페이스(`generate_script`, `generate_storyboard`)를 구현하면 공급자를 바꿀 수 있다. `AISS_SCRIPT_PROVIDER` 환경 변수로 고르며 기본값이자 현재 유일한 값은 `mock`이다.

mock 공급자 규칙 (외부 호출·비용 없음, 같은 입력이면 항상 같은 결과)
- 대본: 목표 길이에 맞춰 3~8개 문단(장면당 약 7초)을 만든다. 모든 문단은 `[mock]`으로 시작한다.
- 스토리보드: 빈 줄로 문단을 나눠 장면으로 만든다(최대 30개). 장면 길이는 글자 수에 비례해 0.5초 단위로 나누고, 합계는 목표 길이와 같다. 화면 설명·프롬프트는 프로젝트 스타일과 문단 요약으로 채운다.

실제 AI 공급자는 비용 표시와 유료 작업 전 확인이 갖춰진 뒤(3단계 이후) 사용자 승인을 받아 추가한다.

## 데이터베이스 초기화

MVP 단계에서는 서버 시작 시 테이블이 없으면 자동으로 만든다 (`app/db.py`의 `init_db`). 이전 단계에서 만든 DB를 열면 나중에 추가된 열을 자동으로 붙인다 (`ADDED_COLUMNS`, 예: 2단계의 `projects.script`). 기존 데이터는 그대로 남는다. 열 추가보다 복잡한 변경(이름 변경·삭제·타입 변경)이 필요해지면 Alembic으로 옮긴다. 데이터를 처음부터 다시 시작하려면 서버를 끄고 `storage/app.db`를 지운다.

## 다음 단계 (3단계 — 장면 생성 및 승인)

- 이미지/영상 provider 어댑터 (mock부터)
- Asset·Job 모델, 장면별 생성 작업과 상태 표시
- 미리보기, 승인, 반려 사유, 재생성, 실패 작업 재시도
- 비용 기록 및 유료 작업 전 확인
