# AI Excel 보고서 자동생성기 (ai-excel-report)

> 사용자가 Excel 또는 CSV 데이터를 업로드하면 AI가 의미를 분석하여 적절한 항목을 매핑하고, 회사에서 사용하는 보고서 양식의 Excel 파일을 자동 생성해주는 서비스입니다.

---

## 📁 프로젝트 구조

```
ai-excel-report/
├─ CLAUDE.md                      # AI 및 개발 원칙 가이드라인
├─ README.md                      # 프로젝트 소개 및 실행 가이드
├─ docker-compose.yml             # 로컬 개발용 PostgreSQL 16
├─ .env.example                   # 환경 변수 템플릿
├─ docs/                          # 설계 문서 원본 (8종)
│  ├─ idea.md                     # 아이디어 개요 및 문제 정의
│  ├─ requirements.md             # 비즈니스 규칙 및 제약조건
│  ├─ features.md                 # 기능 명세 및 인수 조건 (F-001 ~ F-012)
│  ├─ screens.md                  # 화면 설계 (S-01 ~ S-09)
│  ├─ database.md                 # DB 스키마 및 DDL
│  ├─ api.md                      # REST API 명세 (A-01 ~ A-23)
│  ├─ development-plan.md         # 개발 계획 및 마일스톤 (Slice 0 ~ Slice 6)
│  └─ test-plan.md                # 테스트 시나리오 및 검증 계획
├─ backend/                       # Spring Boot 3 (Java 21)
│  ├─ gradlew, gradlew.bat        # Gradle Wrapper
│  ├─ build.gradle, settings.gradle
│  └─ src/
│     ├─ main/java/com/aiexcel/report/
│     │  ├─ common/               # 공통 응답, 예외, 보안, 비동기 설정
│     │  ├─ auth/                 # 회원가입, 로그인, 세션 (F-012)
│     │  ├─ template/             # 보고서 템플릿 조회 (F-002)
│     │  ├─ job/                  # 작업 라이프사이클 및 단계 가드
│     │  ├─ file/                 # 파일 업로드 및 스토리지 (F-001, F-010)
│     │  ├─ analysis/             # 원본 데이터 및 컬럼 분석 (F-003)
│     │  ├─ mapping/              # 컬럼 매핑 규칙/추천 (F-004, F-005)
│     │  ├─ ai/                   # Claude API 연동
│     │  ├─ normalization/        # 날짜/금액 정규화 및 거래처 통합 (F-006)
│     │  ├─ report/               # 데이터 집계 및 엑셀 보고서 생성 (F-007, F-008)
│     │  ├─ history/              # 작업 이력 조회 및 삭제 (F-011)
│     │  └─ batch/                # 만료 파일/임시 작업 정리 배치
│     └─ main/resources/
│        ├─ application.yml       # 백엔드 환경 설정
│        └─ db/migration/         # Flyway DDL (V1__init.sql)
├─ frontend/                      # Vue 3 + TypeScript + Vite + Element Plus
│  └─ src/
│     ├─ pages/                   # 화면 컴포넌트 (S-01 ~ S-09)
│     ├─ components/              # 마법사 단계(WizardSteps) 등 공통 UI
│     ├─ stores/                  # Pinia 상태 관리 (job, auth)
│     ├─ router/                  # Vue Router 라우팅 가드
│     └─ api/                     # Axios API 클라이언트 및 에러 인터셉터
├─ templates/                     # 보고서 엑셀 양식 (.xlsx 시드)
└─ samples/                       # 로컬 검증용 샘플 데이터 (CSV/Excel)
```

---

## 🚀 빠른 시작 가이드 (Quick Start)

### 1. 환경 설정 (.env)
```bash
cp .env.example .env
```

### 2. 로컬 데이터베이스 실행 (PostgreSQL 16)
```bash
docker compose up -d
```

### 3. 백엔드 실행 (Spring Boot 3 + Java 21)
```bash
cd backend
./gradlew bootRun
```
> Flyway에 의해 `db/migration/V1__init.sql`이 자동으로 실행되어 DB 스키마와 기본 템플릿 시드 데이터가 생성됩니다.

### 4. 프론트엔드 실행 (Vue 3 + Vite)
```bash
cd frontend
npm install
npm run dev
```
브라우저에서 `http://localhost:5173`으로 접속합니다. (API 요청은 `http://localhost:8080`으로 자동 프록시됩니다)

---

## 🛡️ 핵심 개발 원칙
1. **AI 역할 제한**: AI는 컬럼 분석 및 매핑 추천에만 사용하며, 모든 수치 계산/합계/셀 입력은 코드가 직접 처리합니다.
2. **고객 데이터 보호**: AI API 호출 시에는 컬럼명과 최대 5개의 샘플 값만 독립적으로 전송하며 전체 행이나 조합을 전송하지 않습니다.
3. **숫자 계산 무결성**: 모든 금액 및 합계 계산은 `BigDecimal`을 사용합니다.
4. **테넌시 소유권 격리**: 모든 Job 및 File 조회는 반드시 세션의 `user_id` 조건을 포함하며, 타인 리소스 접근 시 404로 응답합니다.
