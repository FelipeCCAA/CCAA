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

import { test as setup, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

import { API, ORIGEN, RUTA_ESTADO } from "./constantes";

const CLAVE_SESION = "ccaa.sesion";

const usuario = process.env.E2E_USUARIO;
const clave = process.env.E2E_CLAVE;

setup("obtiene una sesión para auditar las pantallas internas", async ({ request }) => {
  expect(
    usuario && clave,
    "Faltan credenciales. Define E2E_USUARIO y E2E_CLAVE antes de correr la auditoría.",
  ).toBeTruthy();

  const respuesta = await request.post(`${API}/api/usuarios/login/`, {
    data: { username: usuario, password: clave },
  });

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
