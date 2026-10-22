import { expect, test } from "@playwright/test";

test("Administración distingue aceptación e incertidumbre sin reenvío automático", async ({ page }) => {
  const usuario = { id: 808, username: "op08-admin", nombre: "Admin", apellido: "Prueba", rol: "admin",
    capacidades: ["reset_password"],
    perfil: { area: "administracion", nivel: "admin", rol: "admin", debe_cambiar_password: false } };
  const trabajador = { id: 809, username: "operador", nombre: "Operador", apellido: "Prueba", activo: true,
    email: "operador@example.invalid", capacidades: [], perfil: { area: "recepcion", nivel: "trabajador", rol: "recepcion" } };
  let solicitudes = 0;
  const externas: string[] = [];
  await page.addInitScript((usuario) => {
    sessionStorage.setItem("ccaa.sesion", JSON.stringify({ token: "op08-ficticio", usuario }));
  }, usuario);
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== "http://127.0.0.1:5199") { externas.push(url.origin); await route.abort(); return; }
    if (!url.pathname.startsWith("/api/")) { await route.continue(); return; }
    if (url.pathname.endsWith("/restablecer-contrasena/")) {
      solicitudes++;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ estado: "incierto",
        error: "No se confirmó la aceptación del correo. Revisa su estado antes de volver a solicitarlo." }) });
      return;
    }
    const datos = url.pathname === "/api/usuarios/yo/" ? usuario
      : url.pathname === "/api/usuarios/trabajadores/" ? [trabajador] : [];
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(datos) });
  });
  await page.goto("/#/administracion");
  await page.getByRole("button", { name: "Restablecer", exact: true }).click();
  await expect(page.getByText("No se confirmó la aceptación del correo. Revisa su estado antes de volver a solicitarlo.")).toBeVisible();
  expect(solicitudes).toBe(1);
  expect(externas).toEqual([]);
  await expect(page.getByText("Se enviaron las instrucciones de restablecimiento.")).toHaveCount(0);
});
