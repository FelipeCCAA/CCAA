import assert from "node:assert/strict";
import test from "node:test";

import { calcularBalanceMantequilla } from "../src/services/balance-mantequilla.ts";

test("exige clasificar toda la crema utilizada", () => {
  const balance = calcularBalanceMantequilla("1000.000", {
    mantequilla: "420", suero: "560", merma: "10", reproceso: "0",
  });

  assert.equal(balance.cuadrado, false);
  assert.equal(balance.diferencia, 10);
  assert.equal(balance.excedido, false);
});

test("acepta un balance exacto con reproceso segregado", () => {
  const balance = calcularBalanceMantequilla("1000.000", {
    mantequilla: "420.123", suero: "559.877", merma: "10", reproceso: "10",
  });

  assert.equal(balance.cuadrado, true);
  assert.equal(balance.diferencia, 0);
});

test("calcula en milésimas sin errores de punto flotante", () => {
  const balance = calcularBalanceMantequilla("0.300", {
    mantequilla: "0.100", suero: "0.200", merma: "0", reproceso: "0",
  });

  assert.equal(balance.cuadrado, true);
  assert.equal(balance.clasificado, 0.3);
});
