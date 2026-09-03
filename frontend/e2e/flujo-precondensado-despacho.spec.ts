import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

import {
  analizarSilo,
  cerrarSegundaFirma,
  cerrarSesionesArea,
  elegirOpcion,
  irA,
  trasGuardar,
  usarSesionArea,
  vigilar,
} from "./ayudantes";

const RUTA_REGISTRO = path.resolve(
  process.env.E2E_REGISTRO ?? "e2e/.registro/flujo-precondensado.json",
);

test.describe.configure({ mode: "serial" });
test.afterAll(async () => {
  await cerrarSegundaFirma();
  await cerrarSesionesArea();
});

test("del precondensado liberado al despacho fisico desde su silo", async ({ page }) => {
  test.setTimeout(180_000);
  const erroresJs = vigilar(page);
  const flujo = JSON.parse(fs.readFileSync(RUTA_REGISTRO, "utf8")) as {
    lote: string;
    silo_precondensado: string;
    litros_precondensado: number;
  };
  const numeroDespacho = `DG-${flujo.lote.replace(/[^A-Z0-9]/gi, "-")}`;
  const reanudarDesde = Number(process.env.E2E_DESDE ?? 1);

  if (reanudarDesde <= 1) await test.step("1 · Calidad analiza y libera el precondensado para despacho", async () => {
    await usarSesionArea(page, "e2e_calidad");
    await analizarSilo(page, flujo.silo_precondensado, {
      grasa: "5.00",
      sng: "43.00",
    });
    await irA(page, "/calidad");

    const tarjeta = page.locator("article").filter({ hasText: flujo.lote });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await elegirOpcion(tarjeta.getByRole("combobox"), /conforme/i);
    await trasGuardar(page, "/liberar/", async () => {
      await tarjeta.getByRole("button", { name: "Liberar etapa" }).click();
    });
    await expect(tarjeta).toHaveCount(0);
  });

  if (reanudarDesde <= 2) await test.step("2 · Produccion identifica que el siguiente destino es Despacho", async () => {
    await usarSesionArea(page, "e2e_auditoria", "auditoria-e2e-ccaa");
    await irA(page, "/produccion");
    await page.getByRole("button", { name: "Consultar disponibles" }).click();
    const tarjeta = page.locator("article").filter({ hasText: flujo.lote });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await expect(tarjeta.getByRole("link", { name: /Preparar despacho/ })).toBeVisible();
    await tarjeta.getByRole("link", { name: /Preparar despacho/ }).click();
  });

  if (reanudarDesde <= 3) await test.step("3 · Despacho registra, autoriza y confirma la salida fisica", async () => {
    await usarSesionArea(page, "e2e_despacho");
    await irA(page, "/inventario");
    await page.getByRole("button", { name: "Despachar producto" }).click();
    const formulario = page.locator("form").filter({ hasText: "Despachar producto" });
    await formulario.getByPlaceholder("Nº de despacho").fill(numeroDespacho);

    const selectores = formulario.locator("select");
    await selectores.nth(0).selectOption({ index: 1 });
    await selectores.nth(1).selectOption("granel");
    await elegirOpcion(selectores.nth(2), new RegExp(flujo.lote));

    const cantidad = formulario.getByPlaceholder("Cantidad a despachar");
    await expect.poll(async () => Number(await cantidad.inputValue())).toBeGreaterThan(0);
    await trasGuardar(page, "/api/inventario/despachos/", async () => {
      await formulario.getByRole("button", { name: "Confirmar movimiento" }).click();
    });

    await page.getByRole("button", { name: "Despachos", exact: true }).click();
    const tarjeta = page.locator("article").filter({ hasText: numeroDespacho });
    await expect(tarjeta).toContainText(flujo.lote, { timeout: 20_000 });
    await trasGuardar(page, "/autorizar/", async () => {
      await tarjeta.getByRole("button", { name: "Autorizar" }).click();
    });
    await trasGuardar(page, "/ejecutar/", async () => {
      await tarjeta.getByRole("button", { name: "Confirmar salida" }).click();
    });
    await expect(tarjeta).toContainText("despachado");
  });

  expect(erroresJs).toHaveLength(0);
});
