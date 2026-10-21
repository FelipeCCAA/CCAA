import { expect, test, type Browser, type Page } from "@playwright/test";

const BASE = "http://127.0.0.1:5193";
const CLAVE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SILO = {
  silo_id: 71, codigo: "SILO-RESERVADO", tipo: "silo", tipo_etiqueta: "Silo", litros: 10000, capacidad: 20000,
  litros_reservados: 8000, litros_libres: 2000, litros_disponibles: 2000, capacidad_reservada: 0,
  estado: "disponible", estado_etiqueta: "Disponible", producto_actual: "Leche entera",
  temperatura_actual: 4, ultima_limpieza: null, ultimo_movimiento: null, leche_mas_antigua_en: null,
  antiguedad_horas: null, analisis: 9, analisis_tomado_en: null, grasa: "4.20", sng: "8.80",
  analisis_vigente: true, motivo_vigencia: "", motivos_no_disponible: [], pct: 50, excedido: false, negativo: false,
  reservas_activas: [{ id: 1, ejecucion_id: 61, ejecucion_codigo: "CORRIDA-8MIL", tipo: "origen",
    tipo_etiqueta: "Material de origen", cantidad_planificada: "8000.00", producto_id: 1, producto_nombre: "Leche entera" }],
};

async function abrir(browser: Browser, modo: "perdida" | "servidor" | "cambio" | "anterior" | "bodega") {
  const context = await browser.newContext({ baseURL: BASE, serviceWorkers: "block", locale: "es-CL", timezoneId: "America/Santiago", viewport: { width: 1440, height: 1100 } });
  const page = await context.newPage();
  const externos: string[] = [];
  const desconocidos: string[] = [];
  const errores: string[] = [];
  const solicitudes: Record<string, unknown>[] = [];
  let consultas = 0;
  let comprometido = false;
  page.on("pageerror", (error) => errores.push(error.message));
  await page.addInitScript(() => {
    sessionStorage.setItem("ccaa.sesion", JSON.stringify({ token: "op03-ui-sin-credenciales", usuario: {
      id: 900, username: "operador-simulado", nombre: "Operador", apellido: "Simulado", email: "", rol: "recepcion", capacidades: [], perfil: null,
    } }));
  });
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== BASE) { externos.push(url.origin); await route.abort(); return; }
    if (!url.pathname.startsWith("/api/")) { await route.continue(); return; }
    const responder = (json: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(json) });
    if (url.pathname === "/api/usuarios/yo/") { await responder({ id: 900, username: "operador-simulado", nombre: "Operador", apellido: "Simulado", email: "", rol: "recepcion", capacidades: [], perfil: null }); return; }
    if (url.pathname === "/api/recepcion/ocupacion/") {
      consultas += 1;
      const silo: Partial<typeof SILO> = comprometido ? { ...SILO, litros: 8000, litros_libres: 0, litros_disponibles: 0, pct: 40 } : { ...SILO };
      if (modo === "anterior" && consultas === 1) {
        delete silo.litros_reservados; delete silo.litros_libres; delete silo.litros_disponibles; delete silo.capacidad_reservada;
      }
      await responder({ silos: [silo], litros_totales: silo.litros, alertas: { excedidos: [], negativos: [] } }); return;
    }
    if (url.pathname === "/api/recepcion/despachos-leche/" && route.request().method() === "POST") {
      const carga = route.request().postDataJSON() as Record<string, unknown>;
      solicitudes.push(carga);
      if (solicitudes.length === 1) {
        if (modo === "perdida") { comprometido = true; await route.abort("connectionfailed"); }
        else if (modo === "servidor") { comprometido = true; await responder({ detail: "No pudimos confirmar el resultado del envío." }, 503); }
        else await responder({ detail: "La disponibilidad cambió; vuelve a revisar la cantidad." }, 409);
        return;
      }
      comprometido = true;
      await responder({ id: 18, ...carga }, 201); return;
    }
    if (url.pathname === "/api/inventario/movimientos/trasladar/" && route.request().method() === "POST") {
      const carga = route.request().postDataJSON() as Record<string, unknown>;
      solicitudes.push(carga);
      if (solicitudes.length === 1) { await route.abort("connectionfailed"); return; }
      await responder({ id: 28, cantidad: carga.cantidad, insumo_nombre: "Sacos de prueba", origen_codigo: "BOD-A", destino_codigo: "BOD-B", saldo_posterior: "75.000" }); return;
    }
    if (url.pathname.includes("intermedias-disponibles")) { await responder([]); return; }
    if (url.pathname === "/api/procesos/salidas/disponibles/") { await responder([]); return; }
    if (url.pathname.includes("notificaciones")) { await responder({ results: [] }); return; }
    // Análisis se carga al seleccionar el silo, separado de su ocupación.
    if (url.pathname === "/api/recepcion/analisis-silo/mi-borrador/") { await route.fulfill({ status: 204 }); return; }
    if (url.pathname.startsWith("/api/recepcion/analisis-silo/")) { await responder({ results: [] }); return; }
    if (url.pathname.startsWith("/api/maestros/")) { await responder({ results: [] }); return; }
    desconocidos.push(`${route.request().method()} ${url.pathname}`); await route.abort();
  });
  await page.goto(modo === "bodega" ? "/op03-ui/panel-movimiento.html" : "/#/silos");
  return { context, page, externos, desconocidos, errores, solicitudes };
}

