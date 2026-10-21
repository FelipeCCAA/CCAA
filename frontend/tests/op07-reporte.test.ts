import assert from "node:assert/strict";
import test from "node:test";
import { mensajeErrorReporte } from "../src/services/error-reporte.ts";

const detalle = "El reporte supera 1000 recepciones; reduce el rango de fechas.";
const datos = { code: "REPORTE_DEMASIADO_GRANDE", detail: detalle };

test("muestra la explicación de límite al consultar JSON", async () => {
  assert.equal(await mensajeErrorReporte({ response: { status: 400, data: datos } }, "Error"), detalle);
});
test("lee la explicación JSON recibida como Blob al exportar", async () => {
  const data = new Blob([JSON.stringify(datos)], { type: "application/json" });
  assert.equal(await mensajeErrorReporte({ response: { status: 400, data } }, "Error"), detalle);
});
test("un error HTML o red no sustituye el mensaje de respaldo", async () => {
  for (const error of [new Error("red"), { response: { status: 500, data: new Blob(["<html>error</html>"]) } },
    { response: { status: 400, data: new Blob(["sin json"]) } }]) {
    assert.equal(await mensajeErrorReporte(error, "Reintenta"), "Reintenta");
  }
});
test("no presenta datos internos ni errores de autorización como límite", async () => {
  assert.equal(await mensajeErrorReporte({ response: { status: 403, data: datos } }, "Sin acceso"), "Sin acceso");
  assert.equal(await mensajeErrorReporte({ response: { status: 400, data: { detail: "Interno" } } }, "Error"), "Error");
});
