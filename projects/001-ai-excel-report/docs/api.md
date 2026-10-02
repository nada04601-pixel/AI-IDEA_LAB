# 001. AI Excel 보고서 자동생성기

# API 설계서

> 기준 문서: `features.md`, `screens.md`, `database.md`
> 형식: REST + JSON, 필드명은 `snake_case`
> `(가정)` 표시는 확인 전 임시 결정이다.

---

## 1. 설계 원칙

1. **마법사 단계 = API 호출 단위.** 화면 하나가 요청 하나 또는 두 개로 끝나도록 쪼갠다. (`screens.md`의 S-02 ~ S-07)
2. **`job`이 중심 리소스다.** 모든 작업 API는 `/jobs/{job_id}` 아래에 둔다.
3. **서버가 단계 순서를 강제한다.** 사전 조건이 안 맞으면 `409 JOB_STEP_INVALID`를 반환한다. 화면 흐름을 건너뛰어 호출해도 잘못된 결과가 나오지 않게 한다.
4. **오래 걸리는 작업(보고서 생성)만 비동기**로 한다. 분석, AI 매핑, 정규화는 최대 50,000행 기준 수 초 이내이므로 동기 처리한다. (가정)
5. **다른 사용자의 리소스는 `404`로 응답한다.** `403`을 쓰면 존재 여부가 노출된다. (BR-08)
6. **AI로 나가는 데이터는 서버가 직접 만든다.** 클라이언트가 AI에 보낼 내용을 지정하지 못하며, 서버는 컬럼명, 타입, 샘플 5개 이하만 구성한다. (BR-02)

---

## 2. 공통 규칙

### 2-1. 기본 사항

| 항목 | 내용 |
|---|---|
| Base URL | `/api/v1` |
| 인증 | 로그인 시 발급하는 **HttpOnly 세션 쿠키** (가정). `SameSite=Lax`, CSRF 토큰 헤더 `X-CSRF-Token` 사용 |
| 인증 예외 | `POST /auth/signup`, `POST /auth/login` 외 모든 API는 로그인 필요 |
| 요청 형식 | `application/json` (파일 업로드만 `multipart/form-data`) |
| 시간 | ISO 8601, UTC (예: `2026-10-02T06:30:00Z`). 화면에서 로컬 시간으로 변환 |
| ID | `users`, `jobs`, `files`는 UUID. `templates`, `fields`는 정수 |
| 페이지네이션 | `?page=1&page_size=20` (기본 20, 최대 100). 응답에 `page`, `page_size`, `total` 포함 |

### 2-2. 오류 응답 형식

모든 오류는 같은 구조로 응답한다. 화면은 `message`를 그대로 사용자에게 보여줄 수 있다.

```json
{
  "error": {
    "code": "MAPPING_INCOMPLETE",
    "message": "필수 항목 '매출금액'의 원본 컬럼을 선택해주세요.",
    "details": { "missing_required": ["amount"] }
  }
}
```

### 2-3. 공통 HTTP 상태 코드

| 코드 | 의미 |
|---|---|
| 200 / 201 / 202 / 204 | 성공 / 생성됨 / 비동기 접수됨 / 본문 없음 |
| 400 | 요청 형식 오류 |
| 401 | 로그인 필요 또는 세션 만료 |
| 404 | 리소스 없음 (타인의 리소스 포함) |
| 409 | 단계 순서 위반, 이미 생성 중 등 상태 충돌 |
| 410 | 보관 기간이 지나 삭제된 파일 |
| 413 | 파일 용량 초과 |
| 415 | 지원하지 않는 파일 형식 |
| 422 | 값 검증 실패 (필수 매핑 누락, 오류 처리 방식 미선택 등) |
| 429 | 호출 한도 초과 |
| 500 / 503 | 서버 오류 / 일시적 장애 |

---

## 3. API 목록

