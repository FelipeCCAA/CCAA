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

test("crema liberada sigue su ruta comercial hasta despacho directo", async ({ page }) => {
  test.setTimeout(180_000);
  const erroresJs = vigilar(page);
  const siloOrigen = process.env.E2E_SILO_ENTERA ?? "Silo 3";
  const tkDescremada = process.env.E2E_TK_DESCREMADA_DIRECTA ?? "Tk03";
  const tkCrema = process.env.E2E_TK_CREMA_DIRECTA ?? "TkC3";
  const codigo = `CREMA-E2E-${Date.now().toString().slice(-8)}`;
  const numeroDespacho = `DG-${codigo}`;
  let rutaDescremar = "";
  let litrosDescremada = "";
  let litrosCrema = "";

  await test.step("1 · Calidad confirma la materia prima de origen", async () => {
    await usarSesionArea(page, "e2e_calidad");
    await analizarSilo(page, siloOrigen, { grasa: "2.61", sng: "8.70" });
    const href = await page.getByRole("link", { name: "Descremar" }).getAttribute("href");
    rutaDescremar = new URL(href!, page.url()).hash.replace(/^#/, "");
  });

  await test.step("2 · El operador confirma la sugerencia y el destino comercial", async () => {
    await usarSesionArea(page, "e2e_produccion");
    await irA(page, rutaDescremar);
    const formulario = page.locator("form").filter({ hasText: "Iniciar descremación" });
    await expect(formulario).toBeVisible({ timeout: 20_000 });
    await campo(formulario, "Código de ejecución").fill(codigo);
    await elegirOpcion(campo(formulario, "Equipo"), /DES-01/i);
    await campo(formulario, "Litros de entrada").fill("500");
    await elegirOpcion(campo(formulario, "Destino leche descremada"), new RegExp(tkDescremada, "i"));
    await elegirOpcion(campo(formulario, "TK fisico para crema"), new RegExp(tkCrema, "i"));
    await campo(formulario, "Destino crema").selectOption("despacho_directo");
    await elegirOpcion(campo(formulario, "Ruta crema"), /despacho directo/i);

    await trasGuardar(page, "/sugerir-balance/", async () => {
      await formulario.getByRole("button", { name: "Calcular sugerencia" }).click();
    });
    litrosDescremada = await campo(formulario, "Descremada planificada (L)").inputValue();
    litrosCrema = await campo(formulario, "Crema planificada (L)").inputValue();
    expect(Number(litrosDescremada)).toBeGreaterThan(450);
    expect(Number(litrosCrema)).toBeGreaterThan(0);
    await formulario.getByRole("checkbox", { name: /Confirmo que revisé/ }).check();

    const creada = page.waitForResponse((r) => r.url().includes("/crear-guiada/") && r.request().method() === "POST");
    const iniciada = page.waitForResponse((r) => /\/descremaciones\/\d+\/iniciar\/$/.test(r.url()) && r.request().method() === "POST");
    await formulario.getByRole("button", { name: "Confirmar reservas e iniciar" }).click();
    expect((await creada).ok()).toBeTruthy();
    expect((await iniciada).ok()).toBeTruthy();
  });

  await test.step("3 · Producción registra ambas salidas físicas", async () => {
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

  await test.step("4 · Calidad libera por separado descremada y crema", async () => {
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

  await test.step("5 · Producción expone la crema como despacho, no como mantequilla", async () => {
    await usarSesionArea(page, "e2e_produccion");
    await irA(page, "/produccion");
    await page.getByRole("button", { name: "Consultar disponibles" }).click();
    const tarjeta = page.locator("article").filter({ hasText: codigo }).filter({ hasText: tkCrema });
    await expect(tarjeta.getByRole("link", { name: "Preparar despacho" })).toBeVisible({ timeout: 20_000 });
    await expect(tarjeta.getByRole("link", { name: "Iniciar Mantequilla" })).toHaveCount(0);
  });

  await test.step("6 · Bodega autoriza y ejecuta el despacho físico de crema", async () => {
    await usarSesionArea(page, "e2e_despacho");
    await irA(page, "/inventario");
    await page.getByRole("button", { name: "Despachar producto" }).click();
    const formulario = page.locator("form").filter({ hasText: "Despachar producto" });
    await formulario.getByPlaceholder("Nº de despacho").fill(numeroDespacho);
    const selectores = formulario.locator("select");
    await selectores.nth(0).selectOption({ index: 1 });
    await selectores.nth(1).selectOption("granel");
    await elegirOpcion(selectores.nth(2), new RegExp(codigo));
    const cantidad = formulario.getByPlaceholder("Cantidad a despachar");
    await expect.poll(async () => Number(await cantidad.inputValue())).toBeGreaterThan(0);
    await trasGuardar(page, "/api/inventario/despachos/", async () => {
      await formulario.getByRole("button", { name: "Confirmar movimiento" }).click();
    });
    await page.getByRole("button", { name: "Despachos", exact: true }).click();
    const tarjeta = page.locator("article").filter({ hasText: numeroDespacho });
    await expect(tarjeta).toContainText(codigo, { timeout: 20_000 });
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
