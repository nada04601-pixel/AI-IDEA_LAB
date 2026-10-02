package com.aiexcel.report;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@EnableAsync
@SpringBootApplication
public class AiExcelReportApplication {

    public static void main(String[] args) {
        SpringApplication.run(AiExcelReportApplication.class, args);
    }
}
