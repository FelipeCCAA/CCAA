import type { Usuario } from "./sesion";

export type ModuloSistema =
  | "dashboard" | "recepcion" | "estandarizacion" | "produccion"
  | "envasado" | "procesos" | "planificacion" | "inventario"
  | "calidad" | "inocuidad" | "registros" | "auditoria"
  | "maestros" | "administracion";

const AREAS: Record<ModuloSistema, string[]> = {
  dashboard: ["administracion"],
  recepcion: ["recepcion", "calidad"],
  estandarizacion: ["recepcion", "condensacion", "calidad"],
  produccion: ["condensacion", "secado", "calidad"],
  envasado: ["envase", "calidad"],
  procesos: ["condensacion", "secado", "calidad"],
  planificacion: ["condensacion", "secado", "calidad"],
  inventario: ["bodega", "compras", "despacho", "calidad"],
  calidad: ["calidad"],
  inocuidad: ["aseo", "calidad"],
  registros: ["condensacion", "secado", "envase", "calidad"],
  auditoria: ["calidad"],
  maestros: ["administracion"],
  administracion: [],
};

const LEGADO: Record<string, ModuloSistema[]> = {
  recepcion: ["recepcion", "estandarizacion"],
  produccion: ["estandarizacion", "produccion", "envasado", "procesos", "planificacion", "registros"],
  calidad: ["recepcion", "estandarizacion", "produccion", "envasado", "procesos", "planificacion", "inventario", "calidad", "inocuidad", "registros", "auditoria"],
};

export function esAdministradorGlobal(usuario?: Usuario | null): boolean {
  return usuario?.rol === "admin" || usuario?.perfil?.area === "administracion";
}

export function puedeAccederModulo(usuario: Usuario | null | undefined, modulo: ModuloSistema): boolean {
  if (!usuario) return false;
  if (esAdministradorGlobal(usuario)) return true;
  if (modulo === "administracion") return usuario.perfil?.nivel === "admin";
  const area = usuario.perfil?.area;
  if (area) return AREAS[modulo].includes(area);
  return Boolean(usuario.rol && LEGADO[usuario.rol]?.includes(modulo));
}

export function destinoInicial(usuario: Usuario): string {
  if (esAdministradorGlobal(usuario)) return "/dashboard";
  if (usuario.perfil?.nivel === "admin") return "/administracion";
  const porArea: Record<string, string> = {
    recepcion: "/leche", condensacion: "/produccion", secado: "/produccion",
    envase: "/envasado", calidad: "/calidad", aseo: "/calidad/inocuidad",
    bodega: "/inventario", compras: "/inventario", despacho: "/inventario",
  };
  const area = usuario.perfil?.area;
  if (area && porArea[area]) return porArea[area];
  const rol = usuario.rol;
  if (rol === "recepcion") return "/leche";
  if (rol === "produccion") return "/produccion";
  if (rol === "calidad") return "/calidad";
  return "/acceso-restringido";
}
