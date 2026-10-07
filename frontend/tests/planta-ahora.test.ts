import assert from "node:assert/strict";
import test from "node:test";

import { rutaDeEtapa, textoIniciarEnPuesto, totalEsperandoCalidad } from "../src/services/planta-ahora.ts";
import type { PlantaAhora } from "../src/services/procesos.service.ts";

test("cada etapa abre su puesto operacional y conserva un destino seguro", () => {
  assert.equal(rutaDeEtapa("descremacion"), "/procesos?seccion=descremacion");
  assert.equal(rutaDeEtapa("secado"), "/produccion/secado");
  assert.equal(rutaDeEtapa("etapa_futura"), "/produccion");
});

test("todos los etapa_tipo reales (EtapaProceso.Tipo) llevan a un destino que existe", () => {
  // Antes `BandejaTrabajoArea.destinoDe` armaba su propia tabla con
  // `/procesos?seccion=${etapa_tipo}`: para "envasado" y "transferencia" esa
  // sección no existe, y evaporación/condensación debían ir a /produccion, no
  // a /procesos. Esta prueba fija la tabla única (`rutaDeEtapa`) para los diez
  // valores que declara el backend.
  assert.equal(rutaDeEtapa("recepcion"), "/leche");
  assert.equal(rutaDeEtapa("estandarizacion"), "/estandarizacion");
  assert.equal(rutaDeEtapa("descremacion"), "/procesos?seccion=descremacion");
  assert.equal(rutaDeEtapa("evaporacion"), "/produccion/evaporacion");
  assert.equal(rutaDeEtapa("condensacion"), "/produccion/evaporacion");
  assert.equal(rutaDeEtapa("secado"), "/produccion/secado");
  assert.equal(rutaDeEtapa("envasado"), "/envasado");
  assert.equal(rutaDeEtapa("mantequilla"), "/procesos?seccion=mantequilla");
  assert.equal(rutaDeEtapa("transferencia"), "/produccion");
  assert.equal(rutaDeEtapa("otro"), "/produccion");
});

test("Secado y Descremado se inician en su puesto, espejo de MENSAJES_INICIO_EN_PUESTO", () => {
  assert.equal(textoIniciarEnPuesto("secado", "preparacion"), "Iniciar en el puesto de Secado");
  assert.equal(textoIniciarEnPuesto("descremacion", "preparacion"), "Iniciar en el puesto de Descremado");
  // Reanudar no es iniciar, y las demás etapas siguen en la bandeja.
  assert.equal(textoIniciarEnPuesto("descremacion", "pausada"), null);
  assert.equal(textoIniciarEnPuesto("mantequilla", "preparacion"), null);
});

test("Calidad suma procesos y unidades logísticas sin mezclar otros bloqueos", () => {
  const indicadores = {
    esperando_calidad: 3,
    producto_pendiente_calidad: 7,
  } as PlantaAhora["indicadores"];

  assert.equal(totalEsperandoCalidad(indicadores), 10);
  assert.equal(totalEsperandoCalidad(null), 0);
});
