import assert from "node:assert/strict";
import test from "node:test";

import { puedeOperarMantequilla } from "../src/services/permisos-mantequilla.ts";

const conArea = (area: string, rol = "produccion") => ({ rol, perfil: { area } });

test("Condensación opera el puesto de Mantequilla", () => {
  assert.equal(puedeOperarMantequilla(conArea("condensacion")), true);
});

test("Secado no opera la mantequera, como en el servidor", () => {
  assert.equal(puedeOperarMantequilla(conArea("secado")), false);
});

test("Calidad consulta pero no opera", () => {
  assert.equal(puedeOperarMantequilla(conArea("calidad", "calidad")), false);
});

test("Administración y el administrador operan", () => {
  assert.equal(puedeOperarMantequilla(conArea("administracion")), true);
  assert.equal(puedeOperarMantequilla({ rol: "admin", perfil: null }), true);
});

test("sin sesión o sin área no se opera", () => {
  assert.equal(puedeOperarMantequilla(null), false);
  assert.equal(puedeOperarMantequilla({ rol: "produccion", perfil: null }), false);
});
