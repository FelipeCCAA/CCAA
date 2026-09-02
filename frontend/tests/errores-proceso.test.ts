import assert from "node:assert/strict";
import test from "node:test";

import { esErrorDeEquipo, mensajeErrorProceso } from "../src/services/errores-proceso.ts";

test("muestra la ruta faltante con una etiqueta operacional", () => {
  const error = { response: { data: { ruta_producto: ["El producto no tiene una ruta activa."] } } };
  assert.equal(
    mensajeErrorProceso(error, "Error genérico"),
    "Ruta del producto: El producto no tiene una ruta activa.",
  );
});

test("conserva el detalle de dominio y combina errores de equipo", () => {
  const error = { response: { data: { detail: "Conflicto operacional.", equipo: "Ya está ocupado." } } };
  assert.equal(
    mensajeErrorProceso(error, "Error genérico"),
    "Conflicto operacional. · Equipo: Ya está ocupado.",
  );
});

test("usa el mensaje de respaldo cuando no hay respuesta DRF", () => {
  assert.equal(mensajeErrorProceso(new Error("red"), "Sin conexión."), "Sin conexión.");
});

test("identifica solamente errores de equipo para refrescar disponibilidad", () => {
  assert.equal(esErrorDeEquipo({ response: { data: { equipo: "Torre ocupada." } } }), true);
  assert.equal(esErrorDeEquipo({ response: { data: { error: "Evaporador 1 está ocupado por EJ-9." } } }), true);
  assert.equal(esErrorDeEquipo({ response: { data: { detail: "Sin permiso." } } }), false);
});
