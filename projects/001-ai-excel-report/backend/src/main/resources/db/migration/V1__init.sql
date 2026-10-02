-- =========================================================
-- AI Excel 보고서 자동생성기 초기 스키마 (V1__init.sql)
-- 기준 문서: docs/database.md
-- =========================================================

-- UUID 확장을 위해 pgcrypto 확인 (필요시)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =========================================================
-- 1. 사용자 (users)
-- =========================================================
CREATE TABLE users (
    id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    email          VARCHAR(255) NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_login_at  TIMESTAMPTZ
);
CREATE UNIQUE INDEX uq_users_email ON users (lower(email));


-- =========================================================
-- 2. 보고서 템플릿 (report_templates)
-- =========================================================
CREATE TABLE report_templates (
    id                 BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name               VARCHAR(100) NOT NULL,
    description        TEXT,
    template_file_path VARCHAR(500) NOT NULL,
    version            INT          NOT NULL DEFAULT 1,
    aggregation_rules  JSONB        NOT NULL,
    cell_map           JSONB        NOT NULL,
    is_active          BOOLEAN      NOT NULL DEFAULT true,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- =========================================================
-- 3. 템플릿 필드 (template_fields)
-- =========================================================
CREATE TABLE template_fields (
    id           BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    template_id  BIGINT       NOT NULL REFERENCES report_templates(id) ON DELETE CASCADE,
    field_key    VARCHAR(50)  NOT NULL,
    field_name   VARCHAR(100) NOT NULL,
    data_type    VARCHAR(10)  NOT NULL CHECK (data_type IN ('text', 'number', 'date')),
    is_required  BOOLEAN      NOT NULL DEFAULT false,
    sort_order   INT          NOT NULL DEFAULT 0,
    ai_hint      TEXT,
    UNIQUE (template_id, field_key)
);


-- =========================================================
-- 4. 작업 (jobs)
-- =========================================================
CREATE TABLE jobs (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    template_id         BIGINT       REFERENCES report_templates(id),
    template_version    INT,
    status              VARCHAR(12)  NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'generating', 'succeeded', 'failed')),
    current_step        SMALLINT     NOT NULL DEFAULT 1 CHECK (current_step BETWEEN 1 AND 6),

    original_file_name  VARCHAR(255),
    sheet_name          VARCHAR(100),
    header_row          INT          NOT NULL DEFAULT 1,
    total_rows          INT,
    processed_rows      INT,
    excluded_rows       INT,

    column_profile      JSONB,
    summary             JSONB,
    error_code          VARCHAR(50),
    error_message       TEXT,

    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ
);
CREATE INDEX idx_jobs_user_created ON jobs (user_id, created_at DESC);
CREATE INDEX idx_jobs_draft_cleanup ON jobs (updated_at) WHERE status = 'draft';


-- =========================================================
-- 5. 파일 (files)
-- =========================================================
CREATE TABLE files (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id        UUID         NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    kind          VARCHAR(12)  NOT NULL CHECK (kind IN ('source', 'normalized', 'result')),
    file_name     VARCHAR(255) NOT NULL,
    storage_path  VARCHAR(500) NOT NULL,
    size_bytes    BIGINT       NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ  NOT NULL,
    deleted_at    TIMESTAMPTZ
);
CREATE INDEX idx_files_job ON files (job_id);
CREATE INDEX idx_files_expiry ON files (expires_at) WHERE deleted_at IS NULL;


-- =========================================================
-- 6. 컬럼 매핑 (job_mappings)
-- =========================================================
CREATE TABLE job_mappings (
    id                   BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id               UUID         NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    field_id             BIGINT       NOT NULL REFERENCES template_fields(id),
    source_column_name   VARCHAR(255),
    source_column_index  INT,
    ai_suggested_column  VARCHAR(255),
    confidence           VARCHAR(6)   NOT NULL DEFAULT 'none'
                         CHECK (confidence IN ('high', 'medium', 'low', 'none')),
    reason               TEXT,
    origin               VARCHAR(7)   NOT NULL DEFAULT 'ai'
                         CHECK (origin IN ('ai', 'rule', 'history', 'user')),
    is_confirmed         BOOLEAN      NOT NULL DEFAULT false,
    UNIQUE (job_id, field_id)
);
CREATE UNIQUE INDEX uq_job_mappings_source
    ON job_mappings (job_id, source_column_index)
    WHERE source_column_index IS NOT NULL;


