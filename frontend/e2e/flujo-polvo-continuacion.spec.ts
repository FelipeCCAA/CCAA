import { expect, test } from "@playwright/test";
import fs from "node:fs";

import {
  analizarSilo,
  campo,
  cerrarSegundaFirma,
  cerrarSesionesArea,
  elegirOpcion,
  irA,
  trasGuardar,
  usarSesionArea,
  vigilar,
} from "./ayudantes";
import { RUTA_FLUJO_POLVO } from "./constantes";

const HOY = new Date().toISOString().slice(0, 10);

test.describe.configure({ mode: "serial" });
test.afterAll(async () => {
  await cerrarSegundaFirma();
  await cerrarSesionesArea();
});

test("del precondensado liberado al pallet disponible en Inventario", async ({ page }) => {
  test.setTimeout(240_000);
  const erroresJs = vigilar(page);
  const flujo = JSON.parse(fs.readFileSync(RUTA_FLUJO_POLVO, "utf8")) as {
    lote: string;
    silo_precondensado: string;
    litros_precondensado: number;
  };
  const pallet = `PAL-${flujo.lote.replace("CCAA-EVA-", "")}`;
  const reanudarDesde = Number(process.env.E2E_DESDE ?? 1);
  let loteId = Number(process.env.E2E_LOTE_ID ?? 0);

  if (reanudarDesde <= 1) await test.step("1 · Calidad analiza y libera el precondensado", async () => {
    await usarSesionArea(page, "e2e_calidad");
    await analizarSilo(page, flujo.silo_precondensado, { grasa: "7.00", sng: "42.00" });
    await irA(page, "/calidad");

    const tarjeta = page.locator("article").filter({ hasText: flujo.lote });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await expect(tarjeta).toContainText("Leche entera en polvo");
    await elegirOpcion(tarjeta.getByRole("combobox"), /conforme/i);
    await trasGuardar(page, "/liberar/", async () => {
      await tarjeta.getByRole("button", { name: "Liberar etapa" }).click();
    });
    await expect(tarjeta).toHaveCount(0);
  });

  if (reanudarDesde <= 2) await test.step("2 · Secado toma la siguiente etapa de la ruta", async () => {
    await usarSesionArea(page, "e2e_secado");
    await irA(page, "/produccion");
    await page.getByRole("button", { name: "Consultar disponibles" }).click();
    const tarjeta = page.locator("article").filter({ hasText: flujo.lote });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await expect(tarjeta).toContainText("Secado");
    await tarjeta.getByRole("button", { name: /Continuar a Secado/ }).click();
    await expect(tarjeta.getByRole("combobox", { name: "Máquina" })).toContainText(/disponible/i);
    const respuesta = await trasGuardar(page, "/preparar-continuacion/", async () => {
      await tarjeta.getByRole("button", { name: "Confirmar preparación" }).click();
    });
    const ejecucion = await respuesta.json();

    await irA(page, "/procesos");
    const fila = page.getByRole("row", { name: new RegExp(ejecucion.codigo) });
    await expect(fila).toBeVisible({ timeout: 20_000 });
    await trasGuardar(page, "/transicionar/", async () => {
      await fila.getByRole("button", { name: "Iniciar" }).click();
    });
  });

  if (reanudarDesde <= 3) await test.step("3 · Secado registra un balance válido", async () => {
    await irA(page, "/secado");
    const tarjeta = page.locator("article").filter({ hasText: flujo.lote });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await tarjeta.getByRole("button", { name: "Registrar balance y cerrar corrida" }).click();
    const cierre = page.getByRole("dialog");
    await campo(cierre, "Alimentación medida").fill("1500");
    await campo(cierre, "Sólidos de entrada").fill("48");
    await campo(cierre, "Polvo obtenido").fill("500");
    await campo(cierre, "Finos recuperados").fill("10");
    await campo(cierre, "Merma registrada").fill("5");
    await campo(cierre, "Temperatura de salida").fill("82");
    await expect(cierre.getByText("Resumen del balance")).toBeVisible();
    const respuesta = await trasGuardar(page, "/cerrar/", async () => {
      await cierre.getByRole("button", { name: "Confirmar balance y cerrar" }).click();
    });
    const corrida = await respuesta.json();
    loteId = Number(corrida.lote);
    expect(loteId).toBeGreaterThan(0);
    await expect(page.getByRole("button", { name: /Esperando Calidad/ })).toContainText(/[1-9]\d*/);
  });

  if (reanudarDesde <= 4) await test.step("4 · Calidad analiza y libera el polvo", async () => {
    await usarSesionArea(page, "e2e_calidad");
    await irA(page, `/calidad/expedientes?lote=${loteId}`);
    await page.getByRole("button", { name: "Agregar análisis" }).click();
    await page.getByPlaceholder("M-01").fill(`M-${flujo.lote}`);
    await campo(page, "Humedad").fill("3");
    await trasGuardar(page, "/analisis/", async () => {
      await page.getByRole("button", { name: "Registrar análisis" }).click();
    });

    await irA(page, "/calidad");
    const tarjeta = page.locator("article").filter({ hasText: flujo.lote });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await elegirOpcion(tarjeta.getByRole("combobox"), /conforme/i);
    await trasGuardar(page, "/liberar/", async () => {
      await tarjeta.getByRole("button", { name: "Liberar para Envasado" }).click();
    });
  });

  if (reanudarDesde <= 5) await test.step("5 · Envase crea un pallet trazable de 500 kg", async () => {
    await usarSesionArea(page, "e2e_envasado");
    await irA(page, "/envasado");
    await page.getByRole("button", { name: new RegExp(flujo.lote) }).click();
    await expect(page.getByText("Esperando aprobación de Calidad")).toHaveCount(0);
    const formulario = page.locator("form").filter({ hasText: "Envasar en pallet" });
    const selectorEquipo = formulario.locator("select").first();
    await expect.poll(() => selectorEquipo.locator("option").count(), { timeout: 15_000 }).toBeGreaterThan(1);
    await selectorEquipo.selectOption({ index: 1 });
    await formulario.getByPlaceholder("Código pallet").fill(pallet);
    const respuesta = await trasGuardar(page, "/envases/", async () => {
      await formulario.getByRole("button", { name: "Crear pallet" }).click();
    });
    expect((await respuesta.json()).pallets[0].codigo).toBe(pallet);
    await expect(page.getByText(new RegExp(`${pallet}.*500 kg`))).toBeVisible();
  });

  if (reanudarDesde <= 6) await test.step("6 · Calidad libera el lote y entrega el pallet a Bodega", async () => {
    await usarSesionArea(page, "e2e_calidad");
    await irA(page, `/calidad/expedientes?lote=${loteId}`);
    await expect(page.getByRole("heading", { name: flujo.lote })).toBeVisible({ timeout: 20_000 });

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
          const valor = tipo === "number"
            ? "3"
            : tipo === "date"
              ? HOY
              : tipo === "time"
                ? "12:00"
                : tipo === "datetime-local"
                  ? `${HOY}T12:00`
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

    const enviar = page.getByRole("button", { name: "Enviar pallets a Bodega" });
    const liberar = page.getByRole("button", { name: "Liberar", exact: true });
    if (!(await enviar.count())) {
      await expect(liberar).toBeEnabled({ timeout: 20_000 });
      await trasGuardar(page, `/expedientes/${loteId}/liberar/`, async () => liberar.click());
    }
    await expect(enviar).toBeVisible({ timeout: 20_000 });
    await trasGuardar(page, `/expedientes/${loteId}/enviar-bodega/`, async () => enviar.click());
  });

  if (reanudarDesde <= 7) await test.step("7 · Inventario muestra el pallet disponible", async () => {
    await usarSesionArea(page, "e2e_inventario");
    await irA(page, "/inventario");
    await page.getByRole("button", { name: "Productos", exact: true }).click();
    const tarjeta = page.locator("article").filter({ hasText: pallet });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await expect(tarjeta).toContainText(flujo.lote);
    await expect(tarjeta).toContainText("500 kg");
    await expect(tarjeta).toContainText("disponible");
    await expect(tarjeta).toContainText("PT-DISP");
  });

  expect(erroresJs).toHaveLength(0);
});
