import { defineConfig, devices } from "@playwright/test";

const WEB = "http://127.0.0.1:5209";
const API = "http://127.0.0.1:8209";

// Los specs importan estas variables directamente de e2e/constantes.ts.
// Rechazar valores distintos evita que un comando apunte a otra instalación.
for (const [nombre, esperado] of Object.entries({
  E2E_URL: WEB,
  E2E_API_URL: API,
  VITE_API_PROXY_TARGET: API,
})) {
  if (process.env[nombre] && process.env[nombre] !== esperado) {
    throw new Error(`${nombre} debe ser ${esperado} para OP-09.`);
  }
  process.env[nombre] = esperado;
}

const navegador = {
  ...devices["Desktop Chrome"],
  // El proxy sin servicio rechaza destinos externos; las dos direcciones
  // autorizadas se alcanzan directamente. No sustituye el aislamiento del SO
  // para Django ni para otros procesos fuera del navegador.
  proxy: { server: "http://127.0.0.1:9", bypass: "127.0.0.1" },
};

const sesion = "e2e/.auth/estado.json";

export default defineConfig({
  testDir: "../e2e",
  outputDir: "../../../op09-runtime/ui-current",
  workers: 1,
  fullyParallel: false,
  retries: 0,
  // Desarrollo en Windows compila módulos al abrirlos. La latencia de API
  // se mide por separado en carga; este margen sólo espera el montaje UI.
  expect: { timeout: 15_000 },
  forbidOnly: true,
  reporter: [
    ["list"],
    ["html", { outputFolder: "../../../op09-runtime/ui-report", open: "never" }],
  ],
  use: {
    ...navegador,
    baseURL: WEB,
    locale: "es-CL",
    timezoneId: "America/Santiago",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "sesion", testMatch: /auth\.setup\.ts/ },
    {
      name: "circuito",
      testMatch: /circuito-polvo\.spec\.ts/,
      dependencies: ["sesion"],
      use: { storageState: sesion },
    },
    {
      name: "evaporacion",
      testMatch: /evaporacion\.spec\.ts/,
      dependencies: ["sesion"],
      use: { storageState: sesion },
    },
    {
      name: "flujo-polvo",
      testMatch: /flujo-polvo-continuacion\.spec\.ts/,
      dependencies: ["evaporacion"],
      use: { storageState: sesion },
    },
    {
      name: "flujo-precondensado",
      testMatch: /flujo-precondensado-despacho\.spec\.ts/,
      dependencies: ["sesion"],
      use: { storageState: sesion },
    },
    {
      name: "flujo-descremado",
      testMatch: /flujo-descremado\.spec\.ts/,
      dependencies: ["sesion"],
      use: { storageState: sesion },
    },
    {
      name: "flujo-mantequilla",
      testMatch: /flujo-mantequilla\.spec\.ts/,
      dependencies: ["sesion"],
      use: { storageState: sesion },
    },
    {
      name: "flujo-suero",
      testMatch: /flujo-suero\.spec\.ts/,
      dependencies: ["sesion"],
      use: { storageState: sesion },
    },
  ],
});
