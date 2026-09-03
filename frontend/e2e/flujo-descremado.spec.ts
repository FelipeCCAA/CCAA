import { expect, test } from "@playwright/test";

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

test.describe.configure({ mode: "serial" });
test.afterAll(async () => {
  await cerrarSegundaFirma();
  await cerrarSesionesArea();
});

test("descremado separa, Calidad libera y conserva ambas rutas", async ({ page }) => {
  test.setTimeout(180_000);
  const erroresJs = vigilar(page);
  const siloOrigen = process.env.E2E_SILO_ENTERA ?? "Silo 3";
  const tkDescremada = process.env.E2E_TK_DESCREMADA ?? "Tk02";
  const tkCrema = process.env.E2E_TK_CREMA ?? "TkC2";
  const codigo = `DES-E2E-${Date.now().toString().slice(-8)}`;
  let rutaDescremar = "";

  await test.step("1 · Calidad confirma una muestra vigente del origen", async () => {
    await usarSesionArea(page, "e2e_calidad");
    await analizarSilo(page, siloOrigen, { grasa: "2.61", sng: "8.70" });
    const href = await page.getByRole("link", { name: "Descremar" }).getAttribute("href");
    rutaDescremar = new URL(href!, page.url()).hash.replace(/^#/, "");
  });

  let litrosDescremada = "";
  let litrosCrema = "";
  await test.step("2 · Producción revisa la sugerencia y confirma las reservas", async () => {
    await usarSesionArea(page, "e2e_produccion");
    await irA(page, rutaDescremar);

    const formulario = page.locator("form").filter({ hasText: "Iniciar descremación" });
    await expect(formulario).toBeVisible({ timeout: 20_000 });
    await campo(formulario, "Código de ejecución").fill(codigo);
    await elegirOpcion(campo(formulario, "Equipo"), /DES-01/i);
    await campo(formulario, "Litros de entrada").fill("1000");
    await elegirOpcion(campo(formulario, "Destino leche descremada"), new RegExp(tkDescremada, "i"));
    await elegirOpcion(campo(formulario, "TK fisico para crema"), new RegExp(tkCrema, "i"));

    await trasGuardar(page, "/sugerir-balance/", async () => {
      await formulario.getByRole("button", { name: "Calcular sugerencia" }).click();
    });
    litrosDescremada = await campo(formulario, "Descremada planificada (L)").inputValue();
    litrosCrema = await campo(formulario, "Crema planificada (L)").inputValue();
    expect(Number(litrosDescremada)).toBeGreaterThan(900);
    expect(Number(litrosCrema)).toBeGreaterThan(0);
    await formulario.getByRole("checkbox", { name: /Confirmo que revisé/ }).check();

    const creada = page.waitForResponse((r) => r.url().includes("/crear-guiada/") && r.request().method() === "POST");
    const iniciada = page.waitForResponse((r) => /\/descremaciones\/\d+\/iniciar\/$/.test(r.url()) && r.request().method() === "POST");
    await formulario.getByRole("button", { name: "Confirmar reservas e iniciar" }).click();
    expect((await creada).ok()).toBeTruthy();
    expect((await iniciada).ok()).toBeTruthy();
  });

  await test.step("3 · Producción registra las dos salidas físicas", async () => {
    const tarjeta = page.locator("article").filter({ hasText: codigo });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await tarjeta.getByRole("button", { name: "Registrar salidas y cerrar" }).click();
    const formulario = page.locator("form").filter({ hasText: "Cerrar descremación" });
    await campo(formulario, `Litros a ${tkDescremada}`).fill(litrosDescremada);
    await campo(formulario, "Grasa leche descremada (%)").fill("0.06");
    await campo(formulario, `Litros a ${tkCrema}`).fill(litrosCrema);
    await campo(formulario, "Grasa crema (%)").fill("42.00");
    await trasGuardar(page, "/cerrar/", async () => {
      await formulario.getByRole("button", { name: "Cerrar corrida" }).click();
    });
    await expect(tarjeta).toContainText("Cerrada");
  });

  await test.step("4 · Calidad analiza y libera cada rama por separado", async () => {
    await usarSesionArea(page, "e2e_calidad");
    await analizarSilo(page, tkDescremada, { grasa: "0.06", sng: "8.80" });
    await analizarSilo(page, tkCrema, { grasa: "42.00", sng: "8.80" });
    await irA(page, "/calidad");

    for (const tk of [tkDescremada, tkCrema]) {
      const tarjeta = page.locator("article").filter({ hasText: codigo }).filter({ hasText: tk });
      await expect(tarjeta).toBeVisible({ timeout: 20_000 });
      await elegirOpcion(tarjeta.getByRole("combobox"), /conforme/i);
      await trasGuardar(page, "/liberar/", async () => {
        await tarjeta.getByRole("button", { name: "Liberar etapa" }).click();
      });
    }
  });

  await test.step("5 · Las ramas muestran su siguiente acción contractual", async () => {
    await irA(page, "/leche/silos");
    await page.getByRole("button", { name: new RegExp(tkDescremada, "i") }).first().click();
    await expect(page.getByRole("link", { name: /Enviar a Estandarizaci[oó]n/ })).toBeVisible();
    await page.getByRole("button", { name: new RegExp(tkCrema, "i") }).first().click();
    await expect(page.getByRole("link", { name: "Iniciar Mantequilla" })).toBeVisible();
  });

  expect(erroresJs).toHaveLength(0);
});

test("ramas liberadas muestran Estandarización y Mantequilla", async ({ page }) => {
  const tkDescremada = process.env.E2E_TK_DESCREMADA ?? "Tk02";
  const tkCrema = process.env.E2E_TK_CREMA ?? "TkC2";
  await usarSesionArea(page, "e2e_calidad");
  await irA(page, "/leche/silos");
  await page.getByRole("button", { name: new RegExp(tkDescremada, "i") }).first().click();
  await expect(page.getByRole("link", { name: /Enviar a Estandarizaci[oó]n/ })).toBeVisible();
  await page.getByRole("button", { name: new RegExp(tkCrema, "i") }).first().click();
  await expect(page.getByRole("link", { name: "Iniciar Mantequilla" })).toBeVisible();
});
