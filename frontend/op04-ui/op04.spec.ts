import { expect, test, type Browser, type Page } from "@playwright/test";

const BASE = "http://127.0.0.1:5194";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const entradaSiloL = [{ tipo_origen: "silo", origen_id: 31, cantidad: "1200.000", unidad: "L", codigo: "SILO-31", estado_calidad: null }];
const entradaInventarioKg = (id: number, cantidad: unknown) => [{ tipo_origen: "inventario", origen_id: id, cantidad: String(cantidad), unidad: "kg", codigo: `LOTE-KG-${id}`, estado_calidad: "aprobado" }];
const corrida = (extra: Record<string, unknown> = {}) => ({
  id: 44, ejecucion: 84, ejecucion_codigo: "SEC-84", estado: "ejecucion", estado_etiqueta: "En ejecución",
  equipo_id: 7, equipo_nombre: "Torre 1", iniciada_en: "2026-10-21T10:00:00-03:00", lote: 9, lote_codigo: "POLVO-84",
  producto_nombre: "Leche entera en polvo", orden: 8, orden_codigo: "OP-8", kg_alimentacion: null,
  solidos_entrada_pct: null, kg_polvo: null, kg_finos: "0", kg_merma: "0", controles: {}, rendimiento_recuperacion_pct: null,
  finalizada_por: null, finalizada_en: null, requiere_calidad: false, estado_calidad: "no_requerida", operacion_id: "server-run-id",
  entradas_alimentacion: entradaSiloL, requiere_referencia_medicion_kg: true, ...extra,
});

async function abrir(browser: Browser, modo: "inicio-perdida" | "inicio-conflicto" | "cierre-perdida" | "cierre-conflicto") {
  const context = await browser.newContext({ baseURL: BASE, serviceWorkers: "block", locale: "es-CL", timezoneId: "America/Santiago", viewport: { width: 1440, height: 1100 } });
  const page = await context.newPage();
  const externos: string[] = [];
  const desconocidos: string[] = [];
  const errores: string[] = [];
  const solicitudesInicio: Record<string, unknown>[] = [];
  const solicitudesCierre: Record<string, unknown>[] = [];
  let primerInicio = true;
  let primerCierre = true;
  page.on("pageerror", (error) => errores.push(error.message));
  await page.addInitScript(() => sessionStorage.setItem("ccaa.sesion", JSON.stringify({ token: "op04-ui-ficticio", usuario: {
    id: 901, username: "operador-secado-simulado", nombre: "Operador", apellido: "Secado", email: "", rol: "operador", capacidades: [], perfil: { area: "secado" },
  } })));
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== BASE) { externos.push(url.origin); await route.abort(); return; }
    if (!url.pathname.startsWith("/api/")) { await route.continue(); return; }
    const responder = (json: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(json) });
    if (url.pathname === "/api/procesos/secados/" && route.request().method() === "GET") { await responder({ count: 1, next: null, previous: null, results: [corrida()] }); return; }
    if (url.pathname === "/api/procesos/secados/opciones-alimentacion-externa/") {
      await responder({
        ordenes: [{ id: 8, codigo: "OP-8", producto_id: 4, producto_nombre: "Leche entera en polvo", insumo_origen_id: 15 }],
        existencias: [
          { id: 31, lote_id: 31, lote_codigo: "LOTE-KG-31", insumo_id: 15, insumo_nombre: "Concentrado", cantidad_disponible: "1800.000", unidad: "kg", estado_calidad: "aprobado", fifo_recomendado: true, recibido_en: "2026-10-19T08:00:00-03:00" },
          { id: 32, lote_id: 32, lote_codigo: "LOTE-KG-32", insumo_id: 15, insumo_nombre: "Concentrado", cantidad_disponible: "600.000", unidad: "kg", estado_calidad: "aprobado", fifo_recomendado: false, recibido_en: "2026-10-20T08:00:00-03:00" },
        ],
        equipos: [{ id: 7, codigo: "T-1", nombre: "Torre 1", disponible: true }, { id: 9, codigo: "T-2", nombre: "Torre 2", disponible: false }],
      }); return;
    }
    if (url.pathname === "/api/procesos/secados/iniciar-desde-inventario/" && route.request().method() === "POST") {
      const carga = route.request().postDataJSON() as Record<string, unknown>; solicitudesInicio.push(carga);
      if (primerInicio) {
        primerInicio = false;
        if (modo === "inicio-perdida") { await route.abort("connectionfailed"); return; }
        if (modo === "inicio-conflicto") { await responder({ detail: "El saldo cambió; revisa la cantidad." }, 409); return; }
      }
      await responder(corrida({ id: 45, ejecucion_codigo: "SEC-85", kg_alimentacion: String(carga.cantidad), entradas_alimentacion: entradaInventarioKg(Number(carga.existencia), carga.cantidad), requiere_referencia_medicion_kg: false }), 201); return;
    }
    if (url.pathname === "/api/procesos/secados/44/cerrar/" && route.request().method() === "POST") {
      const carga = route.request().postDataJSON() as Record<string, unknown>; solicitudesCierre.push(carga);
      if (primerCierre) {
        primerCierre = false;
        if (modo === "cierre-perdida") { await route.abort("connectionfailed"); return; }
        if (modo === "cierre-conflicto") { await responder({ detail: "La medición requiere una referencia válida." }, 400); return; }
      }
      await responder(corrida({ estado: "cerrada", estado_etiqueta: "Cerrada", kg_alimentacion: String(carga.kg_alimentacion), finalizada_en: "2026-10-21T13:00:00-03:00" })); return;
    }
    if (url.pathname.includes("notificaciones")) { await responder({ results: [] }); return; }
    desconocidos.push(`${route.request().method()} ${url.pathname}`); await responder({});
  });
  await page.goto("/#/secado");
  return { context, page, externos, desconocidos, errores, solicitudesInicio, solicitudesCierre };
}

