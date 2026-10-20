import { defineConfig } from "@playwright/test";

// Independiente del harness industrial: sin sesión guardada ni servidor Django.
const baseURL = "http://127.0.0.1:5189";

export default defineConfig({
  testDir: "./op02-ui",
  testMatch: "op02.spec.ts",
  outputDir: "./op02-ui-results",
  workers: 1,
  retries: 0,
  timeout: 45_000,
  reporter: "list",
  use: {
    baseURL,
    channel: "chrome", // Usa únicamente el Chrome ya instalado.
    headless: true,
    locale: "es-CL",
    timezoneId: "America/Santiago",
    serviceWorkers: "block",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    viewport: { width: 1440, height: 1100 },
    actionTimeout: 8_000,
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5189 --strictPort",
    url: baseURL,
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      VITE_API_URL: "/api/",
      // Nunca derivar una API no interceptada a Django o a otro entorno.
      VITE_API_PROXY_TARGET: "http://127.0.0.1:1",
    },
  },
});
