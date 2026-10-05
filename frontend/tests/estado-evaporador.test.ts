import assert from "node:assert/strict";
import test from "node:test";

import { tarjetaEvaporador } from "../src/services/estado-evaporador.ts";

interface CorridaFicticia {
  id: number;
  equipo_id: number | null;
  estado: string;
  ejecucion_codigo: string;
}

function corrida(datos: Partial<CorridaFicticia> & { id: number }): CorridaFicticia {
  return { equipo_id: 1, estado: "borrador", ejecucion_codigo: `EJ-${datos.id}`, ...datos };
}

test("sin corridas para el equipo, la tarjeta está disponible", () => {
  const tarjeta = tarjetaEvaporador(1, [corrida({ id: 1, equipo_id: 2 })], []);
  assert.equal(tarjeta.estado, "disponible");
  assert.equal(tarjeta.corridaActiva, null);
});

test("una corrida en borrador está preparada, no disponible", () => {
  const preparada = corrida({ id: 70, estado: "borrador" });
  const tarjeta = tarjetaEvaporador(1, [preparada], [{ codigo: "EJ-70", estado: "borrador" }]);
  assert.equal(tarjeta.estado, "preparada");
  assert.equal(tarjeta.etiqueta, "Preparada");
  assert.equal(tarjeta.corridaActiva, preparada);
});

test(
  "con una corrida en curso y una abandonada en borrador, la tarjeta y la acción son de la misma",
  () => {
    // Reproduce el caso real: EJ-PROD-70 quedó abandonada en borrador (un
    // lote anulado no cierra su EjecucionProceso) y EJ-PROD-72 es la corrida
    // que de verdad ocupa el evaporador.
    const abandonada = corrida({ id: 70, estado: "borrador" });
    const enCurso = corrida({ id: 72, estado: "en_proceso" });
    const ejecuciones = [
      { codigo: "EJ-70", estado: "borrador" },
      { codigo: "EJ-72", estado: "ejecucion" },
    ];

    // El orden de llegada no debe cambiar el resultado.
    for (const corridas of [[abandonada, enCurso], [enCurso, abandonada]]) {
      const tarjeta = tarjetaEvaporador(1, corridas, ejecuciones);
      assert.equal(tarjeta.estado, "ejecucion");
      assert.equal(tarjeta.corridaActiva?.ejecucion_codigo, "EJ-72");
    }
  },
);

test("pausada y bloqueada se leen de la ejecución de la MISMA corrida, no de otra", () => {
  const activa = corrida({ id: 72, estado: "en_proceso" });
  const pausada = tarjetaEvaporador(1, [activa], [{ codigo: "EJ-72", estado: "pausada" }]);
  assert.equal(pausada.estado, "pausada");
  assert.equal(pausada.corridaActiva, activa);

  const bloqueada = tarjetaEvaporador(1, [activa], [{ codigo: "EJ-72", estado: "bloqueada" }]);
  assert.equal(bloqueada.estado, "bloqueada");
  assert.equal(bloqueada.corridaActiva, activa);
});

test("pendiente de Calidad no reserva el evaporador", () => {
  const pendiente = corrida({ id: 50, estado: "pendiente_calidad" });
  const tarjeta = tarjetaEvaporador(1, [pendiente], []);
  assert.equal(tarjeta.estado, "disponible");
  assert.equal(tarjeta.corridaActiva, null);
  assert.equal(tarjeta.pendienteCalidad, pendiente);
});
