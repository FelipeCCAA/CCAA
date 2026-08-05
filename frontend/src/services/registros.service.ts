import api from "./api";

import type { Pagina } from "./produccion.service";
import type { CampoPlantilla } from "./calidad.service";


/*
  Registros que pertenecen al equipo y a su período, no a un lote.

  Un aseo semanal se llena una vez y cubre todos los lotes de esa semana. Antes
  había que teclearlo en cada lote —y cinco copias del mismo hecho pueden
  divergir— o registrarlo una vez y dejar los demás lotes sin poder liberarse
  aunque la máquina sí se aseó.

  La ventana la calcula el backend desde la frecuencia del documento: la
  pantalla no la reproduce, porque dos implementaciones de «semana» acabarían
  discrepando justo en el borde.
*/

export interface DocumentoPeriodico {
  id: number;
  codigo: string;
  nombre: string;
  area: string;
  frecuencia: string;
  frecuencia_etiqueta?: string;
  campos: number;
  plantilla: CampoPlantilla[];
}


export interface RegistroEquipo {
  id: number;
  documento: number;
  documento_nombre: string;
  documento_codigo: string;
  frecuencia: string;
  frecuencia_etiqueta: string;
  equipo: number | null;
  equipo_nombre: string | null;
  fecha: string;
  /* Solo para los «según programa»: hasta cuándo cubre. Sin esto no cubre
     nada, y el backend lo exige. */
  vigente_hasta: string | null;
  turno: string;
  valores: Record<string, unknown>;
  estado: "borrador" | "completado" | "observado";
  estado_etiqueta: string;
  observacion: string;
  completado_por: number | null;
  completado_en: string | null;
  completo: boolean;
  faltantes: string[];
}


export interface ConsultaRegistros {
  documento?: number;
  equipo?: number;
  desde?: string;
  hasta?: string;
  estado?: string;
}


export async function obtenerDocumentosPeriodicos(): Promise<DocumentoPeriodico[]> {
  const { data } = await api.get<DocumentoPeriodico[]>(
    "calidad/documentos-periodicos/",
  );

  return data;
}


export async function buscarRegistrosEquipo(
  consulta: ConsultaRegistros = {},
): Promise<RegistroEquipo[]> {

  const { data } = await api.get<Pagina<RegistroEquipo>>(
    "calidad/registros-equipo/",
    {
      params: {
        documento: consulta.documento || undefined,
        equipo: consulta.equipo || undefined,
        desde: consulta.desde || undefined,
        hasta: consulta.hasta || undefined,
        estado: consulta.estado || undefined,
      },
    },
  );

  return data.results;
}


export async function guardarRegistroEquipo(
  id: number | null,
  datos: Record<string, unknown>,
): Promise<RegistroEquipo> {

  const { data } = id
    ? await api.patch<RegistroEquipo>(`calidad/registros-equipo/${id}/`, datos)
    : await api.post<RegistroEquipo>("calidad/registros-equipo/", datos);

  return data;
}
