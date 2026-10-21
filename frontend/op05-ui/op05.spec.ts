import { expect, test, type Browser, type Page } from "@playwright/test";

const BASE = "http://127.0.0.1:5196";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const corrida = (estado = "borrador", extra: Record<string, unknown> = {}) => ({
  id: 801, ejecucion_codigo: "MANT-801", orden_codigo: "OP-M-4", crema_codigo: "CREMA-LOTE-20",
  mantequilla_codigo: "MANTEQUILLA-801", equipo_nombre: "Mantecadora 1", kg_crema: "100.000",
  kg_mantequilla: null, kg_suero: "0.000", kg_merma: "0.000", kg_reproceso: "0.000",
  motivo_reproceso: "", lote_suero: null, lote_reproceso: null, controles: {}, estado,
  estado_etiqueta: estado === "borrador" ? "Preparación" : estado === "en_proceso" ? "En proceso" : "Pendiente de Calidad",
  iniciada_por_nombre: estado === "borrador" ? null : "Operador simulado", iniciada_en: estado === "borrador" ? null : "2026-10-21T10:00:00-03:00",
  finalizada_por_nombre: estado === "pendiente_calidad" ? "Operador simulado" : null,
  finalizada_en: estado === "pendiente_calidad" ? "2026-10-21T12:00:00-03:00" : null,
  ...extra,
});

const opciones = {
  ordenes: [{ id: 4, codigo: "OP-M-4", producto: "Mantequilla con sal" }],
  cremas: [
    { id: 501, codigo: "CREMA-LOTE-20", producto: "Crema", salida_crema: 81, silo_codigo: "TK-4", silo_id: 4, unidad_origen: "L", disponible_kg: "140.000" },
    { id: 501, codigo: "CREMA-LOTE-20", producto: "Crema", salida_crema: 82, silo_codigo: "TK-5", silo_id: 5, unidad_origen: "L", disponible_kg: "90.000" },
  ],
  cremas_pendientes_calidad: [{ id: 502, codigo: "CREMA-PENDIENTE", producto: "Crema", estado_calidad: "pendiente", etapa_origen: "Descremado" }],
  equipos: [{ id: 601, nombre: "Mantecadora 1", tipo: "linea", ocupado_por: null }],
};

async function abrir(browser: Browser, modo: "crear-perdida" | "crear-conflicto" | "iniciar-perdida" | "cerrar-perdida", estado = "borrador") {
  const context = await browser.newContext({ baseURL: BASE, serviceWorkers: "block", locale: "es-CL", timezoneId: "America/Santiago", viewport: { width: 1440, height: 1100 } });
  const page = await context.newPage();
  const externos: string[] = [];
  const desconocidos: string[] = [];
  const errores: string[] = [];
  const solicitudesCrear: Record<string, unknown>[] = [];
  const solicitudesIniciar: Record<string, unknown>[] = [];
  const solicitudesCerrar: Record<string, unknown>[] = [];
  let primeraCrear = true;
  let primeraIniciar = true;
  let primeraCerrar = true;
  page.on("pageerror", (error) => errores.push(error.message));
  await page.addInitScript(() => sessionStorage.setItem("ccaa.sesion", JSON.stringify({ token: "op05-ui-ficticio", usuario: {
    id: 905, username: "operador-mantequilla-simulado", nombre: "Operador", apellido: "Mantequilla", email: "", rol: "produccion", capacidades: [], perfil: null,
  } })));
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== BASE) { externos.push(url.origin); await route.abort(); return; }
    if (!url.pathname.startsWith("/api/")) { await route.continue(); return; }
    const responder = (json: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(json) });
    if (url.pathname === "/api/procesos/ejecuciones/operativas/" && route.request().method() === "GET") { await responder([]); return; }
    if (url.pathname === "/api/procesos/mantequillas/opciones-alta/") { await responder(opciones); return; }
    if (url.pathname === "/api/procesos/mantequillas/" && route.request().method() === "GET") { await responder({ count: 1, next: null, previous: null, results: [corrida(estado)] }); return; }
    if (url.pathname === "/api/procesos/mantequillas/crear-guiada/" && route.request().method() === "POST") {
      const carga = route.request().postDataJSON() as Record<string, unknown>; solicitudesCrear.push(carga);
      if (primeraCrear) {
        primeraCrear = false;
        if (modo === "crear-perdida") { await route.abort("connectionfailed"); return; }
        if (modo === "crear-conflicto") { await responder({ detail: "El saldo de esta salida cambió. Actualiza el lote y su cantidad." }, 409); return; }
      }
      await responder(corrida("borrador", { id: 802, ejecucion_codigo: "MANT-802", mantequilla_codigo: "MANTEQUILLA-802", kg_crema: String(carga.kg_crema), crema_codigo: "CREMA-LOTE-20" }), 201); return;
    }
    if (url.pathname === "/api/procesos/mantequillas/801/iniciar/" && route.request().method() === "POST") {
      const carga = route.request().postDataJSON() as Record<string, unknown>; solicitudesIniciar.push(carga);
      if (primeraIniciar) { primeraIniciar = false; if (modo === "iniciar-perdida") { await route.abort("connectionfailed"); return; } }
      await responder(corrida("en_proceso")); return;
    }
    if (url.pathname === "/api/procesos/mantequillas/801/cerrar/" && route.request().method() === "POST") {
      const carga = route.request().postDataJSON() as Record<string, unknown>; solicitudesCerrar.push(carga);
      if (primeraCerrar) { primeraCerrar = false; if (modo === "cerrar-perdida") { await route.abort("connectionfailed"); return; } }
      await responder(corrida("pendiente_calidad", {
        kg_mantequilla: String(carga.kg_mantequilla), kg_merma: String(carga.kg_merma),
        kg_reproceso: String(carga.kg_reproceso), motivo_reproceso: String(carga.motivo_reproceso),
      })); return;
    }
    if (url.pathname.includes("notificaciones")) { await responder({ results: [] }); return; }
    desconocidos.push(`${route.request().method()} ${url.pathname}`); await responder({});
  });
  await page.goto("/#/procesos");
  return { context, page, externos, desconocidos, errores, solicitudesCrear, solicitudesIniciar, solicitudesCerrar };
}

