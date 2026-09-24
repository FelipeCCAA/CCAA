import assert from "node:assert/strict";
import test from "node:test";

import {
  contextoOperacionalPara,
  esEnlaceOperacionalActual,
  esRutaOperacionalActual,
  navegacionPara,
} from "../src/services/navegacion-operacional.ts";
import { destinoInicial, puedeAccederModulo } from "../src/services/access-control.ts";
import type { Usuario } from "../src/services/sesion.ts";

function usuarioDeArea(area: string, areaEtiqueta: string, rol: Usuario["rol"]): Usuario {
  return {
    id: 1,
    username: area,
    nombre: "Operador",
    apellido: areaEtiqueta,
    email: "",
    rol,
    capacidades: [],
    perfil: {
      cargo: "Operador",
      area,
      area_etiqueta: areaEtiqueta,
      turno: "A",
      rol: rol ?? "lectura",
      rol_etiqueta: "Operador",
      nivel: "trabajador",
      nivel_etiqueta: "Trabajador",
      debe_cambiar_password: false,
    },
  };
}

function etiquetas(usuario: Usuario, grupo: string): string[] {
  return navegacionPara(usuario).grupos.find((item) => item.etiqueta === grupo)?.enlaces
    .map((item) => item.etiqueta) ?? [];
}

test("Condensación entra a Mi Producción y ve solamente sus procesos operables", () => {
  const usuario = usuarioDeArea("condensacion", "Condensación", "produccion");
  const navegacion = navegacionPara(usuario);
  const produccion = etiquetas(usuario, "Producción");

  assert.equal(navegacion.inicio.ruta, "/produccion");
  assert.match(navegacion.inicio.etiqueta, /Condensación/);
  assert.ok(produccion.includes("Estandarización"));
  assert.ok(produccion.includes("Descremado"));
  assert.ok(produccion.includes("Evaporación"));
  assert.ok(produccion.includes("Mantequilla"));
  assert.ok(!produccion.includes("Secado"));
});

test("Secado entra a su puesto y no recibe accesos operacionales de Condensación", () => {
  const usuario = usuarioDeArea("secado", "Secado", "produccion");
  const navegacion = navegacionPara(usuario);
  const produccion = etiquetas(usuario, "Producción");

  assert.equal(navegacion.inicio.ruta, "/secado");
  assert.ok(!produccion.includes("Descremado"));
  assert.ok(!produccion.includes("Evaporación"));
  assert.ok(!produccion.includes("Mantequilla"));
});

test("Calidad conserva lectura transversal y su centro como entrada del puesto", () => {
  const usuario = usuarioDeArea("calidad", "Calidad", "calidad");
  const navegacion = navegacionPara(usuario);
  const produccion = etiquetas(usuario, "Producción");

  assert.equal(navegacion.inicio.ruta, "/calidad");
  assert.ok(produccion.includes("Descremado"));
  assert.ok(produccion.includes("Secado"));
  assert.ok(!navegacion.grupos.flatMap((grupo) => grupo.enlaces).some(
    (enlace) => enlace.ruta === "/calidad",
  ));
});

test("Administración conserva la visión global sin duplicar su panel de entrada", () => {
  const usuario: Usuario = {
    id: 2,
    username: "admin",
    nombre: "Administración",
    apellido: "",
    email: "",
    rol: "admin",
    capacidades: [],
    perfil: null,
  };
  const navegacion = navegacionPara(usuario);

  assert.equal(navegacion.inicio.ruta, "/dashboard");
  assert.equal(navegacion.area, "Administración");
  assert.ok(navegacion.grupos.some((grupo) => grupo.etiqueta === "Recepción"));
  assert.ok(navegacion.grupos.some((grupo) => grupo.etiqueta === "Producción"));
  assert.ok(!navegacion.grupos.flatMap((grupo) => grupo.enlaces).some(
    (enlace) => enlace.ruta === "/dashboard",
  ));
});

test("una jefatura accede a Planta Ahora por responsabilidad, no por ubicación", () => {
  const usuario = usuarioDeArea("secado", "Secado", "produccion");
  if (!usuario.perfil) throw new Error("El perfil de prueba es obligatorio");
  usuario.perfil.nivel = "admin";

  assert.equal(puedeAccederModulo(usuario, "dashboard"), true);
});

