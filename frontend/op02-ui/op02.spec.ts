import { expect, test, type Browser, type Page } from "@playwright/test";

const BASE = "http://127.0.0.1:5189";
const CLAVE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SILOS = [
  { id: 1, codigo: "SILO-VALE", tipo: "silo", litros_disponibles: "10000.00", capacidad_l: "20000.00" },
  { id: 2, codigo: "SILO-ORIGEN", tipo: "silo", litros_disponibles: "100.00", capacidad_l: "20000.00" },
];
const VALE = {
  id: 71, codigo: "OP02-UI-LOCAL", fecha: "2026-10-20", producto: 1,
  producto_nombre: "Leche estandarizada", rc_objetivo: "0.4000", volumen: "10000.00",
  silo_entera: 2, silo_entera_codigo: "SILO-ORIGEN", silo_descremada: null,
  silo_descremada_codigo: null, silo_crema: null, silo_crema_codigo: null,
  silo_destino: 1, silo_destino_codigo: "SILO-VALE", litros_entera: "10000.00",
  litros_descremada: "0.00", litros_crema: "0.00", entera_grasa: "3.20", entera_sng: "8.00",
  descremada_grasa: null, descremada_sng: null, crema_grasa: null, crema_sng: null,
  estado: "muestreado", ejecutado_en: "2026-10-20T12:00:00Z",
  agitacion_desde: "2026-10-20T12:05:00Z", muestreado_en: "2026-10-20T12:20:00Z",
  grasa_real: "3.20", sng_real: "8.00", rc_real: 0.4, minutos_agitando: 15,
  avisos: [], evaluacion: null, observaciones: "", responsable_nombre: "Operador simulado",
  actualizado_en: "2026-10-20T12:20:00Z", es_borrador: false,
  balance: { componentes: "10000.00", volumen_ejecutado: "10000.00", volumen_medido: "9990.00", diferencia: "-10.00", pendiente: true },
  actos: [],
};

async function abrir(browser: Browser, rol: "recepcion" | "produccion") {
  const context = await browser.newContext({ baseURL: BASE, serviceWorkers: "block", viewport: { width: 1440, height: 1100 } });
  const externos: string[] = [];
  const desconocidos: string[] = [];
  const solicitudes: Record<string, unknown>[] = [];
  const errores: string[] = [];
  const page = await context.newPage();
  page.on("pageerror", (error) => errores.push(error.message));
  await page.addInitScript((rolLocal) => {
    sessionStorage.setItem("ccaa.sesion", JSON.stringify({ token: "op02-ui-simulado-sin-credenciales", usuario: {
      id: 900, username: "operador-simulado", nombre: "Operador", apellido: "Simulado", email: "", rol: rolLocal,
      capacidades: [], perfil: null,
    } }));
  }, rol);
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== BASE) { externos.push(url.origin); await route.abort(); return; }
    if (!url.pathname.startsWith("/api/")) { await route.continue(); return; }
    const responder = (json: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(json) });
    const ruta = url.pathname;
    if (ruta === "/api/estandarizacion/vales/71/actos/" && route.request().method() === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      solicitudes.push(body);
      const fisico = body.tipo === "adicion";
      await responder({ ...VALE, estado: fisico ? "corrigiendo" : "muestreado",
        ...(fisico ? { grasa_real: null, sng_real: null, rc_real: null, agitacion_desde: null, muestreado_en: null } : {}),
        balance: { ...VALE.balance, volumen_ejecutado: fisico ? "10000.01" : "10000.00",
          volumen_medido: fisico ? "9990.00" : "9900.00", diferencia: fisico ? "-10.00" : "-100.00", pendiente: true },
        actos: [{ ...body, litros: fisico ? "0.01" : null, silo_contraparte: fisico ? 2 : null,
          volumen_medido: fisico ? null : "9900.00", usuario_nombre: "Operador simulado", creado_en: "2026-10-20T12:30:00Z",
          rectificacion: fisico ? { volumen_ejecutado: ["10000.00", "10000.01"] }
            : { volumen_contable: "10000.00", diferencia: "-100.00" } }],
      }); return;
    }
    if (ruta === "/api/estandarizacion/vales/") { await responder({ results: [VALE] }); return; }
    if (ruta === "/api/estandarizacion/vales/catalogos/") { await responder({ silos: SILOS, estados: [], transiciones: {}, minutos_agitacion: 15 }); return; }
    if (ruta === "/api/estandarizacion/vales/guia-rc/") { await responder([]); return; }
    if (ruta === "/api/maestros/productos/") { await responder({ results: [] }); return; }
    if (ruta.includes("notificaciones")) { await responder({ results: [] }); return; }
    desconocidos.push(`${route.request().method()} ${ruta}`);
    await route.abort();
  });
  await page.goto("/#/estandarizacion");
  await expect(page.getByRole("heading", { name: "Balance y actos del vale" })).toBeVisible();
  return { context, page, externos, desconocidos, solicitudes, errores };
}

function panel(page: Page) {
  return page.locator("section").filter({ has: page.getByRole("heading", { name: "Balance y actos del vale" }) });
}

