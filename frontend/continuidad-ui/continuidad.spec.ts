import { expect, test, type Page } from "@playwright/test";
const ORIGEN = "http://127.0.0.1:5247";
const MENSAJE = "Producción con Calidad pendiente: se puede continuar; la liberación final sigue siendo obligatoria.";
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
async function preparar(page: Page, opciones: { politica?: boolean; fallaPolitica?: boolean; habilitado?: boolean; rol?: string; rechazar?: boolean } = {}) {
  const usuario = { id: 900, username: "operador-local", nombre: "Operador", apellido: "Local", email: "", rol: opciones.rol ?? "produccion", capacidades: [], perfil: null };
  const pedidos: unknown[] = [], externas: string[] = [], errores: string[] = [];
  let continuado = false;
  const vale = () => ({ ...VALE, continuidad_pendiente_disponible: (opciones.habilitado ?? true) && !continuado,
    avisos_calidad: ["Firma de Calidad pendiente"], balance: { ...VALE.balance, volumen_medido: "10000.00", diferencia: "0.00", pendiente: false } });
  page.on("pageerror", error => errores.push(error.message));
  await page.addInitScript(cuenta => sessionStorage.setItem("ccaa.sesion", JSON.stringify({ token: "simulado-local", usuario: cuenta })), usuario);
  await page.route("**/*", async route => {
    const url = new URL(route.request().url()), ruta = url.pathname;
    if (url.origin !== ORIGEN) { externas.push(url.origin); await route.abort(); return; }
    if (!ruta.startsWith("/api/")) { await route.continue(); return; }
    const responder = (data: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    if (ruta === "/api/usuarios/yo/") { await responder(usuario); return; }
    if (ruta === "/api/calidad/politica-continuidad/") { await responder({ avisos_intermedios: opciones.politica ?? true, mensaje: MENSAJE }, opciones.fallaPolitica ? 503 : 200); return; }
    if (ruta === "/api/estandarizacion/vales/71/continuar-pendiente/") {
      pedidos.push({ metodo: route.request().method(), cuerpo: route.request().postDataJSON() });
      if (opciones.rechazar) { await responder({ detail: "El balance cambió; actualiza el vale." }, 409); return; }
      continuado = true; await responder(vale()); return;
    }
    if (ruta === "/api/estandarizacion/vales/") { await responder({ results: [vale()] }); return; }
    if (ruta === "/api/estandarizacion/vales/catalogos/") { await responder({ silos: [], estados: [], transiciones: {}, minutos_agitacion: 15 }); return; }
    if (ruta === "/api/estandarizacion/vales/guia-rc/") { await responder([]); return; }
    if (ruta === "/api/produccion/envases/bandeja/") {
      await responder({ materiales: [{ salida_id: 9, lote_id: 8, lote_codigo: "ENV-PENDIENTE", producto_nombre: "Polvo",
        cantidad_disponible: "500", pallets_total: 0, unidad: "kg", formato_id: 6, formato_nombre: "Saco 25 kg", formato_kg: "25",
        tipo_unidad_logistica: "pallet", tipo_unidad_logistica_etiqueta: "Pallet", maximo_unidad_logistica_kg: "500",
        unidades_por_producto: 20, unidades_disponibles: 0, cantidad_envasable: "0", remanente_kg: "0", equipos: [], materiales_envase: [],
        puede_envasar: false, calidad: "pendiente", avisos_calidad: ["Análisis de Secado pendiente"], motivo_bloqueo: "Falta stock de embalajes", advertencia_materiales: "" }],
        bloqueados_calidad: [], registros_recientes: [] }); return;
    }
    await responder({ results: [], count: 0 });
  });
  return { pedidos, externas, errores };
}
test("banner y continuidad auditada conservan el vale muestreado y sus avisos", async ({ page }, testInfo) => {
  const ui = await preparar(page);
  await page.goto("/#/estandarizacion");
  await expect(page.getByText(MENSAJE, { exact: true })).toBeVisible();
  await expect(page.getByText("Firma de Calidad pendiente", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Continuar con Calidad pendiente", exact: true }).click();
  await expect(page.getByText("Continuidad registrada con Calidad pendiente. La liberación final sigue siendo obligatoria antes del despacho.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continuar con Calidad pendiente", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /OP02-UI-LOCAL muestreado/ })).toBeVisible();
  expect(ui.pedidos).toEqual([{ metodo: "POST", cuerpo: { motivo: "Continuidad operacional con Calidad pendiente" } }]);
  expect(ui.externas).toEqual([]); expect(ui.errores).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("continuidad-pendiente.png"), fullPage: true });
});
for (const caso of [{ nombre: "política desactivada", politica: false }, { nombre: "política sin respuesta", fallaPolitica: true }]) {
  test(`no presume política activa: ${caso.nombre}`, async ({ page }) => {
    await preparar(page, { ...caso, habilitado: false }); await page.goto("/#/estandarizacion");
    await expect(page.getByRole("heading", { name: "Ciclo del vale" })).toBeVisible();
    await expect(page.getByText(MENSAJE, { exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Continuar con Calidad pendiente", exact: true })).toHaveCount(0);
  });
}
test("una cuenta sin permiso operacional no recibe la acción aunque el servidor envíe el flag", async ({ page }) => {
  await preparar(page, { rol: "calidad" }); await page.goto("/#/estandarizacion");
  await expect(page.getByRole("heading", { name: "Ciclo del vale" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continuar con Calidad pendiente", exact: true })).toHaveCount(0);
});
test("un rechazo del servidor conserva el pendiente y muestra su motivo", async ({ page }) => {
  const ui = await preparar(page, { rechazar: true }); await page.goto("/#/estandarizacion");
  await page.getByRole("button", { name: "Continuar con Calidad pendiente", exact: true }).click();
  await expect(page.getByText("El balance cambió; actualiza el vale.", { exact: true })).toBeVisible();
  await expect(page.getByText(/Continuidad registrada/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: /OP02-UI-LOCAL muestreado/ })).toBeVisible(); expect(ui.pedidos).toHaveLength(1);
});
test("Envase muestra pendiente habilitado y conserva bloqueo por stock", async ({ page }) => {
  const ui = await preparar(page, { rol: "admin" }); await page.goto("/#/envasado");
  const material = page.getByRole("button", { name: /ENV-PENDIENTE/ });
  await expect(material).toContainText("Calidad pendiente"); await expect(material).toContainText("Análisis de Secado pendiente"); await material.click();
  await expect(page.getByText("Falta stock de embalajes", { exact: true })).toBeVisible();
  await expect(page.locator("form")).toHaveCount(0); await expect(page.getByText("Calidad liberada", { exact: false })).toHaveCount(0);
  expect(ui.externas).toEqual([]); expect(ui.errores).toEqual([]);
});
