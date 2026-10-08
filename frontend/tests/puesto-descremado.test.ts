import assert from "node:assert/strict";
import test from "node:test";

import {
  accionDeDescremadora, avisosDeCierre, corridaCancelable, moduloDeResolver,
} from "../src/services/puesto-descremado.ts";

const base = {
  equipo_id: 1, codigo: "des-01", nombre: "Descremadora 1", corrida: null,
  motivos_para_tomar: [] as string[], motivos_para_iniciar: [] as string[],
  resolver_en: null, avisos: [] as string[], en_calidad: null,
};
const corrida = {
  id: 8, ejecucion_id: 120, ejecucion_codigo: "EJ-DES-8", ejecucion_estado: "preparacion",
  estado: "borrador", silo_entera: "Silo 3", litros_entrada: "1000.00",
  grasa_entrada: "2.610", sng_entrada: "8.700", silo_descremada: "Tk02",
  litros_descremada_plan: "976.40", estanque_crema: "TkC2", litros_crema_plan: "23.60",
  destino_crema: "siguiente_proceso", iniciada_en: null,
};

test("una descremadora disponible ofrece preparar", () => {
  assert.deepEqual(accionDeDescremadora({ ...base, estado: "disponible" }), { tipo: "preparar", habilitada: true, motivo: null });
});

test("una descremadora en CIP no se prepara y dice por qué", () => {
  const fila = { ...base, estado: "disponible" as const, motivos_para_tomar: ["Descremadora 1 está en CIP."] };
  assert.deepEqual(accionDeDescremadora(fila), { tipo: "preparar", habilitada: false, motivo: "Descremadora 1 está en CIP." });
});

test("una preparada sin motivos se puede iniciar", () => {
  assert.deepEqual(accionDeDescremadora({ ...base, estado: "preparada", corrida }), { tipo: "iniciar", habilitada: true, motivo: null });
});

test("una preparada con motivos muestra el primero y no habilita iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida, motivos_para_iniciar: ["Silo 3: falta la segunda firma.", "otro"] };
  assert.deepEqual(accionDeDescremadora(fila), { tipo: "iniciar", habilitada: false, motivo: "Silo 3: falta la segunda firma." });
});

test("los avisos no deshabilitan iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida, avisos: ["Último aseo con observación."] };
  assert.equal(accionDeDescremadora(fila).habilitada, true);
});

test("una preparación sin corrida no se puede iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida: { ...corrida, id: null } };
  assert.equal(accionDeDescremadora(fila).habilitada, false);
});

test("en curso ofrece cerrar solo en ejecución, espejo de cerrar_descremacion", () => {
  const enCurso = { ...base, estado: "en_curso" as const, corrida: { ...corrida, estado: "en_curso", ejecucion_estado: "ejecucion" } };
  assert.deepEqual(accionDeDescremadora(enCurso), { tipo: "cerrar", habilitada: true, motivo: null });
  for (const ejecucion_estado of ["pausada", "bloqueada"]) {
    const fila = { ...enCurso, corrida: { ...enCurso.corrida, ejecucion_estado } };
    assert.equal(accionDeDescremadora(fila).habilitada, false);
    assert.match(accionDeDescremadora(fila).motivo ?? "", new RegExp(ejecucion_estado));
  }
});

test("se cancela una corrida en borrador con la ejecución preparada o heredada en borrador", () => {
  assert.equal(corridaCancelable(corrida), 8);
  assert.equal(corridaCancelable({ ...corrida, ejecucion_estado: "borrador" }), 8);
  assert.equal(corridaCancelable({ ...corrida, estado: "en_curso", ejecucion_estado: "ejecucion" }), null);
  assert.equal(corridaCancelable({ ...corrida, ejecucion_estado: "cancelada" }), null);
  assert.equal(corridaCancelable({ ...corrida, id: null }), null);
  assert.equal(corridaCancelable(null), null);
});

test("los motivos del silo se resuelven en Silos, módulo de Recepción", () => {
  assert.equal(moduloDeResolver("/silos"), "recepcion");
  assert.equal(moduloDeResolver("/calidad/inocuidad"), "inocuidad");
});

const revisionVacia = { avisos_limites: [], avisos_balance: [], merma_l: null, desvio_grasa_kg: null };

test("los avisos del cierre solo dicen «sin avisos» si el servidor respondió", () => {
  const vacia = avisosDeCierre({ revision: revisionVacia, error: false, pendiente: false });
  assert.equal(vacia.mensaje, "Sin avisos con lo registrado.");
  assert.deepEqual(vacia.avisos, []);
  assert.equal(vacia.vigente, true);
  assert.equal(vacia.advertencia, undefined);

  const sinRespuesta = avisosDeCierre({ revision: null, error: false, pendiente: false });
  assert.notEqual(sinRespuesta.mensaje, "Sin avisos con lo registrado.");
  assert.equal(sinRespuesta.vigente, false);
});

test("si la revisión falla, se dice y la confirmación avisa que el servidor los calcula al cerrar", () => {
  const fallo = avisosDeCierre({ revision: null, error: true, pendiente: false });
  assert.equal(fallo.mensaje, "No se pudieron revisar los avisos; el servidor los vuelve a calcular al cerrar.");
  assert.deepEqual(fallo.avisos, []);
  assert.equal(fallo.vigente, false);
  assert.match(fallo.advertencia ?? "", /el servidor los calcula al cerrar/);
});

test("mientras se teclea no se muestran avisos viejos", () => {
  const vieja = {
    ...revisionVacia,
    avisos_limites: [{ codigo: "grasa_descremada_alta", mensaje: "Grasa alta" }],
    avisos_balance: ["Balance descuadrado"],
  };
  const pendiente = avisosDeCierre({ revision: vieja, error: false, pendiente: true });
  assert.deepEqual(pendiente.avisos, []);
  assert.equal(pendiente.vigente, false);
  assert.equal(pendiente.mensaje, "Revisando avisos…");
  assert.match(pendiente.advertencia ?? "", /el servidor los calcula al cerrar/);

  const lista = avisosDeCierre({ revision: vieja, error: false, pendiente: false });
  assert.deepEqual(lista.avisos, ["Grasa alta", "Balance descuadrado"]);
  assert.equal(lista.mensaje, null);
  // La confirmación repite solo los límites: el balance no es un aviso de calidad.
  assert.equal(lista.advertencia, "Grasa alta");
});
