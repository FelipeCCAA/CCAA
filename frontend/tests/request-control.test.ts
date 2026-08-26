import assert from "node:assert/strict";
import test from "node:test";

import {
  claveGet,
  esLecturaMiBorrador,
  LimitadorSolicitudes,
  recursoDeEscrituraSoloBorrador,
} from "../src/services/request-control.ts";

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

test("draft write invalidates only its matching resume read", () => {
  const recurso = recursoDeEscrituraSoloBorrador(
    "/api/recepcion/analisis-silo/42/guardar-borrador/",
  );

  assert.equal(recurso, "recepcion/analisis-silo");
  assert.equal(
    esLecturaMiBorrador(
      "recepcion/analisis-silo/mi-borrador/?silo=3",
      recurso!,
    ),
    true,
  );
  assert.equal(
    esLecturaMiBorrador("recepcion/recepciones/mi-borrador/", recurso!),
    false,
  );
});

test("confirming a draft preserves global invalidation", () => {
  assert.equal(
    recursoDeEscrituraSoloBorrador(
      "produccion/lotes/7/confirmar-borrador/",
    ),
    null,
  );
});
