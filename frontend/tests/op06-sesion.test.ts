import assert from "node:assert/strict";
import test from "node:test";

import { actualizarUsuarioSesion, guardarSesion, obtenerSesion, type Usuario } from "../src/services/sesion.ts";

class Almacen {
  datos = new Map<string, string>();
  getItem(clave: string) { return this.datos.get(clave) ?? null; }
  setItem(clave: string, valor: string) { this.datos.set(clave, valor); }
  removeItem(clave: string) { this.datos.delete(clave); }
}

function preparar() {
  Object.defineProperty(globalThis, "localStorage", { value: new Almacen(), configurable: true });
  Object.defineProperty(globalThis, "sessionStorage", { value: new Almacen(), configurable: true });
}

const anterior = { id: 1, username: "anterior", rol: "admin" } as Usuario;
const actual = { id: 1, username: "actual", rol: "lectura" } as Usuario;

for (const recordar of [false, true]) {
  test(`actualizar identidad conserva Recordarme=${recordar}`, () => {
    preparar();
    guardarSesion({ token: "token-ficticio", usuario: anterior }, recordar);
    assert.equal(actualizarUsuarioSesion("token-ficticio", actual), true);
    assert.deepEqual(obtenerSesion()?.usuario, actual);
    assert.equal(localStorage.getItem("ccaa.sesion") !== null, recordar);
    assert.equal(sessionStorage.getItem("ccaa.sesion") !== null, !recordar);
  });
}

test("una respuesta antigua no sobrescribe una cuenta que inició después", () => {
  preparar();
  guardarSesion({ token: "token-nuevo", usuario: anterior });
  assert.equal(actualizarUsuarioSesion("token-antiguo", actual), false);
  assert.deepEqual(obtenerSesion(), { token: "token-nuevo", usuario: anterior });
});

test("una respuesta pendiente no restaura una sesión eliminada", () => {
  preparar();
  assert.equal(actualizarUsuarioSesion("token-antiguo", actual), false);
  assert.equal(obtenerSesion(), null);
});
