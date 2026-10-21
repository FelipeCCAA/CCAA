import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

// Aislado del harness industrial: todas las API son interceptadas por el test.
export default defineConfig({
  testDir: ".",
  testMatch: "op03.spec.ts",
  outputDir: "../op03-ui-results",
  workers: 1,
  retries: 0,
  timeout: 45_000,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5193",
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
    command: "npm run dev -- --host 127.0.0.1 --port 5193 --strictPort",
    cwd: fileURLToPath(new URL("..", import.meta.url)),
    url: "http://127.0.0.1:5193",
    reuseExistingServer: false,
    timeout: 60_000,
    env: { VITE_API_URL: "/api/", VITE_API_PROXY_TARGET: "http://127.0.0.1:1" },
  },
});
