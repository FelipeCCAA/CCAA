import { defineConfig, devices } from "@playwright/test";

import { API, ORIGEN, RUTA_ESTADO } from "./e2e/constantes";

/*
  Configuración de la auditoría de accesibilidad.

  Levanta los dos servidores porque la aplicación no se sostiene sola: sin el
  backend, todas las pantallas dibujan su estado de error y la auditoría
  mediría treinta veces el mismo cartel de «no se pudieron cargar los datos».
  Lo que interesa revisar son las tablas llenas.

  `reuseExistingServer` está puesto para desarrollo: si ya tienes Vite o Django
  corriendo, los usa en vez de pelear por el puerto.
*/
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./e2e/.artefactos",

  /* El registro de hallazgos se vacía antes de empezar y se convierte en
     informe al terminar. Van aquí y no en un `afterAll` del archivo de pruebas
     porque el worker se reinicia con cada fallo y se llevaría el acumulado por
     delante — que es justo lo que pasa en una auditoría, donde fallar es lo
     normal. `hallazgos.ts` lo cuenta con detalle. */
  globalSetup: "./e2e/preparar.ts",
  globalTeardown: "./e2e/informe.ts",

  /*
    Un solo worker. El informe se arma acumulando hallazgos en memoria y se
    escribe en un `afterAll`; con varios workers cada uno tendría su propia
    copia del arreglo y el informe saldría con un trozo de los resultados.
  */
  workers: 1,
  fullyParallel: false,

  /*
    Sin reintentos. Un reintento sirve cuando la prueba es inestable; aquí un
    fallo es un defecto de accesibilidad, que no cambia por volver a mirarlo, y
    reintentar solo duplicaría los hallazgos en el informe.
  */
  retries: 0,

  reporter: [
    ["list"],
    ["html", { outputFolder: "e2e/.informe-html", open: "never" }],
  ],

  use: {
    baseURL: ORIGEN,
    /* La aplicación está en español y hay fechas en pantalla: con otra
       configuración regional se auditaría un formato que en planta no se ve. */
    locale: "es-CL",
    timezoneId: "America/Santiago",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "sesion",
      testMatch: /auth\.setup\.ts/,
    },
    {
      name: "accesibilidad",
      testMatch: /accesibilidad\.spec\.ts/,
      dependencies: ["sesion"],
      use: {
        ...devices["Desktop Chrome"],
        storageState: RUTA_ESTADO,
      },
    },
  ],

  webServer: [
    {
      command: "npm run dev -- --port 5173 --strictPort",
      url: ORIGEN,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      /*
        Se usa el lanzador del repositorio en vez de invocar Python a mano:
        ya resuelve dónde está el entorno virtual, que según quien clonó el
        proyecto vive en `backend/.venv` o en la raíz.
      */
      /* Con la ruta explícita: `cmd.exe` no busca en el directorio actual
         cuando lo invoca Playwright, y sin el `.\` no encuentra el archivo. */
      command: ".\\iniciar_servidor.cmd 8000",
      cwd: "../backend",
      /* `/api/salud/` responde 200 sin token. Apuntar a un endpoint con
         permisos daría 401 y Playwright no sabría si el servidor arrancó. */
      url: `${API}/api/salud/`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