async function seleccionar(page: Page) {
  await page.getByRole("button").filter({ has: page.getByText("SILO-RESERVADO", { exact: true }) }).click();
  await expect(page.getByRole("heading", { name: "10.000 L físicos", exact: true })).toBeVisible();
}

async function datosDespacho(page: Page, litros: string) {
  await page.getByRole("button", { name: "Despachar", exact: true }).click();
  await page.getByLabel("Litros", { exact: true }).fill(litros);
  await page.getByLabel("Fecha y hora", { exact: true }).fill("2026-10-21T12:00");
  await page.getByLabel("Destino o cliente", { exact: true }).fill("Cliente simulado");
  await page.getByLabel("Guía de despacho", { exact: true }).fill("GD-OP03");
  await page.getByLabel("Patente del vehículo", { exact: true }).fill("TEST-12");
}

test("OP03: reserva parcial limita a 2000 L y retry recupera el mismo despacho", async ({ browser }, info) => {
  const ui = await abrir(browser, "perdida");
  try {
    await seleccionar(ui.page);
    await expect(ui.page.getByRole("button", { name: "Despachar", exact: true })).toBeEnabled();
    await ui.page.screenshot({ path: info.outputPath("op03-silos.png"), fullPage: true });
    await datosDespacho(ui.page, "5000");
    await ui.page.getByRole("button", { name: "Confirmar despacho", exact: true }).click();
    expect(ui.solicitudes).toHaveLength(0);
    await expect(ui.page.getByLabel("Litros", { exact: true })).toHaveAttribute("max", "2000");
    await ui.page.getByLabel("Litros", { exact: true }).fill("2000");
    await ui.page.getByRole("button", { name: "Confirmar despacho", exact: true }).click();
    await expect(ui.page.getByText("No se pudo registrar el despacho.", { exact: true })).toBeVisible();
    await expect(ui.page.getByRole("alert")).toContainText("No sabemos si se confirmó");
    await expect(ui.page.getByLabel("Litros", { exact: true })).toBeDisabled();
    await expect(ui.page.getByLabel("Destino o cliente", { exact: true })).toBeDisabled();
    await expect(ui.page.getByRole("button", { name: "Actualizar disponibilidad", exact: true })).toBeDisabled();
    await ui.page.getByRole("button", { name: "Recuperar resultado", exact: true }).click();
    await expect(ui.page.getByRole("heading", { name: "8.000 L físicos", exact: true })).toBeVisible();
    expect(ui.solicitudes).toHaveLength(2);
    expect(ui.solicitudes[0]).toEqual(ui.solicitudes[1]);
    expect(ui.solicitudes[0].operacion_id).toMatch(CLAVE);
    await expect(ui.page.getByRole("button", { name: "Despachar", exact: true })).toBeDisabled();
    expect(ui.externos).toEqual([]); expect(ui.desconocidos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});

test("OP03: corregir la carga después del rechazo usa una clave nueva", async ({ browser }) => {
  const ui = await abrir(browser, "cambio");
  try {
    await seleccionar(ui.page); await datosDespacho(ui.page, "2000");
    await ui.page.getByRole("button", { name: "Confirmar despacho", exact: true }).click();
    await expect(ui.page.getByText("La disponibilidad cambió; vuelve a revisar la cantidad.", { exact: true })).toBeVisible();
    await expect(ui.page.getByLabel("Litros", { exact: true })).toBeEnabled();
    await ui.page.getByLabel("Litros", { exact: true }).fill("1000.01");
    await ui.page.getByRole("button", { name: "Confirmar despacho", exact: true }).click();
    await expect.poll(() => ui.solicitudes.length).toBe(2);
    expect(ui.solicitudes[0].operacion_id).not.toBe(ui.solicitudes[1].operacion_id);
    expect(ui.solicitudes[1].litros).toBe(1000.01);
    expect(ui.externos).toEqual([]); expect(ui.desconocidos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});

test("OP03: respuesta anterior no usa el físico como libre; actualizar recupera disponibilidad", async ({ browser }) => {
  const ui = await abrir(browser, "anterior");
  try {
    await seleccionar(ui.page);
    await expect(ui.page.getByRole("button", { name: "Despachar", exact: true })).toBeDisabled();
    await expect(ui.page.getByRole("alert")).toContainText("Disponibilidad desconocida");
    await ui.page.getByRole("button", { name: "Actualizar saldos", exact: true }).click();
    await expect(ui.page.getByRole("button", { name: "Despachar", exact: true })).toBeEnabled();
    expect(ui.solicitudes).toHaveLength(0);
    expect(ui.externos).toEqual([]); expect(ui.desconocidos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});

test("OP03: Bodega inmoviliza la carga incierta y recupera el traslado de 25 con el mismo UUID", async ({ browser }) => {
  const ui = await abrir(browser, "bodega");
  try {
    await ui.page.getByRole("combobox", { name: /^Destino/ }).selectOption("2");
    await ui.page.getByLabel("Cantidad (un)", { exact: true }).fill("25");
    await ui.page.getByRole("button", { name: "Revisar", exact: true }).click();
    await ui.page.getByRole("button", { name: "Registrar movimiento", exact: true }).click();
    await expect(ui.page.getByText("No se pudo registrar el movimiento.", { exact: true })).toBeVisible();
    await expect(ui.page.getByText("No sabemos si se confirmó. Reintenta la misma operación para recuperar el resultado antes de cambiar datos.", { exact: true })).toBeVisible();
    await expect(ui.page.getByRole("button", { name: "Volver y corregir", exact: true })).toBeDisabled();
    await expect(ui.page.getByLabel("Cantidad (un)", { exact: true })).toHaveCount(0);
    ui.page.once("dialog", async (dialog) => {
      expect(dialog.message()).toContain("no anula el traslado"); await dialog.dismiss();
    });
    await ui.page.getByRole("button", { name: "Cerrar movimiento", exact: true }).click();
    await expect(ui.page.getByRole("button", { name: "Volver y corregir", exact: true })).toBeDisabled();
    expect(ui.solicitudes).toHaveLength(1);
    await ui.page.getByRole("button", { name: "Recuperar resultado", exact: true }).click();
    await expect(ui.page.getByRole("status")).toContainText("Traslado registrado");
    expect(ui.solicitudes).toHaveLength(2); expect(ui.solicitudes[0]).toEqual(ui.solicitudes[1]);
    expect(ui.solicitudes[0].operacion_id).toMatch(CLAVE);
    expect(ui.solicitudes[0]).toMatchObject({ existencia: 51, destino: 2, cantidad: 25, motivo: "" });
    expect(ui.externos).toEqual([]); expect(ui.desconocidos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});

test("OP03: un 503 también inmoviliza el despacho hasta recuperar su resultado", async ({ browser }) => {
  const ui = await abrir(browser, "servidor");
  try {
    await seleccionar(ui.page); await datosDespacho(ui.page, "2000");
    await ui.page.getByRole("button", { name: "Confirmar despacho", exact: true }).click();
    await expect(ui.page.getByRole("alert")).toContainText("No sabemos si se confirmó");
    await expect(ui.page.getByLabel("Litros", { exact: true })).toBeDisabled();
    await ui.page.getByRole("button", { name: "Recuperar resultado", exact: true }).click();
    await expect(ui.page.getByRole("heading", { name: "8.000 L físicos", exact: true })).toBeVisible();
    expect(ui.solicitudes).toHaveLength(2); expect(ui.solicitudes[0]).toEqual(ui.solicitudes[1]);
    expect(ui.externos).toEqual([]); expect(ui.desconocidos).toEqual([]); expect(ui.errores).toEqual([]);
  } finally { await ui.context.close(); }
});
