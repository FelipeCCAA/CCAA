import api from "./api";

import type { Pagina } from "./produccion.service";


/*
  Inocuidad: control de proceso con el PCC 1, y monitoreos PPRO.

  Lo que se registra aquí decide si el lote se puede liberar. Una lectura
  fuera del límite del PCC 1 significa que la leche pasó sin el tratamiento
  térmico que la hace inocua, y un PPRO No-OK sin acción correctiva es un
  incidente abierto: los dos bloquean la firma de Calidad.

  El veredicto **no se guarda**: lo recalcula el backend desde las lecturas y
  el límite del propio control. Corregir una lectura mal tecleada desbloquea
  el lote sin tocar nada más.
*/

export interface CatalogosInocuidad {
  equipo_control: { valor: string; etiqueta: string }[];
  turno: { valor: string; etiqueta: string }[];
  tipo_ppro: { valor: string; etiqueta: string }[];
  resultado_ppro: { valor: string; etiqueta: string }[];
  /* Las claves que el PCC 1 vigila dentro de `valores`. Vienen del backend
     para que la captura las rotule igual que el dominio las evalúa: si la
     pantalla las renombrara, el control dejaría de encontrarlas y el PCC
     pasaría a no vigilar nada en silencio. */
  pcc1: { temperatura: string; caudal: string };
}


export interface LecturaControl {
  id: number;
  control: number;
  hora: string;
  valores: Record<string, number>;
  observacion: string;
}


export interface IncumplimientoPcc1 {
  hora: string;
  parametro: string;
  valor: number;
  limite: number;
  sentido: "bajo" | "alto";
  descripcion: string;
}


export interface ControlProceso {
  id: number;
  lote: number;
  lote_codigo: string;
  equipo: string;
  equipo_etiqueta: string;
  turno: string;
  fecha: string;
  hora_arranque: string | null;
  hora_inicio_produccion: string | null;
  hora_termino_produccion: string | null;
  pcc1_temp_min: string | null;
  pcc1_caudal_max: string | null;
  observacion: string;
  lecturas: LecturaControl[];
  /* Derivado, no guardado. */
  pcc1: {
    cumple: boolean;
    sin_limites: boolean;
    sin_lecturas: boolean;
    incumplimientos: IncumplimientoPcc1[];
  };
}


export interface LecturaPpro {
  id: number;
  monitoreo: number;
  hora: string;
  resultado: "ok" | "no_ok";
  resultado_etiqueta: string;
  detalle: Record<string, unknown>;
}


export interface MonitoreoPpro {
  id: number;
  lote: number;
  lote_codigo: string;
  tipo: string;
  tipo_etiqueta: string;
  equipo: string;
  turno: string;
  fecha: string;
  accion_correctiva: string;
  lecturas: LecturaPpro[];
  /* Derivados. `resuelto` es falso solo cuando hay No-OK y falta la acción
     correctiva: es lo que bloquea la liberación. */
  tiene_no_ok: boolean;
  resuelto: boolean;
}


export async function obtenerCatalogosInocuidad(): Promise<CatalogosInocuidad> {
  const { data } = await api.get<CatalogosInocuidad>(
    "produccion/catalogos-inocuidad/",
  );

  return data;
}


export async function obtenerControles(lote: number): Promise<ControlProceso[]> {
  const { data } = await api.get<Pagina<ControlProceso>>(
    "produccion/controles/",
    { params: { lote } },
  );

  return data.results;
}


export async function crearControl(
  datos: Record<string, unknown>,
): Promise<ControlProceso> {

  const { data } = await api.post<ControlProceso>("produccion/controles/", datos);

  return data;
}


export async function crearLecturaControl(
  datos: Record<string, unknown>,
): Promise<LecturaControl> {

  const { data } = await api.post<LecturaControl>(
    "produccion/lecturas-control/",
    datos,
  );

  return data;
}


export async function borrarLecturaControl(id: number): Promise<void> {
  await api.delete(`produccion/lecturas-control/${id}/`);
}


export async function obtenerMonitoreos(lote: number): Promise<MonitoreoPpro[]> {
  const { data } = await api.get<Pagina<MonitoreoPpro>>("inocuidad/monitoreos/", {
    params: { lote },
  });

  return data.results;
}


export async function crearMonitoreo(
  datos: Record<string, unknown>,
): Promise<MonitoreoPpro> {

  const { data } = await api.post<MonitoreoPpro>("inocuidad/monitoreos/", datos);

  return data;
}


export async function editarMonitoreo(
  id: number,
  cambios: Record<string, unknown>,
): Promise<MonitoreoPpro> {

  const { data } = await api.patch<MonitoreoPpro>(
    `inocuidad/monitoreos/${id}/`,
    cambios,
  );

  return data;
}


export async function crearLecturaPpro(
  datos: Record<string, unknown>,
): Promise<LecturaPpro> {

  const { data } = await api.post<LecturaPpro>("inocuidad/lecturas/", datos);

  return data;
}