| ID | 메서드 | 경로 | 설명 | 기능 | 화면 |
|---|---|---|---|---|---|
| A-01 | POST | `/auth/signup` | 회원가입 | F-012 | S-01 |
| A-02 | POST | `/auth/login` | 로그인 | F-012 | S-01 |
| A-03 | POST | `/auth/logout` | 로그아웃 | F-012 | 헤더 |
| A-04 | GET | `/auth/me` | 현재 사용자 조회 | F-012 | 헤더 |
| A-05 | GET | `/templates` | 템플릿 목록 | F-002 | S-03 |
| A-06 | GET | `/templates/{id}` | 템플릿 상세 (필드 목록) | F-002 | S-03 |
| A-07 | GET | `/templates/{id}/preview` | 빈 양식 미리보기 | F-002 | S-03 |
| A-08 | POST | `/jobs` | 작업 생성 + 파일 업로드 | F-001 | S-02 |
| A-09 | PATCH | `/jobs/{job_id}/source` | 시트, 헤더 행 변경 | F-001, F-003 | S-02, S-04 |
| A-10 | PUT | `/jobs/{job_id}/template` | 템플릿 선택 | F-002 | S-03 |
| A-11 | POST | `/jobs/{job_id}/analysis` | 데이터 분석 실행 | F-003 | S-04 |
| A-12 | POST | `/jobs/{job_id}/mappings/suggest` | AI 매핑 추천 | F-004 | S-05 |
| A-13 | PUT | `/jobs/{job_id}/mappings` | 매핑 수정 저장 | F-005 | S-05 |
| A-14 | POST | `/jobs/{job_id}/mappings/confirm` | 매핑 확정 | F-005 | S-05 |
| A-15 | POST | `/jobs/{job_id}/normalization` | 정규화 실행 | F-006 | S-06 |
| A-16 | GET | `/jobs/{job_id}/errors` | 오류 행 목록 | F-006 | S-06, S-09 |
| A-17 | PUT | `/jobs/{job_id}/merge-rules` | 거래처 통합 적용 선택 | F-006 | S-06 |
| A-18 | POST | `/jobs/{job_id}/generate` | 집계 + 보고서 생성 시작 | F-007, F-008 | S-06 → S-07 |
| A-19 | GET | `/jobs/{job_id}` | 작업 상세 및 진행 상태 (폴링) | F-008, F-011 | S-07, S-09 |
| A-20 | GET | `/jobs/{job_id}/preview` | 결과 미리보기 | F-009 | S-07 |
| A-21 | GET | `/files/{file_id}/download` | 결과 파일 다운로드 | F-010 | S-07, S-08, S-09 |
| A-22 | GET | `/jobs` | 작업 이력 목록 | F-011 | S-08 |
| A-23 | DELETE | `/jobs/{job_id}` | 작업 삭제 (파일 포함) | F-011 | S-08, S-09 |

---

## 4. 단계 순서와 초기화 규칙

### 4-1. 사전 조건

| API | 호출하려면 필요한 상태 |
|---|---|
| A-10 템플릿 선택 | 작업이 존재하고 원본 파일이 있음 |
| A-11 분석 | 템플릿이 선택됨 |
| A-12 AI 매핑 | 분석이 완료됨 |
| A-13, A-14 매핑 | 매핑 추천이 완료됨 |
| A-15 정규화 | 매핑이 확정됨 |
| A-18 생성 | 정규화가 완료됨 |

조건이 맞지 않으면 `409 JOB_STEP_INVALID`를 반환한다.

### 4-2. `current_step`의 의미

`jobs.current_step`은 **사용자가 도달할 수 있는 가장 먼 단계**다. 클라이언트는 이 값보다 뒤 단계 화면으로 이동시키지 않는다.

| 이벤트 | `current_step` |
|---|---|
| A-08 작업 생성 (업로드 성공) | 2 |
| A-10 템플릿 선택 | 3 |
| A-11 분석 완료 | 4 |
| A-14 매핑 확정 | 5 |
| A-18 생성 성공 | 6 |

### 4-3. 앞 단계를 바꿨을 때 초기화

`screens.md`의 "앞 단계 입력을 바꾸면 이후 결과는 초기화" 규칙을 서버가 처리한다. 초기화될 때 응답에 `reset: [...]`을 담아 화면이 사용자에게 안내할 수 있게 한다.

| 변경 | 초기화되는 것 | `current_step` |
|---|---|---|
| A-09 시트 또는 헤더 행 변경 | 분석 결과, 매핑, 정규화 결과 | 3 |
| A-10 템플릿 변경 | 매핑, 정규화 결과 | 3 |
| A-13 확정 후 매핑 수정 | 매핑 확정 상태, 정규화 결과 | 4 |

---

## 5. 인증 API

### A-01 `POST /auth/signup`

```json
// 요청
{ "email": "user@example.com", "password": "********", "password_confirm": "********" }

// 201 응답
{ "user": { "id": "7b1e...", "email": "user@example.com" } }
```

- 비밀번호 규칙: 8자 이상 (가정)
- 오류: `EMAIL_ALREADY_EXISTS`(409), `INVALID_EMAIL`(422), `PASSWORD_MISMATCH`(422), `PASSWORD_TOO_SHORT`(422)