test("OP02: Recepción mide y ve retención; Producción registra 0,01 L y debe reagitar", async ({ browser }, testInfo) => {
  await test.step("Recepción registra 9900 L con UUID y conserva el bloqueo de liberación", async () => {
    const ui = await abrir(browser, "recepcion");
    try {
      const balance = panel(ui.page);
      await expect(balance.getByText("-10,00 L", { exact: true })).toBeVisible();
      await expect(balance.getByText("Diferencia registrada", { exact: true })).toBeVisible();
      await expect(balance.getByText(/Balance pendiente: liberación y despacho bloqueados/)).toBeVisible();
      await expect(ui.page.getByRole("button", { name: "Decidir", exact: true })).toHaveCount(0);
      await expect(balance.getByRole("option", { name: "Registrar adición física" })).toHaveCount(0);
      await balance.getByLabel("Volumen medido del vale (L)", { exact: true }).fill("9900.00");
      await balance.getByLabel("Motivo", { exact: true }).fill("Aforo local de prueba con diferencia");
      await balance.getByRole("button", { name: "Registrar volumen medido", exact: true }).click();
      await expect(balance.getByRole("status")).toContainText("Acto registrado");
      expect(ui.solicitudes).toHaveLength(1);
      expect(ui.solicitudes[0]).toEqual({ clave: expect.stringMatching(CLAVE), tipo: "medicion",
        motivo: "Aforo local de prueba con diferencia", volumen_medido: "9900.00" });
      await expect(balance.getByText("-100,00 L", { exact: true })).toBeVisible();
      await expect(balance.getByText("diferencia: -100.00", { exact: true })).toBeVisible();
      await expect(ui.page.getByRole("button", { name: "Decidir", exact: true })).toHaveCount(0);
      expect(ui.externos).toEqual([]); expect(ui.desconocidos).toEqual([]); expect(ui.errores).toEqual([]);
      await ui.page.screenshot({ path: testInfo.outputPath("op02-recepcion.png"), fullPage: true });
    } finally { await ui.context.close(); }
  });
  await test.step("Producción confirma autorización y registra adición sin afirmar ejecución física", async () => {
    const ui = await abrir(browser, "produccion");
    try {
      const balance = panel(ui.page);
      await expect(ui.page.getByRole("button", { name: "Corregir muestra anterior", exact: true })).toBeVisible();
      await ui.page.getByRole("button", { name: "Corregir muestra anterior", exact: true }).click();
      await expect(ui.page.getByRole("button", { name: "Guardar y recalcular", exact: true })).toBeVisible();
      await balance.getByRole("combobox", { name: "Acción", exact: true }).selectOption("adicion");
      await expect(balance.getByText("No realices movimientos si el sistema informa un bloqueo; registra cualquier diferencia medida para revisión.")).toBeVisible();
      await expect(balance.getByText("Confirmo que el movimiento físico fue realizado.")).toHaveCount(0);
      await balance.getByLabel("Litros del movimiento", { exact: true }).fill("0.01");
      await balance.getByRole("combobox", { name: "Silo de origen", exact: true }).selectOption("2");
      await balance.getByLabel("Motivo", { exact: true }).fill("Adición autorizada de prueba local");
      await balance.getByRole("checkbox", { name: "Confirmo la autorización de Producción, el origen, destino y litros de esta corrección." }).check();
      await balance.getByRole("button", { name: "Registrar adición física", exact: true }).click();
      await expect(balance.getByRole("status")).toContainText("Reagita, toma una nueva muestra");
      expect(ui.solicitudes).toHaveLength(1);
      expect(ui.solicitudes[0]).toEqual({ clave: expect.stringMatching(CLAVE), tipo: "adicion",
        motivo: "Adición autorizada de prueba local", litros: "0.01", silo_contraparte: 2 });
      await expect(balance.getByText("volumen_ejecutado: 10000.00 → 10000.01", { exact: true })).toBeVisible();
      await expect(balance.getByText("-10,00 L", { exact: true })).toBeVisible();
      await expect(balance.getByText("Medición y diferencia corresponden al momento de su registro; después de un movimiento puede ser necesario medir nuevamente.")).toBeVisible();
      await expect(ui.page.getByRole("button", { name: "Reagitar", exact: true })).toBeVisible();
      await expect(ui.page.getByRole("button", { name: "Corregir muestra anterior", exact: true })).toHaveCount(0);
      await expect(ui.page.getByRole("button", { name: "Guardar y recalcular", exact: true })).toHaveCount(0);
      await expect(ui.page.getByText("No hay una muestra vigente. Después de la corrección física, debes reagitar, registrar una nueva muestra y solicitar la decisión de Calidad.")).toBeVisible();
      await expect(ui.page.getByRole("button", { name: "Decidir", exact: true })).toHaveCount(0);
      expect(ui.externos).toEqual([]); expect(ui.desconocidos).toEqual([]); expect(ui.errores).toEqual([]);
      await ui.page.screenshot({ path: testInfo.outputPath("op02-produccion.png"), fullPage: true });
    } finally { await ui.context.close(); }
  });
});
