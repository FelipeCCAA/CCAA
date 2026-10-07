import assert from "node:assert/strict";
import test from "node:test";

import { puedeOperarEvaporacion } from "../src/services/permisos-evaporacion.ts";

const conArea = (area: string, rol = "produccion") => ({ rol, perfil: { area } });

test("Condensación opera la evaporación", () => {
  assert.equal(puedeOperarEvaporacion(conArea("condensacion")), true);
});

test("Secado escribe lotes pero no opera el evaporador", () => {
  assert.equal(puedeOperarEvaporacion(conArea("secado")), false);
});

test("Administración y el administrador operan", () => {
  assert.equal(puedeOperarEvaporacion(conArea("administracion")), true);
  assert.equal(puedeOperarEvaporacion({ rol: "admin", perfil: null }), true);
});

test("el rol heredado produccion sin área no opera, como en el servidor", () => {
  assert.equal(puedeOperarEvaporacion({ rol: "produccion", perfil: null }), false);
  assert.equal(puedeOperarEvaporacion(conArea("", "produccion")), false);
});

test("sin sesión no se opera", () => {
  assert.equal(puedeOperarEvaporacion(null), false);
});
