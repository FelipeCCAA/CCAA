import { expect, test } from "@playwright/test";

import {
  campo,
  cerrarSesionesArea,
  elegirOpcion,
  irA,
  trasGuardar,
  usarSesionArea,
  vigilar,
} from "./ayudantes";

const HOY = new Date().toISOString().slice(0, 10);

test.afterAll(cerrarSesionesArea);

test("crema liberada se transforma en mantequilla y pasa por Calidad", async ({ page }) => {
  test.setTimeout(120_000);
  const erroresJs = vigilar(page);
  const crema = process.env.E2E_LOTE_CREMA ?? "INT-DES-2-CR";
  const lote = `MANT-E2E-${Date.now().toString().slice(-8)}`;

  await usarSesionArea(page, "e2e_produccion");
  await irA(page, "/procesos");
  await page.getByRole("button", { name: "Nueva corrida" }).click();
  const alta = page.locator("form").filter({ hasText: "Nueva corrida de mantequilla" });
  await elegirOpcion(campo(alta, "Orden de mantequilla"), /OP-E2E-MANT/);
  await elegirOpcion(campo(alta, "Lote de crema"), new RegExp(crema));
  await campo(alta, "Crema a utilizar (kg)").fill("60");
  await elegirOpcion(campo(alta, "Línea / equipo"), /Línea de mantequilla/i);
  await campo(alta, "Código nuevo lote de mantequilla").fill(lote);
  await elegirOpcion(campo(alta, "Lote de suero (si se medirá)"), /MAZ-E2E/);
  const creada = await trasGuardar(page, "/crear-guiada/", async () => {
    await alta.getByRole("button", { name: "Crear corrida" }).click();
  });
  const loteId = Number((await creada.json()).lote_mantequilla);

  const tarjeta = page.locator("article").filter({ hasText: lote });
  await trasGuardar(page, "/iniciar/", async () => {
    await tarjeta.getByRole("button", { name: "Iniciar con esta crema" }).click();
  });
  await tarjeta.getByRole("button", { name: "Registrar balance y cerrar" }).click();
  const cierre = page.locator("form").filter({ hasText: "Cerrar proceso de mantequilla" });
  await campo(cierre, "Mantequilla producida (kg)").fill("31");
  await campo(cierre, "Suero generado (kg)").fill("28");
  await campo(cierre, "Merma medida (kg)").fill("1");
  await campo(cierre, "Humedad (%)").fill("15.8");
  await trasGuardar(page, "/cerrar/", async () => {
    await cierre.getByRole("button", { name: "Cerrar y enviar a Calidad" }).click();
  });
  await expect(tarjeta).toContainText(/Calidad/);

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
  const calidad = page.locator("article").filter({ hasText: lote });
  await expect(calidad).toBeVisible({ timeout: 20_000 });
  await elegirOpcion(calidad.getByRole("combobox"), /conforme/i);
  await trasGuardar(page, "/liberar/", async () => {
    await calidad.getByRole("button", { name: "Liberar para Envasado" }).click();
  });
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
  await elegirOpcion(selectorEquipo, /Línea de mantequilla/i);
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
  await page.getByRole("button", { name: "Productos", exact: true }).click();
  const tarjeta = page.locator("article").filter({ hasText: pallet });
  await expect(tarjeta).toBeVisible({ timeout: 20_000 });
  await expect(tarjeta).toContainText("20 kg");
  await expect(tarjeta).toContainText(/cuarentena/i);
  await expect(tarjeta).toContainText("PT-CUAR");
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
  await page.getByRole("button", { name: "Productos", exact: true }).click();
  const tarjeta = page.locator("article").filter({ hasText: pallet });
  await expect(tarjeta).toContainText("disponible", { timeout: 20_000 });
  await expect(tarjeta).toContainText("PT-DISP");
  expect(erroresJs).toHaveLength(0);
});
