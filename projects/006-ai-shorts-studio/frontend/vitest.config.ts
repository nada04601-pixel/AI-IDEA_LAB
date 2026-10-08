import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { include: ["src/**/*.test.ts"] }, // e2e/는 Playwright가 실행한다
});
