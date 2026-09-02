import assert from "node:assert/strict";
import test from "node:test";

import {
  bandejaDeSecado,
  calcularBalanceSecado,
} from "../src/services/secado-proceso.ts";

/*
  Aquí no se prueban `estadoFisicoSecado` ni `siguienteAccionSecado`.

  Son tablas de estado → frase: comprobar que devuelven la cadena escrita dos
  líneas más arriba no dice si el sistema funciona, solo que nadie corrigió una
  errata. Lo que sí decide algo —qué bandeja recibe cada corrida, y si el
  balance cierra— está cubierto abajo.
*/

test("clasifica las corridas sin confundir estado físico con Calidad", () => {
  assert.equal(bandejaDeSecado("preparacion"), "activas");
  assert.equal(bandejaDeSecado("ejecucion"), "activas");
  assert.equal(bandejaDeSecado("pausada"), "activas");
  assert.equal(bandejaDeSecado("bloqueada"), "activas");
  assert.equal(bandejaDeSecado("pendiente_control"), "calidad");
  assert.equal(bandejaDeSecado("cerrada", "pendiente"), "calidad");
  assert.equal(bandejaDeSecado("cerrada"), "terminadas");
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
