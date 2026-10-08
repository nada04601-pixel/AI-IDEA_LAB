import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { defineConfig } from "@playwright/test";

// 사용자의 개발 서버(8000/3000)와 겹치지 않는 포트와, 매번 새로 만드는 임시 저장 폴더를 쓴다.
const API_PORT = 8100;
const WEB_PORT = 3100;
const storage = mkdtempSync(path.join(tmpdir(), "aiss-e2e-"));
const python = process.env.AISS_PYTHON ?? path.join(".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");

export const API_BASE = `http://localhost:${API_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    // 브라우저를 직접 지정할 때만 사용 (기본은 npx playwright install chromium으로 받은 브라우저)
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } : {},
  },
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --port ${API_PORT}`,
      cwd: "../backend",
      env: { AISS_STORAGE_DIR: storage, AISS_CORS_ORIGINS: `http://localhost:${WEB_PORT}` },
      url: `${API_BASE}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npx next dev -p ${WEB_PORT}`,
      env: { NEXT_PUBLIC_API_BASE: API_BASE },
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});
