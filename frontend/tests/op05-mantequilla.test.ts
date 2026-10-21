import assert from "node:assert/strict";
import test from "node:test";

import { prepararIntentoOperacion } from "../src/services/intento-operacion.ts";
import { calcularBalanceMantequilla } from "../src/services/balance-mantequilla.ts";

test("OP05: una carga repetida conserva UUID y una corrección crea otra operación", () => {
  const ids = ["uuid-uno", "uuid-dos"];
  const crearUuid = () => ids.shift()!;
  const carga = { lote_crema: 17, salida_crema: 41, kg_crema: 125 };
  const primero = prepararIntentoOperacion(null, carga, crearUuid);
  const reintento = prepararIntentoOperacion(primero, { ...carga }, crearUuid);
  const corregido = prepararIntentoOperacion(reintento, { ...carga, kg_crema: 120 }, crearUuid);

  assert.equal(reintento, primero);
  assert.equal(reintento.carga.operacion_id, "uuid-uno");
  assert.equal(corregido.carga.operacion_id, "uuid-dos");
  assert.equal(corregido.carga.kg_crema, 120);
});

test("OP05: el balance clasifica mantequilla, merma y reproceso sin mazada en nuevas corridas", () => {
  const balance = calcularBalanceMantequilla("1000.000", {
    mantequilla: "720.123", suero: "0", merma: "269.877", reproceso: "10",
  });

  assert.equal(balance.cuadrado, true);
  assert.equal(balance.clasificado, 1000);
  assert.equal(balance.diferencia, 0);
});
