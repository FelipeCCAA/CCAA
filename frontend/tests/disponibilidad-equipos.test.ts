import assert from "node:assert/strict";
import test from "node:test";

import {
  disponibilidadSegunEstado,
  ocupacionesPorEquipo,
} from "../src/services/disponibilidad-equipos.ts";

test("preparación reserva y los estados físicos ocupan el equipo", () => {
  assert.equal(disponibilidadSegunEstado("preparacion"), "reservado");
  for (const estado of ["ejecucion", "pausada", "bloqueada"]) {
    assert.equal(disponibilidadSegunEstado(estado), "ocupado");
  }
});

test("pendiente de control libera físicamente el equipo", () => {
  assert.equal(disponibilidadSegunEstado("pendiente_control"), "disponible");
  assert.equal(disponibilidadSegunEstado("cerrada"), "disponible");
});

test("la ocupación conserva la ejecución informada por backend", () => {
  const ocupaciones = ocupacionesPorEquipo([
    { codigo: "EJ-7", estado: "pausada", estado_etiqueta: "Pausada", equipo_id: 41, equipo_nombre: "Torre repetida" },
    { codigo: "EJ-8", estado: "pendiente_control", estado_etiqueta: "Pendiente", equipo_id: 42, equipo_nombre: "Torre repetida" },
  ]);
  assert.equal(ocupaciones.get(41)?.ejecucion, "EJ-7");
  assert.equal(ocupaciones.has(42), false);
});
