import { expect, test, type Page } from "@playwright/test";

import {
  campo,
  cerrarSesionesArea,
  elegirOpcion,
  irA,
  trasGuardar,
  usarSesionArea,
  vigilar,
} from "./ayudantes";
import { API } from "./constantes";

const HOY = new Date().toISOString().slice(0, 10);

test.describe.configure({ mode: "serial" });
test.afterAll(cerrarSesionesArea);

/*
  El código de una corrida como texto exacto: `EJ-MANT-31` no debe acertarle
  a `EJ-MANT-311` de una corrida anterior en la misma base. El código lo
  asigna el servidor (`EJ-MANT-{lote}`): no trae caracteres especiales.
*/
function exacto(codigo: string): RegExp {
  return new RegExp(`${codigo}(?!\\d)`);
}

interface PuestoLeido {
  cremas: { id: number; codigo: string; disponible_kg: string }[];
  mantequeras: { equipo_id: number; nombre: string; estado: string; motivos_para_tomar: string[] }[];
}

/* `page.request` no pasa por axios: la cabecera va a mano, con el token de la
   sesión que acaba de quedar en `localStorage`. */
async function leerPuesto(page: Page): Promise<PuestoLeido> {
  const token = await page.evaluate(
    () => JSON.parse(localStorage.getItem("ccaa.sesion") ?? "{}").token,
  );
  const respuesta = await page.request.get(`${API}/api/procesos/mantequillas/puesto/`, {
    headers: { Authorization: `Token ${token}` },
  });
  expect(respuesta.ok(), `No se pudo leer el puesto de Mantequilla (HTTP ${respuesta.status()}).`).toBeTruthy();
  return await respuesta.json() as PuestoLeido;
}

/*
  Elige la crema entre lo que **sirve el puesto** (liberada y con disponible),
  como `flujo-descremado` elige sus TK: un código escrito en la prueba deja de
  existir en cuanto la base usa otros. `E2E_LOTE_CREMA`, si viene, manda.
*/
async function elegirCrema(page: Page, kg: number) {
  await usarSesionArea(page, "e2e_produccion");
  const puesto = await leerPuesto(page);
  const pedida = process.env.E2E_LOTE_CREMA;
  const crema = puesto.cremas
    .filter((item) => (!pedida || item.codigo === pedida) && Number(item.disponible_kg) >= kg)
    .sort((a, b) => Number(b.disponible_kg) - Number(a.disponible_kg))[0];
  expect(
    crema,
    `El puesto no ofrece una crema liberada con ${kg} kg disponibles. Ofrece: ` +
      `${puesto.cremas.map((item) => `${item.codigo} ${item.disponible_kg} kg`).join(" · ") || "ninguna"}. ` +
      "Corre flujo-descremado (deja crema liberada en un TK) o libera una crema en Calidad.",
  ).toBeTruthy();
  expect(
    puesto.mantequeras.some((item) => item.estado === "disponible" && item.motivos_para_tomar.length === 0),
    "No hay una mantequera disponible: cancela desde el puesto la preparación que la retiene.",
  ).toBeTruthy();
  return crema!;
}

/*
  Prepara desde el formulario del puesto, ya abierto. La tarjeta se busca
  después por el `ejecucion_codigo` que devuelve `crear-guiada`, no por un
  código tecleado.
*/
async function preparar(page: Page, crema: { id: number }, { kg, conMazada }: { kg: string; conMazada: boolean }) {
  const dialogo = page.getByRole("dialog", { name: "Preparar mantequilla" });
  await expect(dialogo).toBeVisible({ timeout: 20_000 });
  await expect(campo(dialogo, "Crema")).toHaveValue(String(crema.id));
  await campo(dialogo, "Crema a utilizar (kg)").fill(kg);
  await elegirOpcion(campo(dialogo, "Orden de mantequilla"), /OP-E2E-MANT/);
  await elegirOpcion(campo(dialogo, "Mantequera"), /mantequ/i);
  if (conMazada) {
    await elegirOpcion(campo(dialogo, "Lote de suero / mazada (opcional)"), /MAZ-E2E/);
  }
  // El código lo sugiere el servidor (sigla de la mantequera y fecha de hoy).
  await expect(campo(dialogo, "Código del lote de mantequilla")).not.toHaveValue("", { timeout: 10_000 });
  await dialogo.getByRole("button", { name: "Revisar y confirmar" }).click();
  const respuesta = await trasGuardar(page, "/crear-guiada/", async () => {
    await dialogo.getByRole("button", { name: "Preparar mantequilla" }).click();
  });
  const creada = await respuesta.json();
  return {
    codigo: String(creada.ejecucion_codigo),
    loteId: Number(creada.lote_mantequilla),
    lote: String(creada.mantequilla_codigo),
    mantequera: String(creada.equipo_nombre),
  };
}

