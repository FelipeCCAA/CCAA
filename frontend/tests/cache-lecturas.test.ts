import assert from "node:assert/strict";
import test from "node:test";

import { CacheLecturas } from "../src/services/request-control.ts";

/* Un reloj que la prueba mueve a mano: la ventana de la caché se mide sin esperar. */
function relojManual() {
  let ahora = 1_000;
  return { reloj: () => ahora, avanzar: (ms: number) => { ahora += ms; } };
}

/* Cuenta las veces que la lectura llegó a la red. */
function red() {
  let llamadas = 0;
  return {
    pedir: () => { llamadas += 1; return Promise.resolve(`respuesta ${llamadas}`); },
    llamadas: () => llamadas,
  };
}

test("dentro de la ventana la misma lectura sale de la caché", async () => {
  const { reloj, avanzar } = relojManual();
  const cache = new CacheLecturas<string>(10_000, 20, reloj);
  const servidor = red();
  assert.equal(await cache.leer("k", "puesto/", servidor.pedir), "respuesta 1");
  avanzar(5_000);
  assert.equal(await cache.leer("k", "puesto/", servidor.pedir), "respuesta 1");
  assert.equal(servidor.llamadas(), 1);
});

test("vencida la ventana, la lectura vuelve a la red", async () => {
  const { reloj, avanzar } = relojManual();
  const cache = new CacheLecturas<string>(10_000, 20, reloj);
  const servidor = red();
  await cache.leer("k", "puesto/", servidor.pedir);
  avanzar(10_001);
  assert.equal(await cache.leer("k", "puesto/", servidor.pedir), "respuesta 2");
});

/* «Actualizar» lo pulsa alguien que sabe que el dato cambió en otra sesión
   —la segunda firma de Calidad—: esa lectura no puede salir de la caché. */
test("vaciar la caché hace que una recarga dentro de la ventana vaya a la red", async () => {
  const { reloj, avanzar } = relojManual();
  const cache = new CacheLecturas<string>(10_000, 20, reloj);
  const servidor = red();
  await cache.leer("k", "puesto/", servidor.pedir);
  avanzar(2_000);
  cache.vaciar();
  assert.equal(await cache.leer("k", "puesto/", servidor.pedir), "respuesta 2");
  assert.equal(servidor.llamadas(), 2);
});

test("vaciar tampoco reutiliza una lectura que ya iba en camino", async () => {
  const cache = new CacheLecturas<string>(10_000, 20, relojManual().reloj);
  let soltar: (valor: string) => void = () => {};
  const vieja = cache.leer("k", "puesto/", () => new Promise((r) => { soltar = r; }));
  cache.vaciar();
  const servidor = red();
  const nueva = cache.leer("k", "puesto/", servidor.pedir);
  soltar("vieja");
  assert.equal(await vieja, "vieja");
  assert.equal(await nueva, "respuesta 1");
  /* La lectura vieja, al terminar, no pisa la nueva en la caché. */
  assert.equal(await cache.leer("k", "puesto/", servidor.pedir), "respuesta 1");
  assert.equal(servidor.llamadas(), 1);
});

test("dos lecturas simultáneas comparten la misma petición", async () => {
  const cache = new CacheLecturas<string>(10_000, 20, relojManual().reloj);
  const servidor = red();
  const [a, b] = await Promise.all([
    cache.leer("k", "puesto/", servidor.pedir), cache.leer("k", "puesto/", servidor.pedir),
  ]);
  assert.equal(a, b);
  assert.equal(servidor.llamadas(), 1);
});

test("quitar borra solo las lecturas cuya URL cumple el criterio", async () => {
  const cache = new CacheLecturas<string>(10_000, 20, relojManual().reloj);
  const servidor = red();
  await cache.leer("a", "recepciones/mi-borrador/", servidor.pedir);
  await cache.leer("b", "silos/", servidor.pedir);
  cache.quitar((url) => url.endsWith("mi-borrador/"));
  await cache.leer("a", "recepciones/mi-borrador/", servidor.pedir);
  await cache.leer("b", "silos/", servidor.pedir);
  assert.equal(servidor.llamadas(), 3);
});

test("conserva como máximo el número de respuestas pedido", async () => {
  const cache = new CacheLecturas<string>(10_000, 2, relojManual().reloj);
  const servidor = red();
  for (const clave of ["a", "b", "c"]) await cache.leer(clave, clave, servidor.pedir);
  await cache.leer("a", "a", servidor.pedir);
  assert.equal(servidor.llamadas(), 4);
});
