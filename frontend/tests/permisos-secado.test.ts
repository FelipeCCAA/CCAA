import assert from "node:assert/strict";
import test from "node:test";

import { puedeOperarSecado } from "../src/services/permisos-secado.ts";

const conArea = (area: string, rol = "produccion") => ({ rol, perfil: { area } });

test("Secado opera su puesto", () => {
  assert.equal(puedeOperarSecado(conArea("secado")), true);
});

test("Condensación no opera la torre, como en el servidor", () => {
  assert.equal(puedeOperarSecado(conArea("condensacion")), false);
});

test("Calidad consulta pero no opera", () => {
  assert.equal(puedeOperarSecado(conArea("calidad", "calidad")), false);
});

test("Administración y el administrador operan", () => {
  assert.equal(puedeOperarSecado(conArea("administracion")), true);
  assert.equal(puedeOperarSecado({ rol: "admin", perfil: null }), true);
});

test("sin sesión o sin área no se opera", () => {
  assert.equal(puedeOperarSecado(null), false);
  assert.equal(puedeOperarSecado({ rol: "produccion", perfil: null }), false);
});
