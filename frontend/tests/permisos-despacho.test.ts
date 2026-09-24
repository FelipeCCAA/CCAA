import assert from "node:assert/strict";
import test from "node:test";

import { puedeAutorizarDespacho, puedeDespachar } from "../src/services/permisos-despacho.ts";

test("sin sesión no se despacha", () => {
  assert.equal(puedeDespachar(null), false);
  assert.equal(puedeAutorizarDespacho(undefined), false);
});

test("crear despachos no alcanza para autorizarlos", () => {
  const usuario = { capacidades: ["despacho_crear"] };
  assert.equal(puedeDespachar(usuario), true);
  assert.equal(puedeAutorizarDespacho(usuario), false);
});

test("quien autoriza también arma hojas, como decide el servidor", () => {
  const usuario = { capacidades: ["despacho_autorizar"] };
  assert.equal(puedeDespachar(usuario), true);
  assert.equal(puedeAutorizarDespacho(usuario), true);
});

test("el área o el rol no dan permiso: solo las capacidades", () => {
  assert.equal(puedeDespachar({ capacidades: [] }), false);
  assert.equal(puedeDespachar({ capacidades: ["inventario_transferir", "inventario_ajustar"] }), false);
});
