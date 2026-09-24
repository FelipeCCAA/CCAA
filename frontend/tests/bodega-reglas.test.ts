import assert from "node:assert/strict";
import test from "node:test";

import { ajustePorConteo, leerCantidad, tiposDeDestino } from "../src/services/bodega-reglas.ts";

test("contar menos de lo que dice el sistema pide un ajuste negativo por la diferencia", () => {
  assert.deepEqual(ajustePorConteo("20.000", "18"), { tipo: "negativo", cantidad: 2 });
});

test("contar más pide un ajuste positivo, sin arrastrar error de coma flotante", () => {
  assert.deepEqual(ajustePorConteo("13.000", "13.1"), { tipo: "positivo", cantidad: 0.1 });
});

test("si el conteo coincide no hay nada que ajustar", () => {
  assert.equal(ajustePorConteo("20.000", 20), null);
});

test("la cantidad se lee con coma o punto decimal y rechaza lo que no es positivo", () => {
  assert.equal(leerCantidad("12,5"), 12.5);
  assert.equal(leerCantidad(" 3 "), 3);
  assert.equal(leerCantidad("0"), null);
  assert.equal(leerCantidad("-2"), null);
  assert.equal(leerCantidad("abc"), null);
  assert.equal(leerCantidad(""), null);
});

test("recibir va a cuarentena si el material pasa por Calidad, y a disponible si no", () => {
  assert.deepEqual(tiposDeDestino("recibir", { requiereCalidad: true }), ["cuarentena"]);
  assert.deepEqual(tiposDeDestino("recibir", { requiereCalidad: false }), ["disponible"]);
});

test("reubicar material no le cambia el estado: mismo tipo de ubicación", () => {
  assert.deepEqual(tiposDeDestino("reubicar-material", { origenTipo: "cuarentena" }), ["cuarentena"]);
});

test("los pallets se mueven a ubicaciones disponibles, y consumir o contar no tienen destino", () => {
  assert.deepEqual(tiposDeDestino("reubicar-pallet", {}), ["disponible"]);
  assert.deepEqual(tiposDeDestino("ubicar-liberado", {}), ["disponible"]);
  assert.deepEqual(tiposDeDestino("consumir", {}), []);
  assert.deepEqual(tiposDeDestino("contar", {}), []);
});
