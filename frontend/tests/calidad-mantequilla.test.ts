import assert from "node:assert/strict";
import test from "node:test";

import {
  describirRango,
  payloadLiberacionProceso,
} from "../src/services/calidad-proceso.ts";

test("mantequilla libera con analisis_lote_id y no inventa un silo", () => {
  assert.deepEqual(
    payloadLiberacionProceso("lote", 123, "Resultado conforme"),
    { analisis_lote_id: 123, observacion: "Resultado conforme" },
  );
});

test("una salida en silo conserva el contrato analisis_id", () => {
  assert.deepEqual(
    payloadLiberacionProceso("silo", 45, "Conforme"),
    { analisis_id: 45, observacion: "Conforme" },
  );
});

test("los rangos conservan límites, unidad y obligatoriedad", () => {
  assert.equal(
    describirRango({ min: 14, max: 18, unidad: "%", obligatorio: true }),
    "14 a 18 % · obligatorio",
  );
});
