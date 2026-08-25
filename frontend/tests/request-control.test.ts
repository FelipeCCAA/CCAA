import assert from "node:assert/strict";
import test from "node:test";

import { claveGet, LimitadorSolicitudes } from "../src/services/request-control.ts";

test("solo deja dos lecturas activas al mismo tiempo", async () => {
  const limite = new LimitadorSolicitudes(2);
  const liberar1 = await limite.adquirir();
  const liberar2 = await limite.adquirir();
  let entroLaTercera = false;
  const tercera = limite.adquirir().then((liberar) => {
    entroLaTercera = true;
    return liberar;
  });

  await Promise.resolve();
  assert.equal(entroLaTercera, false);
  liberar1();
  const liberar3 = await tercera;
  assert.equal(entroLaTercera, true);
  liberar2();
  liberar3();
});

test("la caché separa parámetros y credenciales", () => {
  assert.notEqual(
    claveGet("silos", { pagina: 1 }, "a"),
    claveGet("silos", { pagina: 2 }, "a"),
  );
  assert.notEqual(claveGet("silos", {}, "a"), claveGet("silos", {}, "b"));
});
