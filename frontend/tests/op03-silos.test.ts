import assert from "node:assert/strict";
import test from "node:test";
import { bloqueoSilo, cantidadInformada, disponibleSilo, validarLitrosDespacho } from "../src/pages/Leche/disponibilidad-silo.ts";
import type { OcupacionSilo } from "../src/services/recepcion.service.ts";
import { resultadoDeEnvioIncierto } from "../src/services/resultado-envio.ts";

const silo = {
  litros: 10000, litros_reservados: 8000, litros_libres: 2000, litros_disponibles: 2000,
  motivos_no_disponible: [], reservas_activas: [{ tipo: "origen", ejecucion_codigo: "CORRIDA-8MIL" }],
} as unknown as OcupacionSilo;

test("OP03: el total físico no sustituye la disponibilidad del servidor", () => {
  assert.equal(disponibleSilo(silo), 2000);
  assert.equal(disponibleSilo({ ...silo, litros_disponibles: "37.25" }), 37.25);
  assert.match(validarLitrosDespacho("5000", disponibleSilo(silo)), /2\.000 L disponibles/);
  assert.equal(validarLitrosDespacho("2000.00", disponibleSilo(silo)), "");
});

test("OP03: datos anteriores o inválidos dejan disponibilidad desconocida", () => {
  for (const valor of [undefined, null, "", Infinity, "no-dato", false]) assert.equal(cantidadInformada(valor), null);
  assert.equal(disponibleSilo({ litros_disponibles: undefined }), null);
  assert.match(bloqueoSilo({ ...silo, litros_disponibles: undefined })!, /desconocida/);
  assert.match(validarLitrosDespacho("1", null), /Actualiza/);
});

test("OP03: una reserva de origen parcial permite solo el remanente informado", () => {
  assert.equal(bloqueoSilo(silo), undefined);
  assert.match(bloqueoSilo({ ...silo, litros_disponibles: 0 })!, /No hay litros/);
});

test("OP03: destino reservado y Calidad conservan el bloqueo", () => {
  const destino = { tipo: "destino", ejecucion_codigo: "CORRIDA-DESTINO" } as OcupacionSilo["reservas_activas"][number];
  assert.match(bloqueoSilo({ ...silo, reservas_activas: [destino] })!, /CORRIDA-DESTINO/);
  assert.equal(bloqueoSilo({ ...silo, motivos_no_disponible: ["Calidad debe revisar"] }), "Calidad debe revisar");
});

test("OP03: rechaza precisión excesiva y conserva 0,01 L", () => {
  assert.equal(validarLitrosDespacho("0.01", 0.01), "");
  for (const valor of ["0", "-1", "0.001", "1e2", "NaN"]) assert.match(validarLitrosDespacho(valor, 1000), /0,01 L/);
  assert.equal(cantidadInformada("-1.25"), -1.25);
});

test("OP03: desconexión y 5xx requieren recuperar el resultado; 400/409 permiten corregir", () => {
  for (const causa of [new Error("Sin respuesta"), null, { response: { status: 0 } }, { response: { status: 500 } }, { response: { status: 503 } }]) {
    assert.equal(resultadoDeEnvioIncierto(causa), true);
  }
  for (const estado of [400, 403, 409]) assert.equal(resultadoDeEnvioIncierto({ response: { status: estado } }), false);
});
