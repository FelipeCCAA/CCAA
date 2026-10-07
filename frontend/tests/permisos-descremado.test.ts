import assert from "node:assert/strict";
import test from "node:test";

import { puedeOperarDescremado } from "../src/services/permisos-descremado.ts";

const conArea = (area: string, rol = "produccion") => ({ rol, perfil: { area } });

test("Condensación opera el puesto de Descremado", () => {
  assert.equal(puedeOperarDescremado(conArea("condensacion")), true);
});

test("Secado no opera la descremadora, como en el servidor", () => {
  assert.equal(puedeOperarDescremado(conArea("secado")), false);
});

test("Calidad consulta pero no opera", () => {
  assert.equal(puedeOperarDescremado(conArea("calidad", "calidad")), false);
});

test("Administración y el administrador operan", () => {
  assert.equal(puedeOperarDescremado(conArea("administracion")), true);
  assert.equal(puedeOperarDescremado({ rol: "admin", perfil: null }), true);
});

test("sin sesión o sin área no se opera", () => {
  assert.equal(puedeOperarDescremado(null), false);
  assert.equal(puedeOperarDescremado({ rol: "produccion", perfil: null }), false);
});
