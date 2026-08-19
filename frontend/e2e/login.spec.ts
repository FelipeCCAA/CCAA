/*
  Las dos caras del 401.

  `services/api.ts` trata cualquier 401 como «el token dejó de servir» y manda
  al login recargando el navegador. Eso es correcto para una sesión caducada y
  destructivo para el login mismo: ahí el 401 es la respuesta esperada a una
  contraseña equivocada, y la recarga borra el mensaje que el formulario acaba
  de escribir. El operario ve la pantalla parpadear y no se entera de nada.

  Las dos pruebas van juntas a propósito. Separadas, la primera se «arregla»
  quitando la redirección —y entonces una sesión caducada se queda dando 401 en
  bucle sin volver al login—, y la segunda se satisface redirigiendo siempre.
  Es el par lo que fija el comportamiento.
*/

import { test, expect } from "@playwright/test";

const CLAVE_SESION = "ccaa.sesion";

test.describe("Respuesta al 401", () => {

  test("una contraseña incorrecta deja el mensaje a la vista", async ({ page }) => {
    await page.goto("/#/login");

    await page.getByPlaceholder("sjuan").fill("noexiste");
    await page.locator('input[type="password"]').fill("contraseña-mala");
    await page.getByRole("button", { name: "Iniciar sesión" }).click();

    // El mensaje lo manda el backend; la pantalla solo tiene que conservarlo.
    await expect(page.getByText("Usuario o contraseña incorrectos")).toBeVisible();
  });

  test("una sesión caducada sí vuelve al login", async ({ page }) => {
    // Un token que el backend rechazará: es lo que queda tras un logout desde
    // otro equipo, o tras recrear la base en desarrollo.
    await page.goto("/#/login");
    await page.evaluate((clave) => {
      sessionStorage.setItem(clave, JSON.stringify({
        token: "token-que-ya-no-sirve",
        usuario: { id: 1, username: "quien", rol: "admin", perfil: { area: "administracion", nivel: "admin" } },
      }));
    }, CLAVE_SESION);

    await page.goto("/#/registros");

    await expect(page).toHaveURL(/#\/login$/);
    // Y la sesión inservible no queda guardada esperando al siguiente intento.
    expect(await page.evaluate((clave) => sessionStorage.getItem(clave), CLAVE_SESION)).toBeNull();
  });

});