async function abrirNueva(page: Page) {
  await page.getByRole("button", { name: "Nueva corrida", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Nueva corrida de mantequilla" })).toBeVisible();
}

async function llenarAlta(page: Page, salida: string, kg = "80") {
  await page.getByLabel("Orden de mantequilla").selectOption("4");
  await page.getByLabel("Origen de crema").selectOption(salida);
  await page.getByLabel("Crema a utilizar (kg)").fill(kg);
  await page.getByLabel("Línea / equipo").selectOption("601");
  await page.getByLabel("Código nuevo lote de mantequilla").fill("MANTEQUILLA-OP05");
}

async function cargarCorridas(page: Page) {
  await page.locator("#proceso-mantequilla").getByRole("button", { name: "Cargar corridas", exact: true }).click();
}

test("OP05: selector identifica cada salida de crema y no ofrece mazada en el alta", async ({ browser }, info) => {
  const ui = await abrir(browser, "crear-conflicto");
  try {
    await abrirNueva(ui.page);
    const origen = ui.page.getByLabel("Origen de crema");
    await expect(origen).toContainText("CREMA-LOTE-20 · TK-4 · 140 kg disponibles");
    await expect(origen).toContainText("CREMA-LOTE-20 · TK-5 · 90 kg disponibles");
    await origen.selectOption("81");
    await expect(ui.page.getByText("Unidad del origen: L", { exact: true })).toBeVisible();
    await expect(origen).not.toContainText("CREMA-PENDIENTE");
    await expect(ui.page.getByText(/CREMA-PENDIENTE.*Pendiente de liberación/)).toBeVisible();
    await expect(ui.page.getByLabel(/mazada|suero/i)).toHaveCount(0);
    await llenarAlta(ui.page, "82");
    await expect(ui.page.getByText("Lote CREMA-LOTE-20 · TK-5 · salida de crema 82")).toBeVisible();
    await expect(ui.page.getByLabel("Crema a utilizar (kg)")).toHaveAttribute("max", "90.000");
    await ui.page.screenshot({ path: info.outputPath("op05-origen-crema.png"), fullPage: true });
    expect(ui.solicitudesCrear).toHaveLength(0);
    expect(ui.externos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});

test("OP05: crear corrida recupera una respuesta perdida con el mismo origen y UUID", async ({ browser }) => {
  const ui = await abrir(browser, "crear-perdida");
  try {
    await abrirNueva(ui.page); await llenarAlta(ui.page, "82");
    await ui.page.getByRole("button", { name: "Crear corrida", exact: true }).click();
    await expect(ui.page.getByRole("alert")).toContainText("No sabemos si se creó la corrida");
    await expect(ui.page.getByLabel("Origen de crema")).toBeDisabled();
    await ui.page.getByRole("button", { name: "Recuperar resultado", exact: true }).click();
    await expect(ui.page.getByText("OP-M-4 · MANTEQUILLA-802", { exact: true })).toBeVisible();
    expect(ui.solicitudesCrear).toHaveLength(2); expect(ui.solicitudesCrear[0]).toEqual(ui.solicitudesCrear[1]);
    expect(ui.solicitudesCrear[0].operacion_id).toMatch(UUID);
    expect(ui.solicitudesCrear[0]).toMatchObject({ lote_crema: 501, salida_crema: 82, kg_crema: 80 });
    expect(ui.solicitudesCrear[0]).not.toHaveProperty("lote_suero");
    expect(ui.desconocidos).toEqual([]); expect(ui.externos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});

test("OP05: iniciar conserva UUID al recuperar respuesta perdida", async ({ browser }) => {
  const ui = await abrir(browser, "iniciar-perdida");
  try {
    await cargarCorridas(ui.page);
    await ui.page.getByRole("button", { name: "Iniciar con esta crema", exact: true }).click();
    await expect(ui.page.getByText(/No sabemos si se inició esta corrida/)).toBeVisible();
    await ui.page.getByRole("button", { name: "Recuperar resultado", exact: true }).click();
    await expect(ui.page.getByRole("button", { name: "Registrar balance y cerrar", exact: true })).toBeVisible();
    expect(ui.solicitudesIniciar).toHaveLength(2); expect(ui.solicitudesIniciar[0]).toEqual(ui.solicitudesIniciar[1]);
    expect(ui.solicitudesIniciar[0].operacion_id).toMatch(UUID);
    expect(ui.desconocidos).toEqual([]); expect(ui.externos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});

test("OP05: balance nuevo excluye mazada y cierre recupera la misma operación", async ({ browser }, info) => {
  const ui = await abrir(browser, "cerrar-perdida", "en_proceso");
  try {
    await cargarCorridas(ui.page);
    await ui.page.getByRole("button", { name: "Registrar balance y cerrar", exact: true }).click();
    await ui.page.getByLabel("Mantequilla producida (kg)").fill("70");
    await ui.page.getByLabel("Merma medida (kg)").fill("25");
    await ui.page.getByLabel("Material segregado para reproceso (kg)").fill("5");
    await ui.page.getByLabel("Motivo del reproceso").fill("Textura segregada para evaluación de Calidad");
    await expect(ui.page.getByRole("status")).toContainText("100 de 100 kg clasificados");
    await expect(ui.page.getByLabel(/mazada|suero/i)).toHaveCount(0);
    await ui.page.screenshot({ path: info.outputPath("op05-balance.png"), fullPage: true });
    await ui.page.getByRole("button", { name: "Cerrar y enviar a Calidad", exact: true }).click();
    await expect(ui.page.getByRole("alert")).toContainText("No sabemos si se cerró la corrida");
    await expect(ui.page.getByLabel("Mantequilla producida (kg)")).toBeDisabled();
    await ui.page.getByRole("button", { name: "Recuperar resultado", exact: true }).click();
    await expect(ui.page.getByText("Pendiente de Calidad", { exact: true })).toBeVisible();
    expect(ui.solicitudesCerrar).toHaveLength(2); expect(ui.solicitudesCerrar[0]).toEqual(ui.solicitudesCerrar[1]);
    expect(ui.solicitudesCerrar[0]).toMatchObject({ kg_mantequilla: 70, kg_merma: 25, kg_reproceso: 5, motivo_reproceso: "Textura segregada para evaluación de Calidad" });
    expect(ui.solicitudesCerrar[0].operacion_id).toMatch(UUID);
    expect(ui.solicitudesCerrar[0]).not.toHaveProperty("kg_suero");
    expect(ui.solicitudesCerrar[0]).not.toHaveProperty("motivo");
    expect(ui.desconocidos).toEqual([]); expect(ui.externos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});

test("OP05: conflicto de saldo deja corregir y asigna UUID nuevo", async ({ browser }) => {
  const ui = await abrir(browser, "crear-conflicto");
  try {
    await abrirNueva(ui.page); await llenarAlta(ui.page, "82", "80");
    await ui.page.getByRole("button", { name: "Crear corrida", exact: true }).click();
    await expect(ui.page.getByText("El saldo de esta salida cambió. Actualiza el lote y su cantidad.", { exact: true })).toBeVisible();
    await ui.page.getByLabel("Crema a utilizar (kg)").fill("75");
    await ui.page.getByRole("button", { name: "Crear corrida", exact: true }).click();
    await expect.poll(() => ui.solicitudesCrear.length).toBe(2);
    expect(ui.solicitudesCrear[0].operacion_id).not.toBe(ui.solicitudesCrear[1].operacion_id);
    expect(ui.solicitudesCrear[1]).toMatchObject({ lote_crema: 501, salida_crema: 82, kg_crema: 75 });
    expect(ui.desconocidos).toEqual([]); expect(ui.externos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});
