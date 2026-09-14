import assert from "node:assert/strict";
import test from "node:test";

import { rutaDeNotificacion } from "../src/services/notificaciones-operacionales.ts";
import type { Notificacion } from "../src/services/inventario.service.ts";

function notificacion(tipo: string, accionUrl = ""): Notificacion {
  return {
    id: 1, tipo, titulo: "Trabajo", mensaje: "Detalle",
    documento_tipo: "", documento_id: null, accion_url: accionUrl,
    leida_en: null, creada_en: "2026-09-11T10:00:00Z",
  };
}

test("usa el destino explícito entregado por el handoff", () => {
  assert.equal(rutaDeNotificacion(notificacion("material_liberado", "/secado")), "/secado");
});

test("mantiene rutas útiles para notificaciones históricas", () => {
  assert.equal(rutaDeNotificacion(notificacion("producto_pendiente_calidad")), "/calidad");
  assert.equal(rutaDeNotificacion(notificacion("producto_liberado")), "/inventario");
});
