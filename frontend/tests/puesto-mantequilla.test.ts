import assert from "node:assert/strict";
import test from "node:test";

import {
  accionDeMantequera, corridaCancelable, estadoDelBalance, moduloDeResolver,
} from "../src/services/puesto-mantequilla.ts";

const base = {
  equipo_id: 1, codigo: "mant-01", nombre: "Mantequera 1", tipo: "mantequera", corrida: null,
  motivos_para_tomar: [] as string[], motivos_para_iniciar: [] as string[],
  resolver_en: null, avisos: [] as string[], en_calidad: null,
};
const corrida = {
  id: 9, estado: "borrador", ejecucion_id: 140, ejecucion_codigo: "EJ-MANT-311",
  ejecucion_estado: "preparacion", orden_codigo: "OP-0412", producto: "Mantequilla sin sal 20 kg",
  lote_mantequilla: "CCAA6281LM-01", lote_crema: "INT-DES-7-CR", kg_crema: "60.000",
  lote_suero: null, iniciada_en: null,
};
const revision = {
  entrada_kg: "60.000", clasificado_kg: "59.000", diferencia_kg: "1.000", cuadra: false,
  mensaje: "El cierre debe clasificar el 100% de la crema: 1.000 kg faltan por clasificar.",
  errores: {} as Record<string, string>,
};

test("una mantequera disponible ofrece preparar", () => {
  assert.deepEqual(accionDeMantequera({ ...base, estado: "disponible" }), { tipo: "preparar", habilitada: true, motivo: null });
});

test("una mantequera en CIP no se prepara y dice por qué", () => {
  const fila = { ...base, estado: "disponible" as const, motivos_para_tomar: ["Mantequera 1 está en CIP."] };
  assert.deepEqual(accionDeMantequera(fila), { tipo: "preparar", habilitada: false, motivo: "Mantequera 1 está en CIP." });
});

test("una preparada sin motivos se puede iniciar", () => {
  assert.deepEqual(accionDeMantequera({ ...base, estado: "preparada", corrida }), { tipo: "iniciar", habilitada: true, motivo: null });
});

test("una preparada con motivos muestra el primero y no habilita iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida, motivos_para_iniciar: ["El lote de crema INT-DES-7-CR todavía no está liberado por Calidad.", "otro"] };
  assert.deepEqual(accionDeMantequera(fila), { tipo: "iniciar", habilitada: false, motivo: "El lote de crema INT-DES-7-CR todavía no está liberado por Calidad." });
});

test("los avisos no deshabilitan iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida, avisos: ["Último aseo con observación."] };
  assert.equal(accionDeMantequera(fila).habilitada, true);
});

test("una preparación sin corrida no se puede iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida: { ...corrida, id: null } };
  assert.equal(accionDeMantequera(fila).habilitada, false);
});

test("en curso ofrece registrar el balance solo en ejecución, espejo de cerrar_mantequilla", () => {
  const enCurso = { ...base, estado: "en_curso" as const, corrida: { ...corrida, estado: "en_proceso", ejecucion_estado: "ejecucion" } };
  assert.deepEqual(accionDeMantequera(enCurso), { tipo: "cerrar", habilitada: true, motivo: null });
  for (const ejecucion_estado of ["pausada", "bloqueada"]) {
    const fila = { ...enCurso, corrida: { ...enCurso.corrida, ejecucion_estado } };
    assert.equal(accionDeMantequera(fila).habilitada, false);
    assert.match(accionDeMantequera(fila).motivo ?? "", new RegExp(ejecucion_estado));
  }
});

test("se cancela una corrida en borrador con la ejecución preparada o heredada en borrador", () => {
  assert.equal(corridaCancelable(corrida), 9);
  assert.equal(corridaCancelable({ ...corrida, ejecucion_estado: "borrador" }), 9);
  assert.equal(corridaCancelable({ ...corrida, estado: "en_proceso", ejecucion_estado: "ejecucion" }), null);
  assert.equal(corridaCancelable({ ...corrida, estado: "anulada", ejecucion_estado: "cancelada" }), null);
  assert.equal(corridaCancelable(null), null);
});

test("el balance incompleto lo dice el servidor y no deja cerrar", () => {
  const estado = estadoDelBalance(revision, false);
  assert.equal(estado.franja, "incompleto");
  assert.equal(estado.titulo, "Balance incompleto");
  assert.equal(estado.detalle, revision.mensaje);
  assert.equal(estado.puedeCerrar, false);
});

test("el balance excedido se lee del signo que manda el servidor", () => {
  const estado = estadoDelBalance({ ...revision, clasificado_kg: "61.000", diferencia_kg: "-1.000", mensaje: "El cierre debe clasificar el 100% de la crema: 1.000 kg exceden la entrada." }, false);
  assert.equal(estado.franja, "excedido");
  assert.equal(estado.titulo, "Balance excedido");
});

test("un balance completo deja cerrar solo sin errores", () => {
  const completo = { ...revision, clasificado_kg: "60.000", diferencia_kg: "0.000", cuadra: true, mensaje: null };
  const estado = estadoDelBalance(completo, false);
  assert.equal(estado.franja, "completo");
  assert.equal(estado.puedeCerrar, true);
  assert.match(estado.detalle ?? "", /60 kg de 60 kg clasificados/);

  const conError = estadoDelBalance({ ...completo, errores: { kg_suero: "Esta corrida no tiene un lote de suero asociado: registra 0 kg." } }, false);
  assert.equal(conError.puedeCerrar, false);
  assert.deepEqual(conError.errores, ["Esta corrida no tiene un lote de suero asociado: registra 0 kg."]);
});

test("una revisión en camino o fallida no habla de lo que se va a cerrar", () => {
  const completo = { ...revision, cuadra: true, mensaje: null, diferencia_kg: "0.000" };
  assert.equal(estadoDelBalance(completo, true).franja, "revisando");
  assert.equal(estadoDelBalance(completo, true).puedeCerrar, false);
  assert.equal(estadoDelBalance(null, false).franja, "revisando");
  assert.equal(estadoDelBalance(null, false, true).franja, "sin_revision");
  assert.equal(estadoDelBalance(null, false, true).puedeCerrar, false);
});

test("los motivos de la orden se resuelven en Planificación", () => {
  assert.equal(moduloDeResolver("/planificacion"), "planificacion");
  assert.equal(moduloDeResolver("/calidad"), "calidad");
});
