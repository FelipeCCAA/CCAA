import assert from "node:assert/strict";
import test from "node:test";

import { agruparHojas, buscarPalletPorCodigo, leerCantidadChilena, totalesCarga } from "../src/services/despacho-reglas.ts";

test("las hojas se agrupan por lo que falta hacer, y de las despachadas solo las de hoy", () => {
  const hojas = [
    { id: 1, estado: "borrador", despachado_en: null },
    { id: 2, estado: "autorizado", despachado_en: null },
    { id: 3, estado: "despachado", despachado_en: "2026-09-24T15:00:00-03:00" },
    { id: 4, estado: "despachado", despachado_en: "2026-09-22T15:00:00-03:00" },
    { id: 5, estado: "cancelado", despachado_en: null },
  ];
  const grupos = agruparHojas(hojas, "2026-09-24");
  assert.deepEqual(grupos.borrador.map((h) => h.id), [1]);
  assert.deepEqual(grupos.autorizada.map((h) => h.id), [2]);
  assert.deepEqual(grupos.despachadaHoy.map((h) => h.id), [3]);
});

test("los totales suman kilos de pallets y de graneles en kg, y los litros aparte", () => {
  assert.deepEqual(
    totalesCarga(
      [{ kg_neto: "500.000" }, { kg_neto: 487.5 }],
      [{ cantidad: "1200", unidad: "kg" }, { cantidad: 8000, unidad: "L" }],
    ),
    { pallets: 2, kg: 2187.5, litros: 8000 },
  );
});

test("el código escaneado se busca sin importar mayúsculas ni espacios", () => {
  const pallets = [{ pallet_codigo: "PAL-001" }, { pallet_codigo: "PAL-002" }];
  assert.equal(buscarPalletPorCodigo(pallets, " pal-002 ")?.pallet_codigo, "PAL-002");
  assert.equal(buscarPalletPorCodigo(pallets, "PAL-9"), null);
});

test("los totales no distinguen mayúsculas en la unidad del granel", () => {
  assert.deepEqual(
    totalesCarga([], [{ cantidad: 1200, unidad: "Kg" }, { cantidad: 8000, unidad: "l" }]),
    { pallets: 0, kg: 1200, litros: 8000 },
  );
});

test("la cantidad de granel se lee en formato chileno", () => {
  assert.equal(leerCantidadChilena("8.000"), 8000);
  assert.equal(leerCantidadChilena("8000"), 8000);
  assert.equal(leerCantidadChilena("12,5"), 12.5);
  assert.equal(leerCantidadChilena("1.234,567"), 1234.567);
  assert.equal(leerCantidadChilena("abc"), null);
  assert.equal(leerCantidadChilena("0"), null);
  assert.equal(leerCantidadChilena("-1"), null);
});
