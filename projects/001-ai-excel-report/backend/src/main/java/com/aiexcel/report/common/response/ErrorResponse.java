package com.aiexcel.report.common.response;

import com.fasterxml.jackson.annotation.JsonInclude;

import java.util.Map;

public record ErrorResponse(ErrorInfo error) {

    @JsonInclude(JsonInclude.Include.NON_EMPTY)
    public record ErrorInfo(
            String code,
            String message,
            Map<String, Object> details
    ) {}

    public static ErrorResponse of(String code, String message) {
        return new ErrorResponse(new ErrorInfo(code, message, null));
    }

    public static ErrorResponse of(String code, String message, Map<String, Object> details) {
        return new ErrorResponse(new ErrorInfo(code, message, details));
    }
}
