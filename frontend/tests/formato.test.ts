import assert from "node:assert/strict";
import test from "node:test";

import { cantidad } from "../src/services/formato.ts";

test("trece unidades se leen trece, no trece mil", () => {
  assert.equal(cantidad("13.000", "un"), "13 un");
});

test("miles con punto y decimales con coma, como en Chile", () => {
  assert.equal(cantidad("1234.5", "kg"), "1.234,5 kg");
  assert.equal(cantidad(25000, "L"), "25.000 L");
  assert.equal(cantidad("0.125"), "0,125");
});

test("hasta tres decimales, que es lo que guarda el modelo", () => {
  assert.equal(cantidad("2.34567", "kg"), "2,346 kg");
});

test("lo que no es un número se muestra como raya", () => {
  assert.equal(cantidad(null, "kg"), "—");
  assert.equal(cantidad(undefined), "—");
  assert.equal(cantidad("", "un"), "—");
  assert.equal(cantidad("abc", "un"), "—");
});
