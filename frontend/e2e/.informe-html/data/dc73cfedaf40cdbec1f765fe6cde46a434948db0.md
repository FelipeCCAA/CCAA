# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: accesibilidad.spec.ts >> Pantallas internas (con sesión) >> accesibilidad · Leche · En camino
- Location: e2e\accesibilidad.spec.ts:150:5

# Error details

```
Error: Defectos en «Leche · En camino»

expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 3

- Array []
+ Array [
+   "color-contrast × 16",
+ ]
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - complementary [ref=e4]:
    - img "Campos Australes" [ref=e6]
    - navigation [ref=e7]:
      - generic [ref=e8]:
        - generic [ref=e9]:
          - paragraph [ref=e10]: Inicio
          - link "Panel general" [ref=e12] [cursor=pointer]:
            - /url: "#/dashboard"
        - generic [ref=e19]:
          - paragraph [ref=e20]: Operación de planta
          - generic [ref=e21]:
            - link "Planificación" [ref=e22] [cursor=pointer]:
              - /url: "#/planificacion"
            - link "Recepción de leche" [ref=e26] [cursor=pointer]:
              - /url: "#/leche"
            - link "Estandarización" [ref=e34] [cursor=pointer]:
              - /url: "#/estandarizacion"
            - link "Producción" [ref=e38] [cursor=pointer]:
              - /url: "#/produccion"
            - link "Procesos y trazabilidad" [ref=e42] [cursor=pointer]:
              - /url: "#/procesos"
            - link "Calidad y liberación" [ref=e48] [cursor=pointer]:
              - /url: "#/liberacion"
            - link "Registros de planta" [ref=e54] [cursor=pointer]:
              - /url: "#/registros"
            - link "Inocuidad · Aseos" [ref=e59] [cursor=pointer]:
              - /url: "#/inocuidad/aseos"
        - generic [ref=e64]:
          - paragraph [ref=e65]: Materiales e inventario
          - generic [ref=e66]:
            - link "Abastecimiento" [ref=e67] [cursor=pointer]:
              - /url: "#/abastecimiento"
            - link "Inventario y bodegas" [ref=e79] [cursor=pointer]:
              - /url: "#/abastecimiento/stock"
        - generic [ref=e84]:
          - paragraph [ref=e85]: Soporte
          - link "Mantenimiento" [ref=e87] [cursor=pointer]:
            - /url: "#/mantenimiento"
        - generic [ref=e91]:
          - paragraph [ref=e92]: Gestión
          - generic [ref=e93]:
            - link "Maestros" [ref=e94] [cursor=pointer]:
              - /url: "#/maestros"
            - link "Auditoría" [ref=e100] [cursor=pointer]:
              - /url: "#/auditoria"
            - link "Administración" [ref=e106] [cursor=pointer]:
              - /url: "#/administracion"
    - generic [ref=e113]:
      - generic [ref=e114]:
        - generic [ref=e115]: Au
        - generic [ref=e116]:
          - paragraph [ref=e117]: Auditoría Accesibilidad
          - paragraph [ref=e118]: Auditoría automática
      - button "Cerrar sesión" [ref=e119]
  - main [ref=e123]:
    - generic [ref=e125]:
      - generic [ref=e126]:
        - paragraph [ref=e127]: Flujo operativo · Leche cruda
        - heading "Del camión a estandarización" [level=1] [ref=e128]
        - paragraph [ref=e129]: Recepciona el camión, controla cada módulo, descarga en un silo y entrega la leche disponible directamente a Estandarización.
        - generic [ref=e130]:
          - generic [ref=e137]:
            - generic [ref=e138]: 1 · Recepción
            - generic [ref=e139]: Datos del camión
          - generic [ref=e145]:
            - generic [ref=e146]: 2 · Calidad
            - generic [ref=e147]: Camión + crioscopía por módulo
          - generic [ref=e154]:
            - generic [ref=e155]: 3 · Silo
            - generic [ref=e156]: Asignar y descargar
          - link "4 · Estandarización Seleccionar silo disponible" [ref=e159] [cursor=pointer]:
            - /url: "#/estandarizacion"
            - generic [ref=e162]:
              - generic [ref=e163]: 4 · Estandarización
              - generic [ref=e164]: Seleccionar silo disponible
      - navigation [ref=e167]:
        - link "Panel" [ref=e168] [cursor=pointer]:
          - /url: "#/leche"
        - link "Rutas" [ref=e169] [cursor=pointer]:
          - /url: "#/leche/rutas"
        - link "En camino" [ref=e170] [cursor=pointer]:
          - /url: "#/leche/en-camino"
        - link "Muestreo" [ref=e171] [cursor=pointer]:
          - /url: "#/leche/muestreo"
        - link "Calidad" [ref=e172] [cursor=pointer]:
          - /url: "#/leche/calidad"
        - link "Silo y descarga" [ref=e173] [cursor=pointer]:
          - /url: "#/leche/descarga"
        - link "Silos" [ref=e174] [cursor=pointer]:
          - /url: "#/leche/silos"
        - link "Historial" [ref=e175] [cursor=pointer]:
          - /url: "#/leche/historial"
      - generic [ref=e176]:
        - generic [ref=e178]:
          - heading "En camino a planta" [level=2] [ref=e179]
          - paragraph [ref=e180]: Cargas cerradas en el predio que todavía no se recepcionaron.
        - generic [ref=e181]:
          - paragraph [ref=e188]: No hay cargas pendientes de llegar
          - paragraph [ref=e189]:
            - text: Aparecen aquí en cuanto se registra una carga en
            - link "Rutas" [ref=e190] [cursor=pointer]:
              - /url: "#/leche/rutas"
            - text: .
        - paragraph [ref=e191]:
          - text: Una carga sale de esta lista cuando se registra su llegada en
          - link "Muestreo" [ref=e192] [cursor=pointer]:
            - /url: "#/leche/muestreo"
          - text: ", eligiéndola en el formulario de nueva recepción."
```

