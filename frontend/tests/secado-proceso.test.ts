import assert from "node:assert/strict";
import test from "node:test";

import {
  bandejaDeSecado,
  calcularBalanceSecado,
  estadoFisicoSecado,
  siguienteAccionSecado,
} from "../src/services/secado-proceso.ts";

test("clasifica las corridas sin confundir estado físico con Calidad", () => {
  assert.equal(bandejaDeSecado("preparacion"), "activas");
  assert.equal(bandejaDeSecado("ejecucion"), "activas");
  assert.equal(bandejaDeSecado("pausada"), "activas");
  assert.equal(bandejaDeSecado("bloqueada"), "activas");
  assert.equal(bandejaDeSecado("pendiente_control"), "calidad");
  assert.equal(bandejaDeSecado("cerrada", "pendiente"), "calidad");
  assert.equal(bandejaDeSecado("cerrada"), "terminadas");
});

test("respeta la regla física de ocupación del equipo", () => {
  assert.equal(estadoFisicoSecado("preparacion"), "Equipo reservado");
  assert.equal(estadoFisicoSecado("ejecucion"), "Equipo ocupado");
  assert.equal(estadoFisicoSecado("pausada"), "Equipo ocupado");
  assert.equal(estadoFisicoSecado("bloqueada"), "Equipo ocupado");
  assert.equal(estadoFisicoSecado("pendiente_control"), "Equipo disponible");
  assert.equal(siguienteAccionSecado("pendiente_control"), "Esperar decisión de Calidad");
});

test("calcula el balance con números sin mezclar unidades formateadas", () => {
  const balance = calcularBalanceSecado({
    kgAlimentacion: 600,
    solidosEntradaPct: 48,
    kgPolvo: 280,
    kgFinos: 5,
    kgMerma: 3,
  });

  assert.equal(balance.kgRecuperados, 285);
  assert.equal(balance.kgSalidas, 288);
  assert.equal(balance.kgNoContabilizados, 312);
  assert.equal(balance.kgSolidosEntrada, 288);
  assert.equal(balance.rendimientoRecuperacionPct, 47.5);
  assert.equal(balance.esPosible, true);
});

test("marca como imposible una salida superior a la alimentación", () => {
  const balance = calcularBalanceSecado({
    kgAlimentacion: 100,
    solidosEntradaPct: 48,
    kgPolvo: 100,
    kgFinos: 5,
    kgMerma: 1,
  });

  assert.equal(balance.esPosible, false);
  assert.equal(balance.kgNoContabilizados, -6);
});