test("crema liberada se prepara, se inicia y se cierra en el puesto de Mantequilla", async ({ page }) => {
  test.setTimeout(180_000);
  const erroresJs = vigilar(page);
  let crema = { id: 0, codigo: "" };
  let corrida = { codigo: "", loteId: 0, lote: "", mantequera: "" };

  await test.step("1 · Producción llega desde Salidas intermedias con la crema elegida", async () => {
    crema = await elegirCrema(page, 60);
    await irA(page, "/produccion");
    await page.getByRole("button", { name: "Consultar disponibles" }).click();
    const tarjeta = page.locator("article").filter({ hasText: exacto(crema.codigo) }).first();
    const enlace = tarjeta.getByRole("link", { name: "Preparar en Mantequilla" });
    await expect(enlace).toBeVisible({ timeout: 20_000 });
    await enlace.click();
    await expect(page).toHaveURL(new RegExp(`#/produccion/mantequilla\\?crema=${crema.id}$`));
  });

  await test.step("2 · Prepara con la mazada y el código sugerido", async () => {
    corrida = await preparar(page, crema, { kg: "60", conMazada: true });
  });

  await test.step("3 · «Iniciar mantequilla» habilitado por el servidor; inicia", async () => {
    const tarjeta = page.getByRole("article").filter({ hasText: exacto(corrida.codigo) });
    await expect(tarjeta).toContainText("Preparada", { timeout: 20_000 });
    const iniciar = tarjeta.getByRole("button", { name: "Iniciar mantequilla" });
    await expect(iniciar).toBeEnabled({ timeout: 20_000 });
    await trasGuardar(page, "/iniciar/", async () => iniciar.click());
    await expect(tarjeta).toContainText("En curso", { timeout: 20_000 });
  });

  await test.step("4 · El balance lo dice el servidor mientras se teclea; se cierra", async () => {
    const tarjeta = page.getByRole("article").filter({ hasText: exacto(corrida.codigo) });
    await tarjeta.getByRole("button", { name: "Registrar balance y cerrar" }).click();
    const dialogo = page.getByRole("dialog", { name: "Registrar balance y cerrar" });
    const balance = dialogo.getByRole("region", { name: "Balance del cierre" });
    await campo(dialogo, "Mantequilla producida (kg)").fill("31");
    await campo(dialogo, "Suero / mazada recuperada (kg)").fill("28");
    await expect(balance).toContainText("Balance incompleto", { timeout: 10_000 });
    await expect(balance).toContainText(/1\.000 kg faltan por clasificar/);
    await expect(dialogo.getByRole("button", { name: "Revisar cierre" })).toBeDisabled();

    await campo(dialogo, "Merma medida (kg)").fill("1");
    await campo(dialogo, "Humedad (%)").fill("15.8");
    await expect(balance).toContainText("Balance completo", { timeout: 10_000 });
    await dialogo.getByRole("button", { name: "Revisar cierre" }).click();
    await trasGuardar(page, "/cerrar/", async () => {
      await dialogo.getByRole("button", { name: "Cerrar y enviar a Calidad" }).click();
    });
    const hoy = page.getByRole("region", { name: "Corridas de hoy" });
    await expect(hoy.getByRole("listitem").filter({ hasText: exacto(corrida.codigo) })).toContainText("Esperando Calidad");
  });

  await test.step("5 · Calidad libera la mantequilla", async () => {
    await usarSesionArea(page, "e2e_calidad");
    await irA(page, `/calidad/expedientes?lote=${corrida.loteId}`);
    await page.getByRole("button", { name: "Agregar análisis" }).click();
    await page.getByPlaceholder("M-01").fill(`M-${corrida.lote}`);
    await campo(page, "Materia grasa").fill("82.0");
    await campo(page, "Humedad").fill("15.8");
    await campo(page, "Sólidos no grasos").fill("1.5");
    await trasGuardar(page, "/analisis/", async () => {
      await page.getByRole("button", { name: "Registrar análisis" }).click();
    });
    await irA(page, "/calidad");
    const calidad = page.locator("article").filter({ hasText: corrida.lote });
    await expect(calidad).toBeVisible({ timeout: 20_000 });
    await elegirOpcion(calidad.getByRole("combobox"), /conforme/i);
    await trasGuardar(page, "/liberar/", async () => {
      await calidad.getByRole("button", { name: "Liberar para Envasado" }).click();
    });
  });

  test.info().annotations.push({
    type: "mantequilla",
    description: `E2E_MANTEQUILLA_ID=${corrida.loteId} E2E_MANTEQUILLA_LOTE=${corrida.lote}`,
  });
  expect(erroresJs).toHaveLength(0);
});

