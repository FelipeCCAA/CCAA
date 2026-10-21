import assert from "node:assert/strict";
import test from "node:test";
import { fifoOperacionalValido, kgConocidosDeEntradas, requiereReferenciaMedicionKg } from "../src/services/secado-operacion.ts";
import type { EntradaAlimentacionSecado } from "../src/services/secado.service.ts";
import { resultadoDeEnvioIncierto } from "../src/services/resultado-envio.ts";

const kg = (cantidad: string): EntradaAlimentacionSecado => ({ tipo_origen: "inventario", origen_id: 1, cantidad, unidad: "kg", codigo: "LOTE-1", estado_calidad: "liberado" });

test("OP04: suma solo alimentaciones informadas íntegramente en kg", () => {
  assert.equal(kgConocidosDeEntradas([kg("12.5"), { ...kg("3"), origen_id: 2 }]), 15.5);
  assert.equal(kgConocidosDeEntradas([]), null);
  assert.equal(kgConocidosDeEntradas([kg("12"), { ...kg("10"), unidad: "L" }]), null);
  assert.equal(kgConocidosDeEntradas([kg("inválido")]), null);
});

test("OP04: entradas en litros requieren referencia de peso medida", () => {
  assert.equal(requiereReferenciaMedicionKg({ requiere_referencia_medicion_kg: true }), true);
  assert.equal(requiereReferenciaMedicionKg({ entradas_alimentacion: [{ ...kg("20"), unidad: "L" }] }), true);
  assert.equal(requiereReferenciaMedicionKg({ entradas_alimentacion: [kg("20")] }), false);
});

test("OP04: conexión perdida y 5xx mantienen recuperación de la operación", () => {
  for (const error of [new Error("offline"), { response: { status: 503 } }]) assert.equal(resultadoDeEnvioIncierto(error), true);
  for (const status of [400, 409]) assert.equal(resultadoDeEnvioIncierto({ response: { status } }), false);
});

test("OP04: FIFO desconocido bloquea y excepción exige un motivo concreto", () => {
  assert.equal(fifoOperacionalValido(undefined, "razón válida"), false);
  assert.equal(fifoOperacionalValido(true, ""), true);
  assert.equal(fifoOperacionalValido(false, "no"), false);
  assert.equal(fifoOperacionalValido(false, "Reserva de ensayo"), true);
});
