import { puedeOperarEvaporacion } from "./permisos-evaporacion.ts";

/*
  Quién opera el puesto de Mantequilla. Refleja `procesos.permisos`
  (`TIPOS_OPERABLES_POR_AREA`): la etapa Mantequilla la opera Condensación y
  el administrador, igual que la evaporación y el descremado —por eso es la
  misma regla y no una copia que pueda divergir—. Calidad ve el puesto en
  modo consulta; Secado escribe lotes pero no opera la mantequera.

  Cortesía para no ofrecer botones que el servidor rechaza con 403; el
  permiso se aplica allá.
*/
export const puedeOperarMantequilla = puedeOperarEvaporacion;
