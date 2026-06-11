import { defineConfig } from "@playwright/test";

/**
 * E2E 풀스택 — 세 서비스를 실제로 띄워 J1~J5 검증.
 *   BE  (FastAPI, :8001)  ← 도메인·오케스트레이터(규칙기반 분류기, 네트워크 불필요)
 *   BFF (FastAPI, :8000)  ← 클라이언트 표면, BE_BASE_URL로 BE 호출
 *   FE  (vite preview, :4173) ← react-native-web 빌드, BFF에 WS/HTTP
 */
export default defineConfig({
  testDir: "./specs",
  testMatch: "**/*.e2e.ts",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: { baseURL: "http://localhost:4173", trace: "retain-on-failure" },
  webServer: [
    {
      command: "python -m uvicorn app.api.internal:app --host 127.0.0.1 --port 8001",
      cwd: "../backend",
      url: "http://127.0.0.1:8001/internal/devices",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "python -m uvicorn gateway.main:app --host 127.0.0.1 --port 8000",
      cwd: "../bff",
      env: { BE_BASE_URL: "http://127.0.0.1:8001" },
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run build && npm run preview -- --port 4173 --host 127.0.0.1",
      cwd: "../frontend",
      url: "http://localhost:4173",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
