import {
  destinoInicial,
  esAdministradorGlobal,
  puedeAccederModulo,
  type ModuloSistema,
} from "./access-control.ts";
import type { Usuario } from "./sesion.ts";

export type IconoNavegacion =
  | "auditoria"
  | "calidad"
  | "configuracion"
  | "despacho"
  | "documentos"
  | "envasado"
  | "estandarizacion"
  | "inicio"
  | "inventario"
  | "inocuidad"
  | "planificacion"
  | "procesos"
  | "produccion"
  | "recepcion"
  | "secado"
  | "silos"
  | "usuarios";

export interface EnlaceOperacional {
  etiqueta: string;
  ruta: string;
  modulo: ModuloSistema;
  icono: IconoNavegacion;
  nivel?: "proceso";
  areas?: string[];
  alias?: string[];
}

export interface GrupoOperacional {
  etiqueta: string;
  enlaces: EnlaceOperacional[];
}

const GRUPOS: GrupoOperacional[] = [
  {
    etiqueta: "Recepción",
    enlaces: [
      { etiqueta: "Recepción de leche", ruta: "/leche", modulo: "recepcion", icono: "recepcion" },
      { etiqueta: "Silos principales", ruta: "/silos", modulo: "recepcion", icono: "silos" },
    ],
  },
  {
    etiqueta: "Producción",
    enlaces: [
      { etiqueta: "Panel de producción", ruta: "/produccion", modulo: "produccion", icono: "produccion" },
      { etiqueta: "Estandarización", ruta: "/estandarizacion", modulo: "estandarizacion", icono: "estandarizacion", nivel: "proceso" },
      { etiqueta: "Descremado", ruta: "/procesos?seccion=descremacion", modulo: "procesos", icono: "procesos", nivel: "proceso", areas: ["condensacion", "calidad"] },
      { etiqueta: "Evaporación", ruta: "/produccion#evaporacion", modulo: "produccion", icono: "produccion", nivel: "proceso", areas: ["condensacion", "calidad"] },
      { etiqueta: "Secado", ruta: "/secado", modulo: "secado", icono: "secado", nivel: "proceso", areas: ["secado", "calidad"] },
      { etiqueta: "Mantequilla", ruta: "/procesos?seccion=mantequilla", modulo: "procesos", icono: "procesos", nivel: "proceso", areas: ["condensacion", "calidad"] },
      { etiqueta: "Trazabilidad productiva", ruta: "/procesos#trazabilidad", modulo: "procesos", icono: "procesos" },
      { etiqueta: "Planificación", ruta: "/planificacion", modulo: "planificacion", icono: "planificacion" },
    ],
  },
  {
    etiqueta: "Envasado y logística",
    enlaces: [
      { etiqueta: "Envase y pallets", ruta: "/envasado", modulo: "envasado", icono: "envasado" },
      { etiqueta: "Inventario y despacho", ruta: "/inventario", modulo: "inventario", icono: "inventario" },
    ],
  },
  {
    etiqueta: "Calidad y control",
    enlaces: [
      { etiqueta: "Centro de Calidad", ruta: "/calidad", modulo: "calidad", icono: "calidad" },
      { etiqueta: "Expedientes y liberación", ruta: "/calidad/expedientes", modulo: "calidad", icono: "estandarizacion", alias: ["/liberacion"] },
      { etiqueta: "Inocuidad · Aseos", ruta: "/calidad/inocuidad", modulo: "inocuidad", icono: "inocuidad" },
      { etiqueta: "Registros operacionales", ruta: "/calidad/registros", modulo: "registros", icono: "documentos" },
      { etiqueta: "Auditoría", ruta: "/auditoria", modulo: "auditoria", icono: "auditoria" },
    ],
  },
  {
    etiqueta: "Gestión",
    enlaces: [
      { etiqueta: "Panel general", ruta: "/dashboard", modulo: "dashboard", icono: "inicio" },
      { etiqueta: "Maestros", ruta: "/maestros", modulo: "maestros", icono: "configuracion" },
      { etiqueta: "Administración", ruta: "/administracion", modulo: "administracion", icono: "usuarios" },
    ],
  },
];

export interface NavegacionOperacional {
  inicio: EnlaceOperacional;
  area: string;
  grupos: GrupoOperacional[];
}

function moduloDelInicio(ruta: string): ModuloSistema {
  const enlace = GRUPOS.flatMap((grupo) => grupo.enlaces).find(
    (item) => item.ruta === ruta,
  );
  return enlace?.modulo ?? "dashboard";
}

export function navegacionPara(usuario: Usuario): NavegacionOperacional {
  const rutaInicio = destinoInicial(usuario);
  const area = usuario.perfil?.area_etiqueta || usuario.perfil?.rol_etiqueta ||
    (esAdministradorGlobal(usuario) ? "Administración" : "Mi área");
  const inicio: EnlaceOperacional = {
    etiqueta: `Mi área · ${area}`,
    ruta: rutaInicio,
    modulo: moduloDelInicio(rutaInicio),
    icono: "inicio",
  };
  const grupos = GRUPOS.map((grupo) => ({
    ...grupo,
    enlaces: grupo.enlaces.filter(
      (enlace) =>
        enlace.ruta !== rutaInicio &&
        puedeAccederModulo(usuario, enlace.modulo) &&
        (!enlace.areas ||
          !usuario.perfil?.area ||
          esAdministradorGlobal(usuario) ||
          enlace.areas.includes(usuario.perfil.area)),
    ),
  })).filter((grupo) => grupo.enlaces.length > 0);
  return { inicio, area, grupos };
}

export function esRutaOperacionalActual(
  ruta: string,
  pathnameActual: string,
  searchActual = "",
  hashActual = "",
): boolean {
  const destino = new URL(ruta, "https://ccaa.local");
  if (
    pathnameActual !== destino.pathname &&
    !(destino.pathname === "/leche" && pathnameActual.startsWith("/leche/"))
  ) {
    return false;
  }

  if (destino.search) {
    const actuales = new URLSearchParams(searchActual);
    return [...destino.searchParams].every(
      ([clave, valor]) => actuales.get(clave) === valor,
    );
  }
  if (destino.hash) return hashActual === destino.hash;

  // Los accesos generales no se marcan junto a un subproceso específico.
  if (pathnameActual === "/procesos" && searchActual) return false;
  if (pathnameActual === "/produccion" && hashActual) return false;
  return true;
}

export function esEnlaceOperacionalActual(
  enlace: EnlaceOperacional,
  pathname: string,
  search = "",
  hash = "",
): boolean {
  return [enlace.ruta, ...(enlace.alias ?? [])].some((ruta) =>
    esRutaOperacionalActual(ruta, pathname, search, hash),
  );
}

export interface ContextoOperacional {
  area: string;
  grupo: string;
  actual: EnlaceOperacional;
  inicio: EnlaceOperacional;
}

export function contextoOperacionalPara(
  usuario: Usuario,
  pathname: string,
  search = "",
  hash = "",
): ContextoOperacional {
  const navegacion = navegacionPara(usuario);
  for (const grupo of navegacion.grupos) {
    const actual = grupo.enlaces.find((enlace) =>
      esEnlaceOperacionalActual(enlace, pathname, search, hash),
    );
    if (actual) {
      return { area: navegacion.area, grupo: grupo.etiqueta, actual, inicio: navegacion.inicio };
    }
  }
  return {
    area: navegacion.area,
    grupo: "Mi área",
    actual: navegacion.inicio,
    inicio: navegacion.inicio,
  };
}