### A-02 `POST /auth/login`

```json
// 요청
{ "email": "user@example.com", "password": "********" }

// 200 응답 (세션 쿠키 설정)
{ "user": { "id": "7b1e...", "email": "user@example.com" } }
```

- 오류: `LOGIN_FAILED`(401) — 이메일과 비밀번호 중 어느 쪽이 틀렸는지 알려주지 않는다.
- 같은 계정 또는 IP에서 연속 실패 시 `429 TOO_MANY_ATTEMPTS` (5회/10분, 가정)

### A-03 `POST /auth/logout` → `204`
### A-04 `GET /auth/me` → `200 { "user": { ... } }` / 세션 없음 `401`

---

## 6. 템플릿 API

### A-05 `GET /templates`

```json
{
  "items": [
    {
      "id": 1,
      "name": "거래처별/상태별 매출 보고서",
      "description": "거래처별, 상태별 매출 합계를 집계합니다.",
      "fields": [
        { "id": 1, "field_key": "customer",  "field_name": "고객사",   "data_type": "text",   "is_required": true },
        { "id": 2, "field_key": "sale_date", "field_name": "거래일자", "data_type": "date",   "is_required": true },
        { "id": 3, "field_key": "amount",    "field_name": "매출금액", "data_type": "number", "is_required": true },
        { "id": 4, "field_key": "status",    "field_name": "처리상태", "data_type": "text",   "is_required": false },
        { "id": 5, "field_key": "dept",      "field_name": "부서",     "data_type": "text",   "is_required": false }
      ]
    }
  ]
}
```

- 활성(`is_active = true`) 템플릿만 반환한다. 필드 목록을 함께 내려서 S-03 카드에 바로 표시한다.
- `ai_hint`는 내부용이므로 응답에 포함하지 않는다.

### A-06 `GET /templates/{id}` → 위 항목 1건 (동일 구조)

### A-07 `GET /templates/{id}/preview` → 빈 양식을 표로 변환한 결과

```json
{ "sheets": [ { "name": "거래처별 매출", "rows": [["거래처", "매출 합계"]] } ] }
```

---

## 7. 작업 API (마법사)

### A-08 `POST /jobs` — 작업 생성 + 파일 업로드 (S-02)

`multipart/form-data`

| 필드 | 필수 | 설명 |
|---|---|---|
| `file` | O | `.xlsx` 또는 `.csv`, 최대 10MB |
| `template_id` | X | 지정하면 템플릿을 미리 선택한 상태로 생성 ("같은 매핑으로 새 작업" 진입 시) |

```json
// 201 응답
{
  "job": { "id": "c2f4...", "status": "draft", "current_step": 2 },
  "file": { "file_name": "9월_매출.xlsx", "size_bytes": 1258291 },
  "sheets": [ { "name": "Sheet1", "row_count": 1240 }, { "name": "Sheet2", "row_count": 30 } ],
  "selected_sheet": "Sheet1",
  "encoding": null
}
```

- CSV는 인코딩(UTF-8, CP949)을 자동 감지해 `encoding`에 담는다. Excel은 `null`.
- 시트가 하나뿐이면 `selected_sheet`가 자동 지정된다. 여러 개면 기본값은 첫 시트이고 A-09로 변경한다.
- 파일 검증 오류

| 코드 | HTTP | 메시지 (화면 표시용) |
|---|---|---|
| `FILE_TOO_LARGE` | 413 | 파일이 10MB를 넘습니다. 데이터를 나누어 올려주세요. |
| `UNSUPPORTED_FORMAT` | 415 | .xlsx 또는 .csv 파일만 올릴 수 있습니다. |
| `FILE_PASSWORD_PROTECTED` | 422 | 암호가 설정된 파일입니다. 암호를 해제한 뒤 올려주세요. |
| `FILE_CORRUPTED` | 422 | 파일을 읽을 수 없습니다. 파일이 손상되었는지 확인해주세요. |
| `FILE_EMPTY` | 422 | 데이터가 없는 파일입니다. |
| `ROW_LIMIT_EXCEEDED` | 422 | 데이터가 50,000행을 넘습니다. 나누어 올려주세요. |

- 확장자뿐 아니라 파일 내용(시그니처)도 검사해서 확장자만 바꾼 파일을 거른다.

### A-09 `PATCH /jobs/{job_id}/source` — 시트, 헤더 행 변경 (S-02, S-04)

