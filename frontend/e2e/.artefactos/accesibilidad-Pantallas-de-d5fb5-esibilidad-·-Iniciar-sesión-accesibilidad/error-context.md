# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: accesibilidad.spec.ts >> Pantallas de acceso (sin sesión) >> accesibilidad · Iniciar sesión
- Location: e2e\accesibilidad.spec.ts:149:5

# Error details

```
Error: Defectos en «Iniciar sesión»

expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 3

- Array []
+ Array [
+   "target-size × 1",
+ ]
```

# Page snapshot

```yaml
- generic [ref=f1e4]:
  - generic [ref=f1e5]:
    - img "Campos Australes" [ref=f1e6]
    - generic [ref=f1e8]:
      - heading "Sistema de Producción" [level=1] [ref=f1e9]
      - heading "Campos Australes" [level=2] [ref=f1e10]
      - paragraph [ref=f1e11]: Plataforma para la gestión integral de la producción, trazabilidad, calidad e inventario.
  - generic [ref=f1e13]:
    - img "Campos Australes" [ref=f1e14]
    - heading "Bienvenido" [level=2] [ref=f1e15]
    - paragraph [ref=f1e16]: Inicia sesión para acceder al sistema.
    - generic [ref=f1e17]:
      - generic [ref=f1e18]:
        - generic [ref=f1e19]: Usuario
        - textbox "Usuario" [ref=f1e24]:
          - /placeholder: sjuan
      - generic [ref=f1e25]:
        - generic [ref=f1e26]: Contraseña
        - generic [ref=f1e27]:
          - textbox "Contraseña" [ref=f1e31]:
            - /placeholder: ••••••••••••
          - button "Mostrar contraseña" [ref=f1e32]
      - generic [ref=f1e36]:
        - generic [ref=f1e37]:
          - checkbox "Mantener la sesión iniciada" [ref=f1e38]
          - text: Mantener la sesión iniciada
        - link "¿Olvidaste tu contraseña?" [ref=f1e39] [cursor=pointer]:
          - /url: "#/recuperar-contrasena"
      - button "Iniciar sesión" [ref=f1e40]
    - generic [ref=f1e41]: Gestión Productiva · CCAAVersión 1.0
```

# Test source

```ts
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
  112 |         /*
  113 |           El motivo concreto, que es lo único que hace corregible el hallazgo:
  114 |           para el contraste trae los dos colores y la razón medida contra la
  115 |           exigida («2.63, se esperaba 4.5:1»). Sin esto el informe dice que
  116 |           algo falla y deja al lector abriendo el navegador para ver cuánto.
  117 |         */
  118 |         detalle: (nodo.failureSummary ?? "")
  119 |           .replace(/\s+/g, " ")
  120 |           .replace(/^Fix any of the following:\s*/i, "")
  121 |           .replace(/^Fix all of the following:\s*/i, "")
  122 |           .trim()
  123 |           .slice(0, 240),
  124 |       })),
  125 |     });
  126 |   }
  127 | 
  128 |   /*
  129 |     Se compara un resumen de texto y no el arreglo de violaciones: axe devuelve
  130 |     objetos enormes y el diff de un fallo llenaba la consola con cientos de
  131 |     líneas de JSON, tapando el resto de la corrida. El detalle está en el
  132 |     informe; aquí solo hace falta ver qué reglas cayó y cuánto.
  133 |   */
  134 |   const resumen = resultado.violations.map((v) => `${v.id} × ${v.nodes.length}`);
  135 | 
> 136 |   expect.soft(resumen, `Defectos en «${pantalla.nombre}»`).toEqual([]);
      |                                                            ^ Error: Defectos en «Iniciar sesión»
  137 | }
  138 | 
  139 | 
  140 | /*
  141 |   Las pantallas de acceso se auditan sin sesión: es el estado en que un
  142 |   operario las ve. Con `storageState` puesto seguirían dibujándose, pero se
  143 |   estaría midiendo una situación que en planta no ocurre.
  144 | */
  145 | test.describe("Pantallas de acceso (sin sesión)", () => {
  146 |   test.use({ storageState: { cookies: [], origins: [] } });
  147 | 
  148 |   for (const pantalla of PANTALLAS_PUBLICAS) {
  149 |     test(`accesibilidad · ${pantalla.nombre}`, async ({ page }) => {
  150 |       await page.goto(`/#${pantalla.ruta}`, { waitUntil: "domcontentloaded" });
  151 |       await esperarDatos(page, pantalla);
  152 |       await auditar(page, pantalla);
  153 |     });
  154 |   }
  155 | });
  156 | 
  157 | 
  158 | test.describe("Pantallas internas (con sesión)", () => {
  159 |   test.use({ storageState: RUTA_ESTADO });
  160 | 
  161 |   for (const pantalla of PANTALLAS_PRIVADAS) {
  162 |     test(`accesibilidad · ${pantalla.nombre}`, async ({ page }) => {
  163 |       await abrirPantalla(page, pantalla);
  164 |       await auditar(page, pantalla);
  165 |     });
  166 |   }
  167 | });
  168 | 
```