-- =========================================================
-- 7. 거래처명 통합 제안 (job_merge_rules)
-- =========================================================
CREATE TABLE job_merge_rules (
    id              BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id          UUID         NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    canonical_name  VARCHAR(255) NOT NULL,
    variants        JSONB        NOT NULL,
    is_applied      BOOLEAN      NOT NULL DEFAULT false
);
CREATE INDEX idx_merge_rules_job ON job_merge_rules (job_id);


-- =========================================================
-- 8. 정규화 오류 행 (job_error_rows)
-- =========================================================
CREATE TABLE job_error_rows (
    id             BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id         UUID         NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    row_number     INT          NOT NULL,
    column_name    VARCHAR(255) NOT NULL,
    raw_value      VARCHAR(500),
    reason_code    VARCHAR(30)  NOT NULL,
    reason_message VARCHAR(255) NOT NULL
);
CREATE INDEX idx_error_rows_job ON job_error_rows (job_id, row_number);


-- =========================================================
-- 9. AI 호출 기록 (ai_call_logs)
-- =========================================================
CREATE TABLE ai_call_logs (
    id                  BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id              UUID         REFERENCES jobs(id) ON DELETE SET NULL,
    user_id             UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose             VARCHAR(30)  NOT NULL DEFAULT 'column_mapping',
    model               VARCHAR(50),
    status              VARCHAR(20)  NOT NULL
                        CHECK (status IN ('success', 'failed', 'timeout', 'invalid_response')),
    fallback_used       BOOLEAN      NOT NULL DEFAULT false,
    sent_column_count   INT,
    sent_sample_count   INT,
    input_tokens        INT,
    output_tokens       INT,
    latency_ms          INT,
    error_message       TEXT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_ai_logs_created ON ai_call_logs (created_at);


-- =========================================================
-- 10. 다운로드 기록 (file_downloads)
-- =========================================================
CREATE TABLE file_downloads (
    id             BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    file_id        UUID         NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    user_id        UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    downloaded_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_downloads_file ON file_downloads (file_id);


-- =========================================================
-- 초기 시드 데이터 (1종: 매출 요약 보고서)
-- =========================================================
INSERT INTO report_templates (name, description, template_file_path, version, aggregation_rules, cell_map, is_active)
VALUES (
    '매출 요약 보고서',
    '거래처별 매출 및 상태별 매출을 집계하여 요약 표를 생성하는 보고서 양식입니다.',
    'templates/sales_summary_template.xlsx',
    1,
    '{
      "outputs": [
        {
          "name": "거래처별 매출",
          "sheet": "거래처별 매출",
          "group_by": "customer",
          "metrics": [{ "field": "amount", "op": "sum", "label": "매출 합계" }]
        },
        {
          "name": "상태별 매출",
          "sheet": "상태별 매출",
          "group_by": "status",
          "metrics": [
            { "field": "amount", "op": "count", "label": "건수" },
            { "field": "amount", "op": "sum", "label": "매출 합계" }
          ]
        }
      ],
      "total_check": { "field": "amount", "op": "sum" }
    }'::jsonb,
    '{
      "sheets": [
        {
          "sheet": "거래처별 매출",
          "output": "거래처별 매출",
          "start_cell": "A5",
          "columns": ["group", "매출 합계"],
          "expand_rows": true,
          "total_row": true
        },
        {
          "sheet": "상태별 매출",
          "output": "상태별 매출",
          "start_cell": "A5",
          "columns": ["group", "건수", "매출 합계"],
          "expand_rows": true,
          "total_row": true
        }
      ]
    }'::jsonb,
    true
);

-- 시드 템플릿 필드 (id=1 템플릿에 연결)
INSERT INTO template_fields (template_id, field_key, field_name, data_type, is_required, sort_order, ai_hint)
VALUES 
    (1, 'customer', '거래처명', 'text', true, 1, '거래 상대 회사명, 고객사, 바이어, 거래처'),
    (1, 'sale_date', '매출일자', 'date', true, 2, '매출 발생 일자, 거래일, 판매일'),
    (1, 'amount', '매출금액', 'number', true, 3, '매출 금액, 결제 금액, 공급가액, 판매금액'),
    (1, 'status', '진행상태', 'text', false, 4, '거래 상태, 결제 상태, 진행 구분 (예: 완료, 대기)');