```json
// 요청 (바꿀 항목만)
{ "sheet_name": "Sheet2", "header_row": 3 }

// 200 응답
{ "job": { "id": "c2f4...", "current_step": 3 }, "reset": ["analysis", "mappings", "normalization"] }
```

- 이미 진행한 결과가 있으면 4-3 규칙대로 초기화하고 `reset`에 알린다.
- 오류: `SHEET_NOT_FOUND`(422), `INVALID_HEADER_ROW`(422)

### A-10 `PUT /jobs/{job_id}/template` — 템플릿 선택 (S-03)

```json
// 요청
{ "template_id": 1 }

// 200 응답
{ "job": { "id": "c2f4...", "current_step": 3, "template_id": 1 }, "reset": [] }
```

- 오류: `TEMPLATE_NOT_FOUND`(404), `TEMPLATE_INACTIVE`(422)

### A-11 `POST /jobs/{job_id}/analysis` — 데이터 분석 (S-04)

요청 본문 없음. 헤더 행을 자동 감지하고 컬럼을 분석한다.

```json
// 200 응답
{
  "header_row": 1,
  "header_row_detected": true,
  "total_rows": 1240,
  "warnings": [
    { "code": "MERGED_CELLS", "message": "병합 셀이 3곳 발견되었습니다.", "locations": ["3행", "5행", "8행"] }
  ],
  "columns": [
    { "index": 0, "name": "거래처", "type": "text",   "empty_ratio": 0.0,  "distinct": 120, "samples": ["(주)대한상사", "대한상사", "ABC테크"] },
    { "index": 1, "name": "매출일", "type": "date",   "empty_ratio": 0.0,  "distinct": 30,  "samples": ["2026-09-01", "2026.09.02", "2026/09/03"] },
    { "index": 2, "name": "금액",   "type": "number", "empty_ratio": 0.02, "distinct": 800, "samples": ["1000000", "1360000", "850000"] }
  ]
}
```

- 결과는 `jobs.column_profile`에 저장한다.
- 경고 코드: `MERGED_CELLS`, `EMPTY_ROWS`, `DUPLICATE_COLUMN_NAME`, `MISSING_COLUMN_NAME`
- 헤더 행을 못 찾으면 `header_row_detected: false`로 응답하고 사용자가 A-09로 지정한다.

### A-12 `POST /jobs/{job_id}/mappings/suggest` — AI 매핑 추천 (S-05)

요청 본문 없음. 서버 처리 순서는 다음과 같다.

1. 같은 사용자, 같은 템플릿의 **최근 성공 작업 매핑**이 있고 그 컬럼명이 새 파일에도 있으면 `history`로 채운다.
2. 나머지 필드는 AI를 호출해서 추천받는다. (내부 규격은 8장)
3. AI 호출이 실패하면 이름 유사도 기반 **규칙 매핑**으로 대체한다.

```json
// 200 응답
{
  "source": "ai",
  "fallback_used": false,
  "loaded_from_history": false,
  "mappings": [
    {
      "field_id": 1, "field_key": "customer", "field_name": "고객사", "is_required": true,
      "source_column": "거래처", "source_column_index": 0,
      "confidence": "high", "origin": "ai",
      "reason": "컬럼명과 값이 거래 상대 회사명 형식과 일치",
      "samples": ["(주)대한상사", "대한상사", "ABC테크"]
    },
    {
      "field_id": 5, "field_key": "dept", "field_name": "부서", "is_required": false,
      "source_column": null, "source_column_index": null,
      "confidence": "none", "origin": "ai",
      "reason": null, "samples": []
    }
  ],
  "unused_columns": ["담당자", "상품"]
}
```

- `source`는 `ai`, `rule`, `history` 중 하나이며, 화면 상단 배지("AI 추천 / 규칙 기반 추천")에 쓴다.
- AI 호출이 실패해도 **오류가 아니라 정상 응답(`fallback_used: true`)** 으로 처리한다.
- 같은 작업에서 다시 호출하면 AI를 새로 호출해 매핑을 덮어쓴다. (화면의 "AI 추천으로 다시 받기") 호출마다 `ai_call_logs`에 기록한다.
- 한도: 사용자당 시간당 30회 (가정, 비용 관리)

### A-13 `PUT /jobs/{job_id}/mappings` — 매핑 수정 저장 (S-05)

