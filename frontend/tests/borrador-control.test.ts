import assert from "node:assert/strict";
import test from "node:test";

import { borradorCambio, huellaBorrador } from "../src/hooks/borrador-control.ts";

test("un render con otro objeto pero los mismos datos no vuelve a guardar", () => {
  const primera = huellaBorrador({ lote: 9, litros: 500, observacion: "" });
  const nuevoRender = huellaBorrador({ lote: 9, litros: 500, observacion: "" });

  assert.equal(borradorCambio(primera, nuevoRender), false);
});

test("un cambio real habilita un nuevo autoguardado", () => {
  const guardada = huellaBorrador({ lote: 9, litros: 500 });
  const editada = huellaBorrador({ lote: 9, litros: 550 });

  assert.equal(borradorCambio(guardada, editada), true);
});
