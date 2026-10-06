import assert from "node:assert/strict";
import test from "node:test";

import { equiposCompatiblesDe } from "../src/services/equipos-apertura.ts";

const equipos = [
  { id: 1, tipo: "evaporador", activo: true },
  { id: 2, tipo: "torre", activo: true },
  { id: 3, tipo: "linea", activo: true },
  { id: 4, tipo: "linea", activo: false },
];
const ids = (lista: { id: number }[]) => lista.map((item) => item.id);

test("en Producción no se ofrecen torres aunque la familia no tenga ruta", () => {
  assert.deepEqual(ids(equiposCompatiblesDe(equipos, "resto", null)), [3]);
});

test("en Producción no se ofrecen torres aunque la ruta las nombre", () => {
  assert.deepEqual(ids(equiposCompatiblesDe(equipos, "resto", ["torre", "linea"])), [3]);
});

test("el puesto de Evaporación ofrece solo evaporadores activos", () => {
  assert.deepEqual(ids(equiposCompatiblesDe(equipos, "evaporacion", null)), [1]);
});
