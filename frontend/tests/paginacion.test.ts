import assert from "node:assert/strict";
import test from "node:test";

import { conFiltros, recorrerPaginas, rutaDePagina, type RespuestaLista } from "../src/services/paginacion.ts";

test("la página siguiente se pide por la ruta relativa, no por la URL absoluta del backend", () => {
  assert.equal(
    rutaDePagina("inventario/movimientos/?q=saco", "http://127.0.0.1:8000/api/inventario/movimientos/?page=3&q=saco"),
    "inventario/movimientos/?q=saco&page=3",
  );
  assert.equal(rutaDePagina("inventario/ajustes/", "/api/inventario/ajustes/?page=2"), "inventario/ajustes/?page=2");
});

test("recorre todas las páginas y junta las filas", async () => {
  const pedidas: string[] = [];
  const paginas: Record<string, RespuestaLista<number>> = {
    "x/": { count: 3, next: "http://b/api/x/?page=2", previous: null, results: [1, 2] },
    "x/?page=2": { count: 3, next: null, previous: "http://b/api/x/", results: [3] },
  };
  const filas = await recorrerPaginas<number>(async (ruta) => { pedidas.push(ruta); return paginas[ruta]; }, "x/");
  assert.deepEqual(filas, [1, 2, 3]);
  assert.deepEqual(pedidas, ["x/", "x/?page=2"]);
});

test("una respuesta sin paginar se devuelve tal cual", async () => {
  assert.deepEqual(await recorrerPaginas<number>(async () => [7, 8], "y/"), [7, 8]);
});

test("una lista sin fin avisa en vez de colgar la pantalla", async () => {
  const infinita = async (): Promise<RespuestaLista<number>> =>
    ({ count: 999, next: "http://b/api/z/?page=2", previous: null, results: [1] });
  await assert.rejects(recorrerPaginas(infinita, "z/", 2), /más de 2 páginas/);
});

test("los filtros vacíos no viajan y los booleanos van como 1", () => {
  assert.equal(
    conFiltros("inventario/producto-terminado/", { q: "pal", estado: "", ubicacion: null, cargable: true, con_saldo: false, page: 2 }),
    "inventario/producto-terminado/?q=pal&cargable=1&page=2",
  );
  assert.equal(conFiltros("inventario/despachos/?vigentes=1", { q: "de6" }), "inventario/despachos/?vigentes=1&q=de6");
  assert.equal(conFiltros("a/", {}), "a/");
});
