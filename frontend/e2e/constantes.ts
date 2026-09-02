/*
  Direcciones y rutas de archivo que comparten la configuración y las pruebas.

  Viven aquí y no en `playwright.config.ts` porque las pruebas también las
  necesitan, e importar el archivo de configuración desde una prueba arrastra
  la configuración entera —incluido el bloque `webServer`— a un sitio donde no
  pinta nada.
*/

/** Dónde escucha Vite. El origen tiene que coincidir con el de `storageState`. */
export const ORIGEN = process.env.E2E_URL ?? "http://localhost:5173";

/** Dónde escucha Django. Es el valor por omisión de `services/api.ts`. */
export const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8000";

/** Sesión serializada que produce `auth.setup.ts` y consume la auditoría. */
export const RUTA_ESTADO = "e2e/.auth/estado.json";

/** Informe legible que deja la auditoría al terminar. */
export const RUTA_INFORME = "e2e/informe-accesibilidad.md";

/** Identificadores producidos por Evaporación y consumidos por su continuación. */
export const RUTA_FLUJO_POLVO = "e2e/.registro/flujo-polvo.json";

/*
  Registro crudo (JSONL) que las pruebas van escribiendo mientras corren.

  Deliberadamente FUERA de `outputDir`: Playwright vacía ese directorio al
  empezar la corrida, así que un registro guardado ahí desaparecería justo
  antes de la primera anotación.
*/
export const RUTA_HALLAZGOS = "e2e/.registro/hallazgos.jsonl";
