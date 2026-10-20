/// <reference types="node" />
import assert from "node:assert/strict";
import test from "node:test";
import { errorPrecisionLitros, validarActo } from "./balance.ts";

test("litros respetan 0,01 L sin redondear entradas", () => {
  for (const valor of ["0", "0.01", "120.25", 20.5, null, ""]) {
    assert.equal(errorPrecisionLitros({ volumen: valor }), "");
  }
  for (const valor of ["0.001", "12.345", "10.000", -1, Infinity, "1e-3"]) {
    assert.match(errorPrecisionLitros({ volumen: valor }), /0,01 L/);
  }
});

test("disponibilidad de catálogo elimina sólo ceros, sin redondear fracciones reales", () => {
  assert.equal(errorPrecisionLitros({ disponible: Number("60000.000") }), "");
  assert.match(errorPrecisionLitros({ disponible: Number("60000.001") }), /0,01 L/);
});

test("actos exigen motivo y datos específicos sin mutar receta", () => {
  const base = { tipo: "medicion" as const, motivo: "Aforo en silo", volumen_medido: "10.25" };
  assert.equal(validarActo(base), "");
  assert.match(validarActo({ ...base, volumen_medido: "10.251" }), /0,01 L/);
  assert.match(validarActo({ ...base, volumen_medido: "" }), /volumen medido/);
  assert.match(validarActo({ tipo: "adicion", motivo: "Ajuste real", litros: "1.01" }), /silo/);
  assert.equal(validarActo({ tipo: "retiro", motivo: "Retiro real", litros: "1.01", silo_contraparte: 2 }), "");
  assert.match(validarActo({ tipo: "documental", motivo: "Error de digitación", rectificacion: { observaciones: "" } }), /anterior y nuevo/);
  assert.equal(validarActo({ tipo: "documental", motivo: "Error de digitación", rectificacion: { observaciones: "Dato corregido" } }), "");
  assert.match(validarActo({ ...base, motivo: "ab" }), /motivo/);
});
