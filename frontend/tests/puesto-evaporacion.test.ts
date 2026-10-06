import assert from "node:assert/strict";
import test from "node:test";

import { accionDeEvaporador } from "../src/services/puesto-evaporacion.ts";

const base = { equipo_id: 1, codigo: "ev", nombre: "Evaporador", corrida: null, motivos_para_iniciar: [] as string[] };
const corrida = { id: 9, codigo: "EJ-9", lote_codigo: "L", silo_origen: "TK 3", silo_destino: "SILO 6", litros_entrada: "100", iniciada_en: null };

test("un evaporador disponible ofrece abrir lote", () => {
  assert.deepEqual(accionDeEvaporador({ ...base, estado: "disponible" }), { tipo: "abrir", habilitada: true, motivo: null });
});

test("una preparada sin motivos se puede iniciar", () => {
  assert.deepEqual(accionDeEvaporador({ ...base, estado: "preparada", corrida }), { tipo: "iniciar", habilitada: true, motivo: null });
});

test("una preparada con motivos muestra el primero y no habilita iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida, motivos_para_iniciar: ["TK 3: sin análisis vigente."] };
  assert.deepEqual(accionDeEvaporador(fila), { tipo: "iniciar", habilitada: false, motivo: "TK 3: sin análisis vigente." });
});

test("en curso ofrece cerrar y esperando Calidad no ofrece nada", () => {
  assert.equal(accionDeEvaporador({ ...base, estado: "en_curso", corrida }).tipo, "cerrar");
  assert.equal(accionDeEvaporador({ ...base, estado: "esperando_calidad", corrida }).tipo, "ninguna");
});