test("una preparación cancelada anula su lote y suelta la mantequera", async ({ page }) => {
  test.setTimeout(120_000);
  const erroresJs = vigilar(page);

  const crema = await elegirCrema(page, 10);
  await irA(page, `/produccion/mantequilla?crema=${crema.id}`);
  const corrida = await preparar(page, crema, { kg: "10", conMazada: false });

  const tarjeta = page.getByRole("article").filter({ hasText: exacto(corrida.codigo) });
  await expect(tarjeta).toContainText("Preparada", { timeout: 20_000 });
  await tarjeta.getByRole("button", { name: "Cancelar preparación" }).click();
  const dialogo = page.getByRole("dialog", { name: `Cancelar la preparación ${corrida.codigo}` });
  await dialogo.getByLabel("Motivo de la cancelación").fill("Prueba E2E: se preparó la crema equivocada.");
  await dialogo.getByRole("button", { name: "Revisar cancelación" }).click();
  await expect(dialogo).toContainText(`Se anulará el lote ${corrida.lote}`);
  await trasGuardar(page, "/cancelar-preparacion/", async () => {
    await dialogo.getByRole("button", { name: "Cancelar preparación" }).click();
  });

  await expect(page.getByRole("status").filter({ hasText: corrida.codigo })).toContainText("la mantequera libre");
  await expect(page.getByRole("article").filter({ hasText: exacto(corrida.codigo) })).toHaveCount(0);
  const mantequera = page.getByRole("article", { name: corrida.mantequera });
  await expect(mantequera).toContainText("Disponible");

  const token = await page.evaluate(
    () => JSON.parse(localStorage.getItem("ccaa.sesion") ?? "{}").token,
  );
  const lote = await page.request.get(`${API}/api/produccion/lotes/${corrida.loteId}/`, {
    headers: { Authorization: `Token ${token}` },
  });
  expect(lote.ok()).toBeTruthy();
  expect((await lote.json()).estado).toBe("anulado");
  expect(erroresJs).toHaveLength(0);
});

test("reanuda solamente la Calidad de una mantequilla ya cerrada", async ({ page }) => {
  const loteId = Number(process.env.E2E_MANTEQUILLA_ID);
  const lote = process.env.E2E_MANTEQUILLA_LOTE;
  test.skip(!loteId || !lote, "Define el lote cerrado que se quiere reanudar.");

  await usarSesionArea(page, "e2e_calidad");
  await irA(page, `/calidad/expedientes?lote=${loteId}`);
  await page.getByRole("button", { name: "Agregar análisis" }).click();
  await page.getByPlaceholder("M-01").fill(`M-${lote}`);
  await campo(page, "Materia grasa").fill("82.0");
  await campo(page, "Humedad").fill("15.8");
  await campo(page, "Sólidos no grasos").fill("1.5");
  await trasGuardar(page, "/analisis/", async () => {
    await page.getByRole("button", { name: "Registrar análisis" }).click();
  });
  await irA(page, "/calidad");
  const calidad = page.locator("article").filter({ hasText: lote! });
  await elegirOpcion(calidad.getByRole("combobox"), /conforme/i);
  await trasGuardar(page, "/liberar/", async () => {
    await calidad.getByRole("button", { name: "Liberar para Envasado" }).click();
  });
});

test("envasa solamente cajas completas y deja visible el remanente", async ({ page }) => {
  test.setTimeout(120_000);
  const loteId = Number(process.env.E2E_MANTEQUILLA_ID);
  const lote = process.env.E2E_MANTEQUILLA_LOTE;
  test.skip(!loteId || !lote, "Define la mantequilla liberada que se quiere envasar.");
  const pallet = `PAL-${lote}`;
  const erroresJs = vigilar(page);

  await usarSesionArea(page, "e2e_envasado");
  await irA(page, "/envasado");
  await page.getByRole("button", { name: new RegExp(lote!) }).click();
  await expect(page.getByText(/1 unidad\(es\) completa\(s\).*20 kg.*11 kg/)).toBeVisible();

  const formulario = page.locator("form").filter({ hasText: "Envasar en pallet" });
  const selectorEquipo = formulario.locator("select").first();
  await elegirOpcion(selectorEquipo, /Envasadora de mantequilla/i);
  await formulario.getByPlaceholder("Código pallet").fill(pallet);
  await expect(formulario.locator('input[type="number"]').first()).toHaveValue("1");
  const respuesta = await trasGuardar(page, "/envases/", async () => {
    await formulario.getByRole("button", { name: "Crear pallet" }).click();
  });
  const creado = await respuesta.json();
  expect(creado.pallets[0]).toMatchObject({ codigo: pallet, unidades: 1, kg_neto: "20.000" });

  await expect(page.getByText(/Quedan 11\.000 kg, menos que una unidad completa/)).toBeVisible();
  await expect(page.getByText(new RegExp(`${pallet}.*20(?:\\.000)? kg`))).toBeVisible();

  await usarSesionArea(page, "e2e_inventario");
  await irA(page, "/inventario");
  await page.getByRole("tab", { name: "Producto terminado" }).click();
  await page.getByLabel("Pallet, lote o producto").fill(pallet);
  await page.getByRole("button", { name: "Filtrar" }).click();
  const fila = page.getByRole("row").filter({ hasText: pallet });
  await expect(fila).toBeVisible({ timeout: 20_000 });
  await expect(fila).toContainText("20 kg");
  await expect(fila).toContainText(/cuarentena/i);
  await expect(fila).toContainText("PT-CUAR");
  expect(erroresJs).toHaveLength(0);
});

