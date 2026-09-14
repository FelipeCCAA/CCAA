import assert from "node:assert/strict";
import test from "node:test";

import {
  contextoOperacionalPara,
  esEnlaceOperacionalActual,
  esRutaOperacionalActual,
  navegacionPara,
} from "../src/services/navegacion-operacional.ts";
import { puedeAccederModulo } from "../src/services/access-control.ts";
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
