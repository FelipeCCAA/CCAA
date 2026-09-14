import assert from "node:assert/strict";
import test from "node:test";

import { rutaDeEtapa, totalEsperandoCalidad } from "../src/services/planta-ahora.ts";
import type { PlantaAhora } from "../src/services/procesos.service.ts";

test("cada etapa abre su puesto operacional y conserva un destino seguro", () => {
  assert.equal(rutaDeEtapa("descremacion"), "/procesos?seccion=descremacion");
  assert.equal(rutaDeEtapa("secado"), "/secado");
  assert.equal(rutaDeEtapa("etapa_futura"), "/produccion");
});

test("Calidad suma procesos y unidades logísticas sin mezclar otros bloqueos", () => {
  const indicadores = {
    esperando_calidad: 3,
    producto_pendiente_calidad: 7,
  } as PlantaAhora["indicadores"];

  assert.equal(totalEsperandoCalidad(indicadores), 10);
  assert.equal(totalEsperandoCalidad(null), 0);
});
