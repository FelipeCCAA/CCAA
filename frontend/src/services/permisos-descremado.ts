import type { Usuario } from "./sesion.ts";

/*
  Quién opera el puesto de Descremado. Refleja `procesos.permisos`
  (`TIPOS_OPERABLES_POR_AREA`): la etapa Descremación la opera Condensación y
  el administrador —rol efectivo `admin`, que el servidor también da al área
  Administración—. Calidad ve el puesto en modo consulta; Secado escribe
  lotes pero no opera la descremadora.

  Cortesía para no ofrecer botones que el servidor rechaza con 403; el
  permiso se aplica allá.
*/
type ConPerfil = (Pick<Usuario, "rol"> & { perfil: Pick<NonNullable<Usuario["perfil"]>, "area"> | null }) | null | undefined;

export function puedeOperarDescremado(usuario: ConPerfil): boolean {
  if (!usuario) return false;
  const area = usuario.perfil?.area;
  return usuario.rol === "admin" || area === "administracion" || area === "condensacion";
}
