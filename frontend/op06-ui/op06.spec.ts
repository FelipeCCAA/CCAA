import { expect, test, type Page } from "@playwright/test";

const BASE = "http://127.0.0.1:5197";
const usuario = (cambio = false, admin = true) => ({
  id: 906, username: "op06-sintetico", nombre: "Cuenta", apellido: "Prueba", email: "",
  rol: admin ? "admin" : "lectura", capacidades: [],
  perfil: { cargo: "", area: admin ? "administracion" : "aseo", area_etiqueta: "Prueba",
    turno: "", rol: admin ? "admin" : "lectura", rol_etiqueta: "Prueba",
    nivel: admin ? "admin" : "trabajador", nivel_etiqueta: "Prueba", debe_cambiar_password: cambio },
});

async function preparar(page: Page, responder: (intento: number) => Promise<{ status?: number; body: unknown }>, recordar = false) {
  let consultas = 0;
  const previas: string[] = [];
  const externas: string[] = [];
  await page.addInitScript(({ cuenta, recordar }) => {
    (recordar ? localStorage : sessionStorage).setItem("ccaa.sesion", JSON.stringify({ token: "op06-ficticio", usuario: cuenta }));
  }, { cuenta: usuario(), recordar });
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== BASE) { externas.push(url.origin); await route.abort(); return; }
    if (!url.pathname.startsWith("/api/")) { await route.continue(); return; }
    if (url.pathname === "/api/usuarios/yo/") {
      consultas++;
      const respuesta = await responder(consultas);
      await route.fulfill({ status: respuesta.status ?? 200, contentType: "application/json", body: JSON.stringify(respuesta.body) });
      return;
    }
    if (!consultas) previas.push(url.pathname);
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(url.pathname.includes("notificaciones") ? { results: [] } : []) });
  });
  return { consultas: () => consultas, previas, externas };
}

test("no muestra permisos antiguos mientras verifica y usa el perfil del servidor", async ({ page }) => {
  let liberar!: () => void;
  const espera = new Promise<void>((resolve) => { liberar = resolve; });
  const control = await preparar(page, async () => { await espera; return { body: usuario(false, false) }; });
  await page.goto("/#/administracion");
  await expect(page.getByText("Verificando acceso…")).toBeVisible();
  expect(control.previas).toEqual([]);
  liberar();
  await expect(page.getByRole("heading", { name: "Acceso restringido" })).toBeVisible();
  expect(await page.evaluate(() => JSON.parse(sessionStorage.getItem("ccaa.sesion")!).usuario.rol)).toBe("lectura");
  expect(control.externas).toEqual([]);
});

test("un error de verificación bloquea la operación y permite reintentar sin perder Recordarme", async ({ page }) => {
  const control = await preparar(page, async (intento) => intento === 1 ? { status: 503, body: {} } : { body: usuario(true) }, true);
  await page.goto("/#/administracion");
  await expect(page.getByText("No pudimos verificar tu acceso. Reintenta para continuar.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Reintentar" })).toBeVisible();
  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(page).toHaveURL(/cambiar-password/);
  expect(control.consultas()).toBe(2);
  expect(await page.evaluate(() => ({ local: !!localStorage.getItem("ccaa.sesion"), temporal: !!sessionStorage.getItem("ccaa.sesion") }))).toEqual({ local: true, temporal: false });
  expect(control.previas).toEqual([]);
});

test("una sesión revocada vuelve al acceso antes de cargar módulos protegidos", async ({ page }) => {
  const control = await preparar(page, async () => ({ status: 401, body: { code: "SESSION_REVOKED" } }));
  await page.goto("/#/administracion");
  await expect(page).toHaveURL(/login/);
  expect(await page.evaluate(() => sessionStorage.getItem("ccaa.sesion"))).toBeNull();
  expect(control.previas).toEqual([]);
});

test("la identidad se consulta nuevamente al reabrir y no se reutiliza la caché GET", async ({ page }) => {
  const control = await preparar(page, async () => ({ body: usuario(true) }));
  await page.goto("/#/cambiar-password");
  await expect(page.getByRole("heading", { name: /cambiar contraseña/i })).toBeVisible();
  const inicial = control.consultas();
  await page.evaluate(async () => {
    // Endpoint real del cliente; la red está interceptada con datos sintéticos.
    const servicio = await import("/src/services/usuario.service.ts");
    await servicio.obtenerUsuarioActual();
    await servicio.obtenerUsuarioActual();
  });
  expect(control.consultas()).toBe(inicial + 2);
});

test("una respuesta 401 de la cuenta anterior no cierra una sesión nueva", async ({ page }) => {
  let liberar!: () => void;
  const espera = new Promise<void>((resolve) => { liberar = resolve; });
  const control = await preparar(page, async (intento) => {
    if (intento === 1) { await espera; return { status: 401, body: { code: "SESSION_REVOKED" } }; }
    return { body: usuario(true) };
  });
  await page.goto("/#/administracion");
  await expect.poll(control.consultas).toBe(1);
  await page.evaluate(() => {
    const almacenada = JSON.parse(sessionStorage.getItem("ccaa.sesion")!);
    sessionStorage.setItem("ccaa.sesion", JSON.stringify({ ...almacenada, token: "op06-nuevo-ficticio" }));
    window.dispatchEvent(new StorageEvent("storage", { key: "ccaa.sesion" }));
  });
  await expect(page).toHaveURL(/cambiar-password/);
  const anterior = page.waitForResponse((respuesta) => respuesta.url().endsWith("usuarios/yo/") && respuesta.status() === 401);
  liberar();
  await anterior;
  await expect(page.getByRole("heading", { name: /cambiar contraseña/i })).toBeVisible();
  expect(await page.evaluate(() => JSON.parse(sessionStorage.getItem("ccaa.sesion")!).token)).toBe("op06-nuevo-ficticio");
});

test("Administración sin permiso explícito conserva altas normales y bloquea altas administrativas", async ({ page }) => {
  await preparar(page, async () => ({ body: usuario() }));
  await page.goto("/#/administracion");
  await page.getByRole("button", { name: "Agregar trabajador" }).click();
  await expect(page.getByLabel("Nivel del nuevo trabajador")).toBeDisabled();
  await expect(page.getByLabel("Área del nuevo trabajador").locator('option[value="administracion"]')).toBeDisabled();
  await page.getByLabel("Área del nuevo trabajador").selectOption("secado");
  await expect(page.getByLabel("Área del nuevo trabajador")).toHaveValue("secado");
  await expect(page.getByText("El trabajador deberá cambiar su contraseña inicial antes de operar.")).toBeVisible();
});

test("la autorización vigente habilita la selección de administradores", async ({ page }) => {
  await preparar(page, async () => ({ body: { ...usuario(), capacidades: ["change_roles"] } }));
  await page.goto("/#/administracion");
  await page.getByRole("button", { name: "Agregar trabajador" }).click();
  await page.getByLabel("Nivel del nuevo trabajador").selectOption("admin");
  await page.getByLabel("Área del nuevo trabajador").selectOption("administracion");
  await expect(page.getByLabel("Nivel del nuevo trabajador")).toHaveValue("admin");
});
