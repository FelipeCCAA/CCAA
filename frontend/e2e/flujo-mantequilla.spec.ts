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