```json
// 요청 (field_id별로 선택한 원본 컬럼 위치, null = 선택 안 함)
{
  "mappings": [
    { "field_id": 3, "source_column_index": 2 },
    { "field_id": 5, "source_column_index": 4 }
  ]
}

// 200 응답: A-12와 같은 mappings 구조 + 검증 결과
{
  "mappings": [ ... ],
  "validation": { "missing_required": [], "duplicates": [] }
}
```

- 사용자가 바꾼 항목은 `origin = 'user'`로 저장한다. 사용자가 원래 추천과 같은 값을 선택하면 원래 `origin`을 유지한다.
- 이 API는 **검증 결과를 알려줄 뿐 오류로 거절하지 않는다.** 필수 누락과 중복은 화면에서 경고로 보여주고, 확정(A-14)에서 막는다.
- 이미 확정된 매핑을 수정하면 `is_confirmed`가 해제되고 정규화 결과가 초기화된다. (4-3)

### A-14 `POST /jobs/{job_id}/mappings/confirm` — 매핑 확정 (S-05)

```json
// 200 응답
{ "job": { "id": "c2f4...", "current_step": 5 } }

// 422 응답
{ "error": { "code": "MAPPING_INCOMPLETE", "message": "필수 항목 '매출금액'의 원본 컬럼을 선택해주세요.",
             "details": { "missing_required": ["amount"], "duplicates": [] } } }
```

- 오류: `MAPPING_INCOMPLETE`(필수 누락), `MAPPING_DUPLICATE`(같은 컬럼 중복) — 둘 다 422 (BR-04)

### A-15 `POST /jobs/{job_id}/normalization` — 정규화 실행 (S-06)

요청 본문 없음.

```json
// 200 응답
{
  "summary": { "total_rows": 1240, "converted": 1230, "errors": 10, "merge_suggestions": 4 },
  "high_error_ratio": false,
  "merge_rules": [
    {
      "id": 11, "canonical_name": "대한상사", "is_applied": false,
      "variants": [ { "name": "(주)대한상사", "rows": 3 }, { "name": "대한상사", "rows": 2 } ]
    }
  ],
  "samples": [
    { "field": "sale_date", "before": "2026.09.02", "after": "2026-09-02" },
    { "field": "amount",    "before": "1,360,000원", "after": 1360000 }
  ],
  "errors_preview": [
    { "row_number": 15, "column_name": "매출일", "raw_value": "2026-13-45", "reason_code": "INVALID_DATE", "reason_message": "날짜로 해석할 수 없음" }
  ]
}
```

- 정규화 결과는 `normalized` 파일로 저장하고, 오류 행은 `job_error_rows`에, 통합 제안은 `job_merge_rules`에 저장한다.
- 거래처 통합 제안은 **항상 `is_applied: false`로 시작**한다. (BR-06)
- `high_error_ratio`: 오류 행이 전체의 30% 이상(가정)이면 `true`. 화면이 경고를 표시한다.
- 오류 행이 1,000건을 넘으면 상위 1,000건만 저장하고 `summary.errors`에는 실제 건수를 담는다. (`database.md`)
- 같은 작업에서 다시 호출하면 이전 정규화 결과를 지우고 다시 만든다.

### A-16 `GET /jobs/{job_id}/errors?page=1&page_size=50` — 오류 행 목록

```json
{
  "items": [
    { "row_number": 15, "column_name": "매출일", "raw_value": "2026-13-45", "reason_code": "INVALID_DATE", "reason_message": "날짜로 해석할 수 없음" },
    { "row_number": 88, "column_name": "금액",   "raw_value": "협의",       "reason_code": "INVALID_NUMBER", "reason_message": "숫자가 아님" }
  ],
  "page": 1, "page_size": 50, "total": 10
}
```

- 이력 상세(S-09)의 "제외된 오류 행"에서도 같은 API를 사용한다.
- 파일 만료로 오류 행이 삭제된 경우 `total: 0`과 함께 `"purged": true`를 반환한다.

### A-17 `PUT /jobs/{job_id}/merge-rules` — 거래처 통합 선택 (S-06)

```json
// 요청 (적용할 규칙 ID 전체 목록. 목록에 없는 규칙은 해제된다)
{ "applied_rule_ids": [11, 12] }

// 200 응답
{ "applied": 2, "total": 4 }
```

- 통합은 보고서 생성 시점(A-18)에 `normalized` 파일에 반영한다.

### A-18 `POST /jobs/{job_id}/generate` — 보고서 생성 시작 (S-06 → S-07)

```json
// 요청
{ "error_policy": "exclude" }

// 202 응답
{ "job": { "id": "c2f4...", "status": "generating" } }
```

