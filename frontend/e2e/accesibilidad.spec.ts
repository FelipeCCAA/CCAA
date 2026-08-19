/*
  Auditoría de accesibilidad de todas las pantallas.

  Qué mide y qué NO mide
  ----------------------
  axe encuentra defectos comprobables por máquina: contraste insuficiente,
  campos sin etiqueta, botones sin nombre accesible, tablas sin encabezados,
  orden de títulos roto, objetivos táctiles chicos. NO dice si una pantalla se
  entiende, si el flujo tiene demasiados pasos, ni si el mensaje de bloqueo de
  un lote sirve para algo. Eso lo contesta ver a un operario usándola.

  Lo que sí gana la planta con esto es concreto: contraste y tamaño de objetivo
  deciden si alguien con guantes, frente a una pantalla con reflejo, acierta el
  campo a la primera. Por eso se incluye `wcag22aa`, que es donde vive la regla
  de tamaño mínimo del objetivo táctil.

  Por qué las comprobaciones son «soft»
  -------------------------------------
  Con `expect` normal, la primera pantalla con un defecto detiene su prueba y
  el inventario sale a medias. La primera pasada tiene que medirlo TODO: se
  busca la lista completa para decidir qué arreglar, no un semáforo. La corrida
  falla igual al final, pero después de haberlo recorrido entero.

  Los hallazgos se escriben en disco según se encuentran, no se acumulan en
  memoria: ver `hallazgos.ts`, que explica por qué.
*/

import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "@playwright/test";

import { RUTA_ESTADO } from "./constantes";
import { anotar } from "./hallazgos";
import { PANTALLAS_PRIVADAS, PANTALLAS_PUBLICAS, type Pantalla } from "./rutas";

/*
  Normas que se comprueban. `wcag22aa` es la que aporta `target-size`; el resto
  son el cuerpo habitual de A y AA.

  `best-practice` queda fuera a propósito: mezcla recomendaciones de estilo con
  incumplimientos reales, y un informe donde ambas cosas pesan igual empuja a
  arreglar lo cómodo antes que lo que deja a alguien sin poder usar la pantalla.
*/
const NORMAS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];


/*
  Abre una pantalla y espera a que esté realmente dibujada.

  Tres esperas, cada una por un motivo distinto:

  1. Las pantallas se cargan con `lazy`, así que primero aparece el texto
     «Cargando módulo…». Auditar en ese instante mide un div con una frase.
  2. Los datos llegan por API después. Una tabla vacía no tiene los problemas
     de contraste y encabezados que tiene la tabla llena, que es la que ve el
     operario.
  3. Se comprueba que la dirección sea la pedida. Si la sesión no valiera,
     `RutaProtegida` mandaría al login y las treinta pantallas saldrían
     «limpias» por haber auditado treinta veces el formulario de acceso — el
     peor resultado posible, porque parece bueno.
*/
async function abrirPantalla(page: Page, pantalla: Pantalla): Promise<void> {
  await page.goto(`/#${pantalla.ruta}`, { waitUntil: "domcontentloaded" });

  await expect(
    page.getByText("Cargando módulo…"),
    `«${pantalla.nombre}» se quedó cargando el módulo.`,
  ).toBeHidden({ timeout: 30_000 });

  await esperarDatos(page, pantalla);

  const hash = new URL(page.url()).hash.replace(/^#/, "");

  expect(
    hash,
    `Se pidió «${pantalla.ruta}» y el navegador terminó en «${hash}». ` +
      "Si terminó en /login, la sesión de la auditoría no es válida.",
  ).toBe(pantalla.ruta);
}


/*
  `networkidle` es la señal de que los datos llegaron, pero un endpoint lento o
  caído dejaría la auditoría entera esperando: axios corta a los 15 s y aquí se
  le da un poco más. Si se agota, se sigue igual — una pantalla auditada con la
  tabla a medias vale más que una pantalla sin auditar.
*/
async function esperarDatos(page: Page, pantalla: Pantalla): Promise<void> {
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => {
    console.warn(`  ⚠ «${pantalla.nombre}»: la red no se aquietó; se audita lo dibujado.`);
  });
}


/** Corre axe sobre la pantalla abierta y anota lo que encuentre. */
async function auditar(page: Page, pantalla: Pantalla): Promise<void> {
  const resultado = await new AxeBuilder({ page }).withTags(NORMAS).analyze();

  anotar({ tipo: "pantalla", pantalla: pantalla.nombre, ruta: pantalla.ruta });

  for (const violacion of resultado.violations) {
    anotar({
      tipo: "hallazgo",
      pantalla: pantalla.nombre,
      ruta: pantalla.ruta,
      regla: violacion.id,
      gravedad: violacion.impact ?? "sin clasificar",
      descripcion: violacion.help,
      ayuda: violacion.helpUrl,
      nodos: violacion.nodes.map((nodo) => ({
        selector: Array.isArray(nodo.target) ? nodo.target.join(" ") : String(nodo.target),
        html: nodo.html.replace(/\s+/g, " ").slice(0, 160),
        /*
          El motivo concreto, que es lo único que hace corregible el hallazgo:
          para el contraste trae los dos colores y la razón medida contra la
          exigida («2.63, se esperaba 4.5:1»). Sin esto el informe dice que
          algo falla y deja al lector abriendo el navegador para ver cuánto.
        */
        detalle: (nodo.failureSummary ?? "")
          .replace(/\s+/g, " ")
          .replace(/^Fix any of the following:\s*/i, "")
          .replace(/^Fix all of the following:\s*/i, "")
          .trim()
          .slice(0, 240),
      })),
    });
  }

  /*
    Se compara un resumen de texto y no el arreglo de violaciones: axe devuelve
    objetos enormes y el diff de un fallo llenaba la consola con cientos de
    líneas de JSON, tapando el resto de la corrida. El detalle está en el
    informe; aquí solo hace falta ver qué reglas cayó y cuánto.
  */
  const resumen = resultado.violations.map((v) => `${v.id} × ${v.nodes.length}`);

  expect.soft(resumen, `Defectos en «${pantalla.nombre}»`).toEqual([]);
}


/*
  Las pantallas de acceso se auditan sin sesión: es el estado en que un
  operario las ve. Con `storageState` puesto seguirían dibujándose, pero se
  estaría midiendo una situación que en planta no ocurre.
*/
test.describe("Pantallas de acceso (sin sesión)", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  for (const pantalla of PANTALLAS_PUBLICAS) {
    test(`accesibilidad · ${pantalla.nombre}`, async ({ page }) => {
      await page.goto(`/#${pantalla.ruta}`, { waitUntil: "domcontentloaded" });
      await esperarDatos(page, pantalla);
      await auditar(page, pantalla);
    });
  }
});


test.describe("Pantallas internas (con sesión)", () => {
  test.use({ storageState: RUTA_ESTADO });

  for (const pantalla of PANTALLAS_PRIVADAS) {
    test(`accesibilidad · ${pantalla.nombre}`, async ({ page }) => {
      await abrirPantalla(page, pantalla);
      await auditar(page, pantalla);
    });
  }
});