test("Calidad dispone el excedente y entrega el pallet de mantequilla a Bodega", async ({ page }) => {
  test.setTimeout(120_000);
  const loteId = Number(process.env.E2E_MANTEQUILLA_ID);
  const lote = process.env.E2E_MANTEQUILLA_LOTE;
  test.skip(!loteId || !lote, "Define la mantequilla envasada que se quiere liberar.");
  const pallet = `PAL-${lote}`;
  const erroresJs = vigilar(page);

  await usarSesionArea(page, "e2e_calidad");
  await irA(page, "/calidad");
  const excedente = page.locator("div.rounded-lg").filter({ hasText: lote! }).filter({
    has: page.getByRole("button", { name: "Resolver excedente" }),
  });
  await expect(excedente).toBeVisible({ timeout: 20_000 });
  await excedente.getByRole("button", { name: "Resolver excedente" }).click();
  const formularioRework = page.locator("form").filter({
    has: page.getByRole("button", { name: "Confirmar disposición" }),
  });
  await expect(formularioRework.getByRole("spinbutton", { name: "Cantidad segregada (kg)" })).toHaveValue("11");
  await formularioRework.getByRole("textbox", { name: "Observación de Calidad" }).fill("Excedente segregado e identificado para rework autorizado.");
  await trasGuardar(page, "/rework/", async () => {
    await formularioRework.getByRole("button", { name: "Confirmar disposición" }).click();
  });

  await irA(page, `/calidad/expedientes?lote=${loteId}`);
  await expect(page.getByRole("heading", { name: lote! })).toBeVisible({ timeout: 20_000 });
  for (;;) {
    const pendiente = page.locator("li").filter({ hasText: /campos por llenar|Sin completar|En borrador/ }).first();
    if (await pendiente.count() === 0) break;
    await pendiente.getByRole("button").click();
    const modal = page.locator(".fixed").filter({ has: page.getByRole("button", { name: "Dar por completado" }) });
    for (const control of await modal.locator("input:not([disabled]), select:not([disabled]), textarea:not([disabled])").all()) {
      const tipo = await control.getAttribute("type");
      if (tipo === "checkbox") await control.check();
      else if (await control.evaluate((elemento) => elemento.tagName === "SELECT")) await control.selectOption({ index: 1 });
      else if (!(await control.inputValue())) {
        const valor = tipo === "number" ? "1" : tipo === "date" ? HOY : tipo === "time" ? "12:00" : tipo === "datetime-local" ? `${HOY}T12:00` : "E2E conforme";
        await control.fill(valor);
      }
    }
    const recarga = page.waitForResponse((respuesta) => respuesta.request().method() === "GET" && respuesta.url().includes(`/api/calidad/expedientes/${loteId}/`));
    await trasGuardar(page, "/calidad/registros/", async () => {
      await modal.getByRole("button", { name: "Dar por completado" }).click();
    });
    await recarga;
  }

  const liberar = page.getByRole("button", { name: "Liberar", exact: true });
  await expect(liberar).toBeEnabled({ timeout: 20_000 });
  await trasGuardar(page, `/expedientes/${loteId}/liberar/`, async () => liberar.click());
  const enviar = page.getByRole("button", { name: "Enviar pallets a Bodega" });
  await expect(enviar).toBeVisible();
  await trasGuardar(page, `/expedientes/${loteId}/enviar-bodega/`, async () => enviar.click());

  await usarSesionArea(page, "e2e_inventario");
  await irA(page, "/inventario");
  await page.getByRole("tab", { name: "Producto terminado" }).click();
  await page.getByLabel("Pallet, lote o producto").fill(pallet);
  await page.getByRole("button", { name: "Filtrar" }).click();
  const fila = page.getByRole("row").filter({ hasText: pallet });
  await expect(fila).toContainText(/disponible/i, { timeout: 20_000 });
  await expect(fila).toContainText("PT-DISP");
  expect(erroresJs).toHaveLength(0);
});
