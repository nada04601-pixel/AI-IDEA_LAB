# 006. AI Shorts Studio

쇼츠 주제를 입력하면 대본·장면을 만들고, 장면별로 승인한 뒤 세로형 MP4로 내보내는 개인용 웹 애플리케이션.

- 요구사항·작업 지침: [ideas/006-ai-shorts-studio/idea.md](../../ideas/006-ai-shorts-studio/idea.md)
- 현재 단계: **1단계 완료 — 기본 뼈대와 프로젝트 관리 (CRUD)**
- 외부 AI·유료 API 호출: **없음** (2단계부터 mock provider로 시작)

## 구성

| 폴더 | 내용 |
|---|---|
| `backend/` | Python + FastAPI + SQLAlchemy(SQLite) |
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
# 백엔드 (API CRUD, 입력 검증, 재시작 후 데이터 유지)
cd backend && pytest

# 프런트엔드 (입력 검증 단위 테스트, 타입 검사, 빌드)
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

## API (1단계 구현분)

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/health` | 상태 확인 |
| GET | `/api/projects` | 프로젝트 목록 (최근 수정순) |
| POST | `/api/projects` | 프로젝트 생성 |
| GET | `/api/projects/{id}` | 프로젝트 상세 |
| PATCH | `/api/projects/{id}` | 프로젝트 수정 (보낸 필드만) |
| DELETE | `/api/projects/{id}` | 프로젝트 삭제 |

입력 규칙: 제목 1~200자, 주제 2000자 이하, 목표 길이 5~180초, 화면 비율 `9:16`(기본)·`16:9`·`1:1`, 스타일 200자 이하.

## 데이터베이스 초기화

MVP 단계에서는 서버 시작 시 테이블이 없으면 자동으로 만든다 (`app/db.py`의 `init_db`). 스키마가 바뀌는 2단계부터 마이그레이션 도구(Alembic) 도입을 검토한다. 데이터를 처음부터 다시 시작하려면 서버를 끄고 `storage/app.db`를 지운다.

## 다음 단계 (2단계 — 대본과 스토리보드)

- Scene 모델·API (생성·수정·정렬)
- 대본 생성 provider 인터페이스 + 외부 키 없이 동작하는 mock provider
- 대본 편집기·스토리보드 화면