# Test source

```ts
  24  |   Los hallazgos se escriben en disco según se encuentran, no se acumulan en
  25  |   memoria: ver `hallazgos.ts`, que explica por qué.
  26  | */
  27  | 
  28  | import AxeBuilder from "@axe-core/playwright";
  29  | import { test, expect, type Page } from "@playwright/test";
  30  | 
  31  | import { RUTA_ESTADO } from "./constantes";
  32  | import { anotar } from "./hallazgos";
  33  | import { PANTALLAS_PRIVADAS, PANTALLAS_PUBLICAS, type Pantalla } from "./rutas";
  34  | 
  35  | /*
  36  |   Normas que se comprueban. `wcag22aa` es la que aporta `target-size`; el resto
  37  |   son el cuerpo habitual de A y AA.
  38  | 
  39  |   `best-practice` queda fuera a propósito: mezcla recomendaciones de estilo con
  40  |   incumplimientos reales, y un informe donde ambas cosas pesan igual empuja a
  41  |   arreglar lo cómodo antes que lo que deja a alguien sin poder usar la pantalla.
  42  | */
  43  | const NORMAS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
  44  | 
  45  | 
  46  | /*
  47  |   Abre una pantalla y espera a que esté realmente dibujada.
  48  | 
  49  |   Tres esperas, cada una por un motivo distinto:
  50  | 
  51  |   1. Las pantallas se cargan con `lazy`, así que primero aparece el texto
  52  |      «Cargando módulo…». Auditar en ese instante mide un div con una frase.
  53  |   2. Los datos llegan por API después. Una tabla vacía no tiene los problemas
  54  |      de contraste y encabezados que tiene la tabla llena, que es la que ve el
  55  |      operario.
  56  |   3. Se comprueba que la dirección sea la pedida. Si la sesión no valiera,
  57  |      `RutaProtegida` mandaría al login y las treinta pantallas saldrían
  58  |      «limpias» por haber auditado treinta veces el formulario de acceso — el
  59  |      peor resultado posible, porque parece bueno.
  60  | */
  61  | async function abrirPantalla(page: Page, pantalla: Pantalla): Promise<void> {
  62  |   await page.goto(`/#${pantalla.ruta}`, { waitUntil: "domcontentloaded" });
  63  | 
  64  |   await expect(
  65  |     page.getByText("Cargando módulo…"),
  66  |     `«${pantalla.nombre}» se quedó cargando el módulo.`,
  67  |   ).toBeHidden({ timeout: 30_000 });
  68  | 
  69  |   await esperarDatos(page, pantalla);
  70  | 
  71  |   const hash = new URL(page.url()).hash.replace(/^#/, "");
  72  | 
  73  |   expect(
  74  |     hash,
  75  |     `Se pidió «${pantalla.ruta}» y el navegador terminó en «${hash}». ` +
  76  |       "Si terminó en /login, la sesión de la auditoría no es válida.",
  77  |   ).toBe(pantalla.ruta);
  78  | }
  79  | 
  80  | 
  81  | /*
  82  |   `networkidle` es la señal de que los datos llegaron, pero un endpoint lento o
  83  |   caído dejaría la auditoría entera esperando: axios corta a los 15 s y aquí se
  84  |   le da un poco más. Si se agota, se sigue igual — una pantalla auditada con la
  85  |   tabla a medias vale más que una pantalla sin auditar.
  86  | */
  87  | async function esperarDatos(page: Page, pantalla: Pantalla): Promise<void> {
  88  |   await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => {
  89  |     console.warn(`  ⚠ «${pantalla.nombre}»: la red no se aquietó; se audita lo dibujado.`);
  90  |   });
  91  | }
  92  | 
  93  | 
  94  | /** Corre axe sobre la pantalla abierta y anota lo que encuentre. */
  95  | async function auditar(page: Page, pantalla: Pantalla): Promise<void> {
  96  |   const resultado = await new AxeBuilder({ page }).withTags(NORMAS).analyze();
  97  | 
  98  |   anotar({ tipo: "pantalla", pantalla: pantalla.nombre, ruta: pantalla.ruta });
  99  | 
  100 |   for (const violacion of resultado.violations) {
  101 |     anotar({
  102 |       tipo: "hallazgo",
  103 |       pantalla: pantalla.nombre,
  104 |       ruta: pantalla.ruta,
  105 |       regla: violacion.id,
  106 |       gravedad: violacion.impact ?? "sin clasificar",
  107 |       descripcion: violacion.help,
  108 |       ayuda: violacion.helpUrl,
  109 |       nodos: violacion.nodes.map((nodo) => ({
  110 |         selector: Array.isArray(nodo.target) ? nodo.target.join(" ") : String(nodo.target),
  111 |         html: nodo.html.replace(/\s+/g, " ").slice(0, 160),
  112 |       })),
  113 |     });
  114 |   }
  115 | 
  116 |   /*
  117 |     Se compara un resumen de texto y no el arreglo de violaciones: axe devuelve
  118 |     objetos enormes y el diff de un fallo llenaba la consola con cientos de
  119 |     líneas de JSON, tapando el resto de la corrida. El detalle está en el
  120 |     informe; aquí solo hace falta ver qué reglas cayó y cuánto.
  121 |   */
  122 |   const resumen = resultado.violations.map((v) => `${v.id} × ${v.nodes.length}`);
  123 | 
> 124 |   expect.soft(resumen, `Defectos en «${pantalla.nombre}»`).toEqual([]);
      |                                                            ^ Error: Defectos en «Leche · En camino»
  125 | }
  126 | 
  127 | 
  128 | /*
  129 |   Las pantallas de acceso se auditan sin sesión: es el estado en que un
  130 |   operario las ve. Con `storageState` puesto seguirían dibujándose, pero se
  131 |   estaría midiendo una situación que en planta no ocurre.
  132 | */
  133 | test.describe("Pantallas de acceso (sin sesión)", () => {
  134 |   test.use({ storageState: { cookies: [], origins: [] } });
  135 | 
  136 |   for (const pantalla of PANTALLAS_PUBLICAS) {
  137 |     test(`accesibilidad · ${pantalla.nombre}`, async ({ page }) => {
  138 |       await page.goto(`/#${pantalla.ruta}`, { waitUntil: "domcontentloaded" });
  139 |       await esperarDatos(page, pantalla);
  140 |       await auditar(page, pantalla);
  141 |     });
  142 |   }
  143 | });
  144 | 
  145 | 
  146 | test.describe("Pantallas internas (con sesión)", () => {
  147 |   test.use({ storageState: RUTA_ESTADO });
  148 | 
  149 |   for (const pantalla of PANTALLAS_PRIVADAS) {
  150 |     test(`accesibilidad · ${pantalla.nombre}`, async ({ page }) => {
  151 |       await abrirPantalla(page, pantalla);
  152 |       await auditar(page, pantalla);
  153 |     });
  154 |   }
  155 | });
  156 | 
```