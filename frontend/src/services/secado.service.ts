import api from "./api";
import type { Pagina } from "./procesos.service";

export interface CorridaSecado {
  id: number;
  ejecucion: number;
  ejecucion_codigo: string;
  estado: string;
  estado_etiqueta: string;
  equipo_id: number | null;
  equipo_nombre: string | null;
  iniciada_en: string | null;
  lote: number;
  lote_codigo: string;
  producto_nombre: string;
  orden: number | null;
  orden_codigo: string | null;
  kg_alimentacion: string | null;
  solidos_entrada_pct: string | null;
  kg_polvo: string | null;
  kg_finos: string;
  kg_merma: string;
  controles: Record<string, unknown>;
  rendimiento_recuperacion_pct: string | null;
  finalizada_por: number | null;
  finalizada_en: string | null;
  requiere_calidad: boolean;
  estado_calidad: "no_requerida" | "pendiente" | "liberado" | "rechazado";
  operacion_id: string;
}

export interface CierreSecado {
  kg_alimentacion: number;
  solidos_entrada_pct: number;
  kg_polvo: number;
  kg_finos: number;
  kg_merma: number;
  controles: Record<string, number>;
}

export async function obtenerSecados(signal?: AbortSignal): Promise<Pagina<CorridaSecado>> {
  const { data } = await api.get<Pagina<CorridaSecado>>("procesos/secados/", { signal });
  return data;
}

export async function obtenerSecado(id: number, signal?: AbortSignal): Promise<CorridaSecado> {
  const { data } = await api.get<CorridaSecado>(`procesos/secados/${id}/`, { signal });
  return data;
}

export async function cerrarSecado(id: number, datos: CierreSecado): Promise<CorridaSecado> {
  const { data } = await api.post<CorridaSecado>(`procesos/secados/${id}/cerrar/`, datos);
  return data;
}
