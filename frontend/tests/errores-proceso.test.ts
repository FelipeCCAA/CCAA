import assert from "node:assert/strict";
import test from "node:test";

import {
  esConflictoVersion,
  esErrorDeEquipo,
  mensajeErrorProceso,
} from "../src/services/errores-proceso.ts";

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

test("informa qué ejecución ocupa el equipo después de una carrera", () => {
  const error = {
    response: {
      data: {
        error: "Torre de secado concurrente está ocupado por EJ-TOR-RACE-1.",
      },
    },
  };
  assert.equal(
    mensajeErrorProceso(error, "No se pudo iniciar la ejecución."),
    "Torre de secado concurrente está ocupado por EJ-TOR-RACE-1.",
  );
  assert.equal(esErrorDeEquipo(error), true);
});

test("muestra limpio el contrato operacional estructurado", () => {
  const error = {
    response: {
      status: 409,
      data: {
        code: "EQUIPO_OCUPADO",
        message: "Evaporador 1 está ocupado por EJ-9.",
        details: { equipo: ["Evaporador 1 está ocupado por EJ-9."] },
      },
    },
  };
  assert.equal(
    mensajeErrorProceso(error, "No se pudo iniciar."),
    "Evaporador 1 está ocupado por EJ-9.",
  );
  assert.equal(esErrorDeEquipo(error), true);
});

test("usa el mensaje de respaldo cuando no hay respuesta DRF", () => {
  assert.equal(mensajeErrorProceso(new Error("red"), "Sin conexión."), "Sin conexión.");
});

test("identifica solamente errores de equipo para refrescar disponibilidad", () => {
  assert.equal(esErrorDeEquipo({ response: { data: { equipo: "Torre ocupada." } } }), true);
  assert.equal(esErrorDeEquipo({ response: { data: { error: "Evaporador 1 está ocupado por EJ-9." } } }), true);
  assert.equal(esErrorDeEquipo({ response: { data: { detail: "Sin permiso." } } }), false);
});

test("identifica el contrato 409 de versión para refrescar la bandeja afectada", () => {
  const conflicto = {
    response: {
      status: 409,
      data: { code: "version_conflict", version_actual: 3 },
    },
  };
  assert.equal(esConflictoVersion(conflicto), true);
  assert.equal(
    esConflictoVersion({ response: { status: 409, data: { code: "otro" } } }),
    false,
  );
});
