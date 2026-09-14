import assert from "node:assert/strict";
import test from "node:test";

import { rutaTrazabilidad } from "../src/services/trazabilidad-visual.ts";


test("conserva la URL histórica para lote y codifica su referencia", () => {
  assert.equal(
    rutaTrazabilidad("lote", " LOTE A/01 "),
    "procesos/trazabilidad/lotes/LOTE%20A%2F01/",
  );
});

test("carga corrida o salida bajo demanda desde su propia referencia", () => {
  assert.equal(
    rutaTrazabilidad("ejecucion", "EJ-SEC-42"),
    "procesos/trazabilidad/ejecucion/EJ-SEC-42/",
  );
  assert.equal(
    rutaTrazabilidad("salida", 81),
    "procesos/trazabilidad/salida/81/",
  );
});
