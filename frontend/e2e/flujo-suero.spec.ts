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

test.describe.configure({ mode: "serial" });
test.afterAll(async () => cerrarSesionesArea());

test("suero externo termina como Big Bag disponible en Inventario", async ({ page }) => {
  test.setTimeout(240_000);
  const erroresJs = vigilar(page);
  const marca = Date.now().toString().slice(-10);
  const lote = process.env.E2E_LOTE_SUERO ?? `SUERO-POLVO-E2E-${marca}`;
  const bigBag = process.env.E2E_BIG_BAG_SUERO ?? `BB-SUERO-E2E-${marca}`;
  let loteId = Number(process.env.E2E_LOTE_ID_SUERO ?? 0);
  const soloInventario = process.env.E2E_SOLO_INVENTARIO === "1";

  if (!soloInventario) await test.step("1 · Secado consume un lote externo liberado", async () => {
    await usarSesionArea(page, "e2e_secado");
    await irA(page, "/secado");
    await page.getByRole("button", { name: "Alimentación externa" }).click();
    const modal = page.getByRole("dialog");
    await elegirOpcion(campo(modal, "Orden / producto"), /Suero en polvo E2E/i);
    await elegirOpcion(campo(modal, "Lote externo liberado"), /SUERO-EXTERNO-E2E/i);
    await elegirOpcion(campo(modal, "Torre"), /TOR-SUERO-E2E/i);
    await campo(modal, "Código lote de salida").fill(lote);
    await campo(modal, "Cantidad a alimentar").fill("800");
    const respuesta = await trasGuardar(page, "/iniciar-desde-inventario/", async () => {
      await modal.getByRole("button", { name: "Confirmar e iniciar Secado" }).click();
    });
    loteId = Number((await respuesta.json()).lote);
    expect(loteId).toBeGreaterThan(0);
    await expect(page.locator("article").filter({ hasText: lote })).toContainText("Equipo ocupado");
  });

  if (!soloInventario) await test.step("2 · El operador registra el balance físico", async () => {
    const tarjeta = page.locator("article").filter({ hasText: lote });
    await tarjeta.getByRole("button", { name: "Registrar balance y cerrar corrida" }).click();
    const modal = page.getByRole("dialog");
    await expect(campo(modal, "Alimentación medida")).toHaveValue("800.000");
    await campo(modal, "Sólidos de entrada").fill("90");
    await campo(modal, "Polvo obtenido").fill("700");
    await campo(modal, "Finos recuperados").fill("10");
    await campo(modal, "Merma registrada").fill("5");
    await campo(modal, "Temperatura de salida").fill("80");
    await expect(modal.getByText("Resumen del balance")).toBeVisible();
    await trasGuardar(page, "/cerrar/", async () => {
      await modal.getByRole("button", { name: "Confirmar balance y cerrar" }).click();
    });
    await page.getByRole("button", { name: /Esperando Calidad/ }).click();
    await expect(page.locator("article").filter({ hasText: lote })).toContainText("Esperar decisión de Calidad");
  });

  if (!soloInventario) await test.step("3 · Calidad analiza y libera el producto de Secado", async () => {
    await usarSesionArea(page, "e2e_calidad");
    await irA(page, `/calidad/expedientes?lote=${loteId}`);
    await page.getByRole("button", { name: "Agregar análisis" }).click();
    await page.getByPlaceholder("M-01").fill(`M-${marca}`);
    await campo(page, "Humedad").fill("5");
    await trasGuardar(page, "/analisis/", async () => {
      await page.getByRole("button", { name: "Registrar análisis" }).click();
    });
    await irA(page, "/calidad");
    const tarjeta = page.locator("article").filter({ hasText: lote });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await elegirOpcion(tarjeta.getByRole("combobox"), /conforme/i);
    await trasGuardar(page, "/liberar/", async () => {
      await tarjeta.getByRole("button", { name: "Liberar para Envasado" }).click();
    });
  });

  if (!soloInventario) await test.step("4 · Envase crea una unidad Big Bag de 700 kg", async () => {
    await usarSesionArea(page, "e2e_envasado");
    await irA(page, "/envasado");
    await page.getByRole("button", { name: new RegExp(lote) }).click();
    const formulario = page.locator("form").filter({ hasText: "Envasar en Big Bag" });
    await elegirOpcion(formulario.locator("select").first(), /ENV-SUERO-E2E/i);
    await formulario.getByPlaceholder("Código Big Bag").fill(bigBag);
    await expect(formulario).toContainText("1 × 700 kg = 700 kg");
    await trasGuardar(page, "/envases/", async () => {
      await formulario.getByRole("button", { name: "Crear Big Bag" }).click();
    });
    await expect(page.getByText(new RegExp(`${bigBag}.*700 kg`))).toBeVisible();
  });

  if (!soloInventario) await test.step("5 · Calidad libera y entrega la unidad a Bodega", async () => {
    await usarSesionArea(page, "e2e_calidad");
    await irA(page, `/calidad/expedientes?lote=${loteId}`);
    await expect(page.getByRole("heading", { name: lote })).toBeVisible({ timeout: 20_000 });
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
          const hoy = new Date().toISOString().slice(0, 10);
          const valor = tipo === "number"
            ? "5"
            : tipo === "date"
              ? hoy
              : tipo === "time"
                ? "12:00"
                : tipo === "datetime-local"
                  ? `${hoy}T12:00`
                  : "E2E conforme";
          await control.fill(valor);
        }
      }
      const recarga = page.waitForResponse((respuesta) =>
        respuesta.request().method() === "GET"
        && respuesta.url().includes(`/api/calidad/expedientes/${loteId}/`),
      );
      await trasGuardar(page, "/calidad/registros/", async () => {
        await modal.getByRole("button", { name: "Dar por completado" }).click();
      });
      await recarga;
      await expect(modal).toHaveCount(0);
    }
    const liberar = page.getByRole("button", { name: "Liberar", exact: true });
    await expect(liberar).toBeEnabled({ timeout: 20_000 });
    await trasGuardar(page, `/expedientes/${loteId}/liberar/`, async () => liberar.click());
    const enviar = page.getByRole("button", { name: "Enviar pallets a Bodega" });
    await trasGuardar(page, `/expedientes/${loteId}/enviar-bodega/`, async () => enviar.click());
  });

  await test.step("6 · Inventario identifica Big Bag, lote y peso", async () => {
    await usarSesionArea(page, "e2e_inventario");
    await irA(page, "/inventario");
    await page.getByRole("button", { name: "Productos", exact: true }).click();
    const tarjeta = page.locator("article").filter({ hasText: bigBag });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await expect(tarjeta).toContainText("Big Bag");
    await expect(tarjeta).toContainText(lote);
    await expect(tarjeta).toContainText("700 kg");
    await expect(tarjeta).toContainText("disponible");
  });

  expect(erroresJs).toHaveLength(0);
});
