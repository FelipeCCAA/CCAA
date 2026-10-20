import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer, type ViteDevServer } from "vite";

import type { Despacho } from "../src/services/inventario.service.ts";

let servidor: ViteDevServer;
let HojaDeCarga: React.ComponentType<{ hoja: Despacho; autoriza: boolean; onCambio: (mensaje: string) => void }>;

before(async () => {
  // Render real del componente, sin servidor HTTP, backend, sesión o requests.
  servidor = await createServer({ server: { middlewareMode: true, hmr: false }, appType: "custom", logLevel: "silent" });
  const modulo = await servidor.ssrLoadModule("/src/pages/Despacho/HojaDeCarga.tsx");
  HojaDeCarga = modulo.default;
});

after(async () => { await servidor?.close(); });

function renderizar(requiere: boolean, autoriza = true) {
  const hoja: Despacho = {
    id: 1, numero: "OP01-UI", cliente: 1, cliente_nombre: "Cliente sintético",
    estado: "autorizado", guia_despacho: "", transportista: "", patente: "",
    creado_en: "2026-10-20T12:00:00Z", autorizado_en: "2026-10-20T12:01:00Z",
    despachado_en: null, detalles: [], detalles_granel: [], motivo_cancelacion: "", cancelado_en: null,
    requiere_reautorizacion: requiere, motivo_reautorizacion: requiere ? "Calidad debe revisar y firmar nuevamente." : "",
  };
  return renderToStaticMarkup(createElement(HojaDeCarga, { hoja, autoriza, onCambio: () => {} }));
}

test("una hoja obsoleta explica el bloqueo y permite reautorizar, sin ofrecer salida", () => {
  const html = renderizar(true);
  assert.match(html, /Requiere revisión antes de salir/);
  assert.match(html, /Calidad debe revisar y firmar nuevamente/);
  assert.match(html, /Revisar y autorizar nuevamente/);
  assert.doesNotMatch(html, /Ejecutar salida/);
});

test("renovada la autorización vuelve a ofrecer salida sin pedir otra aprobación", () => {
  const html = renderizar(false);
  assert.match(html, /Ejecutar salida/);
  assert.doesNotMatch(html, /Revisar y autorizar nuevamente/);
});

test("quien no tiene permiso ve el motivo y no puede autorizar ni ejecutar", () => {
  const html = renderizar(true, false);
  assert.match(html, /Espera la autorización/);
  assert.match(html, /Calidad debe revisar/);
  assert.doesNotMatch(html, /Revisar y autorizar nuevamente|Ejecutar salida/);
});
