import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "op05.spec.ts",
  outputDir: "../op05-ui-results",
  workers: 1,
  retries: 0,
  timeout: 45_000,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5196",
    channel: "chrome",
    headless: true,
    locale: "es-CL",
    timezoneId: "America/Santiago",
    serviceWorkers: "block",
    actionTimeout: 8_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5196 --strictPort",
    cwd: fileURLToPath(new URL("..", import.meta.url)),
    url: "http://127.0.0.1:5196",
    reuseExistingServer: false,
    timeout: 60_000,
    env: { VITE_API_URL: "/api/", VITE_API_PROXY_TARGET: "http://127.0.0.1:1" },
  },
});