- `error_policy`: `exclude`(오류 행 제외하고 진행). 오류 행이 1건 이상인데 값이 없으면 `422 ERROR_POLICY_REQUIRED` (BR-09)
- 서버 처리 순서: 통합 규칙 적용 → 집계 → 합계 검증 → 템플릿에 입력 → 결과 파일 저장
- 합계 검증이 실패하면 보고서를 만들지 않고 `status = failed`, `error_code = TOTAL_MISMATCH`로 기록한다. (공통 원칙, `requirements.md` 비기능)
- 이미 생성 중이면 `409 JOB_ALREADY_GENERATING`, 이미 성공한 작업이면 `409 JOB_ALREADY_COMPLETED`

### A-19 `GET /jobs/{job_id}` — 작업 상세 / 진행 상태 (S-07, S-09)

생성 중에는 **1~2초 간격으로 폴링**한다. (가정, 이후 SSE로 교체 가능)

```json
// 생성 중
{
  "id": "c2f4...", "status": "generating", "current_step": 5,
  "progress": { "stage": "aggregating", "label": "집계 중" }
}

// 성공 (S-07, S-09)
{
  "id": "c2f4...", "status": "succeeded", "current_step": 6,
  "created_at": "2026-10-02T06:30:00Z", "completed_at": "2026-10-02T06:30:21Z",
  "source": { "file_name": "9월_매출.xlsx", "sheet_name": "Sheet1", "header_row": 1, "total_rows": 1240 },
  "template": { "id": 1, "name": "거래처별/상태별 매출 보고서" },
  "result": {
    "processed_rows": 1230, "excluded_rows": 10,
    "summary": { "total_amount": 3210000, "validation": { "passed": true } },
    "file": { "id": "9d3a...", "file_name": "거래처별_상태별_매출_20261002_1530.xlsx",
              "size_bytes": 48210, "expires_at": "2026-11-01T06:30:21Z", "is_expired": false }
  },
  "mappings": [
    { "field_name": "고객사", "source_column": "거래처", "origin": "ai" },
    { "field_name": "매출금액", "source_column": "금액", "origin": "user" }
  ],
  "error": null
}

// 실패
{
  "id": "c2f4...", "status": "failed",
  "error": { "code": "TOTAL_MISMATCH", "message": "집계 결과 검증에 실패해 보고서를 만들지 않았습니다." },
  "result": null
}
```

- `progress.stage`: `merging` → `aggregating` → `writing` → `validating`
- `mappings`는 S-09 상세 화면용이다. 진행 중인 작업에서는 생략한다.

### A-20 `GET /jobs/{job_id}/preview?sheet=거래처별 매출&limit=100` — 결과 미리보기 (S-07)

```json
{
  "sheets": ["거래처별 매출", "상태별 매출"],
  "sheet": "거래처별 매출",
  "rows": [
    ["거래처", "매출 합계"],
    ["대한상사", 2360000],
    ["ABC테크", 850000],
    ["합계", 3210000]
  ],
  "truncated": false,
  "notice": "서식은 실제 파일과 다를 수 있습니다. 전체 내용은 다운로드해서 확인하세요."
}
```

- `sheet` 생략 시 첫 시트. `limit` 기본 100, 최대 100.
- 미리보기 변환에 실패해도 다운로드는 가능해야 하므로, 실패는 `500`이 아니라 `503 PREVIEW_UNAVAILABLE`로 응답하고 화면은 다운로드 버튼을 유지한다.
- 파일 만료 시 `410 FILE_EXPIRED`

---

## 8. 파일 / 이력 API

### A-21 `GET /files/{file_id}/download` — 다운로드 (S-07, S-08, S-09)

