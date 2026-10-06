import assert from "node:assert/strict";
import test from "node:test";

import {
  equiposCompatiblesDe, RUTA_POR_FAMILIA, TIPOS_QUE_ABREN_DESDE_VALE, tiposDeFamilia,
} from "../src/services/equipos-apertura.ts";

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

test("no se ofrece una máquina que el servidor no abre desde un vale", () => {
  const conCarga = [...equipos, { id: 5, tipo: "carga", activo: true }, { id: 6, tipo: "otro", activo: true }];
  assert.deepEqual(ids(equiposCompatiblesDe(conCarga, "resto", ["linea", "carga", "otro"])), [3]);
});

test("ninguna familia pide un tipo que el servidor rechaza al abrir desde el vale", () => {
  for (const [familia, { tipos }] of Object.entries(RUTA_POR_FAMILIA)) {
    for (const tipo of tipos) {
      assert.ok(TIPOS_QUE_ABREN_DESDE_VALE.includes(tipo), `${familia} pide ${tipo}`);
    }
  }
  assert.deepEqual(tiposDeFamilia("otro"), ["linea", "envasadora"]);
  assert.equal(tiposDeFamilia(undefined), null);
});
