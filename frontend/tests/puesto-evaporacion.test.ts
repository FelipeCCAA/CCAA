import assert from "node:assert/strict";
import test from "node:test";

import { accionDeEvaporador, corridaCancelable, destinosDelConcentrado } from "../src/services/puesto-evaporacion.ts";

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

test("en curso ofrece cerrar", () => {
  assert.equal(accionDeEvaporador({ ...base, estado: "en_curso", corrida }).tipo, "cerrar");
});

test("esperando Calidad la máquina está libre: ofrece abrir lote", () => {
  // `pendiente_control` no ocupa el equipo; lo que espera es el concentrado.
  assert.deepEqual(
    accionDeEvaporador({ ...base, estado: "esperando_calidad", corrida }),
    { tipo: "abrir", habilitada: true, motivo: null },
  );
});

test("el silo de origen del vale no se ofrece como destino del concentrado", () => {
  const destinos = [
    { id: 1, codigo: "SILO 2", libre_l: "1000.00" },
    { id: 2, codigo: "PC-1", libre_l: "5000.00" },
  ];
  assert.deepEqual(destinosDelConcentrado(destinos, "SILO 2").map((d) => d.codigo), ["PC-1"]);
});

test("sin vale elegido se ofrecen todos los destinos", () => {
  const destinos = [{ id: 1, codigo: "SILO 2", libre_l: "1000.00" }];
  assert.deepEqual(destinosDelConcentrado(destinos, undefined), destinos);
});

test("solo una preparada se puede cancelar, y por su corrida", () => {
  assert.equal(corridaCancelable({ ...base, estado: "preparada", corrida }), 9);
  // Los motivos que impiden iniciar no impiden cancelar: suelen ser la razón.
  assert.equal(
    corridaCancelable({ ...base, estado: "preparada", corrida, motivos_para_iniciar: ["TK 3: sin análisis."] }),
    9,
  );
  assert.equal(corridaCancelable({ ...base, estado: "en_curso", corrida }), null);
  assert.equal(corridaCancelable({ ...base, estado: "esperando_calidad", corrida }), null);
  assert.equal(corridaCancelable({ ...base, estado: "disponible" }), null);
});
