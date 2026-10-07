import type { Usuario } from "./sesion.ts";

/*
  Quién opera el puesto de Evaporación. Refleja `procesos.permisos`
  (`tipos_operables_para` + `TIPOS_OPERABLES_POR_AREA`): la evaporación es una
  etapa de Condensación, así que la opera esa área y el administrador —rol
  efectivo `admin`, que el servidor también da al área Administración—.

  Secado escribe lotes (`puedeEscribir("produccion")`), pero no opera el
  evaporador: el servidor le responde 403 al abrir un lote ahí y al iniciar.
  Un perfil sin área —el rol heredado `produccion`— tampoco opera.

  Como `puedeEscribir`, esto es cortesía para no ofrecer botones que el
  servidor rechaza; el permiso se aplica allá.
*/
type ConPerfil = (Pick<Usuario, "rol"> & { perfil: Pick<NonNullable<Usuario["perfil"]>, "area"> | null }) | null | undefined;

export function puedeOperarEvaporacion(usuario: ConPerfil): boolean {
  if (!usuario) return false;
  const area = usuario.perfil?.area;
  return usuario.rol === "admin" || area === "administracion" || area === "condensacion";
}
