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

  if (reanudarDesde <= 3) await test.step("3 · Despacho arma, autoriza y ejecuta la hoja de carga", async () => {
    await usarSesionArea(page, "e2e_despacho");
    await irA(page, "/despacho");
    await page.getByRole("button", { name: "Nueva hoja de carga" }).click();
    await page.getByLabel("Cliente").selectOption({ index: 1 });
    const graneles = page.getByRole("group", { name: "Graneles liberados" });
    await graneles.getByRole("listitem").filter({ hasText: new RegExp(flujo.lote) }).getByRole("checkbox").check();
    await page.getByRole("button", { name: "Revisar hoja" }).click();
    await trasGuardar(page, "/api/inventario/despachos/", async () => {
      await page.getByRole("button", { name: "Guardar hoja" }).click();
    });

    const tarjeta = page.locator("article").filter({ hasText: flujo.lote });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await trasGuardar(page, "/autorizar/", async () => {
      await tarjeta.getByRole("button", { name: "Autorizar" }).click();
    });
    await tarjeta.getByRole("button", { name: "Ejecutar salida" }).click();
    await trasGuardar(page, "/ejecutar/", async () => {
      await tarjeta.getByRole("button", { name: "Confirmar salida" }).click();
    });
    await expect(page.getByRole("region", { name: "Despachadas hoy" })).toContainText(flujo.lote);
  });

  expect(erroresJs).toHaveLength(0);
});
