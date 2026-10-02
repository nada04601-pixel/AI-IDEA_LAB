# AI Excel 보고서 자동생성기 (ai-excel-report)

## 프로젝트 개요
Excel/CSV 원본 데이터를 업로드하면 지정된 Excel 양식(템플릿)의 필요 컬럼과 자동 매핑하고, 정규화 및 집계를 거쳐 완성된 보고서 Excel 파일을 생성하는 서비스.
모든 설계 기준 문서는 `docs/` 디렉터리에 위치하며, 구현 전에 반드시 해당 문서를 먼저 읽는다.

## 문서 위치 및 참조 가이드
- 기능 상세 및 인수 조건: `docs/features.md` (F-001 ~ F-012)
- 화면 설계 및 UI 흐름: `docs/screens.md` (S-01 ~ S-09)
- DB 스키마 및 DDL: `docs/database.md`
- REST API 명세: `docs/api.md` (A-01 ~ A-23)
- 비즈니스 규칙 및 제약사항: `docs/requirements.md` (BR-01 ~ BR-09)
- 개발 계획 및 아키텍처: `docs/development-plan.md`
- 테스트 시나리오: `docs/test-plan.md`

## 기술 스택
- **Language**: Java 21 LTS
- **Backend**: Spring Boot 3.3.x, Spring Security (세션 + CSRF), MyBatis, Flyway
- **Excel/CSV**: Apache POI (XSSF + SAX Event Streaming), Apache Commons CSV
- **Database**: PostgreSQL 16 (JSONB, UUID)
- **Frontend**: Vue 3 (Composition API), Vite, TypeScript, Pinia, Vue Router, Element Plus
- **Container**: Docker & Docker Compose (로컬 PostgreSQL 실행)

## 반드시 지켜야 할 핵심 원칙 (Core Rules)
1. **AI(LLM)의 역할 한정**: AI는 컬럼 의미 분석 및 매핑 추천(`mapping/`, `ai/`)에만 사용한다. 합계, 집계, 날짜 변환, 셀 입력은 반드시 코드가 처리한다.
2. **고객 데이터 보호 (데이터 최소 전송)**: AI 호출 시 원본 전체 데이터나 단일 행의 조합을 절대 보내지 않는다. 오직 컬럼명, 타입, 컬럼당 샘플 값(최대 5개)만 전달한다.
3. **숫자/금액 계산 무결성**: 모든 금액 계산 및 합계는 `BigDecimal`을 사용한다. `double` 및 `float`의 사용은 엄격히 금지한다.
4. **엄격한 테넌시/소유권 격리**: 모든 작업(`jobs`) 및 파일(`files`) 조회/수정/삭제 쿼리에는 반드시 `user_id` 조건을 포함한다. 타인의 리소스 요청 시에는 보안을 위해 `404 Not Found`로 응답한다.
5. **표준화된 에러 처리**: 모든 에러 응답은 `docs/api.md`의 표준 에러 응답 형식 및 `ErrorCode`를 준수한다.
6. **거래처 정규화 원칙**: 거래처명 정규화 및 통합은 시스템이 '제안'만 생성하며, 사용자의 명시적 확인/선택 없이 자동으로 원본에 적용하지 않는다 (BR-06).
7. **문서 기반 개발 및 범위 준수**: `features.md`에 명시된 기능 범위(MVP)를 벗어나는 임의의 기능 확장을 하지 않는다. 의문 사항은 먼저 사용자에게 질문한다.
8. **테스트 격리 및 AI Fixture**: 자동화 테스트에서는 실제 AI API를 호출하지 않고 Mock 또는 Fixture 데이터를 사용한다.
9. **보안 및 민감정보 보호**: 파일 내용, 고객 원본 샘플 값, 비밀번호 등은 로그에 남기지 않는다. API 키와 DB 비밀번호는 환경 변수로만 주입한다.

## 작업 및 개발 방식
- **Vertical Slice 개발**: 기능 묶음 단위로 백엔드와 프론트엔드를 함께 구현하고, 테스트를 통과시킨다.
- **TDD / 테스트 선행 검증**: 정규화, 집계, 합계 검증 로직은 반드시 단위 테스트를 먼저 작성하여 증명한다.
- **DB 스키마 관리**: 모든 DB 변경은 `backend/src/main/resources/db/migration/`의 Flyway 스키마 버전 관리 파일(V*__*.sql)로만 수행하며, `docs/database.md`도 동기화한다.
- **커밋 단위**: 기능 1개 단위로 커밋하며 커밋 메시지는 `[F-xxx] 기능명 구현` 형식을 권장한다.