async function abrirInicio(page: Page) {
  await page.getByRole("button", { name: "Alimentación externa", exact: true }).click();
  await page.getByLabel("Orden / producto").selectOption("8");
  await page.getByLabel("Lote externo disponible").selectOption("31");
  await page.getByLabel("Torre").selectOption("7");
  await page.getByLabel("Código lote de salida").fill("SALIDA-OP04");
  await page.getByLabel(/Cantidad a alimentar/).fill("1000");
}

test("OP04: FIFO sugiere el lote más antiguo, muestra unidad y bloquea equipo ocupado", async ({ browser }, info) => {
  const ui = await abrir(browser, "inicio-conflicto");
  try {
    await ui.page.getByRole("button", { name: "Alimentación externa", exact: true }).click();
    await ui.page.getByLabel("Orden / producto").selectOption("8");
    await expect(ui.page.getByLabel("Lote externo disponible")).toContainText("FIFO sugerido");
    await ui.page.getByLabel("Lote externo disponible").selectOption("32");
    await expect(ui.page.getByText("(kg)", { exact: true })).toBeVisible();
    await expect(ui.page.getByText(/Hay un lote anterior habilitado/)).toBeVisible();
    await expect(ui.page.getByLabel("Motivo para usar otro lote (requerido)")).toBeVisible();
    await ui.page.getByLabel("Motivo para usar otro lote (requerido)").fill("Lote anterior reservado para control de planta");
    await ui.page.getByLabel("Torre").selectOption("9");
    await expect(ui.page.getByRole("button", { name: "Confirmar e iniciar Secado", exact: true })).toBeDisabled();
    await ui.page.screenshot({ path: info.outputPath("op04-fifo.png"), fullPage: true });
    expect(ui.solicitudesInicio).toHaveLength(0);
    expect(ui.externos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});

test("OP04: inicio con respuesta perdida reenvía la misma carga y el mismo UUID", async ({ browser }) => {
  const ui = await abrir(browser, "inicio-perdida");
  try {
    await abrirInicio(ui.page);
    await ui.page.getByRole("button", { name: "Confirmar e iniciar Secado", exact: true }).click();
    await expect(ui.page.getByRole("alert").filter({ hasText: "No sabemos si se inició" })).toBeVisible();
    await expect(ui.page.getByLabel("Código lote de salida")).toBeDisabled();
    await ui.page.getByRole("button", { name: "Recuperar resultado", exact: true }).click();
    await expect(ui.page.getByText("Corrida SEC-85 iniciada desde un lote externo liberado.")).toBeVisible();
    expect(ui.solicitudesInicio).toHaveLength(2);
    expect(ui.solicitudesInicio[0]).toEqual(ui.solicitudesInicio[1]);
    expect(ui.solicitudesInicio[0].operacion_id).toMatch(UUID);
    expect(ui.solicitudesInicio[0]).toMatchObject({ existencia: 31, cantidad: 1000 });
    expect(ui.desconocidos).toEqual([]); expect(ui.externos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});

test("OP04: un 409 permite corregir y genera UUID nuevo", async ({ browser }) => {
  const ui = await abrir(browser, "inicio-conflicto");
  try {
    await abrirInicio(ui.page);
    await ui.page.getByRole("button", { name: "Confirmar e iniciar Secado", exact: true }).click();
    await expect(ui.page.getByText("El saldo cambió; revisa la cantidad.", { exact: true })).toBeVisible();
    await ui.page.getByLabel(/Cantidad a alimentar/).fill("900");
    await ui.page.getByRole("button", { name: "Confirmar e iniciar Secado", exact: true }).click();
    await expect.poll(() => ui.solicitudesInicio.length).toBe(2);
    expect(ui.solicitudesInicio[0].operacion_id).not.toBe(ui.solicitudesInicio[1].operacion_id);
    expect(ui.solicitudesInicio[1].cantidad).toBe(900);
    expect(ui.desconocidos).toEqual([]); expect(ui.externos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});

async function llenarCierre(page: Page, referencia: string) {
  await page.getByRole("button", { name: "Registrar balance y cerrar corrida", exact: true }).click();
  await expect(page.getByText("SILO-31", { exact: true })).toBeVisible();
  await page.getByLabel(/Alimentación medida/).fill("850");
  await page.getByLabel("Ticket o registro de medición (kg medidos)").fill(referencia);
  await page.getByLabel(/Sólidos de entrada/).fill("45");
  await page.getByLabel(/Polvo obtenido/).fill("300");
}

test("OP04: cierre L muestra origen y ticket, y recupera con la misma clave", async ({ browser }, info) => {
  const ui = await abrir(browser, "cierre-perdida");
  try {
    await llenarCierre(ui.page, "TICKET-KG-778");
    await ui.page.screenshot({ path: info.outputPath("op04-cierre-litros.png"), fullPage: true });
    await ui.page.getByRole("button", { name: "Confirmar balance y cerrar", exact: true }).click();
    await expect(ui.page.getByRole("alert").filter({ hasText: "No sabemos si se cerró" })).toBeVisible();
    await expect(ui.page.getByLabel("Ticket o registro de medición (kg medidos)")).toBeDisabled();
    await ui.page.getByRole("button", { name: "Recuperar resultado", exact: true }).click();
    await expect(ui.page.getByText("Corrida SEC-84 cerrada correctamente.")).toBeVisible();
    expect(ui.solicitudesCierre).toHaveLength(2); expect(ui.solicitudesCierre[0]).toEqual(ui.solicitudesCierre[1]);
    expect(ui.solicitudesCierre[0]).toMatchObject({ kg_alimentacion: 850, referencia_medicion_kg: "TICKET-KG-778" });
    expect(ui.solicitudesCierre[0].operacion_id).toMatch(UUID);
    expect(ui.desconocidos).toEqual([]); expect(ui.externos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});

test("OP04: rechazo de cierre permite corregir la referencia con otra clave", async ({ browser }) => {
  const ui = await abrir(browser, "cierre-conflicto");
  try {
    await llenarCierre(ui.page, "TICKET-ANTERIOR");
    await ui.page.getByRole("button", { name: "Confirmar balance y cerrar", exact: true }).click();
    await expect(ui.page.getByRole("alert")).toContainText("La medición requiere una referencia válida.");
    await ui.page.getByLabel("Ticket o registro de medición (kg medidos)").fill("TICKET-CORREGIDO");
    await ui.page.getByRole("button", { name: "Confirmar balance y cerrar", exact: true }).click();
    await expect.poll(() => ui.solicitudesCierre.length).toBe(2);
    expect(ui.solicitudesCierre[0].operacion_id).not.toBe(ui.solicitudesCierre[1].operacion_id);
    expect(ui.solicitudesCierre[1].referencia_medicion_kg).toBe("TICKET-CORREGIDO");
    expect(ui.desconocidos).toEqual([]); expect(ui.externos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});
