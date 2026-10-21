import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".", testMatch: "op07.spec.ts", outputDir: "../test-results/op07",
  workers: 1, retries: 0, timeout: 30_000, reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5198", channel: "chrome", headless: true,
    locale: "es-CL", serviceWorkers: "block", actionTimeout: 5_000,
    trace: "retain-on-failure", screenshot: "only-on-failure",
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5198 --strictPort",
    cwd: fileURLToPath(new URL("..", import.meta.url)),
    url: "http://127.0.0.1:5198", reuseExistingServer: false, timeout: 60_000,
    env: { VITE_API_URL: "/api/", VITE_API_PROXY_TARGET: "http://127.0.0.1:1" },
  },
});