test("Recepción no accede a Administración desde una URL directa", () => {
  const usuario = usuarioDeArea("recepcion", "Recepción", "recepcion");

  assert.equal(puedeAccederModulo(usuario, "administracion"), false);
});

test("la ubicación distingue subprocesos que comparten una URL", () => {
  const usuario = usuarioDeArea("condensacion", "Condensación", "produccion");

  assert.ok(esRutaOperacionalActual(
    "/procesos?seccion=descremacion",
    "/procesos",
    "?seccion=descremacion",
  ));
  assert.ok(!esRutaOperacionalActual(
    "/procesos?seccion=mantequilla",
    "/procesos",
    "?seccion=descremacion",
  ));
  assert.equal(
    contextoOperacionalPara(
      usuario,
      "/procesos",
      "?seccion=descremacion",
    ).actual.etiqueta,
    "Descremado",
  );
});

test("las URLs compatibles conservan el contexto operacional", () => {
  const usuario = usuarioDeArea("calidad", "Calidad", "calidad");
  const contexto = contextoOperacionalPara(usuario, "/liberacion");

  assert.equal(contexto.actual.etiqueta, "Expedientes y liberación");
  assert.ok(esEnlaceOperacionalActual(contexto.actual, "/liberacion"));
});

test("Compras vuelve: es el inicio de Compras y aparece en el menú de quien tiene acceso", () => {
  const compras = usuarioDeArea("compras", "Compras", null);
  assert.equal(destinoInicial(compras), "/abastecimiento");
  assert.equal(puedeAccederModulo(compras, "abastecimiento"), true);

  // Compras es el destino inicial de Compras, así que la deduplicación del
  // propio inicio la saca de su grupo (mismo criterio que Administración con
  // /dashboard y Calidad con /calidad, ya fijado más arriba). Bodega también
  // tiene acceso a abastecimiento pero su inicio es otra ruta, así que ahí sí
  // se ve la entrada.
  const bodega = usuarioDeArea("bodega", "Bodega", null);
  assert.ok(etiquetas(bodega, "Envasado y logística").includes("Compras y abastecimiento"));
});

test("Despacho se abre con la capacidad, no con el área", () => {
  const sinPermiso = usuarioDeArea("despacho", "Despacho", null);
  assert.equal(puedeAccederModulo(sinPermiso, "despacho"), false);
  assert.equal(puedeAccederModulo({ ...sinPermiso, capacidades: ["despacho_crear"] }, "despacho"), true);
});

test("Bodega entra a su puesto, y el puesto es su inicio", () => {
  const bodega = usuarioDeArea("bodega", "Bodega", null);
  assert.equal(puedeAccederModulo(bodega, "bodega"), true);
  assert.equal(destinoInicial(bodega), "/bodega");
  // El menú oculta la entrada que coincide con el inicio del usuario; la
  // entrada se comprueba con quien no la tiene de inicio.
  const compras = usuarioDeArea("compras", "Compras", null);
  assert.equal(puedeAccederModulo(compras, "bodega"), false);
});

test("Despacho aparece en el menú solo con la capacidad", () => {
  // Un usuario de Bodega: su inicio es /bodega, así que la entrada de
  // Despacho no se oculta por ser su inicio y se mide solo la capacidad.
  const bodega = usuarioDeArea("bodega", "Bodega", null);
  assert.ok(!etiquetas(bodega, "Envasado y logística").includes("Despacho"));
  assert.ok(etiquetas({ ...bodega, capacidades: ["despacho_crear"] }, "Envasado y logística").includes("Despacho"));
  assert.equal(
    destinoInicial({ ...usuarioDeArea("despacho", "Despacho", null), capacidades: ["despacho_crear"] }),
    "/despacho",
  );
});

test("Despacho sin la capacidad no aterriza en un puesto que va a rechazarlo", () => {
  // Antes de esta regla, `destinoInicial` mandaba a /despacho solo mirando el
  // área, y `puedeAccederModulo` exige además la capacidad: alguien de
  // Despacho sin `despacho_crear` ni `despacho_autorizar` caía en
  // AccesoRestringido apenas entraba. /inventario sí lo acepta: "despacho"
  // está en `AREAS.inventario`.
  const sinCapacidad = usuarioDeArea("despacho", "Despacho", null);
  assert.equal(destinoInicial(sinCapacidad), "/inventario");
  assert.equal(puedeAccederModulo(sinCapacidad, "inventario"), true);
});
