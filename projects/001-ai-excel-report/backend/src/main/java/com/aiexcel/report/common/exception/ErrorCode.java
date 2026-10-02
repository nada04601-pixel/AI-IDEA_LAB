package com.aiexcel.report.common.exception;

import org.springframework.http.HttpStatus;

public enum ErrorCode {

    // Common & Auth
    UNAUTHORIZED(HttpStatus.UNAUTHORIZED, "로그인이 필요하거나 세션이 만료되었습니다."),
    LOGIN_FAILED(HttpStatus.UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다."),
    TOO_MANY_ATTEMPTS(HttpStatus.TOO_MANY_REQUESTS, "로그인 시도 횟수를 초과했습니다. 잠시 후 다시 시도해주세요."),
    EMAIL_ALREADY_EXISTS(HttpStatus.CONFLICT, "이미 사용 중인 이메일입니다."),
    INVALID_EMAIL(HttpStatus.UNPROCESSABLE_ENTITY, "유효한 이메일 형식이 아닙니다."),
    PASSWORD_MISMATCH(HttpStatus.UNPROCESSABLE_ENTITY, "비밀번호 확인이 일치하지 않습니다."),
    PASSWORD_TOO_SHORT(HttpStatus.UNPROCESSABLE_ENTITY, "비밀번호는 최소 8자 이상이어야 합니다."),

    // File
    FILE_TOO_LARGE(HttpStatus.PAYLOAD_TOO_LARGE, "파일 크기는 최대 10MB까지 가능합니다."),
    UNSUPPORTED_FORMAT(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "지원하지 않는 파일 형식입니다. .xlsx, .xls, .csv 파일만 가능합니다."),
    FILE_PASSWORD_PROTECTED(HttpStatus.UNPROCESSABLE_ENTITY, "암호가 설정된 파일은 지원하지 않습니다."),
    FILE_CORRUPTED(HttpStatus.UNPROCESSABLE_ENTITY, "파일이 손상되어 열 수 없습니다."),
    FILE_EMPTY(HttpStatus.UNPROCESSABLE_ENTITY, "파일에 데이터가 없습니다."),
    ROW_LIMIT_EXCEEDED(HttpStatus.UNPROCESSABLE_ENTITY, "데이터 행 수가 최대 제한(50,000행)을 초과했습니다."),
    SHEET_NOT_FOUND(HttpStatus.UNPROCESSABLE_ENTITY, "지정된 시트를 찾을 수 없습니다."),
    INVALID_HEADER_ROW(HttpStatus.UNPROCESSABLE_ENTITY, "헤더 행 번호가 올바르지 않습니다."),
    FILE_NOT_FOUND(HttpStatus.NOT_FOUND, "요청한 파일을 찾을 수 없습니다."),
    FILE_EXPIRED(HttpStatus.GONE, "보관 기간이 경과하여 삭제된 파일입니다."),

    // Template
    TEMPLATE_NOT_FOUND(HttpStatus.NOT_FOUND, "보고서 템플릿을 찾을 수 없습니다."),
    TEMPLATE_INACTIVE(HttpStatus.UNPROCESSABLE_ENTITY, "비활성화된 템플릿입니다."),
    TEMPLATE_BROKEN(HttpStatus.INTERNAL_SERVER_ERROR, "템플릿 파일 또는 셀 정의 오류가 발생했습니다."),

    // Job Step & Workflow
    JOB_NOT_FOUND(HttpStatus.NOT_FOUND, "작업을 찾을 수 없습니다."),
    JOB_STEP_INVALID(HttpStatus.CONFLICT, "작업 단계 순서가 올바르지 않습니다. 이전 단계를 먼저 완료해주세요."),
    JOB_ALREADY_GENERATING(HttpStatus.CONFLICT, "보고서가 이미 생성 중입니다."),
    JOB_ALREADY_COMPLETED(HttpStatus.CONFLICT, "이미 완료된 작업입니다."),

    // Mapping
    MAPPING_INCOMPLETE(HttpStatus.UNPROCESSABLE_ENTITY, "필수 항목의 원본 컬럼을 매핑해주세요."),
    MAPPING_DUPLICATE(HttpStatus.UNPROCESSABLE_ENTITY, "동일한 원본 컬럼이 중복 매핑되었습니다."),

    // Normalization & Report Generation
    ERROR_POLICY_REQUIRED(HttpStatus.UNPROCESSABLE_ENTITY, "오류 행 처리 방식을 선택해주세요."),
    TOTAL_MISMATCH(HttpStatus.INTERNAL_SERVER_ERROR, "집계 합계 검증에 실패했습니다."),
    PREVIEW_UNAVAILABLE(HttpStatus.SERVICE_UNAVAILABLE, "미리보기 생성에 실패했습니다."),

    // AI & Rate Limit
    RATE_LIMITED(HttpStatus.TOO_MANY_REQUESTS, "요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."),
    AI_SERVICE_UNAVAILABLE(HttpStatus.SERVICE_UNAVAILABLE, "AI 분석 서비스에 일시적인 장애가 발생했습니다. 규칙 매핑을 사용합니다."),

    // System
    INTERNAL_SERVER_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "서버 내부 오류가 발생했습니다.");

    private final HttpStatus httpStatus;
    private final String defaultMessage;

    ErrorCode(HttpStatus httpStatus, String defaultMessage) {
        this.httpStatus = httpStatus;
        this.defaultMessage = defaultMessage;
    }

    public HttpStatus getHttpStatus() {
        return httpStatus;
    }

    public String getDefaultMessage() {
        return defaultMessage;
    }
}
