import assert from "node:assert/strict";
import test from "node:test";

import { fechaLocalISO } from "../src/services/fechas.ts";

test("una hora avanzada de la noche sigue siendo el mismo día local", () => {
  assert.equal(fechaLocalISO(new Date(2026, 8, 23, 23, 30)), "2026-09-23");
});

test("rellena con ceros el mes y el día de un solo dígito", () => {
  assert.equal(fechaLocalISO(new Date(2026, 0, 5, 0, 0)), "2026-01-05");
});

test("el último minuto del año no se corre al año siguiente", () => {
  assert.equal(fechaLocalISO(new Date(2026, 11, 31, 23, 59)), "2026-12-31");
});