- 응답: 파일 스트림, `Content-Disposition: attachment; filename*=UTF-8''...` (한글 파일명 인코딩)
- `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- 호출 시 `file_downloads`에 기록한다.
- 오류: `404`(없음 또는 타인의 파일), `410 FILE_EXPIRED`(보관 기간 경과 또는 삭제됨)
- 다운로드 가능한 파일은 `kind = 'result'`만이다. 원본과 중간 파일은 내려주지 않는다.

### A-22 `GET /jobs?page=1&page_size=20` — 작업 이력 목록 (S-08)

```json
{
  "items": [
    {
      "id": "c2f4...", "created_at": "2026-10-02T06:30:00Z",
      "original_file_name": "9월_매출.xlsx", "template_name": "거래처별/상태별 매출 보고서",
      "processed_rows": 1230, "excluded_rows": 10, "status": "succeeded",
      "result_file": { "id": "9d3a...", "is_expired": false }
    },
    {
      "id": "a8b1...", "created_at": "2026-09-18T02:02:00Z",
      "original_file_name": "9월2주.csv", "template_name": "거래처별/상태별 매출 보고서",
      "processed_rows": null, "excluded_rows": null, "status": "failed",
      "result_file": null
    }
  ],
  "page": 1, "page_size": 20, "total": 37
}
```

- `status`가 `succeeded`, `failed`인 작업만 반환한다. (`draft`, `generating`은 제외)
- 최신순 고정. 검색, 필터는 MVP 제외.

### A-23 `DELETE /jobs/{job_id}` → `204`

- 저장소 파일을 먼저 삭제하고 `jobs` 행을 삭제한다. (나머지는 DB cascade)
- 생성 중(`generating`)인 작업은 `409 JOB_ALREADY_GENERATING`
- 진행 중(`draft`) 작업을 사용자가 마법사에서 나가며 버리는 경우에도 같은 API를 사용할 수 있다.

---

## 9. AI 매핑 내부 규격 (서버 ↔ LLM)

공개 API는 아니지만 BR-01, BR-02를 지키는 핵심이라 문서에 남긴다.

### 9-1. 서버가 AI에 보내는 데이터 (이 항목만 허용)

```json
{
  "task": "column_mapping",
  "target_fields": [
    { "field_key": "customer", "field_name": "고객사", "data_type": "text", "required": true, "hint": "거래 상대 회사명" },
    { "field_key": "amount", "field_name": "매출금액", "data_type": "number", "required": true, "hint": "거래 금액" }
  ],
  "source_columns": [
    { "index": 0, "name": "거래처", "type": "text", "samples": ["(주)대한상사", "ABC테크"] },
    { "index": 2, "name": "금액", "type": "number", "samples": ["1000000", "850000"] }
  ]
}
```

- **샘플은 컬럼당 최대 5개**, 한 값은 최대 50자로 자른다. 전체 행, 다른 컬럼과의 행 단위 조합(어느 값이 같은 행인지)은 보내지 않는다.
- 샘플 값을 컬럼마다 **독립적으로 추출**해서 한 행의 값이 통째로 노출되지 않게 한다.

### 9-2. AI가 반환해야 하는 형식 (JSON only)

```json
{
  "mappings": [
    { "field_key": "customer", "source_index": 0, "confidence": "high", "reason": "거래 상대 회사명 형식과 일치" },
    { "field_key": "dept", "source_index": null, "confidence": "none", "reason": null }
  ]
}
```

### 9-3. 서버 검증과 대체

- JSON 파싱 실패, 존재하지 않는 `source_index`, 같은 컬럼 중복 지정, 필수 키 누락 → `invalid_response`로 기록
- 타임아웃(10초, 가정) 또는 호출 실패 → `timeout` / `failed`로 기록
- 위 경우 모두 **규칙 기반 매핑**(컬럼명 유사도 + 타입 일치)으로 대체하고 `fallback_used = true`
- 확신이 낮으면 억지로 채우지 않고 `none`으로 둔다.

---

## 10. 오류 코드 총정리

| 코드 | HTTP | 발생 API | 설명 |
|---|---|---|---|
| `UNAUTHORIZED` | 401 | 공통 | 로그인 필요, 세션 만료 |
| `LOGIN_FAILED` | 401 | A-02 | 이메일 또는 비밀번호 불일치 |
| `TOO_MANY_ATTEMPTS` | 429 | A-02 | 로그인 시도 초과 |
| `EMAIL_ALREADY_EXISTS` | 409 | A-01 | 중복 이메일 |
| `INVALID_EMAIL` / `PASSWORD_MISMATCH` / `PASSWORD_TOO_SHORT` | 422 | A-01 | 가입 값 검증 |
| `FILE_TOO_LARGE` | 413 | A-08 | 10MB 초과 |
| `UNSUPPORTED_FORMAT` | 415 | A-08 | 지원하지 않는 형식 |
| `FILE_PASSWORD_PROTECTED` / `FILE_CORRUPTED` / `FILE_EMPTY` / `ROW_LIMIT_EXCEEDED` | 422 | A-08 | 파일 검증 |
| `SHEET_NOT_FOUND` / `INVALID_HEADER_ROW` | 422 | A-09 | 시트, 헤더 행 오류 |
| `TEMPLATE_NOT_FOUND` | 404 | A-06, A-10 | 템플릿 없음 |
| `TEMPLATE_INACTIVE` | 422 | A-10 | 비활성 템플릿 |
| `JOB_STEP_INVALID` | 409 | A-10 ~ A-18 | 단계 순서 위반 |
| `MAPPING_INCOMPLETE` | 422 | A-14 | 필수 항목 미매핑 |
| `MAPPING_DUPLICATE` | 422 | A-14 | 같은 컬럼 중복 매핑 |
| `ERROR_POLICY_REQUIRED` | 422 | A-18 | 오류 행 처리 방식 미선택 |
| `JOB_ALREADY_GENERATING` | 409 | A-18, A-23 | 생성 중 |
| `JOB_ALREADY_COMPLETED` | 409 | A-18 | 이미 성공한 작업 |
| `TOTAL_MISMATCH` | (작업 `failed`) | A-19 | 합계 검증 실패 |
| `TEMPLATE_BROKEN` | (작업 `failed`) | A-19 | 템플릿 파일 또는 셀 정의 오류 |
| `FILE_EXPIRED` | 410 | A-20, A-21 | 보관 기간 경과 |
| `PREVIEW_UNAVAILABLE` | 503 | A-20 | 미리보기 변환 실패 |
| `RATE_LIMITED` | 429 | A-08, A-12 | 호출 한도 초과 |

---

## 11. 보안 및 운영 규칙

| 항목 | 규칙 |
|---|---|
| 소유권 검증 | 모든 `job`, `file` 조회에 `user_id = 세션 사용자` 조건을 강제한다. 위반은 `404` |
| 파일 접근 | 저장소 파일을 URL로 직접 노출하지 않고 A-21을 통해서만 내려준다. |
| 업로드 | 확장자와 시그니처를 모두 검사하고, 저장 경로는 서버가 생성한 UUID로만 구성한다. (사용자 파일명을 경로에 쓰지 않는다) |
| Excel 파싱 | 매크로(.xlsm)와 외부 링크는 읽지 않는다. 수식은 계산된 값만 사용한다. (가정) |
| 호출 한도 | 업로드 시간당 30건, AI 추천 시간당 30회 (가정). 초과 시 `429` + `Retry-After` |
| 로그 | 요청 로그에 파일 내용, 샘플 값, 비밀번호를 남기지 않는다. |
| CORS | 같은 출처(동일 도메인) 배포를 기본으로 하고 별도 허용 출처는 두지 않는다. |

---

## 12. 확인이 필요한 미결 사항

| # | 질문 | 영향 | 임시 가정 |
|---|---|---|---|
| 1 | 인증 방식: 세션 쿠키 vs JWT | A-01 ~ A-04, 전체 | 세션 쿠키 (웹 단일 도메인) |
| 2 | 분석, AI 매핑, 정규화를 동기로 처리해도 되는가 (50,000행 기준) | A-11, A-12, A-15 | 동기. 실측에서 10초를 넘으면 비동기 전환 |
| 3 | 생성 진행 상태를 폴링으로 할 것인가 SSE로 할 것인가 | A-19 | 폴링 (1~2초) |
| 4 | "같은 매핑으로 새 작업"이 **그 이력 작업의 매핑**을 정확히 쓰는가, **최근 성공 작업의 매핑**을 쓰는가 | A-08, A-12 | 최근 성공 작업. 정확히 쓰려면 `jobs`에 `based_on_job_id` 컬럼 추가 필요 |
| 5 | 업로드를 서버 경유(`multipart`)로 할 것인가, 저장소 직접 업로드(서명 URL)로 할 것인가 | A-08 | 서버 경유 (10MB 제한이므로 충분) |
| 6 | 호출 한도 수치 | A-08, A-12 | 시간당 30회 |
| 7 | API 버전 관리 정책 | 전체 | `/api/v1` 고정 |

---

## 13. 다음 단계

1. `development-plan.md`: 기술 스택(백엔드, 프론트, 저장소, Excel 라이브러리)과 개발 순서를 정한다. 이 문서의 API 중 **A-08 → A-11 → A-15 → A-18**(업로드 → 분석 → 정규화 → 생성)이 AI 없이도 동작하는 핵심 뼈대이므로 가장 먼저 구현하는 순서를 추천한다.
2. `test-plan.md`: `features.md`의 인수 조건과 이 문서의 오류 코드를 테스트 케이스로 옮긴다.
3. 실제 보고서 양식이 확보되면 A-05 응답의 필드 목록과 `aggregation_rules` 예시를 실제 값으로 교체한다.
