import assert from "node:assert/strict";
import test from "node:test";

import { accionDeTorre, corridaCancelable, moduloDeResolver, situacionDeCorrida } from "../src/services/puesto-secado.ts";

const base = {
  equipo_id: 1, codigo: "e1", nombre: "Torre 1", corrida: null,
  motivos_para_iniciar: [] as string[], motivos_para_tomar: [] as string[],
  resolver_en: null, avisos: [] as string[],
  falta_inspeccion: false, en_calidad: null,
};
const corrida = {
  id: 12, ejecucion_id: 90, ejecucion_codigo: "CONT-40", ejecucion_estado: "preparacion",
  lote_codigo: "CCAA6279VB-01", origen: "SILO 6", cantidad: "18000.00", unidad: "L", iniciada_en: null,
};

test("una torre disponible ofrece tomar concentrado", () => {
  assert.deepEqual(accionDeTorre({ ...base, estado: "disponible" }), { tipo: "tomar", habilitada: true, motivo: null });
});

test("una torre disponible en CIP no se toma y dice por qué", () => {
  const fila = { ...base, estado: "disponible" as const, motivos_para_tomar: ["Torre 1 está en CIP: no puede producir mientras se asea."] };
  assert.deepEqual(accionDeTorre(fila), {
    tipo: "tomar", habilitada: false, motivo: "Torre 1 está en CIP: no puede producir mientras se asea.",
  });
});

test("una preparada sin motivos se puede iniciar", () => {
  assert.deepEqual(accionDeTorre({ ...base, estado: "preparada", corrida }), { tipo: "iniciar", habilitada: true, motivo: null });
});

test("una preparada con motivos muestra el primero y no habilita iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida, motivos_para_iniciar: ["Torre 1 está en CIP.", "otro"] };
  assert.deepEqual(accionDeTorre(fila), { tipo: "iniciar", habilitada: false, motivo: "Torre 1 está en CIP." });
});

test("los avisos no deshabilitan iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida, avisos: ["Falta la inspección"], falta_inspeccion: true };
  assert.equal(accionDeTorre(fila).habilitada, true);
});

test("una preparación sin corrida de Secado no se puede iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida: { ...corrida, id: null }, motivos_para_iniciar: [] };
  assert.equal(accionDeTorre(fila).habilitada, false);
});

test("en curso ofrece cerrar, salvo bloqueada", () => {
  const enCurso = { ...base, estado: "en_curso" as const, corrida: { ...corrida, ejecucion_estado: "ejecucion" } };
  assert.deepEqual(accionDeTorre(enCurso), { tipo: "cerrar", habilitada: true, motivo: null });
  const bloqueada = { ...enCurso, corrida: { ...corrida, ejecucion_estado: "bloqueada" } };
  assert.equal(accionDeTorre(bloqueada).habilitada, false);
  assert.match(accionDeTorre(bloqueada).motivo ?? "", /bloqueada/);
});

test("solo una preparada con corrida se puede cancelar, aunque tenga motivos para no iniciar", () => {
  assert.equal(corridaCancelable({ ...base, estado: "preparada", corrida }), 12);
  assert.equal(
    corridaCancelable({ ...base, estado: "preparada", corrida, motivos_para_iniciar: ["Torre 1 está en CIP."] }),
    12,
  );
  assert.equal(corridaCancelable({ ...base, estado: "preparada", corrida: { ...corrida, id: null } }), null);
  assert.equal(corridaCancelable({ ...base, estado: "en_curso", corrida: { ...corrida, ejecucion_estado: "ejecucion" } }), null);
  assert.equal(corridaCancelable({ ...base, estado: "disponible" }), null);
});

test("la situación de una corrida sale de bandejaDeSecado", () => {
  assert.equal(situacionDeCorrida("ejecucion"), "En la torre");
  assert.equal(situacionDeCorrida("pausada"), "En la torre");
  assert.equal(situacionDeCorrida("cerrada", "pendiente"), "Esperando Calidad");
  assert.equal(situacionDeCorrida("cerrada", "liberado"), "Terminada");
  assert.equal(situacionDeCorrida("cancelada"), "Cancelada");
});

test("una preparada se nombra «Preparada», no «En la torre»", () => {
  assert.equal(situacionDeCorrida("preparacion"), "Preparada");
});

test("un estado que no se conoce no se nombra «Cancelada»: usa la etiqueta del servidor", () => {
  assert.equal(situacionDeCorrida("borrador", "no_requerida", "Borrador"), "Borrador");
  assert.equal(situacionDeCorrida("estado_nuevo"), "estado_nuevo");
});

test("cada «dónde se resuelve» sabe a qué módulo lleva", () => {
  assert.equal(moduloDeResolver("/calidad/inocuidad"), "inocuidad");
  assert.equal(moduloDeResolver("/calidad"), "calidad");
  assert.equal(moduloDeResolver("/registros"), "registros");
  // Un destino que no se conoce no se ofrece: no se sabe si se puede entrar.
  assert.equal(moduloDeResolver("/otra-cosa"), null);
});
