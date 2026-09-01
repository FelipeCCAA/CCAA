/*
  Consigue la sesión que usa la auditoría y la deja escrita en disco.

  Se hace por la API y no rellenando el formulario de login por dos razones:
  una prueba de accesibilidad que empieza tecleando en el formulario tarda lo
  mismo treinta veces y no comprueba nada extra; y si el login se rompe,
  conviene que falle este paso —con un mensaje que lo diga— en vez de que
  fallen las treinta pantallas con un error de navegación que no explica nada.

  La sesión se escribe en `localStorage` bajo `ccaa.sesion`, que es la forma
  exacta que `services/sesion.ts` sabe leer. El objeto `usuario` NO se
  construye aquí: se guarda tal como lo devuelve el backend. Escribirlo a mano
  crearía una segunda definición de la forma del usuario que se desincroniza
  el día que alguien agregue un campo al serializador.

  Ojo con `sessionStorage`: la aplicación lo prefiere al leer, pero Playwright
  solo sabe restaurar `localStorage` en su `storageState`. Da igual —
  `obtenerSesion()` cae a `localStorage` cuando el otro está vacío—, pero
  explica por qué aquí no se toca el que la aplicación mira primero.
*/

import { test as setup, expect, type APIRequestContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

import { API, ORIGEN, RUTA_ESTADO } from "./constantes";

const CLAVE_SESION = "ccaa.sesion";

const usuario = process.env.E2E_USUARIO;
const clave = process.env.E2E_CLAVE;

/*
  Cierra la sesión que dejó abierta la corrida anterior.

  El backend permite **una sesión activa por usuario** y responde 409 a la
  segunda. Como el token solo se invalida llamando a `logout/`, y una corrida
  que termina no llama a nada, la segunda ejecución de la auditoría fallaba
  siempre en este paso con «El login rechazó a…», que suena a contraseña
  equivocada y no lo es. El token de la corrida anterior está en el propio
  `storageState`: se usa para cerrarla antes de pedir una nueva.

  Los errores se ignoran a propósito. Si el archivo no existe, si el token ya
  caducó o si el servidor lo rechaza, el estado deseado —sin sesión abierta—
  ya se cumple, y hacer fallar el setup por eso impediría precisamente lo que
  esta función viene a permitir.
*/
async function cerrarSesionAnterior(request: APIRequestContext) {
  try {
    const guardado = JSON.parse(fs.readFileSync(RUTA_ESTADO, "utf8"));
    const entrada = guardado.origins?.[0]?.localStorage?.find(
      (item: { name: string }) => item.name === CLAVE_SESION,
    );
    const token = entrada && JSON.parse(entrada.value).token;

    if (token) {
      await request.post(`${API}/api/usuarios/logout/`, {
        headers: { Authorization: `Token ${token}` },
      });
    }
  } catch {
    /* No había sesión anterior que cerrar. */
  }
}

setup("obtiene una sesión para auditar las pantallas internas", async ({ request }) => {
  expect(
    usuario && clave,
    "Faltan credenciales. Define E2E_USUARIO y E2E_CLAVE antes de correr la auditoría.",
  ).toBeTruthy();

  await cerrarSesionAnterior(request);

  const respuesta = await request.post(`${API}/api/usuarios/login/`, {
    data: { username: usuario, password: clave },
  });

  /* 409 es «ya hay una sesión activa», no una credencial mala. Se nombra
     aparte porque el mensaje genérico manda a revisar la contraseña, que es
     justo donde no está el problema. */
  expect(
    respuesta.status(),
    "El usuario ya tiene una sesión activa en otro equipo y no se pudo cerrar " +
      "desde aquí. Ciérrala en Administración › Sesiones, o espera a que caduque.",
  ).not.toBe(409);

  /* El backend responde 401 con el mismo mensaje exista o no la cuenta, así
     que aquí no se puede distinguir «usuario mal escrito» de «contraseña
     equivocada». Se dice lo que sí se sabe. */
  expect(
    respuesta.status(),
    `El login rechazó a «${usuario}» (HTTP ${respuesta.status()}). ` +
      "Revisa las credenciales; si son correctas, comprueba que la cuenta esté activa.",
  ).toBe(200);

  const sesion = await respuesta.json();

  /* `/administracion` está tras `RutaAdmin`. Con un usuario de otro rol esa
     pantalla redirige al panel y la auditoría mediría el panel dos veces
     creyendo que cubrió administración: un falso «sin problemas». */
  expect(
    sesion.usuario?.rol,
    "El usuario de la auditoría tiene que ser administrador: si no, /administracion " +
      "redirige y quedaría auditada como si estuviera limpia.",
  ).toBe("admin");

  const estado = {
    cookies: [],
    origins: [
      {
        origin: ORIGEN,
        localStorage: [
          {
            name: CLAVE_SESION,
            value: JSON.stringify({ token: sesion.token, usuario: sesion.usuario }),
          },
        ],
      },
    ],
  };

  fs.mkdirSync(path.dirname(RUTA_ESTADO), { recursive: true });
  fs.writeFileSync(RUTA_ESTADO, JSON.stringify(estado, null, 2), "utf8");
});
